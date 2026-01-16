"""
MCP Registry routes.
Provides access to the built-in MCP server registry (SPHERE_REGISTRY).
"""

from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel


router = APIRouter(prefix="/mcp/registry", tags=["MCP Registry"])


# ============================================
# Response Schemas
# ============================================

class OAuthConfigResponse(BaseModel):
    """OAuth configuration for frontend."""
    provider_name: str
    pkce: bool = True
    scopes: List[str]

class AuthFieldResponse(BaseModel):
    """Auth field definition."""
    name: str
    label: str
    description: Optional[str] = None
    type: str = "text"
    required: bool = True

class RegistryAppResponse(BaseModel):
    """Response for a registry app."""
    id: str
    name: str
    description: str
    icon: str
    category: str
    config_template: dict
    auth_fields: List[AuthFieldResponse]
    is_custom: bool = False
    oauth_config: Optional[OAuthConfigResponse] = None


class RegistryListResponse(BaseModel):
    """Response for listing registry apps."""
    apps: List[RegistryAppResponse]
    total: int
    categories: List[str]


# ============================================
# Routes
# ============================================

@router.get("/apps", response_model=RegistryListResponse)
async def list_registry_apps(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name/description"),
):
    """
    List all available MCP apps from the built-in registry.
    
    These are pre-configured MCP server templates that users can easily add.
    """
    # Import the registry
    try:
        from backend.app.core.mcp.registry import SPHERE_REGISTRY, SphereApp
    except ImportError:
        # Fallback if import fails
        return RegistryListResponse(apps=[], total=0, categories=[])
    
    apps = []
    categories = set()
    
    for app in SPHERE_REGISTRY:
        categories.add(app.category)
        
        # Apply filters
        if category and app.category.lower() != category.lower():
            continue
        
        if search:
            search_lower = search.lower()
            if search_lower not in app.name.lower() and search_lower not in app.description.lower():
                continue
        
        # Prepare OAuth Config Response
        oauth_resp = None
        if app.oauth_config:
            oauth_resp = OAuthConfigResponse(
                provider_name=app.oauth_config.provider_name,
                pkce=app.oauth_config.pkce,
                scopes=app.oauth_config.scopes
            )
        
        apps.append(RegistryAppResponse(
            id=app.id,
            name=app.name,
            description=app.description,
            icon=app.icon,
            category=app.category,
            config_template=app.config_template,
            auth_fields=[
                AuthFieldResponse(
                    name=f.name,
                    label=f.label,
                    description=f.description,
                    type=f.type,
                    required=f.required,
                )
                for f in app.auth_fields
            ],
            is_custom=app.is_custom,
            oauth_config=oauth_resp
        ))
    
    return RegistryListResponse(
        apps=apps,
        total=len(apps),
        categories=sorted(list(categories)),
    )


@router.get("/apps/{app_id}", response_model=RegistryAppResponse)
async def get_registry_app(app_id: str):
    """
    Get details for a specific registry app.
    """
    try:
        from backend.app.core.mcp.registry import get_app_by_id
    except ImportError:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_id}' not found"
        )
    
    app = get_app_by_id(app_id)
    
    if not app:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{app_id}' not found"
        )
    
    # Prepare OAuth Config Response
    oauth_resp = None
    if app.oauth_config:
        oauth_resp = OAuthConfigResponse(
            provider_name=app.oauth_config.provider_name,
            pkce=app.oauth_config.pkce,
            scopes=app.oauth_config.scopes
        )

    return RegistryAppResponse(
        id=app.id,
        name=app.name,
        description=app.description,
        icon=app.icon,
        category=app.category,
        config_template=app.config_template,
        auth_fields=[
            AuthFieldResponse(
                name=f.name,
                label=f.label,
                description=f.description,
                type=f.type,
                required=f.required,
            )
            for f in app.auth_fields
        ],
        is_custom=app.is_custom,
        oauth_config=oauth_resp
    )


@router.get("/categories", response_model=List[str])
async def list_categories():
    """
    List all available app categories.
    """
    try:
        from backend.app.core.mcp.registry import SPHERE_REGISTRY
    except ImportError:
        return []
    
    categories = set()
    for app in SPHERE_REGISTRY:
        categories.add(app.category)
    
    return sorted(list(categories))

