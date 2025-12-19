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

    async def plan(self, user_input: str, history: List[BaseMessage], available_servers: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plans the task by determining needed servers or a direct response.
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
1. **COMMON KNOWLEDGE**: If the user asks for general information that an AI would reasonably know (e.g., historical facts, basic science, general "how-to"), RESPOND DIRECTLY. Do not use tools unless the user specifically asks for real-time or verified external data.
2. **TOOL NECESSITY**: Only select MCP servers for:
   - Real-time information (news, weather, stock prices).
   - External service interaction (GitHub, Gmail, Zoho, Drive, Notion).
   - Deep research requiring web crawling/scraping of specific websites.
3. If the user is just chatting (hello, how are you), respond directly.
4. Output MUST be valid JSON.

JSON FORMAT:
{{
  "response": "Your direct response if no tools needed, otherwise null",
  "servers": ["list", "of", "server", "names", "if", "tools", "needed"]
}}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"HISTORY:\n{self._format_history(history)}\n\nUSER QUERY: {user_input}"}
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = response.content
            # Basic JSON cleanup
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            plan_data = json.loads(content)
            return plan_data
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return {"response": "I encountered an error planning your task.", "servers": []}
