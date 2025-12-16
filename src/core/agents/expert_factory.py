from typing import List, Dict, Any, Optional, Type
from langchain.agents import create_agent
from langchain_core.tools import Tool, StructuredTool
from langchain_core.language_models import BaseChatModel
from src.core.mcp.manager import MCPManager
from pydantic import create_model, Field, BaseModel

class ExpertFactory:
    """
    Factory for creating dynamic expert agents from MCP tools.
    """
    
    @staticmethod
    def create_expert_prompt(role: str, tools: List[Any], additional_instructions: Optional[str] = None) -> str:
        """Generate hardened system prompt for an expert agent."""

        tool_descriptions = "\n".join([f"- {t.name}: {t.description}" for t in tools])

        instructions_block = ""
        if additional_instructions:
            instructions_block = f"""
### 🛡️ STRICT CAPABILITIES & LIMITATIONS
{additional_instructions}
(You must STRICTLY adhere to these limitations. Do NOT attempt actions outside this scope.)
"""
            
        return f"""You are the **{role}**.
You are a specialized agent with access to a specific set of tools.

### 🛠️ YOUR AVAILABLE TOOLS
{tool_descriptions}

{instructions_block}

### 🎯 YOUR MISSION
1. **Receive Task**: Read the user's input carefully.
2. **Select Tool**: Choose the *exact* tool from your list that solves the problem.
3. **Execute**: Call the tool with the correct arguments.
4. **Report**: Return the tool's output clearly.

### ⛔ CRITICAL RULES (READ CAREFULLY)
1. **NO HALLUCINATION**: You can ONLY use the tools listed above.
   - **NEVER** say you did something if you didn't use a tool.
   - **NEVER** return a success message like "Email sent" or "File created" unless you actually called the tool and got a success response.
2. **PARTIAL EXECUTION & SCOPE**:
   - You may receive a complex request containing tasks for OTHER agents (e.g., "Search YouTube AND send email").
   - **YOUR JOB**: Identify the part that YOU can do (e.g., "Search YouTube") and **DO IT**.
   - **SILENT IGNORE**: **COMPLETELY IGNORE** the parts you cannot do.
     - **DO NOT** mention them in your final response.
     - **DO NOT** say "I cannot send email".
     - **DO NOT** say "Please ask another agent".
     - **JUST PROVIDE YOUR RESULT.**
   - If the request has NOTHING you can do, then say "I cannot perform this action."
3. **TOOL FIRST**: Your FIRST action should almost always be a tool call. Do not explain what you are going to do, just do it.
4. **ONE TASK AND STOP**: You are assigned a SINGLE, ISOLATED task.
   - **DO NOT** attempt to do the "next step".
   - **DO NOT** ask "what should I do next?".
   - **JUST DO THE TASK AND STOP.**

### 🧠 THOUGHT PROCESS
When you receive a task:
1. **Filter**: "Which part of this request matches my tools?"
2. **Execute**: Call the tool for THAT part immediately.
3. **Ignore**: Disregard the rest of the request silently.
4. **Report**: Return **ONLY** the output of your tool. Do not mention what you didn't do.
5. **ALWAYS RETURN TEXT**: You MUST provide a text response summarizing the tool result. DO NOT return an empty string.
6. **STOP**: Do not do anything else.

### out_of_character
You are a function-calling engine. You are not a conversationalist. Your primary mode of interaction is calling tools.
"""


    @staticmethod
    async def create_all_experts(model: BaseChatModel) -> Dict[str, Any]:
        """
        Create all enabled expert agents based on MCP configuration.
        Returns a dictionary of agent_name -> agent_instance.
        """
        manager = MCPManager()
        # Initialize manager if not already done (it should be though)
        if not manager._initialized:
             # Just in case
             pass
        
        # We need to await initialization if we are running fresh here
        # But create_all_experts is usually called after main.py logic
        # However, main.py calls manager.initialize() then get_dynamic_agents() which calls this.
        
        config = manager.load_config()
        experts = {}
        
        # Get global expert settings
        dynamic_settings = config.get("dynamic_experts", {})
        if not dynamic_settings.get("enabled", True):
            return {}
            
        expert_template = dynamic_settings.get("expert_template")
        
        # Iterate through enabled servers
        for server in config.get("mcp_servers", []):
            if not server.get("enabled", False):
                continue
                
            server_name = server.get("name")
            expert_role = server.get("expert_role", f"{server_name} specialist")
            additional_instructions = server.get("additional_instructions")
            
            # Get tools for this server (now returns LangChain Tools)
            langchain_tools = await manager.get_tools_for_server(server_name)
            
            if not langchain_tools:
                continue
            
            # Generate prompt
            system_prompt = ExpertFactory.create_expert_prompt(
                role=expert_role,
                tools=langchain_tools,
                additional_instructions=additional_instructions
            )
            
            # Create agent
            safe_server_name = server_name.replace("-", "_")
            agent_name = f"{safe_server_name}_expert"
            agent = create_agent(
                model=model,
                tools=langchain_tools,
                name=agent_name,
                system_prompt=system_prompt
            )
            
            experts[agent_name] = agent
            
        return experts
