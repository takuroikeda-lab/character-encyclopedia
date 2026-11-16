"""Single-host append-only Dropbox worker. No generation or image rewriting."""
import argparse
import base64
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import tempfile
import time
import urllib.request
import urllib.error
import zipfile
from PIL import Image
from character_import import audit, next_id, webp
from verify_publication import verify

REPO = 'takuroikeda-lab/character-encyclopedia'
SITE = 'https://character-encyclopedia.link-link.workers.dev'
FOLDERS = ['01_INBOX', '02_PENDING', '03_REGISTERED', '04_FAILED', '05_BACKUP', '06_LOGS']
REQUIRED = {'character.json', 'main.webp', 'a.webp', 'b.webp'}

def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class Stop(ValueError):
    pass


class GitHub:
    def __init__(self, token=None):
        self.token = token

    def api(self, path, data=None, method=None):
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'encyclopedia-dropbox-sync/1'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request('https://api.github.com/repos/' + REPO + '/' + path,
            data=None if data is None else json.dumps(data).encode(), headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=30) as r:
            return json.load(r)

    def head(self):
        return self.api('git/ref/heads/main')['object']['sha']

    def snapshot(self, sha, dest):
        commit = self.api('git/commits/' + sha)
        tree = self.api('git/trees/' + commit['tree']['sha'] + '?recursive=1')
        if tree.get('truncated'):
            raise Stop('truncated tree')
        for item in tree['tree']:
            path = item['path']
            if item['type'] != 'blob' or not path.startswith('public/'):
                continue
            if '..' in Path(path).parts or Path(path).is_absolute():
                raise Stop('unsafe repository path')
            blob = self.api('git/blobs/' + item['sha'])
            data = base64.b64decode(blob['content'])
            if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() != item['sha']:
                raise Stop('Git blob mismatch')
            target = dest / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return commit['tree']['sha']

    def commit(self, parent, tree, changes):
        elements = []
        for path, data in changes.items():
            blob = self.api('git/blobs', {'content': base64.b64encode(data).decode(), 'encoding': 'base64'})
            elements.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
        newtree = self.api('git/trees', {'base_tree': tree, 'tree': elements})
        return self.api('git/commits', {'message': 'Register validated Dropbox character',
            'tree': newtree['sha'], 'parents': [parent]})['sha']

    def publish(self, parent, commit):
        if self.head() != parent:
            raise Stop('CONFLICT: main changed; no ref update')
        # A competing sibling cannot be fast-forwarded. Never force, never rebase.
        try:
            self.api('git/refs/heads/main', {'sha': commit, 'force': False}, 'PATCH')
        except urllib.error.HTTPError as e:
            if e.code in (409, 422):
                raise Stop('CONFLICT: ref update rejected; no automatic renumber/rebase') from e
            raise


def package_data(data):
    if len(data) > 32_000_000:
        raise Stop('ZIP too large')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if set(z.namelist()) != REQUIRED or len(z.infolist()) != 4 or sum(x.file_size for x in z.infolist()) > 31_000_000:
            raise Stop('four root files required; no duplicates, folders or extras')
        raw = {p: z.read(p) for p in REQUIRED}
    return raw, json.loads(raw['character.json'])


