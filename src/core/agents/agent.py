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
        Executes the agent and yields events for streaming.
        """
        # Explicitly instruct the agent about available tools in this turn
        self.agent._conversation_history = history
        
        try:
            # MCPAgent.stream yields tokens or dictionaries
            async for chunk in self.agent.stream(user_input):
                # 1. Direct string (token)
                if isinstance(chunk, str):
                    yield chunk
                
                # 2. Dictionary (LangGraph event or result)
                elif isinstance(chunk, dict):
                    # Check for direct keys
                    found_content = False
                    for key in ["content", "text", "token", "delta"]:
                        if key in chunk and chunk[key]:
                            val = chunk[key]
                            if isinstance(val, str):
                                yield val
                                found_content = True
                            elif isinstance(val, dict) and "content" in val:
                                yield val["content"]
                                found_content = True
                    
                    if found_content:
                        continue

                    # Check for nested messages (LangGraph/LangChain style)
                    # If we find a full message at the end, we might have to simulate streaming
                    # if it wasn't already streamed.
                    if not found_content and "messages" in chunk:
                        msgs = chunk["messages"]
                        if isinstance(msgs, list) and len(msgs) > 0:
                            last_msg = msgs[-1]
                            if hasattr(last_msg, "content") and last_msg.content:
                                yield str(last_msg.content)
                
                # 3. LangChain Chunk object
                elif hasattr(chunk, "content"):
                    content = chunk.content
                    if isinstance(content, str):
                        yield content
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                yield item["text"]
                            elif isinstance(item, str):
                                yield item

        except GraphRecursionError:
            yield "⚠️ Task too complex or loop detected."
        except Exception as e:
            yield f"\n❌ Execution Error: {str(e)}"

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
