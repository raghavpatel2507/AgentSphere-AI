import json
import logging
from typing import Dict, List, Any, Union, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

class Planner:
    """
    The 'Brain' of the system. Implements a Single-Call Router logic.
    Decides if the user's query requires tools (MCP servers) or can be answered directly.
    """
    
    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        # Use centralized LLMFactory
        from src.core.llm.provider import LLMFactory
        self.llm = LLMFactory.load_config_and_create_llm()
        if model_name:
            # Override if specifically provided
             self.llm.model_name = model_name

    def _format_history(self, history: List[BaseMessage]) -> str:
        formatted = []
        for msg in history:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            formatted.append(f"{role}: {msg.content}")
        return "\n".join(formatted)

    async def plan(self, user_input: str, history: List[BaseMessage], available_servers: Dict[str, Any]):
        """
        Plans the task and yields either tokens (for direct response) or the final plan dict.
        """
        # Enhanced Server Descriptions
        known_capabilities = {
            "github": "Access repositories, issues, PRs, and files on GitHub.",
            "zoho": "Integration with Zoho suite. Use for Zoho Mail and Zoho Cliq (messaging, teams, user lookup).",
            "filesystem": "Read/write/list local files.",
            "firecrawl-mcp": "Web scraping and crawling (single or multi-page).",
            "playwright-mcp": "Browser automation for dynamic sites.",
            "youtube": "Search videos and get transcripts.",
            "gmail": "Send, read, and search emails.",
            "notion": "Interact with Notion pages and databases.",
            "google-drive": "Manage Google Drive files."
        }
        
        server_descriptions = []
        for name, info in available_servers.items():
            desc = info.get('description') or known_capabilities.get(name, 'No description available')
            server_descriptions.append(f"- {name}: {desc}")
        server_text = "\n".join(server_descriptions)

        system_prompt = f"""You are the Task Router for AgentSphere-AI.
Analyze the user query and history to decide if you need tools (MCP servers) or can respond directly.

AVAILABLE MCP SERVERS:
{server_text}

RULES:
1. **COMMON KNOWLEDGE**: Respond directly for general info.
2. **TOOL NECESSITY**: Only select MCP servers for real-time/external data.
3. If the user is just chatting, respond directly.
4. Output MUST be valid JSON.

JSON FORMAT:
{{
  "response": "Brief direct response or null",
  "servers": ["list", "of", "server", "names", "if", "tools", "needed"]
}}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"HISTORY:\n{self._format_history(history)}\n\nUSER QUERY: {user_input}"}
        ]

        full_content = ""
        response_started = False
        response_processed = False
        
        try:
            async for chunk in self.llm.astream(messages):
                content = chunk.content
                if not content: continue
                full_content += content
                
                if not response_processed:
                    if not response_started:
                        # Find "response": but ensure it's a field name, then look for the value's opening quote
                        pattern = '"response":'
                        if pattern in full_content:
                            p_idx = full_content.find(pattern)
                            # Check everything AFTER the pattern
                            after_p = full_content[p_idx + len(pattern):]
                            
                            # Trim leading whitespace to see what the value looks like
                            stripped_after = after_p.lstrip()
                            if stripped_after.startswith('"'):
                                # It's a string!
                                response_started = True
                                # Find where the actual value starts in the CURRENT chunk
                                start_quote_global_pos = full_content.find('"', p_idx + len(pattern))
                                start_val_global_pos = start_quote_global_pos + 1
                                
                                pre_chunk_len = len(full_content) - len(content)
                                if start_val_global_pos < len(full_content):
                                    take_from_chunk = max(0, start_val_global_pos - pre_chunk_len)
                                    val_part = content[take_from_chunk:]
                                    if '"' in val_part:
                                        # Whole small response in one chunk?
                                        msg, _ = val_part.split('"', 1)
                                        if msg: yield msg
                                        response_started = False
                                        response_processed = True
                                    elif val_part:
                                        yield val_part
                            elif stripped_after.startswith('n'): # "null"
                                # It's null, skip streaming
                                if len(stripped_after) >= 4: # fully "null"
                                    response_processed = True
                    else:
                        # Already streaming, look for closing quote
                        if '"' in content:
                            msg, _ = content.split('"', 1)
                            if msg: yield msg
                            response_started = False
                            response_processed = True
                        else:
                            yield content

            # Final cleanup and JSON parsing
            clean_content = full_content
            if "```json" in clean_content:
                clean_content = clean_content.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_content:
                clean_content = clean_content.split("```")[1].split("```")[0].strip()
            
            try:
                plan_data = json.loads(clean_content)
                yield plan_data
            except Exception:
                yield {"response": full_content, "servers": []}
                
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            yield {"response": "I encountered an error planning your task.", "servers": []}
