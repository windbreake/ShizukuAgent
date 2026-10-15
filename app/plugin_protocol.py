from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PLUGIN_KINDS = ("core", "skill", "mcp", "observability")


@dataclass(slots=True)
class PluginDescriptor:
    """Unified plugin metadata shared across all plugin families."""

    id: str
    name: str
    kind: str
    version: str
    description: str
    author: str
    enabled: bool
    path: str
    manifest_path: str
    dependencies: list[str] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)
    hooks: list[str] = field(default_factory=list)

    @classmethod
    def from_manifest(cls, manifest_path: Path, kind: str, plugins_root: Path) -> "PluginDescriptor":
        data = read_manifest(manifest_path)
        plugin_id = str(data.get("id") or manifest_path.parent.name)
        try:
            relative_path = str(manifest_path.parent.relative_to(plugins_root))
        except ValueError:
            relative_path = str(manifest_path.parent)
        return cls(
            id=plugin_id,
            name=str(data.get("name") or plugin_id),
            kind=kind,
            version=str(data.get("version") or "0.1.0"),
            description=str(data.get("description") or ""),
            author=str(data.get("author") or ""),
            enabled=bool(data.get("enabled", True)),
            path=str(manifest_path.parent),
            manifest_path=str(manifest_path),
            dependencies=list(data.get("dependencies") or []),
            policy=dict(data.get("policy") or {}),
            hooks=list(data.get("hooks") or []),
        )


def read_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_handler_module(handler_dir: Path, module_prefix: str) -> Any:
    """Load ``handler.py`` from a plugin directory using importlib."""
    handler_path = handler_dir / "handler.py"
    if not handler_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"{module_prefix}_{handler_dir.name}", handler_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def top_level_kind(manifest_path: Path, plugins_root: Path) -> str | None:
    """Return the top-level plugin family directory for a manifest path."""
    try:
        relative = manifest_path.parent.relative_to(plugins_root)
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None