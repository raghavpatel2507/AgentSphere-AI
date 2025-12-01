"""
Custom checkpointer wrapper that filters out Gemini signatures before saving.
"""
from typing import Any, Dict, Optional, Sequence
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import BaseMessage, AIMessage
import copy


class FilteredAsyncPostgresSaver(AsyncPostgresSaver):
    """
    Custom PostgreSQL checkpointer that filters out unnecessary data before saving.
    
    Specifically removes:
    - Gemini signatures from AI message extras (saves space)
    - Other provider-specific metadata that isn't needed for conversation history
    """
    
    @staticmethod
    def _filter_message(message: BaseMessage) -> BaseMessage:
        """
        Filter out unnecessary data from a message before saving.
        
        Args:
            message: The message to filter
            
        Returns:
            Filtered copy of the message
        """
        # Create a copy to avoid modifying the original
        filtered_msg = copy.deepcopy(message)
        
        # For AI messages, remove signature from extras
        if isinstance(filtered_msg, AIMessage):
            # Check if message has content as list with extras
            if isinstance(filtered_msg.content, list):
                for item in filtered_msg.content:
                    if isinstance(item, dict) and 'extras' in item:
                        # Remove signature if present
                        if 'signature' in item['extras']:
                            del item['extras']['signature']
                        # If extras is now empty, remove it
                        if not item['extras']:
                            del item['extras']
        
        return filtered_msg
    
    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Dict[str, Any],
        metadata: Dict[str, Any],
        new_versions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Save checkpoint with filtered messages.
        
        Overrides the parent aput method to filter messages before saving.
        """
        # Filter messages in the checkpoint
        if 'channel_values' in checkpoint and 'messages' in checkpoint['channel_values']:
            messages = checkpoint['channel_values']['messages']
            if isinstance(messages, list):
                checkpoint['channel_values']['messages'] = [
                    self._filter_message(msg) if isinstance(msg, BaseMessage) else msg
                    for msg in messages
                ]
        
        # Call parent implementation with filtered checkpoint
        return await super().aput(config, checkpoint, metadata, new_versions)
