from langgraph_supervisor import create_supervisor
from src.core.agents.model import model
from src.core.agents.system_prompt import system_prompt_supervisor
from src.core.agents.agent import *

# Create supervisor workflow
workflow = create_supervisor(
    agents=[websearch_agent, math_agent, python_agent, github_agent, gmail_agent, zoho_agent,filesystem_agent],
    model=model,
    prompt=system_prompt_supervisor
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
                "zoho_expert",
                "filesystem_expert"
            ],  # Pause before agent calls for approval
        )
    else:
        # Compile without checkpointer (stateless)
        return workflow.compile()


# Default app without checkpointer (for backward compatibility)
app = workflow.compile()
