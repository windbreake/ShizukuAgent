from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.paths import PLUGINS_DIR, ensure_runtime_dirs
from app.plugin_protocol import PluginDescriptor, read_manifest

# Plugin families that have their own dedicated managers.
EXCLUDED_KINDS = {"mcp", "skills", "observability"}


class PluginManager:
    """Manages generic core plugins (``plugin.json`` outside dedicated plugin families)."""

    def __init__(self, plugins_dir: Path | None = None, state_path: Path | None = None) -> None:
        ensure_runtime_dirs()
        self.plugins_dir = plugins_dir or PLUGINS_DIR
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = state_path or PLUGINS_DIR / "plugin_state.json"
        self._plugins: dict[str, PluginDescriptor] = {}
        self._enabled = True
        self.reload()

    def reload(self) -> dict[str, PluginDescriptor]:
        self._plugins.clear()
        for manifest in sorted(self.plugins_dir.rglob("plugin.json")):
            if self._should_skip(manifest):
                continue
            descriptor = PluginDescriptor.from_manifest(manifest, kind="core", plugins_root=self.plugins_dir)
            self._plugins[descriptor.name] = descriptor
        if "core.local" not in self._plugins:
            self._plugins["core.local"] = PluginDescriptor(
                id="core.local",
                name="core.local",
                kind="core",
                version="1.0.0",
                description="Remake 核心插件：聊天、人格、记忆、本地存储",
                author="ShizukuAgent",
                enabled=True,
                path=str(self.plugins_dir / "core"),
                manifest_path=str(self.plugins_dir / "core" / "plugin.json"),
                policy=self._default_policy({}),
                hooks=["chat", "memory"],
            )
        self._apply_state()
        return self._plugins

    def _should_skip(self, manifest: Path) -> bool:
        relative = self._relative_parts(manifest)
        return bool(relative and relative[0] in EXCLUDED_KINDS)

    def _relative_parts(self, manifest: Path) -> tuple[str, ...]:
        try:
            return manifest.parent.relative_to(self.plugins_dir).parts
        except ValueError:
            return ()

    def _default_policy(self, incoming: dict[str, Any]) -> dict[str, Any]:
        return {
            "enabled": bool(incoming.get("enabled", True)),
            "allow_network": bool(incoming.get("allow_network", False)),
            "max_execution_ms": int(incoming.get("max_execution_ms", 10000) or 10000),
            "allowed_domains": list(incoming.get("allowed_domains") or []),
            "allowed_commands": list(incoming.get("allowed_commands") or []),
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _apply_state(self) -> None:
        state = self._load_state()
        for name, plugin in self._plugins.items():
            entry = state.get(name)
            if isinstance(entry, dict) and "enabled" in entry:
                plugin.enabled = bool(entry["enabled"])
                plugin.policy["enabled"] = plugin.enabled

    def _save_state(self) -> None:
        state = {name: {"enabled": plugin.enabled} for name, plugin in self._plugins.items()}
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_plugins(self) -> list[dict[str, Any]]:
        return [
            {
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "author": plugin.author,
                "dependencies": plugin.dependencies,
                "project_path": plugin.path,
                "policy": self._plugin_policy(plugin),
                "hooks": plugin.hooks,
                "id": plugin.id,
                "kind": plugin.kind,
                "enabled": plugin.enabled,
            }
            for plugin in self._plugins.values()
        ]

    def _plugin_policy(self, plugin: PluginDescriptor) -> dict[str, Any]:
        return {**self._default_policy({}), **dict(plugin.policy or {})}

    def get_framework_status(self) -> dict[str, Any]:
        plugins = self.list_plugins()
        return {
            "enabled": self._enabled,
            "loaded_plugins": [item["name"] for item in plugins],
            "plugins": plugins,
            "commands": [],
            "degraded": False,
        }

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def update_policy(self, plugin_name: str, policy: dict[str, Any]) -> dict[str, Any]:
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            raise KeyError(plugin_name)
        plugin.policy = self._default_policy({**plugin.policy, **policy})
        plugin.enabled = bool(plugin.policy.get("enabled", True))
        self._save_state()
        return plugin.policy

    def set_plugin_enabled(self, plugin_name: str, enabled: bool) -> dict[str, Any]:
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            raise KeyError(plugin_name)
        plugin.enabled = bool(enabled)
        plugin.policy["enabled"] = plugin.enabled
        self._save_state()
        return plugin.policy


_PLUGIN_MANAGER: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    global _PLUGIN_MANAGER
    if _PLUGIN_MANAGER is None:
        _PLUGIN_MANAGER = PluginManager()
    return _PLUGIN_MANAGER
