"""OpenAI-compatible model discovery, inspired by CC Switch's candidate URL flow."""
import json
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def model_urls(base_url, override=''):
    source = (override or base_url).strip()
    parsed = urlsplit(source)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('请输入有效的 HTTP(S) API 地址')
    if override:
        return [source]
    path = parsed.path.rstrip('/')
    for suffix in ('/chat/completions', '/responses'):
        if path.endswith(suffix): path = path[:-len(suffix)]
    paths = [path] if path.endswith('/models') else [path+'/models']
    if not path or path == '/': paths.append('/v1/models')
    if path.endswith('/anthropic'):
        parent=path[:-len('/anthropic')]
        paths.extend([parent+'/models',parent+'/v1/models'])
    return list(dict.fromkeys(urlunsplit((parsed.scheme,parsed.netloc,p,'','')) for p in paths))


def parse_models(body):
    items = body if isinstance(body,list) else body.get('data',body.get('models',[])) if isinstance(body,dict) else []
    if not isinstance(items,list): raise ValueError('模型列表响应缺少 data/models 数组')
    result={}
    for item in items:
        name=item if isinstance(item,str) else item.get('id') or item.get('name') if isinstance(item,dict) else None
        if isinstance(name,str) and name.strip():
            name=name.strip()
            record = item if isinstance(item,dict) else {}
            display = record.get('display_name') or record.get('name') or name
            result[name]={'id':name,'name':str(display),'owned_by':str(record.get('owned_by',''))}
            # Only expose capabilities/limits explicitly returned by the provider.
            for field in ('context_length','context_window','max_output_tokens','capabilities','modalities'):
                if field in record and isinstance(record[field],(int,list,dict)):
                    result[name][field]=record[field]
    return sorted(result.values(),key=lambda item:item['id'])


def fetch_models(provider):
    headers={'Accept':'application/json','User-Agent':provider.get('user_agent') or 'ShizukuClaw/1.0'}
    headers.update(provider.get('request_headers') or {})
    key=provider.get('api_key') or ''
    if key: headers['Authorization']='Bearer '+key
    opener=build_opener(NoRedirect())
    failures=[]
    for url in model_urls(provider.get('base_url',''),provider.get('models_url','')):
        try:
            with opener.open(Request(url,headers=headers),timeout=12) as response:
                raw=response.read(2*1024*1024+1)
                if len(raw)>2*1024*1024: raise ValueError('模型列表响应超过 2 MB')
                models=parse_models(json.loads(raw))
                source=urlsplit(url)
                api_path=source.path[:-len('/models')] if source.path.endswith('/models') else None
                api_base=urlunsplit((source.scheme,source.netloc,api_path,'','')) if api_path is not None else provider.get('base_url','')
                return {'models':models,'source_url':url,'api_base_url':api_base}
        except HTTPError as error:
            failures.append(f'HTTP {error.code}')
            if error.code in {401,403}: break
        except (URLError,ValueError,TimeoutError):
            failures.append('连接失败或模型列表格式无效')
    raise ValueError('获取模型列表失败：'+'；'.join(failures)+'。可手动添加模型 ID；现有配置未改动。')
