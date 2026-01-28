"""
AgentSphere-AI Main Entry Point (v2.0)
"""
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

import asyncio
import os
import logging
from typing import List
from uuid import UUID
from backend.app.core.agents.planner import Planner
from backend.app.core.agents.agent import Agent
from backend.app.core.mcp.manager import MCPManager
from backend.app.core.mcp.registry import SPHERE_REGISTRY, get_app_by_id
from backend.app.core.llm.provider import LLMFactory
from backend.app.core.state import (
    get_or_create_session,
    clear_current_session,
    load_history,
    save_history
)

# Configure logging
class ProgressFormatter(logging.Formatter):
    def format(self, record):
        msg = record.msg if isinstance(record.msg, str) else str(record.msg)
        if any(x in msg for x in ["Calling tool", "Executing tool", "Running tool", "Tool:"]):
            return f"🛠️ {msg}"
        if any(x in msg for x in ["Tool returned", "Result:", "Output of"]):
            return f"✅ {msg}"
        if any(x in msg for x in ["Connected to server", "🔌"]):
            return f"🔌 {msg}"
        if record.levelno >= logging.ERROR:
            return f"❌ {msg}"
        if record.levelno >= logging.WARNING:
            return f"⚠️ {msg}"
        return super().format(record)
Assistant_Prefix = "\n🤖: "

handler = logging.StreamHandler()
handler.setFormatter(ProgressFormatter('%(message)s'))

# Clear and set root logger
root = logging.getLogger()
for h in root.handlers[:]:
    root.removeHandler(h)
root.addHandler(handler)
root.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Silence only the truly noisy ones
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# keep mcp_use and backend.app.core at INFO level for progress
mcp_logger = logging.getLogger("mcp_use")
mcp_logger.setLevel(logging.INFO)
mcp_logger.propagate = True

core_logger = logging.getLogger("backend.app.core")
core_logger.setLevel(logging.INFO)
core_logger.propagate = True

