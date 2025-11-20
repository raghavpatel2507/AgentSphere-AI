from langgraph_supervisor import create_supervisor
from src.core.agents.model import model
from src.core.agents.system_prompt import system_prompt_supervisor
from src.core.agents.agent import (
    math_agent,
    websearch_agent,
    python_agent,
    github_agent,
    gmail_agent,
    zoho_agent
)

workflow = create_supervisor(
    agents=[websearch_agent, math_agent, python_agent, github_agent, gmail_agent, zoho_agent],
    model=model,
    prompt=system_prompt_supervisor
)

app = workflow.compile()

