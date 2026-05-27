# Contributing

Thanks for considering a contribution. This repo is small on purpose — please keep PRs focused.

## Ground rules

- The repo has a single owner ([@hhkarimi](https://github.com/hhkarimi)). All PRs require their review before merging.
- `main` is protected: no direct pushes, no force pushes, no deletions.
- CI must pass before merge.

## How to contribute

### Add a product to the protein ranker

The most common contribution. Open a [new add-product issue](https://github.com/hhkarimi/claude-shopping-skills/issues/new?template=add_product.md), or open a PR directly:

1. Find the Amazon ASIN (the 10-character ID in the product URL).
2. Read the manufacturer's nutrition label.
3. Add an entry to `skills/rank-protein-powders/references/nutrition_data.json`:

   ```json
   "B0XXXXXXXX": {
     "name": "Brand X Whey Isolate, Vanilla, 5 lb",
     "type": "whey_isolate",
     "servings_per_container": 65,
     "protein_per_serving_g": 25,
     "calories_per_serving": 120,
     "leucine_per_serving_g": 2.75
   }
   ```

4. If leucine isn't on the label, use the heuristic in `skills/rank-protein-powders/SKILL.md`.
5. Run `uv run skills/rank-protein-powders/scripts/rank.py ...` locally to confirm the row appears.

### Fix the scraper

Amazon changes its DOM occasionally. If `scrape.py` returns null prices:

1. Open a product page in your browser, inspect the price element.
2. Add the new selector to the `PRICE_SELECTORS` list in `skills/amazon-product-data/scripts/scrape.py`.
3. Test locally on 2–3 ASINs.

### Add a new comparison domain

The pattern is "generic scraper skill + domain-specific ranker skill." See the existing pair for the shape.

## Local dev

Requirements: `uv` (`brew install uv`). Everything else is managed by uv.

```bash
# Lint
uvx ruff check .

# Validate SKILL.md frontmatter
python3 tests/validate_skills.py

# Smoke test the ranker
uv run skills/rank-protein-powders/scripts/rank.py \
  --prices tests/fixtures/results_sample.json \
  --nutrition skills/rank-protein-powders/references/nutrition_data.json
```

CI runs the same three checks on every PR.

## Out of scope

- Subjective product reviews (taste, texture, brand reputation)
- Mass-market scraping (>~50 ASINs per run — use the official PA-API)
- Other retailers (could be a separate plugin; keep this one Amazon-focused)
