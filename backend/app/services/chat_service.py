"""
Chat Service for orchestrating chat interactions.
Handles message processing, agent execution, and HITL integration.
Simplified to use LangGraph checkpointer for pause/resume.
"""

import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.models.conversation import Conversation
from backend.app.models.message import Message, MessageRole
from backend.app.models.mcp_server import MCPServerConfig
from backend.app.core.state.models import User

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for orchestrating chat interactions.
    Integrates Planner, Agent, and simplified HITL flows.
    """
    
    def __init__(self, user_id: UUID, db: AsyncSession):
        self.user_id = user_id
        self.db = db
    
    async def process_message(
        self,
        conversation: Conversation,
        user_input: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message and yield streaming events.
        New architecture: uses checkpointer & agent middleware for HITL.
        """
        try:
            yield {"type": "status", "content": "Processing your request..."}
            
            # Load history
            history = await self._load_history(conversation.id)
            
            # 1. Plan / Route
            available_servers = await self._get_available_servers()
            
            if not available_servers:
                yield {"type": "status", "content": "Generating response..."}
                async for event in self._direct_response(user_input, history):
                    yield event
                return
            
            yield {"type": "status", "content": "Planning task..."}
            
            from backend.app.core.agents.planner import Planner
            plan_result = None
            direct_tokens = []
            
            planner_gen = Planner().plan(user_input, history, available_servers)
            async for chunk in planner_gen:
                if isinstance(chunk, str):
                    direct_tokens.append(chunk)
                    yield {"type": "token", "content": chunk}
                elif isinstance(chunk, dict):
                    plan_result = chunk

            if not plan_result:
                if direct_tokens:
                    await self._save_assistant_message(conversation.id, "".join(direct_tokens))
                return

            servers_to_use = plan_result.get("servers", [])
            if not servers_to_use:
                # Direct response
                resp = plan_result.get("response", "")
                
                # Use escaped tokens if we have them (they are more reliable than final parse fallback)
                content_to_save = "".join(direct_tokens) or resp
                
                # If content_to_save looks like raw JSON with "response" key, try to extract it
                # as a last resort fallback for bad data
                if isinstance(content_to_save, str) and content_to_save.strip().startswith("{"):
                    try:
                        maybe_json = json.loads(content_to_save)
                        if isinstance(maybe_json, dict) and "response" in maybe_json:
                            content_to_save = maybe_json["response"]
                    except:
                        pass
                
                if resp and not direct_tokens:
                    yield {"type": "token", "content": resp}
                
                await self._save_assistant_message(conversation.id, content_to_save)
                return

            # 2. Execute with Agent
            yield {"type": "status", "content": f"Connecting to: {', '.join(servers_to_use)}..."}
            
            from backend.app.core.mcp.pool import mcp_pool
            from backend.app.core.agents.agent import Agent
            from backend.app.core.state.checkpointer import get_checkpointer
            from backend.app.core.llm.provider import LLMFactory

            # Get simplified Manager
            mcp_manager = await mcp_pool.get_manager(self.user_id)
            
            # Connect & Get Tools
            # Only connect to the servers suggested by the planner
            await mcp_manager.connect_servers(servers_to_use)
            
            # Get tools only from these servers
            tools = await mcp_manager.get_tools(server_names=servers_to_use)
            
            # --- PERSISTENCE: Save active servers to conversation metadata ---
            # This ensures resume_execution knows which servers to connect to.
            # We create a new dict to ensure SQLAlchemy detects the change on JSONB.
            new_metadata = dict(conversation.extra_metadata or {})
            new_metadata["active_servers"] = servers_to_use
            conversation.extra_metadata = new_metadata
            self.db.add(conversation)
            await self.db.commit()
            # -----------------------------------------------------------------
            
            if not tools:
                yield {"type": "error", "content": "No tools available."}
                return

            # Prepare Agent
            checkpointer = get_checkpointer()
            llm = LLMFactory.load_config_and_create_llm()
            
            # Get user's HITL settings
            user = await self.db.get(User, self.user_id)
            hitl_config = user.hitl_config if user else {}
            
            agent = Agent(llm, tools, checkpointer, hitl_config=hitl_config)

            yield {"type": "status", "content": "Executing..."}
            
            final_response = ""
            
            async for event in agent.execute_streaming(
                user_input, 
                history=[], # Rely on checkpointer for history to avoid duplication/corruption
                thread_id=conversation.thread_id
            ):
                event_type = event.get("type")
                
                if event_type == "token":
                    final_response += event.get("content", "")
                    yield event
                
                elif event_type == "approval_required":
                    # Save what we have so far (thought process) so it persists on refresh
                    if final_response:
                         await self._save_assistant_message(conversation.id, final_response)
                    
                    # Just yield it - no DB record needed for the event itself, checkpointer has state
                    yield event
                    return # Stop stream, wait for resume
                
                elif event_type in ["tool_start", "tool_end", "error"]:
                    yield event
            
            if final_response:
                await self._save_assistant_message(conversation.id, final_response)
                
        except Exception as e:
            logger.error(f"Processing error: {e}", exc_info=True)
            yield {"type": "error", "content": f"Error: {str(e)}"}

    async def resume_execution(
        self,
        conversation: Conversation,
        decisions: List[Dict[str, Any]],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Resume execution after HITL approval.
        Uses checkpointer to continue from interrupted state.
        """
        try:
            from backend.app.core.mcp.pool import mcp_pool
            from backend.app.core.agents.agent import Agent
            from backend.app.core.state.checkpointer import get_checkpointer
            from backend.app.core.llm.provider import LLMFactory

            yield {"type": "status", "content": "Resuming execution..."}

            # Re-initialize context (Manager, Tools, Agent)
            mcp_manager = await mcp_pool.get_manager(self.user_id)
            
            # Re-initialize context (Manager, Tools, Agent)
            mcp_manager = await mcp_pool.get_manager(self.user_id)
            
            # For resume, use persisted active servers if available
            active_servers = (conversation.extra_metadata or {}).get("active_servers", [])
            
            if active_servers:
                await mcp_manager.connect_servers(active_servers)
                tools = await mcp_manager.get_tools(server_names=active_servers)
            else:
                # Fallback for legacy threads: Connect to all enabled
                await mcp_manager._connect_all_enabled()
                tools = await mcp_manager.get_tools()
            
            user = await self.db.get(User, self.user_id)
            hitl_config = user.hitl_config if user else {}
            
            checkpointer = get_checkpointer()
            llm = LLMFactory.load_config_and_create_llm()
            
            agent = Agent(llm, tools, checkpointer, hitl_config=hitl_config)
            
            # Resume
            final_response = ""
            
            async for event in agent.resume_streaming(
                thread_id=conversation.thread_id,
                decisions=decisions
            ):
                event_type = event.get("type")

                if event_type == "token":
                    final_response += event.get("content", "")
                    yield event
                
                elif event_type == "approval_required":
                    yield event
                    return
                
                elif event_type in ["tool_start", "tool_end", "error"]:
                    yield event

            if final_response:
                # Append to last assistant message if we can, or simplified: just save new chunk
                # Ideally we append to the message that was "paused"
                await self._save_assistant_message(conversation.id, final_response)
                
        except Exception as e:
            logger.error(f"Resume error: {e}", exc_info=True)
            yield {"type": "error", "content": f"Resume error: {str(e)}"}

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------
    
    async def _load_history(self, conversation_id: UUID) -> List[Any]:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(50)
        )
        history = []
        for msg in result.scalars().all():
            if msg.role == MessageRole.USER:
                history.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                history.append(AIMessage(content=msg.content))
            elif msg.role == MessageRole.SYSTEM:
                history.append(SystemMessage(content=msg.content))
        return history
    
    async def _get_available_servers(self) -> Dict[str, Any]:
        result = await self.db.execute(
            select(MCPServerConfig).where(
                MCPServerConfig.user_id == self.user_id,
                MCPServerConfig.enabled == True
            )
        )
        return {
            s.name: {"config": s.config, "description": s.config.get("description", "")}
            for s in result.scalars().all()
        }
    
    async def _save_assistant_message(self, conversation_id: UUID, content: str):
        msg = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
        )
        self.db.add(msg)
        await self.db.commit()
        
    async def _direct_response(self, user_input, history):
        """Fallback direct response if no planner."""
        try:
            from backend.app.core.llm.provider import LLMFactory
            llm = LLMFactory.load_config_and_create_llm()
            messages = [{"role": "system", "content": "You are a helpful assistant."}]
            # ... simple reconstruction ...
            # (Simplifying this method for brevity as logic is standard)
            # Reusing history logic
            lc_msgs = history + [("user", user_input)]
            async for chunk in llm.astream(lc_msgs):
                 if hasattr(chunk, 'content') and chunk.content:
                    yield {"type": "token", "content": chunk.content}
        except Exception as e:
            yield {"type": "error", "content": str(e)}
