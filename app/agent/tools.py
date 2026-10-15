from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Callable

from app.agent.llm import model_supports_vision
from app.paths import DATA_DIR
from app.storage.adapter import get_storage

WORKSPACE = DATA_DIR / "workspace"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tif", ".tiff"}


def _safe_path(raw: str) -> Path:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    target = (WORKSPACE / str(raw or "")).resolve()
    root = WORKSPACE.resolve()
    if root != target and root not in target.parents:
        from app.approvals import grant
        if grant.get()!=str(target):raise ValueError("path escapes workspace")
    return target


def tool_list_dir(path: str = ".") -> str:
    target = _safe_path(path)
    if not target.exists():
        return f"目录不存在: {path}"
    if not target.is_dir():
        return f"不是目录: {path}"
    items = []
    for child in sorted(target.iterdir()):
        if child.is_dir():
            items.append(f"{child.name}/")
        elif child.suffix.lower() in IMAGE_SUFFIXES:
            items.append(f"{child.name} [image, skip]")
        else:
            items.append(child.name)
    return "\n".join(items) or "(空目录)"


def encode_image_data_url(path: str | Path) -> str:
    target = path if isinstance(path, Path) else _safe_path(path)
    suffix = target.suffix.lower().lstrip(".") or "png"
    if suffix == "jpg":
        suffix = "jpeg"
    raw = target.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/{suffix};base64,{encoded}"


def tool_read_file(path: str, model_config: dict[str, Any] | None = None) -> str | dict[str, Any]:
    target = _safe_path(path)
    if not target.exists():
        return f"文件不存在: {path}"
    if not target.is_file():
        return f"不是文件: {path}"
    if target.suffix.lower() in IMAGE_SUFFIXES:
        if model_supports_vision(model_config):
            return encode_image_data_url(target)
        return (
            f"{target.name} 是图片文件。当前 Agent 模型没有 vision 能力，"
            "不要再调用 read_file 读取图片，请让用户用文字描述内容。"
        )
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"{target.name} 是二进制文件，已跳过。"
    if len(text) > 12000:
        return text[:12000] + "\n...[truncated]"
    return text


def tool_write_file(path: str, content: str) -> str:
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content or "", encoding="utf-8")
    return f"已写入 {path} ({len(content or '')} chars)"


def tool_search_memory(query: str, persona: str = "shizuku", storage: Any | None = None) -> str:
    items = (storage or get_storage()).search_memories(query or "", persona=persona, top_k=5)
    if not items:
        return "没有找到相关记忆。"
    return "\n".join(f"- {item.get('content')}" for item in items)


def tool_run_local_agent(agent: str, prompt: str) -> str:
    from app.local_agents import run_agent

    result = run_agent(agent, prompt)
    if not result.get("success"):
        return result.get("error") or "本机 Agent 执行失败"
    return str(result.get("output") or "(无输出)")


def tool_add_memory(content: str, persona: str = "shizuku", storage: Any | None = None) -> str:
    if not content.strip():
        return "记忆内容为空。"
    (storage or get_storage()).add_memory(persona, content.strip(), kind="long_term")
    return "已写入长期记忆。"


TOOL_IMPLS: dict[str, Callable[..., str]] = {
    "list_dir": tool_list_dir,
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "search_memory": tool_search_memory,
    "add_memory": tool_add_memory,
    "run_local_agent": tool_run_local_agent,
}

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files in the local workspace.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative workspace path"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a workspace text file. Do not use this on png/jpg/gif/webp images.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write a text file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_memory",
            "description": "Save a fact to long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_local_agent",
            "description": "Run a locally installed coding agent: opencode, hermes, codex, claude, openclaw, or astrbot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "description": "opencode | hermes | codex | claude | openclaw | astrbot"},
                    "prompt": {"type": "string"},
                },
                "required": ["agent", "prompt"],
            },
        },
    },
]


def make_run_skill(skill_manager: Any | None = None) -> Callable[..., Any]:
    def run_skill(skill_id: str, arguments: dict[str, Any] | None = None) -> Any:
        manager = skill_manager or _default_skill_manager()
        skill_id = str(skill_id or "")
        if not manager.get(skill_id):
            return {"ok": False, "error": {"type": "unknown_tool", "message": f"未知技能: {skill_id}"}}
        policy = manager.get_skill_policy(skill_id)
        if not policy.get("enabled", True):
            return {"ok": False, "error": {"type": "policy_denied", "message": f"技能已停用: {skill_id}"}}
        if not policy.get("allow_model_invocation", True):
            return {"ok": False, "error": {"type": "policy_denied", "message": f"技能不允许模型调用: {skill_id}"}}
        result = manager.invoke(skill_id, **(arguments or {}))
        if isinstance(result, dict) and "ok" in result:
            return result
        return {"ok": True, "value": str(result or "(技能无输出)")}
    return run_skill


def make_list_skills(skill_manager: Any | None = None) -> Callable[..., str]:
    def list_skills() -> str:
        manager = skill_manager or _default_skill_manager()
        items = manager.list_skills()
        if not items:
            return "没有可用技能。"
        return "\n".join(
            f"- {item.get('skill_id')}: {item.get('description') or item.get('name')}"
            for item in items
            if item.get("enabled", True)
        )
    return list_skills


