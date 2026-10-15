from __future__ import annotations

import os
from typing import Any

from app.config import settings


def _load_config() -> dict[str, Any]:
    cfg = settings.get("langsmith")
    return cfg if isinstance(cfg, dict) else {}


def configure() -> None:
    """Apply project-level LangSmith settings via the official environment variables.

    If the plugin config is not explicitly enabled, leave the environment untouched so
    the standard ``LANGSMITH_TRACING=true`` / ``LANGSMITH_API_KEY=...`` flow still works.
    """
    cfg = _load_config()
    if not cfg.get("enabled"):
        return
    api_key = str(cfg.get("api_key") or "").strip()
    if not api_key:
        return
    os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGSMITH_TRACING"] = "true"
    project = str(cfg.get("project") or "").strip()
    if project:
        os.environ["LANGSMITH_PROJECT"] = project
    endpoint = str(cfg.get("endpoint") or "").strip()
    if endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = endpoint


def is_enabled() -> bool:
    tracing = os.getenv("LANGSMITH_TRACING", "").lower() == "true"
    return tracing and bool(os.getenv("LANGSMITH_API_KEY"))


def status() -> dict[str, Any]:
    configure()
    cfg = _load_config()
    return {
        "enabled": is_enabled(),
        "project": os.getenv("LANGSMITH_PROJECT") or cfg.get("project") or "shizukuclaw",
        "endpoint": os.getenv("LANGSMITH_ENDPOINT")
        or cfg.get("endpoint")
        or "https://api.smith.langchain.com",
        "has_api_key": bool(os.getenv("LANGSMITH_API_KEY") or cfg.get("api_key")),
        "configured": bool(cfg.get("enabled")),
    }


def invoke_config(thread_id: str | None = None, persona: str | None = None) -> dict[str, Any]:
    """Build a LangGraph invoke config that enriches LangSmith traces with metadata."""
    if not is_enabled():
        return {}
    config: dict[str, Any] = {"metadata": {}}
    if thread_id:
        config["metadata"]["thread_id"] = thread_id
        config["configurable"] = {"thread_id": thread_id}
    if persona:
        config["metadata"]["persona"] = persona
    return config