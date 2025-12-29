import logging
from typing import List, Optional, Any
from langchain_core.messages import BaseMessage
from langgraph.prebuilt import create_react_agent
from langgraph.errors import GraphRecursionError
from mcp_use.client import MCPClient

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """YOU ARE A PROACTIVE, HIGH-EXECUTION MULTI-TOOL AGENT.
1. **TOOL PRIORITY**: If you have been called, it's because tools are required. ALWAYS prioritize using tools over simple conversation.
2. **SELF-HEALING**: If a tool fails (e.g., missing parameters, invalid inputs), do not give up. Search for missing metadata or try an alternative tool/approach.
3. **AUTONOMOUS RESOLUTION**: Never ask the user for information (IDs, usernames, keys) if a listing or search tool can find it.
4. **LOOP PROTECTION**: If you repeat the same failing tool call 3 times, stop and explain the exact technical blocker to the user.
5. **EFFICIENCY**: Be concise. Only fetch the data you need. Do not over-scrape or over-crawl.
6. **STRICT TOOLING**: Never say "I can't interact with external tools". You ARE the interface to those tools. Use them to fulfill the user's request.
"""

class Agent:
    """
    Orchestrates the ReAct execution with safety boundaries and history management.
    """
    
    def __init__(self, llm: Any, mcp_client: MCPClient, tools: Optional[List[Any]] = None):
        self._tools = tools or []
        self._llm = llm
        self.agent = create_react_agent(
            model=llm,
            tools=self._tools,
            prompt=AGENT_SYSTEM_PROMPT
        )

    async def execute_streaming(self, user_input: str, history: List[BaseMessage]):
        """
        Executes the agent and yields structured events for real-time streaming.
        Uses LangGraph's astream_events for granular tracking.
        """
        try:
            config = {"configurable": {"thread_id": "temporary"}} # Not using checkpointer here for turn-based state
            
            async for event in self.agent.astream_events(
                {"messages": history + [("user", user_input)]}, 
                version="v2"
            ):
                kind = event["event"]
                
                # 1. Handle tokens from the model
                if kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk", {})
                    # Safe access to content
                    content = ""
                    if hasattr(chunk, "content"):
                        content = chunk.content
                    elif isinstance(chunk, str):
                        content = chunk
                    elif isinstance(chunk, dict):
                        content = chunk.get("content", "")
                        
                    if content:
                        yield {"type": "token", "content": content}
                
                # 2. Handle Tool Events
                elif kind == "on_tool_start":
                    yield {
                        "type": "tool_start",
                        "tool": event.get("name"),
                        "inputs": event.get("data", {}).get("input", {})
                    }
                
                elif kind == "on_tool_end":
                    yield {
                        "type": "tool_end",
                        "tool": event.get("name"),
                        "output": event.get("data", {}).get("output", "Done")
                    }
                
                # 3. Handle model end (for non-streaming or final capture)
                elif kind == "on_chat_model_end":
                    # Potentially useful for final checks
                    pass

        except GraphRecursionError:
            logger.error("GraphRecursionError encountered")
            yield {"type": "error", "content": "⚠️ Task too complex or loop detected."}
        except Exception as e:
            from src.core.mcp.manager import ApprovalRequiredError
            # Check for ApprovalRequiredError in the cause or the message
            # ReAct agent wraps errors
            err = e
            if hasattr(e, "__cause__") and isinstance(e.__cause__, ApprovalRequiredError):
                err = e.__cause__
            
            if isinstance(err, ApprovalRequiredError):
                yield {
                    "type": "approval_required",
                    "request_id": str(err.request_id) if hasattr(err, 'request_id') else None,
                    "tool_name": err.tool_name,
                    "tool_args": err.tool_args,
                    "message": err.message
                }
            else:
                import traceback
                logger.error(f"Streaming error: {e}\n{traceback.format_exc()}")
                yield {"type": "error", "content": f"Error: {str(e)}"}

    async def execute(self, user_input: str, history: List[BaseMessage]) -> List[BaseMessage]:
        """Legacy execution for compatibility."""
        result = await self.agent.ainvoke({"messages": history + [("user", user_input)]})
        return result["messages"]
