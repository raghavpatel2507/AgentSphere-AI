from langchain.tools import tool
from src.github_mcp_client import GitHubMCPClient
import base64
import json
import requests
import os
from dotenv import load_dotenv
load_dotenv()

# Initialize MCP client once
client = GitHubMCPClient()
OWNER = client.owner
GITHUB_MCP_TOKEN = os.getenv("GITHUB_MCP_TOKEN")

# ==========================================================
# Utility: Normalize Repo
# ==========================================================
def normalize_repo(repo: str):
    if "/" not in repo:
        return f"{OWNER}/{repo}"
    return repo


# ==========================================================
# 1. LIST REPOS (Corrected Query)
# ==========================================================
@tool("github_list_repos")
def github_list_repos(owner: str = OWNER):
    """List GitHub repositories for the authenticated user."""
    return client.call_tool(
        "search_repositories",
        {
            "query": f"user:{owner}",  # FIXED
            "sort": "updated",
            "order": "desc",
            "per_page": 50
        }
    )


# ==========================================================
# RAW FILE FETCHER (Your Logic, Retained + Cleaned)
# ==========================================================
def fetch_raw_file(owner: str, repo: str, path: str, ref: str = None):
    """Direct GitHub API raw content fetch."""

    if not GITHUB_MCP_TOKEN:
        return "Error: Missing GitHub token."

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    params = {"ref": ref} if ref else {}

    headers = {
        "Authorization": f"Bearer {GITHUB_MCP_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 404:
        return f"Error: '{path}' not found in {owner}/{repo}."

    if response.status_code >= 400:
        return f"Error {response.status_code}: {response.text}"

    data = response.json()

    # DIRECTORY LISTING
    if isinstance(data, list):
        return json.dumps({
            "type": "directory",
            "entries": [
                {
                    "name": item["name"],
                    "path": item["path"],
                    "type": item["type"],
                    "size": item.get("size", 0),
                    "url": item.get("html_url")
                }
                for item in data
            ]
        }, indent=2)

    # LARGE FILE
    if data.get("encoding") == "none":
        raw = requests.get(data.get("download_url"))
        return raw.text if raw.status_code == 200 else f"Error fetching raw."

    # NORMAL FILE
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")

    return "Error: Unsupported GitHub content type."


# ==========================================================
# 2. READ FILE (FIXED — Repo Detection Always Works)
# ==========================================================
@tool("github_read_file")
def github_read_file(repo: str, path: str = "README.md"):
    """
    Read any file from any repository:
    - First search authenticated user's repos
    - If not found, search global GitHub
    - Supports private repos + new repos (no cache issues)
    """

    repo_input = repo.lower()

    # -----------------------------------------------------
    # 1) SEARCH USER’S REAL REPOS (FIXED)
    # -----------------------------------------------------
    my_repos = client.call_tool(
        "search_repositories",
        {"query": f"user:{OWNER}", "per_page": 100}
    ).get("items", [])

    matched = None

    for r in my_repos:
        name = r["name"].lower()
        full = r["full_name"].lower()

        if repo_input in name or repo_input in full:
            matched = r["full_name"]
            break

    # USER REPO FOUND → FETCH IT
    if matched:
        owner, repo_name = matched.split("/")
        return fetch_raw_file(owner, repo_name, path)

    # -----------------------------------------------------
    # 2) GLOBAL SEARCH
    # -----------------------------------------------------
    global_repos = client.call_tool(
        "search_repositories",
        {"query": repo, "per_page": 5}
    ).get("items", [])

    if global_repos:
        matched = global_repos[0]["full_name"]
        owner, repo_name = matched.split("/")
        return fetch_raw_file(owner, repo_name, path)

    # -----------------------------------------------------
    # 3) IF STILL NOT FOUND
    # -----------------------------------------------------
    return {
        "error": True,
        "message": f"Repository '{repo}' does NOT exist (user or global)."
    }


# ==========================================================
# REST OF YOUR TOOLS (UNCHANGED)
# ==========================================================

# --- Human-in-the-loop approval state (simple in-memory, replace with persistent/session if needed) ---
_pending_approval = {}

@tool("github_write_file")
def github_write_file(repo: str, path: str, content: str, message: str, approve: bool = None):
    """Create or update a file inside a GitHub repository. If approve is not True, ask for approval first."""
    repo = normalize_repo(repo)
    key = f"write:{repo}:{path}"
    if approve is not True:
        # Store pending action for next call
        _pending_approval[key] = {"repo": repo, "path": path, "content": content, "message": message}
        return {
            "action": "awaiting_approval",
            "prompt": f"Do you approve writing to {repo}/{path}? (yes/no)",
            "repo": repo,
            "path": path,
            "content": content,
            "message": message
        }
    # On approval, perform the action
    _pending_approval.pop(key, None)
    return client.call_tool(
        "create_or_update_file",
        {"repo": repo, "path": path, "content": content, "message": message}
    )


@tool("github_delete_file")
def github_delete_file(repo: str, path: str, message: str):
    """Delete a file from a GitHub repository."""
    repo = normalize_repo(repo)
    return client.call_tool(
        "delete_file",
        {"repo": repo, "path": path, "message": message}
    )


@tool("github_create_repo")
def github_create_repo(name: str, description: str = "", private: bool = False):
    """Create a new GitHub repository."""
    return client.call_tool(
        "create_repository",
        {"name": name, "description": description, "private": private}
    )


@tool("github_create_branch")
def github_create_branch(repo: str, branch: str, from_branch: str = "main"):
    """Create a new branch."""
    repo = normalize_repo(repo)
    return client.call_tool(
        "create_branch",
        {"repo": repo, "branch": branch, "from_branch": from_branch}
    )


@tool("github_list_branches")
def github_list_branches(repo: str):
    """List all branches of a GitHub repository."""
    repo = normalize_repo(repo)
    return client.call_tool("list_branches", {"repo": repo})


@tool("github_list_tags")
def github_list_tags(repo: str):
    """List all Git tags."""
    repo = normalize_repo(repo)
    return client.call_tool("list_tags", {"repo": repo})


@tool("github_list_commits")
def github_list_commits(repo: str, per_page: int = 20):
    """List recent commits."""
    repo = normalize_repo(repo)
    return client.call_tool(
        "list_commits",
        {"repo": repo, "per_page": per_page}
    )



@tool("github_push_files")
def github_push_files(repo: str, files: list, message: str, branch: str = "main", approve: bool = None):
    """Push multiple files. If approve is not True, ask for approval first."""
    repo = normalize_repo(repo)
    key = f"push:{repo}:{branch}:{message}"
    if approve is not True:
        _pending_approval[key] = {"repo": repo, "files": files, "message": message, "branch": branch}
        return {
            "action": "awaiting_approval",
            "prompt": f"Do you approve pushing files to {repo} on branch {branch}? (yes/no)",
            "repo": repo,
            "files": files,
            "message": message,
            "branch": branch
        }
    _pending_approval.pop(key, None)
    return client.call_tool(
        "push_files",
        {"repo": repo, "files": files, "message": message, "branch": branch}
    )


@tool("github_fork_repo")
def github_fork_repo(repo: str):
    """Fork a GitHub repository."""
    repo = normalize_repo(repo)
    return client.call_tool("fork_repository", {"repo": repo})


@tool("github_search_code")
def github_search_code(query: str, repo: str = None):
    """Search code on GitHub."""
    args = {"query": query}
    if repo:
        args["repo"] = normalize_repo(repo)
    return client.call_tool("search_code", args)


@tool("github_get_commit")
def github_get_commit(repo: str, sha: str):
    """Get commit details."""
    repo = normalize_repo(repo)
    return client.call_tool("get_commit", {"repo": repo, "sha": sha})


@tool("github_list_releases")
def github_list_releases(repo: str):
    """List releases."""
    repo = normalize_repo(repo)
    return client.call_tool("list_releases", {"repo": repo})


@tool("github_get_latest_release")
def github_get_latest_release(repo: str):
    """Get latest release."""
    repo = normalize_repo(repo)
    return client.call_tool("get_latest_release", {"repo": repo})


@tool("github_get_release_by_tag")
def github_get_release_by_tag(repo: str, tag: str):
    """Get release by tag."""
    repo = normalize_repo(repo)
    return client.call_tool(
        "get_release_by_tag",
        {"repo": repo, "tag": tag}
    )


@tool("github_get_tag")
def github_get_tag(repo: str, tag: str):
    """Get tag metadata."""
    repo = normalize_repo(repo)
    return client.call_tool(
        "get_tag",
        {"repo": repo, "tag": tag}
    )
