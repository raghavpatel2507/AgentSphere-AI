from langgraph_supervisor import create_supervisor
from src.model import model
from src.agent import *
from src.system_prompt import *

workflow = create_supervisor(
    agents=[websearch_agent, math_agent, python_agent, github_agent, gmail_agent, zoho_agent],
    model=model,
    prompt=system_prompt_supervisor
)


app = workflow.compile()

