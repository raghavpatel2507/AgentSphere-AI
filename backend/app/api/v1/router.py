"""
API v1 Router - Aggregates all route modules.
"""

from fastapi import APIRouter

from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.chat import router as chat_router
from backend.app.api.v1.conversations import router as conversations_router
from backend.app.api.v1.mcp import router as mcp_router
from backend.app.api.v1.tools import router as tools_router
from backend.app.api.v1.registry import router as registry_router
from backend.app.api.v1.hitl import router as hitl_router
from backend.app.api.v1.oauth import router as oauth_router


# Create main v1 router
router = APIRouter(prefix="/api/v1")

# Include all route modules
router.include_router(auth_router)
router.include_router(chat_router)
router.include_router(conversations_router)
router.include_router(mcp_router)
router.include_router(tools_router)
router.include_router(registry_router)
router.include_router(hitl_router)
router.include_router(oauth_router)
