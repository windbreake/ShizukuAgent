import unittest
from unittest.mock import patch

from app.agent.llm import OpenAICompatibleClient
from app.agent.nodes.model_node import ModelNode


class AgentLatencyTests(unittest.TestCase):
    def test_zero_budget_allows_more_than_one_hundred_rounds(self):
        from app.agent.nodes.router_node import RouterNode
        candidate={'id':'working','max_tool_rounds':0}
        state={'tool_rounds':10001,'messages':[],'model_candidates':[candidate],'active_model':'working','model_config':candidate}
        captured=[]
        def gateway(messages, model):
            captured.append(model)
            return {'role':'assistant','content':'','tool_calls':[{'id':'next','function':{'name':'search_memory','arguments':'{}'}}]}
        result=ModelNode(gateway=gateway)(state)
        self.assertTrue(captured[0]['tools'])
        self.assertEqual('tools',RouterNode().route({**state,**result}))

    def test_more_than_six_rounds_allowed_and_budget_generates_summary(self):
        requests=[]
        def gateway(messages, model):
            requests.append((messages,model))
            return {'role':'assistant','content':'已检查项目结构，尚未检查部署。'}
        candidate={'id':'working','max_tool_rounds':100}
        state={'tool_rounds':7,'messages':[],'model_candidates':[candidate],
               'active_model':'working','model_config':candidate}
        node=ModelNode(gateway=gateway)
        self.assertEqual('respond',node(state)['intent'])
        self.assertNotEqual([],requests[-1][1]['tools'])
        state['tool_rounds']=100
        result=node(state)
        self.assertEqual([],requests[-1][1]['tools'])
        self.assertIn('预算',requests[-1][0][-1]['content'])
        self.assertIn('已检查',result['reply'])

    def test_tool_round_starts_with_last_successful_model(self):
        calls = []

        def gateway(messages, model):
            calls.append(model['id'])
            if model['id'] == 'broken':
                raise ConnectionError('unavailable')
            return {'role': 'assistant', 'content': 'done'}

        candidates = [{'id': 'broken'}, {'id': 'working'}]
        state = {'tool_rounds': 0, 'messages': [], 'model_candidates': candidates,
                 'active_model': 'broken', 'model_config': candidates[0]}
        node = ModelNode(gateway=gateway)
        first = node(state)
        state.update(first)
        state['tool_rounds'] = 1
        node(state)
        self.assertEqual(['broken', 'working', 'working'], calls)

    def test_model_requests_have_bounded_timeouts_and_no_hidden_retries(self):
        with patch('openai.OpenAI') as factory:
            client = factory.return_value.__enter__.return_value
            # Support both direct and context-managed SDK use.
            factory.return_value.chat.completions.create.return_value.choices = [
                type('Choice', (), {'message': {'content': 'ok'}})()]
            client.chat.completions.create.return_value.choices = [
                type('Choice', (), {'message': {'content': 'ok'}})()]
            OpenAICompatibleClient().chat([], {'provider_config': {'api_key': 'test'}})
            self.assertEqual(0, factory.call_args.kwargs['max_retries'])
            self.assertEqual(180, factory.call_args.kwargs['timeout'].read)
            self.assertEqual(15, factory.call_args.kwargs['timeout'].connect)


if __name__ == '__main__':
    unittest.main()
