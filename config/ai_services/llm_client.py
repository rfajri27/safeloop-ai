"""LLM client factory for Google Gemini, OpenAI, and Mistral.

This module provides:
- SINGLETON: LLMClient factory for creating LLM instances
"""
from typing import Optional
from langchain_openai import ChatOpenAI
from config.settings import env

DEFAULT_MAX_TOKENS = 16384
DEFAULT_TIMEOUT = 120

class LLMClient:
    """
    Factory for creating LLM clients (Google Gemini, OpenAI, Mistral OCR).

    SINGLETON: Stateless factory, created once at module import.
    Each method creates a new LLM instance with specified configuration.

    Example:
        from config.ai_services import llm_client

        # Create OpenAI client with custom temperature
        llm = llm_client.openai(temperature=0.7)
    """

    def openai(
        self,
        model: str,
        temperature: Optional[float] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 2,
    ) -> ChatOpenAI:
        """
        Create an OpenAI chat client.

        Args:
            model: Model name
            temperature: Sampling temperature (default None)
            max_tokens: Maximum output tokens
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure

        Returns:
            ChatOpenAI: Configured OpenAI client
        """
        return ChatOpenAI(
            base_url=env.azure_openai_endpoint,
            api_key=env.api_key_ai_foundary,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries
        )


# SINGLETON: LLM client factory (created once at module import)
llm_client = LLMClient()