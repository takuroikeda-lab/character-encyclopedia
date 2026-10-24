# Character delivery and import

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
