from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from app.agent.tools import make_call_mcp, make_run_skill
from app.observability import ObservabilityManager
from app.plugin_manager import PluginManager


class FakeSkillManager:
    def __init__(self, policy: dict | None = None) -> None:
        self.skills = {"greet": {"skill_id": "greet", "name": "Greet"}}
        self.policy = {"enabled": True, "allow_model_invocation": True, **(policy or {})}

    def get(self, skill_id: str):
        return self.skills.get(skill_id)

    def get_skill_policy(self, skill_id: str):
        return dict(self.policy)

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
        return []


def write_plugin(tmp: Path, plugin_id: str, kind: str, enabled: bool = True) -> None:
    plugin_dir = tmp / kind / plugin_id
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {"id": plugin_id, "name": plugin_id, "version": "1.0.0", "enabled": enabled},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class PluginManagerTests(unittest.TestCase):
    def test_skips_dedicated_plugin_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plugins"
            write_plugin(root, "langsmith", "observability")
            write_plugin(root, "fs", "mcp")
            write_plugin(root, "greet", "skills")
            write_plugin(root, "myplugin", "core")
            manager = PluginManager(plugins_dir=root)

            names = {item["name"] for item in manager.list_plugins()}
            self.assertIn("core.local", names)
            self.assertIn("myplugin", names)
            self.assertNotIn("langsmith", names)
            self.assertNotIn("fs", names)
            self.assertNotIn("greet", names)

    def test_enabled_state_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plugins"
            state_path = Path(tmp) / "state.json"
            write_plugin(root, "myplugin", "core")
            manager = PluginManager(plugins_dir=root, state_path=state_path)
            manager.set_plugin_enabled("myplugin", False)

            manager2 = PluginManager(plugins_dir=root, state_path=state_path)
            myplugin = next(item for item in manager2.list_plugins() if item["name"] == "myplugin")
            self.assertFalse(myplugin["enabled"])


class ObservabilityProtocolTests(unittest.TestCase):
    def test_loads_plugin_with_unified_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_plugin(Path(tmp), "langsmith", "observability")
            manager = ObservabilityManager(plugins_dir=Path(tmp) / "observability")
            plugins = manager.list_plugins()
            self.assertTrue(any(item["id"] == "langsmith" and item["kind"] == "observability" for item in plugins))


class PolicyEnforcementTests(unittest.TestCase):
    def test_run_skill_respects_policy(self) -> None:
        denied = make_run_skill(FakeSkillManager(policy={"allow_model_invocation": False}))
        result = denied("greet", {"name": "world"})
        self.assertFalse(result["ok"])
        self.assertEqual("policy_denied", result["error"]["type"])

        allowed = make_run_skill(FakeSkillManager())
        result = allowed("greet", {"name": "world"})
        self.assertTrue(result["ok"])
        self.assertEqual("hello world", result["value"])

    def test_call_mcp_respects_enabled(self) -> None:
        disabled = make_call_mcp(FakeMcpManager([{"id": "off", "type": "stdio", "enabled": False}]))
        result = disabled("off", "echo", {})
        self.assertFalse(result["ok"])
        self.assertEqual("policy_denied", result["error"]["type"])


if __name__ == "__main__":
    unittest.main()