from __future__ import annotations

from typing import Any

from app.agent.state import AgentState, message_as_dict
from app.agent.tool_registry import ToolRegistry
from app.agent.tools import parse_tool_arguments
from app.approvals import ask, grant, scope
from app.agent import tools
from pathlib import Path
from time import perf_counter
from app.execution import check, event
from app.agent.permissions import allowed


class ToolExecutorNode:
    name = "ToolExecutorNode"

    def __init__(self, storage: Any | None = None, registry: ToolRegistry | None = None) -> None:
        self.storage = storage
        self.registry = registry or ToolRegistry()

    def __call__(self, state: AgentState) -> dict[str, Any]:
        latest = message_as_dict(state["messages"][-1])
        messages = []
        traces = list(state["traces"])
        tool_result = list(state["tool_result"])
        for call in latest.get("tool_calls") or []:
            check()
            started = perf_counter()
            function = call.get("function") or {}
            name = str(function.get("name") or "")
            call_id = str(call.get("id") or f"{name}-{len(messages)}")
            event('tool',name,call_id=call_id,arguments=function.get('arguments') or '{}',status='running')
            validation_error = function.get("_validation_error")
            try:
                args = parse_tool_arguments(function.get("arguments"))
                validation_error = validation_error or args.pop("_validation_error", None)
                if validation_error:
                    raise ValueError(validation_error)
                mode = (state.get('model_config') or {}).get('workbench_mode')
                if not allowed(name, mode):
                    result = {'ok': False, 'error': {'type':'permission_denied','message':'当前模式不允许执行此工具；对话模式只读，安全模式禁止未隔离的外部代码执行'}}
                elif not self.registry.contains(name):
                    result = {"ok": False, "error": {"type": "unknown_tool", "message": f"未知工具: {name}"}}
                else:
                    approved=None
                    if name in {'read_file','list_dir'}:
                        target=(tools.WORKSPACE / str(args.get('path') or '.')).resolve()
                        approved=grant.set(str(target))
                    if name == 'write_file':
                        target=(tools.WORKSPACE / str(args.get('path') or '.')).resolve()
                        if not target.is_relative_to(tools.WORKSPACE.resolve()):
                            if mode == 'sandbox':
                                raise ValueError('安全模式只能修改沙箱工作区内的文件')
                            ask('external_directory',str(target));approved=grant.set(str(target))
                    if scope.get() and name in {'run_local_agent','call_mcp','run_skill'}:
                        ask('tool_execution',name+' '+str(args)[:2000])
                    try:
                        result = self.registry.execute(
                        name,
                        args,
                        persona=state["persona"],
                        model_config=state.get("model_config"),
                        storage=self.storage,
                        )
                    finally:
                        if approved is not None:grant.reset(approved)
            except ValueError as exc:
                args = {}
                result = {"ok": False, "error": {"type": "invalid_arguments", "message": str(exc)}}
            if not isinstance(result, dict) or "ok" not in result:
                result = {"ok": True, "value": result}
            if result.get("ok"):
                tool_text = str(result.get("value") or "")
            else:
                error = result.get("error") or {}
                tool_text = f"工具执行失败 [{error.get('type', 'unknown')}]: {error.get('message', '未知错误')}"
            traces.append({"tool": name, "call_id": call_id, "args": args, "ok": result.get("ok", False), "result": tool_text[:500], "elapsed_ms": round((perf_counter() - started) * 1000, 1)})
            event('tool',name,call_id=call_id,arguments=function.get('arguments') or '{}',status='completed' if result.get('ok') else 'error',result=tool_text[:12000])
            tool_result.append(tool_text)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": tool_text,
                }
            )
        return {
            "messages": messages,
            "traces": traces,
            "tool_result": tool_result,
            "tool_rounds": state["tool_rounds"] + int(any((call.get('function') or {}).get('name') not in {'todowrite', 'todoread'} for call in latest.get('tool_calls') or [])),
            "intent": "model",
        }
