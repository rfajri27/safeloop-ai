"""Google GenAI client for embeddings (spec Section 8: embeddings only).

This module provides:
- SINGLETON: GenAIClient with embed_documents() / embed_query()
"""
from typing import Optional, Sequence
from google import genai
from google.genai import types
from config.settings import env

EMBED_BATCH_SIZE = 32
EMBED_TIMEOUT_MS = 15_000


class GenAIClient:
    """
    Embeddings through the Google GenAI SDK (gemini-embedding-001, 768 dimensions).

    SINGLETON: the underlying client is created on first use.
    """

    def __init__(self):
        self._client: Optional[genai.Client] = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            options = types.HttpOptions(timeout=EMBED_TIMEOUT_MS)
            if env.google_genai_use_vertexai:
                self._client = genai.Client(
                    vertexai=True,
                    project=env.google_cloud_project,
                    location=env.google_cloud_location,
                    http_options=options,
                )
            else:
                self._client = genai.Client(api_key=env.google_api_key, http_options=options)
        return self._client

    async def _embed(self, texts: Sequence[str], task_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = list(texts[start:start + EMBED_BATCH_SIZE])
            result = await self.client.aio.models.embed_content(
                model=env.gemini_embedding_model,
                contents=batch,
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=env.embedding_dim),
            )
            vectors.extend(list(e.values) for e in result.embeddings)
        return vectors

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed chunks for indexing (task_type RETRIEVAL_DOCUMENT)."""
        return await self._embed(texts, "RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> list[float]:
        """Embed a search query (task_type RETRIEVAL_QUERY)."""
        return (await self._embed([text], "RETRIEVAL_QUERY"))[0]


# SINGLETON: embeddings client
genai_client = GenAIClient()
