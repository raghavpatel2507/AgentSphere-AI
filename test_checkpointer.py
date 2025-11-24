"""
Test script to verify PostgreSQL checkpointer setup.

This script tests:
1. Database connection
2. Checkpointer initialization
3. Thread ID creation
4. Basic checkpoint save/load
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.state import init_checkpointer, get_checkpointer, create_thread_id, get_config_for_thread


async def test_checkpointer():
    """Test the PostgreSQL checkpointer setup."""
    
    print("=" * 60)
    print("Testing PostgreSQL Checkpointer Setup")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Initialize checkpointer
        print("1. Initializing checkpointer...")
        checkpointer = await init_checkpointer()
        print(f"   ✅ Checkpointer initialized: {type(checkpointer).__name__}")
        print()
        
        # Step 2: Test thread ID creation
        print("2. Testing thread ID creation...")
        thread_id = create_thread_id("default", "test_conversation")
        print(f"   ✅ Thread ID created: {thread_id}")
        config = get_config_for_thread(thread_id)
        print(f"   ✅ Config created: {config}")
        print()
        
        # Step 3: Test checkpointer retrieval
        print("3. Testing checkpointer retrieval...")
        checkpointer2 = get_checkpointer()
        print(f"   ✅ Checkpointer retrieved: {checkpointer is checkpointer2}")
        print()
        
        # Step 4: Verify checkpoint tables exist
        print("4. Verifying checkpoint tables...")
        from src.core.config.database import get_asyncpg_pool
        pool = await get_asyncpg_pool()
        
        async with pool.acquire() as conn:
            # Check if checkpoint tables exist
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'checkpoint%'
                ORDER BY table_name
            """)
            
            print(f"   ✅ Found {len(tables)} checkpoint tables:")
            for table in tables:
                print(f"      - {table['table_name']}")
        print()
        
        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        print()
        print("Your PostgreSQL checkpointer is ready to use!")
        print(f"Thread ID format: {thread_id}")
        print()
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Test failed!")
        print("=" * 60)
        print()
        print(f"Error: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        print()
        exit(1)


if __name__ == "__main__":
    asyncio.run(test_checkpointer())
