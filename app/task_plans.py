"""Persistent session task lists, updated explicitly by the agent's tools."""
import contextvars
import hashlib
import json
import threading
import uuid
from contextlib import contextmanager
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.paths import DATA_DIR

router = APIRouter(prefix='/api/task-plan')
current = contextvars.ContextVar('task_plan_session', default=None)
lock = threading.RLock()
active_sessions = set()


class Task(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    status: Literal['pending', 'in_progress', 'completed', 'cancelled']
    priority: Literal['high', 'medium', 'low'] = 'medium'


def path_for(thread_id, persona):
    key = hashlib.sha256(json.dumps([thread_id, persona]).encode()).hexdigest()
    return DATA_DIR / 'task-plans' / f'{key}.json'


def read(thread_id, persona):
    with lock:
        path = path_for(thread_id, persona)
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        return {'items': [], 'running': False, 'run_id': ''}


def persist(thread_id, persona, data):
    path = path_for(thread_id, persona)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


@contextmanager
def execution(thread_id, persona):
    run_id = uuid.uuid4().hex
    with lock:
        if (thread_id, persona) in active_sessions:
            raise ValueError('此会话已有任务正在执行，请等待完成')
        previous = read(thread_id, persona)
        persist(thread_id, persona, {'items': previous.get('items', []), 'running': True, 'run_id': run_id})
        active_sessions.add((thread_id, persona))
    token = current.set((thread_id, persona, run_id))
    try:
        yield
    finally:
        with lock:
            active_sessions.discard((thread_id, persona))
            data = read(thread_id, persona)
            if data['run_id'] == run_id:
                data['running'] = False
                persist(thread_id, persona, data)
        current.reset(token)


def write_todos(todos):
    session = current.get()
    if session is None:
        raise ValueError('任务计划需要运行中的会话')
    if not isinstance(todos, list) or len(todos) > 50:
        raise ValueError('任务列表最多 50 项')
    items = [Task.model_validate(item).model_dump() for item in todos]
    if sum(item['status'] == 'in_progress' for item in items) > 1:
        raise ValueError('同一时间只能有一个正在执行的任务')
    thread, persona, run_id = session
    with lock:
        data = read(thread, persona)
        if data.get('run_id') != run_id or not data.get('running'):
            raise ValueError('本轮任务已经结束')
        data['items'] = items
        persist(thread, persona, data)
    return items


def read_todos():
    session = current.get()
    if session is None:
        raise ValueError('任务计划需要会话')
    return read(session[0], session[1])['items']


@router.get('')
def get_plan(thread_id: str, persona: str):
    with lock:
        data = read(thread_id, persona)
        data['running'] = (thread_id, persona) in active_sessions
        return {'success': True, **data}


def register(registry):
    item_schema = {'type': 'object', 'properties': {
        'content': {'type': 'string'},
        'status': {'type': 'string', 'enum': ['pending', 'in_progress', 'completed', 'cancelled']},
        'priority': {'type': 'string', 'enum': ['high', 'medium', 'low']},
    }, 'required': ['content', 'status', 'priority']}
    registry.register('todowrite', write_todos, {'type': 'function', 'function': {
        'name': 'todowrite',
        'description': 'Create/update the full session task plan for multi-step work. Mark exactly one task in_progress, update after each meaningful step, and mark completed only after verification. Do not create a plan for simple conversation.',
        'parameters': {'type': 'object', 'properties': {'todos': {'type': 'array', 'items': item_schema}}, 'required': ['todos']},
    }})
    registry.register('todoread', read_todos, {'type': 'function', 'function': {
        'name': 'todoread', 'description': 'Read the current session task plan.',
        'parameters': {'type': 'object', 'properties': {}},
    }})
