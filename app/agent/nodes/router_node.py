from __future__ import annotations

from typing import Literal

from app.agent.state import AgentState, message_as_dict

MAX_TOOL_ROUNDS = 6


class RouterNode:
    name = "RouterNode"

    def route(self, state: AgentState) -> Literal["tools", "response"]:
        latest = message_as_dict(state["messages"][-1]) if state.get("messages") else {}
        tool_calls = latest.get("tool_calls")
        if (
            state.get("intent") == "tools"
            and latest.get("role") == "assistant"
            and isinstance(tool_calls, list)
            and any(isinstance(call, dict) and (call.get("function") or {}).get("name") for call in tool_calls)
            and state.get("tool_rounds", 0) < MAX_TOOL_ROUNDS
        ):
            return "tools"
        return "response"
