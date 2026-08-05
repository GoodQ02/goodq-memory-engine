from __future__ import annotations

import json


def test_load_step_config_overlays_isolated_witness_values_on_runtime_defaults(
    monkeypatch,
    tmp_path,
) -> None:
    from cli import step_runner

    witness_cfg = tmp_path / "witness-config.json"
    witness_cfg.write_text(
        json.dumps({"paths": {"data_root": "C:/isolated/data"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        step_runner,
        "load_cfg",
        lambda overrides=None: {
            "audio": {"transcribe": {"model": "small", "chunk_seconds": 10}},
            "paths": {"data_root": "C:/default/data", "models_cache": "C:/models"},
        },
    )

    resolved = step_runner.load_step_config(witness_cfg)

    assert resolved["audio"]["transcribe"]["model"] == "small"
    assert resolved["paths"] == {
        "data_root": "C:/isolated/data",
        "models_cache": "C:/models",
    }
