"""
Thread and session management utilities.

This module provides simple utilities for managing conversation threads
and saving/loading message history from the database.

SIMPLIFIED VERSION - Easy to understand!
"""

import uuid
from uuid import UUID
import json
import logging
from pathlib import Path
from typing import Optional, List, Any
from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)
from backend.app.core.state.conversation_store import (
    get_or_create_conversation,
    load_messages,
    messages_to_langchain,
    save_message
)


# ============================================
# Thread ID Management
# ============================================

def create_thread_id(tenant_id: str, conversation_id: Optional[str] = None) -> str:
    """
    Create a tenant-scoped thread ID.
    
    Format: tenant_{tenant_id}_thread_{conversation_id}
    
    Args:
        tenant_id: The tenant identifier
        conversation_id: Optional conversation identifier
        
    Returns:
        Thread ID string
        
    Example:
        >>> create_thread_id("default", "abc123")
        'tenant_default_thread_abc123'
    """
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())[:8]
    
    return f"tenant_{tenant_id}_thread_{conversation_id}"


def parse_thread_id(thread_id: str) -> tuple[str, str]:
    """
    Parse a thread ID to extract tenant_id and conversation_id.
    
    Args:
        thread_id: The thread ID to parse
        
    Returns:
        Tuple of (tenant_id, conversation_id)
        
    Example:
        >>> parse_thread_id("tenant_default_thread_abc123")
        ('default', 'abc123')
    """
    if not thread_id.startswith("tenant_"):
        raise ValueError(f"Invalid thread_id format: {thread_id}")
    
    parts = thread_id.split("_thread_")
    if len(parts) != 2:
        raise ValueError(f"Invalid thread_id format: {thread_id}")
    
    tenant_id = parts[0].replace("tenant_", "")
    conversation_id = parts[1]
    
    return tenant_id, conversation_id


# ============================================
# Session File Management (for CLI)
# ============================================

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
        "thread_id": str(thread_id),
        "tenant_id": str(tenant_id),
    }
    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)


def load_current_session() -> Optional[dict]:
    """
    Load current session from file.
    
    Returns:
        Dict with thread_id and tenant_id, or None if no session found
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
        Tuple of (thread_id, is_new_session)
    """
    # Try to load existing session
    session = load_current_session()
    
    if session and session.get("tenant_id") == tenant_id:
        # Resume existing session
        thread_id = session["thread_id"]
        return thread_id, False
    
    # Create new session
    conversation_id = str(uuid.uuid4())[:8]
    thread_id = create_thread_id(tenant_id, conversation_id)
    save_current_session(thread_id, tenant_id)
    return thread_id, True


# ============================================
# Message History (Database)
# ============================================

async def load_history(
    thread_id: str,
    tenant_id: Any,
    user_id: Any
) -> List[BaseMessage]:
    """
    Load conversation history from database.
    """
    try:
        # Defensive conversion: Ensure we have UUID objects for DB query
        tenant_uuid = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
        user_uuid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
        
        # Get or create conversation
        conversation = await get_or_create_conversation(
            tenant_uuid,
            user_uuid,
            thread_id
        )
        
        # Load messages from database
        db_messages = await load_messages(conversation.id)
        
        # Convert to LangChain format
        langchain_messages = await messages_to_langchain(db_messages)
        
        return langchain_messages
        
    except Exception as e:
        logger.error(f"⚠️ Error loading history for {thread_id}: {e}")
        return []


async def save_history(
    thread_id: str,
    tenant_id: Any,
    user_id: Any,
    history: List[BaseMessage]
):
    """
    Save conversation history to database.
    """
    try:
        # Defensive conversion: Ensure we have UUID objects for DB query
        tenant_uuid = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
        user_uuid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
        
        # Get or create conversation
        conversation = await get_or_create_conversation(
            tenant_uuid,
            user_uuid,
            thread_id
        )
        
        # Load existing messages to find what's new
        db_messages = await load_messages(conversation.id)
        existing_count = len(db_messages)
        
        # Save only NEW messages (those beyond existing count)
        new_messages = history[existing_count:]
        
        for msg in new_messages:
            # Determine role
            role = 'USER' if msg.type == 'human' else 'ASSISTANT'
            
            # Save to database
            await save_message(conversation.id, role, msg.content)
        
        if new_messages:
            logger.info(f"✅ Saved {len(new_messages)} new message(s) to database")
            
            # Auto-name conversation if it's still "New Conversation"
            if conversation.title == "New Conversation" or not conversation.title:
                # Find the first human message in the entire history
                first_user_msg = next((m for m in history if m.type == 'human'), None)
                if first_user_msg:
                    new_title = first_user_msg.content[:50]
                    if len(first_user_msg.content) > 50:
                        new_title += "..."
                    
                    from src.core.state.conversation_store import update_conversation_title
                    await update_conversation_title(conversation.id, new_title)
                    print(f"📝 Updated conversation title to: {new_title}")
            
    except Exception as e:
        logger.error(f"⚠️ Error saving history for {thread_id}: {e}")

