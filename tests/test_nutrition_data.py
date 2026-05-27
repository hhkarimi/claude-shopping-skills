"""Schema validation for nutrition_data.json files. Catches typos and
implausible values at CI time, before they crash the ranker."""

import json
from pathlib import Path

import pytest

# Single source of truth — same constant the ranker uses.
from ranking import REQUIRED_NUTRITION_KEYS

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEYS = set(REQUIRED_NUTRITION_KEYS)
POSITIVE_NUMERIC_KEYS = (
    "servings_per_container",
    "protein_per_serving_g",
    "calories_per_serving",
    "leucine_per_serving_g",
)

NUTRITION_FILES = sorted(
    (REPO_ROOT / "skills").glob("rank-*/references/nutrition_data.json")
)


@pytest.mark.parametrize(
    "path", NUTRITION_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_nutrition_data_schema(path: Path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    assert data, f"{path}: empty"
    for asin, entry in data.items():
        # ASIN format
        assert len(asin) == 10 and asin.startswith("B"), (
            f"{path}: invalid ASIN {asin!r}"
        )

        # Required keys present
        missing = REQUIRED_KEYS - set(entry.keys())
        assert not missing, f"{path}/{asin}: missing keys {missing}"

        # Numeric fields are positive
        for k in POSITIVE_NUMERIC_KEYS:
            v = entry[k]
            assert isinstance(v, (int, float)) and v > 0, (
                f"{path}/{asin}: {k}={v!r} must be a positive number"
            )

        # Leucine can't exceed total protein
        assert entry["leucine_per_serving_g"] < entry["protein_per_serving_g"], (
            f"{path}/{asin}: leucine ({entry['leucine_per_serving_g']}g) "
            f">= protein ({entry['protein_per_serving_g']}g)"
        )

        # Calorie:protein ratio sanity-check (pure protein is 4 cal/g; real
        # foods top out around 20 cal/g for high-fat bars). Outside this
        # range is almost certainly a typo.
        ratio = entry["calories_per_serving"] / entry["protein_per_serving_g"]
        assert 3.5 < ratio < 25, (
            f"{path}/{asin}: cal:protein ratio {ratio:.2f} outside plausible "
            f"range (3.5-25) — likely a data entry error"
        )
