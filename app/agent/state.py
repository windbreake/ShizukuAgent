from __future__ import annotations

import json
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


def message_as_dict(message: Any) -> dict[str, Any]:
    if isinstance(message, dict):
        return message
    role = getattr(message, "type", None) or getattr(message, "role", "assistant")
    role_map = {"human": "user", "ai": "assistant", "tool": "tool", "system": "system"}
    payload: dict[str, Any] = {
        "role": role_map.get(str(role), str(role)),
        "content": getattr(message, "content", "") or "",
    }
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        payload["tool_calls"] = [_normalise_tool_call(call) for call in tool_calls]
    tool_call_id = getattr(message, "tool_call_id", None)
    if tool_call_id:
        payload["tool_call_id"] = tool_call_id
    return payload


def _normalise_tool_call(call: Any) -> dict[str, Any]:
    if isinstance(call, dict):
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        name = call.get("name") or function.get("name") or ""
        arguments = call.get("args") or call.get("arguments") or function.get("arguments") or "{}"
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)
        return {
            "id": call.get("id") or name,
            "type": "function",
            "function": {"name": name, "arguments": str(arguments or "{}")},
        }
    function = getattr(call, "function", None)
    name = getattr(call, "name", "") or (function.get("name") if isinstance(function, dict) else getattr(function, "name", ""))
    return {
        "id": getattr(call, "id", "") or name,
        "type": "function",
        "function": {"name": name or "", "arguments": _tool_arguments(call)},
    }


def _tool_arguments(call: Any) -> str:
    raw = getattr(call, "args", None)
    if raw is None:
        raw = getattr(call, "arguments", None)
    function = getattr(call, "function", None)
    if raw is None and isinstance(function, dict):
        raw = function.get("arguments")
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False)
    return str(raw or "{}")


class AgentState(TypedDict):
    messages: Annotated[list[dict[str, Any]], add_messages]
    thread_id: str
    persona: str
    intent: str
    tool_result: list[str]
    memory: dict[str, Any]
    traces: list[dict[str, Any]]
    tool_rounds: int
    engine: str
    reply: str
    model_config: dict[str, Any]
    model_candidates: list[dict[str, Any]]
    active_model: str
    rag_context: str


def latest_user_text(state: AgentState) -> str:
    """Extract the latest non-empty user message text from graph state."""
    for item in reversed(state.get("messages") or []):
        if message_as_dict(item).get('role') != 'user':
            continue
        content = item.get("content") if isinstance(item, dict) else getattr(item, "content", "")
        if isinstance(content, list):
            content = " ".join(
                str(part.get("text") or "[图片]")
                for part in content
                if isinstance(part, dict) and part.get("type") in {"text", "image_url"}
            )
        if str(content or "").strip():
            return str(content).strip()
    return ""
