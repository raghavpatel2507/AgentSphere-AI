"""State management package for conversation persistence and memory."""

from langchain_core.messages import BaseMessage
from .thread_manager import (
    create_thread_id,
    parse_thread_id,
    get_or_create_session,
    save_current_session,
    load_current_session,
    clear_current_session,
    load_history,
    save_history,
)

__all__ = [
    "create_thread_id",
    "parse_thread_id",
    "get_or_create_session",
    "save_current_session",
    "load_current_session",
    "clear_current_session",
    "load_history",
    "save_history",
]
