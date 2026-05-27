# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "playwright>=1.49",
#   "playwright-stealth>=1.0.6",
# ]
# ///
"""Scrape Amazon product data (title, price, HTML, screenshot) for given ASINs.

Usage:
    uv run scrape.py <ASIN1> <ASIN2> ... [--out /path/to/dir]
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

PRICE_RE = re.compile(r"\$([0-9]+(?:\.[0-9]{2})?)")

PRICE_SELECTORS = [
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
    "#corePrice_feature_div .a-price .a-offscreen",
    "#apex_desktop .a-price .a-offscreen",
    ".a-price .a-offscreen",
    "#priceblock_ourprice",
    "#priceblock_saleprice",
]


async def scrape_one(context, asin: str, out_dir: Path) -> dict:
    url = f"https://www.amazon.com/dp/{asin}"
    page = await context.new_page()
    result = {"asin": asin, "url": url}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
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

        price_text = None
        for sel in PRICE_SELECTORS:
            loc = page.locator(sel)
            if await loc.count():
                price_text = await loc.first.text_content()
                if price_text and "$" in price_text:
                    break
        result["price_raw"] = (price_text or "").strip()
        m = PRICE_RE.search(price_text or "")
        result["price"] = float(m.group(1)) if m else None

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


async def main(asins: list[str], out_dir: Path) -> None:
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
        results = []
        for asin in asins:
            print(f"--> {asin}", file=sys.stderr, flush=True)
            r = await scrape_one(context, asin, out_dir)
            print(
                f"    price={r.get('price')} ok={r.get('ok')}",
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
    args = ap.parse_args()
    asyncio.run(main(args.asins, Path(args.out)))
