from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message")
    session_id: str = Field(..., description="Session identifier (Thread ID)")
    tenant_id: str = Field(..., description="Tenant identifier")
    user_id: str = Field(..., description="User identifier")

class ChatResponse(BaseModel):
    response: str = Field(..., description="The agent's response")
    history: List[Dict[str, Any]] = Field(default=[], description="Updated conversation history")

class SessionCreate(BaseModel):
    tenant_id: str = Field(..., description="Tenant identifier")
    user_id: str = Field(..., description="User identifier")
    force_new: Optional[bool] = Field(default=False, description="Whether to force a new session")

class SessionResponse(BaseModel):
    session_id: str
    tenant_id: str
    created_at: str
    is_new: bool

class ToolStatus(BaseModel):
    name: str
    connected: bool
    tools_count: int
    description: Optional[str] = None

class ToolToggleRequest(BaseModel):
    enable: bool
