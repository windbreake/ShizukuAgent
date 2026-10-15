from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
PLUGINS_DIR = ROOT / "plugins"
SKILLS_DIR = PLUGINS_DIR / "skills"
PERSONAS_DIR = PLUGINS_DIR / "personas"
MCP_DIR = PLUGINS_DIR / "mcp"
OBSERVABILITY_DIR = PLUGINS_DIR / "observability"
STORAGE_DIR = DATA_DIR / "storage"
LOG_DIR = DATA_DIR / "logs"
FRONTEND_DIR = ROOT / "frontend"
STATIC_DIR = APP_DIR / "static"


def ensure_runtime_dirs() -> None:
    for path in (
        DATA_DIR,
        CONFIG_DIR,
        PLUGINS_DIR,
        SKILLS_DIR,
        PERSONAS_DIR,
        MCP_DIR,
        OBSERVABILITY_DIR,
        STORAGE_DIR,
        LOG_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
