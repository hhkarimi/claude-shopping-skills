"""End-to-end tests for the edamame ranker. Math is covered by test_rank.py
against the shared module — this file verifies the edamame-specific data +
wrapper wiring."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RANK_SCRIPT = REPO_ROOT / "skills" / "rank-dry-edamame" / "scripts" / "rank.py"
NUTRITION = (
    REPO_ROOT / "skills" / "rank-dry-edamame" / "references" / "nutrition_data.json"
)
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "results_edamame_sample.json"


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
    assert "Ranked: 3 products" in out
    assert "Seapoint Farms" in out
    assert "The Only Bean" in out
    assert "Food to Live" in out


def test_food_to_live_bulk_wins_on_unit_cost():
    """6 lb bulk at $44.99 should beat the 27 oz jar at $18.79 on $/g protein."""
    out = _run_rank()
    rows = [
        line
        for line in out.splitlines()
        if line.startswith("|") and "---" not in line and "Product" not in line
    ]
    assert "Food to Live" in rows[0], (
        f"expected Food to Live 6 lb at top of $/g ranking, got: {rows[0]}"
    )


def test_output_includes_amazon_purchase_url():
    out = _run_rank()
    assert "[link](https://www.amazon.com/dp/B0094IXKME)" in out
