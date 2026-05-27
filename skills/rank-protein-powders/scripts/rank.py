# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Rank protein powders by $/g protein, cal:protein, and leucine-adjusted cost.

Usage:
    uv run rank.py --prices results.json --nutrition nutrition_data.json [--sort SORT]

SORT is one of: dollar_per_g_protein (default), cal_protein, leucine_adjusted.
"""

import argparse
import json
from pathlib import Path

WHEY_ISOLATE_LEUCINE_FRACTION = 0.11


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
    }


def format_table(rows: list[dict]) -> str:
    header = (
        "| Product | Type | Price | Total protein | $/g protein | Cal:protein | Leucine-adj $/g |\n"
        "|---|---|---:|---:|---:|---:|---:|"
    )
    lines = [header]
    for r in rows:
        lines.append(
            f"| {r['name']} | {r['type']} | ${r['price']:.2f} | "
            f"{r['total_protein_g']:,} g | ${r['dollar_per_g_protein']:.4f} | "
            f"{r['cal_protein']:.2f} | ${r['leucine_adjusted']:.4f} |"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--prices", required=True, type=Path, help="Path to scraper results.json."
    )
    ap.add_argument(
        "--nutrition", required=True, type=Path, help="Path to nutrition_data.json."
    )
    ap.add_argument(
        "--sort",
        default="dollar_per_g_protein",
        choices=["dollar_per_g_protein", "cal_protein", "leucine_adjusted"],
    )
    args = ap.parse_args()

    prices = json.loads(args.prices.read_text())
    nutrition = json.loads(args.nutrition.read_text())

    rows = []
    missing_nut = []
    missing_price = []
    invalid_nut: list[str] = []
    for entry in prices:
        asin = entry["asin"]
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

    rows.sort(key=lambda r: r[args.sort])

    print(format_table(rows))
    print()
    print(f"Sorted by: {args.sort}")
    print(f"Ranked: {len(rows)} products")
    if missing_price:
        print(f"\nSkipped (no live price): {', '.join(missing_price)}")
    if missing_nut:
        print(
            f"\nSkipped (no nutrition data, add to nutrition_data.json): {', '.join(missing_nut)}"
        )
    if invalid_nut:
        print(f"\nSkipped (invalid nutrition data): {'; '.join(invalid_nut)}")


if __name__ == "__main__":
    main()
