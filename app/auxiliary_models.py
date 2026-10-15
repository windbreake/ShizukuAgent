"""Capability-filtered auxiliary model calls, approved in the conversation dock."""
from app.approvals import ask
from app.model_registry import model_registry

CAPABILITIES={'images':'image','speech':'speech','search':'search','embeddings':'embedding'}

def candidates(kind):
    capability=CAPABILITIES.get(kind)
    if not capability: raise ValueError('未知辅助能力')
    snapshot=model_registry.snapshot()
    found=[]
    for key,model in snapshot['models'].items():
        if model.get('enabled',True) and capability in model.get('capabilities',[]):
            provider=snapshot['providers'].get(model.get('provider'),{})
            if provider and provider.get('enabled',True):
                found.append({'id':key,'name':f"{provider.get('name',model['provider'])} / {model.get('name') or model['model']}"})
    # Existing auxiliary bindings are candidates, never automatic hidden fallbacks.
    binding=snapshot['auxiliary_apis'].get(kind,{})
    model_id=binding.get('model')
    if binding.get('enabled') and model_id and model_id not in [m['id'] for m in found]:
        try:
            model=model_registry.resolve_model(model_id)
            if capability in model.get('capabilities',[]):found.append({'id':model_id,'name':model.get('name') or model['model']})
        except ValueError:pass
    return found

def invoke(kind, prompt):
    choices=candidates(kind)
    if not choices:raise ValueError('没有配置此能力的辅助模型，请在模型配置中添加能力标签')
    selected=ask('auxiliary_model',f'{kind}\n{prompt}',choices)
    model=model_registry.resolve_model(selected)
    provider=model['provider_config']
    from openai import OpenAI
    client=OpenAI(api_key=provider.get('api_key') or 'local-no-key',base_url=provider.get('base_url'),default_headers=provider.get('request_headers') or None,timeout=60,max_retries=0)
    if kind=='images':
        response=client.images.generate(model=model['model'],prompt=prompt,n=1)
        return response.model_dump_json()
    if kind=='speech':
        from app.paths import DATA_DIR
        import uuid
        target=DATA_DIR/'generated'/f'{uuid.uuid4().hex}.mp3'
        target.parent.mkdir(parents=True,exist_ok=True)
        response=client.audio.speech.create(model=model['model'],input=prompt,voice=model.get('voice','alloy'))
        response.stream_to_file(target)
        return {'path':str(target),'model_id':selected}
    if kind=='embeddings':return client.embeddings.create(model=model['model'],input=prompt).model_dump_json()
    return client.chat.completions.create(model=model['model'],messages=[{'role':'user','content':prompt}],max_tokens=2048).model_dump_json()
