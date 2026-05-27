# claude-shopping-skills

Claude Code plugin for comparing products on Amazon by unit cost and per-spec metrics.

Ships two skills:

| Skill | Purpose |
|---|---|
| `amazon-product-data` | Search Amazon for products and scrape live product pages (title, price, rating, raw HTML, screenshot). Two scripts: `search.py` for discovering ASINs from a query, `scrape.py` for full product detail. Uses stealth-enabled headless Chromium to bypass AWS WAF bot challenges. |
| `rank-protein-powders` | Rank protein powders by $/g protein, calorie:protein ratio, and leucine-adjusted cost. Ships with a 12-product curated nutrition database. |
| `rank-protein-bars` | Rank protein bars by the same three criteria. Ships with a 12-product curated nutrition database. |

## Install

In Claude Code:

```
/plugin marketplace add hhkarimi/claude-shopping-skills
/plugin install shopping-skills@hhkarimi/claude-shopping-skills
```

Or clone manually and reference locally.

## Requirements

- `uv` (Astral's Python project manager): `brew install uv`
- macOS or Linux. First run of the scraper downloads a ~150 MB Chromium build into the uv-managed cache.

## Quick start

### Rank the default set of protein powders

```bash
cd skills/rank-protein-powders
ASINS=$(jq -r 'keys[]' references/nutrition_data.json | tr '\n' ' ')
uv run ../amazon-product-data/scripts/scrape.py $ASINS
uv run scripts/rank.py --prices /tmp/amzn/results.json --nutrition references/nutrition_data.json
```

### Discover new candidates from a search query

```bash
uv run skills/amazon-product-data/scripts/search.py "pea protein 5 lb" --max-results 20
cat /tmp/amzn/search_results.json
```

### Scrape arbitrary Amazon products

```bash
uv run skills/amazon-product-data/scripts/scrape.py B000MAK59O B01HOPJAAE
cat /tmp/amzn/results.json
```

### Full pipeline (search → scrape → rank)

```bash
# 1. Find candidates
uv run skills/amazon-product-data/scripts/search.py "whey protein isolate" --max-results 20

# 2. Pick promising ASINs, add nutrition data to nutrition_data.json if missing,
#    then scrape full detail
uv run skills/amazon-product-data/scripts/scrape.py B00... B01...

# 3. Rank
uv run skills/rank-protein-powders/scripts/rank.py \
  --prices /tmp/amzn/results.json \
  --nutrition skills/rank-protein-powders/references/nutrition_data.json
```

## How it works

Amazon blocks plain HTTP scraping with an AWS WAF JavaScript challenge that headless Chrome bails on. This plugin uses `playwright-stealth` to mask the standard headless fingerprint tells (WebDriver navigator props, missing Chrome runtime features), letting WAF pass on a residential IP.

The scraper is a PEP 723 inline-deps Python script — running it with `uv run` creates an ephemeral venv, installs Playwright + stealth, and executes the script. No global Python pollution, no leftover `.venv` directory.

## Repo layout

```
.claude-plugin/
  plugin.json
  lib/ranking.py            # shared ranker logic (compute_row, format_table, CLI entry)
skills/
  amazon-product-data/      # search.py + scrape.py (stealth Playwright)
  rank-protein-powders/     # nutrition data + thin rank.py wrapper
  rank-protein-bars/        # nutrition data + thin rank.py wrapper
tests/                      # pytest suite (lint, schema validation, CLI smoke tests)
```

The shared module lives under `.claude-plugin/` so it ships with the plugin alongside `plugin.json` (the only directory guaranteed-included in a marketplace install).

The shared `lib/ranking.py` lets new comparison domains add just a `SKILL.md`, a `nutrition_data.json`, and a tiny `rank.py` wrapper without duplicating math.

## Adding products to the protein ranker

Edit `skills/rank-protein-powders/references/nutrition_data.json`:

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

Leucine fractions if the label doesn't publish: whey isolate 11%, whey concentrate 10%, egg 8.5%, soy/pea/blends 8%.

## Development

Run the same checks CI runs:

```bash
uvx ruff check .                           # lint
uvx ruff format --check .                  # formatting
python3 tests/validate_skills.py           # SKILL.md frontmatter
uvx --with pytest pytest tests -v          # unit + CLI tests
```

## License

MIT
