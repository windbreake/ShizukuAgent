from __future__ import annotations

import unittest

from app.agent.agent_graph import AgentGraph


class MemoryStorage:
    def __init__(self, memories: list[dict] | None = None) -> None:
        self.memories = memories or []
        self.checkpoints: dict[tuple[str, str], dict] = {}

    def load_checkpoint(self, thread_id: str, persona: str):
        return None

    def save_checkpoint(self, thread_id: str, persona: str, state: dict) -> None:
        self.checkpoints[(thread_id, persona)] = state

    def search_memories(self, query: str, persona: str | None = None, top_k: int = 5) -> list[dict]:
        return self.memories

    def add_chat_record(self, persona: str, role: str, content: str, thread_id: str | None = None) -> int:
        return 0

    def add_memory(self, persona: str, content: str, kind: str = "long_term") -> int:
        return 0


class RagAgenticTests(unittest.TestCase):
    def test_rag_route_injects_enhanced_context(self) -> None:
        storage = MemoryStorage([{"content": "用户喜欢蓝色"}])
        seen: list[list[dict]] = []

        def gateway(messages, model):
            seen.append(messages)
            return {"role": "assistant", "content": "好的"}

        agent = AgentGraph(storage=storage, model_gateway=gateway)
        result = agent.invoke("查找一下我的喜好", persona="shizuku")

        self.assertTrue(seen)
        self.assertTrue(any("检索增强上下文" in (m.get("content") or "") for m in seen[0]))
        self.assertTrue(any("用户喜欢蓝色" in (m.get("content") or "") for m in seen[0]))
        self.assertEqual("好的", result["reply"])

    def test_direct_route_skips_rag(self) -> None:
        storage = MemoryStorage()
        seen: list[list[dict]] = []

        def gateway(messages, model):
            seen.append(messages)
            return {"role": "assistant", "content": "你好"}

        agent = AgentGraph(storage=storage, model_gateway=gateway)
        agent.invoke("在吗", persona="shizuku")

        self.assertTrue(seen)
        self.assertFalse(any("检索增强上下文" in (m.get("content") or "") for m in seen[0]))

    def test_rag_route_can_still_call_tools(self) -> None:
        storage = MemoryStorage([{"content": "用户喜欢蓝色"}])
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
                            "id": "c1",
                            "type": "function",
                            "function": {"name": "search_memory", "arguments": '{"query":"喜好"}'},
                        }
                    ],
                }
            return {"role": "assistant", "content": "完成"}

        agent = AgentGraph(storage=storage, model_gateway=gateway)
        result = agent.invoke("查找我的喜好", persona="shizuku")

        self.assertEqual("完成", result["reply"])
        self.assertEqual(2, calls)


if __name__ == "__main__":
    unittest.main()
