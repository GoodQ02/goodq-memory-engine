from __future__ import annotations

from pathlib import Path


def test_default_models_dir_uses_models_cache_key(monkeypatch, tmp_path: Path):
    from scripts import cache_readiness_check

    monkeypatch.setattr(cache_readiness_check, "load_configs", lambda _overrides=None: {"paths": {}})
    monkeypatch.setattr(
        cache_readiness_check,
        "get_runtime_paths",
        lambda _cfg, *args, **kwargs: {"models_cache": str(tmp_path / "models")},
    )

    resolved = cache_readiness_check._default_models_dir()

    assert resolved == tmp_path / "models"


def test_nrc_emotion_lexicon_is_optional_in_cache_inventory(tmp_path: Path):
    from scripts import cache_readiness_check

    inventory = cache_readiness_check.build_inventory(tmp_path / "models")
    by_name = {item.name: item for item in inventory}

    assert by_name["NRC-Emotion-Lexicon"].optional is True
