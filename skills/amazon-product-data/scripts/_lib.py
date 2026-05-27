"""Shared helpers for the amazon-product-data scripts (scrape.py, search.py).

These helpers live in this file so both scripts can `from _lib import ...`
without duplicating ~100 lines. The directory containing the entrypoint
script is on sys.path by default, which makes the import work without any
package installation.

This module imports nothing from Playwright at module level — both helpers
take a `page` object as a parameter, so the heavy deps stay in the calling
script's PEP 723 metadata."""

import asyncio
import re
import sys

ZIP_RE = re.compile(r"^[0-9]{5}$")

# Amazon's "Dogs of Amazon" 503 page returns HTTP 200 with these markers.
# Detect by content because HTTP status would mislead.
THROTTLE_MARKERS = (
    "Sorry! Something went wrong on our end",
    "/dogsofamazon/",
    "500_503.png",
)


async def navigate_with_retry(page, url: str, max_retries: int = 2) -> None:
    """Navigate to `url`, detecting Amazon's throttle/503 page (which returns
    HTTP 200 with Dogs-of-Amazon markup) and retrying with exponential backoff.

    Retries on both Playwright exceptions and on-page-content throttle markers.
    Max wait per cycle: 30s, 60s. Gives up silently after max_retries; the
    caller should inspect what got loaded."""
    for attempt in range(max_retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            if attempt >= max_retries:
                raise
            wait_s = 30 * (2**attempt)
            print(
                f"  navigation failed ({e}); backing off {wait_s}s",
                file=sys.stderr,
            )
            await asyncio.sleep(wait_s)
            continue

        html = await page.content()
        if any(marker in html for marker in THROTTLE_MARKERS):
            if attempt >= max_retries:
                print(
                    "  Amazon throttle page after max retries; giving up.",
                    file=sys.stderr,
                )
                return
            wait_s = 30 * (2**attempt)
            print(
                f"  Amazon throttle page detected; backing off {wait_s}s",
                file=sys.stderr,
            )
            await asyncio.sleep(wait_s)
            continue
        return


async def set_delivery_zip(page, zip_code: str) -> bool:
    """Set Amazon's delivery location to the given ZIP for the browser context.
    Returns True on success.

    Uses the global-location popover flow because the resulting cookie
    persists across requests in the same context. If any step fails, returns
    False and lets the caller decide whether to continue."""
    try:
        await navigate_with_retry(page, "https://www.amazon.com/")
        await page.wait_for_timeout(1500)

        loc_link = page.locator("#nav-global-location-popover-link")
        if not await loc_link.count():
            return False
        await loc_link.first.click()
        await page.wait_for_selector("#GLUXZipUpdateInput", timeout=10000)
        await page.fill("#GLUXZipUpdateInput", zip_code)
        await page.locator("#GLUXZipUpdate input[type='submit']").first.click()
        await page.wait_for_timeout(2000)
        return True
    except Exception as e:
        print(f"WARN: failed to set delivery ZIP {zip_code}: {e}", file=sys.stderr)
        return False
