from langchain_core.callbacks import BaseCallbackHandler
from typing import Any, Dict, List, Optional, Union
from langchain_core.messages import BaseMessage

class AgentCallbackHandler(BaseCallbackHandler):
    """Callback Handler that prints to std out."""

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Print out that we are entering a chain."""
        pass

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Print out that we finished a chain."""
        pass

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """Print out the usage of a tool."""
        tool_name = serialized.get('name')
        if "transfer" in tool_name.lower():
             print(f"\n\033[1;34m🔄 Transferring task to {tool_name.replace('transfer_to_', '').replace('_', ' ')}...\033[0m")
        else:
             print(f"\n\033[1;33m🛠️  Running tool: {tool_name}...\033[0m")
             print(f"\033[37m   Input: {input_str}\033[0m")

    def on_tool_end(
        self,
        output: str,
        color: Optional[str] = None,
        observation_prefix: Optional[str] = None,
        llm_prefix: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """If not the final action, print out observation."""
        if "Command(" in str(output):
            print(f"\033[1;32m✅ Process Completed\033[0m\n")
        else:
            print(f"\033[1;32m✅ Output: {output}\033[0m\n")

    def on_tool_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> None:
        """Handle tool errors, but suppress interrupt errors (expected for HITL)."""
        # Check if this is an interrupt error (expected for HITL approval)
        error_str = str(error)
        error_type = type(error).__name__
        
        if "Interrupt" in error_type or ("Interrupt" in error_str and "tool_approval_required" in error_str):
            # This is an expected interrupt for HITL approval, don't show as error
            print(f"\033[1;33m⏸️  Waiting for approval...\033[0m\n")
        else:
            # Real error, show it
            print(f"\033[1;31m❌ Error: {error}\033[0m\n")

    def on_text(self, text: str, **kwargs: Any) -> None:
        """Run on arbitrary text."""
        pass

    def on_agent_action(self, action: Any, **kwargs: Any) -> Any:
        """Run on agent action."""
        pass

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> Any:
        """Run on agent end."""
        pass
