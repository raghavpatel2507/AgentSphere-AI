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


# Create supervisor workflow with message trimming
workflow = create_supervisor(
    agents=[websearch_agent, math_agent, python_agent, github_agent, gmail_agent, zoho_agent],
    model=model,
    prompt=system_prompt_supervisor,
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
        # Compile with checkpointer and interrupt before agent execution
        return workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=[
                "websearch_expert",
                "math_expert",
                "python_expert",
                "github_expert",
                "gmail_expert",
                "zoho_expert"
            ],  # Pause before agent calls for approval
        )
    else:
        # Compile without checkpointer (stateless)
        return workflow.compile()


# Default app without checkpointer (for backward compatibility)
app = workflow.compile()
