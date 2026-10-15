from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.agent.agent_graph import get_agent_graph
from app.config import settings
from app.mcp_manager import get_mcp_manager
from app.paths import DATA_DIR, STATIC_DIR
from app.persona_store import (
    activate_persona as store_activate_persona,
    active_filename,
    delete_persona as store_delete_persona,
    list_personas as store_list_personas,
    load_persona,
    persona_id,
    save_persona,
)
from app.plugin_manager import get_plugin_manager
from app.skill_install import install_from_payload
from app.skill_manager import get_skill_manager
from app.storage.adapter import get_storage

router = APIRouter()
def _persona_filename(name: str) -> str:
    text = str(name or "").strip()
    return text if text.endswith(".json") else f"{text}.json"


@router.get("/api/personas")
async def list_personas():
    return store_list_personas()


@router.get("/api/personas/{filename}")
async def get_persona(filename: str):
    data = load_persona(filename)
    if not data:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return data


@router.post("/api/personas")
async def create_persona(payload: dict[str, Any]):
    filename = str(payload.get("filename") or "custom.json")
    content = payload.get("content") or {}
    saved = save_persona(filename, content)
    return {"success": True, "filename": saved}


@router.post("/api/personas/activate")
async def activate_persona(payload: dict[str, Any]):
    filename = payload.get("filename") or payload.get("persona_filename") or ""
    try:
        active = store_activate_persona(str(filename))
    except FileNotFoundError:
        return JSONResponse({"error": f"persona not found: {filename}"}, status_code=404)
    return {"success": True, "active": active}


@router.delete("/api/personas/{filename}")
async def delete_persona(filename: str):
    ok = store_delete_persona(filename)
    return {"success": ok}


@router.get("/api/personas/open-folder")
async def open_persona_folder():
    from app.paths import PERSONAS_DIR
    import os
    import sys
    import subprocess

    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            os.startfile(str(PERSONAS_DIR))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(PERSONAS_DIR)])
        else:
            subprocess.Popen(["xdg-open", str(PERSONAS_DIR)])
    except Exception:
        pass
    return {"success": True, "path": "plugins/personas"}


@router.get("/api/security/status")
async def security_status():
    security = settings.get("security", {}) or {}
    work = settings.get("work_mode", {}) or {}
    return {
        "ok": True,
        "global_admin_enabled": bool(work.get("enabled")),
        "level1_configured": bool(security.get("level1_password_hash") or work.get("password_hash")),
        "level2_configured": bool(security.get("level2_password_hash")),
        "passwords_configured": bool(
            security.get("initialized")
            or security.get("level1_password_hash")
            or work.get("password_hash")
        ),
        "sandbox_mode": "local",
        "platform": "windows",
        "has_docker": False,
        "has_wsl": False,
        "chat_settings": _chat_settings(),
    }


def _chat_settings() -> dict[str, Any]:
    work = settings.get("work_mode") or {}
    current = work.get("chat_settings") or {}
    return {
        "sandbox_show_agent_trace": bool(current.get("sandbox_show_agent_trace", True)),
        "sandbox_trace_collapsed": bool(current.get("sandbox_trace_collapsed", True)),
        "sandbox_show_back_to_top": bool(current.get("sandbox_show_back_to_top", True)),
        "deepseek_thinking_mode": bool(current.get("deepseek_thinking_mode", False)),
        "deepseek_reasoning_effort": str(current.get("deepseek_reasoning_effort") or "high"),
        "voice_reply_enabled": bool(current.get("voice_reply_enabled", False)),
    }


def _tts_settings() -> dict[str, Any]:
    chat = _chat_settings()
    tts = settings.get("tts") or {}
    return {
        "success": True,
        "voice_reply_enabled": bool(chat.get("voice_reply_enabled")),
        "tts_enabled": bool(tts.get("enabled", True)),
        "auto_start": bool(tts.get("auto_start", False)),
        "api_base": tts.get("api_base") or "",
        "service_online": False,
        "detail": "TTS service is optional in remake",
        "ref_audio_exists": False,
        "ref_audio_path": tts.get("ref_audio_path") or "",
        "target_language": tts.get("target_language") or "ja",
        "lang_label": tts.get("lang_label") or "日本語",
        "languages": [
            {"code": "ja", "label": "日本語"},
            {"code": "zh", "label": "中文"},
            {"code": "en", "label": "English"},
        ],
    }


