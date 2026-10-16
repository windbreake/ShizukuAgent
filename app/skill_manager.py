from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from app.paths import SKILLS_DIR, ensure_runtime_dirs


@dataclass
class SkillMeta:
    skill_id: str
    name: str
    description: str = ""
    version: str = "0.1.0"
    author: str = ""
    path: str = ""
    persona: bool = False
    enabled: bool = True
    tools: list[str] | None = None
    system_prompt: str = ""


class SkillManager:
    def __init__(self, skills_dir: Path | None = None) -> None:
        ensure_runtime_dirs()
        self.skills_dir = skills_dir or SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, SkillMeta] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._policies: dict[str, dict[str, Any]] = {}
        self._framework_enabled = True
        self.reload()

    def reload(self) -> dict[str, SkillMeta]:
        self._skills.clear()
        self._handlers.clear()
        for skill_file in sorted(self.skills_dir.rglob("SKILL.md")):
            meta = self._parse_skill_md(skill_file)
            if meta:
                self._skills[meta.skill_id] = meta
                self._policies.setdefault(meta.skill_id, {"enabled": meta.enabled, "allow_model_invocation": True})
                handler = self._load_handler(skill_file.parent)
                if handler:
                    self._handlers[meta.skill_id] = handler
        return self._skills

    def _parse_skill_md(self, path: Path) -> SkillMeta | None:
        text = path.read_text(encoding="utf-8")
        frontmatter: dict[str, Any] = {}
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter = self._parse_frontmatter(parts[1])
                body = parts[2].strip()
        skill_id = str(frontmatter.get("id") or path.parent.name)
        return SkillMeta(
            skill_id=skill_id,
            name=str(frontmatter.get("name") or skill_id),
            description=str(frontmatter.get("description") or ""),
            version=str(frontmatter.get("version") or "0.1.0"),
            author=str(frontmatter.get("author") or ""),
            path=str(path.parent),
            persona=bool(frontmatter.get("persona", False)),
            enabled=bool(frontmatter.get("enabled", True)),
            tools=list(frontmatter.get("tools") or []),
            system_prompt=str(frontmatter.get("system_prompt") or body),
        )

    def _parse_frontmatter(self, raw: str) -> dict[str, Any]:
        data: dict[str, Any] = {}
        current_list_key: str | None = None
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- ") and current_list_key:
                data.setdefault(current_list_key, []).append(stripped[2:].strip().strip('"'))
                continue
            match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", stripped)
            if not match:
                continue
            key, value = match.group(1), match.group(2).strip()
            if value == "":
                current_list_key = key
                data[key] = []
                continue
            current_list_key = None
            if value.lower() in {"true", "false"}:
                data[key] = value.lower() == "true"
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                data[key] = [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]
            else:
                data[key] = value.strip('"').strip("'")
        return data

    def _load_handler(self, skill_dir: Path) -> Callable[..., Any] | None:
        handler_path = skill_dir / "handler.py"
        if not handler_path.exists():
            return None
        spec = importlib.util.spec_from_file_location(f"skill_{skill_dir.name}", handler_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, "run", None)

    def list_skills(self) -> list[dict[str, Any]]:
        items = []
        for item in self._skills.values():
            if item.persona:
                continue
            payload = asdict(item)
            payload["policy"] = self.get_skill_policy(item.skill_id)
            items.append(payload)
        return items

    def get_skill_policy(self, skill_id: str) -> dict[str, Any]:
        return dict(self._policies.get(skill_id) or {"enabled": True, "allow_model_invocation": True})

    def update_skill_policy(self, skill_id: str, policy: dict[str, Any]) -> dict[str, Any]:
        current = self.get_skill_policy(skill_id)
        current.update({k: v for k, v in policy.items() if v is not None})
        current["enabled"] = bool(current.get("enabled", True))
        current["allow_model_invocation"] = bool(current.get("allow_model_invocation", True))
        self._policies[skill_id] = current
        skill = self._skills.get(skill_id)
        if skill is not None:
            skill.enabled = current["enabled"]
        return current

    def get_framework_status(self) -> dict[str, Any]:
        items = self.list_skills()
        return {
            "enabled": self._framework_enabled,
            "loaded_skills": [item["skill_id"] for item in items],
            "skills": items,
            "skills_dir": "plugins/skills",
            "skill_count": len(items),
            "degraded": False,
        }

    def set_framework_enabled(self, enabled: bool) -> None:
        self._framework_enabled = bool(enabled)

    def list_personas(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self._skills.values() if item.persona and item.enabled]

    def get(self, skill_id: str) -> SkillMeta | None:
        return self._skills.get(skill_id)

    def get_prompt(self, skill_id: str) -> str:
        skill = self.get(skill_id)
        return skill.system_prompt if skill else ""

    def invoke(self, skill_id: str, **kwargs: Any) -> Any:
        handler = self._handlers.get(skill_id)
        if handler is None:
            return None
        return handler(**kwargs)


_SKILL_MANAGER: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    global _SKILL_MANAGER
    if _SKILL_MANAGER is None:
        _SKILL_MANAGER = SkillManager()
    return _SKILL_MANAGER
