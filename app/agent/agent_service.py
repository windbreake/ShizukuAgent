from __future__ import annotations

from typing import Any

from app.agent.agent_graph import AgentGraph
from app.agent.dependencies import AgentDependencies
from app.agent.harness import AgentHarness
from app.agent.llm import LLMClient
from app.agent.tool_registry import ToolRegistry


class AgentService:
    """Application-facing facade for graph execution and session lifecycle."""

    def __init__(
        self,
        graph: AgentGraph | None = None,
        *,
        storage: Any | None = None,
        model_gateway: Any | None = None,
        tool_registry: ToolRegistry | None = None,
        llm_client: LLMClient | None = None,
        fallback_client: LLMClient | None = None,
        skill_manager: Any | None = None,
        mcp_manager: Any | None = None,
        dependencies: AgentDependencies | None = None,
    ) -> None:
        self.graph = graph or AgentGraph(
            storage=storage,
            model_gateway=model_gateway,
            tool_registry=tool_registry,
            llm_client=llm_client,
            fallback_client=fallback_client,
            skill_manager=skill_manager,
            mcp_manager=mcp_manager,
            dependencies=dependencies,
        )
        self.harness = AgentHarness(self.graph)

    def run(self, question: str, **options: Any) -> dict[str, Any]:
        return self.harness.run(question, **options)

    def reset_session(self, thread_id: str, persona: str | None = None) -> None:
        self.harness.reset_session(thread_id, persona)

    def available_personas(self) -> list[dict[str, Any]]:
        return self.graph.available_personas()

    def default_persona(self) -> str:
        return self.graph.default_persona()


_SERVICE: AgentService | None = None


def get_agent_service() -> AgentService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = AgentService()
    return _SERVICE
