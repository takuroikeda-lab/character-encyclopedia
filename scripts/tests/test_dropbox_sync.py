import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dropbox_sync import Worker, Stop, plan, digest, save, FOLDERS, GitHub

REPO = Path(__file__).resolve().parents[2]

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for f in FOLDERS:
            (self.root / f).mkdir()
        self.snapshot = self.root / 'snapshot'
        shutil.copytree(REPO / 'public', self.snapshot / 'public')
        self.entry = json.loads((self.snapshot / 'public/characters.json').read_text())[-1]
        self.entry.update(id=55, slug='test-candidate', nameJa='試験用', nameEn='TEST')
        self.entry['images'] = dict(main='/characters/055/main.webp', normal='/characters/055/a.webp', graphic='/characters/055/b.webp')
        self.review = dict.fromkeys(('armsConsistent', 'encyclopediaSheet', 'schemaConsistent', 'printedNumberAndName'), True)

    def package(self, extra=False):
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z:
            z.writestr('character.json', json.dumps(self.entry))
            for n in ('main', 'a', 'b'):
                z.writestr(n + '.webp', (REPO / f'public/characters/054/{n}.webp').read_bytes())
            if extra:
                z.writestr('../escape', 'bad')
        return b.getvalue()

    def queued(self):
        data = self.package()
        sha = digest(data)
        (self.root / '05_BACKUP' / (sha + '.zip')).write_bytes(data)
        path = self.root / '02_PENDING' / (sha + '.json')
        save(path, dict(sha256=sha, receipt={'review': self.review}, phase='queued', attempts=0))
        return path

    def test_plan_append_only(self):
        before = (self.snapshot / 'public/characters.json').read_bytes()
        changes = plan(self.snapshot, self.package(), {'review': self.review})
        self.assertEqual(len(changes), 5)
        self.assertEqual((self.snapshot / 'public/characters.json').read_bytes(), before)
        after = json.loads(changes['public/characters.json'])
        self.assertEqual(after[:-1], json.loads(before))
        self.assertEqual(json.loads(changes['public/numbering-audit.json'])['reservedUnassignedIds'], list(range(19,29)))

    def test_quality_and_crash_hold(self):
        with self.assertRaisesRegex(Stop, 'QUALITY_HOLD'):
            plan(self.snapshot, self.package(), {})
        self.entry['slug'] = 'crash-clamp'
        with self.assertRaisesRegex(Stop, 'Crash Clamp'):
            plan(self.snapshot, self.package(), {'review': self.review})

    def test_stale_number_reserved_and_duplicates(self):
        for ident in (19, 54, 56):
            self.entry['id'] = ident
            with self.assertRaisesRegex(Stop, 'NUMBER_HOLD'):
                plan(self.snapshot, self.package(), {'review': self.review})
        self.entry['slug'] = 'valve-viper'
        with self.assertRaisesRegex(Stop, 'DUPLICATE'):
            plan(self.snapshot, self.package(), {'review': self.review})

    def test_schema_and_traversal(self):
        with self.assertRaises(Stop):
            plan(self.snapshot, self.package(True), {'review': self.review})
        self.entry['note'] = 'extra'
        with self.assertRaisesRegex(Stop, 'schema'):
            plan(self.snapshot, self.package(), {'review': self.review})

    def test_ingest_completion_and_replay(self):
        w = Worker(self.root, None)
        source = self.root / '01_INBOX/test.zip'
        data = self.package()
        source.write_bytes(data)
        w.ingest()
        self.assertFalse(list((self.root / '02_PENDING').glob('*.json')))
        save(source.with_suffix('.ready.json'), dict(sha256=digest(data), size=len(data), review=self.review))
        w.ingest(); w.ingest()
        self.assertEqual(len(list((self.root / '02_PENDING').glob('*.json'))), 1)
        self.assertEqual((self.root / '05_BACKUP' / (digest(data)+'.zip')).read_bytes(), data)
        self.assertEqual(source.read_bytes(), data)

    def test_conflict_no_ref_mutation(self):
        github = GitHub()
        with patch.object(github, 'head', return_value='other'), patch.object(github, 'api') as api:
            with self.assertRaisesRegex(Stop, 'CONFLICT'):
                github.publish('expected', 'new')
            api.assert_not_called()

    def test_network_retry_persisted(self):
        path = self.queued()
        class Offline:
            def head(self):
                raise OSError('offline')
        Worker(self.root, Offline(), True).process(path)
        state = json.loads(path.read_text())
        self.assertEqual(state['attempts'], 1)
        self.assertGreater(state['nextRetry'], 0)
        self.assertNotIn('commit', state)

    def test_uncertain_commit_never_recreated(self):
        path = self.queued()
        state = json.loads(path.read_text()); state['commit'] = 'intended'
        save(path, state)
        class OtherHead:
            def head(self): return 'other'
            def commit(self, *a): raise AssertionError('second commit forbidden')
        Worker(self.root, OtherHead(), True).process(path)
        self.assertIn('RECOVERY_HOLD', json.loads(path.read_text())['reason'])

    def test_dry_run_no_remote_write(self):
        path = self.queued()
        snapshot = self.snapshot
        class ReadOnly:
            def head(self): return 'head'
            def snapshot(self, sha, root):
                shutil.copytree(snapshot / 'public', root / 'public')
                return 'tree'
            def commit(self, *a): raise AssertionError('dry run wrote')
        Worker(self.root, ReadOnly()).process(path)
        self.assertEqual(json.loads(path.read_text())['phase'], 'queued')
        self.assertIn('DRY_RUN_PASS', (self.root / '06_LOGS/sync.jsonl').read_text())

    def test_host_pin(self):
        save(self.root / '06_LOGS/worker-host.json', {'hostname': 'another-host'})
        with self.assertRaisesRegex(Stop, 'host mismatch'):
            Worker(self.root, None).run()

    def test_publication_retry_then_success_without_second_commit(self):
        path = self.queued()
        snapshot = self.snapshot
        changes = plan(snapshot, self.package(), {'review': self.review})
        class Fake:
            commits = 0
            current = 'parent'
            def head(self): return self.current
            def snapshot(self, sha, root):
                shutil.copytree(snapshot / 'public', root / 'public')
                if sha == 'commit':
                    for p, b in changes.items():
                        dest = root / p
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(b)
                return 'tree'
            def commit(self, *a):
                self.commits += 1
                return 'commit'
            def publish(self, parent, commit): self.current = commit
        github = Fake()
        worker = Worker(self.root, github, True)
        with patch('dropbox_sync.verify', side_effect=OSError('stale')):
            worker.process(path)
        state = json.loads(path.read_text())
        self.assertEqual(state['phase'], 'github_committed')
        state['nextRetry'] = 0
        save(path, state)
        with patch('dropbox_sync.verify') as verification:
            worker.process(path)
            self.assertEqual(verification.call_count, 2)
        self.assertEqual(github.commits, 1)
        self.assertFalse(path.exists())
        self.assertEqual(json.loads((self.root / '03_REGISTERED' / path.name).read_text())['phase'], 'published_verified')
