from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routers import chat, sessions, tools, metadata
from src.core.state import init_checkpointer
from src.core.mcp.manager import MCPManager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AgentSphere-AI API",
    description="FastAPI Backend for AgentSphere-AI",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(chat.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(metadata.router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up AgentSphere-AI API...")
    await init_checkpointer()
    
    # Initialize MCP Manager (Deferred)
    manager = MCPManager()
    await manager.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down...")
    manager = MCPManager()
    await manager.cleanup()

@app.get("/health")
async def health_check():
    return {"status": "ok"}
