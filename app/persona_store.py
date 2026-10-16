from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.paths import PERSONAS_DIR, ensure_runtime_dirs


def _safe_name(filename: str) -> str:
    name = Path(str(filename or "").strip()).name
    if not name.endswith(".json"):
        name += ".json"
    return name


def _persona_dir(filename: str) -> Path:
    return PERSONAS_DIR / Path(_safe_name(filename)).stem


def _write_persona_md(persona_dir: Path, data: dict[str, Any]) -> None:
    meta = data.get("meta") or {}
    char = data.get("character") or {}
    persona_id_value = persona_dir.name
    name = meta.get("name") or char.get("name") or persona_id_value
    description = meta.get("description") or ""
    version = meta.get("version") or "1.0"
    author = meta.get("author") or ""
    persona_dir.mkdir(parents=True, exist_ok=True)
    (persona_dir / "PERSONA.md").write_text(
        (
            "---\n"
            f"id: {persona_id_value}\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"version: {version}\n"
            f"author: {author}\n"
            "enabled: true\n"
            "---\n\n"
            f"# {name}\n\n"
            "用户自定义人格。人设数据在 persona.json。工作模式不写在这里。\n"
        ),
        encoding="utf-8",
    )


def ensure_personas() -> Path:
    ensure_runtime_dirs()
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    legacy = Path(__file__).resolve().parent.parent / "data" / "personas"
    if legacy.exists():
        for src in legacy.glob("*.json"):
            dest_dir = _persona_dir(src.name)
            dest = dest_dir / "persona.json"
            if not dest.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                try:
                    data = json.loads(dest.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
                _write_persona_md(dest_dir, data)
    if not any((path / "persona.json").exists() for path in PERSONAS_DIR.iterdir() if path.is_dir()):
        save_persona("shizuku.json", _default_persona())
    return PERSONAS_DIR


def _default_persona() -> dict[str, Any]:
    return {
        "meta": {"name": "小雫", "description": "默认人格", "version": "1.0", "author": "User"},
        "character": {
            "name": "小雫",
            "personality": "傲娇猫娘",
            "brother_qqid": "",
            "height": "",
            "weight": "",
            "catchphrases": "喵~",
        },
        "system_prompt": {"template": "你叫{name}，是一只{personality}。保持简洁自然。"},
        "reply_style": "像真人聊天，不要太工整。",
    }


def list_personas() -> dict[str, Any]:
    ensure_personas()
    active = settings.get("active_persona") or "shizuku.json"
    items = []
    for path in sorted(PERSONAS_DIR.glob("*/persona.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        filename = f"{path.parent.name}.json"
        meta = data.get("meta") or {}
        items.append(
            {
                "filename": filename,
                "name": meta.get("name") or data.get("character", {}).get("name") or path.parent.name,
                "description": meta.get("description") or "",
                "version": meta.get("version") or "1.0",
                "is_active": filename == active,
            }
        )
    if items and not any(item["is_active"] for item in items):
        items[0]["is_active"] = True
    return {"personas": items, "active": active}


def load_persona(filename: str) -> dict[str, Any] | None:
    ensure_personas()
    path = _persona_dir(filename) / "persona.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    data["filename"] = _safe_name(filename)
    document = path.parent / 'PERSONA.md'
    if not document.exists():
        document = path.parent / 'SKILL.md'
    if document.exists():
        data['_document'] = document.read_text(encoding='utf-8')
    return data


def save_persona(filename: str, content: dict[str, Any]) -> str:
    ensure_personas()
    name = _safe_name(filename)
    persona_dir = _persona_dir(name)
    persona_dir.mkdir(parents=True, exist_ok=True)
    (persona_dir / "persona.json").write_text(
        json.dumps(content or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not (persona_dir / 'PERSONA.md').exists():
        _write_persona_md(persona_dir, content or {})
    return name


def delete_persona(filename: str) -> bool:
    persona_dir = _persona_dir(filename)
    persona_file = persona_dir / "persona.json"
    if not persona_file.exists():
        return False
    persona_file.unlink()
    md_file = persona_dir / "PERSONA.md"
    if md_file.exists():
        md_file.unlink()
    return True


def activate_persona(filename: str) -> str:
    name = _safe_name(filename)
    if not (_persona_dir(name) / "persona.json").exists():
        raise FileNotFoundError(name)
    settings.update({"active_persona": name, "agent": {"default_persona": Path(name).stem}})
    return name


def active_filename() -> str:
    ensure_personas()
    name = settings.get("active_persona") or "shizuku.json"
    if not (_persona_dir(name) / "persona.json").exists():
        listed = list_personas()["personas"]
        return listed[0]["filename"] if listed else "shizuku.json"
    return _safe_name(name)


def persona_id(filename: str | None = None) -> str:
    return Path(filename or active_filename()).stem


def build_system_prompt(data: dict[str, Any] | None) -> str:
    data = data or {}
    char = data.get("character") or {}
    system = data.get('system_prompt') or {}
    template = (system if isinstance(system, str) else system.get('template')) or "你是{name}，性格是{personality}。"
    catch = str(char.get("catchphrases") or "")
    parts = [p.strip() for p in catch.replace("，", ",").split(",") if p.strip()]
    values = {
        "name": char.get("name") or data.get("meta", {}).get("name") or "助手",
        "personality": char.get("personality") or "",
        "brother_qqid": char.get("brother_qqid") or "",
        "catchphrases": catch,
        "first_catchphrase": parts[0] if parts else "",
        "second_catchphrase": parts[1] if len(parts) > 1 else (parts[0] if parts else ""),
    }
    try:
        prompt = template.format(**values)
    except Exception:
        prompt = template
    extras = []
    if data.get('_document'):
        extras.append('[人格文档]\n' + data['_document'])
    if data.get("reply_style"):
        extras.append(f"[回复风格]\n{data['reply_style']}")
    if data.get("plan_style"):
        extras.append(f"[行为规划]\n{data['plan_style']}")
    rules = data.get("behavior_rules") or []
    if rules:
        extras.append("[行为规则]\n" + "\n".join(f"- {item}" for item in rules))
    if extras:
        prompt += "\n\n" + "\n\n".join(extras)
    return prompt
