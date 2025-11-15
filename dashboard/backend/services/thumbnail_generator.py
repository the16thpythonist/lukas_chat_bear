"""
Thumbnail generation utility for image gallery.
Generates and caches 300x300px thumbnails from original images.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import logging
import os
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

# Thumbnail configuration
THUMBNAIL_SIZE = (300, 300)
THUMBNAIL_QUALITY = 85
THUMBNAIL_DIR = Path(os.getenv('THUMBNAIL_DIR', '/app/thumbnails'))


def generate_placeholder_thumbnail(image_id: int, message: str = "Image URL Expired") -> Path:
    """
    Generate a placeholder thumbnail when the original image is unavailable.

    Args:
        image_id: ID of the image
        message: Message to display on placeholder

    Returns:
        Path object for the generated placeholder thumbnail
    """
    thumbnail_path = get_thumbnail_path(image_id)

    # If placeholder already exists, return it
    if thumbnail_path.exists():
        return thumbnail_path

    logger.info(f"Generating placeholder thumbnail for image {image_id}")

    # Create a simple placeholder image
    img = Image.new('RGB', THUMBNAIL_SIZE, color=(240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Draw border
    border_color = (200, 200, 200)
    draw.rectangle([0, 0, THUMBNAIL_SIZE[0]-1, THUMBNAIL_SIZE[1]-1], outline=border_color, width=2)

    # Draw diagonal lines for "missing image" pattern
    for i in range(0, THUMBNAIL_SIZE[0] + THUMBNAIL_SIZE[1], 40):
        draw.line([(i, 0), (0, i)], fill=(220, 220, 220), width=1)
        draw.line([(THUMBNAIL_SIZE[0], i - THUMBNAIL_SIZE[0]), (i - THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1])], fill=(220, 220, 220), width=1)

    # Add text
    text_lines = ["Image", "Unavailable", "", message]

    # Try to use a font, fall back to default if not available
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    y_offset = 80
    for i, line in enumerate(text_lines):
        if i < 2:
            current_font = font
            color = (100, 100, 100)
        else:
            current_font = small_font
            color = (150, 150, 150)

        # Get text bounding box
        bbox = draw.textbbox((0, 0), line, font=current_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Center text
        x = (THUMBNAIL_SIZE[0] - text_width) // 2
        y = y_offset

        draw.text((x, y), line, fill=color, font=current_font)
        y_offset += text_height + 10

    # Save placeholder
    img.save(thumbnail_path, 'JPEG', quality=THUMBNAIL_QUALITY)
    logger.info(f"Placeholder thumbnail generated for image {image_id}")

    return thumbnail_path


def get_thumbnail_path(image_id: int) -> Path:
    """
    Get the filesystem path for a thumbnail.

    Args:
        image_id: ID of the image

    Returns:
        Path object for the thumbnail file
    """
    # Ensure thumbnail directory exists
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    return THUMBNAIL_DIR / f"{image_id}.jpg"


def generate_thumbnail(image_url: str, image_id: int) -> Path:
    """
    Generate a thumbnail from an image URL and cache to filesystem.

    Args:
        image_url: URL of the original image
        image_id: ID of the image for cache filename

    Returns:
        Path object for the generated thumbnail

    Raises:
        FileNotFoundError: If image URL is not accessible
        Exception: If thumbnail generation fails
    """
    thumbnail_path = get_thumbnail_path(image_id)

    # If thumbnail already exists, return it
    if thumbnail_path.exists():
        logger.debug(f"Thumbnail cache hit for image {image_id}")
        return thumbnail_path

    logger.info(f"Generating thumbnail for image {image_id} from {image_url}")

    try:
        # Download image from URL
        if image_url.startswith('http'):
            # Remote URL
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            image_data = BytesIO(response.content)
        else:
            # Local file path
            image_data = image_url

        # Open and process image
        with Image.open(image_data) as img:
            # Convert to RGB if needed (handles PNG with transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Generate thumbnail (maintains aspect ratio)
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            # Save to cache
            img.save(thumbnail_path, 'JPEG', quality=THUMBNAIL_QUALITY, optimize=True)

        logger.info(f"Thumbnail generated successfully for image {image_id}")
        return thumbnail_path

    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to download image {image_id} from {image_url}: {e}")
        logger.info(f"Generating placeholder thumbnail for image {image_id}")
        # Generate placeholder for inaccessible images (expired URLs, network errors, etc.)
        if '409' in str(e) or '403' in str(e) or '404' in str(e):
            message = "URL Expired"
        else:
            message = "URL Inaccessible"
        return generate_placeholder_thumbnail(image_id, message)
    except Exception as e:
        logger.error(f"Failed to generate thumbnail for image {image_id}: {e}")
        # Generate placeholder for any other errors
        return generate_placeholder_thumbnail(image_id, "Generation Failed")


def clear_thumbnail_cache(image_id: int = None):
    """
    Clear thumbnail cache for a specific image or all images.

    Args:
        image_id: ID of the image to clear, or None to clear all

    Returns:
        Number of thumbnails removed
    """
    count = 0

    if image_id is not None:
        # Remove specific thumbnail
        thumbnail_path = get_thumbnail_path(image_id)
        if thumbnail_path.exists():
            thumbnail_path.unlink()
            count = 1
            logger.info(f"Cleared thumbnail for image {image_id}")
    else:
        # Remove all thumbnails
        if THUMBNAIL_DIR.exists():
            for thumbnail_file in THUMBNAIL_DIR.glob('*.jpg'):
                thumbnail_file.unlink()
                count += 1
            logger.info(f"Cleared {count} thumbnails from cache")

    return count


def cleanup_orphaned_thumbnails(session):
    """
    Remove thumbnails for images that no longer exist in the database.

    Args:
        session: SQLAlchemy session

    Returns:
        Number of orphaned thumbnails removed
    """
    from backend.models import GeneratedImage

    count = 0

    if not THUMBNAIL_DIR.exists():
        return count

    # Get all image IDs from database
    valid_ids = set(
        row[0] for row in session.query(GeneratedImage.id).all()
    )

    # Check all thumbnail files
    for thumbnail_file in THUMBNAIL_DIR.glob('*.jpg'):
        try:
            # Extract image ID from filename
            image_id = int(thumbnail_file.stem)

            # Remove if not in database
            if image_id not in valid_ids:
                thumbnail_file.unlink()
                count += 1
                logger.debug(f"Removed orphaned thumbnail for deleted image {image_id}")
        except (ValueError, OSError) as e:
            logger.warning(f"Error processing thumbnail file {thumbnail_file}: {e}")

    if count > 0:
        logger.info(f"Cleaned up {count} orphaned thumbnails")

    return count
