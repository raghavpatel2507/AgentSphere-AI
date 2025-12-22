"""
AgentSphere-AI Streamlit UI (v2.0)

A comprehensive chat interface using the new Planner/Agent architecture.
"""

import streamlit as st
import asyncio
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

# Set page config first
st.set_page_config(
    page_title="AgentSphere AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

import logging
# Silence chatty loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp_use").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# Windows event loop policy fix
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# nest_asyncio is REQUIRED for Streamlit + PostgreSQL (asyncpg)
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    st.warning("⚠️ `nest_asyncio` is missing. This is required for database stability in Streamlit. Please run: `pip install nest_asyncio`")
    # We don't stop here, but it will likely crash during DB operations if not installed

@st.cache_resource
def get_stable_loop():
    """Create and return a stable event loop that persists across reruns."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop

def run_async(coro):
    loop = get_stable_loop()
    # Ensure this loop is the current one for this thread
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# Project Modules
from src.core.agents.planner import Planner
from src.core.agents.agent import Agent
from src.core.mcp.manager import MCPManager
from src.core.llm.provider import LLMFactory
from src.core.state import (
    init_checkpointer, 
    get_or_create_session,
    clear_current_session,
    load_history,
    save_history
)

def load_custom_css():
    st.markdown("""
    <style>
        .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        .user-message { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; border-radius: 1rem; margin: 0.5rem 0; width: fit-content; max-width: 80%; margin-left: auto; }
        .assistant-message { background: #1f2937; color: white; padding: 1rem; border-radius: 1rem; margin: 0.5rem 0; width: fit-content; max-width: 85%; border: 1px solid #374151; }
        .event-log { background: #000; color: #0f0; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

def init_session_state():
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
        st.session_state.messages = []
        st.session_state.history = []
        st.session_state.events = []
        st.session_state.thread_id = None
        st.session_state.planner = None
        st.session_state.agent = None
        st.session_state.mcp_manager = None
        st.session_state.is_processing = False
        st.session_state.tenant_id = None
        st.session_state.user_id = None
        st.session_state.pending_approval = None

async def initialize_app():
    await init_checkpointer()
    manager = MCPManager()
    await manager.initialize()
    
    # We load LLM and Planner once
    llm = LLMFactory.load_config_and_create_llm()
    planner = Planner(api_key=os.getenv("OPENROUTER_API_KEY"))
    
    # Use valid UUIDs for database compatibility (default tenant from migration)
    tenant_id = os.getenv("DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001")
    user_id = os.getenv("DEFAULT_USER_ID", "00000000-0000-0000-0000-000000000001")
    
    thread_id, is_new = get_or_create_session(tenant_id)
    history = await load_history(thread_id, tenant_id, user_id)
    
    return planner, manager, thread_id, history, is_new, tenant_id, user_id

async def process_message_async(user_input: str, planner, mcp_manager, history, thread_id, tenant_id, user_id):
    events = []
    full_response = ""
    
    try:
        # 1. PLANNING PHASE (with streaming support for direct response)
        available_servers = await mcp_manager.get_all_tools_status()
        
        container = st.empty()
        full_direct_response = ""
        plan = None
        
        async for chunk in planner.plan(user_input, history, available_servers):
            if isinstance(chunk, str):
                full_direct_response += chunk
                container.markdown(full_direct_response)
            else:
                plan = chunk
        
        # 2. EXECUTION PHASE
        if plan.get("servers"):
            events.append({"type": "info", "content": f"🔌 Connecting to: {', '.join(plan['servers'])}", "ts": datetime.now().strftime("%H:%M:%S")})
            
            # Instant Connection
            await mcp_manager.connect_to_servers(plan['servers'])
            if mcp_manager._mcp_client:
                mcp_manager._mcp_client.allowed_servers = list(plan['servers'])
                
            # EXECUTION: Refresh agent every turn
            llm = LLMFactory.load_config_and_create_llm()
            agent = Agent(llm=llm, mcp_client=mcp_manager._mcp_client)
            
            from langchain_core.messages import HumanMessage, AIMessage
            history.append(HumanMessage(content=user_input))
            
            # Continue streaming from the same container or a new one?
            # Usually better to clear or use the same for continuity
            full_agent_response = ""
            async for chunk in agent.execute_streaming(user_input, history[:-1]):
                if isinstance(chunk, str):
                    full_agent_response += chunk
                    container.markdown(full_agent_response)
                elif isinstance(chunk, dict):
                    if chunk.get("event") == "approval_required":
                         # Store in session state and STOP this turn
                         st.session_state.pending_approval = {
                             "tool_name": chunk["tool_name"],
                             "tool_args": chunk["tool_args"],
                             "message": chunk["message"],
                             "user_input": user_input, # Save to restart after approval
                             "history_before": history[:-1] # Save state before this agent run
                         }
                         st.session_state.is_processing = False
                         st.rerun()
                    elif chunk.get("event") == "error":
                         st.error(chunk.get("message"))
                         full_agent_response += f"\n\n❌ {chunk.get('message')}"
            
            full_response = full_agent_response
            history.append(AIMessage(content=full_response))
        else:
            from langchain_core.messages import HumanMessage, AIMessage
            full_response = plan.get("response", full_direct_response) or "I can help with that."
            # If it wasn't already streamed (unlikely), show it now
            if not full_direct_response:
                container.markdown(full_response)
            
            history.append(HumanMessage(content=user_input))
            history.append(AIMessage(content=full_response))
            
        await save_history(thread_id, tenant_id, user_id, history)
    except Exception as e:
        events.append({"type": "error", "content": str(e), "ts": datetime.now().strftime("%H:%M:%S")})
        full_response = f"Error: {e}"
        st.error(full_response)
        
    return full_response, history, events

def render_sidebar():
    with st.sidebar:
        st.markdown("# 🤖 AgentSphere AI")
        if st.button("🆕 New Chat"):
            clear_current_session()
            st.session_state.initialized = False
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 🔌 Servers")
        if st.session_state.mcp_manager:
            status = run_async(st.session_state.mcp_manager.get_all_tools_status())
            for s_name, s_info in status.items():
                icon = "🟢" if s_info['connected'] else "🔴"
                st.write(f"{icon} {s_name} ({s_info['tools_count']} tools)")

def render_main_chat():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
    if prompt := st.chat_input("Message..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            resp, hist, evs = run_async(process_message_async(
                prompt, 
                st.session_state.planner,
                st.session_state.mcp_manager,
                st.session_state.history,
                st.session_state.thread_id,
                st.session_state.tenant_id,
                st.session_state.user_id
            ))
            st.session_state.messages.append({"role": "assistant", "content": resp})
            st.session_state.history = hist
            st.session_state.events.extend(evs)
    
    # HITL Approval UI Overlay
    if st.session_state.pending_approval:
        with st.chat_message("assistant"):
            pa = st.session_state.pending_approval
            st.warning(f"🛠️ **Approval Required**: `{pa['tool_name']}`")
            st.json(pa['tool_args'])
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve", use_container_width=True):
                    # Resume: Add whitelisted tool for JUST this next turn or inject as tool result
                    # For "Pause & Resume via History", we need to inject a ToolMessage.
                    # But MCPAgent manages history internally. 
                    # The easiest way is to whitelist the tool for THIS session name.
                    st.session_state.mcp_manager.whitelist_tool(pa['tool_name'])
                    
                    # Store variables for rerun
                    u_input = pa['user_input']
                    
                    # Clear pending
                    st.session_state.pending_approval = None
                    
                    # Trigger the same input again - but now it's whitelisted!
                    # We append a hidden message or just re-run process_message_async
                    resp, hist, evs = run_async(process_message_async(
                        u_input, 
                        st.session_state.planner,
                        st.session_state.mcp_manager,
                        st.session_state.history,
                        st.session_state.thread_id,
                        st.session_state.tenant_id,
                        st.session_state.user_id
                    ))
                    st.session_state.messages.append({"role": "assistant", "content": resp})
                    st.session_state.history = hist
                    st.rerun()
                    
            with col2:
                if st.button("❌ Reject", use_container_width=True):
                    st.session_state.pending_approval = None
                    st.error("Action rejected by user.")
                    # Optional: Add "Action rejected" to history so agent knows
                    from langchain_core.messages import AIMessage
                    st.session_state.history.append(AIMessage(content="User rejected the tool execution."))
                    st.rerun()

def main():
    init_session_state()
    load_custom_css()
    
    if not st.session_state.initialized:
        with st.spinner("Initializing..."):
            p, m, tid, hist, is_new, tenant_id, user_id = run_async(initialize_app())
            st.session_state.planner = p
            st.session_state.mcp_manager = m
            st.session_state.thread_id = tid
            st.session_state.history = hist
            st.session_state.tenant_id = tenant_id
            st.session_state.user_id = user_id
            st.session_state.messages = [{"role": "user" if msg.type == "human" else "assistant", "content": msg.content} for msg in hist]
            st.session_state.initialized = True
            st.rerun()
            
    render_sidebar()
    render_main_chat()

if __name__ == "__main__":
    main()
