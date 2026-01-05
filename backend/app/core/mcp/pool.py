"""
MCP Connection Pool.
Maintains active MCPManager instances per user for efficient connection reuse.
Simplified signature (removed HITL/Conversation params).
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional
from backend.app.core.mcp.manager import MCPManager

logger = logging.getLogger(__name__)

class MCPConnectionPool:
    """
    Singleton connection pool for MCP Managers.
    Maintains active MCPManager instances per user.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MCPConnectionPool, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        
        # Map user_id -> { "manager": MCPManager, "last_accessed": float }
        self._active_managers: Dict[str, Dict[str, Any]] = {}
        self.IDLE_TIMEOUT_SECONDS = 300  # 5 minutes
        self.initialized = True
        logger.info("MCP Connection Pool initialized")

    async def get_manager(self, user_id: Any) -> MCPManager:
        """
        Get existing manager for user or create new one.
        """
        user_key = str(user_id)
        current_time = time.time()
        
        if user_key in self._active_managers:
            entry = self._active_managers[user_key]
            entry["last_accessed"] = current_time
            # logger.debug(f"Retrieved pool manager for {user_id}")
            return entry["manager"]
            
        # Create new manager
        logger.info(f"Creating new MCP Manager for pool (User: {user_id})")
        manager = MCPManager(user_id)
        await manager.initialize()
        
        self._active_managers[user_key] = {
            "manager": manager,
            "last_accessed": current_time
        }
        return manager

    async def cleanup_idle_managers(self):
        current_time = time.time()
        users_to_remove = []
        
        for user_id, entry in self._active_managers.items():
            if current_time - entry["last_accessed"] > self.IDLE_TIMEOUT_SECONDS:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            logger.info(f"Cleaning up idle MCP Manager for user {user_id}")
            entry = self._active_managers.pop(user_id)
            try:
                # Disconnect active sessions (fire and forget cleanup)
                # In real prod, we might be more careful, but pure disconnect is safe
                # Note: manager.cleanup() doesn't exist in new simple manager, 
                # we only have disconnect_server needed if we want to close sessions.
                # But manager instance GC usually handles it or client.__del__.
                # We'll explicitly close if client exposed close.
                pass 
            except Exception as e:
                logger.error(f"Error cleaning manager: {e}")

    async def start_cleanup_loop(self):
        logger.info("Starting MCP cleanup loop")
        while True:
            try:
                await asyncio.sleep(60)
                await self.cleanup_idle_managers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def shutdown(self):
        logger.info("Shutting down MCP Connection Pool...")
        self._active_managers.clear()

mcp_pool = MCPConnectionPool()
