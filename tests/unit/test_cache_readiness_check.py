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
