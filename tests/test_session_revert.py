import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.workbench import router
from app.agent.agent_service import AgentService
from app import task_plans
from test_agent_graph import FakeStorage


class SessionRevertTests(unittest.TestCase):
    def test_revert_boundary_resend_duplicates_and_long_history(self):
        seen=[]
        def model(messages, config):
            seen.append(messages)
            return {'role':'assistant','content':'reply'}
        service=AgentService(storage=FakeStorage(), model_gateway=model)
        app=FastAPI();app.include_router(router)
        client=TestClient(app)
        with tempfile.TemporaryDirectory() as tmp, patch.object(task_plans,'DATA_DIR',Path(tmp)), patch('app.agent.agent_service.get_agent_service',return_value=service):
            for _ in range(23):
                service.run('identical message',persona='shizuku',thread_id='thread')
            history=client.get('/api/workbench/session?persona=shizuku&thread_id=thread').json()['messages']
            self.assertEqual(46,len(history))
            self.assertEqual(46,len({m['id'] for m in history}))
            target=history[4]['id']
            body={'thread_id':'thread','persona':'shizuku','message_id':target}
            for _ in range(3):
                response=client.post('/api/workbench/session/revert',json=body)
                self.assertEqual(200,response.status_code,response.text)
                self.assertEqual(history[:4],response.json()['messages'])
                self.assertEqual(46 if _==0 else 6,len(service.harness.storage.load_checkpoint('thread','shizuku')['messages']))
                result=service.run('identical message',persona='shizuku',thread_id='thread')
                self.assertEqual(6,len(result['messages']))
                self.assertNotEqual(target,result['messages'][4]['id'])
                target=result['messages'][4]['id'];body['message_id']=target
                self.assertEqual(6,len(service.harness.storage.load_checkpoint('thread','shizuku')['messages']))
            with task_plans.execution('thread','shizuku'):
                self.assertEqual(409,client.post('/api/workbench/session/revert',json=body).status_code)
            body['message_id']='not-in-this-session'
            self.assertEqual(404,client.post('/api/workbench/session/revert',json=body).status_code)

    def test_legacy_message_ids_are_persisted_and_stable(self):
        storage=FakeStorage()
        storage.save_checkpoint('t','shizuku',{'messages':[{'role':'user','content':'old'}]})
        service=AgentService(storage=storage,model_gateway=lambda m,c: {'content':'ok'})
        first=service.harness.get_history('t','shizuku')
        self.assertEqual(first,service.harness.get_history('t','shizuku'))
        self.assertTrue(first[0]['id'])
