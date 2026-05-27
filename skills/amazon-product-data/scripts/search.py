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
                               [--zip <code>] [--include-fresh]

When --zip is given, the scraper sets Amazon's delivery location to that ZIP
before searching. When --include-fresh is also given, a second search runs
against the Amazon Fresh storefront filter (i=amazonfresh) and Fresh-eligible
ASINs are merged into the result set, each tagged with `source: "fresh"`.
Regular search results are tagged `source: "regular"`.
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

# Add this script's directory to sys.path so `_lib` resolves even when this
# script is imported as a module rather than executed directly via uv run.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import (  # noqa: E402
    ZIP_RE,
    ThrottleExhausted,
    navigate_with_retry,
    set_delivery_zip,
)

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


async def _run_one_search(page, label: str, url: str, max_results: int) -> list[dict]:
    """Run a single search against the given URL and return parsed cards."""
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    try:
        await navigate_with_retry(page, url)
    except ThrottleExhausted as e:
        print(
            f"WARN: {label} search hit Amazon throttle ({e}). "
            "Returning empty results; artifacts saved for diagnosis.",
            file=sys.stderr,
        )
        return []

    results_rendered = True
    try:
        await page.wait_for_selector(
            '[data-component-type="s-search-result"]', timeout=20000
        )
    except PlaywrightTimeoutError:
        results_rendered = False

    await page.wait_for_timeout(2500)

    if not results_rendered:
        html = await page.content()
        if any(marker in html for marker in WAF_MARKERS):
            print(
                f"ERROR: AWS WAF bot challenge during {label} search. "
                "Stealth shim may need an update.",
                file=sys.stderr,
            )
            sys.exit(2)
        print(
            f"WARN: {label} search results selector did not render. "
            "Could be empty results or a layout change.",
            file=sys.stderr,
        )

    cards = await page.locator('[data-component-type="s-search-result"]').all()
    results: list[dict] = []
    for card in cards:
        parsed = await parse_card(card)
        if parsed:
            parsed["source"] = label
            results.append(parsed)
        if len(results) >= max_results:
            break
    return results


async def search(
    query: str,
    max_results: int,
    out_dir: Path,
    *,
    zip_code: str | None = None,
    include_fresh: bool = False,
) -> list[dict]:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    out_dir.mkdir(parents=True, exist_ok=True)
    regular_url = f"https://www.amazon.com/s?k={quote_plus(query)}"
    fresh_url = f"https://www.amazon.com/s?k={quote_plus(query)}&i=amazonfresh"

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

        if zip_code:
            print(f"Setting delivery ZIP to {zip_code}...", file=sys.stderr, flush=True)
            ok = await set_delivery_zip(page, zip_code)
            if not ok:
                print(
                    "  ZIP setup did not complete; Fresh search will be skipped "
                    "even if --include-fresh was passed.",
                    file=sys.stderr,
                )
                include_fresh = False

        print(f"Searching regular Amazon for: {query!r}", file=sys.stderr, flush=True)
        regular = await _run_one_search(page, "regular", regular_url, max_results)
        await page.screenshot(path=str(out_dir / "search.png"), full_page=False)
        html = await page.content()
        (out_dir / "search.html").write_text(html, encoding="utf-8")

        fresh: list[dict] = []
        if include_fresh:
            print(f"Searching Amazon Fresh for: {query!r}", file=sys.stderr, flush=True)
            fresh = await _run_one_search(page, "fresh", fresh_url, max_results)
            await page.screenshot(
                path=str(out_dir / "search_fresh.png"), full_page=False
            )
            fresh_html = await page.content()
            (out_dir / "search_fresh.html").write_text(fresh_html, encoding="utf-8")

        await browser.close()

    # Combine; downstream dedupe by ASIN keeps Fresh entries distinct only when
    # they have a different ASIN. Same-ASIN duplicates are deduped at the
    # filter step in lib/ranking.py.
    results = regular + fresh
    (out_dir / "search_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(
        f"Regular: {len(regular)} | Fresh: {len(fresh)} | Total: {len(results)}",
        file=sys.stderr,
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
        help="Cap returned results PER source (default: 20).",
    )
    ap.add_argument(
        "--out", default="/tmp/amzn", help="Output directory (default: /tmp/amzn)."
    )
    ap.add_argument(
        "--zip",
        dest="zip_code",
        default=None,
        help="US ZIP code (5 digits). Sets the Amazon delivery location for "
        "this search session. Required if you want --include-fresh to return "
        "anything.",
    )
    ap.add_argument(
        "--include-fresh",
        action="store_true",
        help="In addition to the regular search, query the Amazon Fresh "
        "storefront (i=amazonfresh) and merge results. Requires --zip. Each "
        'result is tagged with `source: "regular"` or `source: "fresh"`.',
    )
    args = ap.parse_args()

    if args.zip_code is not None and not ZIP_RE.match(args.zip_code):
        ap.error(f"--zip must be a 5-digit US ZIP code (got {args.zip_code!r})")
    if args.include_fresh and args.zip_code is None:
        ap.error(
            "--include-fresh requires --zip (Fresh search needs a delivery location)"
        )

    results = asyncio.run(
        search(
            args.query,
            args.max_results,
            Path(args.out),
            zip_code=args.zip_code,
            include_fresh=args.include_fresh,
        )
    )
    print(json.dumps(results, indent=2))
    print(
        f"\n{len(results)} results saved to {args.out}/search_results.json",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
