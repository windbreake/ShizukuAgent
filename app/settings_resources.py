"""Editable runtime documents and imported voice assets."""
import io
import json
import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.paths import DATA_DIR, PERSONAS_DIR
from app.persona_store import ensure_personas
from app.mcp_manager import get_mcp_manager
from app.skill_manager import get_skill_manager

router = APIRouter(prefix='/api/settings-resources')


def document_path(kind: str, key: str, filename: str) -> Path:
    if kind == 'mcp':
        manager = get_mcp_manager()
        return manager.registry_path
    if kind == 'persona':
        ensure_personas()
        base = PERSONAS_DIR
        folder = base / key
    elif kind == 'skill':
        manager = get_skill_manager()
        base = manager.skills_dir
        meta = next((item for item in manager.list_skills() if item['skill_id'] == key), None)
        if meta is None:
            raise HTTPException(404, '技能不存在')
        folder = Path(meta['path'])
    else:
        raise HTTPException(400, '未知资源类型')
    path = (folder / filename).resolve()
    if not path.is_relative_to(base.resolve()) or path.suffix.lower() not in {'.json', '.md'}:
        raise HTTPException(400, '请选择资源目录内的 JSON 或 Markdown 文件')
    return path


@router.get('/document')
def read_document(kind: str, key: str = '', filename: str = 'persona.json'):
    path = document_path(kind, key, filename)
    if not path.is_file():
        if kind == 'persona' and filename == 'PERSONA.md' and (path.parent / 'persona.json').is_file():
            legacy = path.parent / 'SKILL.md'
            content = legacy.read_text(encoding='utf-8') if legacy.is_file() else f'# {key}\n\n人格说明。人设与提示词保存在 persona.json。\n'
            return {'success': True, 'content': content, 'name': filename}
        raise HTTPException(404, '文件不存在')
    return {'success': True, 'content': path.read_text(encoding='utf-8'), 'name': path.name}


class Document(BaseModel):
    kind: str
    key: str = ''
    filename: str = 'persona.json'
    content: str


@router.put('/document')
def save_document(body: Document):
    path = document_path(body.kind, body.key, body.filename)
    if len(body.content.encode('utf-8')) > 2 * 1024 * 1024:
        raise HTTPException(413, '配置文件过大')
    if path.suffix == '.json':
        try:
            data = json.loads(body.content)
            if not isinstance(data, dict):
                raise ValueError('JSON 顶层必须为对象')
            if body.kind == 'mcp':
                from app.mcp_manager import MCPServer
                if not isinstance(data.get('servers'), list):
                    raise ValueError('需要 servers 数组')
                ids = []
                for server in data['servers']:
                    parsed = MCPServer(**server)
                    ids.append(parsed.id)
                if len(ids) != len(set(ids)):
                    raise ValueError('服务器 ID 不能重复')
            if body.kind == 'persona':
                for field in ('meta', 'character', 'system_prompt'):
                    if field in data and not isinstance(data[field], dict):
                        raise ValueError(f'{field} 必须为对象')
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(body.content, encoding='utf-8')
    temporary.replace(path)
    if body.kind == 'mcp':
        manager = get_mcp_manager()
        # Keep separately installed server files consistent with the edited registry.
        for config in manager.mcp_dir.glob('*.json'):
            if config == manager.registry_path:
                continue
            try:
                existing = json.loads(config.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                continue
            server_id = str(existing.get('id') or config.stem)
            replacement = next((s for s in data['servers'] if s['id'] == server_id), None)
            if replacement is None:
                config.unlink()
            else:
                config.write_text(json.dumps(replacement, ensure_ascii=False, indent=2), encoding='utf-8')
        manager.reload()
    elif body.kind == 'skill':
        get_skill_manager().reload()
    return {'success': True}


def voice_root():
    return DATA_DIR / 'tts' / 'assets'


@router.get('/tts')
def list_voice_assets():
    root = voice_root()
    return {'success': True, 'items': [{'id': p.name, 'name': p.name, 'files': sum(1 for f in p.rglob('*') if f.is_file())} for p in sorted(root.iterdir()) if p.is_dir()] if root.exists() else [], 'selected': (settings.get('tts') or {}).get('asset', '')}


@router.post('/tts/import')
async def import_voice_assets(request: Request, filename: str):
    # Folder uploads are packed by the client as a sequence of binary requests.
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 256 * 1024 * 1024:
            raise HTTPException(413, '单次导入不能超过 256 MB')
    root = voice_root()
    root.mkdir(parents=True, exist_ok=True)
    name = Path(filename).stem
    if not name or '/' in name or '\\' in name or name in {'.', '..'}:
        raise HTTPException(400, '无效资源名称')
    target = root / f'{name}-{uuid.uuid4().hex[:8]}'
    target.mkdir()
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            total = 0
            for item in archive.infolist():
                destination = (target / item.filename).resolve()
                total += item.file_size
                if not destination.is_relative_to(target.resolve()) or total > 1024 * 1024 * 1024:
                    raise ValueError('压缩包路径无效或解压后超过 1 GB')
                if item.is_dir():
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, destination.open('wb') as output:
                    shutil.copyfileobj(source, output)
        if not any(p.is_file() for p in target.rglob('*')):
            raise ValueError('压缩包中没有文件')
    except (ValueError, zipfile.BadZipFile, RuntimeError, OSError) as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise HTTPException(400, str(exc)) from exc
    return {'success': True, 'id': target.name}


class VoiceSelection(BaseModel):
    asset: str


@router.put('/tts')
def select_voice_asset(body: VoiceSelection):
    root = voice_root().resolve()
    target = (root / body.asset).resolve()
    if body.asset and (not target.is_relative_to(root) or target == root or not target.is_dir()):
        raise HTTPException(400, '资源不存在')
    settings.update({'tts': {**(settings.get('tts') or {}), 'asset': body.asset}})
    return {'success': True}
