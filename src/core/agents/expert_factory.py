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
        """Generate system prompt for an expert agent."""
        tool_descriptions = "\n".join([f"- {t.name}: {t.description}" for t in tools])
        
        if custom_template:
            return custom_template.format(expert_role=role, tools=tool_descriptions)
            
        return f"""
You are a {role}.

Available Tools:
{tool_descriptions}

RULES:
1. ALWAYS use the provided tools to answer user requests.
2. Do NOT hallucinate tool outputs.
3. If a tool is available for the task, USE IT.
4. After using
 a tool, report the result clearly.
5. ALWAYS transfer back to the supervisor when done.

Your job is ACTION, not planning. Execute tools immediately.
"""

    @staticmethod
    def _create_args_schema(name: str, schema: Dict[str, Any]) -> Type[BaseModel]:
        """
        Dynamically create a Pydantic model from a JSON schema.
        """
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
                field_type = list
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
