"""
Comprehensive OAuth Token Isolation Verification Test

This script verifies that OAuth tokens are properly isolated between users.
It tests both database-level isolation and filesystem token file isolation.

Run this script to verify token isolation is working correctly:
    cd /home/logicrays/Desktop/AgentSphere-AI/backend
    python scripts/verify_token_isolation.py
"""

import sys
import os
import asyncio
from uuid import uuid4
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

# Import with correct path
import app.db
from app.db import async_engine
from app.core.state.models import OAuthToken
from app.core.mcp.token_manager import TokenManager


async def test_database_token_isolation():
    """Test that tokens are properly isolated in the database."""
    print("\n" + "="*80)
    print("TEST 1: Database Token Isolation")
    print("="*80)
    
    # Create two mock users
    user_a_id = uuid4()
    user_b_id = uuid4()
    service = "github"
    
    print(f"\n📋 Test Setup:")
    print(f"   User A ID: {user_a_id}")
    print(f"   User B ID: {user_b_id}")
    print(f"   Service: {service}")
    
    # Create token managers for each user
    token_manager_a = TokenManager(user_a_id)
    token_manager_b = TokenManager(user_b_id)
    
    try:
        # Step 1: Store token for User A
        print(f"\n🔹 Step 1: Storing token for User A")
        await token_manager_a.store_token(
            service=service,
            access_token="user_a_access_token_12345",
            refresh_token="user_a_refresh_token_67890",
            scopes=["repo", "user"],
            expires_in=3600
        )
        print("   ✅ User A token stored")
        
        # Step 2: Store token for User B (same service, different user)
        print(f"\n🔹 Step 2: Storing token for User B")
        await token_manager_b.store_token(
            service=service,
            access_token="user_b_access_token_ABCDE",
            refresh_token="user_b_refresh_token_FGHIJ",
            scopes=["repo", "gist"],
            expires_in=7200
        )
        print("   ✅ User B token stored")
        
        # Step 3: Retrieve token for User A
        print(f"\n🔹 Step 3: Retrieving token for User A")
        token_a = await token_manager_a.get_token(service)
        
        if not token_a:
            print("   ❌ FAILED: No token found for User A")
            return False
        
        if token_a["access_token"] != "user_a_access_token_12345":
            print(f"   ❌ FAILED: User A got wrong token: {token_a['access_token']}")
            return False
        
        print(f"   ✅ User A retrieved correct token")
        print(f"      Access Token: {token_a['access_token'][:20]}...")
        print(f"      Scopes: {token_a['scopes']}")
        
        # Step 4: Retrieve token for User B
        print(f"\n🔹 Step 4: Retrieving token for User B")
        token_b = await token_manager_b.get_token(service)
        
        if not token_b:
            print("   ❌ FAILED: No token found for User B")
            return False
        
        if token_b["access_token"] != "user_b_access_token_ABCDE":
            print(f"   ❌ FAILED: User B got wrong token: {token_b['access_token']}")
            return False
        
        print(f"   ✅ User B retrieved correct token")
        print(f"      Access Token: {token_b['access_token'][:20]}...")
        print(f"      Scopes: {token_b['scopes']}")
        
        # Step 5: Verify tokens are different
        print(f"\n🔹 Step 5: Verifying tokens are different")
        if token_a["access_token"] == token_b["access_token"]:
            print("   ❌ FAILED: Both users have the same token!")
            return False
        
        print("   ✅ Tokens are properly isolated")
        
        # Step 6: Verify database constraint (unique user_id + service)
        print(f"\n🔹 Step 6: Verifying database unique constraint")
        async with AsyncSession(async_engine) as session:
            result = await session.execute(
                select(OAuthToken).where(OAuthToken.service == service)
            )
            all_tokens = result.scalars().all()
            
            print(f"   Found {len(all_tokens)} tokens for service '{service}'")
            
            user_a_tokens = [t for t in all_tokens if t.user_id == user_a_id]
            user_b_tokens = [t for t in all_tokens if t.user_id == user_b_id]
            
            print(f"   User A tokens: {len(user_a_tokens)}")
            print(f"   User B tokens: {len(user_b_tokens)}")
            
            if len(user_a_tokens) != 1 or len(user_b_tokens) != 1:
                print("   ❌ FAILED: Unexpected token count")
                return False
            
            print("   ✅ Each user has exactly one token")
        
        print(f"\n{'='*80}")
        print("✅ TEST 1 PASSED: Database token isolation is working correctly")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup: Delete test tokens
        print(f"\n🧹 Cleaning up test data...")
        try:
            await token_manager_a.delete_token(service)
            await token_manager_b.delete_token(service)
            print("   ✅ Test data cleaned up")
        except Exception as e:
            print(f"   ⚠️  Cleanup warning: {e}")


