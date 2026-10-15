import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app import gateway, task_plans
from app.config import settings
from app.agent.agent_graph import AgentGraph
from test_agent_graph import FakeStorage


class GatewayPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.override = patch.object(task_plans, 'DATA_DIR', Path(self.temp.name))
        self.override.start()

    def tearDown(self):
        self.override.stop()
        self.temp.cleanup()

    def test_agent_tool_updates_plan_and_persists_unfinished_status(self):
        calls = 0
        def model(messages, config):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'plan1', 'type': 'function', 'function': {'name': 'todowrite', 'arguments': '{"todos":[{"content":"Inspect files","status":"in_progress","priority":"high"}]}'}}]}
            return {'role': 'assistant', 'content': 'stopped before verification'}
        graph = AgentGraph(storage=FakeStorage(), model_gateway=model)
        graph.invoke('multi-step task', persona='shizuku', thread_id='test-plan')
        plan = task_plans.read('test-plan', 'shizuku')
        self.assertFalse(plan['running'])
        self.assertEqual('in_progress', plan['items'][0]['status'])
        self.assertEqual([], task_plans.read('test-plan', 'alice')['items'])

    def test_only_one_current_task_and_run_cleanup_after_error(self):
        with self.assertRaises(RuntimeError):
            with task_plans.execution('t', 'p'):
                with self.assertRaises(ValueError):
                    task_plans.write_todos([{'content': 'a', 'status': 'in_progress'}, {'content': 'b', 'status': 'in_progress'}])
                raise RuntimeError('failed')
        self.assertFalse(task_plans.read('t', 'p')['running'])
        with task_plans.execution('t', 'p'):
            task_plans.write_todos([{'content': 'done', 'status': 'completed'}])
        self.assertEqual('completed', task_plans.read('t', 'p')['items'][0]['status'])

    def test_websocket_roundtrip_disabled_gate_and_port_validation(self):
        app = FastAPI()
        app.include_router(gateway.router)
        client = TestClient(app)
        with patch.object(settings, '_data', {'unified_api': {'websocket_enabled': False}}):
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect('/ws/chat'):
                    pass
        with patch.object(settings, '_data', {'unified_api': {'websocket_enabled': True}}), patch('app.agent.agent_service.get_agent_service') as factory:
            factory.return_value.default_persona.return_value = 'shizuku'
            factory.return_value.run.return_value = {'success': True, 'reply': 'hello'}
            with client.websocket_connect('/ws/chat') as socket:
                socket.send_json({'message': 'hello', 'thread_id': 'socket-test'})
                self.assertEqual('started', socket.receive_json()['type'])
                response = socket.receive_json()
                if response['type'] == 'plan':
                    response = socket.receive_json()
                self.assertEqual('result', response['type'])
                self.assertEqual('hello', response['data']['reply'])
            self.assertEqual(422, client.put('/api/gateway', json={'port': 99999}).status_code)
            with patch.object(settings, 'update') as update:
                response = client.put('/api/gateway', json={'port': 9001, 'websocket_enabled': True})
                self.assertEqual(200, response.status_code)
                self.assertEqual(9001, update.call_args.args[0]['unified_api']['port'])
