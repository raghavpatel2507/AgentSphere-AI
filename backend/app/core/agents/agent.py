"""
Agent module with LangChain's built-in HITL middleware.

Uses HumanInTheLoopMiddleware + AsyncPostgresSaver for true pause-and-resume.
No custom error handling or approval middleware needed.
"""

import logging
import fnmatch
from typing import List, Optional, Any, Dict, AsyncGenerator
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import Command
from langgraph.errors import GraphRecursionError

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """YOU ARE A PROACTIVE, HIGH-EXECUTION MULTI-TOOL AGENT.
1. **TOOL PRIORITY**: If you have been called, it's because tools are required. ALWAYS prioritize using tools over simple conversation.
2. **SELF-HEALING**: If a tool fails (e.g., missing parameters, invalid inputs), do not give up. Search for missing metadata or try an alternative tool/approach.
3. **AUTONOMOUS RESOLUTION**: Never ask the user for information (IDs, usernames, keys) if a listing or search tool can find it.
4. **LOOP PROTECTION**: If you repeat the same failing tool call 3 times, stop and explain the exact technical blocker to the user.
5. **EFFICIENCY**: Be concise. Only fetch the data you need. Do not over-scrape or over-crawl.
6. **STRICT TOOLING**: Never say "I can't interact with external tools". You ARE the interface to those tools. Use them to fulfill the user's request.
7. **CONTEXT AWARENESS**: You HAVE access to the history of this conversation. Use it to maintain context and answer questions about previous turns.
"""


