from fastapi import APIRouter, HTTPException, Depends
from src.api.schemas.base import SessionCreate, SessionResponse, ChatResponse
from src.core.state import get_or_create_session, load_history, clear_current_session
from typing import List, Dict, Any

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.post("/", response_model=SessionResponse)
async def create_session(request: SessionCreate):
    # If a specific session ID is provided, use it
    if request.session_id and not request.force_new:
        from src.core.state.thread_manager import save_current_session
        save_current_session(request.session_id, request.tenant_id)
        return SessionResponse(
            session_id=request.session_id,
            tenant_id=request.tenant_id,
            created_at="now",
            is_new=False
        )

    # If force_new is requested, clear the current session pointer
    if request.force_new:
        clear_current_session()
        
    # In the current implementation, get_or_create_session uses a global variable for thread_id
    thread_id, is_new = get_or_create_session(request.tenant_id)
    
    return SessionResponse(
        session_id=thread_id,
        tenant_id=request.tenant_id,
        created_at="now",
        is_new=is_new
    )

@router.get("/{session_id}/history")
async def get_session_history(session_id: str, tenant_id: str, user_id: str):
    history = await load_history(session_id, tenant_id, user_id)
    formatted_history = []
    for msg in history:
        role = "user" if msg.type == "human" else "assistant"
        formatted_history.append({"role": role, "content": msg.content})
    return formatted_history

@router.delete("/{session_id}")
async def delete_session(session_id: str):
    from src.core.state.conversation_store import delete_conversation
    
    # Permanently delete from database
    deleted = await delete_conversation(session_id)
    
    # Also clear the global current session if it matches
    clear_current_session()
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {"message": "Session deleted permanently"}

@router.get("/")
async def list_sessions(tenant_id: str, user_id: str):
    from src.core.state.conversation_store import list_conversations
    from uuid import UUID
    
    try:
        tenant_uuid = UUID(tenant_id)
        user_uuid = UUID(user_id)
        conversations = await list_conversations(tenant_uuid, user_uuid)
        
        return [
            {
                "session_id": c.thread_id,
                "title": c.title,
                "updated_at": c.updated_at.isoformat()
            }
            for c in conversations
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
