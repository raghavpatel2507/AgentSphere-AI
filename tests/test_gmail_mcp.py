"""
Test script to diagnose Gmail MCP server issues
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

from src.mcp_clients.gmail import GmailMCPClient

def test_gmail_connection():
    print("\n" + "="*50)
    print("Gmail MCP Connection Test")
    print("="*50 + "\n")
    
    client = GmailMCPClient()
    
    try:
        # Test 1: List tools
        print("📋 Test 1: Listing available tools...")
        tools = client.list_tools_sync()
        print(f"✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool.name}")
        print()
        
        # Test 2: Send a test email
        print("📧 Test 2: Sending test email...")
        recipient = input("Enter recipient email (or press Enter to skip): ").strip()
        
        if recipient:
            result = client.call_tool_sync(
                "send-email",
                {
                    "recipient_id": recipient,
                    "subject": "Gmail MCP Test",
                    "message": "This is a test email from Gmail MCP client."
                }
            )
            print(f"✅ Email sent successfully!")
            print(f"   Result: {result}")
        else:
            print("⏭️  Skipping email send test")
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔌 Closing connection...")
        client.close_sync()
        print("✅ Connection closed")

if __name__ == "__main__":
    test_gmail_connection()
