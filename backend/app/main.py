"""
AgentSphere-AI FastAPI Backend

Production-ready API for AI agent interactions with MCP integration.
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Add project root to path for imports
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.app.config import settings
from backend.app.api.v1.router import router as api_v1_router
from backend.app.api.websocket import router as websocket_router
from backend.app.db import close_db
from backend.app.core.logging import setup_logging
from backend.app.core.middleware import register_middlewares
from backend.app.core.exceptions import register_exception_handlers
from backend.app.core.mcp.pool import mcp_pool
import uvicorn


# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initializes resources on startup and cleans up on shutdown.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Start MCP Pool cleanup task
    cleanup_task = asyncio.create_task(mcp_pool.start_cleanup_loop())

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down background tasks...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    await mcp_pool.shutdown()

    logger.info("Shutting down application...")
    await close_db()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Production-ready API for AI agent interactions with MCP (Model Context Protocol) integration.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Infrastructure
register_middlewares(app)
register_exception_handlers(app)

# Routers
app.include_router(api_v1_router)
app.include_router(websocket_router, prefix="/api/v1")


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "service": settings.APP_NAME,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "api_prefix": "/api/v1",
    }


if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )

