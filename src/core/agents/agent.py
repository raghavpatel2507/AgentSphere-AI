from langgraph_supervisor import create_supervisor
from langchain.agents import create_agent
from src.core.agents.model import model
from src.core.tools.custom_tools import *
from src.core.agents.expert_factory import ExpertFactory
from src.core.mcp.manager import MCPManager
import asyncio
import os

# Initialize MCP Manager
mcp_manager = MCPManager()

def load_prompt(filename):
    """Load system prompt from text file."""
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", filename)
    try:
        with open(prompt_path, "r") as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error loading prompt {filename}: {e}")
        return ""

#------------------------------Core Agents (Always Available)------------------------------#

# Math Agent
math_agent = create_agent(
    model=model,
    tools=[calculate_expression],
    name="math_expert",
    system_prompt=load_prompt("math_agent.txt")
)

# Web Search Agent
websearch_agent = create_agent(
    model=model,
    tools=[search_duckduckgo],
    name="websearch_expert",
    system_prompt=load_prompt("websearch_agent.txt")
)

# Python Agent
python_agent = create_agent(
    model=model,
    tools=[python_executor],
    name="python_expert",
    system_prompt=load_prompt("python_agent.txt")
)

#------------------------------Dynamic MCP Agents------------------------------#

async def get_dynamic_agents():
    """
    Initialize and return all dynamic agents from MCP configuration.
    This needs to be async because it awaits MCP initialization.
    """
    # Ensure MCP manager is initialized
    await mcp_manager.initialize()
    
    # Create experts using factory
    experts = await ExpertFactory.create_all_experts(model)
    
    return experts

# Global variable to store initialized experts
# This will be populated by main.py calling get_dynamic_agents()
dynamic_experts = {}

