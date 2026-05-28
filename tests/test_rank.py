"""Unit tests for lib/ranking.py (shared ranker logic) + the powders rank.py CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ranking import (
    compute_picks,
    compute_row,
    format_freshness,
    format_picks,
    format_table,
    rank,
)

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
            "channel": "regular",
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
    assert "| Channel |" in out
    assert "| % Δ vs prev |" in out
    assert "| Buy |" in out
    assert "| A |" in out
    assert "| regular |" in out
    assert "$0.0500" in out
    # First (and only) row has no previous row to compare against → em-dash.
    assert "| — |" in out
    assert "[link](https://www.amazon.com/dp/B000A1B2C3)" in out


def test_format_table_renders_pct_delta_between_adjacent_rows():
    """Second-row delta is computed against first row's $/g, etc."""
    rows = [
        {
            "asin": "B0CHEAP001",
            "name": "Cheaper",
            "type": "whey",
            "channel": "regular",
            "price": 10.0,
            "total_protein_g": 100,
            "dollar_per_g_protein": 0.10,
            "cal_protein": 4.0,
            "leucine_adjusted": 0.10,
            "url": "https://www.amazon.com/dp/B0CHEAP001",
        },
        {
            "asin": "B0DEAR0001",
            "name": "Dearer",
            "type": "whey",
            "channel": "regular",
            "price": 12.0,
            "total_protein_g": 100,
            "dollar_per_g_protein": 0.12,
            "cal_protein": 4.0,
            "leucine_adjusted": 0.12,
            "url": "https://www.amazon.com/dp/B0DEAR0001",
        },
    ]
    out = format_table(rows)
    # Second row should be +20% more expensive per gram than first row.
    assert "+20.0%" in out
    # First row should still be em-dash.
    assert "| — |" in out


def test_format_table_zero_delta_renders_without_plus_sign():
    """Adjacent identical metrics render as '0.0%', not '+0.0%'."""
    rows = [
        {
            "asin": "B0EQUAL001",
            "name": "First",
            "type": "whey",
            "channel": "regular",
            "price": 10.0,
            "total_protein_g": 100,
            "dollar_per_g_protein": 0.10,
            "cal_protein": 4.0,
            "leucine_adjusted": 0.10,
            "url": "https://www.amazon.com/dp/B0EQUAL001",
        },
        {
            "asin": "B0EQUAL002",
            "name": "Tied",
            "type": "whey",
            "channel": "regular",
            "price": 10.0,
            "total_protein_g": 100,
            "dollar_per_g_protein": 0.10,
            "cal_protein": 4.0,
            "leucine_adjusted": 0.10,
            "url": "https://www.amazon.com/dp/B0EQUAL002",
        },
    ]
    out = format_table(rows)
    assert "| 0.0% |" in out
    assert "+0.0%" not in out


def test_format_table_delta_tracks_sort_key():
    """When sorted by cal_protein, the % delta column reflects cal_protein
    deltas, not $/g protein deltas."""
    rows = [
        {
            "asin": "B0LEAN0001",
            "name": "Lean",
            "type": "whey",
            "channel": "regular",
            "price": 10.0,
            "total_protein_g": 100,
            "dollar_per_g_protein": 0.20,
            "cal_protein": 4.0,
            "leucine_adjusted": 0.20,
            "url": "https://www.amazon.com/dp/B0LEAN0001",
        },
        {
            "asin": "B0FATR0001",
            "name": "Fattier",
            "type": "whey",
            "channel": "regular",
            "price": 10.0,
            "total_protein_g": 100,
            "dollar_per_g_protein": 0.10,
            "cal_protein": 5.0,
            "leucine_adjusted": 0.10,
            "url": "https://www.amazon.com/dp/B0FATR0001",
        },
    ]
    # Sorted by cal_protein: Lean (4.0) first, Fattier (5.0) second.
    # Delta: (5.0 - 4.0) / 4.0 = +25.0%.
    out = format_table(rows, sort_key="cal_protein")
    assert "+25.0%" in out


