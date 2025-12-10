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
    def create_expert_prompt(role: str, tools: List[Any], custom_template: Optional[str] = None) -> str:
        """Generate hardened system prompt for an expert agent."""

        tool_descriptions = "\n".join([f"- {t.name}: {t.description}" for t in tools])

        if custom_template:
            try:
                return custom_template.format(expert_role=role, tools=tool_descriptions)
            except (IndexError, KeyError, ValueError):
                # Fallback if template has issues (e.g. unescaped braces or missing keys)
                # We return the raw template to avoid crashing, though tools might be missing.
                return custom_template
            
        return f"""
    You are a HIGH-PRECISION {role} AGENT with access to specific tools.
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    AVAILABLE TOOLS:
    {tool_descriptions}
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    CRITICAL ANTI-HALLUCINATION RULES:
    1. NEVER claim you did something unless you have a successful TOOL RESPONSE.
    2. Interactive/Routing tools (like "transfer_to_x") do NOT count as task completion.
    3. If a tool fails, you MUST report the failure. DO NOT pretend it succeeded.
    4. You MUST include the actual output from the tool in your final response as proof.
    
    VERIFICATION REQUIRED:
    When you claim a task is done, you must be able to point to a specific tool output that confirms it.
    
    EXECUTION PROTOCOL:
    1. Assess the user request.
    2. Check if you have the right tool.
    3. If yes, CALL THE TOOL.
    4. If no, or if you need another expert, use a routing tool or reply with "I cannot perform this."
    5. Analyze the Tool Output.
       - If "Error", try to fix parameters or fallback.
       - If Success, report the result to the user.
       
    FINAL ANSWER FORMAT:
    "I have [action taken].
    Tool Output Verification: [paste brief summary of tool output here]"
    
    DO NOT apologize. DO NOT fabricate. EXECUTE.
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
            custom_prompt = server.get("custom_prompt")
            
            # Get tools for this server (now returns LangChain Tools)
            langchain_tools = await manager.get_tools_for_server(server_name)
            
            if not langchain_tools:
                continue
            
            # Generate prompt
            system_prompt = ExpertFactory.create_expert_prompt(
                role=expert_role,
                tools=langchain_tools,
                custom_template=custom_prompt or expert_template
            )
            
            # Create agent
            agent_name = f"{server_name}_expert"
            agent = create_agent(
                model=model,
                tools=langchain_tools,
                name=agent_name,
                system_prompt=system_prompt
            )
            
            experts[agent_name] = agent
            
        return experts
