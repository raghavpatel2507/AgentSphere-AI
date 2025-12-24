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
import requests
import urllib.parse
from urllib.parse import urlencode
import uuid

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
def get_loop_factory():
    """Returns a holder for the loop to allow mutability inside cache."""
    return {"loop": None}

def get_stable_loop():
    """Create and return a stable event loop that persists across reruns."""
    holder = get_loop_factory()
    if holder["loop"] is None or holder["loop"].is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        holder["loop"] = loop
    return holder["loop"]

def run_async(coro):
    try:
        loop = get_stable_loop()
        # Ensure this loop is the current one for this thread
        asyncio.set_event_loop(loop)
        if loop.is_running():
            # If we are already in a running loop (unlikely in Streamlit script runner, but possible if nested)
            # using nested_asyncio we might be able to create a future?
            # actually safe to simple run? not if loop is running.
            # For now assume sync context calling async
            import concurrent.futures
            # If loop is running, we can't use run_until_complete.
            # But Streamlit script execution is usually synchronous main thread.
            pass
        return loop.run_until_complete(coro)
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
             # Force recreate
             holder = get_loop_factory()
             loop = asyncio.new_event_loop()
             asyncio.set_event_loop(loop)
             holder["loop"] = loop
             return loop.run_until_complete(coro)
        raise e

