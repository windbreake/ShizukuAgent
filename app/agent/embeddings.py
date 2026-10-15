from __future__ import annotations

from typing import Callable

from app.agent.llm import LLMClient, OpenAICompatibleClient
from app.storage.adapter import _embed_text


def make_embedder(llm_client: LLMClient | None = None) -> Callable[[str], list[float]]:
    """Build an embedding function that prefers semantic LLM embeddings and
    falls back to the local hashed bag-of-words when the LLM is unavailable."""
    if llm_client is None:
        llm_client = OpenAICompatibleClient()

    def embed(text: str) -> list[float]:
        try:
            return list(llm_client.embed(text or " "))  # type: ignore[no-any-return]
        except Exception:
            return _embed_text(text)

    return embed