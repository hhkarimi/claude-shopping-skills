"""Enforce that every skills/rank-*/scripts/rank.py is a thin wrapper.

If a future contributor adds skill-specific logic to a wrapper (instead of
extending lib/ranking.py), tests here catch it. Replaces the byte-equality
test that existed before the lib/ extraction."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WRAPPERS = sorted((REPO_ROOT / "skills").glob("rank-*/scripts/rank.py"))


def test_wrappers_discovered():
    assert WRAPPERS, "expected at least one skills/rank-*/scripts/rank.py wrapper"


def test_wrappers_have_no_logic():
    """Wrappers must not define functions or classes — all logic in ranking.py."""
    forbidden = re.compile(r"^(def |class |for |while |try:)", re.MULTILINE)
    for w in WRAPPERS:
        body = w.read_text(encoding="utf-8")
        offenders = forbidden.findall(body)
        assert not offenders, (
            f"{w.relative_to(REPO_ROOT)} contains logic ({offenders!r}). "
            f"Move it into .claude-plugin/lib/ranking.py — wrappers must stay thin."
        )


def test_wrappers_import_from_ranking():
    """Every wrapper must call into the shared module — no copy-paste logic."""
    for w in WRAPPERS:
        body = w.read_text(encoding="utf-8")
        assert "from ranking import" in body, (
            f"{w.relative_to(REPO_ROOT)} doesn't import from ranking module"
        )
        assert "run_cli" in body, f"{w.relative_to(REPO_ROOT)} doesn't invoke run_cli"
