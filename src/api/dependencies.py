from functools import lru_cache
from src.core.mcp.manager import MCPManager
from src.core.agents.planner import Planner
from src.core.llm.provider import LLMFactory
import os

@lru_cache()
def get_mcp_manager() -> MCPManager:
    manager = MCPManager()
    return manager

@lru_cache()
def get_planner() -> Planner:
    return Planner(api_key=os.getenv("OPENROUTER_API_KEY"))

def get_llm():
    return LLMFactory.load_config_and_create_llm()