def plan(root, data, receipt):
    raw, entry = package_data(data)
    rows, numbering = audit(root)
    if numbering['reservedUnassignedIds'] != list(range(19, 29)):
        raise Stop('reserved audit changed')
    for row in rows:
        if any(entry.get(k) == row.get(k) for k in ('slug', 'nameJa', 'nameEn')):
            raise Stop('DUPLICATE: existing identity; never register again')
    review = receipt.get('review', {})
    # Review is tied to original ZIP digest. Semantic arm/sheet consistency cannot be inferred from decoding.
    checks = ('armsConsistent', 'encyclopediaSheet', 'schemaConsistent', 'printedNumberAndName')
    if any(review.get(k) is not True for k in checks):
        raise Stop('QUALITY_HOLD: original-image review incomplete')
    if entry.get('slug') == 'crash-clamp' or entry.get('nameJa') == 'クラッシュ・クランプ':
        if review.get('crashClampResolved') is not True:
            raise Stop('QUALITY_HOLD: Crash Clamp unresolved')
    ident = next_id(rows, numbering)
    if entry.get('id') != ident:
        raise Stop(f'NUMBER_HOLD: latest HEAD requires {ident}; no silent JSON/image renumbering')
    if set(entry) != set(rows[-1]):
        raise Stop('21-field schema must match latest canonical entry')
    if not re.fullmatch(r'[a-z][a-z0-9-]*', entry.get('slug', '')):
        raise Stop('invalid slug')
    for key, value in rows[-1].items():
        if type(entry[key]) is not type(value):
            raise Stop('wrong field type: ' + key)
        if isinstance(value, str) and not entry[key].strip():
            raise Stop('empty field: ' + key)
        if isinstance(value, list) and (not entry[key] or not all(isinstance(x, str) and x.strip() for x in entry[key])):
            raise Stop('invalid list: ' + key)
    if entry['verified'] is not True or entry['status'] not in ('MAYBE', 'YES', 'NO'):
        raise Stop('invalid verified/status')
    expected = dict(main=f'/characters/{ident:03d}/main.webp', normal=f'/characters/{ident:03d}/a.webp', graphic=f'/characters/{ident:03d}/b.webp')
    if entry['images'] != expected:
        raise Stop('image mapping mismatch')
    for name in REQUIRED - {'character.json'}:
        webp(raw[name])
    with Image.open(io.BytesIO(raw['main.webp'])) as image:
        if image.width <= image.height or image.width < 1000:
            raise Stop('landscape encyclopedia sheet missing')
    if (root / f'public/characters/{ident:03d}').exists():
        raise Stop('destination exists')
    rows.append(entry)
    numbering['canonicalIds'].append(ident)
    changes = {f'public/characters/{ident:03d}/{n}': raw[n] for n in REQUIRED - {'character.json'}}
    for name, value in [('characters.json', rows), ('numbering-audit.json', numbering)]:
        changes['public/' + name] = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    return changes


