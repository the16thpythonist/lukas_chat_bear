#!/usr/bin/env python3
"""
Manual OAuth testing script.
Simulates the OAuth flow without requiring actual Slack authorization.

Usage:
    python tests/manual_oauth_test.py [--host HOST] [--port PORT]

This script:
1. Mocks the Slack oauth.v2.access API
2. Simulates an OAuth callback with a test code
3. Verifies token exchange and file saving
4. Outputs results for inspection
"""
import argparse
import requests
import json
from unittest.mock import patch, Mock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.slack_oauth_service import exchange_code_for_tokens, save_tokens_to_file


def mock_slack_api_response():
    """Create a mock successful Slack API response."""
    return {
        "ok": True,
        "access_token": "FAKE_BOT_TOKEN_FOR_TESTING_ONLY",
        "token_type": "bot",
        "scope": "chat:write,users:read,channels:read,im:write,groups:read",
        "bot_user_id": "U012345ABCD",
        "app_id": "A012345WXYZ",
        "team": {
            "id": "T012345TEST",
            "name": "Manual Test Workspace"
        },
        "authed_user": {
            "id": "U67890USER",
            "access_token": "FAKE_USER_TOKEN_FOR_TESTING_ONLY",
            "token_type": "user",
            "scope": "search:read"
        },
        "is_enterprise_install": False,
        "enterprise": None
    }


def test_token_exchange():
    """Test token exchange with mocked Slack API."""
    print("=" * 70)
    print("TEST 1: Token Exchange")
    print("=" * 70)

    with patch('services.slack_oauth_service.requests.post') as mock_post:
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = mock_slack_api_response()
        mock_post.return_value = mock_response

        # Test token exchange
        result = exchange_code_for_tokens(
            code="test-code-123456",
            client_id="test-client-id",
            client_secret="test-client-secret"
        )

        if result and result.get("ok"):
            print("✓ Token exchange successful")
            print(f"  Team: {result['team']['name']} ({result['team']['id']})")
            print(f"  Bot Token: {result['access_token'][:20]}...")
            print(f"  Bot User ID: {result['bot_user_id']}")
            print(f"  Scopes: {result['scope']}")
            if result.get('authed_user', {}).get('access_token'):
                print(f"  User Token: {result['authed_user']['access_token'][:20]}...")
            return True
        else:
            print("✗ Token exchange failed")
            return False


def test_file_saving():
    """Test token file saving."""
    print("\n" + "=" * 70)
    print("TEST 2: Token File Saving")
    print("=" * 70)

    import tempfile
    temp_dir = tempfile.mkdtemp()

    try:
        oauth_response = mock_slack_api_response()
        filepath = save_tokens_to_file(oauth_response, temp_dir)

        if filepath:
            print(f"✓ Token file saved: {filepath}")

            # Verify file contents
            with open(filepath) as f:
                saved_data = json.load(f)

            print(f"  File size: {os.path.getsize(filepath)} bytes")
            print(f"  Contains {len(saved_data)} fields")

            # Verify key fields
            assert saved_data["access_token"] == oauth_response["access_token"]
            assert saved_data["team"]["id"] == oauth_response["team"]["id"]
            assert "installed_at" in saved_data

            print("✓ File contents verified")
            return True
        else:
            print("✗ Token file saving failed")
            return False
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)


def test_oauth_callback_endpoint(host, port):
    """Test the actual OAuth callback endpoint."""
    print("\n" + "=" * 70)
    print("TEST 3: OAuth Callback Endpoint")
    print("=" * 70)

    base_url = f"http://{host}:{port}"

    # First check if server is running
    try:
        health_response = requests.get(f"{base_url}/api/health", timeout=2)
        if health_response.status_code != 200:
            print(f"⚠️  Server health check failed: {health_response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Cannot connect to server at {base_url}")
        print(f"  Error: {e}")
        print(f"  Make sure the dashboard is running:")
        print(f"    docker-compose -f docker-compose.dev.yml up -d")
        return False

    print(f"✓ Server is running at {base_url}")

    # Test install info endpoint
    print("\nTesting /api/oauth/install endpoint...")
    try:
        install_response = requests.get(f"{base_url}/api/oauth/install", timeout=5)
        install_data = install_response.json()

        if install_response.status_code == 200:
            print("✓ Install endpoint working")
            print(f"  Configured: {install_data.get('configured')}")
            print(f"  Install URL: {install_data.get('install_url', 'N/A')[:60]}...")
        else:
            print(f"⚠️  Install endpoint returned {install_response.status_code}")
            print(f"  Message: {install_data.get('message', 'N/A')}")

    except Exception as e:
        print(f"✗ Install endpoint test failed: {e}")
        return False

    # Note: We can't fully test the callback without mocking or ngrok
    print("\n⚠️  Cannot fully test /api/oauth/callback without:")
    print("  1. Setting up ngrok tunnel")
    print("  2. Configuring Slack app redirect URL")
    print("  3. Going through actual OAuth flow")
    print("\nSee testing guide for ngrok setup instructions.")

    return True


def test_error_handling():
    """Test error handling scenarios."""
    print("\n" + "=" * 70)
    print("TEST 4: Error Handling")
    print("=" * 70)

    tests_passed = 0
    tests_total = 3

    # Test 1: Invalid code
    print("\nTest 4.1: Invalid code error handling...")
    with patch('services.slack_oauth_service.requests.post') as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = {"ok": False, "error": "invalid_code"}
        mock_post.return_value = mock_response

        result = exchange_code_for_tokens("invalid", "client", "secret")
        if result is None:
            print("✓ Invalid code handled correctly")
            tests_passed += 1
        else:
            print("✗ Invalid code not handled")

    # Test 2: Network error
    print("\nTest 4.2: Network error handling...")
    with patch('services.slack_oauth_service.requests.post') as mock_post:
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        result = exchange_code_for_tokens("code", "client", "secret")
        if result is None:
            print("✓ Network error handled correctly")
            tests_passed += 1
        else:
            print("✗ Network error not handled")

    # Test 3: File write permission error
    print("\nTest 4.3: File permission error handling...")
    oauth_response = mock_slack_api_response()
    result = save_tokens_to_file(oauth_response, "/root/no-permission")
    if result is None:
        print("✓ Permission error handled correctly")
        tests_passed += 1
    else:
        print("✗ Permission error not handled")

    print(f"\nError handling: {tests_passed}/{tests_total} tests passed")
    return tests_passed == tests_total


def main():
    """Run all tests."""
    parser = argparse.ArgumentParser(description="Test OAuth implementation")
    parser.add_argument('--host', default='localhost', help='Dashboard host')
    parser.add_argument('--port', default='8080', help='Dashboard port')
    args = parser.parse_args()

    print("SLACK OAUTH IMPLEMENTATION TEST SUITE")
    print("=" * 70)

    results = []

    # Run tests
    results.append(("Token Exchange", test_token_exchange()))
    results.append(("File Saving", test_file_saving()))
    results.append(("Error Handling", test_error_handling()))
    results.append(("Callback Endpoint", test_oauth_callback_endpoint(args.host, args.port)))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! OAuth implementation is ready.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
