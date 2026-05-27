# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "playwright>=1.49",
#   "playwright-stealth>=1.0.6",
# ]
# ///
"""Search Amazon and return candidate ASINs for downstream scrape/rank.

Usage:
    uv run search.py "<query>" [--max-results 20] [--out /path/to/dir]
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

# Playwright deps are imported inside search() so --help / arg validation runs
# without requiring the heavy deps.

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
PRICE_RE = re.compile(r"\$([0-9]+(?:\.[0-9]{2})?)")
RATING_RE = re.compile(r"([0-9.]+) out of 5")
# Review counts are integers possibly with thousands commas. Anchored to avoid
# accidentally matching the leading digit of a star rating like "4.5".
REVIEW_COUNT_RE = re.compile(r"^\s*\(?([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\)?\s*$")

WAF_MARKERS = ("AwsWafIntegration", "awsWafCookieDomainList", "challenge-container")


async def parse_card(card) -> dict | None:
    asin = await card.get_attribute("data-asin")
    if not asin or not ASIN_RE.match(asin):
        return None

    title_loc = card.locator("h2 span").first
    title = (
        (await title_loc.text_content() or "").strip()
        if await title_loc.count()
        else ""
    )

    price_text = None
    price_loc = card.locator(".a-price .a-offscreen").first
    if await price_loc.count():
        price_text = (await price_loc.text_content() or "").strip()
    m = PRICE_RE.search(price_text or "")
    price = float(m.group(1)) if m else None

    rating = None
    rating_loc = card.locator('[aria-label*="out of 5 stars"]').first
    if await rating_loc.count():
        aria = await rating_loc.get_attribute("aria-label") or ""
        rm = RATING_RE.search(aria)
        if rm:
            rating = float(rm.group(1))

    # Use only the dedicated count-component selector — broader fallbacks risk
    # capturing the rating's leading digit instead of the count.
    review_count = None
    rc_loc = card.locator(
        '[data-csa-c-content-id="alf-customer-ratings-count-component"]'
    ).first
    if await rc_loc.count():
        rc_text = (await rc_loc.text_content() or "").strip()
        rcm = REVIEW_COUNT_RE.match(rc_text)
        if rcm:
            review_count = int(rcm.group(1).replace(",", ""))

    return {
        "asin": asin,
        "title": title,
        "price_raw": price_text or "",
        "price": price,
        "rating": rating,
        "review_count": review_count,
        "url": f"https://www.amazon.com/dp/{asin}",
    }


async def search(query: str, max_results: int, out_dir: Path) -> list[dict]:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.amazon.com/s?k={quote_plus(query)}"
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1400, "height": 2400},
            locale="en-US",
        )
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        results_rendered = True
        try:
            await page.wait_for_selector(
                '[data-component-type="s-search-result"]', timeout=20000
            )
        except PlaywrightTimeoutError:
            results_rendered = False

        await page.wait_for_timeout(2500)

        # Save artifacts even on failure so the user can diagnose.
        await page.screenshot(path=str(out_dir / "search.png"), full_page=False)
        html = await page.content()
        (out_dir / "search.html").write_text(html, encoding="utf-8")

        # Detect AWS WAF / bot challenge — distinguishes "0 results" from "blocked".
        if not results_rendered and any(marker in html for marker in WAF_MARKERS):
            print(
                "ERROR: AWS WAF bot challenge detected. The stealth shim may need "
                "an update — see search.html for the challenge page.",
                file=sys.stderr,
            )
            await browser.close()
            sys.exit(2)

        if not results_rendered:
            print(
                "WARN: Search results selector did not render within timeout. "
                "Check search.html — could be empty results or a layout change.",
                file=sys.stderr,
            )

        cards = await page.locator('[data-component-type="s-search-result"]').all()
        results: list[dict] = []
        for card in cards:
            parsed = await parse_card(card)
            if parsed:
                results.append(parsed)
            if len(results) >= max_results:
                break

        await browser.close()

    (out_dir / "search_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    return results


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Search Amazon for products matching a query."
    )
    ap.add_argument("query", help="Search query (e.g. 'whey protein isolate 5 lb').")
    ap.add_argument(
        "--max-results",
        type=int,
        default=20,
        help="Cap returned results (default: 20).",
    )
    ap.add_argument(
        "--out", default="/tmp/amzn", help="Output directory (default: /tmp/amzn)."
    )
    args = ap.parse_args()

    results = asyncio.run(search(args.query, args.max_results, Path(args.out)))
    print(json.dumps(results, indent=2))
    print(
        f"\n{len(results)} results saved to {args.out}/search_results.json",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
