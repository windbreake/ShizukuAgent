import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.model_registry import model_registry

class ProviderSelectionTests(unittest.TestCase):
    def test_selection_keeps_credentials_and_disables_unselected(self):
        snapshot={'providers':{'p':{'name':'Provider','base_url':'https://example.com/v1','api_key':'secret'}},'models':{'old':{'provider':'p','model':'old','enabled':True}},'model_groups':{},'default_model_group':'default','auxiliary_apis':{}}
        with patch.object(model_registry,'snapshot',return_value=snapshot),patch.object(model_registry,'update',side_effect=lambda value:value) as update:
            response=TestClient(app).put('/api/providers/p/models',json={'models':['new','new']})
        self.assertEqual(200,response.status_code)
        data=response.json()
        self.assertEqual('provider:p',data['group_id'])
        saved=update.call_args.args[0]
        self.assertEqual(1,len(saved['model_groups']['provider:p']['models']))
        self.assertFalse(saved['models']['old']['enabled'])
        self.assertEqual('https://example.com/v1',data['providers']['p']['base_url'])

    def test_empty_selection_does_not_save(self):
        with patch.object(model_registry,'snapshot',return_value={'providers':{'p':{}}}),patch.object(model_registry,'update') as update:
            response=TestClient(app).put('/api/providers/p/models',json={'models':[]})
        self.assertEqual(400,response.status_code);update.assert_not_called()