def test_compute_row_uses_regular_price_when_fresh_price_is_none():
    """fresh_available=True with fresh_price=None means Fresh-exclusive
    listing — the regular price IS the Fresh price."""
    nut = {
        "name": "Test",
        "type": "milk_protein",
        "servings_per_container": 4,
        "protein_per_serving_g": 18,
        "calories_per_serving": 90,
        "leucine_per_serving_g": 1.7,
    }
    row = compute_row("B0FRESH003", 6.96, nut, fresh_available=True, fresh_price=None)
    assert row["price"] == 6.96


def test_compute_row_treats_zero_fresh_price_as_set():
    """Edge case: fresh_price=0.0 should NOT silently fall through to the
    regular price (since 0 is falsy). The new conditional uses `is not None`."""
    nut = {
        "name": "Test",
        "type": "milk_protein",
        "servings_per_container": 4,
        "protein_per_serving_g": 18,
        "calories_per_serving": 90,
        "leucine_per_serving_g": 1.7,
    }
    row = compute_row("B0FREE001", 6.96, nut, fresh_available=True, fresh_price=0.0)
    # A $0 fresh_price (theoretical edge case) is now respected as-set, not
    # interpreted as "unset". dollar_per_g_protein becomes 0.0.
    assert row["price"] == 0.0
    assert row["dollar_per_g_protein"] == 0.0


def test_compute_row_channel_from_fresh_available_true():
    nut = {
        "name": "Test",
        "type": "milk_protein",
        "servings_per_container": 4,
        "protein_per_serving_g": 17,
        "calories_per_serving": 100,
        "leucine_per_serving_g": 1.5,
    }
    row = compute_row("B0FRESH001", 5.99, nut, fresh_available=True)
    assert row["channel"] == "fresh"


def test_compute_row_channel_from_fresh_available_false():
    nut = {
        "name": "Test",
        "type": "whey_isolate",
        "servings_per_container": 10,
        "protein_per_serving_g": 25,
        "calories_per_serving": 110,
        "leucine_per_serving_g": 2.75,
    }
    row = compute_row("B0REGULAR1", 20.0, nut, fresh_available=False)
    assert row["channel"] == "regular"


def test_compute_row_respects_nutrition_channel_default_when_unknown():
    """If fresh_available is None (--prices mode), fall back to the nutrition
    entry's `channel` field."""
    nut = {
        "name": "Test",
        "type": "milk_protein",
        "channel": "fresh",
        "servings_per_container": 1,
        "protein_per_serving_g": 14,
        "calories_per_serving": 110,
        "leucine_per_serving_g": 1.4,
    }
    row = compute_row("B0FRESH002", 3.29, nut)
    assert row["channel"] == "fresh"


def test_compute_row_nutrition_channel_fresh_wins_over_scraped_false():
    """An explicit `channel: "fresh"` in nutrition_data.json wins over a
    scrape `fresh_available=False`. This handles ASINs that surface in the
    Fresh storefront search but whose regular product page doesn't render
    the Fresh badge — common for items cross-listed on both channels."""
    nut = {
        "name": "RXBAR-like cross-channel Fresh-storefront listing",
        "type": "egg_whole_food",
        "channel": "fresh",
        "servings_per_container": 10,
        "protein_per_serving_g": 12,
        "calories_per_serving": 210,
        "leucine_per_serving_g": 1.0,
    }
    row = compute_row("B0CND6BGC6", 16.98, nut, fresh_available=False, fresh_price=None)
    assert row["channel"] == "fresh"


def test_compute_row_scrape_fresh_true_wins_over_nutrition_regular():
    """The opposite precedence: if scrape definitively sees the Fresh badge,
    that wins even when nutrition tagged the entry as 'regular'. (Captures
    the case where Amazon expanded Fresh stocking after our DB was last
    updated.)"""
    nut = {
        "name": "Test",
        "type": "milk_protein",
        "channel": "regular",
        "servings_per_container": 4,
        "protein_per_serving_g": 17,
        "calories_per_serving": 100,
        "leucine_per_serving_g": 1.5,
    }
    row = compute_row("B0NEWFRSH1", 5.99, nut, fresh_available=True)
    assert row["channel"] == "fresh"


