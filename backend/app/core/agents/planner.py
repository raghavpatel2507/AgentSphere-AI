import json
import logging
from typing import Dict, List, Any, Union, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

logger = logging.getLogger(__name__)

class Planner:
    """
    The 'Brain' of the system. Implements a Single-Call Router logic.
    Decides if the user's query requires tools (MCP servers) or can be answered directly.
    """
    
    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        # Use centralized LLMFactory
        from backend.app.core.llm.provider import LLMFactory
        self.llm = LLMFactory.load_config_and_create_llm()
        
        # Apply overrides if provided
        if model_name:
             if hasattr(self.llm, 'model_name'):
                self.llm.model_name = model_name
             elif hasattr(self.llm, 'model'):
                self.llm.model = model_name
        
        # Note: api_key is currently handled via .env and LLMFactory
        # but we keep it in the signature to avoid breaking callers.

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
4. **HISTORY ACCESS**: You HAVE access to the history of this specific conversation. Use it to answer questions about previous turns. Never say "I don't have access to your chat history" for messages visible in the HISTORY block.
5. Output MUST be valid JSON.
6. **STRICT EXCLUSIVITY**: If `servers` is not empty, `response` MUST be `null`. Never provide a preamble like "I will help you...". Just select the server and let the agent handle everything.

JSON FORMAT:
{{
  "response": "Brief direct response or null",
  "servers": ["list", "of", "server", "names", "if", "tools", "needed"]
}}
"""
        # Filter history to avoid duplicating the current query if it's already saved
        display_history = history
        if history and hasattr(history[-1], 'content') and history[-1].content == user_input:
            display_history = history[:-1]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"HISTORY:\n{self._format_history(display_history)}\n\nUSER QUERY: {user_input}"}
        ]

        full_content = ""
        yielded_len = 0
        response_started = False
        response_processed = False
        start_char_idx = -1
        
        try:
            async for chunk in self.llm.astream(messages):
                content = chunk.content
                if not content: continue
                full_content += content
                
                if not response_processed:
                    if not response_started:
                        # 1. Search for "response": field
                        if '"response":' in full_content:
                            p_idx = full_content.find('"response":') + 11
                            # Look ahead for opening quote or null
                            after_field = full_content[p_idx:].lstrip()
                            if after_field:
                                if after_field.startswith('"'):
                                    response_started = True
                                    # start_char_idx is first char INSIDE the quotes
                                    start_char_idx = full_content.find('"', p_idx) + 1
                                    yielded_len = start_char_idx
                                elif after_field.startswith('n'): # null
                                    if "null" in after_field:
                                        response_processed = True
                    
                    if response_started and not response_processed:
                        # 2. Extract tokens from the string, respecting escapes
                        to_yield = ""
                        curr_idx = yielded_len
                        
                        while curr_idx < len(full_content):
                            c = full_content[curr_idx]
                            
                            if c == '\\':
                                # Check if we have the escaped character yet
                                if curr_idx + 1 < len(full_content):
                                    esc = full_content[curr_idx + 1]
                                    if esc == '"': to_yield += '"'
                                    elif esc == 'n': to_yield += '\n'
                                    elif esc == 'r': to_yield += '\r'
                                    elif esc == 't': to_yield += '\t'
                                    elif esc == '\\': to_yield += '\\'
                                    else: to_yield += esc # literal fallback
                                    curr_idx += 2
                                    continue
                                else:
                                    # Trailing backslash, wait for next chunk
                                    break
                            
                            if c == '"':
                                # Terminator found
                                response_processed = True
                                break
                            
                            to_yield += c
                            curr_idx += 1
                        
                        if to_yield:
                            yield to_yield
                            yielded_len = curr_idx

            # Final cleanup and JSON parsing
            clean_content = full_content.strip()
            
            # 1. Handle Markdown code blocks
            if "```json" in clean_content:
                clean_content = clean_content.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_content:
                # Find the first and last triple backticks
                parts = clean_content.split("```")
                if len(parts) >= 3:
                    clean_content = parts[1].strip()
            
            # 2. Heuristic: locate first '{' and last '}'
            if not clean_content.startswith("{"):
                start_idx = clean_content.find("{")
                end_idx = clean_content.rfind("}")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    clean_content = clean_content[start_idx:end_idx+1]
            
            try:
                plan_data = json.loads(clean_content)
                yield plan_data
            except Exception:
                # One more try: strip common problematic chars
                try:
                    # Remove potential leading/trailing garbage
                    sanitized = clean_content.strip().lstrip('`').rstrip('`').strip()
                    plan_data = json.loads(sanitized)
                    yield plan_data
                except:
                    yield {"response": full_content, "servers": []}
                
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            yield {"response": "I encountered an error planning your task.", "servers": []}

