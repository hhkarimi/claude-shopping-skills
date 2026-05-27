"""End-to-end tests for the Greek-yogurt ranker. The math is covered by
test_rank.py; this file verifies yogurt-specific data + the Channel column."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RANK_SCRIPT = REPO_ROOT / "skills" / "rank-greek-yogurt" / "scripts" / "rank.py"
NUTRITION = (
    REPO_ROOT / "skills" / "rank-greek-yogurt" / "references" / "nutrition_data.json"
)
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "results_yogurt_sample.json"


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


def test_cli_runs_against_fixture():
    out = _run_rank()
    assert "Ranked: 4 products" in out
    assert "FAGE" in out
    assert "Chobani" in out
    assert "365" in out
    assert "Greek Gods" in out


def test_output_includes_channel_column():
    out = _run_rank()
    assert "| Channel |" in out
    # All fixture entries have channel="regular" via the nutrition database default.
    assert "| regular |" in out


def test_365_wins_on_unit_cost_in_fixture():
    """365 Whole Foods Plain Nonfat at $4.99/68g = $0.0734/g beats:
    - FAGE Total 0% at $6.96/(5*18)=$0.0773/g
    - Chobani Plain at $5.37/(4*17)=$0.079/g
    - Greek Gods at $3.88/(3*6)=$0.2156/g
    """
    out = _run_rank()
    rows = [
        line
        for line in out.splitlines()
        if line.startswith("|") and "---" not in line and "Product" not in line
    ]
    assert "365 by Whole Foods" in rows[0], (
        f"expected 365 Whole Foods at top of $/g ranking, got: {rows[0]}"
    )


def test_greek_gods_loses_on_leucine_adjusted():
    """Greek Gods Honey Vanilla is high-sugar / low-protein — it should rank
    LAST on leucine_adjusted because $0.21/g × pretty low leucine fraction."""
    out = _run_rank(sort="leucine_adjusted")
    rows = [
        line
        for line in out.splitlines()
        if line.startswith("|") and "---" not in line and "Product" not in line
    ]
    assert "Greek Gods" in rows[-1], (
        f"expected Greek Gods at bottom of leucine_adjusted, got: {rows[-1]}"
    )


def test_output_includes_amazon_purchase_url():
    out = _run_rank()
    assert "[link](https://www.amazon.com/dp/B008U5OSTQ)" in out  # Chobani
