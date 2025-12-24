from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class AuthField(BaseModel):
    name: str
    label: str
    description: Optional[str] = None
    type: str = "text"  # text, password, etc.
    required: bool = True

class SphereApp(BaseModel):
    id: str
    name: str
    description: str
    icon: str  # Icon name or SVG
    category: str
    config_template: Dict[str, Any]
    auth_fields: List[AuthField] = []
    is_custom: bool = False

# Initial Registry based on common MCP servers
SPHERE_REGISTRY: List[SphereApp] = [
    SphereApp(
        id="accuweather",
        name="AccuWeather",
        description="Weather forecasting and information agent (AccuWeather API).",
        icon="⛅",
        category="Weather",
        config_template={
            "command": "npx",
            "args": ["-y", "@timlukahorstmann/mcp-weather"],
            "env": {
                "ACCUWEATHER_API_KEY": "${ACCUWEATHER_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="ACCUWEATHER_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="arxiv",
        name="arXiv",
        description="Search, analyze and read scientific papers from arXiv.",
        icon="📚",
        category="Research",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-arxiv"],
            "env": {}
        },
        auth_fields=[]
    ),
    SphereApp(
        id="github",
        name="GitHub",
        description="GitHub agent for repository management and code operations.",
        icon="🐙",
        category="Development",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
            }
        },
        auth_fields=[
            AuthField(name="GITHUB_TOKEN", label="Personal Access Token", type="password")
        ]
    ),
    SphereApp(
        id="giphy",
        name="Giphy",
        description="Giphy integration for searching and retrieving GIFs.",
        icon="🎬",
        category="Media",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-giphy"],
            "env": {
                "GIPHY_API_KEY": "${GIPHY_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="GIPHY_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="coingecko",
        name="CoinGecko",
        description="Cryptocurrency data agent providing real-time prices.",
        icon="🪙",
        category="Finance",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-coingecko"],
            "env": {}
        },
        auth_fields=[]
    ),
    SphereApp(
        id="etherscan",
        name="Etherscan",
        description="Ethereum blockchain data and analytics agent.",
        icon="💎",
        category="Finance",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-etherscan"],
            "env": {
                "ETHERSCAN_API_KEY": "${ETHERSCAN_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="ETHERSCAN_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="elevenlabs",
        name="ElevenLabs",
        description="Generate high-quality AI voices and speech synthesis.",
        icon="🎙️",
        category="Media",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-elevenlabs"],
            "env": {
                "ELEVENLABS_API_KEY": "${ELEVENLABS_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="ELEVENLABS_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="playwright-mcp",
        name="Playwright",
        description="Browser automation agent for web scraping and testing.",
        icon="🎭",
        category="Tooling",
        config_template={
            "command": "npx",
            "args": ["-y", "@playwright/mcp@latest"],
            "env": {
                "DISPLAY": ":1",
                "PLAYWRIGHT_HEADLESS": "true"
            }
        },
        auth_fields=[] # Config is internal mostly, but user could set env
    ),
    SphereApp(
        id="google-drive",
        name="Google Drive",
        description="Connect and manage your Google Drive files.",
        icon="📂",
        category="Storage",
        config_template={
            "command": "npx",
            "args": ["-y", "@piotr-agier/google-drive-mcp"],
            "env": {
                "GOOGLE_DRIVE_OAUTH_CREDENTIALS": "${GOOGLE_DRIVE_OAUTH_CREDENTIALS}"
            }
        },
        auth_fields=[
            AuthField(name="GOOGLE_DRIVE_OAUTH_CREDENTIALS", label="OAuth Credentials JSON Path", type="text", description="Full path to your gmail_credential.json")
        ]
    ),
    SphereApp(
        id="pinecone-mcp",
        name="Pinecone",
        description="Vector database agent for semantic search and long-term memory.",
        icon="🌲",
        category="Database",
        config_template={
            "command": "npx",
            "args": ["-y", "@pinecone-database/mcp"],
            "env": {
                "PINECONE_API_KEY": "${PINECONE_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="PINECONE_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="firecrawl-mcp",
        name="Firecrawl",
        description="Web scraping and crawling agent that converts websites to LLM-ready markdown.",
        icon="🔥",
        category="Search",
        config_template={
            "command": "npx",
            "args": ["-y", "firecrawl-mcp"],
            "env": {
                "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="FIRECRAWL_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="youtube",
        name="YouTube",
        description="Search and fetch video details, transcripts, and metadata.",
        icon="📺",
        category="Media",
        config_template={
            "command": "npx",
            "args": ["-y", "youtube-data-mcp-server"],
            "env": {
                "YOUTUBE_API_KEY": "${YOUTUBE_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="YOUTUBE_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="notion",
        name="Notion",
        description="Connect to your Notion workspace and manage pages and databases.",
        icon="📝",
        category="Productivity",
        config_template={
            "command": "npx",
            "args": ["-y", "@notionhq/notion-mcp-server"],
            "env": {
                "NOTION_TOKEN": "${NOTION_TOKEN}"
            }
        },
        auth_fields=[
            AuthField(name="NOTION_TOKEN", label="Notion Token", type="password")
        ]
    ),
    SphereApp(
        id="figma",
        name="Figma",
        description="Access and manage Figma projects, files, and layers.",
        icon="🎨",
        category="Design",
        config_template={
            "command": "npx",
            "args": ["-y", "figma-developer-mcp", "--stdio"],
            "env": {
                "FIGMA_API_KEY": "${FIGMA_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="FIGMA_API_KEY", label="Personal Access Token", type="password")
        ]
    ),
    SphereApp(
        id="mobile",
        name="Mobile",
        description="Connect to mobile devices for automation and testing.",
        icon="📱",
        category="Tooling",
        config_template={
            "command": "npx",
            "args": ["-y", "@mobilenext/mobile-mcp"],
            "env": {}
        },
        auth_fields=[]
    ),
    SphereApp(
        id="aws-knowledge",
        name="AWS Knowledge",
        description="Connect to AWS Knowledge Bases for retrieval-augmented generation.",
        icon="☁️",
        category="Cloud",
        config_template={
            "type": "httpx",
            "url": "https://knowledge-mcp.global.api.aws",
            "headers": {
                "Content-Type": "application/json"
            }
        },
        auth_fields=[]
    ),
    SphereApp(
        id="zoho",
        name="Zoho",
        description="Connect to Zoho platform for messaging and business tools.",
        icon="🏢",
        category="Business",
        config_template={
            "type": "httpx",
            "url": "https://agentsphere-60059048845.zohomcp.in/mcp/message?key=${ZOHO_KEY}",
            "headers": {
                "Content-Type": "application/json"
            }
        },
        auth_fields=[
            AuthField(name="ZOHO_KEY", label="Zoho Key", type="text")
        ]
    ),
    SphereApp(
        id="brave-search",
        name="Brave Search",
        description="Web search agent for real-time information.",
        icon="🦁",
        category="Search",
        config_template={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {
                "BRAVE_API_KEY": "${BRAVE_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="BRAVE_API_KEY", label="API Key", type="password")
        ]
    )
]

def get_app_by_id(app_id: str) -> Optional[SphereApp]:
    for app in SPHERE_REGISTRY:
        if app.id == app_id:
            return app
    return None

def get_all_apps() -> List[SphereApp]:
    return SPHERE_REGISTRY
