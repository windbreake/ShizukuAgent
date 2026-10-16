from __future__ import annotations

import gc
import json
import os
import sys
import tempfile
import unittest

from app.agent.mcp_client import McpStdioClient
from app.agent.tool_registry import ToolRegistry
from app.agent.tools import register_agent_extensions


class FakeSkillManager:
    def __init__(self) -> None:
        self.skills = {
            "greet": {"skill_id": "greet", "name": "Greet", "description": "greet", "enabled": True}
        }

    def get(self, skill_id: str):
        return self.skills.get(skill_id)

    def get_skill_policy(self, skill_id: str):
        return {"enabled": True, "allow_model_invocation": True}

    def invoke(self, skill_id: str, **kwargs):
        return f"hello {kwargs.get('name', '')}"

    def list_skills(self):
        return list(self.skills.values())


class FakeMcpManager:
    def __init__(self, servers: list[dict]) -> None:
        self.servers = servers

    def list_servers(self):
        return self.servers

    def list_tools(self):
        tools = []
        for server in self.servers:
            if server.get("enabled"):
                for tool in server.get("tools", []):
                    tools.append({"server": server["id"], "name": tool, "status": "connected"})
        return tools


class FakeStorage:
    def load_checkpoint(self, thread_id: str, persona: str):
        return None

    def save_checkpoint(self, thread_id: str, persona: str, state: dict) -> None:
        pass

    def search_memories(self, query: str, persona: str, top_k: int = 5) -> list[dict]:
        return []

    def add_chat_record(self, persona: str, role: str, content: str, thread_id: str | None = None) -> int:
        return 0

    def add_memory(self, persona: str, content: str, kind: str = "long_term") -> int:
        return 0


class SkillMcpIntegrationTests(unittest.TestCase):
    def test_registry_registers_skill_and_mcp_tools(self) -> None:
        registry = ToolRegistry()
        register_agent_extensions(registry, FakeSkillManager(), FakeMcpManager([]))

        for name in ("list_skills", "run_skill", "list_mcp_tools", "call_mcp"):
            self.assertTrue(registry.contains(name))
        names = [item["function"]["name"] for item in registry.definitions()]
        self.assertIn("run_skill", names)
        self.assertIn("call_mcp", names)

    def test_run_skill_tool_with_injected_manager(self) -> None:
        registry = ToolRegistry()
        register_agent_extensions(registry, FakeSkillManager(), FakeMcpManager([]))

        result = registry.execute("run_skill", {"skill_id": "greet", "arguments": {"name": "world"}})

        self.assertTrue(result["ok"])
        self.assertEqual("hello world", result["value"])

    def test_unknown_skill_returns_error(self) -> None:
        registry = ToolRegistry()
        register_agent_extensions(registry, FakeSkillManager(), FakeMcpManager([]))

        result = registry.execute("run_skill", {"skill_id": "nope", "arguments": {}})

        self.assertFalse(result["ok"])
        self.assertEqual("unknown_tool", result["error"]["type"])

    def test_model_gateway_receives_dynamic_tool_definitions(self) -> None:
        from app.agent.agent_graph import AgentGraph

        seen: list[list[dict]] = []

        def gateway(messages, model):
            seen.append(model.get("tools") or [])
            return {"role": "assistant", "content": "ok"}

        agent = AgentGraph(storage=FakeStorage(), model_gateway=gateway)
        from unittest.mock import patch
        original_get = agent.dependencies.settings.get
        with patch.object(agent.dependencies.settings, 'get', side_effect=lambda key, default=None: {'enabled':True} if key=='work_mode' else original_get(key,default)):
            agent.invoke("测试工具", persona="shizuku")

        self.assertTrue(seen)
        names = {item["function"]["name"] for item in seen[0]}
        self.assertIn("run_skill", names)
        self.assertIn("call_mcp", names)
        self.assertIn("read_file", names)


FAKE_MCP_SERVER = r'''
import json
import sys


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        method = req.get("method")
        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "fake", "version": "1.0"},
                },
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo text back",
                            "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
                        }
                    ]
                },
            }
        elif method == "tools/call":
            arguments = (req.get("params") or {}).get("arguments") or {}
            resp = {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "result": {"content": [{"type": "text", "text": f"echo:{arguments.get('text', '')}"}]},
            }
        else:
            resp = {"jsonrpc": "2.0", "id": req.get("id"), "result": {}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
'''


class McpClientTests(unittest.TestCase):
    def test_stdio_client_lists_and_calls_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_path = os.path.join(tmp, "fake_mcp_server.py")
            with open(script_path, "w", encoding="utf-8") as fh:
                fh.write(FAKE_MCP_SERVER)
            client = McpStdioClient(sys.executable, [script_path])
            try:
                tools = client.list_tools()
                self.assertEqual("echo", tools[0]["name"])
                result = client.call_tool("echo", {"text": "hi"})
                self.assertEqual("echo:hi", result)
            finally:
                client.close()

    def test_call_mcp_tool_with_injected_manager(self) -> None:
        registry = ToolRegistry()
        with tempfile.TemporaryDirectory() as tmp:
            script_path = os.path.join(tmp, "fake_mcp_server.py")
            with open(script_path, "w", encoding="utf-8") as fh:
                fh.write(FAKE_MCP_SERVER)
            manager = FakeMcpManager(
                [
                    {
                        "id": "fake",
                        "type": "stdio",
                        "command": sys.executable,
                        "args": [script_path],
                        "enabled": True,
                        "tools": ["echo"],
                    }
                ]
            )
            register_agent_extensions(registry, FakeSkillManager(), manager)

            result = registry.execute(
                "call_mcp",
                {"server_id": "fake", "tool_name": "echo", "arguments": {"text": "hello"}},
            )

            self.assertTrue(result["ok"], msg=str(result))
            self.assertIn("echo:hello", result["value"])
            gc.collect()


if __name__ == "__main__":
    unittest.main()