def test_compute_row_uses_fresh_price_for_dollar_per_g_when_set():
    """When fresh_available is true AND a separate fresh_price exists, that
    Fresh price drives the $/g math because it's what the user would pay."""
    nut = {
        "name": "Test",
        "type": "milk_protein",
        "servings_per_container": 4,
        "protein_per_serving_g": 18,
        "calories_per_serving": 90,
        "leucine_per_serving_g": 1.7,
    }
    row = compute_row("B0FAGE0001", 7.96, nut, fresh_available=True, fresh_price=6.96)
    assert row["price"] == 6.96
    # 6.96 / (4 * 18) = 0.0967
    assert row["dollar_per_g_protein"] == 0.0967


def test_compute_row_falls_back_to_regular_price_when_no_fresh_price():
    """If fresh_available=true but no separate fresh_price, the regular price
    is the Fresh price (Fresh-exclusive listings)."""
    nut = {
        "name": "Test",
        "type": "milk_protein",
        "servings_per_container": 4,
        "protein_per_serving_g": 18,
        "calories_per_serving": 90,
        "leucine_per_serving_g": 1.7,
    }
    row = compute_row("B0FAGE0002", 6.96, nut, fresh_available=True)
    assert row["price"] == 6.96
    assert row["channel"] == "fresh"


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


# ---------- compute_picks / format_picks ----------


def _make_row(asin, name, price, dpg, cal, leu):
    return {
        "asin": asin,
        "name": name,
        "type": "whey_isolate",
        "channel": "regular",
        "price": price,
        "total_protein_g": 1000,
        "dollar_per_g_protein": dpg,
        "cal_protein": cal,
        "leucine_adjusted": leu,
        "url": f"https://www.amazon.com/dp/{asin}",
    }


def test_compute_picks_returns_winner_per_criterion():
    rows = [
        _make_row("B0CHEAP001", "Cheap raw", 30.0, 0.020, 5.00, 0.030),
        _make_row("B0LEAN0001", "Lean macros", 40.0, 0.040, 4.00, 0.045),
        _make_row("B0LEUC0001", "Best leucine", 35.0, 0.030, 4.50, 0.025),
    ]
    picks = compute_picks(rows)
    labels_to_asin = {label: row["asin"] for label, row in picks}
    assert labels_to_asin["Lowest $/g protein"] == "B0CHEAP001"
    assert labels_to_asin["Best muscle-building $/g (leucine-adj)"] == "B0LEUC0001"
    assert labels_to_asin["Leanest macros (cal:protein)"] == "B0LEAN0001"


def test_compute_picks_empty_when_fewer_than_two_rows():
    """Picking the 'best' from a single row is silly — skip the table entirely."""
    assert compute_picks([]) == []
    assert (
        compute_picks([_make_row("B0SOLO0001", "Solo", 30.0, 0.020, 5.0, 0.030)]) == []
    )


def test_compute_picks_allows_same_winner_across_criteria():
    """One product dominating multiple criteria is a feature, not a bug —
    each goal row still appears so the user sees it's the best on each axis."""
    rows = [
        _make_row("B0KING00001", "Dominant", 30.0, 0.020, 4.00, 0.020),
        _make_row("B0LOSER0001", "Worse on all", 40.0, 0.050, 6.00, 0.060),
    ]
    picks = compute_picks(rows)
    assert len(picks) == 3
    assert all(row["asin"] == "B0KING00001" for _, row in picks)


def test_format_picks_renders_header_and_rows():
    rows = [
        _make_row("B0CHEAP001", "Cheap raw", 30.0, 0.020, 5.00, 0.030),
        _make_row("B0LEAN0001", "Lean macros", 40.0, 0.040, 4.00, 0.045),
    ]
    out = format_picks(rows)
    assert "| Goal |" in out
    assert "| Pick |" in out
    assert "| Cal:protein |" in out
    assert "| Leucine-adj $/g |" in out
    assert "Lowest $/g protein" in out
    assert "Leanest macros (cal:protein)" in out
    assert "Cheap raw" in out
    assert "Lean macros" in out
    assert "[link](https://www.amazon.com/dp/B0CHEAP001)" in out


def test_format_picks_returns_empty_string_when_no_picks():
    assert format_picks([]) == ""


