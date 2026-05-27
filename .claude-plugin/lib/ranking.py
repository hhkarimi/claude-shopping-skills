"""Shared ranking logic for protein-product comparison skills.

Used by every `skills/rank-*/scripts/rank.py`. Each skill's wrapper script
calls `run_cli` with a description string; the actual math, CLI parsing,
and output formatting live here.

Two modes:
- `--prices results.json --nutrition nutrition_data.json` — rank known ASINs
- `--search "<query>" --nutrition nutrition_data.json` — search Amazon, filter to
  ASINs that have nutrition data, scrape live prices, rank
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WHEY_ISOLATE_LEUCINE_FRACTION = 0.11

REQUIRED_NUTRITION_KEYS = (
    "name",
    "type",
    "servings_per_container",
    "protein_per_serving_g",
    "calories_per_serving",
    "leucine_per_serving_g",
)

SORT_CHOICES = ("dollar_per_g_protein", "cal_protein", "leucine_adjusted")

# Path to the amazon-product-data skill's scripts, relative to this module.
# .claude-plugin/lib/ranking.py → ../../skills/amazon-product-data/scripts/
AMAZON_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2] / "skills" / "amazon-product-data" / "scripts"
)


def amazon_url(asin: str) -> str:
    return f"https://www.amazon.com/dp/{asin}"


def compute_row(asin: str, price: float, nut: dict) -> dict:
    protein_per_serving = nut["protein_per_serving_g"]
    servings = nut["servings_per_container"]
    if protein_per_serving <= 0 or servings <= 0:
        raise ValueError(
            f"{asin}: protein_per_serving_g and servings_per_container must be > 0 "
            f"(got protein={protein_per_serving}, servings={servings})"
        )
    leucine = nut["leucine_per_serving_g"]
    if leucine <= 0:
        raise ValueError(f"{asin}: leucine_per_serving_g must be > 0 (got {leucine})")

    total_protein_g = servings * protein_per_serving
    dollar_per_g = price / total_protein_g
    cal_protein = nut["calories_per_serving"] / protein_per_serving
    leucine_fraction = leucine / protein_per_serving
    leucine_adjusted = dollar_per_g * (WHEY_ISOLATE_LEUCINE_FRACTION / leucine_fraction)

    return {
        "asin": asin,
        "name": nut["name"],
        "type": nut["type"],
        "price": price,
        "total_protein_g": total_protein_g,
        "dollar_per_g_protein": round(dollar_per_g, 4),
        "cal_protein": round(cal_protein, 2),
        "leucine_adjusted": round(leucine_adjusted, 4),
        "url": amazon_url(asin),
    }


def format_table(rows: list[dict]) -> str:
    header = (
        "| Product | Type | Price | Total protein | $/g protein | "
        "Cal:protein | Leucine-adj $/g | Buy |\n"
        "|---|---|---:|---:|---:|---:|---:|:---:|"
    )
    lines = [header]
    for r in rows:
        url = r.get("url") or amazon_url(r["asin"])
        lines.append(
            f"| {r['name']} | {r['type']} | ${r['price']:.2f} | "
            f"{r['total_protein_g']:,} g | ${r['dollar_per_g_protein']:.4f} | "
            f"{r['cal_protein']:.2f} | ${r['leucine_adjusted']:.4f} | "
            f"[link]({url}) |"
        )
    return "\n".join(lines)


def rank(prices: list[dict], nutrition: dict, sort: str) -> dict:
    """Compute ranked rows + skip categories. Pure function — no I/O."""
    rows: list[dict] = []
    missing_nut: list[str] = []
    missing_price: list[str] = []
    invalid_nut: list[str] = []
    malformed: list[str] = []
    for entry in prices:
        asin = entry.get("asin")
        if not asin:
            malformed.append(repr(entry)[:80])
            continue
        price = entry.get("price")
        if price is None:
            missing_price.append(asin)
            continue
        nut = nutrition.get(asin)
        if not nut:
            missing_nut.append(asin)
            continue
        try:
            rows.append(compute_row(asin, price, nut))
        except ValueError as e:
            invalid_nut.append(f"{asin} ({e})")

    rows.sort(key=lambda r: r[sort])
    return {
        "rows": rows,
        "missing_price": missing_price,
        "missing_nut": missing_nut,
        "invalid_nut": invalid_nut,
        "malformed": malformed,
        "sort": sort,
    }


def print_report(result: dict, unknown_search_hits: list[dict] | None = None) -> None:
    """Print the rank report. Table + sort/count go to stdout (the data);
    every Skipped/Found-but-unknown diagnostic goes to stderr so consumers
    can pipe stdout to a file and get a clean markdown table."""
    rows = result["rows"]
    if rows:
        print(format_table(rows))
        print()
    print(f"Sorted by: {result['sort']}")
    print(f"Ranked: {len(rows)} products")

    if result["missing_price"]:
        print(
            f"Skipped (no live price): {', '.join(result['missing_price'])}",
            file=sys.stderr,
        )
    if result["missing_nut"]:
        print(
            f"Skipped (no nutrition data, add to nutrition_data.json): "
            f"{', '.join(result['missing_nut'])}",
            file=sys.stderr,
        )
    if result["invalid_nut"]:
        print(
            f"Skipped (invalid nutrition data): {'; '.join(result['invalid_nut'])}",
            file=sys.stderr,
        )
    if result["malformed"]:
        print(
            f"Skipped (malformed price entries): {'; '.join(result['malformed'])}",
            file=sys.stderr,
        )
    if unknown_search_hits:
        print(
            "\nFound in search but no nutrition data — "
            "add to nutrition_data.json to include in future rankings:",
            file=sys.stderr,
        )
        for hit in unknown_search_hits[:10]:
            title = (hit.get("title") or "")[:70]
            print(f"  {hit['asin']}  {title}", file=sys.stderr)


def filter_search_results(
    search_results: list[dict], nutrition: dict
) -> tuple[list[dict], list[dict]]:
    """Split search results into (known_asins, unknown_asins). Deduplicates by
    ASIN (Amazon search often returns the same product as both sponsored and
    organic) and drops entries missing an ASIN entirely. Pure function."""
    known_set = set(nutrition.keys())
    seen: set[str] = set()
    known: list[dict] = []
    unknown: list[dict] = []
    for r in search_results:
        asin = r.get("asin")
        if not asin or asin in seen:
            continue
        seen.add(asin)
        if asin in known_set:
            known.append(r)
        else:
            unknown.append(r)
    return known, unknown


class SearchPipelineError(RuntimeError):
    """Raised when the search.py or scrape.py subprocess fails or times out.

    Wraps the underlying subprocess error with context the user can act on
    (artifact path, WAF hint, install hint) so they never see a raw traceback."""


# Per-subprocess defaults. Search hits one URL; scrape hits N.
SEARCH_TIMEOUT_S = 180
SCRAPE_PER_ASIN_S = 30
SCRAPE_BASE_TIMEOUT_S = 60


def _check_uv_available() -> None:
    """Fail fast with a clear message if `uv` isn't on PATH."""
    if shutil.which("uv") is None:
        raise SearchPipelineError(
            "uv not found on PATH. Install it via `brew install uv` "
            "(or see https://docs.astral.sh/uv/) and re-run."
        )


