---
name: rank-protein-powders
description: Rank protein powders by $/g protein, calorie:protein ratio, and leucine-adjusted cost. Uses live Amazon prices via the amazon-product-data skill. Database covers whey, pea, soy, egg, and plant blends.
---

# Protein powder ranker

Ranks protein powders by unit cost ($/g protein), calorie:protein ratio, and leucine-adjusted cost (a muscle-building heuristic that normalizes plant proteins to whey-equivalent leucine).

Math, CLI, and output formatting live in `.claude-plugin/lib/ranking.py`. This skill is curated nutrition data + a thin wrapper.

## When to use

- Choose a protein powder by cost, calorie efficiency, or muscle-building value.
- Compare brands or protein sources (whey vs pea vs soy vs blends).

## When NOT to use

- The user wants taste, mixability, or subjective reviews.
- The user wants bars or edamame — use `rank-protein-bars` or `rank-dry-edamame`.

## How to use

Search mode (recommended — one command):

```bash
uv run scripts/rank.py --search "whey protein isolate 5 lb" \
  --nutrition references/nutrition_data.json
```

Known-ASIN mode (when you've already scraped):

```bash
uv run ../amazon-product-data/scripts/scrape.py B000MAK59O B01HOPJAAE
uv run scripts/rank.py --prices /tmp/amzn/results.json \
  --nutrition references/nutrition_data.json
```

Re-sort with `--sort cal_protein` or `--sort leucine_adjusted`.

### Amazon Fresh comparisons (optional)

If the user asks about Amazon Fresh availability or prices, **ask them for a 5-digit US ZIP code first**, then pass it via `--zip`:

```bash
uv run scripts/rank.py --search "whey protein isolate" --zip 02139 \
  --nutrition references/nutrition_data.json
```

The scraper sets Amazon's delivery location to that ZIP and records `fresh_available` + `fresh_price` per product in `results.json`. Note: protein powders are supplements and rarely Fresh-eligible — most results will show `fresh_available: false` even with a valid ZIP. Fresh data is most useful for refrigerated / grocery-style products.

## Domain-specific schema notes

Shared schema documented in [CONTRIBUTING.md](../../CONTRIBUTING.md#add-a-product-to-a-rank--skill). Valid `type` values for this skill and their approximate leucine fractions:

- `whey_isolate` — ~11% of protein
- `whey_concentrate`, `whey_blend` — ~10%
- `egg` — ~8.5%
- `soy`, `pea`, `pea_rice_blend` — ~8%

Use these to estimate `leucine_per_serving_g` when the manufacturer doesn't publish it.