def test_print_report_includes_picks_table_when_multiple_rows(capsys):
    """The 'Best pick by goal' table is part of the skill's standard output —
    must appear on stdout (not stderr) below the main ranking table."""
    from ranking import print_report

    rows = [
        _make_row("B0CHEAP001", "Cheap raw", 30.0, 0.020, 5.00, 0.030),
        _make_row("B0LEAN0001", "Lean macros", 40.0, 0.040, 4.00, 0.045),
    ]
    print_report(
        {
            "rows": rows,
            "missing_price": [],
            "missing_nut": [],
            "invalid_nut": [],
            "malformed": [],
            "sort": "dollar_per_g_protein",
        }
    )
    captured = capsys.readouterr()
    assert "Best pick by goal:" in captured.out
    assert "Lowest $/g protein" in captured.out
    # Main ranking table must still come first.
    main_idx = captured.out.index("| Product |")
    picks_idx = captured.out.index("Best pick by goal:")
    assert main_idx < picks_idx


def test_print_report_omits_picks_table_when_only_one_row(capsys):
    from ranking import print_report

    rows = [_make_row("B0SOLO0001", "Solo", 30.0, 0.020, 5.0, 0.030)]
    print_report(
        {
            "rows": rows,
            "missing_price": [],
            "missing_nut": [],
            "invalid_nut": [],
            "malformed": [],
            "sort": "dollar_per_g_protein",
        }
    )
    captured = capsys.readouterr()
    assert "Best pick by goal:" not in captured.out


# ---------- price freshness ----------


def test_format_freshness_empty_when_no_timestamps():
    """Zero timestamps (zero products ranked, or external results.json
    predating scraped_at) — render no freshness line rather than 'unknown'."""
    assert format_freshness([]) == ""


def test_format_freshness_single_timestamp_when_all_equal():
    ts = "2026-05-27T18:34:21+00:00"
    assert format_freshness([ts, ts, ts]) == f"Prices captured: {ts}"


def test_format_freshness_range_when_spans_multiple_scrapes():
    earlier = "2026-05-25T10:00:00+00:00"
    later = "2026-05-27T18:34:21+00:00"
    out = format_freshness([later, earlier, later])
    assert out == f"Prices captured: {earlier} .. {later}"


def test_rank_collects_scraped_at_timestamps():
    """rank() must propagate scraped_at from price entries into the result
    so print_report can show freshness."""
    nutrition = {
        "B0TEST00001": {
            "name": "T",
            "type": "whey_isolate",
            "servings_per_container": 10,
            "protein_per_serving_g": 25,
            "calories_per_serving": 100,
            "leucine_per_serving_g": 2.75,
        }
    }
    prices = [
        {
            "asin": "B0TEST00001",
            "price": 25.0,
            "scraped_at": "2026-05-27T18:00:00+00:00",
        }
    ]
    result = rank(prices, nutrition, sort="dollar_per_g_protein")
    assert result["price_timestamps"] == ["2026-05-27T18:00:00+00:00"]


def test_rank_omits_timestamp_when_scraped_at_absent():
    """External results.json (e.g. pre-feature, or hand-rolled) without
    scraped_at must still rank — those entries simply don't contribute a
    timestamp, and the freshness line is suppressed if every entry lacked
    one. scrape.py and the committed fixtures always set scraped_at."""
    nutrition = {
        "B0TEST00001": {
            "name": "T",
            "type": "whey_isolate",
            "servings_per_container": 10,
            "protein_per_serving_g": 25,
            "calories_per_serving": 100,
            "leucine_per_serving_g": 2.75,
        }
    }
    prices = [{"asin": "B0TEST00001", "price": 25.0}]
    result = rank(prices, nutrition, sort="dollar_per_g_protein")
    assert result["price_timestamps"] == []


def test_committed_fixtures_carry_scraped_at():
    """All checked-in fixture files must include scraped_at on every entry
    so the freshness line renders during local dev and CI. Real scrapes
    always stamp; fixtures are stamped at commit time."""
    for fixture in Path(__file__).parent.joinpath("fixtures").glob("*.json"):
        with fixture.open() as f:
            data = json.load(f)
        for entry in data:
            assert "scraped_at" in entry, (
                f"{fixture.name} entry {entry.get('asin')} missing scraped_at"
            )


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
