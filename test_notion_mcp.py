"""
Test script to verify Notion MCP server connection
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.mcp.manager import MCPManager

async def test_notion_connection():
    """Test Notion MCP server connection and tool discovery"""
    print("=" * 60)
    print("Testing Notion MCP Server Connection")
    print("=" * 60)
    
    manager = MCPManager()
    
    try:
        # Initialize MCP Manager
        print("\n1. Initializing MCP Manager...")
        await manager.initialize()
        print("   ✓ MCP Manager initialized successfully")
        
        # Check if Notion server is loaded
        print("\n2. Checking Notion server...")
        if "notion" in manager.handlers:
            print("   ✓ Notion server handler loaded")
        else:
            print("   ✗ Notion server handler NOT found")
            print("   Available handlers:", list(manager.handlers.keys()))
            return
        
        # List Notion tools
        print("\n3. Listing Notion tools...")
        notion_tools = manager.get_tools_for_server("notion")
        
        if notion_tools:
            print(f"   ✓ Found {len(notion_tools)} Notion tools:")
            for tool in notion_tools:
                print(f"      - {tool.name}: {tool.description[:80]}...")
        else:
            print("   ✗ No Notion tools found")
        
        # Get all tools
        print("\n4. All registered tools:")
        all_tools = manager.get_all_tools()
        print(f"   Total tools registered: {len(all_tools)}")
        
        print("\n" + "=" * 60)
        print("Test completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await manager.cleanup()

if __name__ == "__main__":
    asyncio.run(test_notion_connection())
