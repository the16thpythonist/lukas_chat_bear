"""
Image gallery routes for dashboard backend.
Provides endpoints for viewing generated image history and thumbnails.
"""
from flask import Blueprint, request, jsonify, send_file
from backend.auth import require_auth
from backend.services import get_session, paginate, build_images_query
from backend.services.thumbnail_generator import generate_thumbnail, get_thumbnail_path
from backend.utils.errors import handle_exception, not_found_error
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

images_bp = Blueprint('images', __name__)


@images_bp.route('', methods=['GET'])
@require_auth
def list_images():
    """
    Get paginated list of generated images with optional filters.

    Query Parameters:
        page (int): Page number (default: 1)
        limit (int): Items per page (default: 20, max: 100)
        start_date (str): Filter images after this date (ISO format)
        end_date (str): Filter images before this date (ISO format)
        status (str): Filter by status ('pending', 'posted', 'failed')

    Returns:
        200: Paginated list of images with metadata
        500: Database error
    """
    try:
        # Parse query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)

        # Build filters
        filters = {}
        if request.args.get('start_date'):
            filters['start_date'] = request.args.get('start_date')
        if request.args.get('end_date'):
            filters['end_date'] = request.args.get('end_date')
        if request.args.get('status'):
            filters['status'] = request.args.get('status')

        # Get database session
        session = get_session()

        # Build and execute query
        query = build_images_query(session, filters)
        result = paginate(query, page, limit)

        # Format results
        items = []
        for row in result['items']:
            items.append({
                'id': row.id,
                'prompt': row.prompt,
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'status': row.status,
                'channel_id': row.posted_to_channel,
                'image_url': row.image_url,
                'thumbnail_url': f'/api/images/{row.id}/thumbnail',
                'error_message': row.error_message
            })

        return jsonify({
            'items': items,
            'page': result['page'],
            'limit': result['limit'],
            'total': result['total'],
            'pages': result['pages']
        }), 200

    except Exception as e:
        logger.exception(f"Error fetching images list: {e}")
        return handle_exception(e, include_details=False)


@images_bp.route('/<string:image_id>', methods=['GET'])
@require_auth
def get_image_detail(image_id):
    """
    Get detailed information about a specific image.

    Path Parameters:
        image_id (int): Image ID

    Returns:
        200: Image details with full prompt and metadata
        404: Image not found
        500: Database error
    """
    try:
        from backend.models import GeneratedImage

        session = get_session()

        # Get image
        image = session.query(GeneratedImage).filter(
            GeneratedImage.id == image_id
        ).first()

        if not image:
            return not_found_error('Image')

        return jsonify({
            'id': image.id,
            'prompt': image.prompt,
            'created_at': image.created_at.isoformat() if image.created_at else None,
            'posted_at': image.posted_at.isoformat() if image.posted_at else None,
            'status': image.status,
            'channel_id': image.posted_to_channel,
            'image_url': image.image_url,
            'thumbnail_url': f'/api/images/{image.id}/thumbnail',
            'error_message': image.error_message
        }), 200

    except Exception as e:
        logger.exception(f"Error fetching image detail: {e}")
        return handle_exception(e, include_details=False)


@images_bp.route('/<string:image_id>/full', methods=['GET'])
def get_full_image(image_id):
    """
    Get full-size image file.

    Path Parameters:
        image_id (str): Image ID

    Returns:
        200: Full-size image file
        404: Image not found or file missing
        500: Error serving image
    """
    try:
        from backend.models import GeneratedImage

        session = get_session()

        # Get image
        image = session.query(GeneratedImage).filter(
            GeneratedImage.id == image_id
        ).first()

        if not image:
            return not_found_error('Image')

        # Check if image file exists
        if not image.image_url:
            return jsonify({
                'error': 'Image not available',
                'message': 'This image has no URL'
            }), 404

        # Check if it's a local file path
        if not image.image_url.startswith('http'):
            # It's a local file
            image_path = Path(image.image_url)
            if not image_path.exists():
                return jsonify({
                    'error': 'Image file not found',
                    'message': 'The image file no longer exists on disk'
                }), 404

            # Serve the file
            response = send_file(
                image_path,
                mimetype='image/png',
                as_attachment=False
            )
            response.headers['Cache-Control'] = 'public, max-age=86400'  # 24 hours
            return response
        else:
            # It's a URL - redirect to it
            from flask import redirect
            return redirect(image.image_url)

    except Exception as e:
        logger.exception(f"Error serving full image: {e}")
        return handle_exception(e, include_details=False)


@images_bp.route('/<string:image_id>/thumbnail', methods=['GET'])
def get_thumbnail(image_id):
    """
    Get or generate thumbnail for an image.

    Path Parameters:
        image_id (int): Image ID

    Returns:
        200: Thumbnail image file (JPEG)
        404: Image not found or image file missing
        500: Thumbnail generation error
    """
    try:
        from backend.models import GeneratedImage

        session = get_session()

        # Get image
        image = session.query(GeneratedImage).filter(
            GeneratedImage.id == image_id
        ).first()

        if not image:
            return not_found_error('Image')

        # Check if original image exists
        if not image.image_url:
            return jsonify({
                'error': 'Image not available',
                'message': 'This image has no URL (may have failed during generation)'
            }), 404

        # Get or generate thumbnail
        thumbnail_path = get_thumbnail_path(image_id)

        if not thumbnail_path.exists():
            # Generate thumbnail from image_url
            thumbnail_path = generate_thumbnail(image.image_url, image_id)

        # Serve thumbnail with caching headers
        response = send_file(
            thumbnail_path,
            mimetype='image/jpeg',
            as_attachment=False
        )
        response.headers['Cache-Control'] = 'public, max-age=86400'  # 24 hours
        return response

    except FileNotFoundError:
        logger.warning(f"Thumbnail not found for image {image_id}")
        return jsonify({
            'error': 'Thumbnail not available',
            'message': 'Could not generate thumbnail for this image'
        }), 404
    except Exception as e:
        logger.exception(f"Error serving thumbnail: {e}")
        return handle_exception(e, include_details=False)
