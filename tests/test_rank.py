"""Unit tests for lib/ranking.py (shared ranker logic) + the powders rank.py CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ranking import compute_row, format_table

REPO_ROOT = Path(__file__).resolve().parent.parent
RANK_SCRIPT = REPO_ROOT / "skills" / "rank-protein-powders" / "scripts" / "rank.py"
NUTRITION = (
    REPO_ROOT / "skills" / "rank-protein-powders" / "references" / "nutrition_data.json"
)
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "results_sample.json"


# ---------- compute_row ----------


def test_compute_row_basic():
    nut = {
        "name": "Test Whey 5 lb",
        "type": "whey_isolate",
        "servings_per_container": 100,
        "protein_per_serving_g": 25,
        "calories_per_serving": 110,
        "leucine_per_serving_g": 2.75,
    }
    row = compute_row("B000TEST01", 100.0, nut)
    assert row["asin"] == "B000TEST01"
    assert row["total_protein_g"] == 2500
    assert row["dollar_per_g_protein"] == pytest.approx(0.04, abs=1e-6)
    assert row["cal_protein"] == pytest.approx(4.4, abs=1e-6)
    # leucine-adjusted equals raw when product matches whey-isolate leucine fraction (11%)
    assert row["leucine_adjusted"] == pytest.approx(
        row["dollar_per_g_protein"], rel=1e-3
    )


def test_compute_row_rejects_zero_protein():
    nut = {
        "name": "Bad data",
        "type": "whey_isolate",
        "servings_per_container": 50,
        "protein_per_serving_g": 0,
        "calories_per_serving": 100,
        "leucine_per_serving_g": 2.0,
    }
    with pytest.raises(ValueError, match="protein_per_serving_g"):
        compute_row("B000BAD001", 30.0, nut)


def test_compute_row_rejects_zero_servings():
    nut = {
        "name": "Bad data",
        "type": "whey_isolate",
        "servings_per_container": 0,
        "protein_per_serving_g": 25,
        "calories_per_serving": 100,
        "leucine_per_serving_g": 2.75,
    }
    with pytest.raises(ValueError, match="servings_per_container"):
        compute_row("B000BAD002", 30.0, nut)


def test_cli_handles_invalid_nutrition(tmp_path: Path):
    """ASINs with semantically invalid nutrition data are reported and skipped, not crashed."""
    fake_nutrition = tmp_path / "nutrition.json"
    fake_nutrition.write_text(
        json.dumps(
            {
                "B000BADXXX": {
                    "name": "Zero-protein product",
                    "type": "whey_isolate",
                    "servings_per_container": 50,
                    "protein_per_serving_g": 0,
                    "calories_per_serving": 100,
                    "leucine_per_serving_g": 2.0,
                },
            }
        )
    )
    fake_prices = tmp_path / "prices.json"
    fake_prices.write_text(
        json.dumps([{"asin": "B000BADXXX", "price": 30.0, "ok": True}])
    )
    result = subprocess.run(
        [
            sys.executable,
            str(RANK_SCRIPT),
            "--prices",
            str(fake_prices),
            "--nutrition",
            str(fake_nutrition),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    # Table + Ranked summary on stdout; Skipped diagnostics on stderr.
    assert "Ranked: 0 products" in result.stdout
    assert "invalid nutrition data" in result.stderr
    assert "B000BADXXX" in result.stderr


def test_compute_row_leucine_penalty_for_pea():
    nut = {
        "name": "Test Pea 2 lb",
        "type": "pea",
        "servings_per_container": 30,
        "protein_per_serving_g": 25,
        "calories_per_serving": 120,
        "leucine_per_serving_g": 2.0,  # 8% — pea fraction
    }
    row = compute_row("B000PEA001", 30.0, nut)
    # leucine_adjusted should be ~37.5% higher than raw (0.11/0.08 = 1.375)
    assert row["leucine_adjusted"] > row["dollar_per_g_protein"]
    assert row["leucine_adjusted"] / row["dollar_per_g_protein"] == pytest.approx(
        1.375, rel=1e-3
    )


# ---------- format_table ----------


def test_format_table_includes_header_and_rows_and_url():
    rows = [
        {
            "asin": "B000A1B2C3",
            "name": "A",
            "type": "whey_isolate",
            "price": 50.0,
            "total_protein_g": 1000,
            "dollar_per_g_protein": 0.05,
            "cal_protein": 4.4,
            "leucine_adjusted": 0.05,
            "url": "https://www.amazon.com/dp/B000A1B2C3",
        },
    ]
    out = format_table(rows)
    assert "| Product |" in out
    assert "| Buy |" in out
    assert "| A |" in out
    assert "$0.0500" in out
    assert "[link](https://www.amazon.com/dp/B000A1B2C3)" in out


def test_compute_row_includes_amazon_url():
    nut = {
        "name": "Test",
        "type": "whey_isolate",
        "servings_per_container": 10,
        "protein_per_serving_g": 25,
        "calories_per_serving": 110,
        "leucine_per_serving_g": 2.75,
    }
    row = compute_row("B0ABCDEFGH", 20.0, nut)
    assert row["url"] == "https://www.amazon.com/dp/B0ABCDEFGH"


# ---------- end-to-end CLI ----------


def test_cli_runs_against_fixture():
    """End-to-end: rank.py CLI against committed fixture + nutrition data."""
    result = subprocess.run(
        [
            sys.executable,
            str(RANK_SCRIPT),
            "--prices",
            str(FIXTURE),
            "--nutrition",
            str(NUTRITION),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Ranked: 3 products" in result.stdout
    assert "Naked Pea" in result.stdout
    assert "NOW Sports Whey Isolate" in result.stdout


def test_cli_handles_missing_nutrition(tmp_path: Path):
    """ASINs without nutrition data are reported and excluded from ranking."""
    fake_prices = tmp_path / "prices.json"
    fake_prices.write_text(
        json.dumps(
            [
                {"asin": "B000MAK59O", "price": 181.99, "ok": True},
                {"asin": "B0UNKNOWN1", "price": 30.0, "ok": True},
            ]
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            str(RANK_SCRIPT),
            "--prices",
            str(fake_prices),
            "--nutrition",
            str(NUTRITION),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Ranked: 1 products" in result.stdout
    assert "B0UNKNOWN1" in result.stderr
    assert "no nutrition data" in result.stderr


def test_cli_skips_null_prices(tmp_path: Path):
    """ASINs with null price (scrape failure) are listed separately."""
    fake_prices = tmp_path / "prices.json"
    fake_prices.write_text(
        json.dumps(
            [
                {"asin": "B000MAK59O", "price": None, "ok": False},
            ]
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            str(RANK_SCRIPT),
            "--prices",
            str(fake_prices),
            "--nutrition",
            str(NUTRITION),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Ranked: 0 products" in result.stdout
    assert "no live price" in result.stderr


def test_cli_handles_malformed_entries(tmp_path: Path):
    """Price entries missing the asin field are reported, not crashed."""
    fake_prices = tmp_path / "prices.json"
    fake_prices.write_text(
        json.dumps(
            [
                {"price": 10.0, "ok": True},  # missing asin
                {"asin": "B000MAK59O", "price": 181.99, "ok": True},
            ]
        )
    )
    result = subprocess.run(
        [
            sys.executable,
            str(RANK_SCRIPT),
            "--prices",
            str(fake_prices),
            "--nutrition",
            str(NUTRITION),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Ranked: 1 products" in result.stdout
    assert "malformed price entries" in result.stderr
