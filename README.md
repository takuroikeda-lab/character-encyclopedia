# character-encyclopedia

Cloudflare Workers auto-deployment is connected to the `main` branch.

## Source of truth

- `public/characters.json`: verified character registry
- `public/numbering-audit.json`: historical numbering conflicts; numbers are never invented or silently reassigned
- `public/official-selection.json`: reserved for the final official-IP selection
- `public/characters/NNN/`: web images for each verified character

## Daily update rule

1. Generate one new character.
2. Assign the next unused verified number.
3. Generate A normal and B graphic images.
4. Optimize web images to WebP.
5. Add/update one entry in `public/characters.json`.
6. Add images under `public/characters/NNN/`.
7. Commit to `main`.
8. Cloudflare deploys automatically.

## One-time legacy image import

Upload `character_encyclopedia_legacy_import.zip` into the repository path:

`imports/character_encyclopedia_legacy_import.zip`

GitHub Actions will unpack the verified recent images and legacy archive into `public/`, commit them, and trigger Cloudflare automatically.

## Validated daily import

See [delivery contract and release gates](docs/character-import.md). Upload packages only to `imports/daily/`. The former unvalidated legacy extraction workflow is retired. Daily generation remains paused until a real package passes Actions and exact Cloudflare publication verification.

Gemini packages use `imports/gemini/` and the same four-file contract. Follow [the current Gemini prompt](GEMINI_DAILY_PROMPT.md); the former #001 restart rule and hierarchical ZIP format are retired. MAGARI #037 has passed a real end-to-end import and publication check; daily scheduling remains paused.
