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
    You are a HIGH-PRECISION {role} expert.
    You MUST use your tools to complete tasks.
    You MUST return a structured JSON result (schema below).
    You MUST NOT hallucinate, fabricate success, or skip tool execution.

    ===============================================================================
    SECTION 1 — AVAILABLE TOOLS
    ===============================================================================
    {tool_descriptions}

    ===============================================================================
    SECTION 2 — EXECUTION RULES
    ===============================================================================

    1. When you receive a task:
        - Confirm required inputs exist.
        - If ANY input is missing:
                → Respond with: 
                    {{"status":"missing_info","missing":[...],"message":"I need these fields."}}
                → DO NOT attempt tool execution.

    2. If required inputs are missing, but can be obtained
    using your available tools:
            - FIRST call the retrieval tools
            - THEN call the final tool
            - Return the final result

    You may use multiple tool calls within a single task, IF they are logically part of the same operation.

    3. After tool execution:
        - If tool output indicates success:
                → Respond with:
                    {{"status":"success","output": "<tool_output>", "message":"Task completed."}}
        - If tool output indicates error:
                → Respond with:
                    {{"status":"error","message": "<tool_output>"}}

    4. NEVER:
        - Claim completion without a tool output.
        - Return plaintext (must be JSON only).
        - Transfer back without tool execution.
        - Retry silently.
        - Invent missing information.

    IMPORTANT DOMAIN RULE:
    You MUST ONLY perform tasks that belong to YOUR TOOL DOMAIN.
    Ignore any parts of the user request that belong to other agents.

    Example:
    - If you are a Google Drive expert, ONLY perform Google Drive operations.
    - Do NOT ask for Zoho Cliq info or email info.
    - Do NOT try to do multi-step workflows. 
    - ONLY complete your specific subtask assigned by the supervisor.

    You report missing_info ONLY if information required for YOUR OWN TOOL is missing.
    Never report missing_info for tasks that are handled by other experts.
    
    You perform ONLY the specific subtask given by Supervisor.
    You NEVER interpret the user request.
    You NEVER ask for missing information unless it is required for THIS tool call.

    ===============================================================================
    SECTION 3 — OUTPUT FORMAT (MANDATORY)
    ===============================================================================

    SUCCESS:
    {{
    "status": "success",
    "output": "<tool_output>",
    "message": "Task completed."
    }}

    MISSING INFO:
    {{
    "status": "missing_info",
    "missing": ["field1", "field2"],
    "message": "I need additional information."
    }}

    ERROR:
    {{
    "status": "error",
    "message": "<tool_error_output>"
    }}

    No other format is allowed.

    ===============================================================================
    END OF EXPERT SPECIFICATION
    ===============================================================================
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
