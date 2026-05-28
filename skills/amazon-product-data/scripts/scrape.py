# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "playwright>=1.49",
#   "playwright-stealth>=1.0.6",
# ]
# ///
"""Scrape Amazon product data (title, price, HTML, screenshot) for given ASINs.

Usage:
    uv run scrape.py <ASIN1> <ASIN2> ... [--out /path/to/dir] [--zip <code>]

When --zip is provided, the scraper sets the Amazon delivery location to that
ZIP code at the start of the session and annotates each product with
`fresh_available` and `fresh_price`. Fresh availability is region-gated, so
products outside a Fresh delivery area will always come back as
`fresh_available: false` regardless of the ASIN.
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Playwright deps are imported inside main() so `--help` and arg validation
# don't require the heavy deps to be installed — useful for fast CLI tests.

# Add this script's directory to sys.path so `_lib` resolves even when this
# script is imported as a module rather than executed directly via uv run.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import ZIP_RE, navigate_with_retry, set_delivery_zip  # noqa: E402

# Note: scrape_one's generic `except Exception` catches _lib's ThrottleExhausted
# (RuntimeError subclass), so we don't import it explicitly here — its message
# lands in result["error"] just like any other navigation failure.

PRICE_RE = re.compile(r"\$([0-9]+(?:\.[0-9]{2})?)")

PRICE_SELECTORS = [
    # Most specific: Amazon's modern "Apex" main-product-price element.
    # Excludes per-unit prices like "$2.04 / count" which live in a sibling
    # element with class apex-priceperunit-value.
    ".apex-pricetopay-value .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price.aok-align-center .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
    "#corePrice_feature_div .a-price .a-offscreen",
    "#apex_desktop .a-price .a-offscreen",
    ".a-price .a-offscreen",
    "#priceblock_ourprice",
    "#priceblock_saleprice",
]

# Indicators that a product is on Amazon Fresh. Amazon ships these in a few
# layouts depending on category and region — match on any.
FRESH_INDICATORS = [
    "#amazon-fresh-buybox",
    "[data-feature-name='freshBuyBox']",
    "a[href*='/fresh/']",
    "img[alt*='Amazon Fresh']",
]

# Element that holds the Fresh-specific price, separate from the standard price.
FRESH_PRICE_SELECTORS = [
    "#amazon-fresh-buybox .a-price .a-offscreen",
    "[data-feature-name='freshBuyBox'] .a-price .a-offscreen",
]


async def _detect_fresh(page) -> tuple[bool, float | None]:
    """Return (fresh_available, fresh_price) for the current product page."""
    for sel in FRESH_INDICATORS:
        if await page.locator(sel).count():
            fresh_price = None
            for psel in FRESH_PRICE_SELECTORS:
                loc = page.locator(psel)
                if await loc.count():
                    text = (await loc.first.text_content()) or ""
                    m = PRICE_RE.search(text)
                    if m:
                        fresh_price = float(m.group(1))
                        break
            return True, fresh_price
    return False, None


async def scrape_one(context, asin: str, out_dir: Path, with_fresh: bool) -> dict:
    url = f"https://www.amazon.com/dp/{asin}"
    page = await context.new_page()
    result: dict = {
        "asin": asin,
        "url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    try:
        await navigate_with_retry(page, url)
        try:
            await page.wait_for_selector("#productTitle", timeout=20000)
        except Exception:
            pass
        await page.wait_for_timeout(2500)

        title_loc = page.locator("#productTitle")
        if await title_loc.count():
            result["title"] = ((await title_loc.first.text_content()) or "").strip()
        else:
            result["title"] = ""

        # Walk PRICE_SELECTORS in priority order; for each, iterate ALL matches
        # and pick the first price >= $1. Sub-$1 hits are almost always
        # per-unit displays like "$0.22 / ounce", not the product price.
        price_text = None
        price_val: float | None = None
        any_candidate_seen = False
        for sel in PRICE_SELECTORS:
            loc = page.locator(sel)
            n = await loc.count()
            for i in range(n):
                text = (await loc.nth(i).text_content()) or ""
                if "$" not in text:
                    continue
                m = PRICE_RE.search(text)
                if not m:
                    continue
                any_candidate_seen = True
                val = float(m.group(1))
                if val < 1.0:
                    continue  # skip per-unit prices
                price_text = text
                price_val = val
                break
            if price_val is not None:
                break
        if price_val is None and any_candidate_seen:
            print(
                f"WARN: {asin}: all price candidates were sub-$1 (likely "
                f"per-unit displays). Returning price=None. Check the HTML "
                f"artifact and consider adding a more specific selector.",
                file=sys.stderr,
            )
        result["price_raw"] = (price_text or "").strip()
        result["price"] = price_val

        if with_fresh:
            fresh_available, fresh_price = await _detect_fresh(page)
            result["fresh_available"] = fresh_available
            result["fresh_price"] = fresh_price
        else:
            result["fresh_available"] = False
            result["fresh_price"] = None

        await page.screenshot(path=str(out_dir / f"{asin}.png"), full_page=False)
        html = await page.content()
        (out_dir / f"{asin}.html").write_text(html)
        result["html_bytes"] = len(html)
        result["ok"] = result["price"] is not None
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["ok"] = False
    finally:
        await page.close()
    return result


async def main(asins: list[str], out_dir: Path, zip_code: str | None) -> None:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    out_dir.mkdir(parents=True, exist_ok=True)
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1400, "height": 2200},
            locale="en-US",
        )

        with_fresh = False
        if zip_code:
            print(f"Setting delivery ZIP to {zip_code}...", file=sys.stderr, flush=True)
            setup_page = await context.new_page()
            with_fresh = await set_delivery_zip(setup_page, zip_code)
            await setup_page.close()
            if with_fresh:
                print(
                    "  ZIP set; will check Fresh availability per product.",
                    file=sys.stderr,
                )
            else:
                print(
                    "  ZIP setup did not complete; Fresh data will be omitted.",
                    file=sys.stderr,
                )

        results = []
        for asin in asins:
            print(f"--> {asin}", file=sys.stderr, flush=True)
            r = await scrape_one(context, asin, out_dir, with_fresh)
            print(
                f"    price={r.get('price')} ok={r.get('ok')} "
                f"fresh={r.get('fresh_available')}",
                file=sys.stderr,
                flush=True,
            )
            results.append(r)
        await browser.close()
        (out_dir / "results.json").write_text(json.dumps(results, indent=2))
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Scrape Amazon product data for given ASINs."
    )
    ap.add_argument("asins", nargs="+", help="One or more ASINs (e.g. B000MAK59O).")
    ap.add_argument(
        "--out", default="/tmp/amzn", help="Output directory (default: /tmp/amzn)."
    )
    ap.add_argument(
        "--zip",
        dest="zip_code",
        default=None,
        help="US ZIP code (5 digits). When set, the scraper configures the "
        "Amazon delivery location and reports fresh_available + fresh_price "
        "per product. Without --zip, those fields are always false/null.",
    )
    args = ap.parse_args()

    if args.zip_code is not None and not ZIP_RE.match(args.zip_code):
        ap.error(f"--zip must be a 5-digit US ZIP code (got {args.zip_code!r})")

    asyncio.run(main(args.asins, Path(args.out), args.zip_code))
