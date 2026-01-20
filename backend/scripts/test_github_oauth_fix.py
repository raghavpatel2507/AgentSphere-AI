#!/usr/bin/env python3
"""
Test script to verify GitHub OAuth account selection behavior.

This script simulates the OAuth flow and verifies that:
1. The authorization URL includes prompt=select_account for GitHub
2. The authorization URL includes prompt=consent for other services
"""

import sys
import os

# Add backend to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

# Now we can import with the correct path structure
from app.core.mcp.google_oauth import GenericOAuthHandler
from uuid import uuid4

def test_github_oauth_url():
    """Test that GitHub OAuth URL includes prompt=select_account"""
    print("=" * 60)
    print("Testing GitHub OAuth Authorization URL")
    print("=" * 60)
    
    user_id = str(uuid4())
    
    handler = GenericOAuthHandler(
        user_id=user_id,
        service_name="github",
        client_id="test_client_id",
        client_secret="test_client_secret",
        authorization_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        scopes=["repo", "user"],
        use_pkce=False
    )
    
    auth_url = handler.get_authorization_url()
    
    print(f"\nGenerated URL:\n{auth_url}\n")
    
    # Verify prompt=select_account is present
    if "prompt=select_account" in auth_url:
        print("✅ SUCCESS: GitHub URL contains 'prompt=select_account'")
        print("   This will force account selection for user isolation")
        return True
    else:
        print("❌ FAILED: GitHub URL does NOT contain 'prompt=select_account'")
        if "prompt=consent" in auth_url:
            print("   Found 'prompt=consent' instead (incorrect for GitHub)")
        return False

def test_google_oauth_url():
    """Test that Google OAuth URL includes prompt=consent"""
    print("\n" + "=" * 60)
    print("Testing Google OAuth Authorization URL")
    print("=" * 60)
    
    user_id = str(uuid4())
    
    handler = GenericOAuthHandler(
        user_id=user_id,
        service_name="gmail-mcp",
        client_id="test_client_id",
        client_secret="test_client_secret",
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        use_pkce=False
    )
    
    auth_url = handler.get_authorization_url()
    
    print(f"\nGenerated URL:\n{auth_url}\n")
    
    # Verify prompt=consent is present
    if "prompt=consent" in auth_url:
        print("✅ SUCCESS: Google URL contains 'prompt=consent'")
        print("   This will force consent screen to get refresh token")
        return True
    else:
        print("❌ FAILED: Google URL does NOT contain 'prompt=consent'")
        if "prompt=select_account" in auth_url:
            print("   Found 'prompt=select_account' instead (incorrect for Google)")
        return False

def main():
    """Run all tests"""
    print("\n🔍 GitHub OAuth User Isolation Verification\n")
    
    github_test = test_github_oauth_url()
    google_test = test_google_oauth_url()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    if github_test and google_test:
        print("\n✅ ALL TESTS PASSED")
        print("\nGitHub OAuth will now force account selection, ensuring")
        print("each user can connect their own GitHub account without")
        print("interference from already-logged-in sessions.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        if not github_test:
            print("   - GitHub OAuth URL generation failed")
        if not google_test:
            print("   - Google OAuth URL generation failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
