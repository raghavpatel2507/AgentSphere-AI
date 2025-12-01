from typing import List, Dict, Any, Optional, Type
from langchain.agents import create_agent
from langchain_core.tools import Tool, StructuredTool
from langchain_core.language_models import BaseChatModel
from src.core.mcp.manager import MCPManager
from src.core.mcp.tool_registry import ToolRegistry
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
    You are a HIGH-PRECISION {role} AGENT.

    You execute real-world actions using tools. You are NOT allowed to guess, assume, or fabricate results.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    AVAILABLE TOOLS:
    {tool_descriptions}
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ABSOLUTE RULES (VIOLATION = FAILURE):
    1. NEVER claim success unless a tool response explicitly confirms completion.
    2. ALWAYS validate required parameters BEFORE calling a tool.
    3. If required parameters are missing, DO NOT call the tool — fetch them using other tools OR escalate.
    4. DO NOT hallucinate tool results, confirmations, or actions.
    5. Tool responses are the SINGLE SOURCE OF TRUTH.
    6. NEVER retry with the same parameters if a previous attempt failed.
    7. If an error occurs, your response MUST explain:
       - What failed
       - Why it failed (exact error message)
       - What corrective action was taken
    8. NEVER enter a delegation loop. If failure cannot be resolved, escalate with explanation.
    9. If you cannot verify tool success, you MUST respond:
       "I cannot confirm execution because the tool did not return a success state."  
    10. ROUTING TOOLS DO NOT COUNT AS EXECUTION.
        If the only tool used was a transfer or routing tool, 
        you MUST respond:
            "Task not yet executed. Awaiting action tool confirmation." 
    11. CRITICAL: If a tool returns an error starting with "Error:", treat it as FAILURE.
        Parse the error message and take corrective action (e.g., fetch missing parameters).
    12. NEVER say "I have completed" or "I have sent" unless you have PROOF from a tool response.
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    EXECUTION FLOW (MANDATORY):

    STEP 1: Analyze user request → Identify correct tool  
    STEP 2: Validate ALL required parameters  
    STEP 3: If missing parameters → Fetch via supporting tools OR escalate  
    STEP 4: Execute tool  
    STEP 5: Verify tool response  
        - If response contains "Error:" → Treat as FAILURE, analyze error, retry with fixes
        - If response is successful → Treat as SUCCESS  
    STEP 6: Respond with structured result  
    STEP 7: Transfer back to supervisor

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    RESPONSE FORMAT:

    ✅ SUCCESS:
    Action Completed: <what happened>
    Tool Used: <tool name>
    Evidence: <tool response summary>

    ❌ FAILURE:
    Action Failed: <what was attempted>
    Reason: <error from tool>
    Resolution: <what you changed or why you escalated>

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    FINAL RULE:
    You exist to EXECUTE and VERIFY, not to narrate optimism.

    When finished, ALWAYS transfer back to supervisor with a clear status.
    """


    @staticmethod
    def _create_args_schema(name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
        """
        Dynamically create a Pydantic model from a JSON schema.
        Enhanced for Gemini compatibility with complex array types.
        """
        from typing import List
        
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        fields = {}
        for field_name, field_info in properties.items():
            field_type = Any
            t = field_info.get("type")
            
            # Basic type mapping
            if t == "string":
                field_type = str
            elif t == "integer":
                field_type = int
            elif t == "boolean":
                field_type = bool
            elif t == "number":
                field_type = float
            elif t == "array":
                # Enhanced array handling for Gemini compatibility
                items = field_info.get("items", {})
                
                # If items is empty or doesn't have a type, default to List[str]
                if not items or not isinstance(items, dict):
                    field_type = List[str]
                else:
                    item_type = items.get("type")
                    
                    # If no type specified, check if it's a complex object
                    if not item_type:
                        # Complex schema without type - default to List[dict] for objects
                        if items.get("properties") or items.get("oneOf") or items.get("anyOf"):
                            field_type = List[dict]
                        else:
                            field_type = List[str]
                    elif item_type == "integer":
                        field_type = List[int]
                    elif item_type == "boolean":
                        field_type = List[bool]
                    elif item_type == "number":
                        field_type = List[float]
                    elif item_type == "object":
                        field_type = List[dict]
                    else:
                        field_type = List[str]
            elif t == "object":
                field_type = dict
                
            description = field_info.get("description", "")
            
            # Determine default value
            if field_name in required:
                default = ...
            else:
                default = None
                
            fields[field_name] = (field_type, Field(default=default, description=description))
            
        # If no properties, return empty model
        if not fields:
            return create_model(f"{name}Schema")
            
        return create_model(f"{name}Schema", **fields)

    @staticmethod
    async def create_all_experts(model: BaseChatModel) -> Dict[str, Any]:
        """
        Create all enabled expert agents based on MCP configuration.
        Returns a dictionary of agent_name -> agent_instance.
        """
        manager = MCPManager()
        # Ensure manager is initialized
        if not manager._initialized:
             # This might need to be awaited if called early, but usually main.py inits it
             pass
             
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
            
            # Get tools for this server
            mcp_tools = manager.get_tools_for_server(server_name)
            
            if not mcp_tools:
                continue
                
            # Create LangChain tools wrappers
            langchain_tools = []
            for tool_info in mcp_tools:
                # Create a closure to capture tool_name
                def make_tool_func(t_name):
                    async def tool_wrapper(**kwargs):
                        return await manager.call_tool(t_name, kwargs)
                    return tool_wrapper
                
                # Create dynamic args schema
                args_schema = ExpertFactory._create_args_schema(tool_info.name, tool_info.schema)
                
                # Use StructuredTool for proper schema validation
                lc_tool = StructuredTool.from_function(
                    name=tool_info.name,
                    description=tool_info.description,
                    func=None, # We use coroutine
                    coroutine=make_tool_func(tool_info.name),
                    args_schema=args_schema
                )
                langchain_tools.append(lc_tool)
            
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
