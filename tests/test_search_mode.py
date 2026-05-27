"""Tests for the --search mode added to rank CLI. We unit-test the pure
filter_search_results helper directly; the full pipeline that shells out to
search.py and scrape.py is a live-network test the user runs manually."""

import subprocess
import sys
from pathlib import Path


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