@router.post("/api/security/authenticate/level1")
@router.post("/api/security/authenticate/level2")
async def security_auth(payload: dict[str, Any] | None = None):
    return {"ok": True, "session_id": "local-dev", "level": 1, "message": "Authentication skipped in remake"}


@router.get("/api/sandbox/external_approvals")
async def sandbox_approvals():
    return {"success": True, "items": []}


@router.post("/api/sandbox/external_approvals/{request_id}")
@router.post("/api/sandbox/open_path")
@router.post("/api/sandbox/open_url")
@router.post("/api/sandbox/execute")
async def sandbox_actions():
    return {"success": True}


@router.get("/api/chat_settings/deepseek_thinking")
async def get_thinking_mode():
    chat = _chat_settings()
    effort = str(chat.get("deepseek_reasoning_effort") or "high").lower()
    if effort not in {"high", "max"}:
        effort = "high"
    return {
        "success": True,
        "thinking_mode": bool(chat.get("deepseek_thinking_mode")),
        "reasoning_effort": effort,
    }


@router.post("/api/chat_settings/deepseek_thinking")
async def set_thinking_mode(payload: dict[str, Any] | None = None):
    data = payload or {}
    enable = bool(data.get("enable", False))
    effort = str(data.get("reasoning_effort") or "high").lower()
    if effort not in {"high", "max"}:
        effort = "high"
    work = dict(settings.get("work_mode") or {})
    chat = dict(work.get("chat_settings") or {})
    chat["deepseek_thinking_mode"] = enable
    chat["deepseek_reasoning_effort"] = effort
    work["chat_settings"] = chat
    settings.update({"work_mode": work})
    return {
        "success": True,
        "thinking_mode": enable,
        "reasoning_effort": effort,
        "message": f"思考模式已{'启用' if enable else '禁用'}",
    }


@router.get("/api/tts/settings")
async def get_tts_settings():
    return _tts_settings()


@router.post("/api/tts/settings")
async def set_tts_settings(payload: dict[str, Any] | None = None):
    data = payload or {}
    enabled = bool(data.get("voice_reply_enabled", False))
    work = dict(settings.get("work_mode") or {})
    chat = dict(work.get("chat_settings") or {})
    chat["voice_reply_enabled"] = enabled
    work["chat_settings"] = chat
    language = str(data.get('target_language') or (settings.get('tts') or {}).get('target_language') or 'ja')
    labels = {'zh': '中文', 'ja': '日本語', 'en': 'English'}
    if language not in labels:
        return JSONResponse({'success': False, 'error': '不支持的目标语言'}, status_code=400)
    settings.update({"work_mode": work, "tts": {**(settings.get("tts") or {}), "enabled": enabled, 'target_language': language, 'lang_label': labels[language]}})
    result = _tts_settings()
    result["voice_reply_enabled"] = enabled
    result["tts"] = settings.get("tts") or {}
    return result


@router.get("/api/tts/status")
async def tts_status(autostart: int = 0, persona_filename: str = ""):
    result = _tts_settings()
    result["service_online"] = False
    result["autostart"] = bool(autostart)
    result["persona_filename"] = persona_filename or ""
    return result


@router.post("/api/tts/start")
async def tts_start():
    return {"success": True, "message": "TTS 未接入独立服务，开关已保存"}


@router.get("/api/tts/languages")
async def tts_languages():
    cfg = _tts_settings()
    return {
        "success": True,
        "languages": cfg["languages"],
        "current": cfg["target_language"],
        "current_label": cfg["lang_label"],
    }


@router.get("/api/plugins/status")
async def plugins_status():
    return {"success": True, "status": get_plugin_manager().get_framework_status()}


@router.post("/api/plugins/reload")
async def plugins_reload():
    get_plugin_manager().reload()
    return {"success": True, "status": get_plugin_manager().get_framework_status(), "message": "Plugin framework reloaded"}


@router.post("/api/plugins/policy")
async def plugins_policy(payload: dict[str, Any]):
    name = str(payload.get("plugin_name") or "").strip()
    if not name:
        return JSONResponse({"success": False, "error": "plugin_name is required"}, status_code=400)
    try:
        policy = get_plugin_manager().update_policy(name, payload.get("policy") or {})
    except KeyError:
        return JSONResponse({"success": False, "error": f"plugin not found: {name}"}, status_code=404)
    return {"success": True, "plugin_name": name, "policy": policy}


