from __future__ import annotations

from typing import Literal

from app.agent.state import AgentState, message_as_dict

MAX_TOOL_ROUNDS = 0  # Zero means no application-level round limit.


def tool_round_limit(state: AgentState) -> int:
    value = (state.get('model_config') or {}).get('max_tool_rounds', MAX_TOOL_ROUNDS)
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        return MAX_TOOL_ROUNDS


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
            and (not tool_round_limit(state) or state.get("tool_rounds", 0) < tool_round_limit(state))
        ):
            return "tools"
        return "response"
