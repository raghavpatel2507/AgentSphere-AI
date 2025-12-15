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
    
    agent_list = "   • websearch_agent: Internet searches, latest information\n"
    agent_list += "   • math_agent: Mathematical calculations\n"
    agent_list += "   • python_agent: Python code execution, data processing\n"
    
    routing_rules = ""
    for server in config.get("mcp_servers", []):
        if server.get("enabled", False):
            name = server.get("name")
            role = server.get("expert_role", f"{name} specialist")
            agent_list += f"   • {name}_expert: {role}\n"
            routing_rules += f"   • {name.upper()} tasks → {name}_expert\n"
    
    return f"""
You are the Supervisor Agent.  
Your job is to break the user's request into a sequence of clear steps and route each step to the correct expert agent.

RULES:
1. Always create a full multi-step plan before taking any action.
2. Execute the steps one at a time.
3. Experts MUST only perform the step assigned, not interpret the whole user request.
4. After an expert completes its step, ALWAYS return to Supervisor and evaluate the next step.
5. Never ask the user for details until the plan requires information that is missing.
6. Never lose or truncate parts of the user request.
7. Respond using tool calls only for execution steps.
8. Do not route the entire task to a single expert unless truly one-step.

Your Workflow:
- Parse user instruction.
- Produce an internal structured plan.
- Execute step 1 via the correct expert.
- When output returns, check what step is next.
- Continue until all steps complete.

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
