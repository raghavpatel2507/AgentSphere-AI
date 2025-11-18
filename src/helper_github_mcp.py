from langchain.tools import tool
from src.github_mcp_client import GitHubMCPClient

client = GitHubMCPClient()

OWNER = client.owner
def resolve_repo_name(input_name: str):
    """Resolve correct repo casing from user's repo list."""
    repos = client.call_tool(
        "search_repositories",
        {
            "query": f"{OWNER} in:name",
            "sort": "updated",
            "order": "desc",
            "per_page": 20
        }
    )
    

    if "items" not in repos:
        return input_name

    repo_map = {r["name"].lower(): r["name"] for r in repos["items"]}
    return repo_map.get(input_name.lower(), input_name)