"""LLM client factory for Google Gemini (LangGraph agents) and OpenAI.

This module provides:
- SINGLETON: LLMClient factory for creating LLM instances
"""
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from config.settings import env

DEFAULT_MAX_TOKENS = 16384
DEFAULT_TIMEOUT = 120


class LLMClient:
    """
    Factory for creating LLM clients (Google Gemini, OpenAI).

    SINGLETON: Stateless factory, created once at module import.
    Each method creates a new LLM instance with specified configuration.

    Example:
        from config.ai_services.llm_client import llm_client

        llm = llm_client.gemini(thinking_level="medium", max_tokens=4096)
    """

    def gemini(
        self,
        *,
        thinking_level: Optional[str] = None,
        max_tokens: int = 1024,
        timeout: Optional[float] = None,
    ) -> ChatGoogleGenerativeAI:
        """
        Create a Gemini chat model for LangGraph (spec Section 8).

        temperature, top_p and top_k are left unset, as Google advises for the
        Gemini 3.x family. Thinking tokens count against max_tokens.
        """
        return ChatGoogleGenerativeAI(
            model=env.gemini_model,
            google_api_key=env.google_api_key or None,
            vertexai=env.google_genai_use_vertexai or None,
            project=env.google_cloud_project or None,
            location=env.google_cloud_location,
            thinking_level=thinking_level or env.gemini_thinking_level,
            max_output_tokens=max_tokens,
            timeout=timeout or env.llm_timeout_seconds,
            max_retries=env.llm_max_retries,
        )

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
