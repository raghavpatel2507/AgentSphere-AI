from fastapi import APIRouter, HTTPException, Query
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel
from typing import Optional
import logging

router = APIRouter(tags=["metadata"])
logger = logging.getLogger(__name__)

class MetadataResponse(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    url: str


@router.get("/metadata", response_model=MetadataResponse)
async def get_metadata(url: str = Query(..., description="The URL to fetch metadata for")):
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Helper to get meta tag content
        def get_meta(property_name: str, attr: str = "property") -> Optional[str]:
            tag = soup.find("meta", {attr: property_name})
            if not tag:
                tag = soup.find("meta", {"name": property_name})
            return tag.get("content") if tag else None

        title = get_meta("og:title") or (soup.title.string if soup.title else None)
        description = get_meta("og:description") or get_meta("description", "name")
        image = get_meta("og:image")
        
        # Fallback for site icons if no image
        if not image:
            icon_tag = soup.find("link", rel="icon") or soup.find("link", rel="shortcut icon")
            if icon_tag:
                image = icon_tag.get("href")
                if image and not image.startswith("http"):
                    # Resolve relative URL
                    from urllib.parse import urljoin
                    image = urljoin(url, image)

        return MetadataResponse(
            title=title.strip() if title else None,
            description=description.strip() if description else None,
            image=image,
            url=url
        )
    except Exception as e:
        logger.error(f"Error fetching metadata for {url}: {e}")
        # Return at least the URL even if it fails
        return MetadataResponse(url=url)
