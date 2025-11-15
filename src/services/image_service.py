"""
Image service.

Handles AI-generated bear-themed image creation using DALL-E 3.
Includes contextual prompt generation, retry logic, and Slack posting.
"""

import os
import random
import time
import requests
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pathlib import Path

from openai import OpenAI, OpenAIError, APIConnectionError, BadRequestError
from pybreaker import CircuitBreaker

from src.models.generated_image import GeneratedImage
from src.models.scheduled_task import TaskStatus
from src.repositories.team_member_repo import TeamMemberRepository
from src.repositories.conversation_repo import ConversationRepository
from src.utils.logger import logger
from src.utils.retry import retry_on_api_error
from src.services.scheduler_service import update_task_after_execution
from src.utils.config_loader import config


class ImageService:
    """
    Service for AI-generated bear image creation and posting.

    Features:
    - Contextual prompt generation (seasons, occasions)
    - DALL-E 3 integration with retry logic
    - Cost tracking
    - Slack channel posting
    - Circuit breaker for sustained failures
    - Graceful degradation
    """

    # DALL-E 3 pricing (as of 2025)
    DALLE3_COST_1024 = 0.040  # $0.040 per image at 1024x1024
    DALLE3_COST_HD = 0.080  # $0.080 per HD image

    # Local image storage directory
    IMAGES_DIR = Path(os.getenv('IMAGES_DIR', '/app/data/images'))

    # Seasonal themes by month
    SEASONAL_THEMES = {
        # Spring (March, April, May)
        3: ["spring", "flowers", "blooming", "nature", "fresh meadow"],
        4: ["spring", "rain showers", "rainbows", "april flowers", "garden"],
        5: ["late spring", "garden", "butterflies", "sunny day", "picnic"],
        # Summer (June, July, August)
        6: ["early summer", "warm sunshine", "beach", "outdoor adventure", "river"],
        7: ["summer", "july picnic", "watermelon", "swimming", "vacation"],
        8: ["late summer", "camping", "starry night", "sunset", "adventure"],
        # Fall (September, October, November)
        9: ["early autumn", "harvest", "apples", "cozy sweater", "foliage"],
        10: ["autumn", "falling leaves", "pumpkins", "halloween", "cozy"],
        11: ["late fall", "thanksgiving", "grateful", "warm home", "family"],
        # Winter (December, January, February)
        12: ["winter", "holiday", "snow", "christmas", "cozy fireplace"],
        1: ["new year", "winter wonderland", "snow", "ice skating", "cozy"],
        2: ["late winter", "valentine", "hearts", "warm hugs", "friendship"],
    }

    # Special occasions (month, day) -> theme
    SPECIAL_OCCASIONS = {
        (1, 1): "new_year",
        (2, 14): "valentines",
        (3, 17): "st_patricks",
        (7, 4): "independence_day",
        (10, 31): "halloween",
        (11, 25): "thanksgiving",  # Approximate
        (12, 25): "christmas",
        (12, 31): "new_years_eve",
    }

    # Occasion-specific prompt elements
    OCCASION_PROMPTS = {
        "new_year": "wearing a party hat, surrounded by confetti and balloons, celebrating the new year",
        "valentines": "holding a heart, surrounded by love and friendship symbols, sweet and caring",
        "st_patricks": "wearing green, surrounded by shamrocks and rainbows, lucky and cheerful",
        "independence_day": "at a summer picnic with red, white and blue decorations, patriotic and festive",
        "halloween": "wearing a cute costume, surrounded by pumpkins and autumn leaves, friendly and fun (not scary)",
        "thanksgiving": "at a cozy harvest feast, surrounded by pumpkins and autumn colors, grateful and warm",
        "christmas": "wearing a santa hat, near a decorated tree with presents, cozy holiday scene",
        "new_years_eve": "celebrating with sparklers and confetti, excited for new beginnings",
    }

    # Bear character traits (maintain personality)
    CHARACTER_TRAITS = [
        "friendly",
        "adorable",
        "whimsical",
        "charming",
        "cheerful",
        "cute",
        "lovable",
        "gentle",
    ]

    # Art style preferences (workplace appropriate)
    ART_STYLES = [
        "digital art",
        "watercolor illustration",
        "cartoon style",
        "storybook illustration",
        "whimsical art",
    ]

    # Forbidden words (content policy safety)
    FORBIDDEN_WORDS = [
        "violent",
        "scary",
        "aggressive",
        "dark",
        "creepy",
        "disturbing",
        "horror",
        "gore",
        "nsfw",
        "explicit",
    ]

    def __init__(
        self,
        db_session: Session,
        api_key: Optional[str] = None,
        slack_client: Optional[any] = None,
    ):
        """
        Initialize image service.

        Args:
            db_session: SQLAlchemy database session
            api_key: OpenAI API key (defaults to env OPENAI_API_KEY)
            slack_client: Slack WebClient instance (for posting images)
        """
        self.db_session = db_session
        self.slack_client = slack_client
        self.team_member_repo = TeamMemberRepository(db_session)
        self.conversation_repo = ConversationRepository(db_session)

        # Initialize OpenAI client
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OpenAI API key provided - image generation will fail")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)

        # Circuit breaker for sustained DALL-E failures
        self.circuit_breaker = CircuitBreaker(
            fail_max=5,
            reset_timeout=60,
            name="dalle_circuit_breaker"
        )

    def _get_or_create_bot_team_member(self):
        """
        Get or create a synthetic team member for the bot itself.

        This allows channel posts to be associated with a team member
        so they appear in the Activity Log.

        Returns:
            TeamMember representing Lukas the Bear bot
        """
        # Use a special Slack user ID for the bot itself
        # Get bot user ID from environment if available
        bot_user_id = os.getenv("SLACK_BOT_USER_ID", "LUKAS_BOT")

        return self.team_member_repo.get_or_create(
            slack_user_id=bot_user_id,
            display_name="Lukas the Bear (Bot)",
            real_name="Lukas",
            is_bot=True
        )

    def generate_contextual_prompt(
        self,
        theme: Optional[str] = None,
        occasion: Optional[str] = None,
    ) -> Tuple[str, Dict]:
        """
        Generate contextual DALL-E prompt based on season/occasion.

        Args:
            theme: Optional theme override (e.g., "spring", "autumn")
            occasion: Optional occasion override (e.g., "halloween")

        Returns:
            Tuple of (prompt_string, metadata_dict)
        """
        now = datetime.now()
        month = now.month
        day = now.day

        # Determine occasion
        if not occasion:
            occasion_key = (month, day)
            occasion = self.SPECIAL_OCCASIONS.get(occasion_key)

        # Determine theme (seasonal if not specified)
        if not theme:
            theme = random.choice(self.SEASONAL_THEMES.get(month, ["general"]))

        # Build prompt components
        character_trait = random.choice(self.CHARACTER_TRAITS)
        art_style = random.choice(self.ART_STYLES)

        # Base prompt
        prompt_parts = [
            f"A {character_trait} bear"
        ]

        # Add occasion-specific elements
        if occasion and occasion in self.OCCASION_PROMPTS:
            prompt_parts.append(self.OCCASION_PROMPTS[occasion])
        else:
            # Add seasonal elements
            prompt_parts.append(f"in a {theme} setting")

        # Add quality modifiers
        prompt_parts.append(f"{art_style}, high quality, detailed, professional")

        # Combine into final prompt
        prompt = ", ".join(prompt_parts)

        # Create metadata
        metadata = {
            "theme": theme,
            "occasion": occasion,
            "generated_at": now.isoformat(),
            "month": month,
            "day": day,
        }

        logger.info(f"Generated prompt: {prompt}")
        logger.info(f"Prompt metadata: {metadata}")

        return prompt, metadata

    def validate_prompt(self, prompt: str) -> Tuple[bool, Optional[str]]:
        """
        Validate prompt before sending to DALL-E.

        Args:
            prompt: The prompt to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check not empty
        if not prompt or len(prompt.strip()) == 0:
            return False, "Prompt is empty"

        # Check minimum length
        word_count = len(prompt.split())
        if word_count < 3:
            return False, f"Prompt too short ({word_count} words, minimum 3)"

        # Check maximum length
        if word_count > 100:
            return False, f"Prompt too long ({word_count} words, maximum 100)"

        # Check for forbidden words
        prompt_lower = prompt.lower()
        for forbidden in self.FORBIDDEN_WORDS:
            if forbidden in prompt_lower:
                return False, f"Prompt contains forbidden word: {forbidden}"

        return True, None

    @retry_on_api_error(max_attempts=3, min_wait=1, max_wait=10)
    def _generate_image_with_retry(self, prompt: str) -> Dict:
        """
        Generate image with retry logic (called by circuit breaker).

        Args:
            prompt: DALL-E prompt

        Returns:
            Dict with 'url' and 'created' keys

        Raises:
            OpenAIError: On API failures
        """
        if not self.client:
            raise OpenAIError("OpenAI client not initialized (missing API key)")

        start_time = time.time()

        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            duration = time.time() - start_time

            logger.info(f"DALL-E image generated successfully in {duration:.2f}s")

            return {
                "url": response.data[0].url,
                "created": response.created,
                "duration": duration,
            }

        except BadRequestError as e:
            # Content policy violation or bad prompt
            logger.error(f"DALL-E bad request: {e}")
            raise

        except APIConnectionError as e:
            # Network/connection issues - retryable
            logger.warning(f"DALL-E connection error (will retry): {e}")
            raise

        except OpenAIError as e:
            # Other OpenAI errors
            logger.error(f"DALL-E error: {e}")
            raise

    def download_and_save_image(
        self,
        image_url: str,
        image_id: str
    ) -> Optional[str]:
        """
        Download image from URL and save to local filesystem.

        Args:
            image_url: URL of the image to download (from DALL-E)
            image_id: Unique identifier for the image

        Returns:
            Local file path if successful, None otherwise
        """
        try:
            # Ensure images directory exists
            self.IMAGES_DIR.mkdir(parents=True, exist_ok=True)

            # Download image
            logger.info(f"Downloading image from {image_url}")
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            # Save to local file
            local_path = self.IMAGES_DIR / f"{image_id}.png"
            local_path.write_bytes(response.content)

            logger.info(f"Image saved locally to {local_path}")
            return str(local_path)

        except Exception as e:
            logger.error(f"Failed to download and save image {image_id}: {e}")
            return None

    async def generate_and_store_image(
        self,
        theme: Optional[str] = None,
        occasion: Optional[str] = None,
    ) -> Optional[GeneratedImage]:
        """
        Generate bear image and store in database.

        Args:
            theme: Optional theme (e.g., "spring", "autumn")
            occasion: Optional occasion (e.g., "halloween")

        Returns:
            GeneratedImage record (status='generated' or 'failed')
        """
        # Generate contextual prompt
        prompt, metadata = self.generate_contextual_prompt(theme, occasion)

        # Validate prompt
        is_valid, error_msg = self.validate_prompt(prompt)
        if not is_valid:
            logger.error(f"Prompt validation failed: {error_msg}")
            # Create failed record
            image_record = GeneratedImage(
                prompt=prompt,
                image_url="",
                status="failed",
                error_message=f"Prompt validation failed: {error_msg}",
                meta=metadata,
            )
            self.db_session.add(image_record)
            self.db_session.commit()
            return image_record

        # Generate image with circuit breaker
        try:
            result = self.circuit_breaker.call(
                self._generate_image_with_retry,
                prompt
            )

            # Create initial record (need ID for file path)
            image_record = GeneratedImage(
                prompt=prompt,
                image_url=result["url"],  # Store original Azure URL temporarily
                status="generated",
                generation_duration_seconds=result["duration"],
                cost_usd=self.DALLE3_COST_1024,  # Standard quality
                meta=metadata,
            )

            self.db_session.add(image_record)
            self.db_session.flush()  # Get the ID without committing

            # Download and save image locally
            local_path = self.download_and_save_image(
                image_url=result["url"],
                image_id=image_record.id
            )

            # Update record with local path (keep Azure URL in metadata for reference)
            if local_path:
                if image_record.meta is None:
                    image_record.meta = {}
                image_record.meta['original_url'] = result["url"]
                flag_modified(image_record, 'meta')  # Tell SQLAlchemy the JSON field changed
                image_record.image_url = local_path
                logger.info(f"Image saved locally: {local_path}")
            else:
                logger.warning(f"Failed to save locally, keeping Azure URL: {result['url']}")

            self.db_session.commit()

            logger.info(f"Image generated and stored: {image_record.id}")
            return image_record

        except BadRequestError as e:
            # Content policy violation
            error_message = f"Content policy violation: {str(e)}"
            logger.error(error_message)

            image_record = GeneratedImage(
                prompt=prompt,
                image_url="",
                status="failed",
                error_message=error_message,
                meta=metadata,
            )
            self.db_session.add(image_record)
            self.db_session.commit()
            return image_record

        except OpenAIError as e:
            # API failure after retries
            error_message = f"DALL-E API error: {str(e)}"
            logger.error(error_message)

            image_record = GeneratedImage(
                prompt=prompt,
                image_url="",
                status="failed",
                error_message=error_message,
                meta=metadata,
            )
            self.db_session.add(image_record)
            self.db_session.commit()
            return image_record

        except Exception as e:
            # Circuit breaker open or other failure
            error_message = f"Image generation failed: {str(e)}"
            logger.error(error_message)

            image_record = GeneratedImage(
                prompt=prompt,
                image_url="",
                status="failed",
                error_message=error_message,
                meta=metadata,
            )
            self.db_session.add(image_record)
            self.db_session.commit()
            return image_record

    def generate_caption(
        self,
        image_record: GeneratedImage
    ) -> str:
        """
        Generate friendly caption for image post.

        Args:
            image_record: The generated image record

        Returns:
            Caption string in Lukas's voice
        """
        metadata = image_record.meta or {}
        theme = metadata.get("theme", "general")
        occasion = metadata.get("occasion")

        # Occasion-specific captions
        occasion_captions = {
            "new_year": "Happy New Year, everyone! Here's to new adventures!",
            "valentines": "Sending some bear hugs your way! Happy Valentine's Day!",
            "st_patricks": "Feeling lucky today! Happy St. Patrick's Day!",
            "independence_day": "Hope everyone's having a great summer picnic!",
            "halloween": "Happy Halloween! Don't worry, I'm a friendly bear!",
            "thanksgiving": "Grateful for all of you! Happy Thanksgiving!",
            "christmas": "Merry Christmas! Wishing you all a cozy holiday!",
            "new_years_eve": "Can't wait to see what next year brings!",
        }

        if occasion and occasion in occasion_captions:
            return occasion_captions[occasion]

        # Seasonal captions
        seasonal_captions = [
            f"Just enjoying this beautiful {theme} day!",
            f"Thought you all might like this {theme} scene!",
            f"Here's your weekly dose of bear charm!",
            f"Hope this brightens your day!",
            f"Just being my usual adorable self!",
        ]

        return random.choice(seasonal_captions)

    def _post_to_slack(
        self,
        channel_id: str,
        image_path: str,
        caption: str,
        original_url: Optional[str] = None
    ) -> Dict:
        """
        Post image to Slack channel.

        Args:
            channel_id: Slack channel ID
            image_path: Path to image file (local or URL)
            caption: Caption text
            original_url: Optional original DALL-E URL (used if available)

        Returns:
            Slack API response dict

        Raises:
            Exception: On Slack API failure
        """
        if not self.slack_client:
            raise Exception("Slack client not configured")

        # Prefer original URL if available (works without files:write permission)
        # Otherwise use the provided path
        url_to_use = original_url if original_url else image_path

        # Check if we have a URL (original or otherwise)
        if url_to_use and url_to_use.startswith('http'):
            # It's a URL - use it directly in image block (no files:write needed)
            response = self.slack_client.chat_postMessage(
                channel=channel_id,
                text=caption,
                blocks=[
                    {
                        "type": "image",
                        "image_url": url_to_use,
                        "alt_text": "Bear image from Lukas"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": caption
                        }
                    }
                ]
            )
        else:
            # It's a local file - upload to Slack (requires files:write scope)
            logger.warning("Attempting file upload - requires files:write scope")
            with open(image_path, 'rb') as file:
                response = self.slack_client.files_upload_v2(
                    channel=channel_id,
                    file=file,
                    title="Bear image from Lukas",
                    initial_comment=caption
                )

        return response

    async def post_image_to_channel(
        self,
        image_record: GeneratedImage,
        channel_id: str,
        caption: Optional[str] = None,
    ) -> bool:
        """
        Post generated image to Slack channel.

        Args:
            image_record: The generated image record
            channel_id: Slack channel ID
            caption: Optional custom caption

        Returns:
            True if posted successfully, False otherwise
        """
        if image_record.status != "generated":
            logger.error(f"Cannot post image {image_record.id} with status {image_record.status}")
            return False

        # Generate caption if not provided
        if not caption:
            caption = self.generate_caption(image_record)

        try:
            # Get original URL from metadata (if available)
            original_url = None
            if image_record.meta and 'original_url' in image_record.meta:
                original_url = image_record.meta['original_url']
                logger.info(f"Found original URL in metadata: {original_url[:100]}...")
            else:
                logger.warning(f"No original URL found. Meta: {image_record.meta}, image_url: {image_record.image_url}")

            # Post to Slack
            response = self._post_to_slack(
                channel_id=channel_id,
                image_path=image_record.image_url,
                caption=caption,
                original_url=original_url
            )

            # Update record
            image_record.status = "posted"
            image_record.posted_to_channel = channel_id
            image_record.posted_at = datetime.now()

            # Store Slack message timestamp in metadata
            if image_record.meta is None:
                image_record.meta = {}
            image_record.meta["slack_ts"] = response.get("ts")
            flag_modified(image_record, 'meta')  # Tell SQLAlchemy the JSON field changed

            self.db_session.commit()

            # Save message to database for Activity Log
            try:
                # Get or create bot team member
                bot_member = self._get_or_create_bot_team_member()

                # Get or create conversation for this channel
                conversation = self.conversation_repo.get_or_create_conversation(
                    team_member_id=bot_member.id,
                    channel_type="channel",
                    channel_id=channel_id,
                    thread_ts=None
                )

                # Save bot message to database (use caption as content)
                slack_ts = response.get("ts")
                message_content = f"[Image] {caption}"  # Prefix to indicate it's an image post
                self.conversation_repo.add_message(
                    conversation_id=conversation.id,
                    sender_type="bot",
                    content=message_content,
                    slack_ts=slack_ts,
                    token_count=len(caption.split()),  # Rough estimate
                    metadata={
                        "posted_via": "image_post",
                        "image_id": image_record.id,
                        "prompt": image_record.prompt
                    }
                )
                logger.info(f"Saved image post to database (conversation {conversation.id})")
            except Exception as e:
                # Log error but don't fail the operation - image was posted successfully
                logger.error(f"Failed to save image post to database: {e}")

            logger.info(f"Image {image_record.id} posted to {channel_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to post image to Slack: {e}")
            return False

    async def generate_and_post(
        self,
        channel_id: str,
        theme: Optional[str] = None,
        occasion: Optional[str] = None,
    ) -> Optional[GeneratedImage]:
        """
        Generate and post image in one operation (for scheduled tasks).

        Args:
            channel_id: Slack channel ID to post to
            theme: Optional theme
            occasion: Optional occasion

        Returns:
            GeneratedImage record if successful, None otherwise
        """
        # Generate image
        image_record = await self.generate_and_store_image(theme, occasion)

        if not image_record or image_record.status != "generated":
            logger.error("Image generation failed, cannot post")
            # Update task record to failed
            interval_days = config.get("bot.image_posting.interval_days", 7)
            update_task_after_execution(
                job_id="image_post_task",
                status=TaskStatus.FAILED,
                error_message="Image generation failed",
                next_run_interval_days=interval_days
            )
            return image_record

        # Post to channel
        success = await self.post_image_to_channel(
            image_record=image_record,
            channel_id=channel_id
        )

        # Update task record based on success
        interval_days = config.get("bot.image_posting.interval_days", 7)
        if success:
            logger.info(f"Successfully generated and posted image {image_record.id}")
            update_task_after_execution(
                job_id="image_post_task",
                status=TaskStatus.COMPLETED,
                next_run_interval_days=interval_days
            )
        else:
            logger.error(f"Image generated but posting failed: {image_record.id}")
            update_task_after_execution(
                job_id="image_post_task",
                status=TaskStatus.FAILED,
                error_message="Failed to post image to Slack",
                next_run_interval_days=interval_days
            )

        return image_record


# Global service instance (initialized in bot.py with Slack client)
image_service: Optional[ImageService] = None
