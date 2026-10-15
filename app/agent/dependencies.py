from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.agent.llm import LLMClient
from app.agent.tool_registry import ToolRegistry
from app.config import settings as default_settings
from app.model_registry import ModelRegistry, model_registry as default_model_registry
from app.storage.adapter import get_storage


@dataclass(slots=True)
class AgentDependencies:
    """Runtime dependencies assembled once at the application composition root."""

    storage: Any
    model_registry: ModelRegistry
    settings: Any
    tool_registry: ToolRegistry
    llm_client: LLMClient | None = None
    fallback_client: LLMClient | None = None
    skill_manager: Any | None = None
    mcp_manager: Any | None = None

    @classmethod
    def defaults(cls) -> "AgentDependencies":
        return cls(
            storage=get_storage(),
            model_registry=default_model_registry,
            settings=default_settings,
            tool_registry=ToolRegistry(),
        )