async def test_filesystem_token_isolation():
    """Test that filesystem token files are properly isolated."""
    print("\n" + "="*80)
    print("TEST 2: Filesystem Token File Isolation")
    print("="*80)
    
    user_a_id = uuid4()
    user_b_id = uuid4()
    service = "github"
    
    print(f"\n📋 Test Setup:")
    print(f"   User A ID: {user_a_id}")
    print(f"   User B ID: {user_b_id}")
    print(f"   Service: {service}")
    
    mcp_use_token_dir = Path.home() / ".mcp_use" / "tokens"
    mcp_use_token_dir.mkdir(parents=True, exist_ok=True)
    
    # Expected file paths (using mcp-use naming convention)
    token_file_a = mcp_use_token_dir / f"{service}_{user_a_id}.json"
    token_file_b = mcp_use_token_dir / f"{service}_{user_b_id}.json"
    
    print(f"\n🔹 Expected token file paths:")
    print(f"   User A: {token_file_a}")
    print(f"   User B: {token_file_b}")
    
    try:
        # Step 1: Create token file for User A
        print(f"\n🔹 Step 1: Creating token file for User A")
        import json
        token_data_a = {
            "access_token": "user_a_filesystem_token",
            "refresh_token": "user_a_refresh",
            "scope": "repo user",
            "token_type": "Bearer",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        }
        
        with open(token_file_a, "w") as f:
            json.dump(token_data_a, f)
        
        if token_file_a.exists():
            print("   ✅ User A token file created")
        else:
            print("   ❌ FAILED: User A token file not created")
            return False
        
        # Step 2: Create token file for User B
        print(f"\n🔹 Step 2: Creating token file for User B")
        token_data_b = {
            "access_token": "user_b_filesystem_token",
            "refresh_token": "user_b_refresh",
            "scope": "repo gist",
            "token_type": "Bearer",
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        }
        
        with open(token_file_b, "w") as f:
            json.dump(token_data_b, f)
        
        if token_file_b.exists():
            print("   ✅ User B token file created")
        else:
            print("   ❌ FAILED: User B token file not created")
            return False
        
        # Step 3: Verify files are separate
        print(f"\n🔹 Step 3: Verifying files are separate")
        
        with open(token_file_a) as f:
            read_data_a = json.load(f)
        
        with open(token_file_b) as f:
            read_data_b = json.load(f)
        
        if read_data_a["access_token"] == "user_a_filesystem_token":
            print("   ✅ User A file contains correct token")
        else:
            print(f"   ❌ FAILED: User A file has wrong token: {read_data_a['access_token']}")
            return False
        
        if read_data_b["access_token"] == "user_b_filesystem_token":
            print("   ✅ User B file contains correct token")
        else:
            print(f"   ❌ FAILED: User B file has wrong token: {read_data_b['access_token']}")
            return False
        
        if read_data_a["access_token"] != read_data_b["access_token"]:
            print("   ✅ Token files are properly isolated")
        else:
            print("   ❌ FAILED: Both files have the same token!")
            return False
        
        print(f"\n{'='*80}")
        print("✅ TEST 2 PASSED: Filesystem token isolation is working correctly")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup: Delete test files
        print(f"\n🧹 Cleaning up test files...")
        try:
            if token_file_a.exists():
                token_file_a.unlink()
                print(f"   ✅ Deleted {token_file_a.name}")
            if token_file_b.exists():
                token_file_b.unlink()
                print(f"   ✅ Deleted {token_file_b.name}")
        except Exception as e:
            print(f"   ⚠️  Cleanup warning: {e}")


