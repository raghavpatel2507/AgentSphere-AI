import logging
from typing import List, Optional, Any
from langchain_core.messages import BaseMessage
from mcp_use.agents import MCPAgent
from mcp_use.client import MCPClient
from langgraph.errors import GraphRecursionError

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """YOU ARE A PROACTIVE, HIGH-EXECUTION MULTI-TOOL AGENT.
1. **TOOL PRIORITY**: If you have been called, it's because tools are required. ALWAYS prioritize using tools over simple conversation.
2. **SELF-HEALING**: If a tool fails (e.g., missing parameters, invalid inputs), do not give up. Search for missing metadata or try an alternative tool/approach.
3. **AUTONOMOUS RESOLUTION**: Never ask the user for information (IDs, usernames, keys) if a listing or search tool can find it.
4. **LOOP PROTECTION**: If you repeat the same failing tool call 3 times, stop and explain the exact technical blocker to the user.
5. **EFFICIENCY**: Be concise. Only fetch the data you need. Do not over-scrape or over-crawl.
6. **STRICT TOOLING**: Never say "I can't interact with external tools". You ARE the interface to those tools. Use them to fulfill the user's request.
7. **ZOHO CLIQ RULES**:MANDATORY FIRST STEP (ALWAYS) ALWAYS call ONE of the following BEFORE any side-effect:
  - ZohoCliq_Get_Team_Members
  - ZohoCliq_Retrieve_all_direct_chats
"""

class Agent:
    """
    Orchestrates the MCPAgent execution with safety boundaries and history management.
    """
    
    def __init__(self, llm: Any, mcp_client: MCPClient):
        self.agent = MCPAgent(
            llm=llm,
            client=mcp_client,
            use_server_manager=False,
            max_steps=50, # Increased for complex 2.0 flows
            system_prompt=AGENT_SYSTEM_PROMPT
        )

    async def execute_streaming(self, user_input: str, history: List[BaseMessage]):
        """
        Executes the agent and yields events for real-time streaming using stream_events.
        """
        self.agent._conversation_history = history
        
        try:
            async for event in self.agent.stream_events(user_input):
                kind = event["event"]
                
                # 1. Handle raw tokens from Chat Model (v1 & v2 events)
                if kind in ["on_chat_model_stream", "on_llm_stream"]:
                    data = event.get("data", {})
                    chunk = data.get("chunk")
                    if chunk:
                        content = getattr(chunk, "content", chunk)
                        if content:
                            if isinstance(content, str):
                                yield content
                            elif isinstance(content, list):
                                for part in content:
                                    if isinstance(part, dict) and "text" in part:
                                        yield part["text"]
                                    elif isinstance(part, str):
                                        yield part
                
                # 2. Safety fallback for non-streaming models
                elif kind == "on_chat_model_end":
                    # If we missed tokens, the final result might be here
                    pass 

        except GraphRecursionError:
            yield {"event": "error", "message": "⚠️ Task too complex or loop detected."}
        except Exception as e:
            from src.core.mcp.manager import ApprovalRequiredError
            if isinstance(e, ApprovalRequiredError):
                # Yield a structured event for the UI to handle
                yield {
                    "event": "approval_required",
                    "tool_name": e.tool_name,
                    "tool_args": e.tool_args,
                    "message": e.message
                }
            else:
                logger.error(f"Streaming error: {e}")
                yield {"event": "error", "message": str(e)}

    async def execute(self, user_input: str, history: List[BaseMessage]) -> List[BaseMessage]:
        """
        Sync-like execution for compatibility.
        """
        self.agent._conversation_history = history
        try:
            await self.agent.run(user_input)
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            
        return self.agent.get_conversation_history()
