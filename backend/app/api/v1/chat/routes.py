"""
Chat routes.
Handles creating chats, sending messages, and streaming responses.
"""

import uuid
import json
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.api.v1.chat.schemas import (
    NewChatRequest,
    SendMessageRequest,
    ChatResponse,
    ChatStatusResponse,
    MessageResponse,
)


router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/new", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_new_chat(
    request: NewChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new chat conversation.
    
    Returns the new conversation with a unique thread_id.
    """
    thread_id = f"thread_{uuid.uuid4().hex[:12]}"
    
    # Use user's tenant_id or a default
    tenant_id = current_user.tenant_id or current_user.id
    
    conversation = Conversation(
        tenant_id=tenant_id,
        user_id=current_user.id,
        thread_id=thread_id,
        title=request.title or "New Conversation",
        status='ACTIVE',
    )
    
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    
    # If initial message provided, save it
    if request.initial_message:
        message = Message(
            conversation_id=conversation.id,
            role='USER',
            content=request.initial_message,
        )
        db.add(message)
        await db.commit()
    
    return ChatResponse(
        thread_id=conversation.thread_id,
        conversation_id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
    )


@router.post("/{thread_id}/message")
async def send_message(
    thread_id: str,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message and get streaming response.
    
    Returns Server-Sent Events stream with agent responses.
    """
    # Find conversation
    result = await db.execute(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.user_id == current_user.id,
            Conversation.is_deleted == False
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Save user message (skip if resuming to avoid duplicates)
    if not request.is_resume:
        user_message = Message(
            conversation_id=conversation.id,
            role='USER',
            content=request.content,
        )
        db.add(user_message)
        await db.commit()
    
    # Update conversation title if first message
    if conversation.title == "New Conversation":
        # Use first 50 chars of message as title
        conversation.title = request.content[:50] + ("..." if len(request.content) > 50 else "")
        await db.commit()
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate SSE stream from agent execution."""
        try:
            # Import at runtime to avoid circular imports
            from backend.app.services.chat_service import ChatService
            
            chat_service = ChatService(current_user.id, db)
            
            async for event in chat_service.process_message(
                conversation=conversation,
                user_input=request.content,
                hitl_request_id=request.hitl_request_id,
            ):
                # Format as SSE
                yield f"data: {json.dumps(event)}\n\n"
            
            # Send done event
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            error_event = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/{thread_id}/status", response_model=ChatStatusResponse)
async def get_chat_status(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current status of a chat.
    
    Useful for checking if agent is still processing or if there's a pending HITL approval.
    """
    # Find conversation
    result = await db.execute(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.user_id == current_user.id,
            Conversation.is_deleted == False
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Check for pending HITL requests
    from backend.app.models.hitl_request import HITLRequest
    hitl_result = await db.execute(
        select(HITLRequest).where(
            HITLRequest.conversation_id == conversation.id,
            HITLRequest.status == 'PENDING'
        )
    )
    pending_hitl = hitl_result.scalar_one_or_none()
    
    return ChatStatusResponse(
        thread_id=thread_id,
        is_processing=conversation.status == 'PENDING_APPROVAL',
        pending_approval=pending_hitl.id if pending_hitl else None,
        last_activity=conversation.updated_at,
    )


@router.get("/{thread_id}/messages", response_model=list[MessageResponse])
async def get_chat_messages(
    thread_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get messages for a chat conversation.
    """
    # Find conversation
    result = await db.execute(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.user_id == current_user.id,
            Conversation.is_deleted == False
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Get messages
    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    messages = messages_result.scalars().all()
    
    return [
        MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            metadata=msg.extra_metadata or {},
            created_at=msg.created_at,
        )
        for msg in messages
    ]
