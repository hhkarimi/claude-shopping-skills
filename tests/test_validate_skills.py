"""Unit tests for tests/validate_skills.py."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "tests" / "validate_skills.py"


def _make_skill(dir_path: Path, frontmatter: str) -> None:
    (dir_path / "skills" / "fake-skill").mkdir(parents=True, exist_ok=True)
    (dir_path / "skills" / "fake-skill" / "SKILL.md").write_text(
        f"---\n{frontmatter}\n---\n\n# Fake skill\n"
    )


def _run(repo_root: Path) -> subprocess.CompletedProcess:
    # Copy validator into the fake repo so it resolves paths from there.
    validator_copy = repo_root / "tests" / "validate_skills.py"
    validator_copy.parent.mkdir(parents=True, exist_ok=True)
    validator_copy.write_text(VALIDATOR.read_text())
    return subprocess.run(
        [sys.executable, str(validator_copy)],
        capture_output=True,
        text=True,
    )


def test_passes_with_valid_frontmatter(tmp_path: Path):
    _make_skill(tmp_path, "name: fake-skill\ndescription: A test skill.")
    proc = _run(tmp_path)
    assert proc.returncode == 0
    # Assert count too — guards against the validator passing on 0 files.
    assert "OK: 1 SKILL.md" in proc.stdout


def test_fails_without_name(tmp_path: Path):
    _make_skill(tmp_path, "description: Missing name.")
    proc = _run(tmp_path)
    assert proc.returncode == 1
    assert "missing keys" in proc.stderr
    assert "name" in proc.stderr


def test_fails_without_frontmatter(tmp_path: Path):
    (tmp_path / "skills" / "fake-skill").mkdir(parents=True)
    (tmp_path / "skills" / "fake-skill" / "SKILL.md").write_text("# Just a heading\n")
    proc = _run(tmp_path)
    assert proc.returncode == 1
    assert "missing frontmatter" in proc.stderr


def test_real_skills_pass():
    """The actual SKILL.md files in this repo must pass validation."""
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
