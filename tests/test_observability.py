from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config import settings as app_settings
from app.observability import ObservabilityManager, get_observability_manager


_ENV_KEYS = ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_ENDPOINT")


class ObservabilityPluginTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)

    def test_manager_loads_langsmith_plugin(self) -> None:
        manager = get_observability_manager()
        plugins = manager.list_plugins()
        self.assertTrue(any(item["id"] == "langsmith" for item in plugins))
        self.assertIn("langsmith", manager._plugins)
        self.assertEqual("LangSmith", manager._plugins["langsmith"].name)

    def test_configure_all_sets_env(self) -> None:
        fake_data = {
            "langsmith": {"enabled": True, "api_key": "k", "project": "p", "endpoint": "http://e"}
        }
        with patch.object(app_settings, "_data", fake_data):
            get_observability_manager().configure_all()
        self.assertEqual("true", os.environ["LANGSMITH_TRACING"])
        self.assertEqual("k", os.environ["LANGSMITH_API_KEY"])
        self.assertEqual("p", os.environ["LANGSMITH_PROJECT"])
        self.assertEqual("http://e", os.environ["LANGSMITH_ENDPOINT"])

    def test_configure_all_keeps_env_when_disabled(self) -> None:
        fake_data = {"langsmith": {"enabled": False, "api_key": "k"}}
        with patch.object(app_settings, "_data", fake_data):
            get_observability_manager().configure_all()
        self.assertNotIn("LANGSMITH_TRACING", os.environ)
        self.assertNotIn("LANGSMITH_API_KEY", os.environ)

    def test_status_all_shape(self) -> None:
        statuses = get_observability_manager().status_all()
        self.assertTrue(statuses)
        langsmith = next(item for item in statuses if item["id"] == "langsmith")
        for key in ("name", "enabled", "project", "endpoint", "has_api_key"):
            self.assertIn(key, langsmith)

    def test_invoke_config_aggregates_metadata(self) -> None:
        fake_data = {"langsmith": {"enabled": True, "api_key": "k"}}
        with patch.object(app_settings, "_data", fake_data):
            manager = get_observability_manager()
            manager.configure_all()
            config = manager.invoke_config("t-1", "shizuku")
        self.assertEqual("t-1", config["metadata"]["thread_id"])
        self.assertEqual("shizuku", config["metadata"]["persona"])
        self.assertEqual("t-1", config["configurable"]["thread_id"])

    def test_invoke_config_empty_when_disabled(self) -> None:
        fake_data = {"langsmith": {"enabled": False, "api_key": ""}}
        with patch.object(app_settings, "_data", fake_data):
            manager = ObservabilityManager(plugins_dir=__import__(
                "app.paths", fromlist=["OBSERVABILITY_DIR"]
            ).OBSERVABILITY_DIR)
            manager.configure_all()
            config = manager.invoke_config("t-1", "shizuku")
        self.assertEqual({}, config)


if __name__ == "__main__":
    unittest.main()