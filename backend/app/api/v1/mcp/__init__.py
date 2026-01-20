# MCP routes package
from fastapi import APIRouter
from backend.app.api.v1.mcp.routes import router as servers_router
from backend.app.api.v1.mcp import oauth_routes

# Create a main router for the MCP package
router = APIRouter()

# Include sub-routers
router.include_router(servers_router)
router.include_router(oauth_routes.router)

__all__ = ["router"]
