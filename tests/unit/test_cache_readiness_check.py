from __future__ import annotations

from pathlib import Path


def test_nrc_emotion_lexicon_is_optional_in_cache_inventory(tmp_path: Path):
    from scripts import cache_readiness_check

    inventory = cache_readiness_check.build_inventory(tmp_path / "models")
    by_name = {item.name: item for item in inventory}

    assert by_name["NRC-Emotion-Lexicon"].optional is True
