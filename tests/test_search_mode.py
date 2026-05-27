"""Tests for the --search mode added to rank CLI. We unit-test the pure
filter_search_results helper directly; the full pipeline that shells out to
search.py and scrape.py is a live-network test the user runs manually."""

import subprocess
import sys
from pathlib import Path

import pytest

from ranking import filter_search_results

REPO_ROOT = Path(__file__).resolve().parent.parent
POWDERS_RANK = REPO_ROOT / "skills" / "rank-protein-powders" / "scripts" / "rank.py"
POWDERS_NUTRITION = (
    REPO_ROOT / "skills" / "rank-protein-powders" / "references" / "nutrition_data.json"
)


def test_filter_known_and_unknown_split():
    nutrition = {"B000KNOWN1": {"name": "K1"}, "B000KNOWN2": {"name": "K2"}}
    search_results = [
        {"asin": "B000KNOWN1", "title": "K1 product"},
        {"asin": "B000FOO123", "title": "Unknown 1"},
        {"asin": "B000KNOWN2", "title": "K2 product"},
        {"asin": "B000BAR456", "title": "Unknown 2"},
    ]
    known, unknown = filter_search_results(search_results, nutrition)
    assert [k["asin"] for k in known] == ["B000KNOWN1", "B000KNOWN2"]
    assert [u["asin"] for u in unknown] == ["B000FOO123", "B000BAR456"]


def test_filter_empty_search_returns_empty():
    known, unknown = filter_search_results([], {"B000A": {}})
    assert known == [] and unknown == []


def test_filter_no_known_matches():
    known, unknown = filter_search_results(
        [{"asin": "B0NEW00001"}, {"asin": "B0NEW00002"}],
        {"B0KNOWN0001": {}},
    )
    assert known == []
    assert len(unknown) == 2


def test_filter_drops_results_missing_asin():
    """Search-result entries missing 'asin' are dropped entirely (not promoted to unknown)."""
    nutrition = {"B0ABCDEFGH": {}}
    search_results = [{"title": "no asin"}, {"asin": "B0ABCDEFGH"}]
    known, unknown = filter_search_results(search_results, nutrition)
    assert [k["asin"] for k in known] == ["B0ABCDEFGH"]
    assert unknown == []


def test_filter_deduplicates_repeated_asins():
    """Amazon search often returns the same ASIN as sponsored + organic. We
    must dedup to avoid showing the same product twice in the ranking."""
    nutrition = {"B000KNOWN1": {"name": "K1"}}
    search_results = [
        {"asin": "B000KNOWN1", "title": "sponsored"},
        {"asin": "B000DUPE01", "title": "unknown sponsored"},
        {"asin": "B000KNOWN1", "title": "organic"},
        {"asin": "B000DUPE01", "title": "unknown organic"},
    ]
    known, unknown = filter_search_results(search_results, nutrition)
    assert [k["asin"] for k in known] == ["B000KNOWN1"]
    assert [u["asin"] for u in unknown] == ["B000DUPE01"]


