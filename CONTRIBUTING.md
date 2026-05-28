# Contributing

Thanks for considering a contribution. This repo is small on purpose — please keep PRs focused.

## Ground rules

- The repo has a single owner ([@hhkarimi](https://github.com/hhkarimi)). All PRs require their review before merging.
- `main` is protected: no direct pushes, no force pushes, no deletions.
- CI must pass before merge.
- All merges are squash merges (configured at the repo level).

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/) so `release-please` can cut versioned releases automatically:

- `feat:` — a new feature (minor version bump)
- `fix:` — a bug fix (patch bump)
- `feat!:` or `BREAKING CHANGE:` in body — breaking change (major bump)
- `chore:`, `docs:`, `ci:`, `refactor:`, `test:` — no version bump

PR titles become the squash-merge commit message, so prefix your PR title with the right type.

## How to contribute

### Add a product to a `rank-*` skill

Each ranking skill (e.g. `rank-protein-powders`, `rank-protein-bars`, `rank-dry-edamame`, `rank-greek-yogurt`) ships with a curated `references/nutrition_data.json`. To add a product:

1. Find the Amazon ASIN (the 10-character ID in the product URL).
2. Read the manufacturer's nutrition label.
3. Add an entry to the appropriate skill's `references/nutrition_data.json`. The schema is the same across all rank-* skills:
   ```json
   "B0XXXXXXXX": {
     "name": "Brand X Product, Variant, Size",
     "type": "<see SKILL.md for valid values>",
     "channel": "regular",
     "servings_per_container": 12,
     "protein_per_serving_g": 25,
     "calories_per_serving": 200,
     "leucine_per_serving_g": 2.0
   }
   ```
4. If leucine isn't on the label, use the per-type heuristic in the skill's `SKILL.md`.
5. Run the ranker locally (see below) to confirm the row appears.

#### Optional `channel` field

`channel` is `"regular"` or `"fresh"`. It seeds the default Channel column when search-mode can't determine it at runtime (e.g. `--prices` mode without `--search`). The runtime `fresh_available` value from scrape.py overrides this default if it's set. Most entries should be `"regular"`; use `"fresh"` only for products whose Amazon listing is sold by AmazonFresh (e.g. a 10-pack of the same bar that the regular 12-pack ASIN doesn't carry).

#### Cross-channel pairs

Amazon Fresh sometimes lists the same brand under a different ASIN than regular Amazon — often a different pack size. To compare both side-by-side in the ranking, add **both** ASINs as separate entries, each tagged with its `channel`. Example from `rank-protein-bars`:

```json
"B0B17P5N3D": { "name": "think! Brownie Crunch, 12 ct", "channel": "regular", ... },
"B000CRIBCA": { "name": "think! Brownie Crunch, 10 ct (Amazon Fresh)", "channel": "fresh", ... }
```

The ranker treats them as distinct products and surfaces them both in the table at their respective prices — letting the user pick by per-gram cost vs convenience.

### Fix the Amazon scraper

Amazon changes its DOM occasionally. If `search.py` or `scrape.py` returns nulls or empty results:

1. Open a search-results page or product page in your browser, inspect the relevant element.
2. Update the selector lists in `skills/amazon-product-data/scripts/{search,scrape}.py`.
3. Test locally against 2–3 ASINs.

The 503-retry and ZIP-setting helpers are shared between both scripts in `skills/amazon-product-data/scripts/_lib.py` — edit there if you're touching retry/throttle behavior, not in the individual scripts.

### Add a new comparison domain

The pattern: each rank-* skill is just a `SKILL.md`, a `nutrition_data.json`, and a thin `rank.py` wrapper. The actual ranking math lives in `.claude-plugin/lib/ranking.py` and is shared across all domains. To add a new domain, copy the structure of an existing rank-* skill (e.g. `rank-greek-yogurt` is the most recent template) and replace its data.

## Discovery workflow

When you run a `rank-*` skill in search mode, the ranker only considers ASINs that are in the nutrition database. ASINs found by search but not in the DB get listed at the end as `Found in search but no nutrition data`. **That list is the discovery feed** — when you're trying to surface the actual best deals (not just rank what we already know), you should triage that list as part of the run.

The recommended flow:

1. **Run with `--search` + `--zip`** to surface both regular Amazon and Fresh storefront candidates (rank.py passes `--include-fresh` through to search.py automatically when `--zip` is set):
   ```bash
   uv run skills/rank-protein-bars/scripts/rank.py \
     --search "protein bars" --zip 78752 \
     --nutrition skills/rank-protein-bars/references/nutrition_data.json
   ```

2. **Read the "Found in search but no nutrition data" list** under the table on stderr. Each entry is a brand+title preview.

3. **Pick the candidates worth adding**. Useful filters:
   - Brand already in our DB on the OTHER channel — likely cross-channel pair (e.g. Fresh-exclusive 10-ct of a regular 12-ct we have)
   - Notable/popular brand not yet in the DB — fills a real gap
   - Amazon's own house brand (`Amazon Grocery`) — Fresh-exclusive store-brand items often beat name brands on $/g

4. **Scrape each candidate** to confirm the pack count, price, and Fresh availability:
   ```bash
   uv run skills/amazon-product-data/scripts/scrape.py <ASIN> --zip 78752
   ```
   The scraped result includes `fresh_available` and (when present) `fresh_price` — these tell you which `channel` tag to use.

5. **Add to `nutrition_data.json`** with the right channel. For products that exist on both Amazon and Amazon Fresh under different ASINs, add BOTH entries — see [Cross-channel pairs](#cross-channel-pairs).

6. **Re-run the pipeline** and check the ranking with the new entries included.

Result: each cycle expands the database with the actual high-value items the live search surfaced, so subsequent runs rank a more complete set.

## Local dev

Requirements: `uv` (`brew install uv`). Everything else is managed by uv.

```bash
# Lint + format check
uvx ruff check .
uvx ruff format --check .

# Validate SKILL.md frontmatter + nutrition data schema
python3 tests/validate_skills.py

# Run the full test suite
uvx pytest tests -v

# Smoke test any rank-* skill against the committed fixture
uv run skills/rank-protein-powders/scripts/rank.py \
  --prices tests/fixtures/results_sample.json \
  --nutrition skills/rank-protein-powders/references/nutrition_data.json
```

CI runs all of these on every PR.

## Out of scope

- Subjective product reviews (taste, texture, brand reputation).
- Mass-market scraping (>~50 ASINs per run — use Amazon's official Product Advertising API).
- Retailers other than Amazon — could be a separate plugin; keep this one Amazon-focused.
