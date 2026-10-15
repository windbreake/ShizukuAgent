from __future__ import annotations

from typing import Any, Literal

from app.agent.state import AgentState, latest_user_text

RAG_KEYWORDS = (
    "记忆",
    "之前",
    "上次",
    "回忆",
    "记得",
    "忘了",
    "搜索",
    "查找",
    "查询",
    "文档",
    "知识",
    "总结",
    "回顾",
)


class QueryRouterNode:
    """Routes the first user turn between enhanced RAG retrieval and direct answering.

    The route is a lightweight intent heuristic: questions asking about memory,
    history, search, documents or knowledge go through the RAG node once; other
    questions go straight to the model (which still receives the base memory
    injected by the harness and can use retrieval tools agentically).
    """

    name = "QueryRouterNode"

    def __call__(self, state: AgentState) -> dict[str, Any]:
        """Node body is a no-op; the actual routing happens in the conditional edge."""
        return {}

    def route(self, state: AgentState) -> Literal["rag", "model"]:
        query = latest_user_text(state)
        if any(keyword in query for keyword in RAG_KEYWORDS):
            return "rag"
        return "model"