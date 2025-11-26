import asyncio
import logging
import sys
from src.core.mcp.manager import MCPManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def verify_mcp_system():
    print("🚀 Starting MCP System Verification...")
    
    manager = MCPManager()
    
    # 1. Test Config Loading
    print("\n1️⃣  Testing Config Loading...")
    config = manager.load_config()
    if config:
        print(f"✅ Config loaded successfully. Found {len(config.get('mcp_servers', []))} servers.")
    else:
        print("❌ Failed to load config.")
        return
        
    # 2. Test Initialization (only enabled servers)
    print("\n2️⃣  Testing Server Initialization...")
    try:
        await manager.initialize()
        print("✅ Initialization completed.")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return
        
    # 3. Test Tool Registry
    print("\n3️⃣  Testing Tool Registry...")
    tools = manager.get_all_tools()
    print(f"✅ Found {len(tools)} registered tools.")
    
    for tool in tools:
        print(f"   - {tool.name} ({tool.server_name})")
        
    # 4. Cleanup
    print("\n4️⃣  Testing Cleanup...")
    await manager.cleanup()
    print("✅ Cleanup completed.")
    
    print("\n✨ Verification Successful!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_mcp_system())
