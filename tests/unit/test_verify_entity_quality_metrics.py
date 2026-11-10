from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_private_entity_quality_script_is_excluded_from_public_source() -> None:
    # Private dev exercises scripts/internal/verify_entity_quality.py directly.
    # Public source omits scripts/internal/ and verifies that exclusion here.
    assert not (REPO_ROOT / "scripts/internal/verify_entity_quality.py").exists()
