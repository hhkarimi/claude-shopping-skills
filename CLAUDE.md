# CLAUDE.md

Repo-specific guidance for Claude Code sessions working in this plugin.

## Branch protection

- `main` is protected. No direct pushes — all changes via PR.
- PRs require CODEOWNER approval (= @hhkarimi) and passing CI (`lint`, `validate`).
- Squash-merge only — the PR title becomes the squash commit message.

## Commit conventions

Use **Conventional Commits** in PR titles. release-please reads these to decide version bumps:

| Prefix | release-please effect |
|---|---|
| `feat:` | minor version bump (0.1.0 → 0.2.0) |
| `fix:` | patch bump (0.1.0 → 0.1.1) |
| `feat!:` or `BREAKING CHANGE:` in body | major bump (0.1.0 → 1.0.0) |
| `chore:`, `docs:`, `ci:`, `refactor:`, `test:`, `style:` | no version bump |

When in doubt, prefer `chore:` or `docs:` for non-user-visible changes — a missed `feat:` just means the change ships in the next release-worthy bump.

## Architecture

Two layers:

1. **`amazon-product-data`** — generic Amazon search (`search.py`) + scrape (`scrape.py`) using stealth Playwright. Bypasses AWS WAF.
2. **`rank-*` skills** — each is a thin wrapper around `.claude-plugin/lib/ranking.py`. The shared module owns the math, the schema validation, and the CLI. Each skill provides only:
   - `references/nutrition_data.json` — curated per-domain data
   - `scripts/rank.py` — ~15-line wrapper that calls `run_cli(description=...)`
   - `SKILL.md` — domain-specific `type` values + leucine fractions

**Adding a new rank-* domain**: copy an existing skill folder (e.g. `skills/rank-dry-edamame`), replace the nutrition data, edit `SKILL.md` for the new domain.

**Adding a product to an existing skill**: edit that skill's `references/nutrition_data.json`. Schema is shared across rank-* — see [CONTRIBUTING.md](CONTRIBUTING.md#add-a-product-to-a-rank--skill).

**Rule (enforced by `tests/test_wrappers.py`)**: rank-* `scripts/rank.py` files must stay thin — no `def`, no `class`, no copy-paste of the ranking logic. Extend `.claude-plugin/lib/ranking.py` instead.

## Local commands

```bash
uvx ruff check .                  # lint
uvx ruff format --check .         # formatting
uvx pytest tests -v               # full test suite (43+ tests)
python3 tests/validate_skills.py  # SKILL.md frontmatter validator
```

CI runs all four on every PR — same commands, no surprises.

## Releases

[release-please](https://github.com/googleapis/release-please) watches `main` for Conventional Commits and opens a PR titled `chore: release vX.Y.Z` whenever something releasable lands. Merging that PR creates the Git tag and GitHub Release.

- Current baseline version: `0.1.0` (see `.release-please-manifest.json`)
- `.claude-plugin/plugin.json`'s `version` field is auto-bumped by release-please.
- The first release tag (v0.1.0) has not been created yet. Either wait for the first `feat:` PR after this convention lands, or run `gh release create v0.1.0 --generate-notes` to publish it manually.

## Things to NOT do

- Don't bypass branch protection (force-push, admin override on contributor PRs) without a stated reason.
- Don't add ranking logic to a skill's `rank.py` wrapper — extend the shared lib instead.
- Don't break the `nutrition_data.json` schema. `tests/test_nutrition_data.py` catches it, but make sure the change is intentional.
- Don't commit large or sensitive Amazon scrape artifacts (`.html`, `.png`) — `.gitignore` excludes them, but `git add -A` can sometimes pick them up if paths shift.
- Don't introduce new top-level directories without considering plugin-install behavior. The only directory guaranteed-present in an installed plugin is `.claude-plugin/`.
