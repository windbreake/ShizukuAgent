from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from app.paths import CONFIG_DIR, DATA_DIR, ensure_runtime_dirs


DEFAULT_CONFIG: dict[str, Any] = {
    "server": {"host": "127.0.0.1", "port": 8000},
    "storage": {
        "driver": "sqlite",
        "sqlite": {"path": "data/storage/agent.db"},
        "mysql": {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "password": "",
            "database": "shizukuclaw",
        },
        "postgresql": {
            "host": "127.0.0.1",
            "port": 5432,
            "user": "postgres",
            "password": "",
            "database": "shizukuclaw",
        },
    },
    "llm": {
        "provider": "openai_compatible",
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "api_key": os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "",
    },
    "providers": {
        "openai": {
            "name": "OpenAI",
            "type": "openai_compatible",
            "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            "api_key": os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "",
        }
    },
    "models": {
        "primary": {
            "provider": "openai",
            "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
            "name": "Primary Agent Model",
            "capabilities": ["chat", "tools", "vision"],
            "enabled": True,
            "auxiliary_only": False,
        }
    },
    "model_groups": {
        "default": {"name": "Default Agent", "purpose": "agent", "strategy": "fallback", "models": ["primary"]}
    },
    "default_model_group": "default",
    "auxiliary_apis": {
        "search": {"enabled": False, "model": "primary", "endpoint": "/chat/completions"},
        "speech": {"enabled": False, "model": "primary", "endpoint": "/audio/speech"},
        "images": {"enabled": False, "model": "primary", "endpoint": "/images/generations"},
    },
    "database": {
        "engine": "sqlite",
        "host": "",
        "user": "",
        "password": "",
        "database": "data/storage/agent.db",
        "port": 0,
    },
    "api_keys": {
        "primary": {
            "key": os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "",
            "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        },
    },
    "character": {
        "name": "Shizuku",
        "personality": "冷静、可靠、带一点陪伴感",
        "brother_qqid": "",
        "height": "",
        "weight": "",
        "catchphrases": "交给我吧,先确认再动手",
    },
    "security": {
        "initialized": False,
        "level1_password_hash": "",
        "level2_password_hash": "",
    },
    "work_mode": {"enabled": False},
    "langsmith": {
        "enabled": False,
        "api_key": "",
        "project": "shizukuclaw",
        "endpoint": "https://api.smith.langchain.com",
    },
    "unified_api": {"port": 8000},
    "agent": {
        "default_persona": "shizuku",
        "thread_id": "default",
    },
}


class Settings:
    def __init__(self) -> None:
        ensure_runtime_dirs()
        self.settings_path = CONFIG_DIR / "settings.yaml"
        self.storage_path = CONFIG_DIR / "storage.yaml"
        self.runtime_config_path = DATA_DIR / "config.json"
        self._data = deepcopy(DEFAULT_CONFIG)
        self.reload()

    def reload(self) -> None:
        self._data = deepcopy(DEFAULT_CONFIG)
        self._merge_yaml(self.settings_path)
        self._merge_yaml(self.storage_path)
        if self.runtime_config_path.exists():
            try:
                loaded = json.loads(self.runtime_config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data = _deep_merge(self._data, loaded)
            except Exception:
                pass
        self._apply_env_overrides()

    def _merge_yaml(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                self._data = _deep_merge(self._data, loaded)
        except Exception:
            pass

    def _apply_env_overrides(self) -> None:
        driver = os.getenv("STORAGE_DRIVER")
        if driver:
            self._data.setdefault("storage", {})["driver"] = driver.lower()
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        if api_key:
            self._data.setdefault("llm", {})["api_key"] = api_key
        base_url = os.getenv("LLM_BASE_URL")
        if base_url:
            self._data.setdefault("llm", {})["base_url"] = base_url
        model = os.getenv("LLM_MODEL")
        if model:
            self._data.setdefault("llm", {})["model"] = model

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self._data)

    def update(self, incoming: dict[str, Any], *, replace_keys: tuple[str, ...] = ()) -> dict[str, Any]:
        self._data = _deep_merge(self._data, incoming)
        for key in replace_keys:
            if key in incoming:
                self._data[key] = deepcopy(incoming[key])
        llm = self._data.get("llm") or {}
        self._data["api_keys"] = {
            "primary": {
                "key": llm.get("api_key") or "",
                "base_url": llm.get("base_url") or "",
                "model": llm.get("model") or "",
            }
        }
        self.runtime_config_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_config_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.as_dict()

    @property
    def storage_driver(self) -> str:
        return str(self._data.get("storage", {}).get("driver", "sqlite")).lower()


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


settings = Settings()
