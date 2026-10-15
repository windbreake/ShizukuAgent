from __future__ import annotations

import hashlib
import hmac
import html
import os
import platform
import sys
import time
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.agent.agent_service import get_agent_service
from app.approvals import router as approval_router, session_scope, ApprovalDenied
from starlette.concurrency import run_in_threadpool
from app.workbench import router as workbench_router
from app.provider_routes import router as provider_router
from app.config import settings
from app.legacy_ui import mount_static, router as legacy_ui_router
from app.logging_setup import read_log_text, setup_logging
from app.model_registry import ModelRegistryError, model_registry
from app.mcp_manager import get_mcp_manager
from app.observability import get_observability_manager
from app.paths import ensure_runtime_dirs
from app.skill_manager import get_skill_manager
from app.storage.adapter import get_storage


STARTED_AT = time.time()
TOKEN_STATS = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
logger = setup_logging()
ensure_runtime_dirs()

app = FastAPI(title="ShizukuClaw Remake", version="1.0.0")
get_observability_manager().configure_all()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(legacy_ui_router)
app.include_router(approval_router)
app.include_router(workbench_router)
app.include_router(provider_router)
from app.settings_resources import router as settings_resources_router
app.include_router(settings_resources_router)
from app.gateway import router as gateway_router, require_api
from app.task_plans import router as task_plan_router
app.include_router(gateway_router)
app.include_router(task_plan_router)
from app.execution import router as execution_router
app.include_router(execution_router)
mount_static(app)


class ChatRequest(BaseModel):
    message: str
    persona: str | None = None
    thread_id: str | None = None
    model_group: str | None = None
    model_id: str | None = None
    reasoning_effort: str = Field(default="default", pattern="^(default|low|medium|high)$")


class ConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")
    database: dict[str, Any] | None = None
    api_keys: dict[str, Any] | None = None
    character: dict[str, Any] | None = None
    storage: dict[str, Any] | None = None
    llm: dict[str, Any] | None = None


class RecordDeleteRequest(BaseModel):
    id: int


class DeleteFirstNRequest(BaseModel):
    n: int = Field(ge=1)


class ExecCmdRequest(BaseModel):
    cmd: str


class SecurityPasswordRequest(BaseModel):
    level1_password: str
    level2_password: str


class MemoryCreateRequest(BaseModel):
    content: str
    persona: str | None = None
    kind: str = "long_term"


def _storage():
    return get_storage()


def _graph():
    return _agent_service().graph


def _agent_service():
    return get_agent_service()


def _skills():
    return get_skill_manager()


def _mcp():
    return get_mcp_manager()


def _hash_password(value: str) -> str:
    salt = os.urandom(16)
    rounds = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", (value or "").encode("utf-8"), salt, rounds)
    return f"pbkdf2${rounds}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    if hashed.startswith("pbkdf2$"):
        try:
            _, rounds, salt_hex, digest_hex = hashed.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(rounds),
            )
            return hmac.compare_digest(digest.hex(), digest_hex)
        except Exception:
            return False
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, hashed)


def _safe_psutil():
    try:
        import psutil

        return psutil
    except Exception:
        return None


@app.get("/api/backend/status")
async def backend_status() -> dict[str, Any]:
    return {
        "status": "ShizukuClaw Remake Backend Running",
        "version": "1.0.0",
        "docs": "/docs",
        "storage": _storage().status(),
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "uptime": int(time.time() - STARTED_AT)}


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    require_api()
    return {
        "object": "list",
        "data": [
            {"id": item["id"], "object": "model", "owned_by": item.get("provider", "shizukuclaw"), "capabilities": item.get("capabilities", [])}
            for item in model_registry.list_agent_models()
        ],
    }


@app.get("/api/models")
async def managed_models() -> dict[str, Any]:
    return {"success": True, "models": model_registry.snapshot()["models"], "providers": model_registry.snapshot()["providers"]}


@app.get("/api/model-groups")
async def model_groups() -> dict[str, Any]:
    snapshot = model_registry.snapshot()
    return {"success": True, "default": snapshot["default_model_group"], "groups": snapshot["model_groups"]}


