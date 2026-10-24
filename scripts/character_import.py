"""Validated append-only character packages; no archive paths are extracted."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from PIL import Image


def load(path):
    return json.loads(path.read_text())


def webp(data):
    if len(data) > 10_000_000:
        raise ValueError('image exceeds 10 MB')
    with Image.open(io.BytesIO(data)) as im:
        if im.format != 'WEBP' or im.is_animated or not (1 <= im.width <= 8192 and 1 <= im.height <= 8192):
            raise ValueError('invalid WebP dimensions/format')
        im.load()


def registry_dir(source):
    if source not in ('canonical', 'gemini'):
        raise ValueError('unknown character source')
    return Path('public/gemini') if source == 'gemini' else Path('public')


def audit(root, source='canonical'):
    directory = registry_dir(source)
    rows = load(root / directory / 'characters.json')
    numbering = load(root / directory / 'numbering-audit.json')
    ids = [r['id'] for r in rows]
    if any(type(i) is not int or i < 1 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('duplicate/invalid IDs')
    if len({r['slug'] for r in rows}) != len(rows):
        raise ValueError('duplicate slugs')
    verified = {r['id'] for r in rows if r['verified'] is True}
    canonical = numbering['canonicalIds']
    reserved = numbering['reservedUnassignedIds']
    if len(set(canonical)) != len(canonical) or len(set(reserved)) != len(reserved):
        raise ValueError('duplicate audit IDs')
    if verified != set(canonical) or verified & set(reserved):
        raise ValueError('canonical/reserved numbering mismatch')
    for row in rows:
        paths = list(row['images'].values())
        if row.get('regeneratedDraft'):
            paths.append(row['regeneratedDraft'])
        for path in paths:
            if not re.fullmatch(('/gemini/characters/' if source == 'gemini' else '/characters/') + f"{row['id']:03d}" + r'/[a-z]+\.webp', path):
                raise ValueError('invalid image path')
            webp((root / 'public' / path.lstrip('/')).read_bytes())
    return rows, numbering


def apply(root, package, source='canonical'):
    rows, numbering = audit(root, source)
    with zipfile.ZipFile(package) as z:
        names = z.namelist()
        required = {'character.json', 'main.webp', 'a.webp', 'b.webp'}
        if set(names) != required or len(names) != 4 or sum(i.file_size for i in z.infolist()) > 31_000_000:
            raise ValueError('package must contain exactly character.json, main.webp, a.webp, b.webp')
        raw = {name: z.read(name) for name in names}
    entry = json.loads(raw['character.json'])
    ident = entry.get('id')
    if type(ident) is not int or ident != max(r['id'] for r in rows) + 1 or ident in numbering['reservedUnassignedIds']:
        raise ValueError('ID must be next unused number; reserved IDs cannot be filled')
    if not re.fullmatch(r'[a-z][a-z0-9-]*', entry.get('slug', '')) or entry['slug'] in {r['slug'] for r in rows}:
        raise ValueError('invalid/duplicate slug')
    for key in ('nameJa', 'nameEn', 'concept'):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            raise ValueError('missing ' + key)
    if entry.get('verified') is not True or (entry.get('source') != 'gemini' if source == 'gemini' else entry.get('provenance') != 'canonical') or entry.get('status') not in ('MAYBE', 'YES', 'NO'):
        raise ValueError('invalid registry metadata')
    if not isinstance(entry.get('emotionTheme'), list) or not all(isinstance(s, str) for s in entry['emotionTheme']):
        raise ValueError('invalid emotionTheme')
    prefix = '/gemini/characters' if source == 'gemini' else '/characters'
    expected = dict(main=f'{prefix}/{ident:03d}/main.webp', normal=f'{prefix}/{ident:03d}/a.webp', graphic=f'{prefix}/{ident:03d}/b.webp')
    if entry.get('images') != expected or 'regeneratedDraft' in entry:
        raise ValueError('package image mapping mismatch')
    dest = root / registry_dir(source) / f'characters/{ident:03d}'
    if dest.exists():
        raise ValueError('destination already exists')
    for name in ('main.webp', 'a.webp', 'b.webp'):
        webp(raw[name])
    # All validation precedes writes; Git publishes these files in one commit.
    dest.mkdir()
    for name in ('main.webp', 'a.webp', 'b.webp'):
        (dest / name).write_bytes(raw[name])
    rows.append(entry)
    numbering['canonicalIds'].append(ident)
    for path, value in [('characters.json', rows), ('numbering-audit.json', numbering)]:
        (root / registry_dir(source) / path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    audit(root, source)
    return ident


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--package', type=Path)
    p.add_argument('--source', choices=['canonical', 'gemini'], default='canonical')
    args = p.parse_args()
    if args.package:
        print('Imported', apply(args.root, args.package, args.source))
    rows, _ = audit(args.root, args.source)
    print(f"PASS: {len(rows)} entries, {sum(r['verified'] is True for r in rows)} verified, max ID {max(r['id'] for r in rows)}")
