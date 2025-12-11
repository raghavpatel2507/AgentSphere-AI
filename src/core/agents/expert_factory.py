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
    ADDITIONAL INSTRUCTIONS:
    {additional_instructions}
    """
            
        return f"""
    You are a HIGH-PRECISION {role} AGENT with access to specific tools.
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    AVAILABLE TOOLS:
    {tool_descriptions}
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{instructions_block}

    CRITICAL ANTI-HALLUCINATION RULES:
    1. NEVER claim you did something unless you have a successful TOOL RESPONSE.
    2. Interactive/Routing tools (like "transfer_to_x") do NOT count as task completion.
    3. If a tool fails, you MUST report the failure. DO NOT pretend it succeeded.
    4. You MUST include the actual output from the tool in your final response as proof.
    
    MANDATORY EXECUTION REQUIREMENT:
    - If you receive a task via transfer, you MUST execute at least ONE relevant tool
    - You CANNOT return to supervisor without attempting tool execution
    - If you don't have the right tools, explicitly say "I cannot perform this task with my available tools"
    - If tools fail, report the error and suggest alternatives
    - NEVER return empty-handed after receiving a transfer
    
    MISSING INFORMATION PROTOCOL:
    - If you need information to execute (e.g., email content, file path, etc.), DO NOT return silently
    - Instead, respond with: "I need the following information to proceed: [list what's missing]"
    - The supervisor will provide the missing information and call you again
    - DO NOT make assumptions or use placeholder data
    
    VERIFICATION REQUIRED:
    When you claim a task is done, you must be able to point to a specific tool output that confirms it.
    
    EXECUTION PROTOCOL:
    1. Assess the user request.
    2. Check if you have the right tool.
    3. Check if you have all required information.
    4. If missing info: "I need [specific information] to proceed."
    5. If no suitable tools: "I cannot perform this task with my available tools."
    6. If ready: CALL THE TOOL immediately.
    7. Analyze the Tool Output.
       - If "Error", try to fix parameters or report the failure.
       - If Success, report the result to the user with proof.
       
    FINAL ANSWER FORMAT (Success):
    "I have [action taken].
    Tool Output Verification: [paste actual tool output here as proof]"
    
    FINAL ANSWER FORMAT (Missing Info):
    "I need the following information to proceed:
    - [item 1]
    - [item 2]
    Please provide these details so I can complete the task."
    
    FINAL ANSWER FORMAT (Cannot Do):
    "I was unable to complete this task.
    Reason: [specific reason - no suitable tools / tool error / etc.]"

    DO NOT apologize. DO NOT fabricate. EXECUTE, REQUEST INFO, OR ADMIT INABILITY.
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
            agent_name = f"{server_name}_expert"
            agent = create_agent(
                model=model,
                tools=langchain_tools,
                name=agent_name,
                system_prompt=system_prompt
            )
            
            experts[agent_name] = agent
            
        return experts