def test_cli_requires_prices_or_search():
    """At least one of --prices or --search must be passed."""
    result = subprocess.run(
        [
            sys.executable,
            str(POWDERS_RANK),
            "--nutrition",
            str(POWDERS_NUTRITION),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "one of" in result.stderr.lower()


def test_cli_rejects_both_prices_and_search(tmp_path: Path):
    """--prices and --search are mutually exclusive."""
    fake_prices = tmp_path / "p.json"
    fake_prices.write_text("[]")
    result = subprocess.run(
        [
            sys.executable,
            str(POWDERS_RANK),
            "--prices",
            str(fake_prices),
            "--search",
            "whey",
            "--nutrition",
            str(POWDERS_NUTRITION),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert (
        "not allowed with" in result.stderr.lower()
        or "argument" in result.stderr.lower()
    )


def test_print_report_skips_empty_table_header(capsys):
    """Empty result set must not print a bare table header — it's confusing
    for users piping stdout to a file expecting a parsable markdown table."""
    from ranking import print_report

    print_report(
        {
            "rows": [],
            "missing_price": [],
            "missing_nut": [],
            "invalid_nut": [],
            "malformed": [],
            "sort": "dollar_per_g_protein",
        }
    )
    captured = capsys.readouterr()
    assert "| Product |" not in captured.out
    assert "| Buy |" not in captured.out
    # The sort + count summary should still print.
    assert "Sorted by: dollar_per_g_protein" in captured.out
    assert "Ranked: 0 products" in captured.out


def test_print_report_renders_table_when_rows_present(capsys):
    from ranking import print_report

    print_report(
        {
            "rows": [
                {
                    "asin": "B0ABCDEFGH",
                    "name": "X",
                    "type": "whey_isolate",
                    "price": 50.0,
                    "total_protein_g": 1000,
                    "dollar_per_g_protein": 0.05,
                    "cal_protein": 4.4,
                    "leucine_adjusted": 0.05,
                    "url": "https://www.amazon.com/dp/B0ABCDEFGH",
                }
            ],
            "missing_price": [],
            "missing_nut": [],
            "invalid_nut": [],
            "malformed": [],
            "sort": "dollar_per_g_protein",
        }
    )
    captured = capsys.readouterr()
    assert "| Product |" in captured.out
    assert "| X |" in captured.out


def test_uv_pre_flight_check_fails_clearly(monkeypatch):
    """When `uv` isn't on PATH, the orchestrator must raise SearchPipelineError
    with an install hint — not let subprocess.run die with FileNotFoundError."""
    import ranking

    monkeypatch.setattr(ranking.shutil, "which", lambda _: None)
    with pytest.raises(ranking.SearchPipelineError, match="uv not found"):
        ranking._check_uv_available()


def test_default_out_dir_uses_system_temp():
    """--out default must be platform-portable (no hardcoded /tmp)."""
    result = subprocess.run(
        [sys.executable, str(POWDERS_RANK), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    # The help text should reference a system temp path, not a hardcoded /tmp.
    import tempfile

    assert tempfile.gettempdir() in result.stdout or "system temp" in result.stdout


def test_cli_rejects_empty_search():
    """--search '' is a programmer/typo error; argparse accepts it but we
    must reject it before falling through to a None.read_text crash."""
    result = subprocess.run(
        [
            sys.executable,
            str(POWDERS_RANK),
            "--search",
            "",
            "--nutrition",
            str(POWDERS_NUTRITION),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "non-empty" in result.stderr.lower()
    assert "attributeerror" not in result.stderr.lower()
    assert "traceback" not in result.stderr.lower()


def test_cli_rejects_whitespace_only_search():
    result = subprocess.run(
        [
            sys.executable,
            str(POWDERS_RANK),
            "--search",
            "   ",
            "--nutrition",
            str(POWDERS_NUTRITION),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "non-empty" in result.stderr.lower()


def test_search_pipeline_error_wraps_subprocess_failures():
    """A search.py / scrape.py failure surfaces as a clean SearchPipelineError,
    not a raw CalledProcessError traceback."""
    import subprocess as sp

    from ranking import SearchPipelineError, _run_subprocess

    try:
        _run_subprocess(
            [sys.executable, "-c", "import sys; sys.exit(2)"],
            description="fake search",
            timeout=5,
            artifact_dir=Path("/tmp/amzn"),
        )
    except SearchPipelineError as e:
        msg = str(e)
        assert "fake search" in msg
        assert "exit code 2" in msg
        assert "WAF" in msg  # exit-2 hint
    else:
        raise AssertionError("expected SearchPipelineError on exit 2")

    try:
        _run_subprocess(
            ["/nonexistent/binary-that-does-not-exist-xyz"],
            description="fake search",
            timeout=5,
            artifact_dir=Path("/tmp/amzn"),
        )
    except SearchPipelineError as e:
        assert "PATH" in str(e) or "not found" in str(e).lower()
    else:
        raise AssertionError("expected SearchPipelineError on missing binary")

    try:
        _run_subprocess(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            description="fake search",
            timeout=1,
            artifact_dir=Path("/tmp/amzn"),
        )
    except SearchPipelineError as e:
        assert "timeout" in str(e).lower()
    else:
        raise AssertionError("expected SearchPipelineError on timeout")

    # Avoid unused-import warning for the imported `sp` module above.
    _ = sp


def test_search_script_has_fresh_and_retry_logic():
    """The search script must support --zip / --include-fresh and use the
    throttle-page retry helper. The retry/zip helpers themselves live in
    _lib.py — we check that search.py imports them."""
    scripts_dir = REPO_ROOT / "skills" / "amazon-product-data" / "scripts"
    search_body = (scripts_dir / "search.py").read_text(encoding="utf-8")
    lib_body = (scripts_dir / "_lib.py").read_text(encoding="utf-8")

    assert "--include-fresh" in search_body
    assert "i=amazonfresh" in search_body
    # search.py imports the shared helpers and uses them by name.
    assert "from _lib import" in search_body
    assert "navigate_with_retry" in search_body
    assert "set_delivery_zip" in search_body
    # The helper definitions and shared constants live in _lib.py.
    assert "navigate_with_retry" in lib_body
    assert "set_delivery_zip" in lib_body
    assert "ZIP_RE" in lib_body
    assert "THROTTLE_MARKERS" in lib_body


def test_search_help_documents_fresh_flag():
    SEARCH_SCRIPT = (
        REPO_ROOT / "skills" / "amazon-product-data" / "scripts" / "search.py"
    )
    result = subprocess.run(
        [sys.executable, str(SEARCH_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--zip" in result.stdout
    assert "--include-fresh" in result.stdout


def test_search_rejects_include_fresh_without_zip():
    """--include-fresh requires --zip since Fresh storefront needs a location."""
    SEARCH_SCRIPT = (
        REPO_ROOT / "skills" / "amazon-product-data" / "scripts" / "search.py"
    )
    result = subprocess.run(
        [sys.executable, str(SEARCH_SCRIPT), "yogurt", "--include-fresh"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "requires --zip" in result.stderr.lower() or "zip" in result.stderr.lower()


def test_scrape_script_has_retry_logic():
    """scrape.py imports the shared retry helper from _lib."""
    scripts_dir = REPO_ROOT / "skills" / "amazon-product-data" / "scripts"
    scrape_body = (scripts_dir / "scrape.py").read_text(encoding="utf-8")
    lib_body = (scripts_dir / "_lib.py").read_text(encoding="utf-8")

    assert "from _lib import" in scrape_body
    assert "navigate_with_retry" in scrape_body
    assert "navigate_with_retry" in lib_body
    assert "THROTTLE_MARKERS" in lib_body


def test_help_mentions_both_modes():
    """--help text should describe both --prices and --search modes."""
    result = subprocess.run(
        [sys.executable, str(POWDERS_RANK), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--prices" in result.stdout
    assert "--search" in result.stdout
