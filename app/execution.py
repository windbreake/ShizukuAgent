"""Per-session execution events and cooperative cancellation."""
import contextvars
import threading
import time
import uuid
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router=APIRouter(prefix='/api/execution')
current=contextvars.ContextVar('execution',default=None)
lock=threading.RLock()
runs={}
workers=ThreadPoolExecutor(max_workers=8)

class Stopped(Exception): pass

@contextmanager
def running(thread,persona):
    record={'run_id':uuid.uuid4().hex,'events':[],'stopped':threading.Event(),'running':True}
    with lock:runs[(thread,persona)]=record
    token=current.set(record)
    try:yield
    finally:
        record['running']=False
        current.reset(token)

def check():
    record=current.get()
    if record and record['stopped'].is_set():raise Stopped('已中止本轮回复')

def event(kind,title,**details):
    check()
    record=current.get()
    if record:
        with lock:
            record['events'].append({'id':len(record['events']),'kind':kind,'title':title,'time':time.time(),**details})

def delta(text):
    check()
    record=current.get()
    if not record:return
    with lock:
        if record['events'] and record['events'][-1]['kind']=='delta':record['events'][-1]['title']+=text
        else:event('delta',text)

def wait_for(call,*args):
    check()
    future=workers.submit(contextvars.copy_context().run,call,*args)
    while True:
        check()
        try:return future.result(timeout=.1)
        except TimeoutError:continue

@router.get('')
def status(thread_id:str,persona:str):
    with lock:
        record=runs.get((thread_id,persona))
        return {'success':True,'running':bool(record and record['running']), 'run_id':record['run_id'] if record else '', 'events':[dict(item) for item in record['events']] if record else []}

class Stop(BaseModel):
    thread_id:str
    persona:str
    run_id:str

@router.post('/stop')
def stop(body:Stop):
    with lock:
        record=runs.get((body.thread_id,body.persona))
        if not record or record['run_id']!=body.run_id:raise HTTPException(409,'该任务已结束')
        record['stopped'].set()
    return {'success':True}
