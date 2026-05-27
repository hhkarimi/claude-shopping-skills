# claude-shopping-skills

Claude Code plugin for comparing Amazon products by unit cost and per-spec metrics. Currently focused on protein-rich foods — rank protein powders, bars, edamame, and Greek yogurt by $/g protein, with Amazon Fresh and regular Amazon prices in one table.

## Skills

| Skill | Purpose |
|---|---|
| `amazon-product-data` | Search Amazon (`search.py`) and scrape product pages (`scrape.py`). Uses stealth-enabled headless Chromium to bypass AWS WAF bot challenges. Supports an Amazon Fresh storefront search via `--zip` + `--include-fresh`. |
| `rank-protein-powders` | Rank protein powders by $/g protein, calorie:protein, leucine-adjusted cost. 12-product DB (whey, pea, soy, egg, blends). |
| `rank-protein-bars` | Same criteria, 14-product DB (whey blends, milk-protein, plant blends, real-food, plus a cross-channel pair). |
| `rank-dry-edamame` | Same criteria, 8-product DB (bulk jars, multi-bag, single-serve packs). |
| `rank-greek-yogurt` | Same criteria, 10-product DB (plain/flavored × nonfat/lowfat/whole-milk). |

All ranking skills share `.claude-plugin/lib/ranking.py` — the math, schema, CLI, and table renderer live there once. Each skill is just curated data + a thin wrapper.

## Install

```
/plugin marketplace add hhkarimi/claude-shopping-skills
/plugin install shopping-skills@hhkarimi/claude-shopping-skills
```

Or clone the repo and reference locally.

## Requirements

- `uv` ([install](https://docs.astral.sh/uv/)): `brew install uv`
- macOS or Linux. First scraper run downloads a ~150 MB Chromium build into the uv-managed cache.

## Quick start

End-to-end rank — search Amazon, scrape live prices (including Amazon Fresh availability when a ZIP is set), produce a sorted markdown table:

```bash
uv run skills/rank-greek-yogurt/scripts/rank.py \
  --search "greek yogurt" --zip 78752 \
  --nutrition skills/rank-greek-yogurt/references/nutrition_data.json
```

Output looks like this (from the committed test fixture, abbreviated for width):

```
| Product | Channel | Price | $/g protein | % Δ vs prev | Cal:protein | Buy |
|---|:---:|---:|---:|---:|---:|:---:|
| 365 Greek Yogurt, Plain Nonfat, 32 oz | regular | $4.99 | $0.0734 | — | 5.88 | [link] |
| FAGE Total 0% Plain, 32 oz | regular | $6.96 | $0.0773 | +5.3% | 5.00 | [link] |
| Chobani Non-Fat Plain, 32 oz | regular | $5.37 | $0.0790 | +2.2% | 5.88 | [link] |
| The Greek Gods Honey Vanilla, 24 oz | regular | $3.88 | $0.2156 | +172.9% | 33.33 | [link] |
```

Read the `% Δ vs prev` column to spot price gradients — the top three are nearly tied (within 5% on $/g) while rank 4 (the high-sugar dessert yogurt) is 2.7× the price-per-gram of the value pick.

With `--zip` set, the **Channel** column distinguishes Amazon Fresh listings from regular Amazon. Yogurt at Fresh-served ZIPs typically shows most products as `fresh`; supplements like protein powder almost always show `regular` (Fresh doesn't stock them).

### Cross-channel comparison

Some products are sold under different ASINs on regular Amazon and Amazon Fresh. Adding both ASINs to a skill's `nutrition_data.json` puts them in the same ranking. Example from `rank-protein-bars` — the think! Brownie Crunch product is listed two ways:

```
| Product | Channel | Pack | Price | $/g protein |
|---|:---:|---:|---:|---:|
| think! Brownie Crunch, 12 ct | regular | 12 bars | $17.99 | $0.0750 |
| think! Brownie Crunch, 10 ct (Amazon Fresh) | fresh  | 10 bars | $16.09 | $0.0804 |
```

Same product, different SKUs. The Fresh sticker is cheaper but the smaller pack means a higher per-gram cost. The Channel column makes this visible at a glance.

### Search-only or scrape-only

```bash
# Search Amazon (regular + Fresh storefront), no ranking:
uv run skills/amazon-product-data/scripts/search.py "pea protein 5 lb" \
  --max-results 20 --zip 02139 --include-fresh

# Scrape known ASINs directly:
uv run skills/amazon-product-data/scripts/scrape.py B000MAK59O B01HOPJAAE --zip 02139
```

See each skill's `SKILL.md` for the full command set + domain-specific schema.

## How the scraper works

Amazon blocks plain HTTP scraping with an AWS WAF JavaScript challenge that headless Chrome bails on. This plugin uses `playwright-stealth` to mask the standard headless fingerprint tells (WebDriver navigator props, missing Chrome runtime features), letting WAF pass on a residential IP. A separate retry layer detects Amazon's "Dogs of Amazon" 503 throttle page and backs off exponentially.

Scripts use PEP 723 inline metadata so `uv run` creates an ephemeral venv per invocation. No global Python pollution, no leftover `.venv` directory.

## Repo layout

```
.claude-plugin/
  plugin.json
  lib/ranking.py            # shared rank math, schema, CLI, table renderer
skills/
  amazon-product-data/
    scripts/search.py       # search Amazon + Fresh storefront (stealth Playwright)
    scripts/scrape.py       # scrape product pages + Fresh detection
    scripts/_lib.py         # shared throttle-retry and ZIP-setting helpers
  rank-protein-powders/     # nutrition data + thin rank.py wrapper
  rank-protein-bars/        # nutrition data + thin rank.py wrapper
  rank-dry-edamame/         # nutrition data + thin rank.py wrapper
  rank-greek-yogurt/        # nutrition data + thin rank.py wrapper
tests/                      # pytest suite (lint, schema validation, CLI smoke tests)
```

The shared module lives under `.claude-plugin/` so it ships alongside `plugin.json` (the only directory guaranteed to be present in a marketplace install).

## Releases

Versioning is driven by [release-please](https://github.com/googleapis/release-please) on every merge to main. Use [Conventional Commits](https://www.conventionalcommits.org/) in PR titles (e.g. `feat: ...`, `fix: ...`) and release-please opens a versioned release PR with a CHANGELOG entry whenever there's something to ship. See [CHANGELOG.md](CHANGELOG.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch-protection rules, conventional-commit conventions, the nutrition-data schema, and local dev commands.

## License

MIT