async def main():
    """Main async function for the new AgentSphere-AI architecture."""
    
    print("=" * 60)
    print("🤖 AgentSphere-AI - Ground-Up Architecture (v2.0)")
    print("=" * 60)
    
    # 1. Initialize Core Services
    print("🔄 Initializing MCP Manager...")
    mcp_manager = MCPManager()
    await mcp_manager.initialize()
    
    # 2. Setup LLM and Components
    llm = LLMFactory.load_config_and_create_llm()
    
    planner = Planner(api_key=os.getenv("OPENROUTER_API_KEY"))
    # DO NOT initialize agent here, we do it per-turn to refresh tools
    
    # 3. Session Management
    # For thread_id creation, use simple string
    tenant_name = os.getenv("DEFAULT_TENANT_NAME", "default")
    thread_id, is_new = get_or_create_session(tenant_name)
    
    # For database operations, use UUIDs
    tenant_id = os.getenv("DEFAULT_TENANT_ID", "550e8400-e29b-41d4-a716-446655440000")
    user_id = os.getenv("DEFAULT_USER_ID", "550e8400-e29b-41d4-a716-446655440001")
    
    # Validate UUIDs
    try:
        UUID(tenant_id)  # Validate tenant_id
        UUID(user_id)    # Validate user_id
    except ValueError as e:
        print(f"\n❌ Invalid UUID configuration!")
        print(f"   tenant_id: '{tenant_id}'")
        print(f"   user_id: '{user_id}'")
        print(f"   Error: {e}")
        print(f"\n💡 Please set valid UUIDs in your .env file:")
        print(f"   DEFAULT_TENANT_ID=550e8400-e29b-41d4-a716-446655440000")
        print(f"   DEFAULT_USER_ID=550e8400-e29b-41d4-a716-446655440001\n")
        await mcp_manager.cleanup()
        return
    except Exception as e:
        print(f"\n❌ Initialization Error: {e}")
        return
    
    # 4. Load History from DB
    history = await load_history(thread_id, tenant_id, user_id)
    
    print(f"📝 Thread ID: {thread_id}")
    print(f"{'✨ Started NEW' if is_new else '🔄 RESUMED'} conversation")
    print(f"📜 Loaded {len(history)} previous messages")
    print("\nCommands: /exit, /new, /history, /tools\n")

    # 5. Continuous Chat Loop
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input: continue
            
            # Command Handling
            if user_input.lower() == "/exit":
                print("\n👋 Goodbye!")
                await mcp_manager.cleanup()
                break
            
            elif user_input.lower() == "/new":
                clear_current_session()
                thread_id, _ = get_or_create_session(tenant_id)
                history = []
                print(f"\n✨ Started new conversation: {thread_id}\n")
                continue
            
            elif user_input.lower() == "/history":
                print("\n📜 Conversation History:")
                for msg in history:
                    role = "USER" if msg.type == "human" else "AGENT"
                    print(f"[{role}]: {msg.content[:150]}...")
                print()
                continue

            elif user_input.lower().startswith("/tools"):
                status = await mcp_manager.get_all_tools_status()
                print("\n🛠️  MCP Servers Status:")
                for s_name, s_info in status.items():
                    conn = "✅" if s_info['connected'] else "❌"
                    print(f"- {s_name}: {conn} ({s_info['tools_count']} tools)")
                print()
                continue
            
            # --- PLANNING & EXECUTION PHASE ---
            print("\n🤔 Planning...", end="", flush=True)
            available_servers = await mcp_manager.get_all_tools_status()
            
            plan = None
            full_direct_response = ""
            prefix_printed = False
            
            async for chunk in planner.plan(user_input, history, available_servers):
                if isinstance(chunk, str):
                    if not prefix_printed:
                        print("\n🤖: ", end="", flush=True)
                        prefix_printed = True
                    print(chunk, end="", flush=True)
                    full_direct_response += chunk
                else:
                    plan = chunk

            if plan.get("servers"):
                if not prefix_printed:
                    print(f" Routing to servers: {', '.join(plan['servers'])}")
                
                # Instant Connection
                await mcp_manager.connect_to_servers(plan['servers'])
                if mcp_manager._mcp_client:
                    mcp_manager._mcp_client.allowed_servers = list(plan['servers'])
                
                # Get wrapped tools (with HITL guards)
                tools = await mcp_manager.get_tools_for_servers(plan['servers'])
                
                # Re-create agent with wrapped tools
                agent = Agent(llm=llm, mcp_client=mcp_manager._mcp_client, tools=tools)
                
                if not prefix_printed:
                    print("\n🤔 Thinking and using tools...\n", flush=True)
                    print("\n🤖: ", end="", flush=True)
                    prefix_printed = True
                
                from langchain_core.messages import HumanMessage, AIMessage
                history.append(HumanMessage(content=user_input))
                
                full_agent_response = ""
                async for event in agent.execute_streaming(user_input, history[:-1]):
                    etype = event.get("type")
                    
                    if etype == "token":
                        content = event.get("content", "")
                        print(content, end="", flush=True)
                        full_agent_response += content
                    
                    elif etype == "tool_start":
                        t_name = event.get("tool")
                        print(f"\n🛠️ Calling tool: {t_name}...")
                    
                    elif etype == "tool_end":
                        t_name = event.get("tool")
                        print(f"✅ {t_name} complete.")
                    
                    elif etype == "approval_required":
                        print(f"\n\n🛑 APPROVAL REQUIRED: {event['tool_name']}")
                        print(f"Arguments: {event['tool_args']}")
                        print(f"Message: {event['message']}")
                        
                        choice = input("\n✅ Approve execution? (y/n): ").strip().lower()
                        if choice == 'y':
                            mcp_manager.whitelist_tool(event['tool_name'], event['tool_args'])
                            print("🚀 Resuming execution...")
                            # Restart the generator with the SAME history and input
                            # The whitelist ensures it won't trigger again
                            full_agent_response = ""
                            async for sub_event in agent.execute_streaming(user_input, history[:-1]):
                                sex_type = sub_event.get("type")
                                if sex_type == "token":
                                    content = sub_event.get("content", "")
                                    print(content, end="", flush=True)
                                    full_agent_response += content
                                elif sex_type == "tool_start":
                                    print(f"\n🛠️ Calling tool: {sub_event.get('tool')}...")
                                elif sex_type == "tool_end":
                                    print(f"✅ {sub_event.get('tool')} complete.")
                                elif sex_type == "error":
                                    print(f"\n❌ Error during resumed execution: {sub_event.get('message')}")
                                    full_agent_response += f"\n❌ Error: {sub_event.get('message')}"
                            break
                        else:
                            print("❌ Execution rejected.")
                            full_agent_response += f"\n[User rejected execution of {event['tool_name']}]"
                            # We stop here for this turn
                            break
                
                print("\n")
                history.append(AIMessage(content=full_agent_response))
            else:
                # Direct response already streamed from Planner if response was present
                if not prefix_printed and plan.get("response"):
                     print(f"\n🤖: {plan['response']}")
                
                print("\n")
                from langchain_core.messages import HumanMessage, AIMessage
                history.append(HumanMessage(content=user_input))
                history.append(AIMessage(content=plan.get("response", full_direct_response)))
            
            # --- PERSISTENCE PHASE ---
            await save_history(thread_id, tenant_id, user_id, history)

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            # Suppress noisy cancel scope errors during turn processing
            if "cancel scope" not in str(e):
                print(f"\n❌ Error: {str(e)}")
                import traceback
                traceback.print_exc()
        finally:
             # Regular cleanup
             pass
             
    # Final cleanup before exiting main()
    try:
        await mcp_manager.cleanup()
    except Exception:
        pass

def custom_exception_handler(loop, context):
    exception = context.get("exception")
    # Mask anyio/mcp-use internal cleanup noise
    if exception and isinstance(exception, (RuntimeError, Exception)):
        exc_str = str(exception)
        if "cancel scope" in exc_str or "session" in exc_str:
            return
    loop.default_exception_handler(context)

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(custom_exception_handler)
    
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()

