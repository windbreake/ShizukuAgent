from __future__ import annotations

from typing import Any

from app.agent.state import AgentState, message_as_dict


class ResponseNode:
    name = "ResponseNode"

    def __call__(self, state: AgentState) -> dict[str, Any]:
        latest = message_as_dict(state["messages"][-1]) if state["messages"] else {}
        reply = state.get("reply") or str(latest.get("content") or "模型未返回内容。")
        return {"reply": reply, "intent": "end"}
