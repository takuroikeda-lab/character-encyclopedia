# Character delivery and import

## Current release status — 2026-10-24

MAGARI #037 was newly generated in this Codex session; no earlier ZIP was recovered. Built-in image generation produced A, B and the encyclopedia sheet, which were visually inspected and saved persistently before conversion to WebP. Delivery commit `867fe103fdba1f85474cd4975b4d674d278fd725` transferred the actual ZIP with the authenticated GitHub blob/tree/commit API. The real import workflow [40046677015](https://github.com/takuroikeda-lab/character-encyclopedia/actions/runs/40046677015) succeeded. Atomic publication commit `ea1b6d3441e347f7c66b57d4367d573a13abaf77` added three images and updated both JSON files together; the staging ZIP was consumed. Cloudflare's check on that commit succeeded, and published JSON plus all 56 referenced canonical-series images matched exact bytes. The old 36 records and reserved IDs 19–28 were unchanged. There are now 37 records, 27 verified, maximum ID 37.

The source-to-GitHub handoff has therefore been proven in this environment: generate → persist local files → WebP package → base64 Git blob → staging commit → validated Actions import → atomic public commit → Cloudflare → exact byte verification. This proves this delivery path, not a scheduled runtime's capabilities. Daily scheduling remains paused; no automation was resumed.

Gemini uses the same validator with `--source gemini`, input path `imports/gemini/*.zip`, registry `public/gemini/characters.json`, audit `public/gemini/numbering-audit.json`, and image prefix `/gemini/characters/`. Its existing #049 AMAOTO is preserved; next number is determined from current Gemini main, never reset to 001. The ZIP contract is the same four root members, with `source: "gemini"` and Gemini-prefixed paths. See [the Gemini execution prompt](../GEMINI_DAILY_PROMPT.md). The old hierarchical `imports/gemini_daily_import.zip` contract is retired.

The sections below describe the original audit and release limitations before this real MAGARI import.

## Audit on 2026-10-24

main at `68689b2b6d670be6e1f236fbb4359e0fc8280c4e` contains 36 entries, 26 verified, maximum ID 36. IDs 19–28 are unverified drafts and remain reserved. The audit file omitted canonical ID 36; only that omission is corrected. Existing character records and images are unchanged. Gemini's separate registry is not renumbered or merged.

The referenced ChatGPT conversation supplies only a `sandbox:/mnt/data/character_037_MAGARI.zip` link; its attachment list is empty and the ZIP is unavailable in this workspace. No MAGARI images are present in the repository. `imports/{main,a,b}.webp` are byte-identical to #036, and must not be relabeled as #037. The historical safety rejection cannot be diagnosed from the available transcript because detailed rejection logs are absent. The temporary note is inert and retained pending any separate cleanup request.

## Delivery contract

The generation process must save actual files to a persistent location before its temporary runtime expires. A ChatGPT sandbox link is not a URL GitHub Actions can download. This implementation accepts a GitHub commit containing `imports/daily/037-MAGARI.zip`. Use the authenticated GitHub web upload, or the local helper below after downloading/exporting generated files. Do not place tokens in the ZIP, JSON, prompt, or repository. Fully automatic generation-to-GitHub delivery is not established until the generation runtime has an authenticated persistent transport and a real package passes the production workflow.

Each ZIP must have exactly four root members (no folders):

- `character.json`: one complete registry entry
- `main.webp`: encyclopedia sheet
- `a.webp`: normal version
- `b.webp`: graphic version

#037 metadata must include `id: 37`, `slug: "magari"`, `nameJa: "まがり"`, `nameEn: "MAGARI"`, `verified: true`, `provenance: "canonical"`, `status: "MAYBE"`, `concept`, and string array `emotionTheme`. Its `images` object must map `main` to `/characters/037/main.webp`, `normal` to `/characters/037/a.webp`, and `graphic` to `/characters/037/b.webp`. Preserve any additional character settings in the entry. Review the actual images against the character brief before delivery; decoding alone does not establish identity or artistic correctness.

Run locally with Python 3.12 and `pip install -r scripts/requirements-import.txt`:

```
python scripts/deliver_character.py /path/to/037-MAGARI.zip
```

The helper validates in an isolated copy, checks that local main equals remote main, and pushes only the ZIP. Git authentication must already be configured. It never rewrites a branch. The workflow checks out current main, serializes import jobs, validates all assets and numbering, rejects existing IDs and directories, and commits three WebPs plus both registry files and removal of the incoming ZIP in one commit. The staging ZIP commit is separate from the atomic publication commit. If another main writer wins the race, push fails without forcing; rerun against current main after inspection. A failed validation never commits partial public data. Successful imports are not replayed because the ZIP is consumed.

The original legacy extraction workflow is retired because `unzip -o` could overwrite arbitrary repository files without registry checks. Legacy and Gemini migrations require their own reviewed validation contract; do not route them through the canonical daily importer.

## Publication gate

Workers Builds is already connected to main. The importer waits for exact SHA-256 equality of both JSON files and every referenced canonical image at `https://character-encyclopedia.link-link.workers.dev`. A missing deployment, stale data, or HTML fallback fails after bounded retries. GitHub's `GITHUB_TOKEN` does not trigger another Actions push workflow, so the import job itself performs publication verification; no downstream workflow is assumed. Workers Builds delivery from an Actions-authenticated push must be proven by a real package, not inferred from a previous human/API push. If it fails, investigate the Cloudflare check for the resulting commit and configure an approved GitHub App transport or explicit deployment integration before resuming generation.

Keep the daily generation task paused. Required release gate: recover and visually inspect MAGARI's actual three WebPs, import once through Actions, verify its single publication commit and matching production bytes, then explicitly resume the daily task. Synthetic fixtures stay in temporary test directories and are never added as real characters.

## Verification results

Implementation commit: `56c33ae18742cab9235ad38ce9db5d455ac629d2`. Eight automated tests cover successful import, replay rejection, reserved/out-of-sequence IDs, traversal/extra members, corrupt images, incorrect image mapping, audit drift, exact publication bytes/stale rejection, and a real isolated Git commit/push with concurrent push rejection. The atomic Git test confirms exactly three WebPs and two JSON files change together. No synthetic character is published. Production JSON and all 53 unique referenced image files matched byte-for-byte after deployment. The Python default User-Agent returned HTTP 403 locally; a named publication-check User-Agent succeeded. Detailed historical safety rejection logs remain unavailable. A real MAGARI ZIP and generation-runtime authenticated transport are still required for the final daily automation release gate.
