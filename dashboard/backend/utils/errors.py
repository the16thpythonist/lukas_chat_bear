"""
Error translation utilities for dashboard backend.
Maps technical exceptions to user-friendly error messages.
"""
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError
from werkzeug.exceptions import HTTPException
import logging

logger = logging.getLogger(__name__)


class ErrorResponse:
    """
    Standardized error response format for API endpoints.

    Attributes:
        error: Error type/category
        message: User-friendly error message
        details: Optional technical details (only in development)
        status_code: HTTP status code
    """

    def __init__(self, error, message, status_code=500, details=None):
        self.error = error
        self.message = message
        self.status_code = status_code
        self.details = details

    def to_dict(self, include_details=False):
        """
        Convert error response to dictionary.

        Args:
            include_details: Whether to include technical details (development only)

        Returns:
            dict: Error response dictionary
        """
        response = {
            'error': self.error,
            'message': self.message
        }

        if include_details and self.details:
            response['details'] = self.details

        return response

    def to_tuple(self, include_details=False):
        """
        Convert error response to Flask response tuple.

        Args:
            include_details: Whether to include technical details

        Returns:
            tuple: (response_dict, status_code)
        """
        return self.to_dict(include_details), self.status_code


def translate_database_error(exc):
    """
    Translate SQLAlchemy exceptions to user-friendly error messages.

    Args:
        exc: SQLAlchemy exception

    Returns:
        ErrorResponse: User-friendly error response

    Note:
        Maps database errors to readable messages per FR-016 requirement.
    """
    logger.error(f"Database error: {exc}", exc_info=True)

    if isinstance(exc, OperationalError):
        # Database locked, connection failed, etc.
        return ErrorResponse(
            error='Database Error',
            message='The database is temporarily unavailable. Please try again in a moment.',
            status_code=503,
            details=str(exc)
        )

    elif isinstance(exc, IntegrityError):
        # Constraint violations
        return ErrorResponse(
            error='Data Integrity Error',
            message='The operation could not be completed due to data constraints.',
            status_code=400,
            details=str(exc)
        )

    elif isinstance(exc, SQLAlchemyError):
        # Generic SQLAlchemy error
        return ErrorResponse(
            error='Database Error',
            message='An error occurred while accessing the database. Please try again.',
            status_code=500,
            details=str(exc)
        )

    else:
        # Unknown database error
        return ErrorResponse(
            error='Database Error',
            message='An unexpected database error occurred. Please try again.',
            status_code=500,
            details=str(exc)
        )


def translate_http_error(status_code, message=None):
    """
    Translate HTTP status codes to readable descriptions.

    Args:
        status_code: HTTP status code (e.g., 404, 500)
        message: Optional custom message

    Returns:
        ErrorResponse: User-friendly error response
    """
    # Map common status codes to user-friendly messages
    status_messages = {
        400: ('Bad Request', 'The request was invalid. Please check your input and try again.'),
        401: ('Unauthorized', 'Authentication required. Please log in.'),
        403: ('Forbidden', 'You do not have permission to access this resource.'),
        404: ('Not Found', 'The requested resource was not found.'),
        429: ('Too Many Requests', 'You have exceeded the rate limit. Please try again later.'),
        500: ('Internal Server Error', 'An unexpected error occurred. Please try again later.'),
        503: ('Service Unavailable', 'The service is temporarily unavailable. Please try again later.')
    }

    error_type, default_message = status_messages.get(
        status_code,
        ('Error', 'An error occurred processing your request.')
    )

    return ErrorResponse(
        error=error_type,
        message=message or default_message,
        status_code=status_code
    )


def handle_exception(exc, include_details=False):
    """
    Central exception handler that translates any exception to ErrorResponse.

    Args:
        exc: Exception to handle
        include_details: Whether to include technical details (development mode)

    Returns:
        tuple: (response_dict, status_code) suitable for Flask return
    """
    if isinstance(exc, HTTPException):
        # Werkzeug HTTP exceptions
        error_response = translate_http_error(exc.code, exc.description)

    elif isinstance(exc, SQLAlchemyError):
        # Database exceptions
        error_response = translate_database_error(exc)

    else:
        # Generic exceptions
        logger.exception(f"Unhandled exception: {exc}")
        error_response = ErrorResponse(
            error='Internal Server Error',
            message='An unexpected error occurred. Please try again.',
            status_code=500,
            details=str(exc)
        )

    return error_response.to_tuple(include_details)


def not_found_error(resource_type='Resource'):
    """
    Create a standardized 404 Not Found error response.

    Args:
        resource_type: Type of resource that wasn't found (e.g., 'Message', 'Image')

    Returns:
        tuple: (response_dict, status_code)
    """
    error_response = ErrorResponse(
        error='Not Found',
        message=f'{resource_type} not found.',
        status_code=404
    )
    return error_response.to_tuple()


def validation_error(message, field=None):
    """
    Create a standardized validation error response.

    Args:
        message: Validation error message
        field: Optional field name that failed validation

    Returns:
        tuple: (response_dict, status_code)
    """
    error_response = ErrorResponse(
        error='Validation Error',
        message=message,
        status_code=400,
        details={'field': field} if field else None
    )
    return error_response.to_tuple(include_details=True)


def rate_limit_error(limit, window):
    """
    Create a standardized rate limit error response.

    Args:
        limit: Rate limit threshold
        window: Time window for rate limit (e.g., 'hour', 'minute')

    Returns:
        tuple: (response_dict, status_code)
    """
    error_response = ErrorResponse(
        error='Rate Limit Exceeded',
        message=f'You have exceeded the rate limit of {limit} requests per {window}. Please try again later.',
        status_code=429
    )
    return error_response.to_tuple()
