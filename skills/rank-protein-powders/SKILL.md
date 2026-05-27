---
name: rank-protein-powders
description: Rank protein powders by $/g protein and calorie:protein ratio, with optional leucine adjustment for muscle-building cost comparison. Uses live Amazon prices via the amazon-product-data skill. Includes a curated database of common whey, pea, soy, egg, and blended-plant protein products.
---

# Protein powder ranker

Rank protein powders by economic + nutritional efficiency. Combines live Amazon pricing with curated nutrition data to produce a ranked comparison table.

## When to use

- The user wants to choose a protein powder by $/g protein, calorie:protein ratio, or muscle-building cost-efficiency.
- The user wants to compare multiple brands or protein sources (whey, pea, soy, egg, blends).
- The user has new ASINs to add to an existing comparison.

## When NOT to use

- The user wants taste, mixability, or subjective reviews — this skill compares numbers only.
- The user wants a single recommendation without seeing the data — provide one, but caveat that it's heuristic.

## How to use

1. Decide which ASINs to rank. Defaults live in `references/nutrition_data.json` (12 products as of last update). The user may add their own.
2. Scrape live prices via the `amazon-product-data` skill:
   ```bash
   uv run ../amazon-product-data/scripts/scrape.py B000MAK59O B01HOPJAAE B002TG3QPO ...
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

`references/nutrition_data.json` keys products by ASIN. Each entry has:
- `name`: human label
- `type`: `whey_isolate`, `whey_concentrate`, `whey_blend`, `pea`, `soy`, `egg`, `pea_rice_blend`
- `servings_per_container`: int
- `protein_per_serving_g`: int
- `calories_per_serving`: int
- `leucine_per_serving_g`: float

Approximate leucine fractions by source (used if a manufacturer doesn't publish the value):
- Whey isolate: ~11% of protein
- Whey concentrate / blend: ~10%
- Egg white: ~8.5%
- Soy isolate: ~8%
- Pea isolate: ~8%
- Pea+rice blend: ~8%

## Leucine adjustment

Muscle protein synthesis (MPS) requires ~2.5–3 g leucine per serving. Whey hits this at ~25 g protein; pea/soy needs ~30–35 g. The `leucine_adjusted` column normalizes $/g protein to whey-equivalent cost so plant and animal sources can be compared as cost-per-anabolic-unit.

Formula: `leucine_adjusted = dollar_per_g_protein * (0.11 / leucine_fraction_of_protein)`.

This is a heuristic. At total daily protein ≥ 1.6 g/kg bodyweight, source differences in hypertrophy outcomes shrink to nil per recent meta-analyses (Lim 2021, Nichele 2022).

## Adding new products

1. Find the Amazon ASIN.
2. Add an entry to `references/nutrition_data.json` with manufacturer label values. Use the leucine fraction guide above if leucine isn't published.
3. Re-run the scrape + rank flow.

ASINs scraped without a nutrition entry are listed in a separate "unknown nutrition" section of the output and excluded from ranking.
