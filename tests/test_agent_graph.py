from __future__ import annotations

import unittest
from unittest.mock import patch, Mock

from app.agent.agent_graph import AgentGraph
from app.agent.agent_service import AgentService
from app.agent.tool_registry import ToolRegistry
from app.agent.dependencies import AgentDependencies


class FakeLLM:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls = 0

    def chat(self, messages, model_config):
        self.calls += 1
        return self.response

    def embed(self, text, model_config=None):
        return []


class FakeStorage:
    def __init__(self) -> None:
        self.checkpoints: dict[tuple[str, str], dict] = {}
        self.records: list[tuple[str, str, str]] = []
        self.memories: list[tuple[str, str, str]] = []

    def load_checkpoint(self, thread_id: str, persona: str):
        return self.checkpoints.get((thread_id, persona))

    def save_checkpoint(self, thread_id: str, persona: str, state: dict) -> None:
        self.checkpoints[(thread_id, persona)] = state

    def search_memories(self, query: str, persona: str, top_k: int = 5) -> list[dict]:
        return []

    def add_chat_record(self, persona: str, role: str, content: str, thread_id: str | None = None) -> int:
        self.records.append((persona, role, content))
        return len(self.records)

    def add_memory(self, persona: str, content: str, kind: str = "long_term") -> int:
        self.memories.append((persona, content, kind))
        return len(self.memories)


