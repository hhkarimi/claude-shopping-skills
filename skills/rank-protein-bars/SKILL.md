---
name: rank-protein-bars
description: Rank protein bars by $/g protein, calorie:protein ratio, and leucine-adjusted cost (muscle-building quality). Uses live Amazon prices via the amazon-product-data skill. Includes a curated database of common protein bars (whey blends, milk-protein, real-food).
---

# Protein bar ranker

Rank protein bars by the same three criteria as the protein-powder ranker: unit cost ($/g protein), calorie:protein ratio, and leucine-adjusted cost.

## When to use

- The user wants to choose a protein bar by $/g protein, calorie:protein ratio, or muscle-building cost-efficiency.
- The user wants to compare bars across categories (low-sugar/keto, mainstream whey, real-food).
- The user has new ASINs to add to an existing comparison.

## When NOT to use

- The user wants taste, texture, or subjective reviews.
- The user wants powders — use `rank-protein-powders` instead.

## How to use

Two modes:

### Search mode (one-command end-to-end)

```bash
uv run scripts/rank.py --search "protein bar low sugar" --nutrition references/nutrition_data.json
```

Searches Amazon, filters results to ASINs in the nutrition database, scrapes live prices, ranks. Search-result ASINs without nutrition data are listed at the end as candidates to add.

### Known-ASIN mode

1. Decide which ASINs to rank. Defaults live in `references/nutrition_data.json` (12 products as of last update, spanning whey blends, milk-protein blends, hydrolyzed whey, whey+collagen, plant blends, egg-based whole food, and peanut-butter/honey).
2. Scrape live prices via the `amazon-product-data` skill:
   ```bash
   uv run ../amazon-product-data/scripts/scrape.py B016MEN14O B0FN7MFN37 ...
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

`references/nutrition_data.json` keys products by ASIN. Same schema as `rank-protein-powders` — a bar counts as one serving:
- `name`: human label
- `type`: `whey_blend`, `whey_milk_blend`, `whey_collagen_blend`, `milk_protein`, `plant_blend`, `peanut_butter_honey`, `dairy_free`
- `servings_per_container`: bars per box
- `protein_per_serving_g`: protein per bar
- `calories_per_serving`: calories per bar
- `leucine_per_serving_g`: leucine per bar

Approximate leucine fractions by source (used when a manufacturer doesn't publish the value):
- Pure whey isolate: ~11% of protein
- Whey blend / milk protein blend: ~9–10%
- Whey + collagen blend: ~7–8% (collagen has almost no leucine)
- Plant blend: ~8%
- Real-food (peanut/honey/almond): ~7–8%

## Leucine adjustment

Same heuristic as `rank-protein-powders`: `leucine_adjusted = dollar_per_g_protein * (0.11 / leucine_fraction)`. Normalizes plant/blend bars to whey-equivalent muscle-building cost.

## Adding new products

1. Find the Amazon ASIN.
2. Read the manufacturer's nutrition facts panel.
3. Add an entry to `references/nutrition_data.json`.
4. Re-run the scrape + rank flow.

## Shared ranker implementation

The actual ranking logic lives in `.claude-plugin/lib/ranking.py`. The `scripts/rank.py` in this skill is a thin wrapper that calls into it. The same shared module backs `rank-protein-powders`. To add a new comparison domain, copy this skill's wrapper pattern and provide a new `nutrition_data.json`.
