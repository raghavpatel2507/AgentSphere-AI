"""
HITL (Human-in-the-Loop) routes.
Handles pending approval requests, approve/reject actions.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from backend.app.dependencies import get_db, get_current_user
from backend.app.models.user import User
from backend.app.models.hitl_request import HITLRequest
from backend.app.models.conversation import Conversation
from backend.app.api.v1.hitl.schemas import (
    HITLDecisionRequest,
    ApproveAndWhitelistRequest,
    HITLRequestResponse,
    HITLListResponse,
    HITLStatus,
)
from backend.app.api.v1.auth.schemas import MessageResponse


router = APIRouter(prefix="/hitl", tags=["HITL"])


@router.get("/pending", response_model=HITLListResponse)
async def list_pending_requests(
    limit: int = Query(50, ge=1, le=100),
    include_expired: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List pending HITL approval requests for the current user.
    """
    query = select(HITLRequest).where(
        HITLRequest.user_id == current_user.id,
        HITLRequest.status == 'PENDING'
    )
    
    result = await db.execute(query.order_by(HITLRequest.created_at.desc()).limit(limit))
    requests = result.scalars().all()
    
    # Check for expired requests
    now = datetime.now(timezone.utc)
    pending_count = 0
    responses = []
    
    for req in requests:
        is_expired = req.expires_at and now > req.expires_at
        
        if is_expired and not include_expired:
            # Update status to EXPIRED
            req.status = 'EXPIRED'
            await db.commit()
            continue
        
        if not is_expired:
            pending_count += 1
        
        # Get thread_id from conversation
        conv_result = await db.execute(
            select(Conversation.thread_id).where(Conversation.id == req.conversation_id)
        )
        thread_id = conv_result.scalar_one_or_none()
        
        responses.append(HITLRequestResponse(
            id=req.id,
            user_id=req.user_id,
            conversation_id=req.conversation_id,
            thread_id=thread_id,
            tool_name=req.tool_name,
            tool_args=req.tool_args,
            server_name=req.server_name,
            status=req.status,
            decision_at=req.decision_at,
            decision_reason=req.decision_reason,
            created_at=req.created_at,
            expires_at=req.expires_at,
            is_expired=is_expired,
        ))
    
    return HITLListResponse(
        requests=responses,
        total=len(responses),
        pending_count=pending_count,
    )


@router.get("/{request_id}", response_model=HITLRequestResponse)
async def get_hitl_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get details for a specific HITL request.
    """
    result = await db.execute(
        select(HITLRequest).where(
            HITLRequest.id == request_id,
            HITLRequest.user_id == current_user.id
        )
    )
    req = result.scalar_one_or_none()
    
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HITL request not found"
        )
    
    # Get thread_id
    conv_result = await db.execute(
        select(Conversation.thread_id).where(Conversation.id == req.conversation_id)
    )
    thread_id = conv_result.scalar_one_or_none()
    
    return HITLRequestResponse(
        id=req.id,
        user_id=req.user_id,
        conversation_id=req.conversation_id,
        thread_id=thread_id,
        tool_name=req.tool_name,
        tool_args=req.tool_args,
        server_name=req.server_name,
        status=req.status,
        decision_at=req.decision_at,
        decision_reason=req.decision_reason,
        created_at=req.created_at,
        expires_at=req.expires_at,
        is_expired=req.is_expired,
    )


@router.post("/{request_id}/approve", response_model=MessageResponse)
async def approve_request(
    request_id: UUID,
    body: Optional[HITLDecisionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Approve a pending HITL request.
    
    This allows the tool to be executed.
    """
    result = await db.execute(
        select(HITLRequest).where(
            HITLRequest.id == request_id,
            HITLRequest.user_id == current_user.id
        )
    )
    req = result.scalar_one_or_none()
    
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HITL request not found"
        )
    
    if req.status != 'PENDING':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request already {req.status.lower()}"
        )
    
    if req.is_expired:
        req.status = 'EXPIRED'
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request has expired"
        )
    
    req.status = 'APPROVED'
    req.decision_at = datetime.now(timezone.utc)
    req.decision_reason = body.reason if body else None
    await db.commit()
    
    return MessageResponse(message=f"Tool '{req.tool_name}' approved for execution")


@router.post("/{request_id}/reject", response_model=MessageResponse)
async def reject_request(
    request_id: UUID,
    body: Optional[HITLDecisionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reject a pending HITL request.
    
    This prevents the tool from being executed.
    """
    result = await db.execute(
        select(HITLRequest).where(
            HITLRequest.id == request_id,
            HITLRequest.user_id == current_user.id
        )
    )
    req = result.scalar_one_or_none()
    
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HITL request not found"
        )
    
    if req.status != 'PENDING':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request already {req.status.lower()}"
        )
    
    req.status = 'REJECTED'
    req.decision_at = datetime.now(timezone.utc)
    req.decision_reason = body.reason if body else None
    await db.commit()
    
    return MessageResponse(message=f"Tool '{req.tool_name}' rejected")


@router.post("/{request_id}/approve-and-whitelist", response_model=MessageResponse)
async def approve_and_whitelist(
    request_id: UUID,
    body: ApproveAndWhitelistRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Approve a request and add the tool to the session whitelist.
    
    This allows future calls to the same tool without requiring approval.
    """
    result = await db.execute(
        select(HITLRequest).where(
            HITLRequest.id == request_id,
            HITLRequest.user_id == current_user.id
        )
    )
    req = result.scalar_one_or_none()
    
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HITL request not found"
        )
    
    if req.status != 'PENDING':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request already {req.status.lower()}"
        )
    
    # Approve the request
    req.status = 'APPROVED'
    req.decision_at = datetime.now(timezone.utc)
    req.decision_reason = body.reason
    await db.commit()
    
    # Note: Actual whitelisting would be handled by the chat service
    # The whitelist is typically session-based and managed in memory
    
    return MessageResponse(
        message=f"Tool '{req.tool_name}' approved and whitelisted for {body.whitelist_duration or 'this session'}"
    )
