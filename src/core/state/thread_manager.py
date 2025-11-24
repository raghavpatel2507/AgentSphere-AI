"""
Thread and session management utilities for multi-tenant conversations.

This module provides utilities for creating tenant-scoped thread IDs
and managing conversation sessions.
"""

import uuid
from typing import Optional


def create_thread_id(tenant_id: str, conversation_id: Optional[str] = None) -> str:
    """
    Create a tenant-scoped thread ID for LangGraph checkpointer.
    
    Format: tenant_{tenant_id}_thread_{conversation_id}
    
    Args:
        tenant_id: The tenant identifier (UUID or string)
        conversation_id: Optional conversation identifier. If not provided,
                        a new UUID will be generated.
    
    Returns:
        str: The tenant-scoped thread ID
        
    Examples:
        >>> create_thread_id("550e8400-e29b-41d4-a716-446655440000", "conv_123")
        'tenant_550e8400-e29b-41d4-a716-446655440000_thread_conv_123'
        
        >>> create_thread_id("default")
        'tenant_default_thread_a1b2c3d4-...'
    """
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())
    
    return f"tenant_{tenant_id}_thread_{conversation_id}"


def parse_thread_id(thread_id: str) -> tuple[str, str]:
    """
    Parse a thread ID to extract tenant_id and conversation_id.
    
    Args:
        thread_id: The thread ID to parse
        
    Returns:
        tuple[str, str]: (tenant_id, conversation_id)
        
    Raises:
        ValueError: If thread_id format is invalid
        
    Examples:
        >>> parse_thread_id("tenant_default_thread_conv_123")
        ('default', 'conv_123')
    """
    if not thread_id.startswith("tenant_"):
        raise ValueError(f"Invalid thread_id format: {thread_id}")
    
    parts = thread_id.split("_thread_")
    if len(parts) != 2:
        raise ValueError(f"Invalid thread_id format: {thread_id}")
    
    tenant_id = parts[0].replace("tenant_", "")
    conversation_id = parts[1]
    
    return tenant_id, conversation_id


def get_config_for_thread(thread_id: str) -> dict:
    """
    Get LangGraph config dict for a given thread ID.
    
    Args:
        thread_id: The thread ID
        
    Returns:
        dict: Config dict with thread_id in configurable section
        
    Example:
        >>> get_config_for_thread("tenant_default_thread_conv_123")
        {'configurable': {'thread_id': 'tenant_default_thread_conv_123'}}
    """
    return {"configurable": {"thread_id": thread_id}}


class SessionManager:
    """
    Manages conversation sessions for multi-tenant support.
    
    Provides utilities for creating, tracking, and managing
    conversation sessions with tenant isolation.
    """
    
    def __init__(self, tenant_id: str):
        """
        Initialize session manager for a specific tenant.
        
        Args:
            tenant_id: The tenant identifier
        """
        self.tenant_id = tenant_id
        self.active_sessions: dict[str, dict] = {}
    
    def create_session(self, conversation_id: Optional[str] = None) -> str:
        """
        Create a new conversation session.
        
        Args:
            conversation_id: Optional conversation ID. If not provided,
                           a new UUID will be generated.
        
        Returns:
            str: The thread ID for the new session
        """
        thread_id = create_thread_id(self.tenant_id, conversation_id)
        
        self.active_sessions[thread_id] = {
            "thread_id": thread_id,
            "tenant_id": self.tenant_id,
            "conversation_id": conversation_id or thread_id.split("_thread_")[1],
            "created_at": None,  # Will be set when first message is sent
            "last_activity": None,
        }
        
        return thread_id
    
    def get_session(self, thread_id: str) -> Optional[dict]:
        """
        Get session information.
        
        Args:
            thread_id: The thread ID
            
        Returns:
            dict: Session information or None if not found
        """
        return self.active_sessions.get(thread_id)
    
    def end_session(self, thread_id: str):
        """
        End a conversation session.
        
        Args:
            thread_id: The thread ID to end
        """
        if thread_id in self.active_sessions:
            del self.active_sessions[thread_id]
    
    def list_sessions(self) -> list[dict]:
        """
        List all active sessions for this tenant.
        
        Returns:
            list[dict]: List of session information dicts
        """
        return list(self.active_sessions.values())


# ============================================
# Session File Management for CLI
# ============================================

import json
from pathlib import Path
from typing import Optional


def get_session_file_path() -> Path:
    """Get path to session file for storing current active thread."""
    session_dir = Path.home() / ".agentsphere"
    session_dir.mkdir(exist_ok=True)
    return session_dir / "current_session.json"


def save_current_session(thread_id: str, tenant_id: str):
    """
    Save current session to file.
    
    Args:
        thread_id: The thread ID to save
        tenant_id: The tenant ID
    """
    session_file = get_session_file_path()
    session_data = {
        "thread_id": thread_id,
        "tenant_id": tenant_id,
        "last_active": None,  # Could add timestamp if needed
    }
    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)


def load_current_session() -> Optional[dict]:
    """
    Load current session from file.
    
    Returns:
        dict with thread_id and tenant_id, or None if no session found
    """
    session_file = get_session_file_path()
    if not session_file.exists():
        return None
    
    try:
        with open(session_file, "r") as f:
            return json.load(f)
    except Exception:
        return None


def clear_current_session():
    """Clear the current session file."""
    session_file = get_session_file_path()
    if session_file.exists():
        session_file.unlink()


def get_or_create_session(tenant_id: str) -> tuple[str, bool]:
    """
    Get existing session or create new one.
    
    Args:
        tenant_id: The tenant ID
        
    Returns:
        tuple of (thread_id, is_new_session)
    """
    # Try to load existing session
    session = load_current_session()
    
    if session and session.get("tenant_id") == tenant_id:
        # Resume existing session
        thread_id = session["thread_id"]
        return thread_id, False
    
    # Create new session
    import uuid
    conversation_id = str(uuid.uuid4())[:8]
    thread_id = create_thread_id(tenant_id, conversation_id)
    save_current_session(thread_id, tenant_id)
    return thread_id, True
