from langgraph_supervisor import create_supervisor
from langchain.agents import create_agent
from src.core.agents.model import model
from src.core.tools.custom_tools import *
from src.core.agents.system_prompt import *
from src.Figma_MCP.figma_tools import *


import asyncio
from src.core.tools import load_mcp_tools_sync
from src.mcp_clients.gmail import GmailMCPClient
from src.mcp_clients.zoho import ZohoMCPClient
from src.mcp_clients.github import GithubMCPClient
from src.mcp_clients.Filesystem.client import FilesystemMCPClient


# Initialize MCP tools dynamically (Synchronous)
def init_mcp_tools():
    gmail_client = GmailMCPClient()
    try:
       
        gmail_tools = load_mcp_tools_sync(gmail_client)
    except Exception as e:
        print(f"Error loading Gmail MCP tools: {e}")
        gmail_tools = []
        
    return gmail_tools

def init_zoho_tools():
    zoho_client = ZohoMCPClient()
    try:
        zoho_tools = load_mcp_tools_sync(zoho_client)
    except Exception as e:
        print(f"Error loading Zoho MCP tools: {e}")
        zoho_tools = []
    return zoho_tools

def init_github_tools():
    github_client = GithubMCPClient()
    try:
        github_tools = load_mcp_tools_sync(github_client)
    except Exception as e:
        print(f"Error loading GitHub MCP tools: {e}")
        github_tools = []
    return github_tools

def init_filesystem_tools():
    fs_client = FilesystemMCPClient()
    try:
        fs_tools = load_mcp_tools_sync(fs_client)
    except Exception as e:
        print(f"Error loading Filesystem MCP tools: {e}")
        fs_tools = []
    return fs_tools


# Load tools synchronously for module-level definition
try:
    gmail_tools = init_mcp_tools()
    zoho_tools = init_zoho_tools()
    github_tools = init_github_tools()
    filesystem_tools = init_filesystem_tools()
    
except Exception as e:
    print(f"Warning: Error initializing MCP tools: {e}")
    gmail_tools = []
    zoho_tools = []
    github_tools = []
    filesystem_tools = []
    whatsapp_tools = []


#------------------------------This agent used for The mathmatical calculation------------------------------#
math_agent = create_agent(
    model=model,
    tools=[calculate_expression],
    name="math_expert",
    system_prompt=system_prompt_mathagent
)

#------------------------------This agent used for The web search------------------------------#
websearch_agent = create_agent(
    model=model,
    tools=[search_duckduckgo],
    name="websearch_expert",
    system_prompt=system_prompt_websearch
)

#------------------------------This agent used for The python code execution------------------------------#
python_agent = create_agent(
    model=model,
    tools=[python_executor],
    name="python_expert",
    system_prompt=system_prompt_python
)

#------------------------------This agent used for The GitHub MCP operations------------------------------#
github_agent = create_agent(
    model=model,
    tools=github_tools, # Dynamically loaded tools
    name="github_expert",
    system_prompt=system_prompt_github_mcp
)

#------------------------------This agent used for Gmail MCP operations------------------------------#
gmail_agent = create_agent(
    model=model,
    tools=gmail_tools, # Dynamically loaded tools
    name="gmail_expert",
    system_prompt=system_prompt_gmail_mcp
)


# figma_agent = create_agent(
#     model=model,
#     tools=[
#         figma_get_design_context,
#         figma_get_variable_defs,
#         figma_get_code_connect_map
#     ],
#     name="figma_expert",
#     system_prompt=system_prompt_figma_mcp

# )#------------------------------This agent used for Zoho Books MCP operations------------------------------#
zoho_agent = create_agent(
    model=model,
    tools=zoho_tools, # Dynamically loaded tools
    name="zoho_expert",
    system_prompt=system_prompt_zoho_mcp
)



#------------------------------This agent used for Filesystem MCP operations------------------------------#
filesystem_agent = create_agent(
    model=model,
    tools=filesystem_tools, # Dynamically loaded tools
    name="filesystem_expert",
    system_prompt=system_prompt_filesystem_mcp
)

#------------------------------This agent used for WhatsApp MCP operations------------------------------#