@app.get("/api/auxiliary-apis")
async def auxiliary_apis() -> dict[str, Any]:
    return {"success": True, "apis": model_registry.snapshot()["auxiliary_apis"]}


@app.post("/api/model-registry")
async def update_model_registry(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"success": True, **model_registry.update(payload)}
    except ModelRegistryError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)


@app.post("/api/auxiliary/{api_id}")
async def call_auxiliary_api(api_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke search, speech, image, or another non-agent model endpoint."""
    try:
        config = model_registry.resolve_auxiliary(api_id)
    except ModelRegistryError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    model = config["model_config"]
    provider = model["provider_config"]
    api_key = provider.get("api_key") or os.getenv("OPENAI_API_KEY") or ""
    if not api_key:
        return JSONResponse({"success": False, "error": "auxiliary API provider has no API key"}, status_code=503)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=provider.get("base_url") or None)
        model_name = model.get("model")
        if api_id == "speech":
            response = client.audio.speech.create(
                model=model_name,
                voice=payload.get("voice") or "alloy",
                input=str(payload.get("input") or payload.get("text") or ""),
                response_format=payload.get("format") or "mp3",
            )
            import base64

            return {"success": True, "type": "audio", "format": payload.get("format") or "mp3", "data": base64.b64encode(response.read()).decode("ascii")}
        if api_id == "images":
            response = client.images.generate(
                model=model_name,
                prompt=str(payload.get("prompt") or ""),
                size=payload.get("size") or "1024x1024",
                n=int(payload.get("n") or 1),
            )
            return {"success": True, "type": "images", "data": [item.model_dump() for item in response.data]}

        messages = payload.get("messages") or [{"role": "user", "content": str(payload.get("query") or payload.get("input") or "")}]
        response = client.chat.completions.create(model=model_name, messages=messages)
        return {"success": True, "type": api_id, "data": response.model_dump()}
    except Exception as exc:
        logger.exception("auxiliary API failed: %s", api_id)
        return JSONResponse({"success": False, "error": str(exc)}, status_code=502)


@app.post("/v1/chat/completions")
async def chat_completions(payload: dict[str, Any]) -> dict[str, Any]:
    require_api()
    messages = payload.get("messages") or []
    user_text = ""
    for item in reversed(messages):
        if item.get("role") == "user":
            user_text = item.get("content") or ""
            break
    result = _agent_service().run(
        user_text or "hello",
        persona=payload.get("persona"),
        thread_id=payload.get("thread_id"),
        model_group=payload.get("model_group"),
    )
    TOKEN_STATS["input_tokens"] += max(len(user_text) // 4, 1)
    TOKEN_STATS["output_tokens"] += max(len(result["reply"]) // 4, 1)
    TOKEN_STATS["total_tokens"] = TOKEN_STATS["input_tokens"] + TOKEN_STATS["output_tokens"]
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": result.get("engine", "langgraph").removeprefix("langgraph:") if result.get("engine") else payload.get("model"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["reply"]},
                "finish_reason": "stop",
            }
        ],
    }


@app.post("/api/chat")
async def api_chat(body: ChatRequest) -> dict[str, Any]:
    def execute():
        persona=body.persona or _agent_service().default_persona()
        with session_scope(body.thread_id,persona):
            try:
                return _agent_service().run(body.message, persona=persona, thread_id=body.thread_id, model_group=body.model_group, model_id=body.model_id, reasoning_effort=body.reasoning_effort)
            except ApprovalDenied as error:
                return {'success':True,'persona':persona,'reply':str(error),'trace':[],'engine':'permission-rejected'}
    result = await run_in_threadpool(execute)
    TOKEN_STATS["input_tokens"] += max(len(body.message) // 4, 1)
    TOKEN_STATS["output_tokens"] += max(len(result["reply"]) // 4, 1)
    TOKEN_STATS["total_tokens"] = TOKEN_STATS["input_tokens"] + TOKEN_STATS["output_tokens"]
    logger.info("chat persona=%s engine=%s", result.get("persona"), result.get("engine"))
    return result


@app.get("/api/agent/status")
async def agent_status() -> dict[str, Any]:
    graph = _graph()
    return {
        "success": True,
        "personas": graph.available_personas(),
        "default_persona": graph.default_persona(),
        "storage": _storage().status(),
        "skills": _skills().list_skills(),
        "mcp": _mcp().list_servers(),
    }


@app.get("/api/observability")
async def observability_status() -> dict[str, Any]:
    manager = get_observability_manager()
    return {"success": True, "plugins": manager.status_all()}


@app.get("/api/agent/memory/long_term")
async def long_term_memory(
    include_meta: int = Query(default=0),
    persona: str | None = None,
) -> dict[str, Any]:
    items = _storage().list_memories(persona=persona, kind="long_term", limit=50)
    text = "\n".join(item.get("content", "") for item in items)
    payload: dict[str, Any] = {"success": True, "long_term": text}
    if include_meta:
        payload["meta"] = {"count": len(items), "items": items, "persona": persona}
    return payload


@app.post("/api/agent/memory")
async def create_memory(body: MemoryCreateRequest) -> dict[str, Any]:
    persona = body.persona or _graph().default_persona()
    memory_id = _storage().add_memory(persona, body.content, kind=body.kind)
    return {"success": True, "id": memory_id}


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    data = settings.as_dict()
    llm = data.get("llm", {}) or {}
    registry = model_registry.snapshot()
    return {
        "database": {
            "engine": (data.get("database") or {}).get("engine") or "sqlite",
            "host": (data.get("database") or {}).get("host") or "",
            "user": (data.get("database") or {}).get("user") or "",
            "password": (data.get("database") or {}).get("password") or "",
            "database": (data.get("database") or {}).get("database") or "data/storage/agent.db",
            "port": (data.get("database") or {}).get("port") or 0,
        },
        "api_keys": {
            "primary": {
                "key": "",
                "base_url": llm.get("base_url") or "",
                "model": llm.get("model") or "",
            }
        },
        "character": data.get("character", {}),
        "storage": data.get("storage", {}),
        "llm": {
            "provider": llm.get("provider") or "openai_compatible",
            "model": llm.get("model") or "",
            "base_url": llm.get("base_url") or "",
            "api_key": "",
            "has_api_key": bool(llm.get("api_key")),
        },
        "providers": registry["providers"],
        "models": registry["models"],
        "model_groups": registry["model_groups"],
        "default_model_group": registry["default_model_group"],
        "auxiliary_apis": registry["auxiliary_apis"],
    }


@app.post("/api/config")
async def save_config(body: ConfigUpdate) -> dict[str, Any]:
    incoming = {k: v for k, v in body.model_dump().items() if v is not None}
    llm = dict(incoming.get("llm") or {})
    primary = ((incoming.get("api_keys") or {}).get("primary") or {})
    if not llm.get("model"):
        llm["model"] = primary.get("model") or settings.get("llm", {}).get("model")
    if not llm.get("base_url"):
        llm["base_url"] = primary.get("base_url") or settings.get("llm", {}).get("base_url")
    submitted_key = llm.get("api_key") or primary.get("key") or ""
    if not submitted_key or submitted_key == "***":
        llm["api_key"] = settings.get("llm", {}).get("api_key") or ""
    else:
        llm["api_key"] = submitted_key
    llm["provider"] = "openai_compatible"
    incoming["llm"] = llm
    incoming["api_keys"] = {
        "primary": {
            "key": llm.get("api_key") or "",
            "base_url": llm.get("base_url") or "",
            "model": llm.get("model") or "",
        }
    }
    if incoming.get("database"):
        db = dict(incoming["database"])
        engine = str(db.get("engine") or "sqlite").lower()
        incoming["storage"] = {
            **(settings.get("storage") or {}),
            "driver": "postgresql" if engine.startswith("postgres") else engine,
        }
        if engine in {"mysql", "postgresql", "postgres"}:
            key = "postgresql" if engine.startswith("postgres") else "mysql"
            incoming["storage"][key] = {
                "host": db.get("host") or "127.0.0.1",
                "port": int(db.get("port") or (5432 if engine.startswith("postgres") else 3306)),
                "user": db.get("user") or "",
                "password": db.get("password") or "",
                "database": db.get("database") or "shizukuclaw",
            }
    settings.update(incoming)
    model_name = str(llm.get("model") or "gpt-4o-mini")
    capabilities = ["chat", "tools"]
    if model_name.lower() != "u2-flash":
        capabilities.append("vision")
    model_registry.update(
        {
            "providers": {
                "openai": {
                    "name": "OpenAI Compatible",
                    "type": "openai_compatible",
                    "base_url": llm.get("base_url") or "https://api.openai.com/v1",
                    "api_key": llm.get("api_key") or "",
                }
            },
            "models": {
                "primary": {
                    "provider": "openai",
                    "model": model_name,
                    "name": "Primary Agent Model",
                    "capabilities": capabilities,
                    "enabled": True,
                    "auxiliary_only": False,
                }
            },
            "model_groups": {"default": {"name": "Default Agent", "purpose": "agent", "strategy": "fallback", "models": ["primary"]}},
            "default_model_group": "default",
        }
    )
    logger.info("config updated: %s", list(incoming.keys()))
    from app.storage.adapter import probe_database

    db_test = probe_database(incoming.get("database") or settings.get("database") or {})
    return {"success": True, "database_test": db_test}


@app.get("/api/records")
async def get_records(limit: int = 200, offset: int = 0, persona_filename: str | None = None) -> list[dict[str, Any]]:
    persona = persona_filename.removesuffix('.json') if persona_filename else None
    return _storage().list_records(limit=limit, offset=offset, persona=persona)


@app.get('/api/record-groups')
def record_groups(query: str = ''):
    return {'success': True, 'items': _storage().record_groups(query)}


@app.get('/api/persona-records')
def persona_records(persona: str, page: int = 1, page_size: int = 20, query: str = ''):
    page_size = max(1, min(page_size, 100))
    groups = _storage().record_groups(query)
    total = next((item['total'] for item in groups if item['persona'] == persona), 0)
    page = max(1, min(page, max(1, (total + page_size - 1) // page_size)))
    return {'success': True, 'items': _storage().list_records(limit=page_size, offset=(page-1)*page_size, persona=persona, query=query), 'total': total, 'page': page}


@app.post("/api/delete_record")
async def delete_record(body: RecordDeleteRequest) -> dict[str, Any]:
    ok = _storage().delete_record(body.id)
    return {"success": ok}


@app.post("/api/clear_records")
async def clear_records() -> dict[str, Any]:
    _storage().clear_records()
    return {"success": True}


@app.post("/api/delete_first_n")
async def delete_first_n(body: DeleteFirstNRequest) -> dict[str, Any]:
    deleted = _storage().delete_first_n(body.n)
    return {"success": True, "deleted": deleted}


@app.get("/api/logs")
async def get_logs() -> PlainTextResponse:
    return PlainTextResponse(read_log_text())


@app.get("/api/adapter_logs")
async def adapter_logs() -> PlainTextResponse:
    return PlainTextResponse(read_log_text())


@app.get("/stream_logs")
async def stream_logs() -> StreamingResponse:
    def event_stream():
        last = ""
        while True:
            current = read_log_text()
            if current != last:
                added = current[len(last) :] if current.startswith(last) else current
                for line in added.splitlines():
                    if line.strip():
                        yield f"data: {line}\n\n"
                last = current
            time.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/monitoring")
async def monitoring() -> dict[str, Any]:
    psutil = _safe_psutil()
    cpu_percent = psutil.cpu_percent(interval=0.1) if psutil else 8.0
    memory_percent = psutil.virtual_memory().percent if psutil else 32.0
    total_memory = int(psutil.virtual_memory().total) if psutil else 0
    used_memory = int(psutil.virtual_memory().used) if psutil else 0
    return {
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "uptime": int(time.time() - STARTED_AT),
        "token_stats": TOKEN_STATS,
        "system_info": {
            "cpu": platform.processor() or platform.machine(),
            "cpu_count": os.cpu_count() or 0,
            "total_memory": total_memory,
            "used_memory": used_memory,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }


@app.get("/api/diagnosis")
async def diagnosis() -> HTMLResponse:
    storage = _storage().status()
    skills = _skills().list_skills()
    mcp = _mcp().list_servers()
    lines = [
        "<h3>ShizukuClaw 诊断结果</h3>",
        f"<p>时间: {datetime.now().isoformat(timespec='seconds')}</p>",
        f"<p>存储驱动: {html.escape(str(storage.get('driver')))} / ready={storage.get('ready')}</p>",
        f"<p>Skill 数量: {len(skills)}</p>",
        f"<p>MCP 数量: {len(mcp)}</p>",
        f"<p>默认人格: {html.escape(_graph().default_persona())}</p>",
        f"<p>Python: {html.escape(sys.version.split()[0])} / {html.escape(platform.platform())}</p>",
    ]
    return HTMLResponse("".join(lines))


@app.post("/api/exec_cmd")
async def exec_cmd(body: ExecCmdRequest) -> HTMLResponse:
    allowed = {"dir", "ls", "pwd", "whoami", "hostname", "python --version", "status"}
    cmd = body.cmd.strip()
    if cmd not in allowed and not cmd.startswith("echo "):
        text = f"安全限制: 当前仅允许只读诊断命令。收到: {cmd}"
        return HTMLResponse(f"<pre>{html.escape(text)}</pre>")
    if cmd == "status":
        text = f"driver={_storage().driver}\npersona={_graph().default_persona()}"
    elif cmd == "pwd":
        from app.paths import ROOT

        text = str(ROOT)
    else:
        import subprocess

        completed = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8)
        text = completed.stdout or completed.stderr or "(no output)"
    return HTMLResponse(f"<pre>{html.escape(text)}</pre>")


@app.get("/api/skills/status")
async def skills_status() -> dict[str, Any]:
    return {"success": True, "status": _skills().get_framework_status()}


@app.post("/api/skills/reload")
async def skills_reload() -> dict[str, Any]:
    _skills().reload()
    return {"success": True, "status": _skills().get_framework_status(), "message": "Skill framework reloaded"}


@app.post("/api/skills/policy")
async def skills_policy(payload: dict[str, Any]) -> dict[str, Any]:
    skill_id = str(payload.get("skill_id") or "").strip()
    if not skill_id:
        return JSONResponse({"success": False, "error": "skill_id is required"}, status_code=400)
    policy = _skills().update_skill_policy(skill_id, payload.get("policy") or {})
    return {"success": True, "skill_id": skill_id, "policy": policy}





@app.post("/api/security/config/set-passwords")
async def set_passwords(body: SecurityPasswordRequest) -> dict[str, Any]:
    if len(body.level1_password) < 8 or len(body.level2_password) < 8:
        return JSONResponse({"ok": False, "error": "密码至少 8 位"}, status_code=400)
    if body.level1_password == body.level2_password:
        return JSONResponse({"ok": False, "error": "两层密码不能相同"}, status_code=400)
    settings.update(
        {
            "security": {
                "initialized": True,
                "level1_password_hash": _hash_password(body.level1_password),
                "level2_password_hash": _hash_password(body.level2_password),
            }
        }
    )
    return {"ok": True}


@app.get("/api/work_mode/status")
async def work_mode_status() -> dict[str, Any]:
    from app.legacy_ui import _chat_settings
    from app.persona_store import active_filename

    wm = settings.get("work_mode") or {}
    return {
        "success": True,
        "enabled": bool(wm.get("enabled")),
        "global_enabled": bool(wm.get("enabled")),
        "sandbox_enabled": bool(wm.get("sandbox_enabled", False)),
        "has_password": bool(wm.get("password_hash") or (settings.get("security") or {}).get("level1_password_hash")),
        "active_persona": active_filename(),
        "features": wm.get("features") or {},
        "chat_settings": _chat_settings(),
        "reply_policy": wm.get("reply_policy") or {},
    }


class WorkModeToggleRequest(BaseModel):
    scope: str = "global"
    enable: bool | None = None
    password: str = ""
    mode: str | None = Field(default=None, pattern="^(chat|sandbox|full)$")


class WorkModePasswordRequest(BaseModel):
    password: str
    current_password: str = ""


class WorkModeOptionsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    features: dict[str, Any] | None = None
    chat_settings: dict[str, Any] | None = None
    reply_policy: dict[str, Any] | None = None


def _work_mode() -> dict[str, Any]:
    return dict(settings.get("work_mode") or {})


def _work_mode_password_hash() -> str:
    wm = _work_mode()
    return str(wm.get("password_hash") or (settings.get("security") or {}).get("level1_password_hash") or "")


@app.post("/api/work_mode/toggle")
async def work_mode_toggle(body: WorkModeToggleRequest | None = None) -> dict[str, Any]:
    payload = body or WorkModeToggleRequest()
    scope = (payload.scope or "global").strip().lower()
    wm = _work_mode()
    if payload.mode in {"chat", "sandbox"}:
        settings.update({"work_mode": {**wm, "enabled": False, "sandbox_enabled": payload.mode == "sandbox"}})
        return {"success": True, "mode": payload.mode, "enabled": False, "sandbox_enabled": payload.mode == "sandbox"}
    if payload.mode == "full":
        payload.enable = True
        scope = "global"
    if scope == "sandbox":
        enable = not bool(wm.get("sandbox_enabled")) if payload.enable is None else bool(payload.enable)
        settings.update({"work_mode": {**wm, "sandbox_enabled": enable}})
        return {"success": True, "scope": "sandbox", "enabled": enable}

    if scope not in {"global", ""}:
        return JSONResponse({"success": False, "error": "scope 必须是 sandbox 或 global"}, status_code=400)

    if payload.enable is None:
        enable = not bool(wm.get("enabled"))
    else:
        enable = bool(payload.enable)

    saved_hash = _work_mode_password_hash()
    if not saved_hash:
        return JSONResponse({"success": False, "error": "请先在设置中配置安全密码"}, status_code=400)
    if not _verify_password(payload.password, saved_hash):
        return JSONResponse({"success": False, "error": "安全密码错误"}, status_code=403)

    settings.update({"work_mode": {**wm, "enabled": enable, "sandbox_enabled": False, "password_hash": saved_hash}})
    return {"success": True, "scope": "global", "enabled": enable}


@app.post("/api/work_mode/password")
async def work_mode_password(body: WorkModePasswordRequest) -> dict[str, Any]:
    password = body.password or ""
    if len(password) < 6:
        return JSONResponse({"success": False, "error": "安全密码至少 6 位"}, status_code=400)
    wm = _work_mode()
    existing = str(wm.get("password_hash") or "")
    if existing and not _verify_password(body.current_password, existing):
        return JSONResponse({"success": False, "error": "旧密码错误，无法修改"}, status_code=403)
    settings.update({"work_mode": {**wm, "password_hash": _hash_password(password)}})
    return {"success": True, "message": "安全密码已设置"}


@app.post("/api/work_mode/options")
async def work_mode_options(body: WorkModeOptionsRequest) -> dict[str, Any]:
    wm = _work_mode()
    features = {**(wm.get("features") or {}), **(body.features or {})}
    chat_settings = {**(wm.get("chat_settings") or {}), **(body.chat_settings or {})}
    reply_policy = {**(wm.get("reply_policy") or {}), **(body.reply_policy or {})}
    settings.update(
        {
            "work_mode": {
                **wm,
                "features": features,
                "chat_settings": chat_settings,
                "reply_policy": reply_policy,
            }
        }
    )
    return {
        "success": True,
        "features": features,
        "chat_settings": chat_settings,
        "reply_policy": reply_policy,
    }


@app.post("/api/work_mode/reset_password_terminal")
async def work_mode_reset_password_terminal() -> dict[str, Any]:
    wm = _work_mode()
    wm.pop("password_hash", None)
    settings.update({"work_mode": wm})
    return {"success": True, "message": "已清除工作模式密码，请重新设置。"}


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error: %s", exc)
    return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
