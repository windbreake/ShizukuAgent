import unittest
from app.model_identity import model_display_name
from app.model_discovery import parse_models

class ModelIdentityTests(unittest.TestCase):
    def test_placeholder_is_not_model_name(self):
        self.assertEqual('deepseek-flash',model_display_name({'model':'deepseek-flash','name':'Primary Agent Model'}))
        self.assertEqual('My custom name',model_display_name({'model':'deepseek-flash','name':'My custom name'}))

    def test_provider_metadata_is_preserved(self):
        model=parse_models({'data':[{'id':'vendor/model','display_name':'Vendor Model','owned_by':'vendor','context_length':200000,'modalities':{'input':['text','image']}}]})[0]
        self.assertEqual('vendor/model',model['id']);self.assertEqual('Vendor Model',model['name'])
        self.assertEqual(200000,model['context_length']);self.assertEqual(['text','image'],model['modalities']['input'])
        plain=parse_models({'data':[{'id':'text-model'}]})[0]
        self.assertNotIn('capabilities',plain)