@router.get("/api/plugins/config")
@router.post("/api/plugins/config")
async def plugins_config(plugin_name: str | None = None, payload: dict[str, Any] | None = None):
    return {"success": True, "plugin_name": plugin_name or (payload or {}).get("plugin_name"), "config": {}}


@router.get("/api/plugins/ui-extensions")
@router.get("/api/plugins/ui-extensions/menu")
@router.get("/api/plugins/ui-extensions/pages")
@router.get("/api/plugins/ui-extensions/settings")
@router.get("/api/plugins/ui-extensions/widgets")
async def plugin_ui_extensions():
    return {"success": True, "extensions": [], "items": []}


@router.get("/api/systems/tasks")
@router.post("/api/systems/tasks")
@router.get("/api/systems/knowledge")
@router.get("/api/systems/knowledge/entries")
@router.get("/api/systems/instructions")
@router.get("/api/systems/system-status")
async def systems_stub():
    return {
        "success": True,
        "code": 0,
        "data": [],
        "items": [],
        "tasks": [],
        "status": {"ok": True, "storage": get_storage().status()},
    }


@router.get("/api/systems/plugins")
async def systems_plugins():
    plugins = get_plugin_manager().list_plugins()
    return {"success": True, "code": 0, "data": plugins}


@router.get("/api/systems/skills")
async def systems_skills():
    skills = get_skill_manager().list_skills()
    return {"success": True, "code": 0, "data": skills}


@router.get("/api/systems/mcp")
@router.get("/api/systems/mcp/servers")
async def systems_mcp():
    servers = get_mcp_manager().list_servers()
    return {"success": True, "code": 0, "data": servers}


@router.post("/api/systems/mcp/servers")
async def create_mcp_server(payload: dict[str, Any]):
    server = get_mcp_manager().upsert(payload)
    return {"success": True, "code": 0, "data": server.__dict__}


@router.get("/api/systems/mcp/servers/{server_id}")
async def get_mcp_server(server_id: str):
    for item in get_mcp_manager().list_servers():
        if item.get("id") == server_id:
            return {"success": True, "code": 0, "data": item}
    return JSONResponse({"success": False, "code": 1, "message": "not found"}, status_code=404)


@router.put("/api/systems/mcp/servers/{server_id}")
async def update_mcp_server(server_id: str, payload: dict[str, Any] | None = None):
    server = get_mcp_manager().update(server_id, payload or {})
    if not server:
        return JSONResponse({"success": False, "code": 1, "message": "not found"}, status_code=404)
    return {"success": True, "code": 0, "message": "Server updated", "data": server.__dict__}


@router.delete("/api/systems/mcp/servers/{server_id}")
async def delete_mcp_server(server_id: str):
    ok = get_mcp_manager().delete(server_id)
    return {"success": ok, "code": 0 if ok else 1}


def _agent_payload(agent_id: str = "") -> dict[str, Any]:
    from app.local_agents import detect_agents

    agents = detect_agents()
    if agent_id:
        agents = [item for item in agents if item["id"] == agent_id or agent_id in item["commands"]]
    installed = [item for item in agents if item.get("installed")]
    first = agents[0] if agents else {}
    return {
        "success": True,
        "code": 0,
        "installed": bool(installed),
        "cli": first.get("path") or "",
        "version": first.get("version") or "",
        "mode": "local-agent",
        "data": first or {"installed": False, "cli": "", "version": "", "mode": "local-agent"},
        "agents": agents,
    }


@router.get("/api/systems/agents")
@router.get("/api/systems/cli")
async def list_local_agents():
    payload = _agent_payload()
    return payload


@router.get("/api/systems/cli/{cli_name}/status")
async def local_agent_status(cli_name: str = ""):
    return _agent_payload(cli_name)


@router.post("/api/systems/agents/{agent_id}/run")
async def run_local_agent(agent_id: str, payload: dict[str, Any] | None = None):
    from app.local_agents import run_agent

    data = payload or {}
    return run_agent(agent_id, str(data.get("prompt") or data.get("message") or "status"))


