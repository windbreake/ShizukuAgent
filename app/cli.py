from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.agent.agent_service import AgentService, get_agent_service


ROOT = Path(__file__).resolve().parent.parent


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nekoagent", description="NekoAgent terminal and web interface")
    subparsers = parser.add_subparsers(dest="command")
    web = subparsers.add_parser("web", help="start the visual web interface")
    web.add_argument("--no-frontend", action="store_true", help="start only the backend")
    web.add_argument("--no-reload", action="store_true", help="disable backend auto reload")
    parser.add_argument("--persona", default=None, help="persona used by terminal chat")
    parser.add_argument("--thread", default=None, help="conversation thread id")
    parser.add_argument("--model-group", default=None, help="agent model group")
    return parser


def run_chat(service: AgentService, persona: str | None = None, thread_id: str | None = None, model_group: str | None = None) -> int:
    current_persona = persona or service.default_persona()
    current_thread = thread_id or f"cli:{current_persona}"
    print("NekoAgent CLI | 输入 /help 查看命令，输入 /exit 退出。")
    print(f"persona={current_persona} thread={current_thread}")

    while True:
        try:
            question = input("\n你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            return 0
        if not question:
            continue
        if question in {"/exit", "/quit", ":q"}:
            print("已退出。")
            return 0
        if question == "/help":
            print("/help                 显示帮助")
            print("/clear                清空当前会话")
            print("/persona [name]       查看或切换人格")
            print("/model [group]        查看或切换模型组")
            print("/exit                 退出 CLI")
            continue
        if question == "/clear":
            service.reset_session(current_thread, current_persona)
            print("当前会话已清空。")
            continue
        if question.startswith("/persona"):
            value = question.partition(" ")[2].strip()
            if value:
                current_persona = value
                current_thread = thread_id or f"cli:{current_persona}"
                print(f"已切换人格: {current_persona}")
            else:
                print(f"当前人格: {current_persona}")
                print("可用人格: " + ", ".join(item.get("id", "") for item in service.available_personas()))
            continue
        if question.startswith("/model"):
            value = question.partition(" ")[2].strip()
            if value:
                model_group = value
                print(f"已切换模型组: {model_group}")
            else:
                print(f"当前模型组: {model_group or '(默认)'}")
            continue

        try:
            result = service.run(
                question,
                persona=current_persona,
                thread_id=current_thread,
                model_group=model_group,
            )
            reply = result.get("reply") or "模型未返回内容。"
            model = result.get("active_model")
            print(f"\n猫 > {reply}")
            if model:
                print(f"[{model}]")
        except Exception as exc:
            print(f"\n错误: {exc}")


def run_web(no_frontend: bool = False, no_reload: bool = False) -> int:
    python = sys.executable
    backend_args = [python, str(ROOT / "scripts" / "run_backend.py")]
    if no_reload:
        backend_args.append("--no-reload")
    processes: list[subprocess.Popen[Any]] = []
    try:
        processes.append(subprocess.Popen(backend_args, cwd=ROOT))
        if not no_frontend:
            import urllib.request
            print('等待后端健康检查通过…')
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if processes[0].poll() is not None:
                    raise RuntimeError('后端启动失败，请检查上方错误日志')
                try:
                    port = (ROOT / 'data' / 'dev_port.txt').read_text().strip()
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as response:
                        if response.status == 200: break
                except (OSError, ValueError):
                    pass
                time.sleep(.25)
            else:
                raise RuntimeError('后端 60 秒内未就绪，前端未启动')
            npm = "npm.cmd" if os.name == "nt" else "npm"
            processes.append(subprocess.Popen([npm, "run", "dev"], cwd=ROOT / "frontend"))
        print("NekoAgent web 已启动。前端通常位于 http://127.0.0.1:5173。")
        print("按 Ctrl+C 停止服务。")
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "web":
        return run_web(no_frontend=args.no_frontend, no_reload=args.no_reload)
    return run_chat(get_agent_service(), args.persona, args.thread, args.model_group)


if __name__ == "__main__":
    raise SystemExit(main())
