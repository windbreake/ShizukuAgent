from __future__ import annotations

import os
import json
from abc import ABC, abstractmethod
from typing import Any

from app.agent.state import message_as_dict

class LLMClient(ABC):
    @abstractmethod
    def chat(self, messages: list[dict[str, Any]], model_config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def embed(self, text: str, model_config: dict[str, Any] | None = None) -> list[float]:
        raise NotImplementedError


class OpenAICompatibleClient(LLMClient):
    def chat(self, messages: list[dict[str, Any]], model_config: dict[str, Any]) -> dict[str, Any]:
        from openai import OpenAI

        from app.agent.tools import OPENAI_TOOLS

        provider = model_config.get("provider_config") or {}
        with OpenAI(
            api_key=provider.get("api_key") or os.getenv(str(provider.get("env_key") or "OPENAI_API_KEY")),
            base_url=provider.get("base_url") or None,
            default_headers=provider.get('request_headers') or None,
            timeout=float(provider.get('timeout') or 60),
            max_retries=0,
        ) as client:
            extra = {}
            if model_config.get("reasoning_effort") in {"low", "medium", "high"}:
                extra["reasoning_effort"] = model_config["reasoning_effort"]
            from app.execution import current, check, delta
            if current.get() is not None:
                content='';calls={}
                stream=client.chat.completions.create(model=model_config.get('model') or 'gpt-4o-mini',messages=messages,tools=model_config.get('tools',OPENAI_TOOLS),temperature=.4,stream=True,**extra)
                try:
                    for chunk in stream:
                        check()
                        if not chunk.choices:continue
                        part=chunk.choices[0].delta
                        if part.content:
                            content+=part.content;delta(part.content)
                        for call in part.tool_calls or []:
                            item=calls.setdefault(call.index,{'id':'','type':'function','function':{'name':'','arguments':''}})
                            if call.id:item['id']=call.id
                            if call.function:
                                if call.function.name:item['function']['name']+=call.function.name
                                if call.function.arguments:item['function']['arguments']+=call.function.arguments
                finally:stream.close()
                return {'role':'assistant','content':content,'tool_calls':[calls[index] for index in sorted(calls)]}
            completion = client.chat.completions.create(
                model=model_config.get("model") or "gpt-4o-mini",
                messages=messages,
                tools=model_config.get("tools", OPENAI_TOOLS),
                temperature=0.4,
                **extra,
            )
        return _normalise_model_message(completion.choices[0].message)

    def embed(self, text: str, model_config: dict[str, Any] | None = None) -> list[float]:
        from openai import OpenAI

        provider = (model_config or {}).get("provider_config") or {}
        with OpenAI(
            api_key=provider.get("api_key") or os.getenv(str(provider.get("env_key") or "OPENAI_API_KEY")),
            base_url=provider.get("base_url") or None,
            default_headers=provider.get('request_headers') or None,
            timeout=float(provider.get('embedding_timeout') or 5),
            max_retries=0,
        ) as client:
            response = client.embeddings.create(
                model=(model_config or {}).get("embedding_model") or "text-embedding-3-small",
                input=text,
            )
        return list(response.data[0].embedding)


class LocalFallbackClient(LLMClient):
    def chat(self, messages: list[dict[str, Any]], model_config: dict[str, Any]) -> dict[str, Any]:
        last_user = next((message_as_dict(item).get("content") for item in reversed(messages) if message_as_dict(item).get("role") == "user"), "")
        persona = model_config.get("persona") or "agent"
        return {
            "role": "assistant",
            "content": (
                f"[{persona}] 已收到：{_content_to_text(last_user)}\n"
                "当前运行 LangGraph Agent。未配置主模型 API Key，因此使用本地回退回复。"
            ),
        }

    def embed(self, text: str, model_config: dict[str, Any] | None = None) -> list[float]:
        return [float((ord(ch) % 13) / 13) for ch in (text or " ")[:8]]


def provider_has_key(model_config: dict[str, Any]) -> bool:
    provider = model_config.get("provider_config") or {}
    return bool(provider.get("api_key") or os.getenv(str(provider.get("env_key") or "OPENAI_API_KEY")))


def model_supports_vision(model_config: dict[str, Any] | None = None) -> bool:
    capabilities = list((model_config or {}).get("capabilities") or [])
    return "vision" in capabilities


def _normalise_model_message(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        message = dict(response)
        message["tool_calls"] = [_normalise_tool_call(call) for call in message.get("tool_calls") or []]
        return message
    tool_calls = []
    for call in list(getattr(response, "tool_calls", None) or []):
        function = call.function
        tool_calls.append(
            {
                "id": call.id,
                "type": "function",
                "function": {"name": function.name, "arguments": function.arguments or "{}"},
            }
        )
    return {
        "role": "assistant",
        "content": getattr(response, "content", None) or "",
        "tool_calls": tool_calls,
    }


def _normalise_tool_call(call: Any) -> dict[str, Any]:
    call = dict(call or {})
    function = dict(call.get("function") or {})
    raw_arguments = function.get("arguments") or "{}"
    try:
        parsed = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        if not isinstance(parsed, dict):
            raise ValueError("工具参数必须是 JSON 对象")
        function["arguments"] = json.dumps(parsed, ensure_ascii=False)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        # Keep the graph message valid while preserving the parse failure for the executor.
        function["arguments"] = json.dumps({"_validation_error": str(exc)}, ensure_ascii=False)
    call["function"] = function
    return call


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text") or "[图片]")
            for part in content
            if isinstance(part, dict) and part.get("type") in {"text", "image_url"}
        )
    return str(content or "")
