import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.agent.agent_service import AgentService
from app.storage.adapter import StorageAdapter
from app import persona_store, task_plans
from app.workbench import router
from test_agent_graph import FakeStorage


class SessionIntegrityTests(unittest.TestCase):
    def test_manual_compaction_persists_result_and_failure_in_history(self):
        storage=FakeStorage()
        service=AgentService(storage=storage,model_gateway=lambda m,c:{'content':'reply'})
        app=FastAPI();app.include_router(router)
        history=[{'role':role,'content':f'{role} {i}'} for i in range(5) for role in ('user','assistant')]
        storage.save_checkpoint('compact','shizuku',{'messages':history})
        with patch('app.agent.agent_service.get_agent_service',return_value=service),patch.object(service.harness.dependencies.model_registry,'resolve_agent_group',return_value=[{'id':'test'}]),patch('app.agent.llm.OpenAICompatibleClient.chat',return_value={'content':'目标：继续任务；下一步：验证。'}):
            client=TestClient(app)
            response=client.post('/api/workbench/context/compact',json={'thread_id':'compact','persona':'shizuku'})
            self.assertEqual(200,response.status_code,response.text)
            operation=service.harness.get_history('compact','shizuku')[-1]
            self.assertEqual('compaction',operation['kind'])
            self.assertEqual('completed',operation['status'])
            self.assertIn('目标：继续任务',operation['content'])
            self.assertEqual(11,len(service.harness.get_history('compact','shizuku')))
            with patch('app.agent.llm.OpenAICompatibleClient.chat',side_effect=RuntimeError('provider unavailable')):
                storage.save_checkpoint('failure','shizuku',{'messages':history[:10]})
                response=client.post('/api/workbench/context/compact',json={'thread_id':'failure','persona':'shizuku'})
                self.assertEqual(400,response.status_code)
                operation=service.harness.get_history('failure','shizuku')[-1]
                self.assertEqual('failed',operation['status'])
                self.assertIn('provider unavailable',operation['content'])

    def test_fork_copies_only_visible_history_and_has_independent_ownership(self):
        from app import session_history
        storage=FakeStorage()
        storage.save_checkpoint('source','shizuku',{'messages':[
            {'id':'u1','role':'user','content':'keep','record_id':1},
            {'id':'a1','role':'assistant','content':'reply','record_id':2,'execution_context':[{'role':'tool','content':'detail'}]},
            {'id':'u2','role':'user','content':'hidden'}],
            'revert':{'message_id':'u2'},'context':{'summary':'stale'}})
        target=session_history.fork(storage,'source','shizuku')
        branch=storage.load_checkpoint(target,'shizuku')
        self.assertEqual(['keep','reply'],[m['content'] for m in branch['messages']])
        self.assertNotIn('context',branch)
        self.assertNotIn('revert',branch)
        self.assertTrue(all('record_id' not in m for m in branch['messages']))
        self.assertNotEqual('u1',branch['messages'][0]['id'])
        branch['messages'][1]['execution_context'][0]['content']='changed'
        original=storage.load_checkpoint('source','shizuku')
        self.assertEqual('detail',original['messages'][1]['execution_context'][0]['content'])
        service=AgentService(storage=storage,model_gateway=lambda m,c:{'content':'reply'})
        app=FastAPI();app.include_router(router)
        with patch('app.agent.agent_service.get_agent_service',return_value=service):
            client=TestClient(app)
            with task_plans.execution('source','shizuku'):
                self.assertEqual(409,client.post('/api/workbench/session/fork',json={'thread_id':'source','persona':'shizuku'}).status_code)
            response=client.post('/api/workbench/session/fork',json={'thread_id':'source','persona':'shizuku'})
            self.assertEqual(200,response.status_code,response.text)
            self.assertNotEqual('source',response.json()['thread_id'])
            self.assertEqual(['keep','reply'],[m['content'] for m in response.json()['messages']])

    def test_full_history_tools_and_persona_survive_next_turn(self):
        captured=[]
        def gateway(messages,config):
            captured.append(messages)
            if any(m.get('role')=='user' and m['content']=='inspect' for m in messages) and not any(m.get('role')=='tool' for m in messages):
                return {'content':'','tool_calls':[{'id':'read1','type':'function','function':{'name':'read_file','arguments':'{"path":"note.txt"}'}}]}
            return {'content':'finished'}
        storage=FakeStorage()
        service=AgentService(storage=storage,model_gateway=gateway)
        storage.save_checkpoint('thread','shizuku',{'messages':[{'role':'user','content':'original requirement'}]+[{'role':'assistant','content':str(i)} for i in range(20)]})
        with patch('app.agent.tools.run_tool',return_value='file contains secret task detail'):
            service.run('inspect',persona='shizuku',thread_id='thread')
            service.run('continue',persona='shizuku',thread_id='thread')
        last=captured[-1]
        reminder=next(m['content'] for m in last if '[当前回复的人格约束]' in m.get('content',''))
        self.assertIn('小雫',reminder)
        for request in captured:
            reminders=[m for m in request if '[当前回复的人格约束]' in m.get('content','')]
            self.assertEqual(1,len(reminders))
            self.assertIn('技术分析',reminders[0]['content'])
        self.assertTrue(any(m.get('content')=='original requirement' for m in last))
        self.assertTrue(any(m.get('role')=='tool' and 'secret task detail' in m['content'] for m in last),last)
        self.assertIsNone(storage.load_checkpoint('persona:shizuku','shizuku'))
        self.assertEqual([],storage.memories)

    def test_timeout_does_not_become_assistant_history(self):
        service=AgentService(storage=FakeStorage(),model_gateway=lambda m,c: (_ for _ in ()).throw(TimeoutError('request timed out')))
        with self.assertRaisesRegex(RuntimeError,'会话已保留'):
            service.run('hello',persona='shizuku',thread_id='failed')
        history=service.harness.get_history('failed','shizuku')
        self.assertEqual(['user'],[m['role'] for m in history])

    def test_persona_markdown_is_loaded_and_string_templates_supported(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(persona_store,'PERSONAS_DIR',Path(tmp)):
            folder=Path(tmp)/'custom';folder.mkdir()
            (folder/'persona.json').write_text('{"character":{"name":"Alice"},"system_prompt":"You are {name}"}',encoding='utf-8')
            (folder/'PERSONA.md').write_text('Always speak like a sailor.',encoding='utf-8')
            prompt=persona_store.build_system_prompt(persona_store.load_persona('custom.json'))
            self.assertIn('You are Alice',prompt)
            self.assertIn('sailor',prompt)

    def test_delete_clears_database_and_plan_without_other_sessions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(StorageAdapter,'_resolve_sqlite_path',return_value=Path(tmp)/'test.db'), patch.object(task_plans,'DATA_DIR',Path(tmp)):
            storage=StorageAdapter(driver='sqlite')
            service=AgentService(storage=storage,model_gateway=lambda m,c:{'content':'reply'})
            service.run('same',persona='shizuku',thread_id='a')
            service.run('same',persona='shizuku',thread_id='b')
            storage.add_memory('shizuku','session memory',metadata={'thread_id':'a'})
            storage.add_memory('shizuku','shared memory')
            app=FastAPI();app.include_router(router)
            with patch('app.agent.agent_service.get_agent_service',return_value=service):
                client=TestClient(app)
                with task_plans.execution('a','shizuku'):
                    self.assertEqual(409,client.request('DELETE','/api/workbench/session',json={'thread_id':'a','persona':'shizuku'}).status_code)
                response=client.request('DELETE','/api/workbench/session',json={'thread_id':'a','persona':'shizuku'})
                self.assertEqual(200,response.status_code,response.text)
                self.assertEqual(2,response.json()['records'])
                self.assertIsNone(storage.load_checkpoint('a','shizuku'))
                self.assertEqual(2,len(storage.list_records()))
                self.assertEqual(2,len(service.harness.get_history('b','shizuku')))
                self.assertEqual(['shared memory'],[m['content'] for m in storage.list_memories()])
                self.assertFalse(task_plans.path_for('a','shizuku').exists())
            storage._conn.close()
