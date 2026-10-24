import base64
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from generate_gemini import Gemini, FIELDS, generate, parts
from gemini_run_state import gate
from character_import import apply, audit


class FakeGemini:
    def __init__(self, accepted=True):
        self.calls = 0
        self.accepted = accepted

    def structured(self, model, inputs, schema):
        self.calls += 1
        if 'accepted' in schema['properties']:
            return {'accepted': self.accepted, 'issues': [] if self.accepted else ['identity mismatch']}
        return {**{k: 'fixture' for k in FIELDS}, 'slug': 'generation-test-only', 'emotionTheme': ['quiet kindness'], 'comicIdeas': ['one', 'two', 'three'], 'id': 1, 'source': 'canonical', 'images': {'main': '/characters/001/main.webp'}}

    def image(self, model, inputs, aspect):
        self.calls += 1
        out = io.BytesIO()
        Image.new('RGB', (16, 16), 'green').save(out, 'PNG')
        return out.getvalue()


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        repo = Path(__file__).resolve().parents[2]
        for directory in ('public', 'config', 'prompts'):
            shutil.copytree(repo / directory, self.root / directory)
        self.out = self.root / 'output/run'

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in (self.root / 'public').rglob('*') if p.is_file()}

    def test_generate_package_then_import_without_cross_series_changes(self):
        client = FakeGemini()
        before = self.snapshot()
        rows, _ = audit(self.root, 'gemini')
        expected = max(r['id'] for r in rows) + 1
        package = generate(self.root, self.out, client, '2026-10-24')
        self.assertEqual(client.calls, 5)
        self.assertEqual(before, self.snapshot())
        apply(self.root, package, 'gemini')
        after, _ = audit(self.root, 'gemini')
        self.assertEqual(after[-1]['id'], expected)
        self.assertEqual(after[-1]['source'], 'gemini')
        self.assertEqual(after[-1]['generationDateTokyo'], '2026-10-24')
        self.assertEqual(after[-1]['images']['main'], f'/gemini/characters/{expected:03d}/main.webp')
        for path, data in before.items():
            if not path.startswith('public/gemini/'):
                self.assertEqual(data, (self.root / path).read_bytes())

    def test_review_failure_preserves_artifacts_without_publication(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'visual review failed'):
            generate(self.root, self.out, FakeGemini(False), '2026-10-24')
        self.assertEqual(before, self.snapshot())
        self.assertTrue((self.out / 'a.webp').exists())
        self.assertFalse(list(self.out.glob('*.zip')))

    def test_same_day_is_idempotent_without_calls(self):
        client = FakeGemini()
        package = generate(self.root, self.out, client, '2026-10-24')
        apply(self.root, package, 'gemini')
        fresh = FakeGemini()
        self.assertIsNone(generate(self.root, self.root / 'next-run', fresh, '2026-10-24'))
        self.assertEqual(fresh.calls, 0)

    def test_missing_key_and_refused_response(self):
        with self.assertRaisesRegex(ValueError, 'GEMINI_API_KEY'):
            Gemini('')
        with self.assertRaises(ValueError):
            parts({'status': 'incomplete', 'steps': []})

    def test_rest_contract_secret_is_header_only_and_outputs_parsed(self):
        response = {'status': 'completed', 'steps': [{'type': 'model_output', 'content': [{'type': 'text', 'text': '{"ok":true}'}]}]}
        context = unittest.mock.MagicMock()
        context.__enter__.return_value.read.return_value = json.dumps(response).encode()
        with patch('generate_gemini.urllib.request.urlopen', return_value=context) as request:
            result = Gemini('SECRET-FIXTURE').structured('test-model', [{'type': 'text', 'text': 'test'}], {'type': 'object'})
        self.assertEqual(result, {'ok': True})
        req = request.call_args.args[0]
        self.assertEqual(req.headers['X-goog-api-key'], 'SECRET-FIXTURE')
        self.assertNotIn('SECRET-FIXTURE', req.full_url)
        self.assertNotIn(b'SECRET-FIXTURE', req.data)
        self.assertEqual(json.loads(req.data)['store'], False)

    def test_http_error_does_not_echo_secret_and_no_automatic_retry(self):
        with patch('generate_gemini.urllib.request.urlopen', side_effect=urllib.error.HTTPError('url', 403, 'SECRET-FIXTURE', {}, None)) as request:
            with self.assertRaises(RuntimeError) as error:
                Gemini('SECRET-FIXTURE').call('test', [], {})
        self.assertNotIn('SECRET-FIXTURE', str(error.exception))
        self.assertEqual(request.call_count, 1)

    def test_image_response_and_call_limit(self):
        payload = {'status': 'completed', 'steps': [{'type': 'model_output', 'content': [{'type': 'image', 'mime_type': 'image/png', 'data': base64.b64encode(b'fixture').decode()}]}]}
        client = Gemini('fixture')
        with patch.object(client, 'call', return_value=payload):
            self.assertEqual(client.image('test', [], '4:5'), b'fixture')
        client.calls = 5
        with self.assertRaisesRegex(ValueError, 'Five-call'):
            client.call('test', [], {})

    def test_schedule_requires_proven_activation_and_push_cannot_spend(self):
        self.assertFalse(gate({'dailyEnabled': False}, 'schedule', '')['generate'])
        self.assertFalse(gate({'dailyEnabled': True}, 'schedule', '')['generate'])
        self.assertTrue(gate({'dailyEnabled': True, 'lastVerifiedCommit': 'abc'}, 'schedule', '')['generate'])
        self.assertFalse(gate({}, 'push', 'publish-and-enable')['generate'])
        self.assertEqual(gate({}, 'workflow_dispatch', 'publish-and-enable'), dict(generate=True, publish=True, activate=True))
