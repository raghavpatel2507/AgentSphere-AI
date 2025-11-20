from langchain_community.tools import tool
from src.Figma_MCP.figma_client import FigmaMCPClient

client = FigmaMCPClient()


@tool("figma_get_design_context")
def figma_get_design_context(url: str):
    """
    Fetch design context (frames, layers, components) from a Figma URL.
    """
    return client.call_tool("get_design_context", {"url": url})


@tool("figma_get_variable_defs")
def figma_get_variable_defs(url: str):
    """
    Fetch design system variable definitions.
    """
    return client.call_tool("get_variable_defs", {"url": url})


@tool("figma_get_code_connect_map")
def figma_get_code_connect_map(url: str):
    """
    Fetch code component mapping (Figma Code Connect).
    """
    return client.call_tool("get_code_connect_map", {"url": url})
