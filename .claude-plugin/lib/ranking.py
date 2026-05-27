"""Shared ranking logic for protein-product comparison skills.

Used by every `skills/rank-*/scripts/rank.py`. Each skill's wrapper script
calls `run_cli` with a description string; the actual math, CLI parsing,
and output formatting live here.
"""

import argparse
import json
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


def print_report(result: dict) -> None:
    print(format_table(result["rows"]))
    print()
    print(f"Sorted by: {result['sort']}")
    print(f"Ranked: {len(result['rows'])} products")
    if result["missing_price"]:
        print(f"Skipped (no live price): {', '.join(result['missing_price'])}")
    if result["missing_nut"]:
        print(
            f"Skipped (no nutrition data, add to nutrition_data.json): "
            f"{', '.join(result['missing_nut'])}"
        )
    if result["invalid_nut"]:
        print(f"Skipped (invalid nutrition data): {'; '.join(result['invalid_nut'])}")
    if result["malformed"]:
        print(f"Skipped (malformed price entries): {'; '.join(result['malformed'])}")


def run_cli(description: str) -> None:
    """Entry point for skills' rank.py wrappers."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument(
        "--prices", required=True, type=Path, help="Path to scraper results.json."
    )
    ap.add_argument(
        "--nutrition", required=True, type=Path, help="Path to nutrition_data.json."
    )
    ap.add_argument("--sort", default="dollar_per_g_protein", choices=SORT_CHOICES)
    args = ap.parse_args()

    # utf-8-sig handles both plain UTF-8 and files with a leading BOM.
    prices = json.loads(args.prices.read_text(encoding="utf-8-sig"))
    nutrition = json.loads(args.nutrition.read_text(encoding="utf-8-sig"))
    result = rank(prices, nutrition, args.sort)
    print_report(result)
