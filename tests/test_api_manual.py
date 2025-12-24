import asyncio
import httpx
import json
import time
import sys

BASE_URL = "http://localhost:8000/api/v1"

async def run_tests():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("1. Checking Health...")
        try:
            resp = await client.get("http://localhost:8000/health")
            print(f"   Status: {resp.status_code}, Body: {resp.json()}")
        except Exception as e:
            print(f"   Failed to connect: {e}")
            return

        print("\n2. Creating Session...")
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        user_id = "550e8400-e29b-41d4-a716-446655440001"
        resp = await client.post(f"{BASE_URL}/sessions/", json={
            "tenant_id": tenant_id,
            "user_id": user_id
        })
        print(f"   Status: {resp.status_code}")
        session_data = resp.json()
        print(f"   Session Data: {session_data}")
        session_id = session_data["session_id"]

        print("\n3. Listing Tools...")
        resp = await client.get(f"{BASE_URL}/tools/")
        print(f"   Status: {resp.status_code}")
        tools = resp.json()
        print(f"   Tools Found: {len(tools)}")
        # print(f"   Tools: {json.dumps(tools, indent=2)}")

        print("\n4. Sending Chat Message (Streaming)...")
        chat_payload = {
            "message": "Hello, are you online?",
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id
        }
        
        async with client.stream("POST", f"{BASE_URL}/chat/", json=chat_payload) as response:
            print(f"   Status: {response.status_code}")
            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if data["type"] == "token":
                            print(data["content"], end="", flush=True)
                        elif data["type"] == "plan":
                            print(f"\n   [Plan]: {data['content']}")
                    except:
                        print(f"\n   [Raw]: {line}")
        print("\n")

        print("\n5. Checking History...")
        resp = await client.get(f"{BASE_URL}/sessions/{session_id}/history?tenant_id={tenant_id}&user_id={user_id}")
        print(f"   Status: {resp.status_code}")
        history = resp.json()
        print(f"   History Length: {len(history)}")
        print(f"   Last Message: {history[-1] if history else 'None'}")

if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        pass
