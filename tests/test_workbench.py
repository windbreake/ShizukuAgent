import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

class WorkbenchTests(unittest.TestCase):
    def test_modes_are_exclusive(self):
        from app.config import settings
        state={'enabled': True, 'sandbox_enabled': False}
        def update(value): state.update(value['work_mode'])
        with patch.object(settings,'get',side_effect=lambda key,default=None:state if key=='work_mode' else default),patch.object(settings,'update',side_effect=update):
            client=TestClient(app)
            self.assertEqual(200,client.post('/api/work_mode/toggle',json={'mode':'sandbox'}).status_code)
            self.assertFalse(state['enabled']);self.assertTrue(state['sandbox_enabled'])
            client.post('/api/work_mode/toggle',json={'mode':'chat'})
            self.assertFalse(state['enabled']);self.assertFalse(state['sandbox_enabled'])

    def test_files_and_shell(self):
        with tempfile.TemporaryDirectory() as folder,patch('app.agent.tools.WORKSPACE',Path(folder)),patch('app.workbench.settings.get',return_value={'enabled':True}):
            client=TestClient(app)
            (Path(folder)/'example.txt').write_text('content',encoding='utf-8')
            self.assertEqual('content',client.get('/api/workbench/files',params={'path':'example.txt'}).json()['content'])
            self.assertEqual(400,client.get('/api/workbench/files',params={'path':'../escape'}).status_code)
            result=client.post('/api/workbench/shell',json={'command':'echo workbench_test'})
            self.assertEqual(0,result.json()['exit_code']);self.assertIn('workbench_test',result.json()['stdout'])

    def test_shell_mode_gate(self):
        with patch('app.workbench.settings.get',return_value={'enabled':False}):
            self.assertEqual(403,TestClient(app).post('/api/workbench/shell',json={'command':'echo test'}).status_code)
