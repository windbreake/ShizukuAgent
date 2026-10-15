from __future__ import annotations

from typing import Any
from time import perf_counter
import logging

from app.agent.llm import _content_to_text
from app.observability import get_observability_manager
from app.persona_store import build_system_prompt, load_persona, persona_id

IMAGE_HINT = "不要调用 read_file 去读 png/jpg/gif/webp。"


class AgentHarness:
    """Execution shell orchestrating the full agent session lifecycle:
    context assembly -> graph execution -> persistence -> response.

    The harness owns everything around the compiled LangGraph: loading history,
    retrieving memories, building prompts, resolving model candidates, persisting
    checkpoints and producing the public response payload.
    """

    def __init__(self, graph: Any) -> None:
        self.graph = graph

    @property
    def storage(self) -> Any:
        return self.graph.storage

    @property
    def dependencies(self) -> Any:
        return self.graph.dependencies

    def run(self, message: str, persona: str | None = None, thread_id: str | None = None,
            model_group: str | None = None, image: str | None = None,
            attachments: list[dict[str, Any]] | None = None, model_id: str | None = None,
            reasoning_effort: str = 'default') -> dict[str, Any]:
        from app.task_plans import execution
        current = persona_id(persona) if persona else self.graph.default_persona()
        thread = thread_id or f'persona:{current}'
        with execution(thread, current):
            return self._run(message, current, thread, model_group, image, attachments, model_id, reasoning_effort)

    def _run(
        self,
        message: str,
        persona: str | None = None,
        thread_id: str | None = None,
        model_group: str | None = None,
        image: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        model_id: str | None = None,
        reasoning_effort: str = "default",
    ) -> dict[str, Any]:
        started = perf_counter()
        timings = {}
        current = persona_id(persona) if persona else self.graph.default_persona()
        thread = thread_id or f"persona:{current}"
        checkpoint = self.storage.load_checkpoint(thread, current) or {"messages": []}
        history = [_sanitize_history(item) for item in checkpoint.get("messages") or []]
        user_content = _compose_user_content(message, image, attachments)
        history.append({"role": "user", "content": user_content})

        timings['history_ms'] = round((perf_counter() - started) * 1000, 1)
        stage = perf_counter()
        memories = self.storage.search_memories(message or current, persona=current, top_k=5)
        timings['memory_ms'] = round((perf_counter() - stage) * 1000, 1)
        memory_text = "\n".join(f"- {item.get('content')}" for item in memories) or "暂无长期记忆。"
        system_prompt = self._system_prompt(current, memory_text)
        model_candidates = ([self.dependencies.model_registry.resolve_model(model_id, for_agent=True)]
                            if model_id else self.dependencies.model_registry.resolve_agent_group(model_group))
        work = self.dependencies.settings.get('work_mode') or {}
        mode = 'full' if work.get('enabled') else 'sandbox' if work.get('sandbox_enabled') else 'chat'
        model_candidates = [{**candidate, "reasoning_effort": reasoning_effort, "workbench_mode": mode} for candidate in model_candidates]
        graph_messages = [{"role": "system", "content": system_prompt}, *history[-12:]]
        stage = perf_counter()
        result = self.graph.graph.invoke(
            {
                "messages": graph_messages,
                "thread_id": thread,
                "persona": current,
                "intent": "",
                "tool_result": [],
                "memory": {"thread_id": thread, "items": memories},
                "traces": [],
                "tool_rounds": 0,
                "engine": "langgraph",
                "reply": "",
                "model_config": model_candidates[0],
                "model_candidates": model_candidates,
                "active_model": model_candidates[0]["id"],
                "rag_context": "",
            },
            config={**get_observability_manager().invoke_config(thread, current), 'recursion_limit': 100},
        )

        timings['graph_ms'] = round((perf_counter() - stage) * 1000, 1)
        reply = result.get("reply") or "模型未返回内容。"
        stage = perf_counter()
        self._persist(thread, current, history, message, user_content, reply)
        timings['persist_ms'] = round((perf_counter() - stage) * 1000, 1)
        timings['total_ms'] = round((perf_counter() - started) * 1000, 1)
        logging.getLogger(__name__).info('agent_timing thread=%s timings=%s', thread, timings)
        return {
            "success": True,
            "persona": current,
            "reply": reply,
            "memory": memories,
            "engine": result.get("engine") or "langgraph",
            "trace": result.get("traces") or [],
            "active_model": result.get("active_model") or model_candidates[0]["id"],
            "thread_id": thread,
            "work_mode": mode,
            "timings": timings,
        }

    def _persist(
        self,
        thread: str,
        persona: str,
        history: list[dict[str, Any]],
        message: str,
        user_content: str,
        reply: str,
    ) -> None:
        """Persist session state. Persistence failures are degraded, not fatal:
        the generated reply should still reach the caller."""
        try:
            persisted_history = [*history, {"role": "assistant", "content": reply}][-40:]
            self.storage.save_checkpoint(thread, persona, {"messages": persisted_history})
            if thread != f'persona:{persona}':
                self.storage.save_checkpoint(f'persona:{persona}', persona, {"messages": persisted_history})
            self.storage.add_chat_record(persona, "user", message or _content_to_text(user_content))
            self.storage.add_chat_record(persona, "assistant", reply)
            if message and len(message) >= 12:
                self.storage.add_memory(persona, message, kind="long_term")
        except Exception:
            # Persistence is best-effort; never let it break the conversation.
            pass

    def reset_session(self, thread_id: str, persona: str | None = None) -> None:
        current = persona or self.graph.default_persona()
        self.storage.save_checkpoint(thread_id, current, {"messages": []})

    def get_history(self, thread_id: str, persona: str | None = None) -> list[dict[str, Any]]:
        current = persona or self.graph.default_persona()
        checkpoint = self.storage.load_checkpoint(thread_id, current) or {"messages": []}
        return [_sanitize_history(item) for item in checkpoint.get("messages") or []]

    def _system_prompt(self, persona: str, memory_text: str) -> str:
        persona_data = load_persona(f"{persona}.json") or {}
        prompt = build_system_prompt(persona_data)
        work = self.dependencies.settings.get("work_mode") or {}
        mode = "允许执行文件与工具操作，但仍按当前人格说话。" if work.get("enabled") else "不要执行危险系统操作，以当前人格正常聊天。"
        return (
            f"{prompt}\n\n[工作模式]\n{mode}\n\n[长期记忆]\n{memory_text}\n\n"
            "你是 LangGraph 工具型 Agent。需要外部信息时先调用工具，再根据工具结果回答。"
            f"{IMAGE_HINT}"
            "\n[任务计划]\n多步骤执行任务开始时使用 todowrite 创建具体任务列表，"
            "只将当前步骤标为 in_progress，每完成一个步骤就更新。验证后才标为 completed。"
            "中断或失败时保留未完成状态，不要虚报完成；简单问答不需要计划。"
        )


def _compose_user_content(
    message: str,
    image: str | None,
    attachments: list[dict[str, Any]] | None,
) -> str:
    parts = [(message or "").strip()]
    if image:
        parts.append("[图片已忽略，请用文字描述图片内容]")
    for item in attachments or []:
        name = str(item.get("name") or item.get("filename") or "attachment")
        kind = str(item.get("type") or item.get("mime") or "").lower()
        if "image" in kind or name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
            parts.append(f"[图片附件已忽略: {name}]")
        else:
            parts.append(f"[附件: {name}]")
    return "\n".join(part for part in parts if part) or "（空消息）"


def _sanitize_history(message: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(message)
    cleaned["content"] = _content_to_text(cleaned.get("content")) or "（空消息）"
    cleaned.pop("tool_calls", None)
    cleaned.pop("tool_call_id", None)
    return cleaned
