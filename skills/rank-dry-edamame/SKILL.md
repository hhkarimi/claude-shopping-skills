---
name: rank-dry-edamame
description: Rank dry-roasted edamame snacks by $/g protein, calorie:protein ratio, and leucine-adjusted cost. Uses live Amazon prices via the amazon-product-data skill. Includes a curated database of common dry-roasted edamame products (bulk jars, snack packs, multi-flavor variety).
---

# Dry-roasted edamame ranker

Rank dry-roasted edamame snacks by the same three criteria as `rank-protein-powders` and `rank-protein-bars`: unit cost ($/g protein), calorie:protein ratio, and leucine-adjusted cost.

## When to use

- The user wants to choose a dry-roasted edamame product by $/g protein, cal:protein ratio, or muscle-building cost-efficiency.
- The user wants to compare bulk jars vs single-serve snack packs.
- The user has new ASINs to add to an existing comparison.

## When NOT to use

- The user wants taste or texture reviews.
- The user wants frozen/in-pod edamame — this skill covers shelf-stable dry-roasted only.
- The user wants powders or bars — use `rank-protein-powders` or `rank-protein-bars` instead.

## How to use

Two modes:

### Search mode (one-command end-to-end)

```bash
uv run scripts/rank.py --search "dry roasted edamame bulk" --nutrition references/nutrition_data.json
```

Searches Amazon, filters results to ASINs in the nutrition database, scrapes live prices, ranks. Search-result ASINs without nutrition data are listed at the end as candidates to add.

### Known-ASIN mode

1. Decide which ASINs to rank. Defaults live in `references/nutrition_data.json` (8 products as of last update, spanning bulk jars, multi-pack bags, and single-serve snack packs).
2. Scrape live prices via the `amazon-product-data` skill:
   ```bash
   uv run ../amazon-product-data/scripts/scrape.py B0094IXKME B09FFXR2VV ...
   ```
3. Run the ranker:
   ```bash
   uv run scripts/rank.py --prices /tmp/amzn/results.json --nutrition references/nutrition_data.json
   ```
4. Prints a markdown table sorted by $/g protein. Pass `--sort cal_protein` or `--sort leucine_adjusted` to re-sort.

To rank the full default set in one shot:
```bash
ASINS=$(jq -r 'keys[]' references/nutrition_data.json | tr '\n' ' ')
uv run ../amazon-product-data/scripts/scrape.py $ASINS
uv run scripts/rank.py --prices /tmp/amzn/results.json --nutrition references/nutrition_data.json
```

## Nutrition database

Same schema as the other rank-* skills. See `.claude-plugin/lib/ranking.py` for the canonical key list and `tests/test_nutrition_data.py` for the validation rules.

Edamame is whole soybean — the leucine fraction is ~8% of protein (same as soy isolate). A 1 oz (28g) serving of dry-roasted edamame typically delivers 13–14g protein at 130 calories.

## Why "dry roasted" specifically

Frozen or fresh edamame has very different shipping logistics, pricing, and serving conventions. Limiting this skill to shelf-stable dry-roasted keeps the data set internally comparable.

## Adding new products

1. Find the Amazon ASIN.
2. Read the manufacturer's nutrition facts panel (look for grams of protein per labeled serving, not per package).
3. Add an entry to `references/nutrition_data.json`.
4. Re-run the scrape + rank flow.

## Shared ranker implementation

The actual ranking logic lives in `.claude-plugin/lib/ranking.py`. The `scripts/rank.py` in this skill is a thin wrapper that calls into it — same pattern as `rank-protein-powders` and `rank-protein-bars`.
