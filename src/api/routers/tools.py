from fastapi import APIRouter, Depends, HTTPException
from src.api.schemas.base import ToolStatus, ToolToggleRequest
from src.api.dependencies import get_mcp_manager
from src.core.mcp.manager import MCPManager
from typing import Dict, List

router = APIRouter(prefix="/tools", tags=["tools"])

@router.get("/", response_model=List[ToolStatus])
async def get_tools_status(manager: MCPManager = Depends(get_mcp_manager)):
    status_dict = await manager.get_all_tools_status()
    result = []
    for name, info in status_dict.items():
        result.append(ToolStatus(
            name=name,
            connected=info['connected'],
            tools_count=info['tools_count'],
            description=info.get('description')
        ))
    return result

@router.post("/{tool_name}/toggle")
async def toggle_tool(tool_name: str, request: ToolToggleRequest, manager: MCPManager = Depends(get_mcp_manager)):
    result = await manager.toggle_tool_status(tool_name, request.enable)
    if "not found" in result:
        raise HTTPException(status_code=404, detail=result)
    return {"message": result}