# Project Modules
from src.core.agents.planner import Planner
from src.core.agents.agent import Agent
from src.core.mcp.manager import MCPManager
from src.core.llm.provider import LLMFactory
from src.core.auth.service import AuthService
from src.core.state import (
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
        .auth-container { max-width: 400px; margin: 100px auto; padding: 2rem; background: #1f2937; border-radius: 1rem; border: 1px solid #374151; }
    </style>
    """, unsafe_allow_html=True)

def init_session_state():
    if "initialized" not in st.session_state:
        st.session_state.user = None
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

async def initialize_app(user_id: Any):
    # Instantiate Manager with user_id
    manager = MCPManager(user_id=user_id)
    await manager.initialize()
    
    # We load LLM and Planner once
    llm = LLMFactory.load_config_and_create_llm()
    planner = Planner(api_key=os.getenv("OPENROUTER_API_KEY"))
    
    # Use valid UUIDs for database compatibility
    # Tenant ID could also be user-specific, for now we use a default tenant
    tenant_id = os.getenv("DEFAULT_TENANT_ID", "00000000-0000-0000-0000-000000000001")
    
    thread_id, is_new = get_or_create_session(tenant_id)
    history = await load_history(thread_id, tenant_id, user_id)
    
    return planner, manager, thread_id, history, is_new, tenant_id, user_id

def render_login_page():
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    st.title("🔐 Login")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login", use_container_width=True):
            user = run_async(AuthService.authenticate_user(email, password))
            if user:
                st.session_state.user = user
                st.success("Welcome back!")
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        r_email = st.text_input("Email", key="reg_email")
        r_pw = st.text_input("Password", type="password", key="reg_pw")
        r_name = st.text_input("Full Name", key="reg_name")
        if st.button("Register", use_container_width=True):
            try:
                user = run_async(AuthService.register_user(r_email, r_pw, r_name))
                st.session_state.user = user
                st.success("Account created!")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    
    st.markdown('</div>', unsafe_allow_html=True)

async def process_message_async(user_input: str, planner, mcp_manager, history, thread_id, tenant_id, user_id):
    events = []
    full_response = ""
    
    try:
        # 1. PLANNING PHASE (with streaming support for direct response)
        # Fetch status but filtering for Planner: Only show ENABLED servers
        full_status = await mcp_manager.get_all_tools_status()
        available_servers = {
            k: v for k, v in full_status.items() 
            if v.get("enabled", True)
        }
        
        # Main message container
        message_container = st.empty()
        full_direct_response = ""
        plan = None
        
        # Planning visualization
        with st.status("🧠 Thinking...", expanded=True) as plan_status:
            async for chunk in planner.plan(user_input, history, available_servers):
                if isinstance(chunk, str):
                    full_direct_response += chunk
                    message_container.markdown(full_direct_response)
                else:
                    plan = chunk
            plan_status.update(label="🧠 Thought process complete", state="complete", expanded=False)
        
        # 2. EXECUTION PHASE
        if plan.get("servers"):
            with st.spinner("🔌 Initiating Agents..."):
                await mcp_manager.connect_to_servers(plan['servers'])
                if mcp_manager._mcp_client:
                    mcp_manager._mcp_client.allowed_servers = list(plan['servers'])
            
            # EXECUTION: Refresh agent every turn
            llm = LLMFactory.load_config_and_create_llm()
            # Get wrapped tools (with HITL guards)
            tools = await mcp_manager.get_tools_for_servers(plan['servers'])
            agent = Agent(llm=llm, mcp_client=mcp_manager._mcp_client, tools=tools)
            
            from langchain_core.messages import HumanMessage, AIMessage
            history.append(HumanMessage(content=user_input))
            
            full_agent_response = ""
            
            # Status container for tool tracking
            status = st.status("🤖 Agent is working...", expanded=True)
            
            async for event in agent.execute_streaming(user_input, history[:-1]):
                etype = event.get("type")
                
                if etype == "token":
                    full_agent_response += event["content"]
                    message_container.markdown(full_agent_response)
                
                elif etype == "tool_start":
                    t_name = event.get("tool")
                    status.update(label=f"🛠️ Tool: `{t_name}`")
                    with status:
                        with st.expander(f"Parameters: `{t_name}`", expanded=False):
                            st.json(event.get("inputs", {}))
                
                elif etype == "tool_end":
                    t_name = event.get("tool")
                    status.update(label=f"✅ `{t_name}` finished.")
                    with status:
                        with st.expander(f"Result: `{t_name}`", expanded=False):
                            st.markdown(event.get("output", "Done"))
                
                elif etype == "approval_required":
                    # Store in session state and STOP this turn
                    st.session_state.pending_approval = {
                        "tool_name": event["tool_name"],
                        "tool_args": event["tool_args"],
                        "message": event["message"],
                        "user_input": user_input, 
                        "history_before": history[:-1]
                    }
                    st.session_state.is_processing = False
                    st.rerun()
                
                elif etype == "error":
                    st.error(event.get("message"))
                    full_agent_response += f"\n\n❌ {event.get('message')}"
            
            status.update(label="✨ Task Complete", state="complete", expanded=False)
            
            full_response = full_agent_response
            history.append(AIMessage(content=full_response))
        else:
            from langchain_core.messages import HumanMessage, AIMessage
            full_response = plan.get("response", full_direct_response) or "I can help with that."
            # If it wasn't already streamed (unlikely), show it now
            if not full_direct_response:
                message_container.markdown(full_response)
            
            history.append(HumanMessage(content=user_input))
            history.append(AIMessage(content=full_response))
            
        await save_history(thread_id, tenant_id, user_id, history)
    except Exception as e:
        events.append({"type": "error", "content": str(e), "ts": datetime.now().strftime("%H:%M:%S")})
        full_response = f"Error: {e}"
        st.error(full_response)
        
    return full_response, history, events

# -----------------------------------------------------------------------------
# OAuth & Server Management Logic
# -----------------------------------------------------------------------------
def get_google_auth_url(client_id: str, redirect_uri: str, scopes: List[str]) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": "google_drive_connect" 
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

def exchange_google_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> Optional[Dict]:
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    try:
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Token exchange failed: {response.text}")
            return None
    except Exception as e:
        st.error(f"Token exchange error: {e}")
        return None

async def handle_oauth_callback():
    """Check for OAuth code in query params and handle server addition."""
    # Use st.query_params (New Streamlit API)
    query_params = st.query_params
    code = query_params.get("code")
    state = query_params.get("state")
    
    if code and state == "google_drive_connect":
        st.toast("Processing Google Drive Connection...", icon="🔄")
        
        # We need credentials. Best effort: check Env or use what was saved in session
        c_id = os.getenv("GOOGLE_CLIENT_ID") or st.session_state.get("temp_oauth_client_id")
        c_secret = os.getenv("GOOGLE_CLIENT_SECRET") or st.session_state.get("temp_oauth_client_secret")
        
        if not c_id or not c_secret:
            st.error("Missing Client ID/Secret for token exchange. Please add them to .env or settings.")
            return

        redirect_uri = "http://localhost:8501" # Default for local streamlit
        
        token_data = exchange_google_code(code, c_id, c_secret, redirect_uri)
        
        if token_data:
            access_token = token_data.get("access_token")
            
            # Construct Google Drive Server Config
            config = {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-gdrive"],
                "env": {
                    "GOOGLE_DRIVE_TOKEN": access_token 
                }
            }
            
            server_name = "google-drive"
            if st.session_state.mcp_manager:
                success = await st.session_state.mcp_manager.add_server(server_name, config)
                if success:
                    st.success("✅ Google Drive Connected Successfully!")
                    st.query_params.clear()
                    # Rerun to clear URL
                    # st.rerun()
                else:
                    st.error("Failed to add server.")

@st.dialog("Manage Servers")
def render_server_manager_dialog():
    st.subheader("Add / Manage Servers")
    
    tab1, tab2, tab3 = st.tabs(["Add Server", "Installed Servers", "HITL Settings"])
    
    with tab3:
        st.markdown("#### Human-In-The-Loop Settings")
        if st.session_state.mcp_manager:
            curr_config = st.session_state.mcp_manager.config_data.get("hitl_config", {})
            
            enabled = st.toggle("Enable HITL Approval", value=curr_config.get("enabled", True))
            
            mode = st.radio("HITL Mode", ["denylist", "allowlist"], 
                          index=0 if curr_config.get("mode") == "denylist" else 1,
                          help="Denylist: Approve only sensitive tools. Allowlist: Approve ALL tools.")
            
            sensitive_tools_str = st.text_area(
                "Sensitive Tools (one per line, supports wildcards *)",
                value="\n".join(curr_config.get("sensitive_tools", [])),
                help="Only used in denylist mode. Matches against either the full name (e.g. gmail_server__send) OR the base name (e.g. send)."
            )
            
            msg = st.text_input("Approval Message", value=curr_config.get("approval_message", "Execution requires your approval."))
            
            if st.button("Save HITL Settings", use_container_width=True):
                new_config = {
                    "enabled": enabled,
                    "mode": mode,
                    "sensitive_tools": [s.strip() for s in sensitive_tools_str.split("\n") if s.strip()],
                    "approval_message": msg
                }
                success = run_async(st.session_state.mcp_manager.update_user_hitl_config(new_config))
                if success:
                    st.success("✅ HITL Settings Updated!")
                    st.rerun()
                else:
                    st.error("Failed to update settings.")
    
    with tab1:
        st.markdown("#### Add New Server")
        server_type = st.selectbox("Server Type", ["NPM / Node (stdio)", "Python (stdio)", "SSE (URL)", "Google Drive (OAuth)"])
        
        server_name = st.text_input("Server Name (unique)", value="my-server")
        
        if server_type == "Google Drive (OAuth)":
            st.info("Connect to Google Drive using OAuth.")
            c_id = st.text_input("Client ID", value=os.getenv("GOOGLE_CLIENT_ID", ""), type="password")
            c_secret = st.text_input("Client Secret", value=os.getenv("GOOGLE_CLIENT_SECRET", ""), type="password")
            
            if st.button("Connect Google Drive"):
                if not c_id or not c_secret:
                    st.error("Client ID and Secret are required.")
                else:
                    # Save to session/env for callback
                    st.session_state["temp_oauth_client_id"] = c_id
                    st.session_state["temp_oauth_client_secret"] = c_secret
                    
                    # Redirect
                    scope = ["https://www.googleapis.com/auth/drive.readonly"]
                    redirect_uri = "http://localhost:8501"
                    url = get_google_auth_url(c_id, redirect_uri, scope)
                    st.link_button("👉 Click to Authorize", url)
                    
        elif server_type == "SSE (URL)":
            url = st.text_input("Server URL", placeholder="http://localhost:3000/sse")
            if st.button("Add Server"):
                if not url:
                    st.error("URL required")
                else:
                    config = {
                        "url": url,
                        "transport": "sse"
                    }
                    run_async(st.session_state.mcp_manager.add_server(server_name, config))
                    st.success(f"Added {server_name}")
                    st.rerun()
                    
        elif server_type == "NPM / Node (stdio)":
            pkg = st.text_input("Package Name", placeholder="@modelcontextprotocol/server-filesystem")
            args_str = st.text_input("Arguments (space separated)", placeholder=".")
            env_str = st.text_area("Environment Variables (JSON)", value="{}")
            
            if st.button("Add Server"):
                try:
                    env_dict = json.loads(env_str)
                    config = {
                        "command": "npx",
                        "args": ["-y", pkg] + args_str.split(),
                        "env": env_dict
                    }
                    run_async(st.session_state.mcp_manager.add_server(server_name, config))
                    st.success(f"Added {server_name}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

        elif server_type == "Python (stdio)":
            cmd = st.text_input("Command", value="python")
            args_str = st.text_input("Arguments", placeholder="main.py")
            env_str = st.text_area("Environment Vars (JSON)", value="{}")
            
            if st.button("Add Server"):
                try:
                    env_dict = json.loads(env_str)
                    config = {
                        "command": cmd,
                        "args": args_str.split(),
                        "env": env_dict
                    }
                    run_async(st.session_state.mcp_manager.add_server(server_name, config))
                    st.success(f"Added {server_name}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with tab2:
        if st.session_state.mcp_manager:
            status = run_async(st.session_state.mcp_manager.get_all_tools_status())
            
            for s_name, s_info in status.items():
                is_enabled = s_info.get("enabled", True)
                is_connected = s_info.get("connected", False)
                
                # Header Row
                col_icon, col_name, col_status, col_toggle, col_del = st.columns([0.5, 3, 2, 1.5, 0.5])
                
                with col_icon:
                    st.write("🟢" if is_connected else ("🔴" if not is_enabled else "⚪"))
                
                with col_name:
                    st.markdown(f"**{s_name}**")
                
                with col_status:
                    if is_connected:
                        st.caption(f"{s_info['tools_count']} tools running")
                    elif not is_enabled:
                         st.caption("Disabled")
                    else:
                         st.caption("Disconnected (Idle)")
                
                with col_toggle:
                    # Callback wrapper for server toggle
                    def on_server_toggle(s_n=s_name):
                        # Get new state from session state
                        new_state = st.session_state.get(f"server_toggle_{s_n}")
                        run_async(st.session_state.mcp_manager.toggle_server_status(s_n, new_state))

                    st.toggle("Enable", value=is_enabled, key=f"server_toggle_{s_name}", 
                             label_visibility="collapsed", on_change=on_server_toggle)

                with col_del:
                    def on_delete_server(s_n=s_name):
                        run_async(st.session_state.mcp_manager.remove_server(s_n))
                        
                    st.button("🗑️", key=f"del_{s_name}", on_click=on_delete_server)
                
                # Drill Down for Tools
                with st.expander(f"🛠️ Managed Tools ({s_name})"):
                     # Inspect button if not connected standardly
                     if not is_connected and is_enabled:
                         def on_inspect(s_n=s_name):
                             run_async(st.session_state.mcp_manager.inspect_server_tools(s_n))

                         st.button(f"Inspect Tools for {s_name}", key=f"inspect_{s_name}", on_click=on_inspect)
                     
                     current_tools = s_info.get("tools", [])
                     disabled_tools = s_info.get("disabled_tools", [])
                     
                     if current_tools:
                         st.write("Toggle specific tools:")
                         tool_cols = st.columns(3)
                         for i, t_name in enumerate(current_tools):
                             is_tool_enabled = t_name not in disabled_tools
                             
                             def on_tool_toggle(t_n=t_name, s_n=s_name):
                                 # Current checkbox value
                                 new_val = st.session_state.get(f"tool_cb_{s_n}_{t_n}")
                                 run_async(st.session_state.mcp_manager.toggle_tool_status(t_n, new_val))

                             with tool_cols[i % 3]:
                                 st.checkbox(t_name, value=is_tool_enabled, 
                                            key=f"tool_cb_{s_name}_{t_name}",
                                            on_change=on_tool_toggle)
                     else:
                         if is_connected:
                             st.info("No tools found on this server.")
                         else:
                             st.info("Connect or Inspect to see tools.")
                
                st.divider()

def render_sidebar():
    with st.sidebar:
        st.markdown("# 🤖 AgentSphere AI")
        
        if st.session_state.user:
            st.caption(f"👤 {st.session_state.user.email}")
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        
        st.markdown("---")
        
        if st.button("🆕 New Chat", use_container_width=True):
            clear_current_session()
            # Keep user but reset conversation
            st.session_state.initialized = False
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 🔌 Servers")
        if st.session_state.mcp_manager:
            status = run_async(st.session_state.mcp_manager.get_all_tools_status())
            for s_name, s_info in status.items():
                icon = "🟢" if s_info['connected'] else "🔴"
                st.write(f"{icon} {s_name} ({s_info['tools_count']} tools)")
                
            st.markdown("---")
            if st.button("⚙️ Manage Servers", use_container_width=True):
                render_server_manager_dialog()

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
                    # Resume: Add whitelisted tool (name + args) for next execution
                    st.session_state.mcp_manager.whitelist_tool(pa['tool_name'], pa['tool_args'])
                    
                    # Store variables for rerun
                    u_input = pa['user_input']
                    
                    # Clear pending
                    st.session_state.pending_approval = None
                    
                    # Trigger the SAME turn again
                    # The middleware will now skip this tool because it's whitelisted
                    # This is the "Pause & Resume via Whitelist" pattern
                    with st.status("🚀 Resuming...", expanded=True) as status:
                        resp, hist, evs = run_async(process_message_async(
                            u_input, 
                            st.session_state.planner,
                            st.session_state.mcp_manager,
                            st.session_state.history,
                            st.session_state.thread_id,
                            st.session_state.tenant_id,
                            st.session_state.user_id
                        ))
                        # We need to manually append to messages here because we outside the main loop
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
    
    # Auth Guard
    if not st.session_state.user:
        render_login_page()
        return

    if not st.session_state.initialized:
        with st.spinner("Initializing..."):
            # Initialize with logged in user
            p, m, tid, hist, is_new, tenant_id, user_id = run_async(initialize_app(st.session_state.user.id))
            st.session_state.planner = p
            st.session_state.mcp_manager = m
            st.session_state.thread_id = tid
            st.session_state.history = hist
            st.session_state.tenant_id = tenant_id
            st.session_state.user_id = user_id
            st.session_state.messages = [{"role": "user" if msg.type == "human" else "assistant", "content": msg.content} for msg in hist]
            st.session_state.initialized = True
            st.rerun()

    # Process OAuth Callback now that manager is initialized
    if "code" in st.query_params and st.session_state.mcp_manager:
        run_async(handle_oauth_callback())
            
    render_sidebar()
    render_main_chat()

if __name__ == "__main__":
    main()
