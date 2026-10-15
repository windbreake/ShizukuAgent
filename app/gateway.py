"""API and WebSocket connection settings for the shared backend listener."""
import asyncio
import json
import uuid
import logging
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from app.config import settings

router = APIRouter()


class GatewayConfig(BaseModel):
    host: str = Field(default='127.0.0.1', pattern=r'^(localhost|(?:\d{1,3}\.){3}\d{1,3})$')
    port: int = Field(default=8888, ge=1, le=65535)
    api_enabled: bool = True
    websocket_enabled: bool = False


def config():
    saved = settings.get('unified_api') or {}
    return GatewayConfig.model_validate({**saved, 'port': saved.get('port') or 8888})


def require_api():
    from fastapi import HTTPException
    if not config().api_enabled:
        raise HTTPException(503, 'API 网关已停用')


@router.get('/api/gateway')
def get_gateway(request: Request):
    cfg = config().model_dump()
    current = request.scope.get('server')
    return {'success': True, 'config': cfg, 'current': {'host': current[0], 'port': current[1]} if current else None}


@router.put('/api/gateway')
def save_gateway(body: GatewayConfig):
    settings.update({'unified_api': {**(settings.get('unified_api') or {}), **body.model_dump()}})
    return {'success': True, 'config': body.model_dump(), 'message': '配置已保存；监听地址和端口在重启服务后生效，连接开关立即生效。'}


class SocketChat(BaseModel):
    message: str = Field(min_length=1, max_length=100000)
    thread_id: str = Field(min_length=1, max_length=200)
    persona: str | None = None
    model_group: str | None = None
    model_id: str | None = None
    reasoning_effort: str = 'default'


@router.websocket('/ws/chat')
async def socket_chat(websocket: WebSocket):
    if not config().websocket_enabled:
        await websocket.close(code=1008, reason='WebSocket 网关已停用')
        return
    await websocket.accept()
    from app.agent.agent_service import get_agent_service
    from app.approvals import session_scope, ApprovalDenied
    from app.task_plans import read
    try:
        while True:
            try:
                payload = await websocket.receive_json()
                body = SocketChat.model_validate(payload)
            except (ValidationError, ValueError, TypeError) as exc:
                await websocket.send_json({'type': 'error', 'error': str(exc)})
                continue
            if not config().websocket_enabled:
                await websocket.close(code=1008)
                return
            service = get_agent_service()
            persona = body.persona or service.default_persona()
            request_id = uuid.uuid4().hex
            await websocket.send_json({'type': 'started', 'request_id': request_id, 'thread_id': body.thread_id})

            def execute():
                with session_scope(body.thread_id, persona):
                    try:
                        return service.run(body.message, persona=persona, thread_id=body.thread_id, model_group=body.model_group, model_id=body.model_id, reasoning_effort=body.reasoning_effort)
                    except ApprovalDenied as exc:
                        return {'success': True, 'reply': str(exc), 'engine': 'permission-rejected', 'persona': persona}

            task = asyncio.create_task(run_in_threadpool(execute))
            # A disconnected client must not leave an unobserved worker error.
            def observe(future):
                if not future.cancelled() and future.exception() is not None:
                    logging.getLogger(__name__).warning('WebSocket agent request failed: %s', type(future.exception()).__name__)
            task.add_done_callback(observe)
            last = None
            while not task.done():
                await asyncio.wait({task}, timeout=.35)
                plan = read(body.thread_id, persona)
                encoded = json.dumps(plan)
                if encoded != last:
                    await websocket.send_json({'type': 'plan', 'request_id': request_id, **plan})
                    last = encoded
            try:
                result = task.result()
                await websocket.send_json({'type': 'result', 'request_id': request_id, 'data': result})
            except Exception as exc:
                await websocket.send_json({'type': 'error', 'request_id': request_id, 'error': str(exc)})
    except WebSocketDisconnect:
        return