class Worker:
    def __init__(self, root, github, apply=False):
        self.root, self.github, self.apply = root, github, apply

    def log(self, event, **fields):
        with (self.root / '06_LOGS/sync.jsonl').open('a') as f:
            f.write(json.dumps(dict(time=time.time(), event=event, **fields), ensure_ascii=False) + '\n')
            f.flush()
            os.fsync(f.fileno())

    def ingest(self):
        for source in sorted((self.root / '01_INBOX').glob('*.zip')):
            # Producer uploads ZIP first and writes matching .ready.json last.
            receipt = source.with_suffix('.ready.json')
            if not receipt.is_file():
                self.log('WAIT_COMPLETE', file=source.name)
                continue
            try:
                before = source.stat()
                data = source.read_bytes()
                after = source.stat()
                meta = json.loads(receipt.read_text())
                sha = digest(data)
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise Stop('file still changing')
                if meta.get('sha256') != sha or meta.get('size') != len(data):
                    raise Stop('receipt mismatch: wait for Dropbox completion')
                package_data(data)
                backup = self.root / '05_BACKUP' / (sha + '.zip')
                if backup.exists() and backup.read_bytes() != data:
                    raise Stop('backup collision')
                if not backup.exists():
                    with backup.open('xb') as f:
                        f.write(data)
                        f.flush()
                        os.fsync(f.fileno())
                state = self.root / '02_PENDING' / (sha + '.json')
                if not state.exists() and not (self.root / '03_REGISTERED' / state.name).exists():
                    save(state, dict(sha256=sha, receipt=meta, source=source.name, phase='queued', attempts=0, nextRetry=0))
                self.log('PERSISTED', sha256=sha)
            except Exception as e:
                self.log('INBOX_HOLD', file=source.name, reason=str(e))

    def process(self, path):
        state = json.loads(path.read_text())
        if state.get('stop') or state.get('nextRetry', 0) > time.time():
            return
        sha = state['sha256']
        try:
            if not re.fullmatch(r'[0-9a-f]{64}', sha):
                raise Stop('invalid queue hash')
            data = (self.root / '05_BACKUP' / (sha + '.zip')).read_bytes()
            if digest(data) != sha:
                raise Stop('backup SHA256 mismatch')
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                if state.get('commit'):
                    if not self.apply:
                        self.log('DRY_RUN_RECOVERY_HOLD', sha256=sha)
                        return
                    # Never create a second commit after an uncertain ref-update response.
                    head = self.github.head()
                    if head != state['commit']:
                        raise Stop('RECOVERY_HOLD: inspect stored commit and main before resuming')
                    self.github.snapshot(state['commit'], root)
                    changes = {p: (root / p).read_bytes() for p in state['hashes']}
                    if any(digest(changes[p]) != h for p, h in state['hashes'].items()):
                        raise Stop('GitHub re-fetch mismatch')
                else:
                    parent = self.github.head()
                    tree = self.github.snapshot(parent, root)
                    changes = plan(root, data, state['receipt'])
                    if not self.apply:
                        self.log('DRY_RUN_PASS', sha256=sha, head=parent, files=list(changes))
                        return
                    state.update(parent=parent, phase='planned', hashes={p: digest(b) for p, b in changes.items()})
                    save(path, state)
                    commit = self.github.commit(parent, tree, changes)
                    state.update(commit=commit, phase='commit_created')
                    save(path, state)  # Intent durable BEFORE the only ref mutation.
                    self.github.publish(parent, commit)
                    state['phase'] = 'github_committed'
                    save(path, state)
                    with tempfile.TemporaryDirectory() as check:
                        fresh = Path(check)
                        self.github.snapshot(commit, fresh)
                        if any((fresh / p).read_bytes() != b for p, b in changes.items()):
                            raise Stop('GitHub re-fetch mismatch')
                    for p, b in changes.items():
                        target = root / p
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(b)
                audit(root)
                verify(root / 'public', SITE)
                verify(root / 'public', SITE, 'gemini')
                state.update(phase='published_verified', verifiedAt=time.time())
                save(path, state)
                dest = self.root / '03_REGISTERED' / path.name
                if dest.exists():
                    raise Stop('registered journal collision')
                os.rename(path, dest)
                self.log('SUCCESS', sha256=sha, commit=state['commit'])
        except Stop as e:
            state.update(stop=True, reason=str(e))
            save(path, state)
            save(self.root / '04_FAILED' / path.name, state)
            self.log('STOP', sha256=sha, reason=str(e))
        except Exception as e:
            state['attempts'] += 1
            state.update(nextRetry=time.time() + min(3600, 60 * 2 ** min(state['attempts'], 6)), error=type(e).__name__)
            save(path, state)
            self.log('RETRY', sha256=sha, phase=state['phase'], error=type(e).__name__)

    def run(self):
        for folder in FOLDERS:
            (self.root / folder).mkdir(exist_ok=True)
        with (self.root / '06_LOGS/worker.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            host = self.root / '06_LOGS/worker-host.json'
            if host.exists() and json.loads(host.read_text())['hostname'] != socket.gethostname():
                raise Stop('single-host worker only: host mismatch')
            if not host.exists():
                save(host, {'hostname': socket.gethostname()})
            self.ingest()
            for path in sorted((self.root / '02_PENDING').glob('*.json')):
                self.process(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='default is dry-run; requires GITHUB_TOKEN')
    args = parser.parse_args()
    if args.apply and not os.environ.get('GITHUB_TOKEN'):
        parser.error('--apply requires GITHUB_TOKEN; no secrets in files')
    Worker(args.root.resolve(), GitHub(os.environ.get('GITHUB_TOKEN')), args.apply).run()
