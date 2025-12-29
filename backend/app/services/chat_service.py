"""
Chat Service for orchestrating chat interactions.
Handles message processing, agent execution, and HITL integration.
"""

import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.models.mcp_server import MCPServerConfig
from backend.app.models.hitl_request import HITLRequest
from backend.app.config import settings

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for orchestrating chat interactions.
    Integrates Planner, Agent, and HITL flows.
    """
    
    def __init__(self, user_id: UUID, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self._mcp_manager = None
        self._planner = None
        self._whitelist = set()  # Session whitelist for HITL bypass
    
    async def process_message(
        self,
        conversation: Conversation,
        user_input: str,
        hitl_request_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user message and yield streaming events.
        
        Yields:
            Stream events (status, token, tool_start, tool_end, approval_required, error, done)
        """
        try:
            # Yield initial status
            yield {"type": "status", "content": "Processing your request..."}
            
            # Load conversation history
            history = await self._load_history(conversation.id)
            
            # Get available MCP servers
            available_servers = await self._get_available_servers()
            
            if not available_servers:
                # No MCP servers, use direct LLM response
                yield {"type": "status", "content": "Generating response..."}
                
                async for event in self._direct_response(user_input, history):
                    yield event
                return
            
            # Initialize planner
            yield {"type": "status", "content": "Analyzing request..."}
            
            from src.core.agents.planner import Planner
            from src.core.llm.provider import LLMFactory
            
            planner = Planner()
            
            # Get plan
            plan_result = None
            direct_tokens = []
            
            async for chunk in planner.plan(user_input, history, available_servers):
                if isinstance(chunk, str):
                    # Direct response token
                    direct_tokens.append(chunk)
                    yield {"type": "token", "content": chunk}
                elif isinstance(chunk, dict):
                    plan_result = chunk
            
            if not plan_result:
                # Planner returned direct response
                if direct_tokens:
                    final_response = "".join(direct_tokens)
                    await self._save_assistant_message(conversation.id, final_response)
                return
            
            # Check if tools are needed
            servers_to_use = plan_result.get("servers", [])
            
            if not servers_to_use:
                # Direct response from planner
                response_text = plan_result.get("response", "")
                if response_text:
                    yield {"type": "token", "content": response_text}
                    await self._save_assistant_message(conversation.id, response_text)
                return
            
            # Initialize MCP and Agent
            yield {"type": "status", "content": f"Connecting to agents: {', '.join(servers_to_use)}..."}
            
            from src.core.mcp.manager import MCPManager
            from src.core.agents.agent import Agent
            
            mcp_manager = MCPManager(
                self.user_id, 
                conversation_id=conversation.id,
                hitl_request_id=hitl_request_id
            )
            await mcp_manager.initialize()
            
            # Connect to required servers
            await mcp_manager.connect_to_servers(servers_to_use)
            
            # Get tools
            yield {"type": "status", "content": "Loading tools..."}
            tools = await mcp_manager.get_tools_for_servers(servers_to_use)
            
            if not tools:
                yield {"type": "error", "content": "No tools available from selected servers"}
                return
            
            # Create agent
            llm = LLMFactory.load_config_and_create_llm()
            agent = Agent(llm, mcp_manager._mcp_client, tools)
            
            # Execute agent with streaming
            yield {"type": "status", "content": "Executing task..."}
            
            final_response = ""
            
            try:
                async for event in agent.execute_streaming(user_input, history):
                    event_type = event.get("type")
                    
                    if event_type == "token":
                        final_response += event.get("content", "")
                        yield event
                    
                    elif event_type == "tool_start":
                        yield {
                            "type": "tool_start",
                            "tool": event.get("tool"),
                            "inputs": event.get("inputs", {}),
                        }
                    
                    elif event_type == "tool_end":
                        # Serialize tool output - it may be a LangChain message object
                        output = event.get("output")
                        if hasattr(output, 'content'):
                            output = output.content
                        elif not isinstance(output, (str, int, float, bool, type(None))):
                            output = str(output)
                        
                        yield {
                            "type": "tool_end",
                            "tool": event.get("tool"),
                            "output": output,
                        }
                    
                    elif event_type == "approval_required":
                        # Create HITL request
                        hitl_request = await self._create_hitl_request(
                            conversation=conversation,
                            tool_name=event.get("tool_name"),
                            tool_args=event.get("tool_args"),
                            server_name=servers_to_use[0] if servers_to_use else "unknown",
                        )
                        
                        yield {
                            "type": "approval_required",
                            "request_id": str(hitl_request.id),
                            "tool_name": event.get("tool_name"),
                            "tool_args": event.get("tool_args"),
                            "message": event.get("message"),
                        }
                        return  # Stop processing until approval
                    
                    elif event_type == "error":
                        yield event
                
                # Save final response
                if final_response:
                    await self._save_assistant_message(conversation.id, final_response)
                    
            finally:
                # Cleanup MCP connections
                await mcp_manager.cleanup()
                
        except Exception as e:
            import traceback
            logger.error(f"Chat processing error: {e}\n{traceback.format_exc()}")
            yield {"type": "error", "content": f"Error: {str(e)}"}
    
    async def _load_history(self, conversation_id: UUID) -> List[Any]:
        """Load conversation history as LangChain messages."""
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(50)  # Limit history for context window
        )
        messages = result.scalars().all()
        
        history = []
        for msg in messages:
            if msg.role == 'USER':
                history.append(HumanMessage(content=msg.content))
            elif msg.role == 'ASSISTANT':
                history.append(AIMessage(content=msg.content))
            elif msg.role == 'SYSTEM':
                history.append(SystemMessage(content=msg.content))
        
        return history
    
    async def _get_available_servers(self) -> Dict[str, Any]:
        """Get available enabled MCP servers for the user."""
        result = await self.db.execute(
            select(MCPServerConfig).where(
                MCPServerConfig.user_id == self.user_id,
                MCPServerConfig.enabled == True
            )
        )
        servers = result.scalars().all()
        
        available = {}
        for server in servers:
            available[server.name] = {
                "config": server.config,
                "description": server.config.get("description", ""),
            }
        
        return available
    
    async def _save_assistant_message(self, conversation_id: UUID, content: str):
        """Save assistant message to database."""
        message = Message(
            conversation_id=conversation_id,
            role='ASSISTANT',
            content=content,
        )
        self.db.add(message)
        await self.db.commit()
    
    async def _create_hitl_request(
        self,
        conversation: Conversation,
        tool_name: str,
        tool_args: Dict[str, Any],
        server_name: str,
    ) -> HITLRequest:
        """Create a HITL approval request."""
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.HITL_REQUEST_TIMEOUT_SECONDS
        )
        
        hitl_request = HITLRequest(
            user_id=self.user_id,
            conversation_id=conversation.id,
            tool_name=tool_name,
            tool_args=tool_args,
            server_name=server_name,
            status='PENDING',
            expires_at=expires_at,
        )
        
        self.db.add(hitl_request)
        
        # Update conversation status
        conversation.status = 'PENDING_APPROVAL'
        await self.db.commit()
        await self.db.refresh(hitl_request)
        
        return hitl_request
    
    async def _direct_response(
        self,
        user_input: str,
        history: List[Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate direct LLM response without tools."""
        try:
            from src.core.llm.provider import LLMFactory
            
            llm = LLMFactory.load_config_and_create_llm()
            
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant."},
            ]
            
            for msg in history:
                if hasattr(msg, 'content'):
                    role = "user" if "Human" in type(msg).__name__ else "assistant"
                    messages.append({"role": role, "content": msg.content})
            
            messages.append({"role": "user", "content": user_input})
            
            async for chunk in llm.astream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    yield {"type": "token", "content": chunk.content}
                    
        except Exception as e:
            logger.error(f"Direct response error: {e}")
            yield {"type": "error", "content": f"Error: {str(e)}"}
