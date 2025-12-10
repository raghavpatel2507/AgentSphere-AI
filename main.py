"""
AgentSphere-AI Main Entry Point

Continuous chat interface with:
- PostgreSQL state persistence
- Human-in-the-loop (HITL) tool approval
- Multi-tenant support
- Conversation memory
"""

import asyncio
import os
from src.core.agents.supervisor import get_app
from src.core.agents.callbacks import AgentCallbackHandler
from src.core.mcp.manager import MCPManager
from langgraph.types import Command
from src.core.state import (
    init_checkpointer, 
    get_checkpointer, 
    get_or_create_session,
    clear_current_session,
    get_config_for_thread
)
from src.core.mcp.manager import MCPManager





def print_prompt_data(messages, title="Prompt Data"):
    """
    Pretty-print the messages being sent to the model.
    This shows exactly what the supervisor receives after trimming.
    """
    print("\n" + "=" * 70)
    print(f"📋 {title}")
    print("=" * 70)
    print(f"Total messages: {len(messages)}")
    print()
    
    for idx, msg in enumerate(messages, 1):
        msg_type = type(msg).__name__.replace("Message", "")
        content = msg.content if hasattr(msg, "content") else str(msg)
        
        # Show truncated content
        display_content = content[:200] + "..." if len(content) > 200 else content
        
        print(f"[{idx}] {msg_type}:")
        print(f"    {display_content}")
        print()
    
    # Rough token estimate (4 chars ≈ 1 token)
    total_chars = sum(len(msg.content if hasattr(msg, "content") else str(msg)) for msg in messages)
    estimated_tokens = total_chars // 4
    print(f"Estimated tokens: ~{estimated_tokens:,}")
    print("=" * 70)
    print()



def build_agent_app(checkpointer):
    """
    Builds the LangGraph application. 
    Can be called repeatedly for hot swapping.
    """
    return get_app(checkpointer=checkpointer)

