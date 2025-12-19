from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import os
import logging
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
# from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def create_model(self, config: Dict[str, Any]) -> BaseChatModel:
        """Create and return a configured LangChain chat model."""
        pass

class OpenAIProvider(LLMProvider):
    def create_model(self, config: Dict[str, Any]) -> BaseChatModel:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
            
        return ChatOpenAI(
            model_name=config.get("model", "gpt-4o"),
            temperature=config.get("temperature", 0.7),
            openai_api_key=api_key,
            max_tokens=config.get("max_tokens"),
            max_retries=3,
            streaming=True
        )

class OpenROuterProvider(LLMProvider):
    def create_model(self, config: Dict[str, Any]) -> BaseChatModel:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")
            
        return ChatOpenAI(
            model=config.get("model", "gpt-4o"),
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens"),
            max_retries=3,
            streaming=True
        )

class GeminiProvider(LLMProvider):
    def create_model(self, config: Dict[str, Any]) -> BaseChatModel:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
            
        return ChatGoogleGenerativeAI(
            model=config.get("model", "gemini-1.5-pro"),
            temperature=config.get("temperature", 0.7),
            google_api_key=api_key,
            max_retries=3,
            streaming=True
        )

class ClaudeProvider(LLMProvider):
    def create_model(self, config: Dict[str, Any]) -> BaseChatModel:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
            
        return ChatAnthropic(
            model_name=config.get("model", "claude-3-sonnet-20240229"),
            temperature=config.get("temperature", 0.7),
            anthropic_api_key=api_key,
            streaming=True
        )

class GroqProvider(LLMProvider):
    def create_model(self, config: Dict[str, Any]) -> BaseChatModel:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
            
        return ChatGroq(
            model_name=config.get("model", "llama3-70b-8192"),
            temperature=config.get("temperature", 0.7),
            groq_api_key=api_key,
            max_retries=3,
            streaming=True
        )


class LLMFactory:
    """Factory to create LLM instances based on configuration."""
    
    @staticmethod
    def create_llm(config: Dict[str, Any]) -> BaseChatModel:
        provider_name = config.get("provider", "openai").lower()
        
        providers = {
            "openai": OpenAIProvider(),
            "gemini": GeminiProvider(),
            "claude": ClaudeProvider(),
            "groq": GroqProvider(),
            "openrouter": OpenROuterProvider()
        }
        
        provider = providers.get(provider_name)
        if not provider:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")
            
        return provider.create_model(config)

    @staticmethod
    def load_config_and_create_llm(config_path: str = "multi_server_config.json") -> BaseChatModel:
        """Loads config from file or env and creates LLM."""
        import json
        
        # Default configuration from environment variables
        # Default configuration from environment variables
        max_tokens_env = os.getenv("LLM_MAX_TOKENS")
        max_tokens = int(max_tokens_env) if max_tokens_env else 4096
        # Hard cap to prevent 400 errors with some providers
        if max_tokens > 8192:
            max_tokens = 4096

        config = {
            "provider": os.getenv("LLM_PROVIDER", "openrouter"),
            "model": os.getenv("MODEL_NAME", "mistralai/mistral-large-2411"),
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
            "max_tokens": max_tokens
        }
        
        # Try loading from multi_server_config.json if it exists (for overrides if any)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    full_config = json.load(f)
                    # extending support if user still wants to put llm config in multi_server_config.json
                    llm_settings = full_config.get("llm", {})
                    if llm_settings:
                        config.update(llm_settings)
                        logger.info(f"Updated LLM config from {config_path}: {llm_settings}")
            except Exception as e:
                logger.warning(f"Error loading LLM config from {config_path}: {e}")
            
        return LLMFactory.create_llm(config)
