import copy
import io
import json
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image
from character_import import apply, audit


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(Path(__file__).resolve().parents[2] / 'public', self.root / 'public')
        rows, _ = audit(self.root)
        self.entry = dict(id=max(r['id'] for r in rows)+1, slug='test-only', nameJa='試験', nameEn='TEST', concept='fixture', verified=True, provenance='canonical', status='MAYBE', emotionTheme=[])
        n = self.entry['id']
        self.entry['images'] = dict(main=f'/characters/{n:03d}/main.webp', normal=f'/characters/{n:03d}/a.webp', graphic=f'/characters/{n:03d}/b.webp')
        b = io.BytesIO()
        Image.new('RGB', (8, 8), 'red').save(b, format='WEBP')
        self.image = b.getvalue()

    def package(self, entry=None, extra=None, image=None):
        p = self.root / 'test.zip'
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('character.json', json.dumps(entry or self.entry))
            for name in ('main.webp', 'a.webp', 'b.webp'):
                z.writestr(name, self.image if image is None else image)
            if extra:
                z.writestr(extra, 'bad')
        return p

    def snapshot(self):
        return {str(p.relative_to(self.root / 'public')): p.read_bytes() for p in (self.root / 'public').rglob('*') if p.is_file()}

    def reject(self, package):
        before = self.snapshot()
        with self.assertRaises((ValueError, OSError)):
            apply(self.root, package)
        self.assertEqual(before, self.snapshot())

    def test_success_and_replay(self):
        before, numbering = audit(self.root)
        package = self.package()
        apply(self.root, package)
        after, new_numbering = audit(self.root)
        self.assertEqual(before, after[:-1])
        self.assertEqual(numbering['reservedUnassignedIds'], new_numbering['reservedUnassignedIds'])
        self.reject(package)

    def test_atomic_commit_and_concurrent_push_rejection(self):
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.STDOUT, text=True).strip()
        git('init', '-b', 'main')
        git('config', 'user.name', 'test')
        git('config', 'user.email', 'test@example.invalid')
        git('add', 'public')
        git('commit', '-m', 'baseline')
        remote = self.root / 'remote.git'
        subprocess.check_output(['git', 'init', '--bare', str(remote)], stderr=subprocess.STDOUT)
        git('remote', 'add', 'origin', str(remote))
        git('push', 'origin', 'main')
        baseline = git('rev-parse', 'HEAD')
        apply(self.root, self.package())
        git('add', 'public')
        git('commit', '-m', 'atomic import')
        changed = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines())
        n = self.entry['id']
        self.assertEqual(changed, {'public/characters.json', 'public/numbering-audit.json', *{f'public/characters/{n:03d}/{name}.webp' for name in ('main', 'a', 'b')}})
        git('push', 'origin', 'main')
        # A competing writer based on the old registry cannot overwrite the winner.
        git('checkout', '-b', 'competing', baseline)
        (self.root / 'other.txt').write_text('concurrent edit')
        git('add', 'other.txt')
        git('commit', '-m', 'competing writer')
        with self.assertRaises(subprocess.CalledProcessError):
            git('push', 'origin', 'HEAD:main')

    def test_reserved_and_out_of_sequence(self):
        for n in (19, 36, 38):
            entry = copy.deepcopy(self.entry)
            entry['id'] = n
            self.reject(self.package(entry))

    def test_traversal_and_unknown_files(self):
        for path in ('../outside', '/tmp/outside', 'unexpected.txt'):
            self.reject(self.package(extra=path))

    def test_invalid_image(self):
        self.reject(self.package(image=b'not an image'))

    def test_wrong_image_mapping(self):
        self.entry['images']['main'] = '/characters/036/main.webp'
        self.reject(self.package())

    def test_audit_rejects_numbering_drift(self):
        p = self.root / 'public/numbering-audit.json'
        data = json.loads(p.read_text())
        data['canonicalIds'].pop()
        p.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            audit(self.root)


if __name__ == '__main__':
    unittest.main()
