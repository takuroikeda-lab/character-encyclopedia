import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from character_import import apply, audit


class GeminiImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(Path(__file__).resolve().parents[2] / 'public', self.root / 'public')
        rows, _ = audit(self.root, 'gemini')
        self.ident = max(r['id'] for r in rows) + 1
        n = self.ident
        self.entry = dict(id=n, slug='gemini-test-only', nameJa='試験', nameEn='TEST', concept='fixture', verified=True, source='gemini', status='MAYBE', emotionTheme=[], images=dict(main=f'/gemini/characters/{n:03d}/main.webp', normal=f'/gemini/characters/{n:03d}/a.webp', graphic=f'/gemini/characters/{n:03d}/b.webp'))

    def package(self):
        p = self.root / 'test.zip'
        b = io.BytesIO()
        Image.new('RGB', (8, 8), 'green').save(b, format='WEBP')
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('character.json', json.dumps(self.entry))
            for name in ('main.webp', 'a.webp', 'b.webp'):
                z.writestr(name, b.getvalue())
        return p

    def test_separate_atomic_append_and_replay(self):
        canonical = (self.root / 'public/characters.json').read_bytes()
        audit_bytes = (self.root / 'public/numbering-audit.json').read_bytes()
        before, old_audit = audit(self.root, 'gemini')
        package = self.package()
        apply(self.root, package, 'gemini')
        after, new_audit = audit(self.root, 'gemini')
        self.assertEqual(before, after[:-1])
        self.assertEqual(old_audit['canonicalIds'] + [self.ident], new_audit['canonicalIds'])
        self.assertEqual(canonical, (self.root / 'public/characters.json').read_bytes())
        self.assertEqual(audit_bytes, (self.root / 'public/numbering-audit.json').read_bytes())
        with self.assertRaises(ValueError):
            apply(self.root, package, 'gemini')

    def test_no_restart_at_one_or_overwrite(self):
        for n in (1, self.ident - 1):
            self.entry['id'] = n
            with self.assertRaises(ValueError):
                apply(self.root, self.package(), 'gemini')

    def test_cross_series_path_and_source_rejected(self):
        original = dict(self.entry['images'])
        self.entry['images']['main'] = f'/characters/{self.ident:03d}/main.webp'
        with self.assertRaises(ValueError):
            apply(self.root, self.package(), 'gemini')
        self.entry['images'] = original
        self.entry['source'] = 'canonical'
        with self.assertRaises(ValueError):
            apply(self.root, self.package(), 'gemini')
