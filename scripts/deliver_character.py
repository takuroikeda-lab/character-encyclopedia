"""Authenticated local-file handoff; validates without changing public data."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
from character_import import apply


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('package', type=Path)
    a = p.parse_args()
    data = a.package.resolve()
    if git('status', '--porcelain'):
        raise SystemExit('Use a clean checkout')
    if git('branch', '--show-current') != 'main':
        raise SystemExit('Use main')
    git('fetch', 'origin', 'main')
    if git('rev-parse', 'HEAD') != git('rev-parse', 'origin/main'):
        raise SystemExit('Local main differs from origin/main')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shutil.copytree('public', root / 'public')
        ident = apply(root, data)
    dest = Path(f'imports/daily/{ident:03d}.zip')
    if dest.exists():
        raise SystemExit('Incoming package already exists')
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(data, dest)
    git('add', '--', str(dest))
    git('commit', '-m', f'Deliver character {ident:03d} for validated import')
    git('push', 'origin', 'HEAD:main')
    print('Delivered ZIP; check the Validated character import workflow before declaring success')
