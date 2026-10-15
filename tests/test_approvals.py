import threading
import time
import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.approvals import session_scope,ask,ApprovalDenied

class ApprovalTests(unittest.TestCase):
    def execute_question(self, decision, choices=None):
        result=[]
        thread_id='approval-test-'+str(time.time_ns())
        def worker():
            with session_scope(thread_id,'shizuku'):
                try: result.append(ask('test','resource',choices))
                except ApprovalDenied: result.append('denied')
        thread=threading.Thread(target=worker);thread.start()
        client=TestClient(app)
        try:
            for _ in range(50):
                items=client.get('/api/approvals',params={'thread_id':thread_id,'persona':'shizuku'}).json()['items']
                if items:break
                time.sleep(.01)
            self.assertTrue(thread.is_alive())
            response=client.post('/api/approvals/'+items[0]['id'],json={'thread_id':thread_id,'persona':'shizuku','decision':decision,'selected':'model-b' if choices else None})
            self.assertEqual(200,response.status_code)
            thread.join(2);self.assertFalse(thread.is_alive())
            return result
        finally:
            if thread.is_alive():
                client.post('/api/approvals/'+items[0]['id'],json={'thread_id':thread_id,'persona':'shizuku','decision':'reject'})
                thread.join(2)

    def test_allow_resumes(self):self.assertEqual([None],self.execute_question('once'))
    def test_reject_terminates(self):self.assertEqual(['denied'],self.execute_question('reject'))
    def test_user_selects_auxiliary(self):self.assertEqual(['model-b'],self.execute_question('once',[{'id':'model-a','name':'A'},{'id':'model-b','name':'B'}]))

    def test_external_read_is_allowed_in_chat_and_sandbox_without_approval(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app.agent.nodes.tool_executor_node import ToolExecutorNode
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'workspace';root.mkdir()
            outside=Path(folder)/'outside.txt';outside.write_text('approved content',encoding='utf-8')
            state={'messages':[{'role':'assistant','content':'','tool_calls':[{'id':'read-1','function':{'name':'read_file','arguments':{'path':str(outside)}}}]}],'traces':[],'tool_result':[],'tool_rounds':0,'persona':'shizuku','model_config':{'workbench_mode':'full'}}
            result=[];thread_id='external-'+str(time.time_ns())
            def execute():
                with session_scope(thread_id,'shizuku'):result.append(ToolExecutorNode()(state))
            with patch('app.agent.tools.WORKSPACE',root):
                for mode in ['chat','sandbox']:
                    state['model_config']['workbench_mode']=mode
                    execute()
                    self.assertEqual('approved content',result[-1]['messages'][0]['content'])
                    self.assertEqual([],TestClient(app).get('/api/approvals',params={'thread_id':thread_id,'persona':'shizuku'}).json()['items'])

    def test_mode_policy_blocks_unisolated_execution(self):
        from app.agent.permissions import allowed
        for mode in ['chat','sandbox']:
            self.assertTrue(allowed('read_file',mode))
            self.assertTrue(allowed('list_dir',mode))
            for name in ['run_skill','call_mcp','run_local_agent']:
                self.assertFalse(allowed(name,mode))
        self.assertFalse(allowed('write_file','chat'))
        self.assertTrue(allowed('write_file','sandbox'))
