"""Provider-owned model collections: one credential pair, explicit model selection."""
import hashlib
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.model_registry import model_registry, ModelRegistryError
from app.model_discovery import fetch_models
from app.model_identity import model_display_name

router=APIRouter(prefix='/api/providers')

class ModelSelection(BaseModel):
    models: list[str]
    model_names: dict[str,str] = {}
    model_roles: dict[str,str] = {}

class ProviderEdit(BaseModel):
    provider_id: str = ''
    name: str
    base_url: str
    api_key: str = ''
    models: list[str]
    request_headers: dict[str,str] = {}
    models_url: str = ''
    model_names: dict[str,str] = {}
    model_roles: dict[str,str] = {}

@router.put('/{provider_id}')
def save_provider(provider_id: str, body: ProviderEdit):
    from app.model_discovery import model_urls
    try:
        model_urls(body.base_url)
        if not body.models: raise ValueError('至少添加一个模型')
        snapshot=model_registry.snapshot(reveal_secrets=True)
        old=snapshot['providers'].get(provider_id,{})
        if body.provider_id and body.provider_id != provider_id: raise ValueError('提供商标识不一致')
        snapshot['providers'][provider_id]={**old,'name':body.name,'base_url':body.base_url.rstrip('/'),'api_key':body.api_key or old.get('api_key',''),'type':'openai_compatible','request_headers':body.request_headers,'models_url':body.models_url}
        # Build provider and model collection in one registry write.
        import hashlib
        members=[]
        for name in dict.fromkeys(n.strip() for n in body.models if n.strip()):
            key=next((k for k,m in snapshot['models'].items() if m.get('provider')==provider_id and m.get('model')==name),provider_id+'__'+hashlib.sha256(name.encode()).hexdigest()[:12])
            previous=snapshot['models'].get(key,{})
            display=body.model_names.get(name,'').strip() or model_display_name({**previous,'model':name})
            snapshot['models'][key]={**previous,'provider':provider_id,'model':name,'name':display,'enabled':True,'capabilities':previous.get('capabilities',['chat'])}
            role=body.model_roles.get(name)
            if role:
                caps={'chat':['chat'],'images':['image'],'speech':['speech'],'search':['search'],'embeddings':['embedding']}.get(role)
                if caps is None: raise ValueError('无效模型用途')
                snapshot['models'][key]['capabilities']=caps
                snapshot['models'][key]['auxiliary_only']=role!='chat'
            members.append(key)
        if not members: raise ValueError('模型 ID 不能为空')
        for key,m in snapshot['models'].items():
            if m.get('provider')==provider_id and key not in members:m['enabled']=False
        group='provider:'+provider_id
        chat_members=[key for key in members if not snapshot['models'][key].get('auxiliary_only') and 'chat' in snapshot['models'][key].get('capabilities',[])]
        snapshot['model_groups'][group]={'name':body.name,'provider':provider_id,'purpose':'agent' if chat_members else 'auxiliary','strategy':'fallback','models':chat_members or members}
        # Refresh existing provider-owned collections rather than leaving stale members.
        for entry in snapshot['model_groups'].values():
            if entry.get('provider')==provider_id:
                entry['models']=(chat_members or members)[:]
                entry['purpose']='agent' if chat_members else 'auxiliary'
                entry['name']=body.name
        if snapshot['default_model_group'] not in snapshot['model_groups']: snapshot['default_model_group']=group
        model_registry.update(snapshot)
        return {'success':True,'group_id':group}
    except ValueError as error:
        return JSONResponse({'success':False,'error':str(error)},status_code=400)

@router.post('/discover')
def discover_draft(body: ProviderEdit):
    try:
        draft=body.model_dump()
        if not draft['api_key'] and body.provider_id:
            draft['api_key']=model_registry.snapshot(reveal_secrets=True)['providers'].get(body.provider_id,{}).get('api_key','')
        return {'success':True,**fetch_models(draft)}
    except ValueError as error:
        return JSONResponse({'success':False,'error':str(error)},status_code=400)

@router.get('/{provider_id}/models/remote')
def remote_models(provider_id: str):
    provider=model_registry.snapshot(reveal_secrets=True)['providers'].get(provider_id)
    if not provider:
        return JSONResponse({'success':False,'error':'提供商不存在'},status_code=404)
    try:
        return {'success':True,**fetch_models(provider)}
    except ValueError as error:
        return JSONResponse({'success':False,'error':str(error)},status_code=400)

@router.post('/{provider_id}/models/import')
def import_all_models(provider_id: str):
    provider=model_registry.snapshot(reveal_secrets=True)['providers'].get(provider_id)
    if not provider:
        return JSONResponse({'success':False,'error':'提供商不存在'},status_code=404)
    try:
        discovered=fetch_models(provider)
        names=[model['id'] for model in discovered['models']]
        if not names: raise ValueError('远端列表为空，现有配置未改动')
        return select_models(provider_id,ModelSelection(models=names,model_names={m['id']:m.get('name',m['id']) for m in discovered['models']}))
    except ValueError as error:
        return JSONResponse({'success':False,'error':str(error)},status_code=400)

@router.put('/{provider_id}/models')
def select_models(provider_id: str, body: ModelSelection):
    snapshot=model_registry.snapshot(reveal_secrets=True)
    if provider_id not in snapshot['providers']:
        return JSONResponse({'success':False,'error':'提供商不存在'},status_code=404)
    names=list(dict.fromkeys(name.strip() for name in body.models if name.strip()))
    if not names:
        return JSONResponse({'success':False,'error':'至少选择一个模型'},status_code=400)
    owned={key:value for key,value in snapshot['models'].items() if value.get('provider')==provider_id}
    members=[]
    for name in names:
        existing=next((key for key,value in owned.items() if value.get('model')==name),None)
        key=existing or provider_id+'__'+hashlib.sha256(name.encode()).hexdigest()[:12]
        display=body.model_names.get(name,'').strip() or model_display_name({**owned.get(key,{}),'model':name})
        snapshot['models'][key]={**owned.get(key,{}),'provider':provider_id,'model':name,'name':display,'enabled':True,'capabilities':owned.get(key,{}).get('capabilities',['chat']),'auxiliary_only':False}
        members.append(key)
    for key in owned:
        if key not in members:snapshot['models'][key]['enabled']=False
    group_id='provider:'+provider_id
    snapshot['model_groups'][group_id]={'name':snapshot['providers'][provider_id].get('name',provider_id),'provider':provider_id,'models':members,'purpose':'agent','strategy':'fallback'}
    for group in snapshot['model_groups'].values():
        if group.get('provider')==provider_id: group['models']=members[:]
    try:
        model_registry.update(snapshot)
        return {'success':True,'group_id':group_id,**model_registry.snapshot()}
    except ModelRegistryError as error:
        return JSONResponse({'success':False,'error':str(error)},status_code=400)
