---
name: amazon-product-data
description: Scrape live Amazon product data (title, price, raw HTML, screenshot) for a list of ASINs using a stealth-enabled headless browser. Use when you need current Amazon pricing or product details for comparison shopping. Bypasses Amazon's AWS WAF bot challenge via Playwright + playwright-stealth.
---

# Amazon product data scraper

Fetch current price + product title + raw page HTML from Amazon product pages, bypassing Amazon's bot challenge.

## When to use

- The user wants current Amazon prices for one or more specific ASINs.
- The user wants to compare multiple Amazon products and needs live data.
- A previous Amazon-related task failed because WebFetch returned an AWS WAF challenge page or a price-less DOM stub.

## When NOT to use

- The user only wants a single quick price check — recommend manual lookup first.
- The user wants nutrition facts that Amazon displays as an image — this skill returns text/HTML only.
- Bulk scraping (>~50 products) — Amazon rate-limits aggressively; suggest the official Product Advertising API.

## How to use

The scraper is `scripts/scrape.py`, a PEP 723 inline-deps Python script. Invoke with `uv run`:

```bash
uv run scripts/scrape.py <ASIN1> <ASIN2> ... [--out /path/to/dir]
```

Each ASIN is a 10-character Amazon product identifier (e.g. `B000MAK59O`). Default output directory is `/tmp/amzn/`.

### Output

Writes to the output directory:
- `results.json` — list of `{asin, url, title, price_raw, price, html_bytes, ok}` objects
- `<asin>.png` — viewport screenshot of each product page
- `<asin>.html` — full rendered HTML

Also prints `results.json` to stdout for piping.

### Example

```bash
uv run scripts/scrape.py B000MAK59O B01HOPJAAE B002TG3QPO
```

## Requirements

- `uv` (Astral's Python project manager): `brew install uv`
- First run installs Playwright + a Chromium build (~150 MB), then completes in ~5 s per ASIN.

## Troubleshooting

- **All prices come back null** — Amazon updated its DOM. Edit the selector fallback list in `scrape.py` (`for sel in [...]`).
- **Chromium not found** — run `uv run --with playwright playwright install chromium`.
- **AWS WAF challenge page returned** — the stealth shim may have broken. Bump `playwright-stealth` in the PEP 723 header.
