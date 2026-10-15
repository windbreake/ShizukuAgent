from __future__ import annotations

from typing import Any
import logging
from time import perf_counter

from app.agent.state import AgentState, latest_user_text


class RagNode:
    """Performs on-demand retrieval enhancement before the first model call.

    Unlike the harness's base memory injection (top_k=5 baked into the system
    prompt), this node runs a deeper retrieval for questions that the
    QueryRouter flagged as memory- or knowledge-related, and injects the
    results as a dedicated retrieval-augmented context.
    """

    name = "RagNode"

    def __init__(self, storage: Any | None = None, top_k: int = 10) -> None:
        self.storage = storage
        self.top_k = top_k

    def __call__(self, state: AgentState) -> dict[str, Any]:
        started = perf_counter()
        query = latest_user_text(state)
        items: list[dict[str, Any]] = []
        if self.storage is not None:
            try:
                items = self.storage.search_memories(
                    query, persona=state.get("persona"), top_k=self.top_k
                ) or []
            except Exception:
                items = []
        memory_text = "\n".join(f"- {item.get('content')}" for item in items) if items else ""
        logging.getLogger(__name__).info('agent_rag elapsed_ms=%.1f items=%s', (perf_counter() - started) * 1000, len(items))
        return {
            "rag_context": memory_text,
            "memory": {"items": items, "rag": True},
        }
