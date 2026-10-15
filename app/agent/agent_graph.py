from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.nodes.model_node import ModelNode
from app.agent.nodes.query_router_node import QueryRouterNode
from app.agent.nodes.rag_node import RagNode
from app.agent.nodes.response_node import ResponseNode
from app.agent.nodes.router_node import RouterNode
from app.agent.nodes.tool_executor_node import ToolExecutorNode
from app.agent.llm import LLMClient
from app.agent.embeddings import make_embedder
from app.agent.dependencies import AgentDependencies
from app.config import settings
from app.model_registry import model_registry
from app.observability import get_observability_manager
from app.agent.state import AgentState
from app.agent.tool_registry import ToolRegistry
from app.agent.tools import register_agent_extensions
from app.agent.harness import AgentHarness
from app.persona_store import active_filename, list_personas, persona_id
from app.skill_manager import get_skill_manager
from app.mcp_manager import get_mcp_manager
from app.storage.adapter import get_storage


class AgentGraph:
    """LangGraph agent: START -> model -> (tools | response) -> END."""

    def __init__(
        self,
        storage: Any | None = None,
        model_gateway: Any | None = None,
        tool_registry: ToolRegistry | None = None,
        llm_client: LLMClient | None = None,
        fallback_client: LLMClient | None = None,
        skill_manager: Any | None = None,
        mcp_manager: Any | None = None,
        dependencies: AgentDependencies | None = None,
    ) -> None:
        runtime = dependencies or AgentDependencies(
            storage=storage if storage is not None else get_storage(),
            model_registry=model_registry,
            settings=settings,
            tool_registry=tool_registry or ToolRegistry(),
            llm_client=llm_client,
            fallback_client=fallback_client,
            skill_manager=skill_manager,
            mcp_manager=mcp_manager,
        )
        self.dependencies = runtime
        self.storage = runtime.storage
        if hasattr(self.storage, "set_embedder"):
            try:
                self.storage.set_embedder(make_embedder(runtime.llm_client))
            except Exception:
                pass
        self.tool_registry = runtime.tool_registry
        self.skill_manager = runtime.skill_manager or get_skill_manager()
        self.mcp_manager = runtime.mcp_manager or get_mcp_manager()
        register_agent_extensions(self.tool_registry, self.skill_manager, self.mcp_manager)
        self.model_node = ModelNode(
            gateway=model_gateway,
            llm_client=runtime.llm_client,
            fallback_client=runtime.fallback_client,
            tool_registry=self.tool_registry,
        )
        self.tool_node = ToolExecutorNode(storage=self.storage, registry=self.tool_registry)
        self.response_node = ResponseNode()
        self.router = RouterNode()
        self.query_router = QueryRouterNode()
        self.rag_node = RagNode(storage=self.storage)
        builder = StateGraph(AgentState)
        builder.add_node("query_router", self.query_router)
        builder.add_node("rag", self.rag_node)
        builder.add_node("model", self.model_node)
        builder.add_node("tools", self.tool_node)
        builder.add_node("response", self.response_node)
        builder.add_edge(START, "query_router")
        builder.add_conditional_edges(
            "query_router",
            self.query_router.route,
            {"rag": "rag", "model": "model"},
        )
        builder.add_edge("rag", "model")
        builder.add_conditional_edges(
            "model",
            self.router.route,
            {"tools": "tools", "response": "response"},
        )
        builder.add_edge("tools", "model")
        builder.add_edge("response", END)
        get_observability_manager().configure_all()
        self.graph = builder.compile()
        self._harness = AgentHarness(self)

    def available_personas(self) -> list[dict[str, Any]]:
        return list_personas().get("personas") or []

    def default_persona(self) -> str:
        return persona_id(active_filename())

    def invoke(
        self,
        message: str,
        persona: str | None = None,
        thread_id: str | None = None,
        model_group: str | None = None,
        image: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self._harness.run(
            message,
            persona=persona,
            thread_id=thread_id,
            model_group=model_group,
            image=image,
            attachments=attachments,
        )


_GRAPH: AgentGraph | None = None


def get_agent_graph() -> AgentGraph:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = AgentGraph()
    return _GRAPH
