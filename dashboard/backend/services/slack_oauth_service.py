"""
Slack OAuth service for handling OAuth 2.0 token exchange.
Exchanges authorization codes for access tokens and saves them to filesystem.
"""
import json
import logging
import requests
from base64 import b64encode
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

SLACK_OAUTH_ACCESS_URL = "https://slack.com/api/oauth.v2.access"


def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Exchange OAuth authorization code for access tokens.

    Args:
        code: Temporary authorization code from Slack (expires in 10 minutes)
        client_id: Slack app client ID
        client_secret: Slack app client secret
        redirect_uri: Optional redirect URI (must match if sent in authorize step)

    Returns:
        dict: OAuth response from Slack containing tokens and metadata
        None: If exchange fails

    Example response:
        {
            "ok": true,
            "access_token": "xoxb-...",
            "token_type": "bot",
            "scope": "chat:write,users:read",
            "bot_user_id": "U012345",
            "app_id": "A012345",
            "team": {"id": "T012345", "name": "Workspace Name"},
            "authed_user": {"id": "U67890"},
            "is_enterprise_install": false
        }
    """
    try:
        # Prepare HTTP Basic Auth (recommended by Slack)
        auth_string = f"{client_id}:{client_secret}"
        auth_encoded = b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {auth_encoded}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # Prepare form data
        data = {"code": code}
        if redirect_uri:
            data["redirect_uri"] = redirect_uri

        logger.info(f"Exchanging OAuth code for tokens (code: {code[:10]}...)")

        # Make request to Slack
        response = requests.post(
            SLACK_OAUTH_ACCESS_URL,
            headers=headers,
            data=data,
            timeout=10
        )

        # Parse response
        result = response.json()

        if not result.get("ok"):
            error = result.get("error", "unknown_error")
            logger.error(f"OAuth token exchange failed: {error}")
            logger.error(f"Full response: {json.dumps(result, indent=2)}")
            return None

        logger.info(f"✓ OAuth token exchange successful for team: {result.get('team', {}).get('name', 'Unknown')}")
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during OAuth token exchange: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during OAuth token exchange: {e}")
        return None


def save_tokens_to_file(oauth_response: Dict[str, Any], output_dir: str) -> Optional[str]:
    """
    Save OAuth tokens to filesystem and print to console.

    Args:
        oauth_response: Response from oauth.v2.access
        output_dir: Directory to save token files

    Returns:
        str: Path to saved file
        None: If save fails

    Creates file:
        {output_dir}/tokens_{team_id}_{timestamp}.json
    """
    try:
        # Extract team information
        team_info = oauth_response.get("team", {})
        team_id = team_info.get("id", "unknown")
        team_name = team_info.get("name", "Unknown Workspace")

        # Extract token information
        bot_token = oauth_response.get("access_token", "")
        bot_user_id = oauth_response.get("bot_user_id", "")
        scopes = oauth_response.get("scope", "")
        app_id = oauth_response.get("app_id", "")
        is_enterprise = oauth_response.get("is_enterprise_install", False)

        # User token (if user scopes were requested)
        authed_user = oauth_response.get("authed_user", {})
        user_token = authed_user.get("access_token", None)
        user_id = authed_user.get("id", "")

        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"tokens_{team_id}_{timestamp}.json"
        filepath = output_path / filename

        # Add installation timestamp to response
        output_data = {
            **oauth_response,
            "installed_at": datetime.utcnow().isoformat() + "Z"
        }

        # Write to file with pretty formatting
        with open(filepath, 'w') as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"✓ Tokens saved to: {filepath}")

        # Print formatted output to console
        print("\n" + "=" * 70)
        print("SLACK OAUTH INSTALLATION SUCCESSFUL")
        print("=" * 70)
        print(f"Team: {team_name} ({team_id})")
        print(f"App ID: {app_id}")
        print(f"Bot User ID: {bot_user_id}")
        print(f"Enterprise Install: {is_enterprise}")
        print(f"\nBot Token: {bot_token}")
        print(f"Bot Scopes: {scopes}")

        if user_token:
            print(f"\nUser Token: {user_token}")
            print(f"User ID: {user_id}")

        print(f"\nTokens saved to: {filepath}")
        print("=" * 70 + "\n")

        return str(filepath)

    except Exception as e:
        logger.error(f"Failed to save tokens to file: {e}")
        return None


def get_oauth_error_message(error_code: str) -> str:
    """
    Get user-friendly error message for OAuth error codes.

    Args:
        error_code: Slack OAuth error code

    Returns:
        User-friendly error message
    """
    error_messages = {
        "invalid_code": "The authorization code is invalid or has expired. Please try again.",
        "bad_redirect_uri": "The redirect URI doesn't match the configured URL in your Slack app settings.",
        "code_already_used": "This authorization code has already been used. Please start the installation process again.",
        "invalid_client_id": "Invalid client ID. Check your SLACK_CLIENT_ID configuration.",
        "bad_client_secret": "Invalid client secret. Check your SLACK_CLIENT_SECRET configuration.",
        "invalid_grant_type": "Invalid grant type specified.",
        "invalid_scope": "One or more requested scopes are invalid.",
        "oauth_authorization_url_mismatch": "The redirect URI must match the URL configured in your Slack app.",
    }

    return error_messages.get(
        error_code,
        f"OAuth error: {error_code}. Please check Slack API documentation."
    )
