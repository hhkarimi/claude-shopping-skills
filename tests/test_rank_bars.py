"""End-to-end tests for the bars ranker. The math is covered by test_rank.py
(same compute_row/format_table from the powders script); this file verifies
the bars-specific data + script wiring."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RANK_SCRIPT = REPO_ROOT / "skills" / "rank-protein-bars" / "scripts" / "rank.py"
NUTRITION = (
    REPO_ROOT / "skills" / "rank-protein-bars" / "references" / "nutrition_data.json"
)
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "results_bars_sample.json"


def test_cli_runs_against_fixture():
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
    assert "Quest" in result.stdout
    assert "BUILT" in result.stdout
    assert "Pure Protein" in result.stdout


def _run_rank(sort: str | None = None) -> str:
    cmd = [
        sys.executable,
        str(RANK_SCRIPT),
        "--prices",
        str(FIXTURE),
        "--nutrition",
        str(NUTRITION),
    ]
    if sort:
        cmd += ["--sort", sort]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def _first_data_row(stdout: str) -> str:
    """First product row from the markdown table — skips header and separator."""
    for line in stdout.splitlines():
        if line.startswith("|") and "---" not in line and "Product" not in line:
            return line
    raise AssertionError("no data rows found in stdout")


def test_cli_sort_by_cal_protein_changes_order():
    """Sort by cal_protein should put the leanest bar (BUILT Puff, 7.65 cal/g) first,
    not the cheapest (Pure Protein at $0.062/g)."""
    default_first = _first_data_row(_run_rank())
    cal_sorted_first = _first_data_row(_run_rank(sort="cal_protein"))

    assert "Sorted by: cal_protein" in _run_rank(sort="cal_protein")
    assert "Pure Protein" in default_first, (
        f"expected Pure Protein at top of default sort, got: {default_first}"
    )
    assert "BUILT" in cal_sorted_first, (
        f"expected BUILT Puff at top of cal_protein sort, got: {cal_sorted_first}"
    )


def test_bars_and_powders_rank_scripts_share_logic():
    """Sanity check: the two ranker scripts are byte-identical except for the docstring."""
    powders = (
        REPO_ROOT / "skills" / "rank-protein-powders" / "scripts" / "rank.py"
    ).read_text()
    bars = RANK_SCRIPT.read_text()

    # Strip everything before the first `import argparse` line — drops the
    # docstring on both sides.
    powders_body = powders[powders.index("import argparse") :]
    bars_body = bars[bars.index("import argparse") :]
    assert powders_body == bars_body, (
        "rank.py for bars and powders have diverged below their docstrings. "
        "Either re-sync them, or extract the shared logic to a module."
    )
