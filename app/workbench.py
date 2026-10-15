"""Local workbench operations. All paths are scoped to the agent workspace."""
import os
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent import tools
from app.config import settings

router = APIRouter(prefix="/api/workbench")


class Operation(BaseModel):
    path: str = "."
    command: str = ""
    opener: str = "explorer"
    thread_id: str | None = None
    persona: str = 'shizuku'


class Session(BaseModel):
    thread_id: str
    persona: str


class RevertSession(Session):
    message_id: str


@router.post('/session/revert')
def revert_session(body: RevertSession):
    from app.agent.agent_service import get_agent_service
    from app.persona_store import persona_id
    from app.task_plans import lock, active_sessions, persist
    current = persona_id(body.persona)
    with lock:
        if (body.thread_id, current) in active_sessions:
            return JSONResponse({'success': False, 'error': '请等待当前任务结束后再回退'}, status_code=409)
        service = get_agent_service()
        from app import session_history
        try:
            draft, messages = session_history.revert(service.harness.storage, body.thread_id, current, body.message_id)
        except ValueError as exc:
            return JSONResponse({'success': False, 'error': str(exc)}, status_code=404)
        persist(body.thread_id, current, {'items': [], 'running': False, 'run_id': ''})
        return {'success': True, 'draft': draft, 'messages': messages}


@router.get('/session')
def session(persona: str, thread_id: str | None = None):
    from app.agent.agent_service import get_agent_service
    from app.persona_store import persona_id
    current = persona_id(persona)
    service = get_agent_service()
    thread = thread_id or f'persona:{current}'
    return {'success': True, 'thread_id': thread, 'messages': service.harness.get_history(thread, current)}


@router.post('/session/unrevert')
def unrevert_session(body: Session):
    from app.agent.agent_service import get_agent_service
    from app.persona_store import persona_id
    from app import session_history
    from app.task_plans import lock, active_sessions
    current = persona_id(body.persona)
    with lock:
        if (body.thread_id, current) in active_sessions:
            return JSONResponse({'success': False, 'error': '当前任务正在执行'}, status_code=409)
        storage = get_agent_service().harness.storage
        checkpoint = session_history.load(storage, body.thread_id, current)
        checkpoint.pop('revert', None)
        storage.save_checkpoint(body.thread_id, current, checkpoint)
        return {'success': True, 'messages': checkpoint.get('messages', [])}


@router.post('/session/reset')
def reset_session(body: Session):
    from app.agent.agent_service import get_agent_service
    get_agent_service().reset_session(body.thread_id, body.persona)
    return {'success': True}


def root():
    tools.WORKSPACE.mkdir(parents=True, exist_ok=True)
    return tools.WORKSPACE.resolve()


def path_for(value):
    path = (root() / value).resolve()
    if not path.is_relative_to(root()):
        raise ValueError("路径超出工作区")
    return path


def git(*args):
    result = subprocess.run(["git", "-C", str(root()), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    return result


@router.get("/files")
def files(path: str = "."):
    try:
        target = path_for(path)
        if target.is_file():
            if target.stat().st_size > 1024 * 1024:
                return {"success": False, "error": "文件超过 1 MB，无法预览"}
            return {"success": True, "content": target.read_text(encoding="utf-8", errors="replace"), "path": path}
        return {"success": True, "root": str(root()), "path": path, "entries": [
            {"name": p.name, "path": p.relative_to(root()).as_posix(), "kind": "dir" if p.is_dir() else "file"}
            for p in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())) if p.name != ".git"
        ]}
    except (ValueError, OSError) as error:
        return JSONResponse({"success": False, "error": str(error)}, status_code=400)


@router.get("/changes")
def changes():
    status = git("status", "--short")
    if status.returncode:
        return {"success": True, "initialized": False, "status": "", "diff": ""}
    diff = git("diff", "HEAD", "--", ".")
    if diff.returncode:
        diff = git("diff")
    return {"success": True, "initialized": True, "status": status.stdout, "diff": diff.stdout[:100000]}


@router.post("/git/init")
def init_git():
    result = git("init")
    return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr if result.returncode else ""}


@router.post("/shell")
def shell(body: Operation):
    work = settings.get("work_mode") or {}
    if not work.get("enabled"):
        return JSONResponse({"success": False, "error": "Shell 需要开启完全控制模式"}, status_code=403)
    if not body.command.strip():
        return JSONResponse({"success": False, "error": "命令不能为空"}, status_code=400)
    if body.thread_id:
        from app.approvals import session_scope,ask,ApprovalDenied
        try:
            with session_scope(body.thread_id,body.persona):
                ask('shell',body.command)
        except ApprovalDenied as error:
            return {'success':True,'exit_code':-1,'stdout':'','stderr':str(error)}
    executable = shutil.which("pwsh") or shutil.which("powershell")
    args = [executable, "-NoProfile", "-NonInteractive", "-Command", body.command] if os.name == "nt" and executable else ["/bin/sh", "-c", body.command]
    try:
        result = subprocess.run(args, cwd=root(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return {"success": True, "exit_code": result.returncode, "stdout": result.stdout[:100000], "stderr": result.stderr[:100000]}
    except subprocess.TimeoutExpired:
        return JSONResponse({"success": False, "error": "命令执行超时（60 秒）"}, status_code=408)


@router.post("/open")
def open_path(body: Operation):
    try:
        target = path_for(body.path)
        if not target.exists():
            raise ValueError("文件或目录不存在")
        if body.opener == "explorer":
            if os.name == "nt":
                os.startfile(str(target))
            else:
                subprocess.Popen(["xdg-open", str(target)])
        else:
            commands = {"vscode": "code", "cursor": "cursor", "zed": "zed", "sublime": "subl", "powershell": "pwsh"}
            executable = shutil.which(commands.get(body.opener, ""))
            if not executable:
                raise ValueError("对应程序未安装或不在 PATH 中")
            if body.opener == "powershell":
                subprocess.Popen([executable, "-NoExit"], cwd=target if target.is_dir() else target.parent)
            else:
                subprocess.Popen([executable, str(target)])
        return {"success": True}
    except (ValueError, OSError) as error:
        return JSONResponse({"success": False, "error": str(error)}, status_code=400)
