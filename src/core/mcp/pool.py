import asyncio
import time
import logging
from typing import Dict, Optional, Any
from src.core.mcp.manager import MCPManager

logger = logging.getLogger(__name__)

class MCPConnectionPool:
    """
    Singleton connection pool for MCP Managers.
    Maintains active MCPManager instances per user to allow connection reuse ("Instant Resume").
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
        # Configuration
        self.IDLE_TIMEOUT_SECONDS = 300  # 5 minutes
        self.initialized = True
        logger.info("MCP Connection Pool initialized")

    async def get_manager(self, user_id: Any, conversation_id: Optional[Any] = None, hitl_request_id: Optional[str] = None) -> MCPManager:
        """
        Get an existing manager for the user or create a new one.
        Updates the last_accessed timestamp.
        """
        user_key = str(user_id)
        current_time = time.time()
        
        if user_key in self._active_managers:
            logger.debug(f"Retrieved pooled MCP Manager for user {user_id}")
            entry = self._active_managers[user_key]
            entry["last_accessed"] = current_time
            manager = entry["manager"]
            
            # Update request-specific context
            manager.conversation_id = conversation_id
            manager.hitl_request_id = hitl_request_id
            return manager
            
        # Create new manager
        logger.info(f"Creating new MCP Manager for pool (User: {user_id})")
        manager = MCPManager(user_id, conversation_id, hitl_request_id)
        await manager.initialize()
        
        self._active_managers[user_key] = {
            "manager": manager,
            "last_accessed": current_time
        }
        return manager

    async def cleanup_idle_managers(self):
        """
        Remove managers that haven't been accessed within the timeout period.
        """
        current_time = time.time()
        users_to_remove = []
        
        for user_id, entry in self._active_managers.items():
            if current_time - entry["last_accessed"] > self.IDLE_TIMEOUT_SECONDS:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            logger.info(f"Cleaning up idle MCP Manager for user {user_id}")
            entry = self._active_managers.pop(user_id)
            manager = entry["manager"]
            await manager.cleanup()

    async def start_cleanup_loop(self):
        """Run periodic cleanup in background."""
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
        """Close all managers."""
        logger.info("Shutting down MCP Connection Pool...")
        for user_id, entry in self._active_managers.items():
            await entry["manager"].cleanup()
        self._active_managers.clear()

# Global instance
mcp_pool = MCPConnectionPool()
