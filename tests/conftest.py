"""Make the rank-protein-powders script importable as a module under tests/."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Only add the scripts dir — pytest's rootdir discovery already handles
# imports under tests/, and adding tests/ to sys.path risks future shadowing.
sys.path.insert(0, str(REPO_ROOT / "skills" / "rank-protein-powders" / "scripts"))
