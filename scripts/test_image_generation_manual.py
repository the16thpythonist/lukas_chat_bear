#!/usr/bin/env python3
"""
Manual test script for DALL-E image generation.

This script actually generates real bear images using the DALL-E API.
Cost: ~$0.04 per image generated.

Usage:
    python scripts/test_image_generation_manual.py [--theme THEME] [--occasion OCCASION]

Examples:
    python scripts/test_image_generation_manual.py
    python scripts/test_image_generation_manual.py --theme "autumn"
    python scripts/test_image_generation_manual.py --occasion "halloween"
    python scripts/test_image_generation_manual.py --theme "winter" --occasion "christmas"
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime
import requests

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.services.image_service import ImageService
from src.utils.database import get_db, init_db
from src.utils.logger import logger


def download_image(url: str, output_dir: Path) -> Path:
    """
    Download image from URL and save locally.

    Args:
        url: Image URL
        output_dir: Directory to save image

    Returns:
        Path to saved image
    """
    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bear_image_{timestamp}.png"
    output_path = output_dir / filename

    # Download image
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    # Save to file
    with open(output_path, "wb") as f:
        f.write(response.content)

    return output_path


async def test_image_generation(theme: str = None, occasion: str = None):
    """
    Test real image generation with DALL-E API.

    Args:
        theme: Optional theme (e.g., "spring", "autumn")
        occasion: Optional occasion (e.g., "halloween", "christmas")
    """
    print("=" * 80)
    print("DALL-E Image Generation Manual Test")
    print("=" * 80)
    print()

    # Load environment variables
    load_dotenv()

    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in environment")
        print("Please set OPENAI_API_KEY in your .env file")
        return False

    print(f"✅ OpenAI API key found: {api_key[:10]}...{api_key[-4:]}")
    print()

    # Initialize database
    print("📊 Initializing database...")
    init_db()
    print("✅ Database initialized")
    print()

    # Create output directory
    output_dir = project_root / "test_images"
    output_dir.mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir}")
    print()

    # Initialize image service
    print("🖼️  Initializing image service...")
    with get_db() as db:
        service = ImageService(
            db_session=db,
            api_key=api_key,
            slack_client=None  # Not posting to Slack
        )
        print("✅ Image service initialized")
        print()

        # Generate prompt
        print("🎨 Generating contextual prompt...")
        prompt, metadata = service.generate_contextual_prompt(
            theme=theme,
            occasion=occasion
        )

        print(f"Theme: {metadata.get('theme', 'N/A')}")
        print(f"Occasion: {metadata.get('occasion', 'N/A')}")
        print(f"Month/Day: {metadata.get('month')}/{metadata.get('day')}")
        print(f"Prompt: {prompt}")
        print()

        # Validate prompt
        print("✔️  Validating prompt...")
        is_valid, error_msg = service.validate_prompt(prompt)
        if not is_valid:
            print(f"❌ ERROR: Prompt validation failed: {error_msg}")
            return False
        print("✅ Prompt is valid")
        print()

        # Generate image
        print("🎨 Generating image with DALL-E 3...")
        print("⚠️  This will cost approximately $0.04")
        print("⏳ Please wait (this may take 10-30 seconds)...")
        print()

        try:
            image_record = await service.generate_and_store_image(
                theme=theme,
                occasion=occasion
            )

            if image_record.status != "generated":
                print(f"❌ ERROR: Image generation failed")
                print(f"Status: {image_record.status}")
                print(f"Error: {image_record.error_message}")
                return False

            # Success!
            print("✅ Image generated successfully!")
            print()
            print("-" * 80)
            print("RESULT")
            print("-" * 80)
            print(f"Image ID: {image_record.id}")
            print(f"Status: {image_record.status}")
            print(f"Prompt: {image_record.prompt}")
            print(f"URL: {image_record.image_url}")
            print(f"Cost: ${image_record.cost_usd:.4f}")
            print(f"Duration: {image_record.generation_duration_seconds:.2f}s")
            print(f"Created: {image_record.created_at}")
            print()

            # Download image
            print("💾 Downloading image...")
            try:
                image_path = download_image(image_record.image_url, output_dir)
                print(f"✅ Image saved to: {image_path}")
                print()

                # Display file info
                file_size = os.path.getsize(image_path)
                print(f"File size: {file_size / 1024:.2f} KB")
                print()

            except Exception as e:
                print(f"⚠️  Warning: Could not download image: {e}")
                print(f"You can still view it at: {image_record.image_url}")
                print()

            # Generate caption
            caption = service.generate_caption(image_record)
            print(f"Caption: {caption}")
            print()

            print("=" * 80)
            print("✅ TEST PASSED")
            print("=" * 80)
            return True

        except Exception as e:
            print(f"❌ ERROR: {e}")
            logger.exception("Image generation failed")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manual test for DALL-E bear image generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate seasonal image (based on current date)
  python scripts/test_image_generation_manual.py

  # Generate autumn-themed image
  python scripts/test_image_generation_manual.py --theme autumn

  # Generate Halloween image
  python scripts/test_image_generation_manual.py --occasion halloween

  # Generate winter Christmas image
  python scripts/test_image_generation_manual.py --theme winter --occasion christmas

Available themes: spring, summer, autumn, winter, flowers, snow, etc.
Available occasions: halloween, christmas, thanksgiving, valentines, new_year, etc.
        """
    )

    parser.add_argument(
        "--theme",
        type=str,
        help="Image theme (e.g., 'autumn', 'winter', 'spring')"
    )

    parser.add_argument(
        "--occasion",
        type=str,
        help="Special occasion (e.g., 'halloween', 'christmas')"
    )

    args = parser.parse_args()

    # Run async test
    success = asyncio.run(test_image_generation(
        theme=args.theme,
        occasion=args.occasion
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
