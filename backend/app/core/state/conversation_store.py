"""
Conversation and message persistence layer.

This module provides simple CRUD operations for conversations and messages.
All functions are async and use SQLAlchemy with PostgreSQL.

Usage:
    # Create a conversation
    conversation = await create_conversation(tenant_id, user_id, thread_id, "My Chat")
    
    # Save a message
    await save_message(conversation.id, "human", "Hello!")
    
    # Load messages
    messages = await load_messages(conversation.id)
"""

from typing import Optional, List
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, update
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

# Import database session factory
from backend.app.db import AsyncSessionLocal
# Import models
from backend.app.core.state.models import Conversation, Message


# ============================================
# Conversation Operations
# ============================================

async def create_conversation(
    tenant_id: UUID,
    user_id: UUID,
    thread_id: str,
    title: Optional[str] = None
) -> Conversation:
    """
    Create a new conversation.
    
    Args:
        tenant_id: UUID of the tenant
        user_id: UUID of the user
        thread_id: Thread ID (links to LangGraph state)
        title: Optional conversation title
        
    Returns:
        Created Conversation object
    """
    async with AsyncSessionLocal() as session:
        conversation = Conversation(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            title=title or "New Conversation",
            status='ACTIVE',
            updated_at=datetime.now(timezone.utc)
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation


async def get_conversation_by_thread_id(thread_id: str) -> Optional[Conversation]:
    """
    Get a conversation by its thread_id.
    
    Args:
        thread_id: The thread ID to search for
        
    Returns:
        Conversation object if found, None otherwise
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.thread_id == thread_id)
        )
        return result.scalar_one_or_none()


async def get_or_create_conversation(
    tenant_id: UUID,
    user_id: UUID,
    thread_id: str,
    title: Optional[str] = None
) -> Conversation:
    """
    Get existing conversation or create a new one.
    
    Args:
        tenant_id: UUID of the tenant
        user_id: UUID of the user
        thread_id: Thread ID
        title: Optional conversation title (used only if creating new)
        
    Returns:
        Conversation object (existing or newly created)
    """
    # Try to get existing conversation
    conversation = await get_conversation_by_thread_id(thread_id)
    
    if conversation:
        return conversation
    
    # Create new conversation if not found
    return await create_conversation(tenant_id, user_id, thread_id, title)


async def update_conversation_title(conversation_id: UUID, title: str) -> None:
    """
    Update the title of a conversation.
    
    Args:
        conversation_id: UUID of the conversation
        title: New title
    """
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(title=title)
        )
        await session.commit()


async def archive_conversation(conversation_id: UUID) -> None:
    """
    Archive a conversation (set status to 'archived').
    
    Args:
        conversation_id: UUID of the conversation
    """
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(status='ARCHIVED')
        )
        await session.commit()


async def delete_conversation(thread_id: str) -> bool:
    """
    Permanently delete a conversation and all its messages.
    
    Args:
        thread_id: The thread ID to delete
        
    Returns:
        True if deleted, False if not found
    """
    from sqlalchemy import delete
    async with AsyncSessionLocal() as session:
        # Find the conversation first
        result = await session.execute(
            select(Conversation).where(Conversation.thread_id == thread_id)
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            return False
            
        # Delete messages first (though CASCADE should handle it, being explicit is safer)
        await session.execute(
            delete(Message).where(Message.conversation_id == conversation.id)
        )
        
        # Delete conversation
        await session.execute(
            delete(Conversation).where(Conversation.id == conversation.id)
        )
        
        await session.commit()
        return True


async def list_conversations(
    tenant_id: UUID,
    user_id: UUID,
    limit: int = 50
) -> List[Conversation]:
    """
    List all conversations for a user and tenant.
    
    Args:
        tenant_id: UUID of the tenant
        user_id: UUID of the user
        limit: Maximum number of conversations to return
        
    Returns:
        List of Conversation objects, ordered by updated_at desc
    """
    async with AsyncSessionLocal() as session:
        query = (
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        result = await session.execute(query)
        return list(result.scalars().all())


# ============================================
# Message Operations
# ============================================

async def save_message(
    conversation_id: UUID,
    role: str,
    content: str,
    metadata: Optional[dict] = None
) -> Message:
    """
    Save a single message to the database.
    
    Args:
        conversation_id: UUID of the conversation
        role: Message role ('human', 'ai', or 'system')
        content: Message content
        metadata: Optional metadata dict
        
    Returns:
        Created Message object
    """
    async with AsyncSessionLocal() as session:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata or {},
            updated_at=datetime.now(timezone.utc)
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message


async def load_messages(
    conversation_id: UUID,
    limit: Optional[int] = None
) -> List[Message]:
    """
    Load messages for a conversation.
    
    Args:
        conversation_id: UUID of the conversation
        limit: Optional limit on number of messages to load
        
    Returns:
        List of Message objects, ordered by creation time
    """
    async with AsyncSessionLocal() as session:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        
        if limit:
            query = query.limit(limit)
        
        result = await session.execute(query)
        return list(result.scalars().all())


async def messages_to_langchain(messages: List[Message]) -> List[BaseMessage]:
    """
    Convert database Message objects to LangChain BaseMessage objects.
    
    Args:
        messages: List of database Message objects
        
    Returns:
        List of LangChain message objects (HumanMessage, AIMessage, SystemMessage)
    """
    langchain_messages = []
    
    for msg in messages:
        if msg.role == 'USER':
            langchain_messages.append(HumanMessage(content=msg.content))
        elif msg.role == 'ASSISTANT':
            langchain_messages.append(AIMessage(content=msg.content))
        elif msg.role == 'SYSTEM':
            langchain_messages.append(SystemMessage(content=msg.content))
    
    return langchain_messages


async def save_langchain_messages(
    conversation_id: UUID,
    messages: List[BaseMessage]
) -> None:
    """
    Save a list of LangChain messages to the database.
    
    This is a convenience function that converts LangChain messages
    to database format and saves them.
    
    Args:
        conversation_id: UUID of the conversation
        messages: List of LangChain BaseMessage objects
    """
    for msg in messages:
        # Determine role from message type
        if isinstance(msg, HumanMessage):
            role = 'USER'
        elif isinstance(msg, AIMessage):
            role = 'ASSISTANT'
        elif isinstance(msg, SystemMessage):
            role = 'SYSTEM'
        else:
            role = 'SYSTEM'  # Default fallback
        
        # Save to database
        await save_message(conversation_id, role, msg.content)