async def main():
    """Main async function for continuous chat with HITL."""
    
    print("=" * 60)
    print("🤖 AgentSphere-AI - Continuous Chat with HITL")
    print("=" * 60)
    print()
    
    # Initialize checkpointer
    print("🔄 Initializing PostgreSQL checkpointer...")
    await init_checkpointer()
    checkpointer = get_checkpointer()
    
    # Initialize dynamic agents
    print("🔄 Initializing Dynamic Agents...")
    from src.core.agents.agent import get_dynamic_agents, dynamic_experts
    experts = await get_dynamic_agents()
    dynamic_experts.update(experts)
    print(f"✅ Initialized {len(experts)} dynamic experts")
    
    # 1. Build app initially
    app = build_agent_app(checkpointer)
    
    # Setup tenant and get/create session
    tenant_id = os.getenv("DEFAULT_TENANT_ID", "default")
    
    # Smart session management: resume existing or create new
    thread_id, is_new = get_or_create_session(tenant_id)
    config = get_config_for_thread(thread_id)
    
    print(f"✅ Checkpointer initialized")
    print(f"📝 Thread ID: {thread_id}")
    if is_new:
        print(f"✨ Started NEW conversation")
    else:
        print(f"🔄 RESUMED existing conversation")
    print()
    print("Commands:")
    print("  /exit - Exit the chat")
    print("  /new  - Start a new conversation (fresh thread)")
    print("  /history - Show conversation history")
    print()
  
    print()
    
    # Callback handler
    agent_callback = AgentCallbackHandler()
    config["callbacks"] = [agent_callback]
    
    # Continuous chat loop
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.lower() == "/exit":
                print("\n👋 Goodbye!\n")
                print("🔄 Cleaning up MCP connections...")
                manager = MCPManager()
                await manager.cleanup()
                print("✅ Cleanup complete\n")
                break
            
            elif user_input.lower() == "/new":
                clear_current_session()
                thread_id, _ = get_or_create_session(tenant_id)
                config = get_config_for_thread(thread_id)
                config["callbacks"] = [agent_callback]
                print(f"\n✨ Started new conversation: {thread_id}\n")
                continue

            elif user_input.lower() == "/reload":
                # Deep Reload: Restarts MCP connections
                manager = MCPManager()
                manager.reload_config()
                
                print("🔄 Deep reloading agents...")
                # Re-fetch all dynamic agents (forces MCP discovery)
                experts = await get_dynamic_agents()
                dynamic_experts.update(experts)
                
                # Rebuild app
                app = build_agent_app(checkpointer)
                print("\n✅ Configuration and Agents reloaded!\n")
                continue
            
            elif user_input.lower() == "/history":
                state = await app.aget_state(config)
                if state.values.get("messages"):
                    print("\n📜 Conversation History:")
                    print("-" * 60)
                    for msg in state.values["messages"]:
                        msg_type = type(msg).__name__.replace("Message", "").upper()
                        content = msg.content if hasattr(msg, "content") else str(msg)
                        display_content = content[:100] + "..." if len(content) > 100 else content
                        print(f"{msg_type}: {display_content}")
                    print("-" * 60)
                    print(f"\nTotal messages: {len(state.values['messages'])}")
                    print()
                else:
                    print("\n📜 No conversation history yet.\n")
                continue

            elif user_input.lower().startswith("/tools"):
                manager = MCPManager()
                args = user_input.split()
                if len(args) > 1:
                    # Specific tool/agent search (simplified)
                    # We can pass the name to explore
                    requested_name = args[1]
                    print(f"\n🔍 Searching for tools matching '{requested_name}'...\n")
                    
                    found = False
                    status = await manager.get_all_tools_status()
                    for s_name, s_info in status.items():
                        if requested_name.lower() in s_name.lower():
                            print(f"📦 Server: {s_name} ({'Enabled' if s_info['enabled'] else 'Disabled'})")
                            if s_info.get('error'):
                                print(f"   ❌ Error: {s_info['error']}")
                            elif not s_info['tools']:
                                print("   ⚠️  No tools found.")
                            else:
                                for t in s_info['tools']:
                                    status_icon = "🟢" if t['active'] else "🔴"
                                    print(f"   {status_icon} {t['name']}")
                                    print(f"      {t['description']}")
                            found = True
                    if not found:
                         print("❌ No matching server found.")
                else:
                    # List all servers
                    status = await manager.get_all_tools_status()
                    print("\n🛠️  MCP Servers Status:")
                    print("-" * 60)
                    print(f"{'Server Name':<20} | {'Enabled':<8} | {'Connected':<10} | {'Tools':<5}")
                    print("-" * 60)
                    for s_name, s_info in status.items():
                        enabled = "✅" if s_info['enabled'] else "❌"
                        connected = "✅" if s_info['connected'] else "❌"
                        tool_count = len(s_info['tools'])
                        print(f"{s_name:<20} | {enabled:<8} | {connected:<10} | {tool_count:<5}")
                    print("-" * 60)
                    print("Use /tools <name> to see details.\n")
                continue

            elif user_input.lower().startswith("/enable"):
                manager = MCPManager()
                args = user_input.split()
                if len(args) > 1:
                    res = await manager.toggle_tool_status(args[1], True)
                    print(f"\n✅ {res}")
                    
                    # HOT SWAP
                    print("🔄 Hot-swapping agent logic...")
                    experts = await get_dynamic_agents() # Refresh tools
                    dynamic_experts.update(experts)
                    app = build_agent_app(checkpointer)
                    print("⚡ Agent updated instantly!\n")
                else:
                     print("\nUsage: /enable <tool_name>\n")
                continue

            elif user_input.lower().startswith("/disable"):
                manager = MCPManager()
                args = user_input.split()
                if len(args) > 1:
                    res = await manager.toggle_tool_status(args[1], False)
                    print(f"\n⛔ {res}")
                    
                    # HOT SWAP
                    print("🔄 Hot-swapping agent logic...")
                    experts = await get_dynamic_agents()
                    dynamic_experts.update(experts)
                    app = build_agent_app(checkpointer)
                    print("⚡ Agent updated instantly!\n")
                else:
                     print("\nUsage: /disable <tool_name>\n")
                continue
            
            # Streaming Loop
            print("\n" + "🤖 " * 30)
            print()
            
            try:
                # Use astream_events for granular token streaming
                async for event in app.astream_events(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config=config,
                    version="v2"
                ):
                    kind = event["event"]
                    
                    if kind == "on_chat_model_stream":
                        content = event["data"]["chunk"].content
                        if content:
                            print(content, end="", flush=True)
                            
                    elif kind == "on_tool_start":
                        print(f"\n\n🛠️  Running tool: {event['name']}...")
                        inputs = event['data'].get('input')
                        if inputs:
                            print(f"   Input: {str(inputs)[:200]}...")
                        
                    elif kind == "on_tool_end":
                         output = str(event['data'].get('output'))
                         print(f"✅ Output: {output[:200]}...")
                         print("\n", end="", flush=True) # Spacing back to normal flow

            except Exception as e:
                # pass interrupts
                pass
            
            print("\n") # Final newline

            # Check for interrupts (HITL)
            state = await app.aget_state(config)
            
            if state.tasks and (parsed_interrupt := state.tasks[0].interrupts):
                # We have an interrupt!
                interrupt_value = parsed_interrupt[0].value
                
                print("\n" + "=" * 60)
                print("⚠️  HUMAN-IN-THE-LOOP APPROVAL REQUIRED")
                print("=" * 60)
                
                tool_name = interrupt_value.get("tool_name", "Unknown")
                tool_args = interrupt_value.get("tool_args", {})
                message = interrupt_value.get("message", "Approve?")
                
                print(f"\n🛠️  Tool: {tool_name}")
                print(f"📋 Args: {tool_args}")
                print(f"❓ {message}")
                
                print("\nOptions:")
                print("  [y] Approve")
                print("  [a] Approve for Session (Auto-approve future calls)")
                print("  [n] Reject")
                
                decision = input("\nDecision: ").strip().lower()
                
                if decision in ["y", "yes"]:
                    print("\n✅ Approved. Resuming...\n")
                    resume_value = {"action": "approve"}
                    
                    # Resume stream
                    async for chunk in app.astream(
                        Command(resume=resume_value),
                        config=config,
                        stream_mode="updates"
                    ):
                         for node, values in chunk.items():
                            if "messages" in values:
                                print(f"\n[{node}]: {values['messages'][-1].content}\n")

                elif decision in ["a", "all", "always"]:
                    print(f"\n✅ Approved {tool_name} for this session. Resuming...\n")
                    resume_value = {"action": "approve_forever"}
                    
                    # Resume stream
                    async for chunk in app.astream(
                        Command(resume=resume_value),
                        config=config,
                        stream_mode="updates"
                    ):
                         for node, values in chunk.items():
                            if "messages" in values:
                                print(f"\n[{node}]: {values['messages'][-1].content}\n")
                                
                else:
                    print("\n❌ Rejected.\n")
                    resume_value = {"action": "reject"}
                    
                    # Resume stream (wont execute tool, will raise error in manager)
                    try:
                        async for chunk in app.astream(
                            Command(resume=resume_value),
                            config=config,
                            stream_mode="updates"
                        ):
                             pass
                    except Exception as e:
                        print(f"Error after rejection: {e}")

            print("=" * 60)
            print()
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!\n")
            # Cleanup MCP connections before exit
            print("🔄 Cleaning up MCP connections...")
            manager = MCPManager()
            await manager.cleanup()
            print("✅ Cleanup complete\n")
            break
        
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")
            import traceback
            traceback.print_exc()
            print()


def custom_exception_handler(loop, context):
    """Custom exception handler to suppress known MCP cleanup errors."""
    exception = context.get("exception")
    message = context.get("message", "")
    
    # Suppress known anyio cancel scope errors during MCP cleanup
    if exception and isinstance(exception, RuntimeError):
        error_msg = str(exception)
        if "cancel scope" in error_msg or "GeneratorExit" in error_msg:
            # This is expected during MCP server cleanup, silently ignore
            return
    
    # Suppress BaseExceptionGroup errors from anyio task groups
    if "unhandled errors in a TaskGroup" in message:
        return
    
    # For all other exceptions, use the default handler
    loop.default_exception_handler(context)


def sync_main():
    """Synchronous wrapper for async main."""
    if os.name == 'nt':
        # Windows workaround for psycopg: use SelectorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Set custom exception handler to suppress MCP cleanup errors
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(custom_exception_handler)
    
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()


if __name__ == "__main__":
    sync_main()