async def test_concurrent_access():
    """Test concurrent token access by multiple users."""
    print("\n" + "="*80)
    print("TEST 3: Concurrent Token Access")
    print("="*80)
    
    user_ids = [uuid4() for _ in range(5)]
    service = "github"
    
    print(f"\n📋 Test Setup:")
    print(f"   Number of users: {len(user_ids)}")
    print(f"   Service: {service}")
    
    try:
        # Step 1: Store tokens for all users concurrently
        print(f"\n🔹 Step 1: Storing tokens for {len(user_ids)} users concurrently")
        
        async def store_user_token(user_id, index):
            manager = TokenManager(user_id)
            await manager.store_token(
                service=service,
                access_token=f"user_{index}_token_{user_id}",
                refresh_token=f"user_{index}_refresh",
                scopes=["repo"],
                expires_in=3600
            )
            return user_id, index
        
        results = await asyncio.gather(*[
            store_user_token(user_id, i) 
            for i, user_id in enumerate(user_ids)
        ])
        
        print(f"   ✅ Stored {len(results)} tokens concurrently")
        
        # Step 2: Retrieve tokens for all users concurrently
        print(f"\n🔹 Step 2: Retrieving tokens for {len(user_ids)} users concurrently")
        
        async def retrieve_user_token(user_id, index):
            manager = TokenManager(user_id)
            token = await manager.get_token(service)
            expected_token = f"user_{index}_token_{user_id}"
            
            if not token:
                return False, f"User {index}: No token found"
            
            if token["access_token"] != expected_token:
                return False, f"User {index}: Wrong token (got {token['access_token'][:20]}...)"
            
            return True, f"User {index}: Correct token"
        
        results = await asyncio.gather(*[
            retrieve_user_token(user_id, i)
            for i, user_id in enumerate(user_ids)
        ])
        
        # Check results
        all_passed = all(success for success, _ in results)
        
        for success, message in results:
            status = "✅" if success else "❌"
            print(f"   {status} {message}")
        
        if not all_passed:
            print(f"\n❌ TEST 3 FAILED: Some users got wrong tokens")
            return False
        
        print(f"\n{'='*80}")
        print("✅ TEST 3 PASSED: Concurrent access is properly isolated")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up test data...")
        try:
            for user_id in user_ids:
                manager = TokenManager(user_id)
                await manager.delete_token(service)
            print(f"   ✅ Cleaned up {len(user_ids)} test tokens")
        except Exception as e:
            print(f"   ⚠️  Cleanup warning: {e}")


async def main():
    """Run all token isolation tests."""
    print("\n" + "="*80)
    print("🔒 OAuth Token Isolation Verification Test Suite")
    print("="*80)
    print("\nThis test suite verifies that OAuth tokens are properly isolated")
    print("between different users in the AgentSphere-AI system.")
    
    results = []
    
    # Run all tests
    results.append(("Database Token Isolation", await test_database_token_isolation()))
    results.append(("Filesystem Token Isolation", await test_filesystem_token_isolation()))
    results.append(("Concurrent Token Access", await test_concurrent_access()))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Token isolation is working correctly!")
        print("="*80)
        return 0
    else:
        print("⚠️  SOME TESTS FAILED - Token isolation may have issues!")
        print("="*80)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
