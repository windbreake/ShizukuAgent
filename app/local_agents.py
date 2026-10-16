from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class LocalAgent:
    id: str
    name: str
    commands: list[str]
    description: str
    run_args: list[str]


AGENTS = [
    LocalAgent("opencode", "OpenCode", ["opencode"], "本机 OpenCode CLI", ["run"]),
    LocalAgent("hermes", "Hermes Agent", ["hermes", "hermes-agent"], "本机 Hermes Agent", []),
    LocalAgent("codex", "Codex", ["codex"], "本机 Codex CLI", ["exec"]),
    LocalAgent("claude", "Claude / Cloud Code", ["claude", "cloudcode"], "本机 Claude Code / Cloud Code", ["-p"]),
    LocalAgent("openclaw", "OpenClaw", ["openclaw"], "本机 OpenClaw", []),
    LocalAgent("astrbot", "AstrBot", ["astrbot", "astr"], "本机 AstrBot", []),
]


def _which(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    extra = []
    home = Path.home()
    extra.extend(
        [
            home / "AppData" / "Roaming" / "npm" / f"{name}.cmd",
            home / "AppData" / "Local" / "Programs" / name / f"{name}.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / name / f"{name}.exe",
        ]
    )
    for path in extra:
        if path and path.exists():
            return str(path)
    return ""


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _version(exe: str) -> str:
    for args in ([exe, "--version"], [exe, "-V"], [exe, "version"]):
        try:
            proc = _run(args, 4)
            text = (proc.stdout or proc.stderr or "").strip().splitlines()
            if text:
                return text[0][:120]
        except Exception:
            continue
    return ""


def detect_agents() -> list[dict[str, Any]]:
    items = []
    for agent in AGENTS:
        exe = ""
        matched = ""
        for command in agent.commands:
            exe = _which(command)
            if exe:
                matched = command
                break
        items.append(
            {
                **asdict(agent),
                "installed": bool(exe),
                "command": matched,
                "path": exe,
                "version": _version(exe) if exe else "",
            }
        )
    return items


def run_agent(agent_id: str, prompt: str, timeout: int = 60) -> dict[str, Any]:
    agent = next((item for item in detect_agents() if item["id"] == agent_id), None)
    if not agent:
        return {"success": False, "error": f"未知 Agent: {agent_id}"}
    if not agent["installed"]:
        return {"success": False, "error": f"{agent['name']} 未在本机 PATH 中找到"}
    cmd = [agent["path"], *agent["run_args"], prompt]
    try:
        proc = _run(cmd, timeout)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"{agent['name']} 执行超时"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    output = (proc.stdout or proc.stderr or "").strip()
    return {
        "success": proc.returncode == 0,
        "agent": agent["id"],
        "command": cmd,
        "returncode": proc.returncode,
        "output": output[:8000],
    }
