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

    def test_external_read_waits_then_runs_with_scoped_grant(self):
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
                thread=threading.Thread(target=execute);thread.start();client=TestClient(app)
                for _ in range(100):
                    items=client.get('/api/approvals',params={'thread_id':thread_id,'persona':'shizuku'}).json()['items']
                    if items:break
                    time.sleep(.01)
                self.assertTrue(items);self.assertFalse(result)
                client.post('/api/approvals/'+items[0]['id'],json={'thread_id':thread_id,'persona':'shizuku','decision':'once'})
                thread.join(3);self.assertFalse(thread.is_alive())
                self.assertEqual('approved content',result[0]['messages'][0]['content'])
