"""
Chat routes.
Handles creating chats, sending messages, resumes, and streaming responses.
Simplified to remove DB-based HITL logic.
"""

import uuid
import json
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.conversation import Conversation, ConversationStatus
from backend.app.models.message import Message, MessageRole
from backend.app.api.v1.chat.schemas import (
    NewChatRequest,
    SendMessageRequest,
    ResumeRequest,
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
    """Create a new chat conversation."""
    thread_id = f"thread_{uuid.uuid4().hex[:12]}"
    tenant_id = current_user.tenant_id or current_user.id
    
    conversation = Conversation(
        tenant_id=tenant_id,
        user_id=current_user.id,
        thread_id=thread_id,
        title=request.title or "New Conversation",
        status=ConversationStatus.ACTIVE,
    )
    
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    
    if request.initial_message:
        message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
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
    May return 'approval_required' event if HITL is triggered.
    """
    # Verify ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    
    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=request.content,
    )
    db.add(user_message)
    await db.commit()
    
    # Auto-title
    if conversation.title == "New Conversation":
        conversation.title = request.content[:50] + ("..." if len(request.content) > 50 else "")
        await db.commit()
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            from backend.app.services.chat_service import ChatService
            chat_service = ChatService(current_user.id, db)
            
            async for event in chat_service.process_message(
                conversation=conversation,
                user_input=request.content,
            ):
                yield f"data: {json.dumps(event)}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/{thread_id}/resume")
async def resume_chat(
    thread_id: str,
    request: ResumeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Resume chat after HITL approval.
    Provide decisions like [{"type": "approve"}] or [{"type": "reject"}].
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
        
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            from backend.app.services.chat_service import ChatService
            chat_service = ChatService(current_user.id, db)
            
            async for event in chat_service.resume_execution(
                conversation=conversation,
                decisions=request.decisions,
            ):
                yield f"data: {json.dumps(event)}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
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
    Checks checkpointer for any pending HITL interruptions.
    """
    result = await db.execute(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.user_id == current_user.id,
            Conversation.is_deleted == False
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    
    # Check for pending approval using Checkpointer directly
    # No need to instantiate Agent or connect to tools!
    try:
        from backend.app.core.state.checkpointer import get_checkpointer
        
        checkpointer = get_checkpointer()
        if not checkpointer:
            # Should basically never happen if app is running
            return ChatStatusResponse(
                thread_id=thread_id,
                is_processing=False,
                has_pending_approval=False,
                last_activity=conversation.updated_at,
            )

        config = {"configurable": {"thread_id": thread_id}}
        state = await checkpointer.aget(config)
        
        pending_approval = False
        tool_name = None
        tool_args = None
        
        # Parse LangGraph state for interrupts
        # State format: {"v": 1, "ts": "...", "channel_values": { ... "tasks": [...] }, ...}
        # Actually checkpointer returns a Checkpoint object or dict depending on implementation
        # But wait, we need to know the *structure* of the state to find interrupts.
        # LangGraph's checkpointer returns a Checkpoint tuple.
        # However, `agent.get_pending_interrupt` used `agent.aget_state()` which returns StateSnapshot.
        # StateSnapshot wraps the checkpoint. 
        # Accessing raw checkpoint is harder because we need to know where interrupts are stored (usually in 'tasks' in channel_values?).
        # Actually, simpler approach:
        # The 'tasks' logic in `agent.get_pending_interrupt` was looking at `state.tasks`.
        # `state` from `aget_state` is a `StateSnapshot`.
        # We can construct a lightweight StateSnapshot if we have the checkpoint?
        # Or... let's look at how tasks are stored.
        # It's safer to re-implement `get_pending_interrupt` logic logic WITHOUT Agent class if possible,
        # but `aget_state` handles a lot of complexity (filtering, etc).
        
        # ALTERNATIVE: Instantiate Agent with NO tools.
        # If we just want to read state, we don't need tools bound to it, usually.
        # Let's try init Agent with empty tools list.
        # This is much safer than parsing raw checkpoint blobs.
        
        from backend.app.core.agents.agent import Agent
        from backend.app.core.llm.provider import LLMFactory
        
        # No tools needed for just checking state!
        agent = Agent(
            llm=LLMFactory.load_config_and_create_llm(), 
            tools=[], 
            checkpointer=checkpointer
        )
        
        pending = await agent.get_pending_interrupt(thread_id)
        
        return ChatStatusResponse(
            thread_id=thread_id,
            is_processing=False, # We don't track active processing state easily 
            has_pending_approval=bool(pending),
            pending_tool_name=pending["tool_name"] if pending else None,
            pending_tool_args=pending["tool_args"] if pending else None,
            last_activity=conversation.updated_at,
        )
    except Exception as e:
        # Fallback 
        return ChatStatusResponse(
            thread_id=thread_id,
            is_processing=False,
            has_pending_approval=False,
            last_activity=conversation.updated_at,
        )


@router.get("/{thread_id}/messages", response_model=list[MessageResponse])
async def get_chat_messages(
    thread_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    
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


@router.get("/suggestions", response_model=list[str])
async def get_chat_suggestions(
    q: str = "",
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get prompt autocomplete suggestions from message history.
    """
    if not q or len(q.strip()) < 2:
        return []
        
    from backend.app.services.chat_service import ChatService
    chat_service = ChatService(current_user.id, db)
    
    return await chat_service.get_suggestions(q, limit)