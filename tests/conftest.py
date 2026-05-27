"""Make the rank-protein-powders script importable as a module under tests/."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "rank-protein-powders" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "tests"))
