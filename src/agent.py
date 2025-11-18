from langgraph_supervisor import create_supervisor
from langchain.agents import create_agent
from src.model import model
from src.tool import *
from src.system_prompt import *
from src.github_tools import *

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
    tools=[
        github_list_repos,
        github_read_file,
        github_write_file,
        github_delete_file,
        github_create_repo,
        github_create_branch,
        github_list_branches,
        github_list_tags,
        github_list_commits,
        github_push_files,
        github_fork_repo,
        github_search_code,
        github_get_commit,
        github_list_releases,
        github_get_latest_release,
        github_get_release_by_tag,
        github_get_tag,
    ],
    name="github_expert",
    system_prompt=system_prompt_github_mcp
)