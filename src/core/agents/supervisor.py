from langgraph_supervisor import create_supervisor
from langchain_core.messages import trim_messages
from src.core.agents.model import model, MAX_TOKENS
from src.core.agents.system_prompt import system_prompt_supervisor
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
    """Generate supervisor prompt with only enabled agents listed"""
    
    # Base prompt
    base_prompt = (
        "You are the Supervisor Agent. You orchestrate complex workflows by intelligently routing tasks across multiple specialized agents and delivering the FINAL, USER-READY response."
        "\n\n"
        "   AVAILABLE AGENTS:\n"
        "   - websearch_agent: Internet searches, latest information\n"
        "   - math_agent: Mathematical calculations\n"
        "   - python_agent: Python code execution, data processing\n"
    )
    
    # Add dynamic experts to prompt
    manager = MCPManager()
    config = manager.load_config()
    
    for server in config.get("mcp_servers", []):
        if server.get("enabled", False):
            name = server.get("name")
            role = server.get("expert_role", f"{name} specialist")
            base_prompt += f"   - {name}_expert: {role}\n"
    
    # Add routing guidance
    base_prompt += (
        "\n\n"
        "   ROUTING GUIDELINES:\n"
        "   - General web searches (not YouTube-specific) → websearch_agent\n"
        "   - Code execution → python_agent\n"
        "   - Math calculations → math_agent\n"
    )
    
    # Add dynamic routing guidelines
    for server in config.get("mcp_servers", []):
        if server.get("enabled", False):
            name = server.get("name")
            base_prompt += f"   - {name} related tasks → {name}_expert\n"
    
    # Add core principles from original prompt
    # We'll just append the standard principles
    base_prompt += (
        "\n\n"
        "   CORE PRINCIPLE - WORKFLOW CHAINING:\n"
        "   When a user request contains multiple actions connected by 'and', 'then', or implies a sequence:\n"
        "\n"
        "   1. PARSE the request into discrete steps\n"
        "   2. ROUTE each step to the correct agent\n"
        "   3. CAPTURE the output of each step\n"
        "   4. AUTOMATICALLY continue until all steps are complete\n"
        "   5. COMPOSE a final response for the user\n"
        "\n\n"
        "   ============================\n"
        "   CRITICAL RESPONSE PRINCIPLE\n"
        "   ============================\n"
        "\n"
        "   You are responsible for the FINAL user experience.\n"
        "\n"
        "   Your response must reflect the actual outcome of the workflow, not the process used to achieve it.\n"
        "\n"
        "   Always:\n"
        "   - Present the end result clearly and completely\n"
        "   - Communicate outcomes, content, or answers directly to the user\n"
        "   - Speak as the primary responder, not as a coordinator or system narrator\n"
        "\n"
        "   Never:\n"
        "   - Describe internal routing, transfers, or tool operations\n"
        "   - Respond with status-only confirmations\n"
        "   - Refer to agents, systems, or workflow mechanics\n"
        "   - Indicate that work was 'handed back' or 'delegated'\n"
        "\n\n"
        "   You are not a messenger between tools.\n"
        "   You are the final intelligence presenting the solution.\n"
    )
    
    return base_prompt


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
        # Build dynamic interrupt list based on enabled agents
        interrupt_list = ["websearch_expert", "math_expert", "python_expert"]
        
        # Add dynamic experts to interrupt list
        if dynamic_experts:
            interrupt_list.extend(dynamic_experts.keys())
        
        # Compile with checkpointer and interrupt before agent execution
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=interrupt_list  # Pause before agent calls for approval
        )
    else:
        # Compile without checkpointer (stateless)
        return workflow.compile()