def _run_subprocess(
    args: list[str], *, description: str, timeout: int, artifact_dir: Path
) -> None:
    """Run a subprocess.run with friendly error wrapping."""
    try:
        subprocess.run(args, check=True, timeout=timeout)
    except FileNotFoundError as e:
        raise SearchPipelineError(
            f"{description} failed: required binary not found ({e.filename!r}). "
            f"Install uv (https://docs.astral.sh/uv/) and ensure it's on PATH."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise SearchPipelineError(
            f"{description} exceeded {timeout}s timeout. "
            f"Amazon may be slow or blocking; check artifacts in {artifact_dir}."
        ) from e
    except subprocess.CalledProcessError as e:
        hint = ""
        if e.returncode == 2:
            hint = (
                " (exit 2 from search.py indicates an AWS WAF bot challenge — "
                "inspect search.html in the artifact dir)"
            )
        raise SearchPipelineError(
            f"{description} failed with exit code {e.returncode}.{hint} "
            f"Artifacts in {artifact_dir}."
        ) from e


def _run_search(query: str, max_results: int, out_dir: Path) -> list[dict]:
    """Shell out to search.py and parse its JSON output."""
    out_dir.mkdir(parents=True, exist_ok=True)
    _run_subprocess(
        [
            "uv",
            "run",
            str(AMAZON_SCRIPTS_DIR / "search.py"),
            query,
            "--max-results",
            str(max_results),
            "--out",
            str(out_dir),
        ],
        description="Amazon search",
        timeout=SEARCH_TIMEOUT_S,
        artifact_dir=out_dir,
    )
    return json.loads((out_dir / "search_results.json").read_text(encoding="utf-8-sig"))


def _run_scrape(asins: list[str], out_dir: Path) -> list[dict]:
    """Shell out to scrape.py and parse its JSON output."""
    out_dir.mkdir(parents=True, exist_ok=True)
    timeout = SCRAPE_BASE_TIMEOUT_S + SCRAPE_PER_ASIN_S * len(asins)
    _run_subprocess(
        [
            "uv",
            "run",
            str(AMAZON_SCRIPTS_DIR / "scrape.py"),
            *asins,
            "--out",
            str(out_dir),
        ],
        description=f"Amazon scrape of {len(asins)} ASINs",
        timeout=timeout,
        artifact_dir=out_dir,
    )
    return json.loads((out_dir / "results.json").read_text(encoding="utf-8-sig"))


def run_cli(description: str) -> None:
    """Entry point for skills' rank.py wrappers."""
    ap = argparse.ArgumentParser(description=description)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--prices",
        type=Path,
        help="Path to scraper results.json. Mutually exclusive with --search.",
    )
    mode.add_argument(
        "--search",
        type=str,
        help="Search Amazon for this query, filter to ASINs in the nutrition "
        "database, scrape live prices, then rank.",
    )
    ap.add_argument(
        "--nutrition", required=True, type=Path, help="Path to nutrition_data.json."
    )
    ap.add_argument("--sort", default="dollar_per_g_protein", choices=SORT_CHOICES)
    ap.add_argument(
        "--max-results",
        type=int,
        default=20,
        help="With --search: cap how many of the FIRST PAGE of Amazon search "
        "results to consider (default 20). Amazon's first page returns up to "
        "~48 cards; pagination is not yet supported, so values above ~48 "
        "have no further effect.",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(tempfile.gettempdir()) / "amzn",
        help="Working directory for search/scrape artifacts "
        "(default: <system temp>/amzn). Artifacts accumulate over runs — "
        "clean periodically.",
    )
    args = ap.parse_args()

    # Distinguish "not passed" (None) from "passed empty" (""). argparse's
    # mutually_exclusive_group accepts --search "" as satisfying the group,
    # so we must check explicitly rather than relying on truthiness.
    if args.search is not None and not args.search.strip():
        ap.error("--search requires a non-empty query")

    nutrition = json.loads(args.nutrition.read_text(encoding="utf-8-sig"))

    unknown_hits: list[dict] = []
    try:
        if args.search is not None:
            _check_uv_available()
            print(f"Searching Amazon for: {args.search!r}", file=sys.stderr, flush=True)
            search_results = _run_search(args.search, args.max_results, args.out)
            known, unknown_hits = filter_search_results(search_results, nutrition)
            if not known:
                print(
                    f"No matches between {len(search_results)} search results and the "
                    f"nutrition database ({len(nutrition)} products).",
                    file=sys.stderr,
                )
                print_report(
                    {
                        "rows": [],
                        "missing_price": [],
                        "missing_nut": [],
                        "invalid_nut": [],
                        "malformed": [],
                        "sort": args.sort,
                    },
                    unknown_search_hits=unknown_hits,
                )
                return
            print(
                f"Found {len(known)} known + {len(unknown_hits)} unknown ASINs. "
                f"Scraping prices for the {len(known)} known...",
                file=sys.stderr,
                flush=True,
            )
            asins = [r["asin"] for r in known]
            prices = _run_scrape(asins, args.out)
        else:
            prices = json.loads(args.prices.read_text(encoding="utf-8-sig"))
    except SearchPipelineError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)

    result = rank(prices, nutrition, args.sort)
    print_report(result, unknown_search_hits=unknown_hits)

    if args.search is not None:
        print(f"\nArtifacts in {args.out}", file=sys.stderr)
