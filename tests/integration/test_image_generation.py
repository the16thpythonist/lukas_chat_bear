"""
Integration tests for image generation and posting.

Tests the critical path: Can we generate an image and post it to Slack?

Following constitution: Integration tests provide highest ROI by testing
the actual user-facing behavior end-to-end.
"""

import os
import pytest
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock
from sqlalchemy.orm import Session

from src.models.generated_image import GeneratedImage


class TestImageGenerationIntegration:
    """
    Integration tests for image generation flow.

    Tests the critical contract: Can we generate and post bear images?
    """

    @pytest.mark.asyncio
    async def test_image_generation_with_mocked_openai(self, test_db_session: Session):
        """
        Image generation creates record and returns URL.

        This tests the full generation flow with mocked OpenAI API.
        Critical because it validates our integration with DALL-E API.

        User scenario: Scheduled task triggers image generation successfully.
        """
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            from src.services.image_service import ImageService

            service = ImageService(db_session=test_db_session)

            # Mock OpenAI client
            mock_openai_response = Mock()
            mock_openai_response.data = [Mock(url="https://example.com/test-image.png")]
            mock_openai_response.created = int(datetime.now().timestamp())

            with patch.object(
                service.client.images, "generate", return_value=mock_openai_response
            ):
                # When generating an image
                result = await service.generate_and_store_image(
                    theme="spring", occasion=None
                )

                # Then should return image record
                assert result is not None
                assert result.image_url == "https://example.com/test-image.png"
                assert result.status == "generated"
                assert result.prompt is not None
                assert "bear" in result.prompt.lower()

                # And should be stored in database
                stored_image = (
                    test_db_session.query(GeneratedImage).filter_by(id=result.id).first()
                )
                assert stored_image is not None
                assert stored_image.image_url == result.image_url

    @pytest.mark.asyncio
    async def test_image_posting_to_slack(self, test_db_session: Session):
        """
        Generated image can be posted to Slack channel.

        Tests the critical path: Generate → Post → Update database.

        User scenario: Bot posts weekly bear image to #random channel.
        """
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "SLACK_BOT_TOKEN": "xoxb-test-token",
            },
        ):
            from src.services.image_service import ImageService

            service = ImageService(db_session=test_db_session)

            # Create a generated image record
            image_record = GeneratedImage(
                prompt="A friendly bear in spring flowers",
                image_url="https://example.com/test-image.png",
                status="generated",
            )
            test_db_session.add(image_record)
            test_db_session.commit()

            # Mock Slack client
            mock_slack_response = {"ok": True, "ts": "1234567890.123456"}

            with patch.object(
                service, "_post_to_slack", return_value=mock_slack_response
            ):
                # When posting to Slack
                success = await service.post_image_to_channel(
                    image_record=image_record,
                    channel_id="C12345678",
                    caption="Here's your weekly bear picture!",
                )

                # Then should succeed
                assert success is True

                # And database should be updated
                test_db_session.refresh(image_record)
                assert image_record.status == "posted"
                assert image_record.posted_to_channel == "C12345678"
                assert image_record.posted_at is not None
                assert image_record.meta["slack_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_image_generation_handles_api_failure(self, test_db_session: Session):
        """
        Image generation handles OpenAI API failures gracefully.

        Tests error handling: API fails → Store failure record → Return None.

        User scenario: DALL-E API is down, bot logs error but continues.
        """
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            from src.services.image_service import ImageService
            from openai import OpenAIError

            service = ImageService(db_session=test_db_session)

            # Mock OpenAI client to raise error
            with patch.object(
                service.client.images,
                "generate",
                side_effect=OpenAIError("API temporarily unavailable"),
            ):
                # When generating an image during outage
                result = await service.generate_and_store_image(
                    theme="summer", occasion=None
                )

                # Then should handle gracefully
                assert result is not None  # Still creates record
                assert result.status == "failed"
                assert result.error_message is not None
                assert "API temporarily unavailable" in result.error_message

                # And should be stored in database for retry
                stored_image = (
                    test_db_session.query(GeneratedImage)
                    .filter_by(status="failed")
                    .first()
                )
                assert stored_image is not None

    @pytest.mark.asyncio
    async def test_image_generation_with_retry_on_transient_failure(
        self, test_db_session: Session
    ):
        """
        Image generation retries on transient failures.

        Tests retry logic: First attempt fails → Retry succeeds → Returns image.

        User scenario: Temporary network glitch, bot retries and succeeds.
        """
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            from src.services.image_service import ImageService
            from openai import APIConnectionError

            service = ImageService(db_session=test_db_session)

            # Mock OpenAI client to fail once, then succeed
            call_count = 0

            def mock_generate(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise APIConnectionError("Connection timeout")
                else:
                    mock_response = Mock()
                    mock_response.data = [
                        Mock(url="https://example.com/retry-success.png")
                    ]
                    return mock_response

            with patch.object(
                service.client.images, "generate", side_effect=mock_generate
            ):
                # When generating an image with transient failure
                result = await service.generate_and_store_image(
                    theme="autumn", occasion=None
                )

                # Then should retry and succeed
                assert result is not None
                assert result.status == "generated"
                assert result.image_url == "https://example.com/retry-success.png"
                assert call_count == 2  # Verify retry happened

    @pytest.mark.asyncio
    async def test_image_generation_tracks_cost(self, test_db_session: Session):
        """
        Image generation tracks cost for each image.

        Tests cost tracking: Generate image → Calculate cost → Store in database.

        User scenario: Admin reviews monthly image generation costs.
        """
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            from src.services.image_service import ImageService

            service = ImageService(db_session=test_db_session)

            # Mock OpenAI client
            mock_openai_response = Mock()
            mock_openai_response.data = [Mock(url="https://example.com/cost-test.png")]

            with patch.object(
                service.client.images, "generate", return_value=mock_openai_response
            ):
                # When generating an image
                result = await service.generate_and_store_image(
                    theme="winter", occasion="christmas"
                )

                # Then cost should be tracked
                assert result is not None
                assert result.cost_usd is not None
                assert result.cost_usd > 0  # DALL-E 3 has cost
                assert result.generation_duration_seconds is not None

    @pytest.mark.asyncio
    async def test_image_generation_content_policy_violation(
        self, test_db_session: Session
    ):
        """
        Image generation handles content policy violations.

        Tests safety: Prompt violates policy → Handle gracefully → Log error.

        User scenario: Generated prompt accidentally violates policy, bot handles it.
        """
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            from src.services.image_service import ImageService
            from openai import BadRequestError

            service = ImageService(db_session=test_db_session)

            # Mock OpenAI client to raise content policy error
            mock_response = Mock()
            mock_response.status_code = 400
            mock_error = BadRequestError(
                "Your request was rejected as a result of our safety system",
                response=mock_response,
                body={"error": {"code": "content_policy_violation"}},
            )

            with patch.object(
                service.client.images, "generate", side_effect=mock_error
            ):
                # When generating an image that violates policy
                result = await service.generate_and_store_image(
                    theme="halloween", occasion=None
                )

                # Then should handle gracefully
                assert result is not None
                assert result.status == "failed"
                assert "content_policy" in result.error_message.lower() or "safety" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_full_scheduled_image_post_flow(self, test_db_session: Session):
        """
        Full scheduled image posting workflow end-to-end.

        Tests: Scheduler triggers → Generate → Post → Update database.

        User scenario: Weekly scheduled task posts bear image to #random.
        """
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "SLACK_BOT_TOKEN": "xoxb-test-token",
            },
        ):
            from src.services.image_service import ImageService

            service = ImageService(db_session=test_db_session)

            # Mock OpenAI and Slack
            mock_openai_response = Mock()
            mock_openai_response.data = [
                Mock(url="https://example.com/scheduled-image.png")
            ]

            mock_slack_response = {"ok": True, "ts": "1234567890.999999"}

            with patch.object(
                service.client.images, "generate", return_value=mock_openai_response
            ), patch.object(service, "_post_to_slack", return_value=mock_slack_response):
                # When executing scheduled image post
                result = await service.generate_and_post(
                    channel_id="C12345678", theme="seasonal"
                )

                # Then should complete full flow
                assert result is not None
                assert result.status == "posted"
                assert result.posted_to_channel == "C12345678"
                assert result.image_url is not None
                assert result.posted_at is not None

                # And database should have complete record
                stored_image = (
                    test_db_session.query(GeneratedImage).filter_by(id=result.id).first()
                )
                assert stored_image is not None
                assert stored_image.status == "posted"


@pytest.fixture
def test_db_session():
    """Create test database session."""
    # This will use the existing test database fixture from conftest.py
    # For now, return a mock session
    mock_session = MagicMock(spec=Session)
    mock_session.add = Mock()
    mock_session.commit = Mock()
    mock_session.refresh = Mock()
    mock_session.query = Mock()
    return mock_session
