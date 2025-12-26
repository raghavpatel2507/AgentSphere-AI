"""
Conversation routes.
Handles listing, viewing, archiving, and deleting conversations.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.api.v1.conversations.schemas import (
    UpdateTitleRequest,
    ConversationListItem,
    ConversationDetail,
    ConversationListResponse,
    MessageSummary,
)
from backend.app.api.v1.auth.schemas import MessageResponse


router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    include_deleted: bool = Query(False),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List user's conversations with pagination.
    """
    # Base query
    query = select(Conversation).where(Conversation.user_id == current_user.id)
    
    # Apply filters
    if not include_deleted:
        query = query.where(Conversation.is_deleted == False)
    
    if status_filter:
        query = query.where(Conversation.status == status_filter)
    
    if search:
        query = query.where(Conversation.title.ilike(f"%{search}%"))
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.order_by(Conversation.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    conversations = result.scalars().all()
    
    # Build response with message counts
    items = []
    for conv in conversations:
        # Get message count
        msg_count_result = await db.execute(
            select(func.count()).where(Message.conversation_id == conv.id)
        )
        msg_count = msg_count_result.scalar() or 0
        
        # Get last message preview
        last_msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = last_msg_result.scalar_one_or_none()
        preview = None
        if last_msg:
            preview = last_msg.content[:100] + ("..." if len(last_msg.content) > 100 else "")
        
        items.append(ConversationListItem(
            id=conv.id,
            thread_id=conv.thread_id,
            title=conv.title,
            status=conv.status,
            message_count=msg_count,
            last_message_preview=preview,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            is_deleted=conv.is_deleted or False,
        ))
    
    return ConversationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    include_messages: bool = Query(True),
    message_limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get conversation details with messages.
    """
    from uuid import UUID
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format"
        )
    
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    messages = []
    if include_messages:
        msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
            .limit(message_limit)
        )
        msgs = msg_result.scalars().all()
        messages = [
            MessageSummary(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in msgs
        ]
    
    return ConversationDetail(
        id=conversation.id,
        thread_id=conversation.thread_id,
        title=conversation.title,
        status=conversation.status,
        metadata=conversation.extra_metadata or {},
        messages=messages,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        is_deleted=conversation.is_deleted or False,
        deleted_at=conversation.deleted_at,
    )


@router.patch("/{conversation_id}/title", response_model=MessageResponse)
async def update_conversation_title(
    conversation_id: str,
    request: UpdateTitleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation title.
    """
    from uuid import UUID
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format"
        )
    
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid,
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
    
    conversation.title = request.title
    await db.commit()
    
    return MessageResponse(message="Title updated successfully")


@router.delete("/{conversation_id}", response_model=MessageResponse)
async def delete_conversation(
    conversation_id: str,
    hard_delete: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete a conversation (or hard delete if specified).
    """
    from uuid import UUID
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format"
        )
    
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    if hard_delete:
        await db.delete(conversation)
        await db.commit()
        return MessageResponse(message="Conversation permanently deleted")
    else:
        conversation.is_deleted = True
        conversation.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        return MessageResponse(message="Conversation deleted")


@router.patch("/{conversation_id}/restore", response_model=MessageResponse)
async def restore_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Restore a soft-deleted conversation.
    """
    from uuid import UUID
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format"
        )
    
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid,
            Conversation.user_id == current_user.id,
            Conversation.is_deleted == True
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deleted conversation not found"
        )
    
    conversation.is_deleted = False
    conversation.deleted_at = None
    await db.commit()
    
    return MessageResponse(message="Conversation restored")


@router.patch("/{conversation_id}/archive", response_model=MessageResponse)
async def archive_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Archive a conversation.
    """
    from uuid import UUID
    
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format"
        )
    
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid,
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
    
    conversation.status = 'ARCHIVED'
    await db.commit()
    
    return MessageResponse(message="Conversation archived")