class Agent:
    """
    Orchestrates ReAct execution with LangChain's built-in HITL middleware.
    
    Uses checkpointer for true pause-and-resume - no re-running planning
    or re-executing previous steps after approval.
    """
    
    def __init__(
        self, 
        llm: Any, 
        tools: List[Any],
        checkpointer: Any,
        hitl_config: Optional[Dict[str, Any]] = None
    ):
        self._tools = tools
        self._llm = llm
        self._checkpointer = checkpointer
        
        # Build interrupt_on config from user's HITL glob patterns
        interrupt_on = self._build_interrupt_config(hitl_config, tools)
        
        # Create agent with built-in HITL middleware
        self.agent = create_agent(
            model=llm,
            tools=self._tools,
            system_prompt=AGENT_SYSTEM_PROMPT,
            middleware=[
                HumanInTheLoopMiddleware(
                    interrupt_on=interrupt_on,
                    description_prefix="Tool execution pending approval",
                ),
            ] if interrupt_on else [],  # No middleware if no tools need approval
            checkpointer=checkpointer,
        )
        
        logger.info(f"Agent created with {len(tools)} tools, HITL patterns: {list(interrupt_on.keys()) if interrupt_on else 'none'}")
    
    def _build_interrupt_config(
        self, 
        hitl_config: Optional[Dict[str, Any]], 
        tools: List[Any]
    ) -> Dict[str, bool]:
        """
        Convert user's glob patterns to LangChain's interrupt_on format.
        
        User config: {"enabled": true, "mode": "denylist", "sensitive_tools": ["*delete*", "*write*"]}
        Output: {"delete_file": True, "write_data": True, "read_file": False}
        """
        if not hitl_config or not hitl_config.get("enabled", False):
            return {}
        
        mode = hitl_config.get("mode", "denylist")
        patterns = hitl_config.get("sensitive_tools", [])
        
        interrupt_on = {}
        
        for tool in tools:
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            
            if mode == "allowlist":
                # In allowlist mode, everything needs approval by default
                interrupt_on[tool_name] = True
            else:
                # In denylist mode, check against glob patterns
                needs_approval = any(
                    fnmatch.fnmatch(tool_name, pattern) 
                    for pattern in patterns
                )
                if needs_approval:
                    interrupt_on[tool_name] = True
        
        return interrupt_on

    async def execute_streaming(
        self, 
        user_input: str, 
        history: List[BaseMessage],
        thread_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute agent and yield structured events.
        
        If a tool needs HITL approval, yields an 'approval_required' event
        with all the info the frontend needs.
        
        Args:
            user_input: The user's message
            history: Previous messages
            thread_id: Unique identifier for this conversation
            
        Yields:
            Events: token, tool_start, tool_end, approval_required, error
        """
        try:
            # Prepare messages
            messages = history.copy()
            
            # Avoid duplicating last user message if it's already in history
            last_content = None
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, 'content'):
                    last_content = last_msg.content
                elif isinstance(last_msg, tuple) and len(last_msg) > 1:
                    last_content = last_msg[1]
            
            if last_content != user_input:
                messages.append(("user", user_input))
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # --- SELF-HEALING: Check for dangling tool calls ---
            current_state = await self.agent.aget_state(config)
            if current_state and current_state.values and "messages" in current_state.values:
                state_messages = current_state.values["messages"]
                if state_messages and isinstance(state_messages[-1], AIMessage) and state_messages[-1].tool_calls:
                    logger.warning(f"Found dangling tool calls in thread {thread_id}. Attempting repair...")
                    tool_outputs = []
                    for tc in state_messages[-1].tool_calls:
                        tool_outputs.append(
                            ToolMessage(
                                tool_call_id=tc["id"],
                                content="Error: Execution interrupted or resumed without result. Please retry.",
                                name=tc["name"]
                            )
                        )
                    # Inject repair messages
                    await self.agent.aupdate_state(config, {"messages": tool_outputs}, as_node="tools")
            
            async for mode, chunk in self.agent.astream(
                {"messages": messages},
                config=config,
                stream_mode=["updates", "messages"],
            ):
                if mode == "messages":
                    token, metadata = chunk
                    if not isinstance(token, ToolMessage) and hasattr(token, 'content') and token.content:
                        yield {"type": "token", "content": token.content}
                
                elif mode == "updates":
                    action_event = self._extract_action_info(chunk)
                    if action_event:
                        yield action_event
                        return
                    
                    # Tool start/end events (if available in updates)
                    # Note: The exact structure depends on LangChain version
                    
        except GraphRecursionError:
            logger.error("GraphRecursionError - task too complex")
            yield {"type": "error", "content": "⚠️ Task too complex or loop detected."}
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield {"type": "error", "content": f"Error: {str(e)}"}

    async def resume_streaming(
        self,
        thread_id: str,
        decisions: List[Dict[str, Any]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Resume execution after HITL approval.
        
        Uses the checkpointer to continue from the exact point where
        we interrupted. No re-planning, no re-executing previous steps.
        
        Args:
            thread_id: Same thread_id used in execute_streaming
            decisions: List of decisions, e.g. [{"type": "approve"}]
                      or [{"type": "edit", "edited_action": {"name": "...", "args": {...}}}]
                      or [{"type": "reject", "message": "reason"}]
                      
        Yields:
            Events: token, tool_start, tool_end, approval_required (if chained), error
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            async for mode, chunk in self.agent.astream(
                Command(resume={"decisions": decisions}),
                config=config,
                stream_mode=["updates", "messages"],
            ):
                if mode == "messages":
                    token, metadata = chunk
                    # Check if it's a ToolMessage or just text content
                    if not isinstance(token, ToolMessage) and hasattr(token, 'content') and token.content:
                        yield {"type": "token", "content": token.content}
                
                elif mode == "updates":
                    # Check for another interrupt (chained approvals)
                    action_event = self._extract_action_info(chunk)
                    if action_event:
                        yield action_event
                        return
                            
        except Exception as e:
            logger.error(f"Resume error: {e}", exc_info=True)
            yield {"type": "error", "content": f"Resume error: {str(e)}"}

    async def get_pending_interrupt(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if there's a pending interrupt for this thread.
        
        Useful when user refreshes the page - we can check if there's
        an approval waiting and show the ApprovalCard.
        
        Returns:
            Interrupt info if pending, None otherwise
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            state = await self.agent.aget_state(config)
            
            # Check for pending interrupts in tasks
            if state and state.tasks:
                for task in state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        interrupt_val = task.interrupts[0].value
                        requests = interrupt_val.get("action_requests", [])
                        if requests:
                            r = requests[0]
                            args = r.get("arguments") or r.get("args") or r.get("inputs") or {}
                            return {
                                "tool_name": r.get("name"),
                                "tool_args": args,
                                "description": r.get("description") or "Action requires approval",
                            }
            return None
        except Exception as e:
            logger.warning(f"Error checking pending interrupt: {e}")
            return None

    def _extract_action_info(self, chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Helper to extract action info from a LangGraph interrupt chunk."""
        if "__interrupt__" in chunk:
            interrupt = chunk["__interrupt__"][0]
            val = interrupt.value
            requests = val.get("action_requests", [])
            if requests:
                r = requests[0]
                # Robust extract: check multiple common keys
                args = r.get("arguments") or r.get("args") or r.get("inputs") or {}
                return {
                    "type": "approval_required",
                    "tool_name": r.get("name"),
                    "tool_args": args,
                    "description": r.get("description") or "Action requires approval",
                    "allowed_decisions": ["approve", "reject", "edit"]
                }
        return None