@router.post("/api/systems/knowledge/entries")
@router.get("/api/systems/knowledge/entries/{entry_id}")
@router.post("/api/systems/knowledge/entries/{entry_id}")
@router.delete("/api/systems/knowledge/entries/{entry_id}")
async def knowledge_entries(entry_id: str = ""):
    return {"success": True, "code": 0, "data": [], "id": entry_id}


@router.get("/api/systems/personalities")
@router.post("/api/systems/personalities")
async def systems_personalities(payload: dict[str, Any] | None = None):
    items = store_list_personas().get("personas") or []
    return {"success": True, "code": 0, "data": items}


@router.get("/api/skills/market/github")
@router.get("/api/skills/market/local")
async def market_search(request: Request, page: int = 1, page_size: int = 24, query: str = ""):
    if "github" in request.url.path:
        from app.skill_install import search_github_skills

        return search_github_skills(query, page, page_size)
    items = []
    for skill in get_skill_manager().list_skills():
        name = str(skill.get("name") or skill.get("skill_id") or "")
        desc = str(skill.get("description") or "")
        if query and query.lower() not in f"{name} {desc}".lower():
            continue
        items.append(
            {
                "id": skill.get("skill_id"),
                "name": name,
                "description": desc,
                "external_url": "",
                "source": "local",
            }
        )
    start = max(page - 1, 0) * page_size
    sliced = items[start : start + page_size]
    return {
        "success": True,
        "code": 0,
        "items": sliced,
        "data": sliced,
        "page": page,
        "page_size": page_size,
        "total": len(items),
        "has_more": start + page_size < len(items),
        "source": "local",
        "diagnostics": {
            "cache": {"count": len(items), "age_seconds": 0},
            "sources": [{"source": "local", "ok": True, "count": len(items)}],
            "errors": [],
        },
    }


@router.post("/api/skills/market/github/install")
@router.post("/api/skills/market/agent-deploy")
async def market_install(payload: dict[str, Any]):
    result = install_from_payload(payload)
    result["message"] = f"Skill 已安装: {result.get('skill_id')}"
    result["job_id"] = result.get("skill_id")
    result["status"] = "success"
    return result


@router.get("/api/skills/market/agent-deploy/jobs/{job_id}")
async def market_install_job(job_id: str):
    return {"success": True, "job_id": job_id, "status": "success"}


@router.post("/api/skills/upload")
async def skills_upload(payload: dict[str, Any] | None = None):
    result = install_from_payload(payload or {})
    result["message"] = f"Skill 已加载: {result.get('skill_id')}"
    return result


@router.delete("/api/systems/tasks/{task_id}")
async def delete_task(task_id: str):
    return {"success": True, "id": task_id}


@router.get("/api/gateway/diagnose")
async def gateway_diagnose():
    return {"success": True, "adapter": {"models": True}, "message": "remake gateway ready"}


@router.post("/api/database/query")
async def database_query(payload: dict[str, Any] | None = None):
    from app.storage.adapter import run_sql

    data = payload or {}
    return run_sql(str(data.get("query") or ""), data.get("database") if isinstance(data.get("database"), dict) else None)


@router.post("/api/database/test")
async def database_test(payload: dict[str, Any] | None = None):
    from app.storage.adapter import probe_database

    result = probe_database(payload or {})
    return {"success": bool(result.get("overall_ok")), "database_test": result}


@router.post("/api/run_mode")
async def run_mode():
    return {"success": True}


@router.get("/api/realtime_search/subscriptions")
@router.post("/api/realtime_search/subscriptions")
@router.get("/api/realtime_search/updates")
async def realtime_search_stub():
    return {"success": True, "items": []}


@router.delete("/api/realtime_search/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: str):
    return {"success": True}





@router.get("/api/status")
async def api_status():
    graph = get_agent_graph()
    return {
        "status": "ShizukuClaw Remake Backend Running",
        "version": "1.0.0",
        "docs": "/docs",
        "storage": get_storage().status(),
        "persona": graph.default_persona(),
        "skills": get_skill_manager().list_skills(),
        "mcp": get_mcp_manager().list_servers(),
    }


def mount_static(app) -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _sse(event_name: str, payload: Any) -> str:
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_name}\ndata: {body}\n\n"