def make_call_mcp(mcp_manager: Any | None = None) -> Callable[..., Any]:
    cache: dict[str, Any] = {}

    def call_mcp(server_id: str, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        from app.agent.mcp_client import build_mcp_clients

        manager = mcp_manager or _default_mcp_manager()
        servers = manager.list_servers()
        server = next((item for item in servers if str(item.get("id") or "") == str(server_id or "")), None)
        if server is None:
            return {"ok": False, "error": {"type": "unknown_tool", "message": f"未知 MCP 服务器: {server_id}"}}
        if not server.get("enabled", True):
            return {"ok": False, "error": {"type": "policy_denied", "message": f"MCP 服务器已停用: {server_id}"}}
        if str(server.get("type") or "") == "internal":
            value = _run_internal_mcp_tool(tool_name, arguments or {}, server_id)
            return {"ok": True, "value": value}
        if server_id not in cache:
            cache.update(build_mcp_clients(servers))
        client = cache.get(server_id)
        if client is None:
            return {"ok": False, "error": {"type": "policy_denied", "message": f"MCP 服务器不可用或未启用: {server_id}"}}
        try:
            value = client.call_tool(str(tool_name), arguments or {})
            return {"ok": True, "value": value}
        except Exception as exc:
            return {"ok": False, "error": {"type": "execution_error", "message": f"MCP 工具执行失败 [{server_id}/{tool_name}]: {exc}"}}
    return call_mcp


def make_list_mcp_tools(mcp_manager: Any | None = None) -> Callable[..., str]:
    def list_mcp_tools() -> str:
        manager = mcp_manager or _default_mcp_manager()
        items = manager.list_tools()
        if not items:
            return "没有已启用的 MCP 工具。"
        return "\n".join(f"- {item.get('server')}/{item.get('name')} [{item.get('status')}]" for item in items)
    return list_mcp_tools


def _default_skill_manager() -> Any:
    from app.skill_manager import get_skill_manager
    return get_skill_manager()


def _default_mcp_manager() -> Any:
    from app.mcp_manager import get_mcp_manager
    return get_mcp_manager()


def _run_internal_mcp_tool(tool_name: str, arguments: dict[str, Any], server_id: str) -> str:
    return f"[{server_id}] {tool_name}: {json.dumps(arguments, ensure_ascii=False)}"


def register_agent_extensions(
    registry: Any,
    skill_manager: Any | None = None,
    mcp_manager: Any | None = None,
) -> None:
    from app.task_plans import register
    register(registry)
    from app.auxiliary_models import invoke
    registry.register('use_auxiliary_model',invoke,{'type':'function','function':{'name':'use_auxiliary_model','description':'Use a configured image generation, speech, search or embedding model. The user must approve and select the model before any API call.','parameters':{'type':'object','properties':{'kind':{'type':'string','enum':['images','speech','search','embeddings']},'prompt':{'type':'string'}},'required':['kind','prompt']}}})
    registry.register(
        "list_skills",
        make_list_skills(skill_manager),
        {
            "type": "function",
            "function": {
                "name": "list_skills",
                "description": "List available agent skills.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    )
    registry.register(
        "run_skill",
        make_run_skill(skill_manager),
        {
            "type": "function",
            "function": {
                "name": "run_skill",
                "description": "Run an installed skill by id. Pass arguments expected by the skill.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_id": {"type": "string", "description": "Skill id"},
                        "arguments": {"type": "object", "description": "Keyword arguments for the skill handler"},
                    },
                    "required": ["skill_id"],
                },
            },
        },
    )
    registry.register(
        "list_mcp_tools",
        make_list_mcp_tools(mcp_manager),
        {
            "type": "function",
            "function": {
                "name": "list_mcp_tools",
                "description": "List available MCP server tools.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    )
    registry.register(
        "call_mcp",
        make_call_mcp(mcp_manager),
        {
            "type": "function",
            "function": {
                "name": "call_mcp",
                "description": "Call an MCP tool on a configured MCP server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "server_id": {"type": "string", "description": "MCP server id"},
                        "tool_name": {"type": "string", "description": "Tool name exposed by the server"},
                        "arguments": {"type": "object", "description": "Tool arguments"},
                    },
                    "required": ["server_id", "tool_name"],
                },
            },
        },
    )


def run_tool(
    name: str,
    arguments: dict[str, Any],
    persona: str,
    model_config: dict[str, Any] | None = None,
    storage: Any | None = None,
) -> dict[str, Any]:
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {"ok": False, "error": {"type": "unknown_tool", "message": f"未知工具: {name}"}}
    kwargs = dict(arguments or {})
    if name in {"search_memory", "add_memory"}:
        kwargs["persona"] = persona
    if name == "read_file":
        kwargs["model_config"] = model_config
    if name in {"search_memory", "add_memory"}:
        kwargs["storage"] = storage
    try:
        return {"ok": True, "value": impl(**kwargs)}
    except TypeError as exc:
        return {"ok": False, "error": {"type": "invalid_arguments", "message": str(exc)}}
    except Exception as exc:
        return {"ok": False, "error": {"type": "execution_error", "message": str(exc)}}


def parse_tool_arguments(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"工具参数不是合法 JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("工具参数必须是 JSON 对象")
    return data