class AgentGraphTests(unittest.TestCase):
    def test_direct_model_response_ends_graph(self) -> None:
        storage = FakeStorage()
        agent = AgentGraph(storage=storage, model_gateway=lambda messages, model: {"role": "assistant", "content": "你好"})

        result = agent.invoke("在吗", persona="shizuku", thread_id="thread-1")

        self.assertEqual("你好", result["reply"])
        self.assertEqual("langgraph:primary", result["engine"])
        self.assertEqual([], result["trace"])
        self.assertEqual("你好", storage.checkpoints[("thread-1", "shizuku")]["messages"][-1]["content"])

    def test_tool_call_routes_back_to_model(self) -> None:
        storage = FakeStorage()
        calls = 0

        def gateway(messages, model):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "search_memory", "arguments": '{"query":"测试"}'},
                        }
                    ],
                }
            self.assertEqual("tool", messages[-1]["role"])
            return {"role": "assistant", "content": "工具执行完成"}

        agent = AgentGraph(storage=storage, model_gateway=gateway)
        with patch("app.agent.tools.run_tool", return_value="工具结果") as mocked_tool:
            result = agent.invoke("帮我查一下", persona="shizuku")

        self.assertEqual(2, calls)
        mocked_tool.assert_called_once()
        self.assertEqual("search_memory", mocked_tool.call_args.args[0])
        self.assertEqual({"query": "测试"}, mocked_tool.call_args.args[1])
        self.assertEqual("shizuku", mocked_tool.call_args.args[2])
        self.assertEqual("工具执行完成", result["reply"])
        self.assertEqual("search_memory", result["trace"][0]["tool"])
        self.assertEqual("工具结果", result["trace"][0]["result"])

    def test_memory_tool_uses_graph_storage(self) -> None:
        storage = FakeStorage()
        agent = AgentGraph(
            storage=storage,
            model_gateway=Mock(side_effect=[{
                "role": "assistant",
                "content": "已查询",
                "tool_calls": [
                    {
                        "id": "memory-1",
                        "type": "function",
                        "function": {"name": "search_memory", "arguments": '{"query":"测试"}'},
                    }
                ],
            }, {'role':'assistant','content':'查询完成'}]),
        )

        with patch("app.agent.tools.run_tool", wraps=__import__(
            "app.agent.tools", fromlist=["run_tool"]
        ).run_tool) as mocked_tool:
            agent.invoke("查记忆", persona="shizuku")

        self.assertIs(mocked_tool.call_args.args[4], storage)

    def test_malformed_tool_arguments_are_not_executed(self) -> None:
        storage = FakeStorage()
        agent = AgentGraph(
            storage=storage,
            model_gateway=Mock(side_effect=[{
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "bad-1",
                        "type": "function",
                        "function": {"name": "list_dir", "arguments": "not-json"},
                    }
                ],
            }, {'role':'assistant','content':'参数错误'}]),
        )

        with patch("app.agent.tools.run_tool") as mocked_tool:
            result = agent.invoke("执行目录查询", persona="shizuku")

        mocked_tool.assert_not_called()
        self.assertFalse(result["trace"][0]["ok"])
        self.assertEqual("invalid_arguments", result["trace"][0]["result"].split("[")[1].split("]")[0])

    def test_missing_api_key_uses_langgraph_fallback(self) -> None:
        storage = FakeStorage()
        agent = AgentGraph(storage=storage)

        with patch.dict("os.environ", {}, clear=True), patch.object(
            agent.dependencies.model_registry, "resolve_agent_group",
            return_value=[{"id": "primary", "provider_config": {}, "model": "offline"}],
        ):
            result = agent.invoke("离线消息", persona="shizuku")

        self.assertEqual("langgraph-local-fallback", result["engine"])
        self.assertIn("当前运行 LangGraph Agent", result["reply"])

    def test_model_group_falls_back_to_next_candidate(self) -> None:
        storage = FakeStorage()
        attempts: list[str] = []

        def gateway(messages, model):
            attempts.append(model["id"])
            if model["id"] == "primary":
                raise RuntimeError("primary unavailable")
            return {"role": "assistant", "content": "备用模型响应"}

        agent = AgentGraph(storage=storage, model_gateway=gateway)
        with patch.dict(
            "app.model_registry.settings._data",
            {
                "providers": {"test": {"api_key": "test-key", "base_url": "http://localhost"}},
                "models": {
                    "primary": {"provider": "test", "model": "main", "capabilities": ["chat"], "enabled": True},
                    "backup": {"provider": "test", "model": "backup", "capabilities": ["chat"], "enabled": True},
                },
                "model_groups": {"fallback": {"purpose": "agent", "models": ["primary", "backup"]}},
                "default_model_group": "fallback",
            },
            clear=False,
        ):
            result = agent.invoke("测试 fallback", persona="shizuku", model_group="fallback")

        self.assertEqual(["primary", "backup"], attempts)
        self.assertEqual("备用模型响应", result["reply"])
        self.assertEqual("langgraph:backup", result["engine"])
        self.assertEqual("backup", result["active_model"])

    def test_all_group_candidates_fail(self) -> None:
        storage = FakeStorage()

        def gateway(messages, model):
            raise RuntimeError(f"{model['id']} down")

        agent = AgentGraph(storage=storage, model_gateway=gateway)
        with patch.dict(
            "app.model_registry.settings._data",
            {
                "providers": {"test": {"api_key": "test-key", "base_url": "http://localhost"}},
                "models": {
                    "primary": {"provider": "test", "model": "main", "capabilities": ["chat"], "enabled": True},
                    "backup": {"provider": "test", "model": "backup", "capabilities": ["chat"], "enabled": True},
                },
                "model_groups": {"fallback": {"purpose": "agent", "models": ["primary", "backup"]}},
                "default_model_group": "fallback",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(RuntimeError,'模型请求失败'):
                agent.invoke("全部失败", persona="shizuku", model_group="fallback")
        self.assertEqual(['user'],[m['role'] for m in agent._harness.get_history('persona:shizuku','shizuku')])


class VisionCapabilityTests(unittest.TestCase):
    def test_vision_uses_model_capabilities_not_legacy_llm(self) -> None:
        from app.agent.llm import model_supports_vision

        self.assertTrue(model_supports_vision({"capabilities": ["chat", "vision"]}))
        self.assertFalse(model_supports_vision({"capabilities": ["chat"]}))
        self.assertFalse(model_supports_vision({}))


class ArchitectureTests(unittest.TestCase):
    def test_graph_uses_injected_runtime_dependencies(self) -> None:
        class FakeSettings:
            def get(self, key, default=None):
                return {"work_mode": {"enabled": True}}.get(key, default)

        class FakeRegistry:
            def resolve_agent_group(self, group_id=None):
                return [{"id": "injected", "provider_config": {"api_key": "test"}, "model": "test"}]

        client = FakeLLM({"role": "assistant", "content": "runtime"})
        dependencies = AgentDependencies(
            storage=FakeStorage(),
            model_registry=FakeRegistry(),
            settings=FakeSettings(),
            tool_registry=ToolRegistry(),
            llm_client=client,
        )
        agent = AgentGraph(dependencies=dependencies)

        result = agent.invoke("测试运行时依赖", persona="shizuku")

        self.assertEqual("runtime", result["reply"])
        self.assertEqual("injected", result["active_model"])

    def test_graph_uses_injected_llm_client(self) -> None:
        client = FakeLLM({"role": "assistant", "content": "injected"})
        agent = AgentGraph(storage=FakeStorage(), llm_client=client)

        result = agent.invoke("测试注入", persona="shizuku")

        self.assertEqual("injected", result["reply"])
        self.assertEqual(1, client.calls)

    def test_service_owns_graph_and_can_reset_session(self) -> None:
        storage = FakeStorage()
        graph = AgentGraph(storage=storage, model_gateway=lambda messages, model: {"role": "assistant", "content": "ok"})
        service = AgentService(graph)
        service.run("保存会话", persona="shizuku", thread_id="session-1")
        self.assertTrue(storage.checkpoints[("session-1", "shizuku")]["messages"])

        service.reset_session("session-1", "shizuku")

        self.assertEqual([], storage.checkpoints[("session-1", "shizuku")]["messages"])

    def test_service_uses_harness_and_exposes_history(self) -> None:
        storage = FakeStorage()
        service = AgentService(
            graph=AgentGraph(
                storage=storage,
                model_gateway=lambda messages, model: {"role": "assistant", "content": "ok"},
            )
        )
        service.run("你好", persona="shizuku", thread_id="h-1")

        history = service.harness.get_history("h-1", "shizuku")

        self.assertTrue(any(item["role"] == "user" and item["content"] == "你好" for item in history))
        self.assertTrue(any(item["role"] == "assistant" and item["content"] == "ok" for item in history))
        # tool metadata is stripped from persisted history
        self.assertTrue(all("tool_calls" not in item for item in history))

    def test_tool_registry_exposes_registered_definitions(self) -> None:
        registry = ToolRegistry({"list_dir": object()})

        self.assertTrue(registry.contains("list_dir"))
        self.assertFalse(registry.contains("write_file"))
        self.assertEqual(["list_dir"], [item["function"]["name"] for item in registry.definitions()])


if __name__ == "__main__":
    unittest.main()
