# claude-shopping-skills

Claude Code plugin for comparing Amazon products by unit cost and per-spec metrics.

## Skills

| Skill | Purpose |
|---|---|
| `amazon-product-data` | Search Amazon (`search.py`) and scrape product pages (`scrape.py`). Uses stealth-enabled headless Chromium to bypass AWS WAF bot challenges. |
| `rank-protein-powders` | Rank protein powders by $/g protein, calorie:protein ratio, and leucine-adjusted cost. 12-product database. |
| `rank-protein-bars` | Rank protein bars by the same criteria. 12-product database. |
| `rank-dry-edamame` | Rank dry-roasted edamame snacks by the same criteria. 8-product database. |

All ranking skills share `.claude-plugin/lib/ranking.py` — the math, schema, and CLI live there once. Each skill is just curated data + a thin wrapper.

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

End-to-end rank in one command (works for any `rank-*` skill):

```bash
uv run skills/rank-protein-powders/scripts/rank.py \
  --search "whey protein isolate 5 lb" \
  --nutrition skills/rank-protein-powders/references/nutrition_data.json
```

Or scrape arbitrary ASINs directly:

```bash
uv run skills/amazon-product-data/scripts/scrape.py B000MAK59O B01HOPJAAE
```

See each skill's `SKILL.md` for the full command set.

## How the scraper works

Amazon blocks plain HTTP scraping with an AWS WAF JavaScript challenge that headless Chrome bails on. This plugin uses `playwright-stealth` to mask the standard headless fingerprint tells (WebDriver navigator props, missing Chrome runtime features), letting WAF pass on a residential IP.

Scripts use PEP 723 inline metadata so `uv run` creates an ephemeral venv per invocation. No global Python pollution, no leftover `.venv` directory.

## Repo layout

```
.claude-plugin/
  plugin.json
  lib/ranking.py            # shared rank math, schema, CLI
skills/
  amazon-product-data/      # search.py + scrape.py (stealth Playwright)
  rank-protein-powders/     # nutrition data + thin rank.py wrapper
  rank-protein-bars/        # nutrition data + thin rank.py wrapper
  rank-dry-edamame/         # nutrition data + thin rank.py wrapper
tests/                      # pytest suite (lint, schema validation, CLI smoke tests)
```

The shared module lives under `.claude-plugin/` so it ships alongside `plugin.json` (the only directory guaranteed to be present in a marketplace install).

## Releases

Versioning is driven by [release-please](https://github.com/googleapis/release-please) on every merge to main. Use [Conventional Commits](https://www.conventionalcommits.org/) in PR titles (e.g. `feat: ...`, `fix: ...`) and release-please opens a versioned PR with a CHANGELOG entry whenever there's something to ship.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch protection rules, conventional-commit conventions, the schema for adding products, and local dev commands.

## License

MIT
