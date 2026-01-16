from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class AuthField(BaseModel):
    name: str
    label: str
    description: Optional[str] = None
    type: str = "text"  # text, password, etc.
    required: bool = True

class OAuthConfig(BaseModel):
    provider_name: str # e.g. "google", "github"
    authorize_url: str
    token_url: str
    scopes: List[str]
    client_id_env: str
    client_secret_env: str
    pkce: bool = True
    userinfo_url: Optional[str] = None

class SphereApp(BaseModel):
    id: str
    name: str
    description: str
    icon: str  # Icon name or SVG
    category: str
    config_template: Dict[str, Any]
    auth_fields: List[AuthField] = []
    is_custom: bool = False
    oauth_config: Optional[OAuthConfig] = None

# Initial Registry based on common MCP servers
SPHERE_REGISTRY: List[SphereApp] = [
    SphereApp(
        id="accuweather",
        name="AccuWeather",
        description="Weather forecasting and information agent (AccuWeather API).",
        icon="https://cdn.brandfetch.io/accuweather.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/arxiv.org/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/github.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Development",
        config_template={
            "type": "httpx",
            "url": "https://api.githubcopilot.com/mcp/",
            "auth": "${GITHUB_TOKEN}"
        },
        auth_fields=[],
        oauth_config=OAuthConfig(
            provider_name="github",
            authorize_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scopes=["repo", "read:user", "user:email"],
            client_id_env="GITHUB_CLIENT_ID",
            client_secret_env="GITHUB_CLIENT_SECRET",
            pkce=False
        )
    ),
    SphereApp(
        id="exa",
        name="Exa",
        description="Web crawling, company research, competitor analysis, and research paper retrieval.",
        icon="https://cdn.brandfetch.io/exa.ai/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Search",
        config_template={
            "type": "httpx",
            "url": "https://mcp.exa.ai/mcp",
            "headers": {}
        },
        auth_fields=[]
    ),
    SphereApp(
        id="giphy",
        name="Giphy",
        description="Giphy integration for searching and retrieving GIFs.",
        icon="https://cdn.brandfetch.io/giphy.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Media",
        config_template={
            "command": "npx",
            "args": ["-y", "mcp-server-giphy"],
            "env": {
                "GIPHY_API_KEY": "${GIPHY_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="GIPHY_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="huggingface",
        name="Hugging Face",
        description="Hugging Face Hub integration for accessing models, datasets, spaces, and papers.",
        icon="https://cdn.brandfetch.io/huggingface.co/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Development",
        config_template={
            "type": "httpx",
            "url": "https://huggingface.co/mcp",
            "auth": "${HUGGINGFACE_API_KEY}"
        },
        auth_fields=[
            AuthField(name="HUGGINGFACE_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="linear",
        name="linear",
        description="Linear issue tracking and project management agent. Use Linear in Agentsphere to interact with your data through natural conversation. Just ask and Linear will handle the rest.",
        icon="https://cdn.brandfetch.io/linear.app/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Development",
        config_template={
            "type": "httpx",
            "url": "https://mcp.linear.app/mcp",
            "auth": {
                "callback_port": 8082
            }
        },
        auth_fields=[]
    ),
    SphereApp(
        id="coingecko",
        name="CoinGecko",
        description="Cryptocurrency data agent providing real-time prices.",
        icon="https://cdn.brandfetch.io/coingecko.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/etherscan.io/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/elevenlabs.io/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Media",
        config_template={
            "command": "uvx",
            "args": ["elevenlabs-mcp"],
            "env": {
                "ELEVENLABS_API_KEY": "${ELEVENLABS_API_KEY}"
            }
        },
        auth_fields=[
            AuthField(name="ELEVENLABS_API_KEY", label="API Key", type="password")
        ]
    ),
    SphereApp(
        id="MongoDB",
        name="MongoDB",
        description="Mongodb agent to list collections and executing read-only queries on database. Use Mongodb to interact with your data through natural conversation. Just ask and Mongodb will handle the rest.",
        icon="https://cdn.brandfetch.io/ideyyfT0Lp/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Database",
        config_template={
            "command": "npx",
            "args": ["-y", "mongodb-mcp-server@latest", "--readOnly"],
            "env": {
                "MDB_MCP_CONNECTION_STRING": "${MDB_MCP_CONNECTION_STRING}"
            }
        },
        auth_fields=[
            AuthField(name="MDB_MCP_CONNECTION_STRING", label="Connection String", type="text")
        ]
    ),
    SphereApp(
        id="Mysql",
        name="Mysql",
        description="MySQL agent to list tables and execute read-only SQL queries on database. Use MySQL in Agentsphere to interact with your data through natural conversation. Just ask and MySQL will handle the rest.",
        icon="https://cdn.brandfetch.io/mysql.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Database",
        config_template={
            "command": "npx",
            "command": "uvx",
            "args": [
                "--from",
                "mysql-mcp-server",
                "mysql_mcp_server"
            ],
            "env": {
                "MYSQL_HOST": "localhost",
                "MYSQL_PORT": "3306",
                "MYSQL_USER": "${MYSQL_USER}",
                "MYSQL_PASSWORD": "${MYSQL_PASSWORD}",
                "MYSQL_DATABASE": "${MYSQL_DATABASE}"
            }
        },
        auth_fields=[
            AuthField(name="MYSQL_USER", label="User", type="text"),
            AuthField(name="MYSQL_PASSWORD", label="Password", type="password"),
            AuthField(name="MYSQL_DATABASE", label="Database", type="text")
        ]
    ),
    SphereApp(
        id="google-calendar",
        name="Google Calendar",
        description="Google Calendar integration for managing events and appointments.",
        icon="https://cdn.brandfetch.io/google.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Calendar",
        config_template={
            "command": "npx",
            "args": ["-y", "@cocal/google-calendar-mcp"],
            "auth": "${GOOGLE_CALENDAR_TOKEN}"
        }
    ),
    SphereApp(
        id="playwright-mcp",
        name="Playwright",
        description="Browser automation agent for web scraping and testing.",
        icon="https://cdn.brandfetch.io/playwright.dev/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/google.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/pinecone.io/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/firecrawl.dev/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/youtube.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/notion.so/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/figma.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/android.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        icon="https://cdn.brandfetch.io/aws.amazon.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
        description="Connect to Zoho platform using OAuth. Provide your Zoho MCP Server URL and we'll handle authentication.",
        icon="https://cdn.brandfetch.io/zoho.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
        category="Business",
        config_template={
            "type": "sse",
            "url": "${ZOHO_URL}",
            "auth": "${ZOHO_TOKEN}"
        },
        auth_fields=[
            AuthField(
                name="ZOHO_MCP_URL", 
                label="Zoho MCP Server URL", 
                type="text", 
                description="Your Zoho MCP Server URL (OAuth metadata will be discovered automatically)"
            )
        ],
        oauth_config=OAuthConfig(
            provider_name="zoho",
            authorize_url="DYNAMIC",  # Discovered from server's .well-known
            token_url="DYNAMIC",       # Discovered from server's .well-known
            scopes=[],                 # Discovered from server
            client_id_env="",          # Uses Dynamic Client Registration
            client_secret_env="",
            pkce=True
        )
    ),
    SphereApp(
        id="gmail-mcp",
        name="Gmail",
        description="Connect and manage your Gmail account.",
        icon="https://cdn.brandfetch.io/id6O2oGzv-/theme/dark/idncaAgFGT.svg?c=1bxid64Mup7aczewSAYMX&t=1755572716016",
        category="Storage",
        config_template={
            "command": "npx",
            "args": ["-y", "@gongrzhe/server-gmail-autoauth-mcp"],
            "auth": "${GMAIL_TOKEN}"
        },
        auth_fields=[],
        oauth_config=OAuthConfig(
            provider_name="google",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=[
                "https://www.googleapis.com/auth/drive.readonly",
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.modify",
                "email",
                "profile",
                "openid"
            ],
            client_id_env="GOOGLE_CLIENT_ID",
            client_secret_env="GOOGLE_CLIENT_SECRET",
            pkce=True
        )
    ),
    SphereApp(
        id="brave-search",
        name="Brave Search",
        description="Web search agent for real-time information.",
        icon="https://cdn.brandfetch.io/brave.com/w/400/h/400/theme/dark/icon.png?c=1bxid64Mup7aczewSAYMX&t=1671109848386",
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
