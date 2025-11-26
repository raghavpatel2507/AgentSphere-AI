from langgraph_supervisor import create_supervisor
from langchain_core.messages import trim_messages
from src.core.agents.model import model, MAX_TOKENS
from src.core.agents.system_prompt import system_prompt_supervisor
from src.core.agents.agent import *


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
    
    # Add MCP agents only if enabled
    if enabled_mcp_agents.get("github", False):
        agents.append(github_agent)
    if enabled_mcp_agents.get("gmail", False):
        agents.append(gmail_agent)
    if enabled_mcp_agents.get("zoho", False):
        agents.append(zoho_agent)
    if enabled_mcp_agents.get("filesystem", False):
        agents.append(filesystem_agent)
    if enabled_mcp_agents.get("discord", False):
        agents.append(discord_agent)
    if enabled_mcp_agents.get("youtube", False):
        agents.append(youtube_agent)
    
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
    
    # Add MCP agents only if enabled
    if enabled_mcp_agents.get("github", False):
        base_prompt += "   - github_expert: GitHub operations (repos, files, commits, branches)\n"
    if enabled_mcp_agents.get("gmail", False):
        base_prompt += "   - gmail_expert: Email operations (send, read, search, drafts, labels)\n"
    if enabled_mcp_agents.get("zoho", False):
        base_prompt += "   - zoho_expert: Zoho Books (invoices, expenses, contacts, items)\n"
    if enabled_mcp_agents.get("filesystem", False):
        base_prompt += "   - filesystem_agent: File system operations (read, write, list, move, delete files/directories)\n"
    if enabled_mcp_agents.get("discord", False):
        base_prompt += "   - discord_expert: Discord operations (servers, channels, messages)\n"
    if enabled_mcp_agents.get("youtube", False):
        base_prompt += "   - youtube_expert: YouTube operations (search videos, get info, comments, summarization, flashcards, quizzes)\n"
    
    # Add routing guidance
    base_prompt += (
        "\n\n"
        "   ROUTING GUIDELINES:\n"
        "   - YouTube queries (search videos, get video info, YouTube URLs, video summaries, flashcards, quizzes) → youtube_expert\n"
        "   - General web searches (not YouTube-specific) → websearch_agent\n"
        "   - Email operations → gmail_expert\n"
        "   - File operations → filesystem_agent\n"
        "   - Code execution → python_agent\n"
        "   - Math calculations → math_agent\n"
    )
    
    # Add the rest of the system prompt (workflow principles, etc.)
    base_prompt += system_prompt_supervisor.split("AVAILABLE AGENTS:")[1].split("   CORE PRINCIPLE")[1] if "CORE PRINCIPLE" in system_prompt_supervisor else ""
    
    # Add core principles from original prompt
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
active_agents = get_active_agents()
dynamic_prompt = get_dynamic_supervisor_prompt()

workflow = create_supervisor(
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
    if checkpointer is not None:
        # Build dynamic interrupt list based on enabled agents
        interrupt_list = ["websearch_expert", "math_expert", "python_expert"]
        
        if enabled_mcp_agents.get("github", False):
            interrupt_list.append("github_expert")
        if enabled_mcp_agents.get("gmail", False):
            interrupt_list.append("gmail_expert")
        if enabled_mcp_agents.get("zoho", False):
            interrupt_list.append("zoho_expert")
        if enabled_mcp_agents.get("filesystem", False):
            interrupt_list.append("filesystem_expert")
        if enabled_mcp_agents.get("discord", False):
            interrupt_list.append("discord_expert")
        if enabled_mcp_agents.get("youtube", False):
            interrupt_list.append("youtube_expert")
        
        # Compile with checkpointer and interrupt before agent execution
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=interrupt_list  # Pause before agent calls for approval
        )
    else:
        # Compile without checkpointer (stateless)
        return workflow.compile()


# Default app without checkpointer (for backward compatibility)
app = workflow.compile()
