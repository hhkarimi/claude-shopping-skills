# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Rank protein powders by $/g protein, cal:protein, and leucine-adjusted cost.

Thin wrapper over lib/ranking.py — see that module for the math and CLI.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from ranking import run_cli  # noqa: E402

if __name__ == "__main__":
    run_cli(description=__doc__.splitlines()[0])
