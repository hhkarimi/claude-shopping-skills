---
name: rank-protein-bars
description: Rank protein bars by $/g protein, calorie:protein ratio, and leucine-adjusted cost. Uses live Amazon prices via the amazon-product-data skill. Database covers whey blends, milk-protein blends, plant blends, and real-food bars.
---

# Protein bar ranker

Ranks protein bars by the same three criteria as `rank-protein-powders`: unit cost ($/g protein), calorie:protein ratio, and leucine-adjusted cost.

Math, CLI, and output formatting live in `.claude-plugin/lib/ranking.py`. This skill is curated nutrition data + a thin wrapper.

## When to use

- Choose a protein bar by cost, calorie efficiency, or muscle-building value.
- Compare bar categories (low-sugar/keto, mainstream whey, plant, real-food).

## When NOT to use

- The user wants taste, texture, or subjective reviews.
- The user wants powders or edamame — use the corresponding rank-* skill instead.

## How to use

Search mode (recommended — one command):

```bash
uv run scripts/rank.py --search "protein bar low sugar" \
  --nutrition references/nutrition_data.json
```

Known-ASIN mode (when you've already scraped):

```bash
uv run ../amazon-product-data/scripts/scrape.py B016MEN14O B0FN7MFN37
uv run scripts/rank.py --prices /tmp/amzn/results.json \
  --nutrition references/nutrition_data.json
```

Re-sort with `--sort cal_protein` or `--sort leucine_adjusted`.

## Domain-specific schema notes

Shared schema documented in [CONTRIBUTING.md](../../CONTRIBUTING.md#add-a-product-to-a-rank--skill). A bar counts as one serving (`servings_per_container` = bars per box). Valid `type` values and their approximate leucine fractions:

- `hydrolyzed_whey` — ~11% of protein
- `whey_blend`, `whey_milk_blend`, `milk_protein_whey_blend`, `whey_soy_blend` — ~9–10%
- `whey_collagen_blend` — ~7–8% (collagen has almost no leucine)
- `egg_whole_food`, `peanut_butter_honey` — ~7–8.5%
- `soy_rice_blend`, `pea_almond_blend` — ~8%

Use these to estimate `leucine_per_serving_g` when the label doesn't publish it.
