# Dropbox automatic synchronization

2026-11-16: canonical baseline f5796a8, 54 records / 44 verified, reserved 019–028 unchanged. Gemini is separate (24 verified). The worker never generates images, modifies original pixels, fills reserved IDs, or changes generation schedules.

## Package handoff

Single writer host: Mac mini. Root: `/Users/takuroikedamacbookpro/Library/CloudStorage/Dropbox/WORK/AI_System/CHARACTER_ENCYCLOPEDIA`.

Save exactly four root ZIP members: `character.json`, `main.webp`, `a.webp`, `b.webp`. The JSON must match the latest canonical 21-field schema. Determine the next ID from fresh main before creating the final sheet. The worker independently derives the ID from fresh HEAD; a stale printed number requires a reviewed replacement package and is held, never silently rewritten.

Upload `name.zip` completely, then write `name.ready.json` **last**, preferably via temporary file and atomic rename. Compute SHA256 and size at the producer before transport. Example receipt (replace placeholders; do not mark review true without inspecting actual originals):

```json
{
  "sha256": "64 lowercase hexadecimal characters",
  "size": 123456,
  "review": {
    "armsConsistent": true,
    "encyclopediaSheet": true,
    "schemaConsistent": true,
    "printedNumberAndName": true
  }
}
```

Hash equality to this producer receipt is the completion gate; stable size alone is insufficient. Image decode checks do not prove visual consistency or printed text. Those require actual review of the exact ZIP, represented by the receipt. Crash Clamp additionally requires `crashClampResolved: true` after arms, sheet and JSON are fixed. The existing unresolved package cannot pass with the ordinary four flags alone. No image rewriting is performed.

## Operation

Use Python 3.12 and `pip install -r scripts/requirements-import.txt` in a dedicated environment. Default invocation is dry-run:

```
python scripts/dropbox_sync.py --root /absolute/CHARACTER_ENCYCLOPEDIA
```

Dry-run persists originals, queue and logs but creates no GitHub object or registration. `--apply` additionally requires `GITHUB_TOKEN` supplied securely to the process, with Contents read/write for this repository. Never store the token in Dropbox, a receipt, source code or chat. This worker's Git Data API authentication is independent of the connected GitHub tool; connector access does not authenticate a scheduled local Python process. Even a populated dry-run benefits from an authenticated token because snapshot blob reads exceed the anonymous API quota.

Each run handles INBOX and due queue items independently. Invoke periodically using the Codex scheduled task. Generation at 07:00 remains an independent producer: save every day's output regardless of sync success, never make generation conditional on publication. This change does not create, disable or verify the external ChatGPT generation schedule.

## Durable state and safety

- `01_INBOX`: untouched originals and completion receipts; never delete automatically.
- `05_BACKUP/<zip-sha256>.zip`: exact originals, checked again before processing.
- `02_PENDING/<sha>.json`: durable phase, receipt, attempts, retry time, expected parent, commit and output hashes.
- `03_REGISTERED/<sha>.json`: success journal only after GitHub re-fetch and both production series pass exact byte verification; the original remains in BACKUP and INBOX.
- `04_FAILED/<sha>.json`: STOP diagnostic copy; source queue remains stopped for inspection.
- `06_LOGS/sync.jsonl`: append-only run events; `worker-host.json` pins the single host and `worker.lock` prevents overlapping same-host runs. Do not run this worker on another synced Mac: Dropbox is not a distributed lock service.

The worker reads fresh main and builds an append-only five-file change: three unmodified WebPs, registry and numbering audit. Existing public tree entries are retained. It creates Git blobs/tree/one parented commit, journals its SHA **before** updating main, checks main again, and uses `force: false`. A concurrent writer rejects the sibling commit. Conflict stops the item; no automatic rebase, force or number reuse. Unreferenced Git objects may remain after failure but do not publish anything.

Transient failures retry with exponential delay capped at one hour. Cloudflare lag resumes the stored commit without re-registering. If the ref response is lost and main equals that stored commit, re-fetch and verify it; if main has advanced, STOP for ancestry/content inspection. Conservative holds are intentional: do not clear `stop` blindly. Verify parent, stored commit, package, current HEAD and public bytes before repairing state. Never delete a stored commit field to retry a possibly registered package.

A STOP does not block other candidates or generation. Quality correction uses a new immutable ZIP + matching receipt. Old stopped journals remain as evidence. Existing names/slugs cannot register twice; known legacy ZIPs for #053/#054 remain duplicates even with provisional IDs. Names are compared exactly; semantic aliases require review.

## Verification scope

Tests cover partial transfer/no receipt, exact backup/replay, dry-run, duplicate identity, reserved/stale IDs, append-only changes, schema/archive safety, Crash Clamp hold, host pin, ref conflict, network backoff, uncertain ref recovery, and publication retry without a second commit. Synthetic fixtures never leave temporary test directories. Actual new-character publication requires a real reviewed ZIP and local runtime authentication; an empty INBOX does not establish end-to-end registration success.
