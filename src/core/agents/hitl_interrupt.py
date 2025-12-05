"""
Human-In-The-Loop Interrupt Module with Selective Approval

This module provides conditional LangGraph interrupt functionality for tool approval.
Only sensitive/dangerous tools require approval based on configuration.
"""

from langgraph.types import interrupt
from typing import Dict, Any, Optional
import fnmatch


def load_hitl_config() -> Dict[str, Any]:
    """Load HITL configuration from mcp_config.json"""
    try:
        from src.core.mcp.manager import MCPManager
        manager = MCPManager()
        config = manager.load_config()
        return config.get("hitl_config", {})
    except Exception:
        # Fallback to default config if loading fails
        return {}


def get_default_config() -> Dict[str, Any]:
    """Get default HITL configuration"""
    return {
        "enabled": True,
        "mode": "denylist",
        "sensitive_tools": [
            "browser_navigate",
            "browser_click",
            "browser_fill",
            "browser_type",
            "create_*",
            "delete_*",
            "write_*",
            "execute_*",
            "send_*",
            "post_*",
            "upload_*",
            "run_*",
            "python_executor"
        ],
        "safe_tools": [
            "search_*",
            "read_*",
            "list_*",
            "get_*",
            "fetch_*",
            "calculate_*"
        ]
    }


def requires_approval(tool_name: str) -> bool:
    """
    Check if tool requires HITL approval based on configuration.
    
    Args:
        tool_name: Name of the tool to check
        
    Returns:
        True if tool requires approval, False otherwise
    """
    config = load_hitl_config()
    
    # Merge with defaults
    default_config = get_default_config()
    enabled = config.get("enabled", default_config["enabled"])
    mode = config.get("mode", default_config["mode"])
    sensitive_tools = config.get("sensitive_tools", default_config["sensitive_tools"])
    safe_tools = config.get("safe_tools", default_config["safe_tools"])
    
    if not enabled:
        return False
    
    if mode == "none":
        return False
    elif mode == "all":
        return True
    elif mode == "denylist":
        # Interrupt if tool matches sensitive pattern
        return any(fnmatch.fnmatch(tool_name, pattern) for pattern in sensitive_tools)
    elif mode == "allowlist":
        # Interrupt if tool does NOT match safe pattern
        return not any(fnmatch.fnmatch(tool_name, pattern) for pattern in safe_tools)
    
    # Default: require approval
    return True


def request_tool_approval(tool_name: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Conditionally trigger a LangGraph interrupt to request human approval.
    
    Only triggers interrupt if the tool is marked as sensitive in configuration.
    Safe tools execute automatically without approval.
    
    Args:
        tool_name: Name of the tool to be executed
        tool_args: Arguments to be passed to the tool
        
    Returns:
        Interrupt event dictionary if approval required, None otherwise
    """
    if requires_approval(tool_name):
        return interrupt({
            "event": "tool_approval_required",
            "tool_name": tool_name,
            "tool_args": tool_args,
        })
    
    # Tool is safe, no approval needed
    return None
