#!/usr/bin/env python3
"""Validate a staged character and publish all files in one Git commit."""
import argparse
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"

def fail(message):
    raise SystemExit("STOP: " + message)

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, help="Directory containing metadata.json and main/a/b.webp")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    stage = (ROOT / args.stage).resolve()
    if not stage.is_relative_to(ROOT / "imports"):
        fail("stage must be inside imports/")
    records = load(PUBLIC / "characters.json")
    audit = load(PUBLIC / "numbering-audit.json")
    metadata = load(stage / "metadata.json")
    verified = [c for c in records if c.get("verified") is True]
    ids = [c["id"] for c in records]
    if len(ids) != len(set(ids)):
        fail("existing duplicate ids")
    maximum = max(c["id"] for c in verified)
    number = maximum + 1
    if metadata.get("id") != number:
        fail(f"expected next verified id {number}, got {metadata.get('id')}")
    reserved = set(audit.get("reservedUnassignedIds", []))
    if number in reserved or number in ids or number in audit.get("canonicalIds", []):
        fail("number is reserved or already used")
    if any(c.get("slug") == metadata.get("slug") for c in records):
        fail("duplicate slug")
    required = ("id", "slug", "nameJa", "nameEn", "concept", "emotionTheme")
    if any(not metadata.get(key) for key in required):
        fail("missing required metadata")
    if not re.fullmatch(r"[a-z0-9-]+", metadata["slug"]):
        fail("invalid slug")
    if metadata.get("verified") not in (None, True) or metadata.get("status") not in (None, "MAYBE"):
        fail("invalid status/verified")
    for name in ("main", "a", "b"):
        file = stage / (name + ".webp")
        if not file.is_file():
            fail("missing " + str(file))
        data = file.read_bytes()
        if len(data) < 100 or len(data) > 5_000_000 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            fail("invalid WebP or size: " + name)
    dest = PUBLIC / "characters" / f"{number:03d}"
    if dest.exists():
        fail("destination already exists")
    images = {"main": f"/characters/{number:03d}/main.webp", "normal": f"/characters/{number:03d}/a.webp", "graphic": f"/characters/{number:03d}/b.webp"}
    entry = dict(metadata)
    entry.update(status="MAYBE", verified=True, images=images)
    if args.check_only:
        print(f"PASS: #{number:03d} {entry['nameEn']}; no files changed")
        return
    dest.mkdir(parents=True)
    for name in ("main", "a", "b"):
        shutil.copyfile(stage / (name + ".webp"), dest / (name + ".webp"))
    records.append(entry)
    (PUBLIC / "characters.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit["canonicalIds"].append(number)
    (PUBLIC / "numbering-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ADD: #{number:03d} {entry['nameEn']}")

if __name__ == "__main__":
    main()
