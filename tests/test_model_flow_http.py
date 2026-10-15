"""Exercise real HTTP model discovery and the app's draft/save boundary."""
import json
import threading
import unittest
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.model_registry import model_registry


class ModelFlowHttpTests(unittest.TestCase):
    def test_discovery_then_apply_and_save_names(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                received.append((self.path,self.headers.get('Authorization'),self.headers.get('X-Workspace')))
                if self.path!='/v1/models':
                    self.send_response(404);self.end_headers();return
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(json.dumps({'data':[{'id':'remote/a','display_name':'Remote Alpha','owned_by':'vendor','context_length':200000},{'id':'remote/b'}]}).encode())
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        snapshot={'providers':{'p':{'name':'Demo','base_url':base,'api_key':'stored-key'}},'models':{'primary':{'provider':'p','model':'remote/a','name':'Primary Agent Model','capabilities':['chat']}},'model_groups':{'default':{'purpose':'agent','models':['primary']}},'default_model_group':'default','auxiliary_apis':{}}
        try:
            with patch.object(model_registry,'snapshot',side_effect=lambda **kwargs:deepcopy(snapshot)),patch.object(model_registry,'update') as update:
                client=TestClient(app)
                discovery=client.post('/api/providers/discover',json={'provider_id':'p','name':'Demo','base_url':base,'api_key':'','request_headers':{'X-Workspace':'test'},'models':[]})
                self.assertEqual(200,discovery.status_code)
                data=discovery.json()
                self.assertEqual(base+'/v1',data['api_base_url'])
                self.assertEqual('Remote Alpha',data['models'][0]['name'])
                self.assertEqual('stored-key',snapshot['providers']['p']['api_key'])
                update.assert_not_called()
                self.assertEqual(('/v1/models','Bearer stored-key','test'),received[-1])
                saved=client.put('/api/providers/p',json={'provider_id':'p','name':'Demo','base_url':data['api_base_url'],'models':['remote/a','remote/b'],'model_names':{'remote/a':'Remote Alpha','remote/b':'My Beta'}})
                self.assertEqual(200,saved.status_code)
                written=update.call_args.args[0]
                self.assertEqual('Remote Alpha',written['models']['primary']['name'])
                self.assertEqual({'Remote Alpha','My Beta'},set(m['name'] for m in written['models'].values()))
                self.assertEqual(2,len(written['model_groups']['provider:p']['models']))
                self.assertEqual(base+'/v1',written['providers']['p']['base_url'])
                self.assertEqual('stored-key',written['providers']['p']['api_key'])
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
