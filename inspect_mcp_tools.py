import asyncio
import json
import os
import sys

# Ensure src is in pythonpath
sys.path.append(os.getcwd())

from src.core.mcp.manager import MCPManager

async def main():
    manager = MCPManager()
    print("Initializing MCP Manager...")
    await manager.initialize()
    
    report = {}
    
    print("Fetching tools from servers...")
    # Check Zoho to verify the recursive fix and ensure it appears
    target_servers = ["zoho"]
    for server_name, session in manager.server_sessions.items():
        if server_name not in target_servers:
            continue
        print(f"Inspecting server: {server_name}")
        
        try:
            # Get processed LangChain tools
            lc_tools = await manager.get_tools_for_server(server_name)
            
            # Get raw MCP tools
            raw_tools = await session.list_tools()
            
            server_report = []
            
            for rt in raw_tools:
                tool_data = {
                    "name": rt.name,
                    "description": getattr(rt, "description", ""),
                    "raw_inputSchema": getattr(rt, "inputSchema", {}),
                    "processed_schema": {}
                }
                
                # Find matching LangChain tool
                lct = next((t for t in lc_tools if t.name == rt.name), None)
                if lct and lct.args_schema:
                    tool_data["processed_schema"] = lct.args_schema.schema()
                    
                server_report.append(tool_data)
                
            report[server_name] = server_report
            
        except Exception as e:
            print(f"Error inspecting {server_name}: {e}")
            report[server_name] = {"error": str(e)}

    print("Closing sessions...")
    await manager.cleanup()
    
    output_file = "tool_comparison_report.json"
    print(f"Writing report to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
