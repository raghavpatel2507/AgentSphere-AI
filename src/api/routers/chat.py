from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from src.api.schemas.base import ChatRequest
from src.api.dependencies import get_mcp_manager, get_planner, get_llm
from src.core.mcp.manager import MCPManager
from src.core.agents.planner import Planner
from src.core.agents.agent import Agent
from src.core.state import load_history, save_history
from langchain_core.messages import HumanMessage, AIMessage
import json
import asyncio

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/")
async def chat(
    request: ChatRequest,
    manager: MCPManager = Depends(get_mcp_manager),
    planner: Planner = Depends(get_planner),
    llm = Depends(get_llm)
):
    # 1. Load History
    history = await load_history(request.session_id, request.tenant_id, request.user_id)
    
    # 2. Plan
    available_servers = await manager.get_all_tools_status()
    plan = await planner.plan(request.message, history, available_servers)
    
    async def event_generator():
        # Yield planning status
        yield json.dumps({"type": "status", "status": "planning", "message": "Analyzing your request..."}) + "\n"
        
        # Yield plan info
        yield json.dumps({"type": "plan", "content": plan}) + "\n"
        
        full_response = ""
        
        if plan.get("servers"):
            # Yield searching status
            yield json.dumps({"type": "status", "status": "searching", "message": f"Connecting to {len(plan['servers'])} tool(s)..."}) + "\n"
            
            # Connect to servers
            await manager.connect_to_servers(plan['servers'])
            if manager._mcp_client:
                manager._mcp_client.allowed_servers = list(plan['servers'])
            
            # Yield executing status
            yield json.dumps({"type": "status", "status": "executing", "message": "Running tools and gathering information..."}) + "\n"
            
            # Create Agent
            agent = Agent(llm=llm, mcp_client=manager._mcp_client)
            
            # Update history for execution
            exec_history = history.copy()
            exec_history.append(HumanMessage(content=request.message))
            
            # Yield thinking status before streaming
            yield json.dumps({"type": "status", "status": "thinking", "message": "Processing information and formulating response..."}) + "\n"
            
            # Execute and Stream
            async for chunk in agent.execute_streaming(request.message, history):
                if chunk:
                    yield json.dumps({"type": "token", "content": chunk}) + "\n"
                    full_response += chunk
            
            # Save history
            history.append(HumanMessage(content=request.message))
            history.append(AIMessage(content=full_response))
            await save_history(request.session_id, request.tenant_id, request.user_id, history)
            
        else:
            # Yield thinking status for direct response
            yield json.dumps({"type": "status", "status": "thinking", "message": "Formulating response..."}) + "\n"
            
            # Direct Response
            response = plan.get("response")
            if not response:
                # If planner didn't provide a response, call LLM directly
                async for chunk in llm.astream(history + [HumanMessage(content=request.message)]):
                    if hasattr(chunk, "content"):
                        token = chunk.content
                        if token:
                            yield json.dumps({"type": "token", "content": token}) + "\n"
                            full_response += token
                response = full_response
            else:
                yield json.dumps({"type": "token", "content": response}) + "\n"
            
            # Save history
            history.append(HumanMessage(content=request.message))
            history.append(AIMessage(content=response))
            await save_history(request.session_id, request.tenant_id, request.user_id, history)
            
        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
