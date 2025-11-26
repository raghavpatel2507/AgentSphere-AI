from dotenv import load_dotenv
import os
import json
from src.core.llm.provider import LLMFactory

load_dotenv()

def load_llm_config():
    """Load LLM configuration from mcp_config.json or env vars."""
    config_path = "mcp_config.json"
    default_config = {
        "provider": os.getenv("LLM_PROVIDER", "openai"),
        "model": os.getenv("MODEL_NAME", "gpt-4o"),
        "temperature": 0.7,
        "max_tokens": int(os.getenv("MAX_TOKENS", "100000"))
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                full_config = json.load(f)
                llm_config = full_config.get("llm", {})
                # Merge with defaults/env vars if missing
                return {**default_config, **llm_config}
    except Exception as e:
        print(f"Warning: Error loading LLM config: {e}")
        
    return default_config

# Load configuration
llm_config = load_llm_config()

# Export constants
MODEL_NAME = llm_config.get("model")
MAX_TOKENS = llm_config.get("max_tokens", 100000)

# Initialize model
try:
    model = LLMFactory.create_llm(llm_config)
    print(f"✅ LLM Initialized: {llm_config.get('provider')} / {MODEL_NAME}")
except Exception as e:
    print(f"❌ Failed to initialize LLM: {e}")
    # Fallback to OpenAI if possible, or raise
    raise