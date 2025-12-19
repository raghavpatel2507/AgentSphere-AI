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

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    st.error("Please install nest_asyncio: pip install nest_asyncio")
    st.stop()

def get_event_loop():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

def run_async(coro):
    loop = get_event_loop()
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
        st.session_state.events = []
        st.session_state.thread_id = None
        st.session_state.planner = None
        st.session_state.agent = None
        st.session_state.mcp_manager = None
        st.session_state.is_processing = False

async def initialize_app():
    await init_checkpointer()
    manager = MCPManager()
    await manager.initialize()
    
    # We load LLM and Planner once
    llm = LLMFactory.load_config_and_create_llm()
    planner = Planner(api_key=os.getenv("OPENROUTER_API_KEY"))
    
    tenant_id = os.getenv("DEFAULT_TENANT_ID", "default")
    thread_id, is_new = get_or_create_session(tenant_id)
    history = await load_history(thread_id)
    
    return planner, manager, thread_id, history, is_new

async def process_message_async(user_input: str, planner, mcp_manager, history, thread_id):
    events = []
    full_response = ""
    
    try:
        # Planning
        available_servers = await mcp_manager.get_all_tools_status()
        plan = await planner.plan(user_input, history, available_servers)
        
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
            
            # Streaming UI placeholder
            container = st.empty()
            async for chunk in agent.execute_streaming(user_input, history[:-1]):
                if isinstance(chunk, str):
                    full_response += chunk
                    container.markdown(full_response)
            
            history.append(AIMessage(content=full_response))
        else:
            from langchain_core.messages import HumanMessage, AIMessage
            full_response = plan.get("response", "I can help with that.")
            history.append(HumanMessage(content=user_input))
            history.append(AIMessage(content=full_response))
            st.markdown(full_response)
            
        await save_history(thread_id, history)
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
                st.session_state.thread_id
            ))
            st.session_state.messages.append({"role": "assistant", "content": resp})
            st.session_state.history = hist
            st.session_state.events.extend(evs)

def main():
    init_session_state()
    load_custom_css()
    
    if not st.session_state.initialized:
        with st.spinner("Initializing..."):
            p, m, tid, hist, is_new = run_async(initialize_app())
            st.session_state.planner = p
            st.session_state.mcp_manager = m
            st.session_state.thread_id = tid
            st.session_state.history = hist
            st.session_state.messages = [{"role": "user" if m.type == "human" else "assistant", "content": m.content} for m in hist]
            st.session_state.initialized = True
            st.rerun()
            
    render_sidebar()
    render_main_chat()

if __name__ == "__main__":
    main()
