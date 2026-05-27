---
name: rank-dry-edamame
description: Rank dry-roasted edamame snacks by $/g protein, calorie:protein ratio, and leucine-adjusted cost. Uses live Amazon prices via the amazon-product-data skill. Covers bulk jars, multi-bag packs, and single-serve snack packs.
---

# Dry-roasted edamame ranker

Ranks dry-roasted edamame products by the same three criteria as the other `rank-*` skills: unit cost ($/g protein), calorie:protein ratio, and leucine-adjusted cost.

Math, CLI, and output formatting live in `.claude-plugin/lib/ranking.py`. This skill is curated nutrition data + a thin wrapper.

## When to use

- Choose a dry-roasted edamame product by cost, calorie efficiency, or muscle-building value.
- Compare bulk jars vs single-serve snack packs.

## When NOT to use

- The user wants taste reviews or flavored variants beyond what the database covers.
- The user wants frozen or in-pod edamame — this skill covers shelf-stable dry-roasted only.
- The user wants powders or bars — use the corresponding rank-* skill instead.

## How to use

Search mode (recommended — one command):

```bash
uv run scripts/rank.py --search "dry roasted edamame bulk" \
  --nutrition references/nutrition_data.json
```

Known-ASIN mode (when you've already scraped):

```bash
uv run ../amazon-product-data/scripts/scrape.py B0094IXKME B09FFXR2VV
uv run scripts/rank.py --prices /tmp/amzn/results.json \
  --nutrition references/nutrition_data.json
```

Re-sort with `--sort cal_protein` or `--sort leucine_adjusted`.

## Domain-specific schema notes

Shared schema documented in [CONTRIBUTING.md](../../CONTRIBUTING.md#add-a-product-to-a-rank--skill). Only one `type` value here:

- `edamame` — whole soybean, ~8% leucine fraction (same as soy isolate)

A 1 oz (28 g) serving of dry-roasted edamame typically delivers 13–14 g protein at ~130 calories. Bulk jars list servings explicitly; multi-bag products list one bag as the serving — count accordingly.
