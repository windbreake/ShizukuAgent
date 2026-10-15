from __future__ import annotations

import concurrent.futures
import contextvars
import time
from app.execution import check, Stopped
from app.approvals import ApprovalDenied
from typing import Any, Callable

from app.agent.tools import OPENAI_TOOLS, TOOL_IMPLS

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)
DEFAULT_TOOL_TIMEOUT = 60.0


class ToolRegistry:
    """Registry of built-in and dynamically registered agent tools."""

    def __init__(self, tools: dict[str, Any] | None = None) -> None:
        self._tools: dict[str, Callable[..., Any]] = dict(tools or TOOL_IMPLS)
        self._dynamic_impls: dict[str, Callable[..., Any]] = {}
        self._definitions: dict[str, dict[str, Any]] = {}

    def names(self) -> list[str]:
        return sorted(self._tools)

    def contains(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> Callable[..., Any] | None:
        return self._tools.get(name)

    def register(self, name: str, impl: Callable[..., Any], definition: dict[str, Any]) -> None:
        self._tools[name] = impl
        self._dynamic_impls[name] = impl
        self._definitions[name] = dict(definition)

    def definitions(self) -> list[dict[str, Any]]:
        result = [
            dict(item)
            for item in OPENAI_TOOLS
            if (item.get("function") or {}).get("name") in self._tools
        ]
        for name in sorted(self._definitions):
            result.append(dict(self._definitions[name]))
        return result

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        persona: str = "shizuku",
        model_config: dict[str, Any] | None = None,
        storage: Any | None = None,
        timeout: float | None = DEFAULT_TOOL_TIMEOUT,
    ) -> dict[str, Any]:
        if name not in self._tools:
            return {"ok": False, "error": {"type": "unknown_tool", "message": f"未知工具: {name}"}}
        future = _EXECUTOR.submit(
            contextvars.copy_context().run, self._execute_inner, name, arguments, persona, model_config, storage
        )
        if name == 'use_auxiliary_model':
            timeout = 370  # Human wait has its own 300-second deadline.
        try:
            deadline=time.monotonic()+timeout if timeout is not None else None
            while True:
                check()
                remaining=deadline-time.monotonic() if deadline else None
                if remaining is not None and remaining<=0:raise concurrent.futures.TimeoutError()
                try:return future.result(timeout=min(.1,remaining) if remaining is not None else .1)
                except concurrent.futures.TimeoutError:
                    if future.done():raise
                    continue
        except Stopped:
            future.cancel()
            raise
        except concurrent.futures.TimeoutError:
            return {
                "ok": False,
                "error": {"type": "timeout", "message": f"工具执行超时（>{timeout} 秒）: {name}"},
            }
        except ApprovalDenied:
            raise
        except Exception as exc:
            return {"ok": False, "error": {"type": "execution_error", "message": str(exc)}}

    def _execute_inner(
        self,
        name: str,
        arguments: dict[str, Any],
        persona: str,
        model_config: dict[str, Any] | None,
        storage: Any | None,
    ) -> dict[str, Any]:
        check()
        impl = self._dynamic_impls.get(name)
        if impl is not None:
            try:
                value = impl(**dict(arguments or {}))
            except ApprovalDenied:
                raise
            except TypeError as exc:
                return {"ok": False, "error": {"type": "invalid_arguments", "message": str(exc)}}
            except Exception as exc:
                return {"ok": False, "error": {"type": "execution_error", "message": str(exc)}}
            if isinstance(value, dict) and "ok" in value:
                return dict(value)
            return {"ok": True, "value": value}
        from app.agent.tools import run_tool

        return run_tool(name, arguments, persona, model_config, storage)
