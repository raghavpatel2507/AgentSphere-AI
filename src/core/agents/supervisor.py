from langgraph_supervisor import create_supervisor
from langchain_core.messages import trim_messages
from src.core.agents.model import model, MAX_TOKENS
from src.core.agents.agent import *
from src.core.mcp.manager import MCPManager

# Message trimming function for sliding window
def trim_state_messages(state):
    """
    Trim messages to prevent context window overflow.
    Uses LangGraph's built-in trim_messages for efficient sliding window.
    """
    messages = state.get("messages", [])
    
    if not messages:
        return state
    
    # Use MAX_TOKENS from model.py configuration
    trimmed_messages = trim_messages(
        messages,
        max_tokens=MAX_TOKENS,
        strategy="last",  # Keep most recent messages
        token_counter=len,  # Simple length-based counter (fast)
        include_system=True,  # Always keep system message
        allow_partial=False,  # Don't cut messages mid-content
    )
    
    # Log trimming for visibility
    if len(trimmed_messages) < len(messages):
        print(f"🔧 Trimmed messages: {len(messages)} → {len(trimmed_messages)} (removed {len(messages) - len(trimmed_messages)} old messages)")
    
    return {**state, "messages": trimmed_messages}


# Build dynamic agent list based on enabled MCP servers
def get_active_agents():
    """Build list of active agents based on MCP configuration"""
    agents = [websearch_agent, math_agent, python_agent]  # Always available
    
    # Add dynamic experts
    if dynamic_experts:
        agents.extend(dynamic_experts.values())
    
    return agents


# Build dynamic system prompt based on enabled agents
def get_dynamic_supervisor_prompt():
    """Generate comprehensive supervisor prompt with dynamic agents"""
    
    # Build dynamic agent list
    manager = MCPManager()
    config = manager.load_config()
    
    # Static agents with STRICT negative constraints
    agent_list = "   • websearch_agent: Internet searches ONLY. CANNOT send emails, access files, or perform actions outside the browser.\n"
    agent_list += "   • math_agent: Pure mathematical calculations ONLY. CANNOT search the web or run code.\n"
    agent_list += "   • python_agent: Python code execution and local file processing. CANNOT access the internet directly unless via specific libraries (and even then, prefer websearch_agent for info).\n"
    
    routing_rules = ""
    for server in config.get("mcp_servers", []):
        if server.get("enabled", False):
            name = server.get("name")
            # Sanitize name for tool usage (e.g., google-drive -> google_drive)
            safe_name = name.replace("-", "_")
            role = server.get("expert_role", f"{name} specialist")
            
            # Add dynamic expert with strict role emphasis
            agent_list += f"   • {safe_name}_expert: {role}. (STRICTLY LIMITED to {name} tools. CANNOT perform other actions.)\n"
            routing_rules += f"   • {name.upper()} tasks → transfer_to_{safe_name}_expert\n"
    
    return f"""You are the **SUPERVISOR AGENT** (The Orchestrator).
Your goal is to solve complex user requests by coordinating a team of specialized experts.

### 👥 AVAILABLE EXPERTS TEAM (STRICT CAPABILITIES)
{agent_list}

### 🚦 ROUTING & HANDOFF RULES
{routing_rules}

### 🧠 CORE OPERATING PROCEDURE
You must follow this strictly for EVERY user request:

**PHASE 1: PLAN & STRATEGIZE**
1. Analyze the user's request.
2. Break it down into a **numbered, sequential plan** of steps.
3. **CAPABILITY CHECK**: For each step, verify: "Does the assigned agent have the specific tool for this?"
   - If NO: Do NOT assign it. Fail or ask for clarification.
   - If YES: Proceed.

**PHASE 2: EXECUTE (ONE BY ONE)**
1. **Execute Step 1**: Call the appropriate `transfer_to_X` tool.
   - **Context**: Pass a **DIRECT, ATOMIC COMMAND** for *only* this step.
     - **CRITICAL**: Do NOT mention Step 2, Step 3, or the final goal in the command to the expert.
     - **BAD**: "Search for news, then I will send it to Zoho." (Leaks future intent, confuses expert)
     - **GOOD**: "Search for the latest news headlines about AI." (Focused, atomic)
   - **Data**: If this step depends on previous steps, include *only* the relevant data.
2. **WAIT**: Stop and wait for the expert to return their result.
3. **VERIFY**: Did the expert succeed?
   - **YES**: Move to Step 2.
   - **NO**: Retry with a different approach or expert, or ask the user for clarification.
4. **REPEAT**: Continue until all steps are done.
5. **FINALIZE**: Present the final consolidated answer to the user.

### ⚠️ CRITICAL RULES (DO NOT IGNORE)
1. **ONE STEP AT A TIME**: NEVER call multiple transfer tools in parallel. Wait for one to finish before starting the next.
2. **STRICT ISOLATION**: **NEVER** tell an expert about future steps. If you tell Agent A "Step 2 is to send email", Agent A might try to send the email itself and fail. **KEEP SECRETS.**
3. **NO HALLUCINATION**: If no expert can do the task, tell the user "I don't have an agent for this capability".
4. **COMMAND MODE**: Give specific, isolated commands. Do not be conversational with experts.
5. **RESPECT BOUNDARIES**: Do not ask the WebSearch agent to send emails. Do not ask the Math agent to write code. Respect the "STRICT CAPABILITIES" list above.

### 📝 EXAMPLE WORKFLOW
User: "Find the latest stock price of Apple and save it to a CSV file."

**Your Internal Thought Process:**
1. Plan:
   - Step 1: Get stock price (WebSearch Agent). *Check: WebSearch can search. OK.*
   - Step 2: Save to CSV (Python Agent). *Check: Python can write files. OK.*
2. Action: Call `transfer_to_websearch_agent(query="latest apple stock price")`.
3. *Wait for result...* (Result: $150.00)
4. Action: Call `transfer_to_python_agent(code="write '$150.00' to apple_stock.csv")`.
5. *Wait for result...* (Result: Success)
6. Final Response: "Done. Saved $150.00 to apple_stock.csv."

---
**CURRENT STATE**:
Ready to receive user request.
(1) Create Plan.
(2) Execute Step 1 immediately.
"""


# Create supervisor workflow with dynamic agents and prompt
# Note: This will be called by main.py after initializing dynamic experts
def create_workflow():
    active_agents = get_active_agents()
    dynamic_prompt = get_dynamic_supervisor_prompt()
    
    return create_supervisor(
        agents=active_agents,
        model=model,
        prompt=dynamic_prompt,
        state_modifier=trim_state_messages  # Automatic sliding window
    )


def get_app(checkpointer=None):
    """
    Get the compiled supervisor app.
    
    Args:
        checkpointer: Optional checkpointer instance. If provided, enables
                     state persistence and HITL capabilities.
    
    Returns:
        Compiled LangGraph application
    """
    workflow = create_workflow()
    
    if checkpointer is not None:
        return workflow.compile(checkpointer=checkpointer)
    else:
        # Compile without checkpointer (stateless)
        return workflow.compile()
