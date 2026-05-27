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

Each ranking skill (e.g. `rank-protein-powders`, `rank-protein-bars`, `rank-dry-edamame`) ships with a curated `references/nutrition_data.json`. To add a product:

1. Find the Amazon ASIN (the 10-character ID in the product URL).
2. Read the manufacturer's nutrition label.
3. Add an entry to the appropriate skill's `references/nutrition_data.json`. The schema is the same across all rank-* skills:
   ```json
   "B0XXXXXXXX": {
     "name": "Brand X Product, Variant, Size",
     "type": "<see SKILL.md for valid values>",
     "servings_per_container": 12,
     "protein_per_serving_g": 25,
     "calories_per_serving": 200,
     "leucine_per_serving_g": 2.0
   }
   ```
4. If leucine isn't on the label, use the per-type heuristic in the skill's `SKILL.md`.
5. Run the ranker locally (see below) to confirm the row appears.

### Fix the Amazon scraper

Amazon changes its DOM occasionally. If `search.py` or `scrape.py` returns nulls or empty results:

1. Open a search-results page or product page in your browser, inspect the relevant element.
2. Update the selector lists in `skills/amazon-product-data/scripts/{search,scrape}.py`.
3. Test locally against 2–3 ASINs.

### Add a new comparison domain

The pattern: each rank-* skill is just a `SKILL.md`, a `nutrition_data.json`, and a thin `rank.py` wrapper. The actual ranking math lives in `.claude-plugin/lib/ranking.py` and is shared across all domains. To add a new domain, copy the structure of an existing rank-* skill and replace its data.

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
