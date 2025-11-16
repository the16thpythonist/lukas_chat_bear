"""
OAuth routes for Slack app installation.
Handles OAuth callback from Slack and saves tokens to filesystem.
"""
from flask import Blueprint, request, jsonify, current_app, render_template_string
from backend.services.slack_oauth_service import (
    exchange_code_for_tokens,
    save_tokens_to_file,
    get_oauth_error_message
)
import logging

logger = logging.getLogger(__name__)

oauth_bp = Blueprint('oauth', __name__)


# Simple HTML template for success/error pages
SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Slack Installation Successful</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .success {
            color: #2eb886;
            font-size: 48px;
            text-align: center;
            margin-bottom: 20px;
        }
        h1 {
            color: #1d1c1d;
            text-align: center;
            margin-bottom: 30px;
        }
        .info {
            background-color: #f8f8f8;
            padding: 20px;
            border-radius: 4px;
            margin: 20px 0;
        }
        .info p {
            margin: 10px 0;
            line-height: 1.6;
        }
        .token-file {
            font-family: monospace;
            background: #e8e8e8;
            padding: 10px;
            border-radius: 4px;
            word-break: break-all;
        }
        .next-steps {
            background-color: #fff4e5;
            border-left: 4px solid #ff9800;
            padding: 15px;
            margin-top: 20px;
        }
        .next-steps ol {
            margin: 10px 0;
            padding-left: 20px;
        }
        .next-steps li {
            margin: 8px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="success">✓</div>
        <h1>Slack Installation Successful</h1>

        <div class="info">
            <p><strong>Workspace:</strong> {{ team_name }}</p>
            <p><strong>Team ID:</strong> {{ team_id }}</p>
            <p><strong>Bot User ID:</strong> {{ bot_user_id }}</p>
        </div>

        <div class="token-file">
            <strong>Tokens saved to:</strong><br>
            {{ filepath }}
        </div>

        <div class="next-steps">
            <strong>Next Steps:</strong>
            <ol>
                <li>Check your server logs for the printed tokens</li>
                <li>Copy the token file from the server</li>
                <li>Manually update your bot's <code>.env</code> file with the tokens</li>
                <li>Restart your bot to use the new workspace tokens</li>
            </ol>
        </div>
    </div>
</body>
</html>
"""

ERROR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Slack Installation Failed</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .error {
            color: #e01e5a;
            font-size: 48px;
            text-align: center;
            margin-bottom: 20px;
        }
        h1 {
            color: #1d1c1d;
            text-align: center;
            margin-bottom: 30px;
        }
        .error-info {
            background-color: #fff0f0;
            border-left: 4px solid #e01e5a;
            padding: 20px;
            margin: 20px 0;
        }
        .error-info p {
            margin: 10px 0;
            line-height: 1.6;
        }
        .help {
            background-color: #f8f8f8;
            padding: 15px;
            border-radius: 4px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="error">✗</div>
        <h1>Slack Installation Failed</h1>

        <div class="error-info">
            <p><strong>Error:</strong> {{ error_message }}</p>
            {% if error_code %}
            <p><strong>Error Code:</strong> {{ error_code }}</p>
            {% endif %}
        </div>

        <div class="help">
            <strong>What to do:</strong>
            <ul>
                <li>Try the installation process again</li>
                <li>Check your Slack app configuration</li>
                <li>Verify the redirect URL matches: <code>{{ redirect_url }}</code></li>
                <li>Check server logs for more details</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""


@oauth_bp.route('/callback', methods=['GET'])
def oauth_callback():
    """
    Handle OAuth redirect from Slack.

    This endpoint is called by Slack after a user authorizes the app installation.
    It exchanges the temporary authorization code for access tokens, then saves
    them to the filesystem and prints them to the console.

    Query Parameters:
        code (str): Temporary authorization code from Slack (expires in 10 minutes)
        error (str, optional): Error code if user denied installation
        state (str, optional): CSRF protection token (not validated in this simple implementation)

    Returns:
        200: HTML success page with installation details
        400: HTML error page for missing/invalid parameters
        500: HTML error page for server errors

    Example:
        GET /api/oauth/callback?code=1234567890.1234567890&state=random_string
    """
    # Check if user denied installation
    error = request.args.get('error')
    if error:
        logger.warning(f"OAuth installation denied by user: {error}")
        return render_template_string(
            ERROR_TEMPLATE,
            error_message="Installation was cancelled by the user.",
            error_code=error,
            redirect_url=request.url_root + 'api/oauth/callback'
        ), 400

    # Extract authorization code
    code = request.args.get('code')
    if not code:
        logger.error("OAuth callback received without code parameter")
        return render_template_string(
            ERROR_TEMPLATE,
            error_message="Missing authorization code. Please try the installation again.",
            error_code=None,
            redirect_url=request.url_root + 'api/oauth/callback'
        ), 400

    # Get configuration
    client_id = current_app.config.get('SLACK_CLIENT_ID')
    client_secret = current_app.config.get('SLACK_CLIENT_SECRET')
    redirect_uri = current_app.config.get('SLACK_REDIRECT_URI')
    output_dir = current_app.config.get('OAUTH_TOKENS_DIR', '/app/data/oauth_tokens')

    # Validate configuration
    if not client_id or not client_secret:
        logger.error("Slack OAuth credentials not configured")
        return render_template_string(
            ERROR_TEMPLATE,
            error_message="Server configuration error: Slack OAuth credentials not set.",
            error_code="missing_credentials",
            redirect_url=request.url_root + 'api/oauth/callback'
        ), 500

    # Exchange code for tokens
    logger.info(f"Processing OAuth callback with code: {code[:10]}...")
    oauth_response = exchange_code_for_tokens(
        code=code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri
    )

    if not oauth_response:
        return render_template_string(
            ERROR_TEMPLATE,
            error_message="Failed to exchange authorization code for tokens. The code may have expired.",
            error_code="token_exchange_failed",
            redirect_url=request.url_root + 'api/oauth/callback'
        ), 500

    # Check if Slack returned an error
    if not oauth_response.get('ok'):
        error_code = oauth_response.get('error', 'unknown_error')
        error_message = get_oauth_error_message(error_code)
        logger.error(f"Slack OAuth error: {error_code}")
        return render_template_string(
            ERROR_TEMPLATE,
            error_message=error_message,
            error_code=error_code,
            redirect_url=request.url_root + 'api/oauth/callback'
        ), 400

    # Save tokens to file
    filepath = save_tokens_to_file(oauth_response, output_dir)

    if not filepath:
        return render_template_string(
            ERROR_TEMPLATE,
            error_message="Tokens received but failed to save to filesystem. Check server logs.",
            error_code="file_write_failed",
            redirect_url=request.url_root + 'api/oauth/callback'
        ), 500

    # Extract team information for success page
    team_info = oauth_response.get('team', {})
    team_name = team_info.get('name', 'Unknown Workspace')
    team_id = team_info.get('id', 'Unknown')
    bot_user_id = oauth_response.get('bot_user_id', 'Unknown')

    # Return success page
    return render_template_string(
        SUCCESS_TEMPLATE,
        team_name=team_name,
        team_id=team_id,
        bot_user_id=bot_user_id,
        filepath=filepath
    ), 200


@oauth_bp.route('/install', methods=['GET'])
def install_info():
    """
    Provide installation instructions and configuration info.

    Returns:
        200: JSON with installation URL and configuration details
    """
    client_id = current_app.config.get('SLACK_CLIENT_ID')
    redirect_uri = current_app.config.get('SLACK_REDIRECT_URI')

    if not client_id:
        return jsonify({
            'error': 'Slack OAuth not configured',
            'message': 'SLACK_CLIENT_ID is not set in environment variables'
        }), 500

    # Construct OAuth URL for "Add to Slack" button
    # Note: Scopes should be configured in Slack app settings
    base_url = "https://slack.com/oauth/v2/authorize"
    params = f"client_id={client_id}"

    if redirect_uri:
        params += f"&redirect_uri={redirect_uri}"

    install_url = f"{base_url}?{params}"

    return jsonify({
        'install_url': install_url,
        'callback_url': request.url_root + 'api/oauth/callback',
        'configured': bool(client_id and current_app.config.get('SLACK_CLIENT_SECRET')),
        'redirect_uri_configured': bool(redirect_uri)
    }), 200
