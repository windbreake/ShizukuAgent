"""Session-scoped permission questions; waiting tools never block the ASGI loop."""
import contextvars
import threading
import time
import uuid
from contextlib import contextmanager
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

scope=contextvars.ContextVar('approval_scope',default=None)
grant=contextvars.ContextVar('approved_path',default=None)
lock=threading.RLock()
pending={}
allowed=set()

class ApprovalDenied(Exception): pass

@contextmanager
def session_scope(thread_id,persona):
    token=scope.set((thread_id or f'persona:{persona}',persona))
    try: yield
    finally: scope.reset(token)

def ask(kind,detail,choices=None):
    session=scope.get()
    if session is None: raise ApprovalDenied('此操作需要会话内审批')
    key=(*session,kind,detail)
    with lock:
        if not choices and key in allowed:return None
        request_id=uuid.uuid4().hex
        record={'id':request_id,'thread_id':session[0],'persona':session[1],'kind':kind,'detail':detail,'choices':choices or [],'created_at':time.time(),'event':threading.Event(),'decision':None,'selected':None}
        pending[request_id]=record
    try:
        if not record['event'].wait(300):raise ApprovalDenied('审批等待超时，本轮已停止')
        if record['decision']=='reject':raise ApprovalDenied('用户拒绝操作，本轮已停止')
        return record['selected']
    finally:
        with lock:pending.pop(request_id,None)

router=APIRouter(prefix='/api/approvals')
class Decision(BaseModel):
    thread_id:str
    persona:str
    decision:str
    selected:str|None=None

@router.get('')
def list_pending(thread_id:str,persona:str):
    with lock:return {'success':True,'items':[{k:v for k,v in item.items() if k not in {'event','decision','selected'}} for item in pending.values() if item['thread_id']==thread_id and item['persona']==persona]}

@router.post('/{request_id}')
def reply(request_id:str,body:Decision):
    with lock:
        item=pending.get(request_id)
        if not item or (item['thread_id'],item['persona'])!=(body.thread_id,body.persona):raise HTTPException(404,'审批不存在')
        if item['event'].is_set():raise HTTPException(409,'审批已处理')
        if body.decision not in {'once','always','reject'}:raise HTTPException(400,'无效审批结果')
        if item['choices'] and body.decision!='reject' and body.selected not in [c['id'] for c in item['choices']]:raise HTTPException(400,'请选择具体模型')
        if body.decision=='always' and not item['choices']:allowed.add((body.thread_id,body.persona,item['kind'],item['detail']))
        item['decision']=body.decision;item['selected']=body.selected;item['event'].set()
    return {'success':True}
