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

Two-layer plugin with one shared lib per concern:

1. **`amazon-product-data` skill** — generic Amazon search (`search.py`) + scrape (`scrape.py`) using stealth Playwright. Bypasses AWS WAF. The two scripts share `_lib.py` (co-located) for the 503-retry helper and the delivery-ZIP setter — edit there for retry/throttle changes, not in the individual scripts.

2. **`rank-*` skills** — each is a thin wrapper around `.claude-plugin/lib/ranking.py`. The shared module owns the math, the schema, the CLI, the table renderer (incl. Channel column, `% Δ vs prev` between adjacent ranks, and a `Buy` column rendering `[link](https://www.amazon.com/dp/<ASIN>)` for every product), and the "Best pick by goal" summary table that follows the main ranking. Each skill provides only:
   - `references/nutrition_data.json` — curated per-domain data
   - `scripts/rank.py` — ~15-line wrapper that calls `run_cli(description=...)`
   - `SKILL.md` — domain-specific `type` values + leucine fractions

**Channel column**: derived from each price entry's `fresh_available` field (set by scrape.py when `--zip` is passed). Falls back to the nutrition entry's `channel` field, then `"regular"`. When `fresh_available=True` AND a separate `fresh_price` was captured, that price drives the $/g math.

**Price freshness**: scrape.py stamps each result with `scraped_at` (ISO-8601 in Eastern Time via `zoneinfo.ZoneInfo("America/New_York")` — EDT in summer, EST in winter, DST switch is automatic). rank.py surfaces this as a "Prices captured: …" line below the picks table. Amazon prices move — sale items can shift hourly, stable SKUs weekly. Re-scrape within 24h of any purchase decision. The `scraped_at` field is on the scrape output (results.json), **not** in `nutrition_data.json` — nutrition facts are static, so don't conflate the two. Committed test fixtures carry an explicit `scraped_at` baked in (currently `2026-05-27T22:00:00-04:00`) so the freshness line renders deterministically in CI. External `results.json` that predates the field will simply not render the line — accurate ("we don't know when these were captured") rather than misleading.

**Adding a new rank-* domain**: copy an existing skill folder (e.g. `skills/rank-greek-yogurt` as the most recent template), replace the nutrition data, edit `SKILL.md` for the new domain.

**Adding a product to an existing skill**: edit that skill's `references/nutrition_data.json`. Schema is shared across rank-* — see [CONTRIBUTING.md](CONTRIBUTING.md#add-a-product-to-a-rank--skill).

**Cross-channel pairs**: same product on Fresh + Regular under different ASINs? Add both as separate entries with explicit `"channel"` fields — see [CONTRIBUTING.md](CONTRIBUTING.md#cross-channel-pairs) for the think! bars example.

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

[release-please](https://github.com/googleapis/release-please) watches `main` for Conventional Commits and opens a PR titled `chore(main): release vX.Y.Z` whenever something releasable lands. Merging that PR creates the Git tag and GitHub Release.

- Current released version: see [CHANGELOG.md](CHANGELOG.md). At time of writing v0.3.0.
- `.claude-plugin/plugin.json`'s `version` field is auto-bumped by release-please.
- Versions live in `.release-please-manifest.json` too — both files must stay in sync; release-please handles this automatically.

## Things to NOT do

- Don't bypass branch protection (force-push, admin override on contributor PRs) without a stated reason.
- Don't add ranking logic to a skill's `rank.py` wrapper — extend the shared lib instead.
- Don't break the `nutrition_data.json` schema. `tests/test_nutrition_data.py` catches it, but make sure the change is intentional.
- Don't commit large or sensitive Amazon scrape artifacts (`.html`, `.png`) — `.gitignore` excludes them, but `git add -A` can sometimes pick them up if paths shift.
- Don't introduce new top-level directories without considering plugin-install behavior. The only directory guaranteed-present in an installed plugin is `.claude-plugin/`.
