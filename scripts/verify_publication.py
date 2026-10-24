"""Require exact published registry, audit and image bytes, not SPA fallback HTTP 200."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request


def verify(root, url):
    paths = ['characters.json', 'numbering-audit.json']
    for row in json.loads((root / 'characters.json').read_text()):
        paths.extend(p.lstrip('/') for p in row['images'].values())
        if row.get('regeneratedDraft'):
            paths.append(row['regeneratedDraft'].lstrip('/'))
    for path in dict.fromkeys(paths):
        request = urllib.request.Request(url.rstrip('/') + '/' + path + '?verify=' + str(time.time_ns()),
                                         headers={'User-Agent': 'character-encyclopedia-publication-check/1.0', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=20) as response:
            actual = response.read(10_000_001)
        if hashlib.sha256(actual).digest() != hashlib.sha256((root / path).read_bytes()).digest():
            raise ValueError('publication mismatch: ' + path)
    print('PASS: published JSON and all referenced image bytes match')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path('public'))
    p.add_argument('--url', required=True)
    p.add_argument('--attempts', type=int, default=1)
    a = p.parse_args()
    for attempt in range(a.attempts):
        try:
            verify(a.root, a.url)
            break
        except Exception as e:
            print(e, flush=True)
            if attempt + 1 == a.attempts:
                raise
            time.sleep(15)
