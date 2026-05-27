---
name: amazon-product-data
description: Search Amazon for products and scrape live product pages (title, price, rating, raw HTML, screenshot). Two scripts — `search.py` finds candidate ASINs from a query, `scrape.py` pulls full product detail for known ASINs. Uses Playwright + stealth to bypass Amazon's AWS WAF bot challenge.
---

# Amazon product data scraper

Two complementary scripts for Amazon data:

- **`search.py`** — given a query, returns a list of candidate ASINs with title, price, rating, and review count from the search results page.
- **`scrape.py`** — given known ASINs, fetches full product detail pages and extracts title + price.

Together they support a "discover → confirm → rank" workflow.

## When to use

- The user wants current Amazon prices for one or more specific ASINs.
- The user wants to compare multiple Amazon products and needs live data.
- A previous Amazon-related task failed because WebFetch returned an AWS WAF challenge page or a price-less DOM stub.

## When NOT to use

- The user only wants a single quick price check — recommend manual lookup first.
- The user wants nutrition facts that Amazon displays as an image — this skill returns text/HTML only.
- Bulk scraping (>~50 products) — Amazon rate-limits aggressively; suggest the official Product Advertising API.

## How to use

Both scripts are PEP 723 inline-deps Python — run with `uv run`. Default output dir is `/tmp/amzn/`.

### Search

```bash
uv run scripts/search.py "<query>" [--max-results 20] [--out /path/to/dir]
```

Writes:
- `search_results.json` — list of `{asin, url, title, price_raw, price, rating, review_count}` objects (one per result card)
- `search.png` — screenshot of the results page
- `search.html` — full rendered HTML

Example:
```bash
uv run scripts/search.py "pea protein 5 lb" --max-results 10
```

### Scrape (for known ASINs)

```bash
uv run scripts/scrape.py <ASIN1> <ASIN2> ... [--out /path/to/dir] [--zip <code>]
```

Each ASIN is a 10-character Amazon product identifier (e.g. `B000MAK59O`).

Writes:
- `results.json` — list of `{asin, url, title, price_raw, price, fresh_available, fresh_price, html_bytes, ok}` objects
- `<asin>.png` — viewport screenshot per product
- `<asin>.html` — full rendered HTML per product

Example:
```bash
uv run scripts/scrape.py B000MAK59O B01HOPJAAE B002TG3QPO
```

#### Amazon Fresh availability (`--zip`)

When you pass `--zip <5-digit ZIP>`, the scraper sets the Amazon delivery
location at the start of the session and checks every product page for an
Amazon Fresh badge. Results gain:

- `fresh_available: bool` — whether the product is purchasable on Amazon Fresh
  at that ZIP
- `fresh_price: float | null` — the Fresh-specific price if it differs from
  the regular price

Without `--zip`, both fields are always `false`/`null`. Amazon Fresh is
geographically limited; a ZIP outside any Fresh delivery zone will return
`fresh_available: false` for every product.

```bash
uv run scripts/scrape.py B016MEN14O B0FN7MFN37 --zip 02139
```

### Typical pipeline

```bash
# 1. Discover candidates
uv run scripts/search.py "whey protein isolate 5 lb" --max-results 20

# 2. Inspect search_results.json, pick promising ASINs

# 3. Pull full detail (price, rendered HTML for nutrition extraction, etc.)
uv run scripts/scrape.py B000... B01...
```

## Requirements

- `uv` (Astral's Python project manager): `brew install uv`
- First run installs Playwright + a Chromium build (~150 MB), then completes in ~5 s per ASIN.

## Troubleshooting

- **All prices come back null** — Amazon updated its DOM. Edit the selector fallback list in `scrape.py` (`PRICE_SELECTORS`).
- **`search.py` returns empty** — Amazon's search-result card markup changed. Update the `[data-component-type="s-search-result"]` selector and field selectors in `parse_card`.
- **Chromium not found** — run `uv run --with playwright playwright install chromium`.
- **AWS WAF challenge page returned** — the stealth shim may have broken. Bump `playwright-stealth` in the PEP 723 header of the affected script.
