import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import settings_resources as resources
from app.config import settings
from app.mcp_manager import MCPManager
from app.storage.adapter import StorageAdapter


class SettingsResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        app = FastAPI()
        app.include_router(resources.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp.cleanup()

    def test_json_edit_validates_before_writing_and_preserves_markdown(self):
        folder = self.root / 'alice'
        folder.mkdir()
        (folder / 'persona.json').write_text('{}', encoding='utf-8')
        (folder / 'PERSONA.md').write_text('# Custom notes', encoding='utf-8')
        with patch.object(resources, 'PERSONAS_DIR', self.root), patch.object(resources, 'ensure_personas'):
            body = {'kind': 'persona', 'key': 'alice', 'filename': 'persona.json', 'content': '{bad'}
            self.assertEqual(400, self.client.put('/api/settings-resources/document', json=body).status_code)
            self.assertEqual('{}', (folder / 'persona.json').read_text())
            body['content'] = json.dumps({'character': {'name': 'Alice'}})
            self.assertEqual(200, self.client.put('/api/settings-resources/document', json=body).status_code)
            result = self.client.get('/api/settings-resources/document', params={'kind': 'persona', 'key': 'alice', 'filename': 'persona.json'})
            self.assertEqual('Alice', json.loads(result.json()['content'])['character']['name'])
            self.assertEqual('# Custom notes', (folder / 'PERSONA.md').read_text())
            body['filename'] = '../../escape.json'
            self.assertEqual(400, self.client.put('/api/settings-resources/document', json=body).status_code)

    def test_voice_zip_import_and_reject_path_escape(self):
        def archive(name):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as zipped:
                zipped.writestr(name, b'test voice configuration')
            return stream.getvalue()
        with patch.object(resources, 'DATA_DIR', self.root):
            result = self.client.post('/api/settings-resources/tts/import?filename=voice.zip', content=archive('voice/config.json'))
            self.assertEqual(200, result.status_code)
            asset = result.json()['id']
            self.assertTrue((self.root / 'tts/assets' / asset / 'voice/config.json').exists())
            self.assertEqual(1, self.client.get('/api/settings-resources/tts').json()['items'][0]['files'])
            result = self.client.post('/api/settings-resources/tts/import?filename=bad.zip', content=archive('../../escape.txt'))
            self.assertEqual(400, result.status_code)
            self.assertFalse((self.root / 'escape.txt').exists())

    def test_legacy_persona_markdown_can_be_edited_without_overwriting_source(self):
        folder = self.root / 'alice'
        folder.mkdir()
        (folder / 'persona.json').write_text('{}')
        (folder / 'SKILL.md').write_text('# Legacy persona', encoding='utf-8')
        with patch.object(resources, 'PERSONAS_DIR', self.root), patch.object(resources, 'ensure_personas'):
            params = {'kind': 'persona', 'key': 'alice', 'filename': 'PERSONA.md'}
            result = self.client.get('/api/settings-resources/document', params=params)
            self.assertEqual('# Legacy persona', result.json()['content'])
            self.assertEqual(200, self.client.put('/api/settings-resources/document', json={**params, 'content': '# Updated'}).status_code)
            self.assertEqual('# Updated', (folder / 'PERSONA.md').read_text())
            self.assertEqual('# Legacy persona', (folder / 'SKILL.md').read_text())

    def test_mcp_edit_and_delete_survive_reload(self):
        folder = self.root / 'mcp'
        folder.mkdir()
        (folder / 'demo.json').write_text(json.dumps({'id': 'demo', 'name': 'Demo', 'command': 'old'}))
        manager = MCPManager(folder)
        manager.update('demo', {'command': 'new'})
        manager.reload()
        self.assertEqual('new', manager.list_servers()[0]['command'])
        manager.delete('demo')
        manager.reload()
        self.assertNotIn('demo', [s['id'] for s in manager.list_servers()])

    def test_persona_filter_is_applied_before_pagination(self):
        with patch.object(settings, '_data', {'storage': {'sqlite': {'path': str(self.root / 'records.db')}}}):
            storage = StorageAdapter()
        try:
            for index in range(25):
                storage.add_chat_record('alice', 'user', f'alice {index}')
                storage.add_chat_record('bob', 'assistant', f'bob {index}')
            page = storage.list_records(limit=20, offset=20, persona='alice')
            self.assertEqual(5, len(page))
            self.assertTrue(all(row['persona'] == 'alice' for row in page))
            self.assertEqual([{'persona': 'alice', 'total': 25}, {'persona': 'bob', 'total': 25}], storage.record_groups())
        finally:
            storage._conn.close()
