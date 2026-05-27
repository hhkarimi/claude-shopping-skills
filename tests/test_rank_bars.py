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


def test_cli_sort_by_cal_protein():
    result = subprocess.run(
        [
            sys.executable,
            str(RANK_SCRIPT),
            "--prices",
            str(FIXTURE),
            "--nutrition",
            str(NUTRITION),
            "--sort",
            "cal_protein",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Sorted by: cal_protein" in result.stdout


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
