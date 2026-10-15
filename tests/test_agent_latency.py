import unittest
from unittest.mock import patch

from app.agent.llm import OpenAICompatibleClient
from app.agent.nodes.model_node import ModelNode


class AgentLatencyTests(unittest.TestCase):
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
            self.assertLessEqual(factory.call_args.kwargs['timeout'], 60)


if __name__ == '__main__':
    unittest.main()
