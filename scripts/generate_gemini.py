"""Bounded Gemini API generation. Never writes to public/ or commits by itself."""
import argparse
import base64
from datetime import datetime
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import shutil
import urllib.error
import urllib.request
import zipfile
from zoneinfo import ZoneInfo
from PIL import Image
from character_import import apply, audit, next_id

ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/interactions'
FIELDS = ('slug', 'nameJa', 'nameEn', 'animal', 'concept', 'silhouette', 'asymmetry', 'personality', 'signatureAction', 'plushConcept', 'internationalMessage')
PLAN_SCHEMA = dict(type='object', properties={**{k: {'type': 'string'} for k in FIELDS}, 'emotionTheme': {'type': 'array', 'items': {'type': 'string'}}, 'comicIdeas': {'type': 'array', 'items': {'type': 'string'}}}, required=[*FIELDS, 'emotionTheme', 'comicIdeas'])
REVIEW_SCHEMA = {'type': 'object', 'properties': {'accepted': {'type': 'boolean'}, 'issues': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['accepted', 'issues']}


def parts(response):
    if response.get('status') != 'completed':
        raise ValueError('Gemini interaction did not complete; nothing published')
    return [part for step in response.get('steps', []) if step.get('type') == 'model_output' for part in step.get('content', [])]


class Gemini:
    def __init__(self, key):
        if not key or not key.strip():
            raise ValueError('Set the GitHub Actions secret GEMINI_API_KEY first')
        self.key = key
        self.calls = 0

    def call(self, model, inputs, response_format):
        if self.calls >= 5:
            raise ValueError('Five-call generation limit reached')
        self.calls += 1
        body = json.dumps({'model': model, 'input': inputs, 'response_format': response_format, 'store': False}).encode()
        request = urllib.request.Request(ENDPOINT, data=body, headers={'x-goog-api-key': self.key, 'Content-Type': 'application/json', 'User-Agent': 'character-encyclopedia-generator/1.0'}, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                raw = response.read(40_000_001)
            if len(raw) > 40_000_000:
                raise ValueError('Gemini response exceeds limit')
            return json.loads(raw)
        except urllib.error.HTTPError as error:
            # Do not print request headers, API key, or raw remote error bodies.
            raise RuntimeError(f'Gemini API HTTP {error.code}; check API key, billing, model access and quota') from None

    def structured(self, model, inputs, schema):
        result = parts(self.call(model, inputs, {'type': 'text', 'mime_type': 'application/json', 'schema': schema}))
        return json.loads(''.join(p.get('text', '') for p in result if p.get('type') == 'text'))

    def image(self, model, inputs, aspect):
        result = parts(self.call(model, inputs, {'type': 'image', 'aspect_ratio': aspect, 'image_size': '1K'}))
        images = [p for p in result if p.get('type') == 'image' and p.get('data')]
        if len(images) != 1:
            raise ValueError('Expected exactly one generated image')
        return base64.b64decode(images[0]['data'], validate=True)


def image_part(data):
    with Image.open(io.BytesIO(data)) as im:
        if im.format not in ('PNG', 'JPEG', 'WEBP') or getattr(im, 'is_animated', False) or not (1 <= im.width <= 8192 and 1 <= im.height <= 8192):
            raise ValueError('Invalid generated image')
        im.load()
        mime = Image.MIME[im.format]
    return {'type': 'image', 'mime_type': mime, 'data': base64.b64encode(data).decode()}


def text(value):
    return {'type': 'text', 'text': value}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def generate(root, out, client, day=None):
    day = day or datetime.now(ZoneInfo('Asia/Tokyo')).date().isoformat()
    datetime.strptime(day, '%Y-%m-%d')
    rows, numbering = audit(root, 'gemini')
    if any(row.get('generationDateTokyo') == day for row in rows):
        return None
    if out.exists():
        raise ValueError('Output directory already exists; preserve it and use a new directory')
    out.mkdir(parents=True)
    config = json.loads((root / 'config/gemini-automation.json').read_text())
    brief = (root / 'prompts/gemini-creative-brief.md').read_text()
    ident = next_id(rows, numbering, 'gemini')
    existing = [{k: row.get(k) for k in ('id', 'slug', 'nameJa', 'animal', 'concept', 'emotionTheme')} for row in rows]
    plan_prompt = f'{brief}\nCreate one NEW character for Gemini #{ident:03d}. Return Japanese settings and a unique lowercase ASCII slug, 3 comic ideas. Avoid these existing designs:\n' + json.dumps(existing, ensure_ascii=False)
    plan = client.structured(config['textModel'], [text(plan_prompt)], PLAN_SCHEMA)
    if any(not isinstance(plan.get(k), str) or not plan[k].strip() for k in FIELDS):
        raise ValueError('Incomplete character plan')
    if not re.fullmatch('[a-z][a-z0-9-]*', plan['slug']) or plan['slug'] in {r['slug'] for r in rows}:
        raise ValueError('Invalid or duplicate generated slug')
    for field in ('emotionTheme', 'comicIdeas'):
        if not isinstance(plan.get(field), list) or not plan[field] or not all(isinstance(s, str) and s.strip() for s in plan[field]):
            raise ValueError('Invalid plan list: ' + field)
    if len(plan['comicIdeas']) != 3:
        raise ValueError('Exactly three comic ideas required')
    # Whitelist model fields: the model never controls IDs, source, verification or paths.
    entry = {k: plan[k] for k in (*FIELDS, 'emotionTheme', 'comicIdeas')}
    entry.update(id=ident, status='MAYBE', verified=True, source='gemini', generationDateTokyo=day, generationMethod='gemini-api', images=dict(main=f'/gemini/characters/{ident:03d}/main.webp', normal=f'/gemini/characters/{ident:03d}/a.webp', graphic=f'/gemini/characters/{ident:03d}/b.webp'))
    write_json(out / 'character.json', entry)
    latest = max(rows, key=lambda row: row['id'])
    reference = (root / 'public' / latest['images']['main'].lstrip('/')).read_bytes()
    identity = json.dumps(entry, ensure_ascii=False)
    prompts = {'plan': plan_prompt}
    prompts['a'] = brief + '\nGenerate A normal edition. The reference is STYLE ONLY; invent the new character described below, never copy the old animal, silhouette or number. Full body with clear margins, portrait, no lettering.\n' + identity
    a = client.image(config['imageModel'], [text(prompts['a']), image_part(reference)], '4:5')
    image_part(a)
    (out / 'a-original').write_bytes(a)
    prompts['b'] = brief + '\nGenerate B graphic edition using THIS new A as identity reference. Preserve exact body, asymmetry, animal, clothing, colors and personality. Bold screen-print poster with short message internationalMessage and name only, legible lettering, full body.\n' + identity
    b = client.image(config['imageModel'], [text(prompts['b']), image_part(a)], '4:5')
    image_part(b)
    (out / 'b-original').write_bytes(b)
    prompts['main'] = brief + '\nCreate a landscape encyclopedia sheet. Use supplied A and B unchanged in separate panels, with a clean Japanese settings panel. Exact ID and text from metadata below. No invented total counts. Ensure correct Japanese names and no clipped text.\n' + identity
    sheet = client.image(config['imageModel'], [text(prompts['main']), image_part(a), image_part(b)], '16:9')
    image_part(sheet)
    (out / 'main-original').write_bytes(sheet)
    for name, data in [('a', a), ('b', b), ('main', sheet)]:
        with Image.open(io.BytesIO(data)) as im:
            im.convert('RGB').save(out / (name + '.webp'), 'WEBP', quality=90, method=6)
    write_json(out / 'prompts.json', prompts)
    review_prompt = 'Review the actual three images A, B, sheet against metadata. Reject inconsistent identity, wrong animal/number/name, cropped limbs, obvious extra limbs, materially garbled Japanese text, or missing requested panels. Do not assume success. Return accepted boolean and issues.\n' + identity
    review = client.structured(config['textModel'], [text(review_prompt), image_part(a), image_part(b), image_part(sheet)], REVIEW_SCHEMA)
    write_json(out / 'review.json', review)
    if review.get('accepted') is not True or review.get('issues') != []:
        raise ValueError('Automated visual review failed; artifacts retained, nothing published')
    package = out / f'{ident:03d}-{entry["slug"]}.zip'
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ('character.json', 'main.webp', 'a.webp', 'b.webp'):
            z.write(out / name, name)
    # Reuse the same importer in an isolated copy before allowing publication.
    with tempfile.TemporaryDirectory() as temp:
        sandbox = Path(temp)
        shutil.copytree(root / 'public', sandbox / 'public')
        apply(sandbox, package, 'gemini')
    write_json(out / 'manifest.json', {'dateTokyo': day, 'id': ident, 'slug': entry['slug'], 'textModel': config['textModel'], 'imageModel': config['imageModel'], 'review': 'automated-pass', 'package': package.name})
    return package


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--out', type=Path, default=Path('output/gemini-run'))
    args = parser.parse_args()
    try:
        package = generate(args.root, args.out, Gemini(os.environ.get('GEMINI_API_KEY')))
        print('Already generated today; no API generation needed' if package is None else 'Validated package: ' + str(package))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
