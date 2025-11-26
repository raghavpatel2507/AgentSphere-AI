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
from src.core.state import (
    init_checkpointer, 
    get_checkpointer, 
    get_or_create_session,
    clear_current_session,
    get_config_for_thread
)





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
    
    # Get supervisor app with checkpointer
    # Note: get_app calls create_workflow which uses the now-populated dynamic_experts
    app = get_app(checkpointer=checkpointer)
    
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
                break
            
            elif user_input.lower() == "/new":
                # Start new conversation with new thread ID
                clear_current_session()  # Clear old session
                thread_id, _ = get_or_create_session(tenant_id)  # Create fresh one
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
                        # Handle LangChain message objects properly
                        # Messages are AIMessage, HumanMessage, SystemMessage, etc.
                        msg_type = type(msg).__name__.replace("Message", "").upper()
                        content = msg.content if hasattr(msg, "content") else str(msg)
                        
                        # Truncate long messages for display
                        display_content = content[:100] + "..." if len(content) > 100 else content
                        print(f"{msg_type}: {display_content}")
                    print("-" * 60)
                    print(f"\nTotal messages: {len(state.values['messages'])}")
                    print()
                else:
                    print("\n📜 No conversation history yet.\n")
                continue
            
            # Get current state to show what will be sent to supervisor
            current_state = await app.aget_state(config)
            current_messages = current_state.values.get("messages", [])
            
            # Show prompt data for verification
            print("\n" + "🔍 " * 35)
            print("BEFORE TRIMMING:")
            print(f"Total messages in database: {len(current_messages)}")
            print("🔍 " * 35)
            
            # Invoke supervisor with proper error handling
            try:
                result = await app.ainvoke(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config=config
                )
                
                # Show what was actually sent after trimming
                post_state = await app.aget_state(config)
                post_messages = post_state.values.get("messages", [])
                
                print("\n" + "📤 " * 35)
                print("AFTER TRIMMING (Actual prompt sent to model):")
                print_prompt_data(post_messages, "Messages Sent to Supervisor")
                print("📤 " * 35)
                
            except Exception as e:
                error_msg = str(e)
                
                # Handle different types of errors with user-friendly messages
                if "413" in error_msg or "too large" in error_msg.lower():
                    print("\n" + "=" * 70)
                    print("❌ REQUEST TOO LARGE ERROR")
                    print("=" * 70)
                    print("\n📏 Your request exceeds the model's token limit.\n")
                    print("📋 Quick Fix:")
                    print("  1. Edit your .env file")
                    print("  2. Change MAX_TOKENS to a lower value:")
                    print("     MAX_TOKENS=6000  # For openai/gpt-oss-120b")
                    print("  3. Restart the application")
                    print("\n💡 Better Solution - Switch to a model with higher limits:")
                    print("  - llama-3.1-70b-tool-use (128k context)")
                    print("  - llama-3.3-70b-versatile (128k context)")
                    print("  - gemini-2.0-flash-exp (1M context, free!)")
                    print("\n⚠️  Current model (openai/gpt-oss-120b) has only 8k limit - too small!")
                    print("=" * 70)
                    
                elif "429" in error_msg or "quota" in error_msg.lower():
                    print("\n" + "=" * 70)
                    print("❌ QUOTA/RATE LIMIT ERROR")
                    print("=" * 70)
                    print("\n🚫 Your API quota is exceeded or rate limit hit.\n")
                    print("📋 Possible Solutions:")
                    print("  1. Check your OpenAI billing: https://platform.openai.com/usage")
                    print("  2. Add funds to your account")
                    print("  3. Wait a moment and try again (rate limit may reset)")
                    print("  4. Switch to a different model in .env:")
                    print("     - Change MODEL_NAME to 'gpt-3.5-turbo' (cheaper)")
                    print("     - Or use Groq/Gemini (free tier available)")
                    print("\n💡 To switch models:")
                    print("  1. Edit .env file")
                    print("  2. Uncomment a different model in src/core/agents/model.py")
                    print("  3. Restart the application")
                    print("=" * 70)
                    
                elif "401" in error_msg or "unauthorized" in error_msg.lower() or "api" in error_msg.lower() and "key" in error_msg.lower():
                    print("\n" + "=" * 70)
                    print("❌ API KEY ERROR")
                    print("=" * 70)
                    print("\n🔑 Your API key is invalid or missing.\n")
                    print("📋 Solutions:")
                    print("  1. Check your .env file has correct API key")
                    print("  2. Verify key at: https://platform.openai.com/api-keys")
                    print("  3. Make sure .env is loaded (should be in project root)")
                    print("=" * 70)
                    
                elif "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                    print("\n" + "=" * 70)
                    print("❌ NETWORK/CONNECTION ERROR")
                    print("=" * 70)
                    print("\n🌐 Network connection issue.\n")
                    print("📋 Solutions:")
                    print("  1. Check your internet connection")
                    print("  2. Try again in a moment")
                    print("  3. Check if OpenAI API is down: https://status.openai.com")
                    print("=" * 70)
                    
                elif "context_length" in error_msg.lower() or "token" in error_msg.lower():
                    print("\n" + "=" * 70)
                    print("❌ TOKEN LIMIT ERROR")
                    print("=" * 70)
                    print("\n📏 Message context too long.\n")
                    print("📋 Solutions:")
                    print("  1. Lower MAX_TOKENS in .env (try 50000)")
                    print("  2. Start a new conversation with /new")
                    print("  3. Use a model with larger context window")
                    print("=" * 70)
                    
                else:
                    # Generic error
                    print("\n" + "=" * 70)
                    print("❌ UNEXPECTED ERROR")
                    print("=" * 70)
                    print(f"\n💥 Error: {error_msg[:200]}")
                    print("\n📋 Suggestions:")
                    print("  1. Try your request again")
                    print("  2. Use /new to start fresh conversation")
                    print("  3. Check logs above for details")
                    print("=" * 70)
                
                # Continue the conversation loop
                print()
                continue
            
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
                    content = last_message.content
                    
                    # Handle structured content (list of dicts with text/extras)
                    if isinstance(content, list):
                        # Extract text from each item
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                text_parts.append(item["text"])
                            elif isinstance(item, str):
                                text_parts.append(item)
                            else:
                                text_parts.append(str(item))
                        print(f"\n{' '.join(text_parts)}\n")
                    else:
                        # Simple string content
                        print(f"\n{content}\n")
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

