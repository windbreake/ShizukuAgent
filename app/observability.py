from __future__ import annotations

from pathlib import Path
from typing import Any

from app.paths import OBSERVABILITY_DIR, ensure_runtime_dirs
from app.plugin_protocol import PluginDescriptor, load_handler_module, read_manifest


class ObservabilityManager:
    """Loads observability plugins (e.g. LangSmith) from plugins/observability/.

    Each plugin directory contains ``plugin.json`` and an optional ``handler.py``
    exposing ``configure()``, ``status()`` and ``invoke_config(thread_id, persona)``.
    """

    def __init__(self, plugins_dir: Path | None = None) -> None:
        ensure_runtime_dirs()
        self.plugins_dir = plugins_dir or OBSERVABILITY_DIR
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._plugins: dict[str, PluginDescriptor] = {}
        self._handlers: dict[str, Any] = {}
        self.reload()

    def reload(self) -> dict[str, PluginDescriptor]:
        self._plugins.clear()
        self._handlers.clear()
        for plugin_file in sorted(self.plugins_dir.rglob("plugin.json")):
            descriptor = PluginDescriptor.from_manifest(
                plugin_file, kind="observability", plugins_root=self.plugins_dir
            )
            self._plugins[descriptor.id] = descriptor
            self._handlers[descriptor.id] = load_handler_module(plugin_file.parent, "observability")
        return self._plugins

    def list_plugins(self) -> list[dict[str, Any]]:
        return [
            {
                "id": plugin.id,
                "name": plugin.name,
                "kind": plugin.kind,
                "version": plugin.version,
                "description": plugin.description,
                "author": plugin.author,
                "enabled": plugin.enabled,
                "path": plugin.path,
            }
            for plugin in self._plugins.values()
        ]

    def configure_all(self) -> None:
        for plugin in self._plugins.values():
            if not plugin.enabled:
                continue
            configure = getattr(self._handlers.get(plugin.id), "configure", None)
            if callable(configure):
                try:
                    configure()
                except Exception:
                    continue

    def status_all(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for plugin in self._plugins.values():
            status: dict[str, Any] = {}
            handler = self._handlers.get(plugin.id)
            if handler is not None:
                status_fn = getattr(handler, "status", None)
                if callable(status_fn):
                    try:
                        status = status_fn() or {}
                    except Exception:
                        status = {}
            result.append(
                {
                    "id": plugin.id,
                    "name": plugin.name,
                    "description": plugin.description,
                    "version": plugin.version,
                    "enabled": plugin.enabled,
                    "path": plugin.path,
                    **status,
                }
            )
        return result

    def invoke_config(self, thread_id: str | None = None, persona: str | None = None) -> dict[str, Any]:
        config: dict[str, Any] = {"metadata": {}, "configurable": {}}
        for plugin in self._plugins.values():
            if not plugin.enabled:
                continue
            fn = getattr(self._handlers.get(plugin.id), "invoke_config", None)
            if not callable(fn):
                continue
            try:
                part = fn(thread_id, persona) or {}
            except Exception:
                continue
            metadata = part.get("metadata")
            if isinstance(metadata, dict):
                config["metadata"].update(metadata)
            configurable = part.get("configurable")
            if isinstance(configurable, dict):
                config["configurable"].update(configurable)
        if not config["metadata"]:
            config.pop("metadata", None)
        if not config["configurable"]:
            config.pop("configurable", None)
        return config


_OBSERVABILITY_MANAGER: ObservabilityManager | None = None


def get_observability_manager() -> ObservabilityManager:
    global _OBSERVABILITY_MANAGER
    if _OBSERVABILITY_MANAGER is None:
        _OBSERVABILITY_MANAGER = ObservabilityManager()
    return _OBSERVABILITY_MANAGER