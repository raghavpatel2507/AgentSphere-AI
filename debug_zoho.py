import httpx
import asyncio
import json

async def test_connection():
    # Configuration
    # New key provided by user in mcp_config.json
    url = "https://agentsphere-60059048845.zohomcp.in/mcp/message?key=4826f38f3035b49a33b8ae17531c7e89"
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "test", "version": "1.0"},
            "capabilities": {}
        }
    }
    
    output = []
    output.append("--- Debug: List Tools and Inspect Schemas ---")
    try:
        async with httpx.AsyncClient() as client:
            # 1. Initialize
            resp = await client.post(url, json=payload)
            output.append(f"Init Status: {resp.status_code}")
            
            if resp.status_code == 200:
                # 2. List Tools
                list_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {}
                }
                resp = await client.post(url, json=list_payload)
                output.append(f"List Tools Status: {resp.status_code}")
                
                if resp.status_code == 200:
                    data = resp.json()
                    tools = data.get("result", {}).get("tools", [])
                    
                    output.append(f"\nFound {len(tools)} total tools:")
                    for tool in tools:
                        output.append(f"- {tool['name']}")
                        
                # 3. Try to call ZohoMail_getMailAccounts to check Mail Auth
                output.append(f"\n--- Attempting to call ZohoMail_getMailAccounts ---")
                call_payload = {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "ZohoMail_getMailAccounts",
                        "arguments": {} 
                    }
                }
                resp = await client.post(url, json=call_payload)
                output.append(f"Call Status: {resp.status_code}")
                output.append(f"Response: {resp.text}")

                # 4. Try to call ZohoCliq_Retrieve_all_direct_chats to check Cliq Auth
                output.append(f"\n--- Attempting to call ZohoCliq_Retrieve_all_direct_chats ---")
                call_payload = {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "ZohoCliq_Retrieve_all_direct_chats",
                        "arguments": {"query_params": {}} 
                    }
                }
                resp = await client.post(url, json=call_payload)
                output.append(f"Call Status: {resp.status_code}")
                output.append(f"Response: {resp.text}")

    except Exception as e:
        output.append(f"Error: {e}")

    with open("debug_output.txt", "w") as f:
        f.write("\n".join(output))

if __name__ == "__main__":
    asyncio.run(test_connection())
