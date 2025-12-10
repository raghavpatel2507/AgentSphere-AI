from typing import List, Dict, Any, Optional, Type
from langchain.agents import create_agent
from langchain_core.tools import Tool, StructuredTool
from langchain_core.language_models import BaseChatModel
from src.core.mcp.manager import MCPManager
from src.core.agents.hitl_interrupt import request_tool_approval
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

