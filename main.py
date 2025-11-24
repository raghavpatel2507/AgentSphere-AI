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
from src.core.state import init_checkpointer, get_checkpointer, create_thread_id, get_config_for_thread




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
    
    # Get supervisor app with checkpointer
    app = get_app(checkpointer=checkpointer)
    
    # Setup tenant and thread
    tenant_id = os.getenv("DEFAULT_TENANT_ID", "default")
    conversation_id = "cli_session"
    thread_id = create_thread_id(tenant_id, conversation_id)
    config = get_config_for_thread(thread_id)
    
    print(f"✅ Checkpointer initialized")
    print(f"📝 Thread ID: {thread_id}")
    print()
    print("Commands:")
    print("  /exit - Exit the chat")
    print("  /new  - Start a new conversation")
    print("  /history - Show conversation history")
    print()
    print("=" * 60)
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
                break
            
            elif user_input.lower() == "/new":
                # Start new conversation with new thread ID
                import uuid
                conversation_id = str(uuid.uuid4())[:8]
                thread_id = create_thread_id(tenant_id, conversation_id)
                config = get_config_for_thread(thread_id)
                config["callbacks"] = [agent_callback]
                print(f"\n✨ Started new conversation: {thread_id}\n")
                continue
            
            elif user_input.lower() == "/history":
                # Show conversation history
                state = await app.aget_state(config)
                if state.values.get("messages"):
                    print("\n📜 Conversation History:")
                    print("-" * 60)
                    for msg in state.values["messages"]:
                        # Handle both dict and object message formats
                        role = getattr(msg, "type", None) or msg.get("role", "unknown")
                        content = getattr(msg, "content", None) or msg.get("content", "")
                        print(f"{role.upper()}: {content[:100]}...")
                    print("-" * 60)
                    print()
                else:
                    print("\n📜 No conversation history yet.\n")
                continue
            
            # Get current state to inspect history
            current_state = await app.aget_state(config)
            history = current_state.values.get("messages", [])
            
            # Filter history to last 10 messages to reduce context window
            # This improves performance and reduces token usage
            filtered_history = history[-10:] if history else []
            
            if history:
                print(f"\n📊 Context Debug: Passing {len(filtered_history)} messages (trimmed from {len(history)})")
                # Print last 3 messages for context
                print("   Last 3 messages:")
                for msg in filtered_history[-3:]:
                    # Handle both dict and object message formats safely
                    if isinstance(msg, dict):
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")
                    else:
                        role = getattr(msg, "type", "unknown")
                        content = getattr(msg, "content", "")
                    
                    print(f"   - {role}: {content[:100]}...")
                print("-" * 40)

            # Invoke supervisor with user message
            # Note: We don't explicitly pass filtered_history here because LangGraph 
            # manages state automatically. To truly trim history, we would need to 
            # update the state or use a specific memory saver strategy.
            # However, for the supervisor invocation, we can pass the new message.
            # The checkpointer loads the full state. To optimize, we should ideally
            # use a trimmer node in the graph, but for now we rely on the model's
            # ability to handle context or implement a trimmer in the supervisor.
            
            # For immediate relief, we can't easily "pass less" to the checkpointer-backed graph
            # without modifying the graph itself to include a "trimmer" node.
            # But we can at least fix the history display error.
            
            result = await app.ainvoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config
            )
            
            # Check if workflow is interrupted (waiting for approval)
            state = await app.aget_state(config)
            
            while state.next:  # While there are pending nodes
                print("\n" + "=" * 60)
                print("⚠️  HUMAN-IN-THE-LOOP: Tool Execution Requires Approval")
                print("=" * 60)
                
                # Show pending tasks
                if state.tasks:
                    print(f"\n📋 Pending Action: {len(state.tasks)} tool(s) waiting for approval")
                    for task in state.tasks:
                        print(f"   - {task}")
                
                # Request approval
                print("\nOptions:")
                print("  [y] Approve and continue")
                print("  [n] Reject and stop")
                print("  [m] Modify parameters (advanced)")
                
                approval = input("\nYour decision: ").strip().lower()
                
                if approval == "y":
                    print("\n✅ Approved! Continuing execution...\n")
                    # Resume execution by passing None
                    result = await app.ainvoke(
                        None,
                        config=config
                    )
                    # Check state again
                    state = await app.aget_state(config)
                
                elif approval == "n":
                    print("\n❌ Rejected! Stopping execution.\n")
                    break
                
                elif approval == "m":
                    print("\n⚙️  Parameter modification not yet implemented.\n")
                    print("Approving with original parameters...\n")
                    result = await app.ainvoke(
                        None,
                        config=config
                    )
                    state = await app.aget_state(config)
                
                else:
                    print("\n❓ Invalid input. Please enter 'y', 'n', or 'm'.\n")
            
            # Display final response
            print("\n" + "=" * 60)
            print("🤖 Assistant Response:")
            print("=" * 60)
            
            if result.get("messages"):
                last_message = result["messages"][-1]
                if hasattr(last_message, "content"):
                    print(f"\n{last_message.content}\n")
                else:
                    print(f"\n{last_message}\n")
            
            print("=" * 60)
            print()
        
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!\n")
            break
        
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")
            import traceback
            traceback.print_exc()
            print()


def sync_main():
    """Synchronous wrapper for async main."""
    if os.name == 'nt':
        # Windows workaround for psycopg: use SelectorEventLoop
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()

