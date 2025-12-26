"""
WebSocket handler for real-time chat streaming.
"""

import json
import logging
from typing import Dict, Any
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.db import AsyncSessionLocal
from backend.app.models.user import User
from backend.app.models.conversation import Conversation
from backend.app.core.auth import decode_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, thread_id: str):
        await websocket.accept()
        self.active_connections[thread_id] = websocket
    
    def disconnect(self, thread_id: str):
        if thread_id in self.active_connections:
            del self.active_connections[thread_id]
    
    async def send_event(self, thread_id: str, event: Dict[str, Any]):
        if thread_id in self.active_connections:
            await self.active_connections[thread_id].send_json(event)


manager = ConnectionManager()


async def get_user_from_token(token: str) -> UUID | None:
    """Authenticate user from WebSocket token."""
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    
    user_id_str = payload.get("sub")
    if not user_id_str:
        return None
    
    try:
        return UUID(user_id_str)
    except ValueError:
        return None


@router.websocket("/ws/{thread_id}")
async def websocket_chat(
    websocket: WebSocket,
    thread_id: str,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time chat streaming.
    
    Connect with: ws://host/api/v1/ws/{thread_id}?token=<jwt>
    
    Send message format:
    {
        "type": "message",
        "content": "Your message here"
    }
    
    Receive events:
    - {"type": "status", "content": "..."}
    - {"type": "token", "content": "..."}
    - {"type": "tool_start", "tool": "...", "inputs": {...}}
    - {"type": "tool_end", "tool": "...", "output": "..."}
    - {"type": "approval_required", "request_id": "...", "tool_name": "...", "tool_args": {...}}
    - {"type": "error", "message": "..."}
    - {"type": "done"}
    """
    # Authenticate
    user_id = await get_user_from_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    
    # Connect
    await manager.connect(websocket, thread_id)
    
    try:
        async with AsyncSessionLocal() as db:
            # Verify conversation belongs to user
            result = await db.execute(
                select(Conversation).where(
                    Conversation.thread_id == thread_id,
                    Conversation.user_id == user_id,
                    Conversation.is_deleted == False
                )
            )
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                await websocket.send_json({
                    "type": "error",
                    "message": "Conversation not found"
                })
                await websocket.close(code=4004, reason="Conversation not found")
                return
            
            # Send connected confirmation
            await websocket.send_json({
                "type": "status",
                "content": "Connected to chat"
            })
            
            # Listen for messages
            while True:
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON"
                    })
                    continue
                
                msg_type = message.get("type")
                
                if msg_type == "message":
                    content = message.get("content", "").strip()
                    if not content:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Empty message"
                        })
                        continue
                    
                    # Process message
                    from backend.app.services.chat_service import ChatService
                    from backend.app.models.message import Message
                    
                    # Save user message
                    user_message = Message(
                        conversation_id=conversation.id,
                        role='USER',
                        content=content,
                    )
                    db.add(user_message)
                    await db.commit()
                    
                    # Process with ChatService
                    chat_service = ChatService(user_id, db)
                    
                    final_response = ""
                    async for event in chat_service.process_message(conversation, content):
                        await websocket.send_json(event)
                        
                        if event.get("type") == "token":
                            final_response += event.get("content", "")
                    
                    # Send done event
                    await websocket.send_json({
                        "type": "done",
                        "final_response": final_response
                    })
                    
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    
                elif msg_type == "hitl_decision":
                    # Handle HITL approval/rejection
                    request_id = message.get("request_id")
                    approved = message.get("approved", False)
                    
                    if request_id:
                        from backend.app.models.hitl_request import HITLRequest
                        from datetime import datetime, timezone
                        
                        result = await db.execute(
                            select(HITLRequest).where(
                                HITLRequest.id == UUID(request_id),
                                HITLRequest.user_id == user_id
                            )
                        )
                        hitl_req = result.scalar_one_or_none()
                        
                        if hitl_req and hitl_req.status == 'PENDING':
                            hitl_req.status = 'APPROVED' if approved else 'REJECTED'
                            hitl_req.decision_at = datetime.now(timezone.utc)
                            await db.commit()
                            
                            await websocket.send_json({
                                "type": "status",
                                "content": f"Tool {'approved' if approved else 'rejected'}"
                            })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {thread_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        manager.disconnect(thread_id)
