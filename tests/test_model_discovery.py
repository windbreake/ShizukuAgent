import unittest
from unittest.mock import patch
from app.model_discovery import model_urls,parse_models,fetch_models
from app.provider_routes import import_all_models

class DiscoveryTests(unittest.TestCase):
    def test_candidate_paths(self):
        self.assertEqual(['https://example.com/models','https://example.com/v1/models'],model_urls('https://example.com'))
        self.assertEqual(['https://example.com/v1/models'],model_urls('https://example.com/v1/chat/completions'))
        self.assertEqual(['https://example.com/custom/list'],model_urls('https://example.com/v1','https://example.com/custom/list'))

    def test_sorted_deduplicated(self):
        self.assertEqual(['a','b'],[m['id'] for m in parse_models({'data':[{'id':'b'},{'id':'a'},{'id':'a'}]})])
        self.assertEqual(['vendor/model'],[m['id'] for m in parse_models({'models':['vendor/model']})])

    def test_import_creates_single_provider_group(self):
        from app.model_registry import model_registry
        snapshot={'providers':{'p':{'name':'Provider','base_url':'https://example.com/v1','api_key':'secret'}},'models':{},'model_groups':{},'default_model_group':'default','auxiliary_apis':{}}
        with patch.object(model_registry,'snapshot',return_value=snapshot),patch.object(model_registry,'update') as update,patch('app.provider_routes.fetch_models',return_value={'models':[{'id':'a'},{'id':'b'}]}):
            import_all_models('p')
        data=update.call_args.args[0]
        self.assertEqual(['provider:p'],list(data['model_groups']))
        self.assertEqual(2,len(data['model_groups']['provider:p']['models']))
        self.assertTrue(all(m['provider']=='p' for m in data['models'].values()))

    def test_failed_fetch_never_saves(self):
        from app.model_registry import model_registry
        with patch.object(model_registry,'snapshot',return_value={'providers':{'p':{'base_url':'https://example.com'}}}),patch.object(model_registry,'update') as update,patch('app.provider_routes.fetch_models',side_effect=ValueError('HTTP 403')):
            response=import_all_models('p')
        self.assertEqual(400,response.status_code)
        update.assert_not_called()
