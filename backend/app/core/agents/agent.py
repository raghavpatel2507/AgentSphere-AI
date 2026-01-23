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

# AGENT_SYSTEM_PROMPT = """YOU ARE A PROACTIVE, HIGH-EXECUTION MULTI-TOOL AGENT.
# 1. **TOOL PRIORITY**: If you have been called, it's because tools are required. ALWAYS prioritize using tools over simple conversation.
# 2. **SELF-HEALING**: If a tool fails (e.g., missing parameters, invalid inputs), do not give up. Search for missing metadata or try an alternative tool/approach.
# 3. **AUTONOMOUS RESOLUTION**: Never ask the user for information (IDs, usernames, keys) if a listing or search tool can find it.
# 4. **LOOP PROTECTION**: If you repeat the same failing tool call 3 times, stop and explain the exact technical blocker to the user.
# 5. **EFFICIENCY**: Be concise. Only fetch the data you need. Do not over-scrape or over-crawl.
# 6. **STRICT TOOLING**: Never say "I can't interact with external tools". You ARE the interface to those tools. Use them to fulfill the user's request.
# 7. **CONTEXT AWARENESS**: You HAVE access to the history of this conversation. Use it to maintain context and answer questions about previous turns.
# """

AGENT_SYSTEM_PROMPT = """YOU ARE A TOOL-GROUNDED, HALLUCINATION-SAFE AUTONOMOUS AGENT.

========================
CORE PRINCIPLES
========================

1. PARAMETER CLASSIFICATION
Tool parameters fall into TWO categories:

A) IDENTIFIERS (STRICT)
- System-defined, opaque, exact-match values
- Examples: chat_id, user_id, repo_id, issue_id, message_id
- IDENTIFIERS MUST come ONLY from:
  1. Explicit user-provided identifiers, OR
  2. Tool responses (search/list/lookup)
- IDENTIFIERS MUST NEVER be guessed, inferred, formatted, or defaulted

B) SEMANTIC PARAMETERS (FLEXIBLE)
- Human-language, descriptive values
- Examples: city, country, query, topic, date, language, message text
- SEMANTIC parameters MAY be:
  - Inferred from user intent
  - Normalized (e.g., "Delhi" → "New Delhi")
  - Defaulted when reasonable

Natural-language names (people, teams, projects) are NOT identifiers.

========================
EXECUTION MODEL (STRICT)
========================

PHASE 1 — INTENT
- Understand what the user wants to achieve

PHASE 2 — REQUIREMENTS
- Identify which parameters are required
- Classify each parameter as IDENTIFIER or SEMANTIC

PHASE 3 — DISCOVERY (IDENTIFIERS ONLY)
- If an IDENTIFIER is missing:
  - Use available tools to search/list/lookup
  - Extract the identifier EXACTLY as returned
- If no tool can retrieve it:
  - Stop and explain what is missing

PHASE 4 — ACTION
- Call action tools ONLY after all IDENTIFIERS are resolved
- SEMANTIC parameters may be inferred or defaulted

PHASE 5 — VERIFICATION
- Claim success ONLY if the tool response explicitly confirms success
- Never assume an action succeeded

========================
AUTONOMY RULES
========================

- If a required parameter can be discovered via tools:
  - DO NOT ask the user for it
- Ask the user ONLY when:
  - No tool exists to retrieve the missing IDENTIFIER

- If a semantic default or inference is used:
  - Clearly state the assumption in the response

- If a tool fails repeatedly (3 times with same issue):
  - Stop and explain the exact technical blocker

========================
FORBIDDEN BEHAVIOR
========================

- Inventing or guessing identifiers
- Reusing example IDs or placeholders
- Deriving IDs from names or patterns
- Claiming success without tool confirmation

========================
FUNDAMENTAL RULE
========================

NO IDENTIFIER → NO ACTION
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
                    # Check for interrupts/approval
                    action_event = self._extract_action_info(chunk)
                    if action_event:
                        yield action_event
                        return
                    
                    # Yield tool start/end events from node updates
                    # chunk is usually {node_name: {messages: [...]}}
                    for node_name, data in chunk.items():
                        if not isinstance(data, dict) or "messages" not in data:
                            continue
                            
                        for msg in data["messages"]:
                            # Tool start: AIMessage has tool_calls
                            if isinstance(msg, AIMessage) and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    yield {
                                        "type": "tool_start",
                                        "tool": tc["name"],
                                        "inputs": tc["args"]
                                    }
                            
                            # Tool end: ToolMessage has the output
                            elif isinstance(msg, ToolMessage):
                                yield {
                                    "type": "tool_end",
                                    "tool": msg.name,
                                    "output": str(msg.content)
                                }
                    
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
            # --- RECONCILIATION: Handle mismatch between user decisions and pending tool calls ---
            # If we have 2 pending calls but user only approved 1, we must provide 2 results
            # to prevent "ValueError: mismatch" in HumanInTheLoopMiddleware.
            
            # 1. Fetch current state to see what's pending
            current_state = await self.agent.aget_state(config)
            
            reconciled_decisions = decisions
            
            if current_state and current_state.tasks:
                # Find the interrupt value
                interrupt_val = None
                for task in current_state.tasks:
                    if task.interrupts:
                        interrupt_val = task.interrupts[0].value
                        break
                
                if interrupt_val:
                    pending_requests = interrupt_val.get("action_requests", [])
                    
                    if len(pending_requests) > len(decisions):
                        logger.warning(
                            f"HITL Decision Mismatch: Pending {len(pending_requests)} requests, "
                            f"received {len(decisions)} decisions. Reconciling..."
                        )
                        
                        # We need valid decisions for ALL pending requests.
                        # Strategy: Match the ones we have, "soft reject" the others to queue them.
                        
                        new_decisions = []
                        used_indices = set()
                        
                        # match provided decisions to requests if possible
                        # (Since we don't have IDs easily, we assume the frontend sends the "first" one.
                        #  Better approach: strict order or fuzzy matching.
                        #  For now: Use the decisions for the first N requests, soft-reject the rest.)
                        
                        for i in range(len(pending_requests)):
                            if i < len(decisions):
                                new_decisions.append(decisions[i])
                            else:
                                # Create a "soft reject" for the unaddressed tool call
                                # This tells the agent: "This tool didn't fail, but we are waiting to run it."
                                # The agent's loop should then pick it up again in the next step.
                                req = pending_requests[i]
                                tool_name = req.get("name", "tool")
                                
                                new_decisions.append({
                                    "type": "reject",
                                    "message": f"Sequential processing: Action '{tool_name}' queued. Please retry after current action completes."
                                })
                        
                        reconciled_decisions = new_decisions

            async for mode, chunk in self.agent.astream(
                Command(resume={"decisions": reconciled_decisions}),
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
                        
                    # Yield tool start/end events from node updates
                    for node_name, data in chunk.items():
                        if not isinstance(data, dict) or "messages" not in data:
                            continue
                            
                        for msg in data["messages"]:
                            if isinstance(msg, AIMessage) and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    yield {
                                        "type": "tool_start",
                                        "tool": tc["name"],
                                        "inputs": tc["args"]
                                    }
                            elif isinstance(msg, ToolMessage):
                                yield {
                                    "type": "tool_end",
                                    "tool": msg.name,
                                    "output": str(msg.content)
                                }
                            
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

