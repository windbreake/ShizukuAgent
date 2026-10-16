from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.paths import FRONTEND_DIR, ROOT


REQUIRED_NODE_DEPS = ["vue", "pinia", "vue-router", "vite", "@vitejs/plugin-vue", "typescript"]


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, shell=os.name == "nt")


def detect_node() -> dict[str, str | bool]:
    npm = shutil.which("npm")
    node = shutil.which("node")
    return {
        "node": bool(node),
        "npm": bool(npm),
        "node_path": node or "",
        "npm_path": npm or "",
    }


def ensure_frontend_deps() -> dict:
    status = detect_node()
    if not status["npm"]:
        return {"ok": False, "error": "未检测到 npm / Node.js", **status}
    package_json = FRONTEND_DIR / "package.json"
    node_modules = FRONTEND_DIR / "node_modules"
    missing = []
    if package_json.exists():
        pkg = json.loads(package_json.read_text(encoding="utf-8"))
        declared = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        for dep in REQUIRED_NODE_DEPS:
            if dep not in declared:
                missing.append(dep)
            elif not (node_modules / dep).exists():
                missing.append(dep)
    if missing or not node_modules.exists():
        completed = _run(["npm", "install"], FRONTEND_DIR)
        return {
            "ok": completed.returncode == 0,
            "installed": True,
            "missing": missing,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
            **status,
        }
    return {"ok": True, "installed": False, "missing": [], **status}


def ensure_python_deps() -> dict:
    required = ["fastapi", "uvicorn", "pydantic", "yaml"]
    missing = []
    for name in required:
        module = "yaml" if name == "yaml" else name
        try:
            __import__(module)
        except Exception:
            missing.append("pyyaml" if name == "yaml" else name)
    if not missing:
        return {"ok": True, "missing": []}
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "install", *missing],
        capture_output=True,
        text=True,
    )
    return {
        "ok": completed.returncode == 0,
        "missing": missing,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }


def bootstrap() -> dict:
    python_status = ensure_python_deps()
    frontend_status = ensure_frontend_deps()
    return {
        "root": str(ROOT),
        "python": python_status,
        "frontend": frontend_status,
        "ok": bool(python_status.get("ok") and frontend_status.get("ok")),
    }


if __name__ == "__main__":
    print(json.dumps(bootstrap(), ensure_ascii=False, indent=2))
