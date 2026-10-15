from __future__ import annotations

from typing import Any, Callable
from app.execution import check, event, wait_for, Stopped
from app.agent.permissions import allowed
from time import perf_counter
import logging

from app.agent.llm import LLMClient, LocalFallbackClient, OpenAICompatibleClient, _normalise_model_message, provider_has_key
from app.agent.nodes.router_node import tool_round_limit
from app.agent.state import AgentState, message_as_dict
from app.agent.tool_registry import ToolRegistry


class ModelNode:
    name = "ModelNode"

    def __init__(
        self,
        gateway: Callable[[list[dict[str, Any]], dict[str, Any]], Any] | None = None,
        llm_client: LLMClient | None = None,
        fallback_client: LLMClient | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        primary = llm_client or OpenAICompatibleClient()
        self._explicit_client = llm_client is not None
        self._local = fallback_client or LocalFallbackClient()
        self._custom_gateway = gateway
        self._gateway = gateway or primary.chat
        self._tool_registry = tool_registry or ToolRegistry()

    def __call__(self, state: AgentState) -> dict[str, Any]:
        check()
        event('model','思考中')
        limit = tool_round_limit(state)
        summarizing = bool(limit and state['tool_rounds'] >= limit)

        outgoing = [message_as_dict(item) for item in state["messages"]]
        outgoing = _inject_rag_context(outgoing, state.get("rag_context") or "")
        if summarizing:
            outgoing.append({'role':'system','content':'本轮工具执行预算已用完。请根据已有工具结果直接总结已完成的分析、发现和未完成项，不再调用工具，不要声称未完成的工作已完成。'})
        if (
            self._custom_gateway is None
            and not self._explicit_client
            and not any(provider_has_key(candidate) for candidate in state["model_candidates"])
        ):
            response = self._local.chat(outgoing, {**state["model_config"], "persona": state["persona"]})
            return {
                "messages": [response],
                "reply": response["content"],
                "engine": "langgraph-local-fallback",
                "intent": "respond",
                "active_model": "local-fallback",
                "rag_context": "",
            }

        response = None
        last_error: Exception | None = None
        active_model = state["active_model"]
        candidates = list(state["model_candidates"])
        if state.get('tool_rounds', 0):
            candidates.sort(key=lambda item: item['id'] != active_model)
        for candidate in candidates:
            started = perf_counter()
            try:
                payload = dict(candidate)
                payload["tools"] = self._tool_registry.definitions()
                payload['tools'] = [tool for tool in payload['tools'] if allowed(tool.get('function',{}).get('name'), candidate.get('workbench_mode'))]
                if summarizing:
                    payload['tools'] = []
                response = wait_for(self._gateway,outgoing,payload)
                active_model = candidate["id"]
                break
            except Stopped:
                raise
            except Exception as exc:
                last_error = exc
            finally:
                logging.getLogger(__name__).info(
                    'agent_model model=%s round=%s elapsed_ms=%.1f',
                    candidate['id'], state['tool_rounds'], (perf_counter() - started) * 1000,
                )
        if response is None:
            reply = f"所有 Agent 模型均调用失败：{last_error}"
            return {
                "reply": reply,
                "engine": "langgraph-model-fallback-failed",
                "intent": "respond",
                "messages": [{"role": "assistant", "content": reply}],
            }
        message = _normalise_model_message(response)
        if summarizing:
            message.pop('tool_calls', None)
            if not message.get('content'):
                message['content'] = '本轮已达到工具预算，已有执行结果已保留；尚未生成总结，可发送“继续”接着处理。'
        if message.get('content'):event('text',str(message['content']))
        intent = "tools" if message.get("tool_calls") else "respond"
        chosen = next((item for item in state["model_candidates"] if item["id"] == active_model), state["model_config"])
        return {
            "messages": [message],
            "reply": str(message.get("content") or "") if not message.get("tool_calls") else "",
            "engine": f"langgraph:{active_model}",
            "active_model": active_model,
            "model_config": chosen,
            "intent": intent,
            "rag_context": "",
        }


def _inject_rag_context(
    outgoing: list[dict[str, Any]],
    rag_context: str,
) -> list[dict[str, Any]]:
    """Insert retrieval-augmented context right before the latest user message.

    The injected system message keeps the enhanced memory next to the user turn,
    which is required by OpenAI-compatible APIs and makes the augmentation visible
    to the model at the moment it matters most.
    """
    if not rag_context.strip():
        return outgoing
    system_note = {"role": "system", "content": f"[检索增强上下文]\n{rag_context}"}
    result = list(outgoing)
    last_user_idx = -1
    for idx in range(len(result) - 1, -1, -1):
        if result[idx].get("role") == "user":
            last_user_idx = idx
            break
    if last_user_idx >= 0:
        result.insert(last_user_idx, system_note)
    else:
        result.insert(0, system_note)
    return result
