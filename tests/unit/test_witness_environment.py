from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from cli.witness_environment import (
    bootstrap_witness_environment,
    build_witness_environment,
)


def _snapshot(tmp_path):
    from cli.golden_witness import _isolated_runtime_snapshot

    root = tmp_path / "witness"
    models = tmp_path / "shared-models"
    models.mkdir()
    config = _isolated_runtime_snapshot(
        {
            "epoch_id": "epoch_witness_environment_test",
            "preflight": {"config": {
                "paths": {"models_cache": str(models)},
                "host": {"profile": "PUBLIC_GPU_ENHANCED", "require_gpu": True},
            }},
        },
        root,
    )
    path = root / "config" / "witness.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config), encoding="utf-8")
    return path, config


def _hostile_environment(tmp_path):
    env = dict(os.environ)
    for key in (
        "GOODQ_DATA_ROOT", "GOODQ_LOGS_ROOT", "GOODQ_TEMP_ROOT", "GOODQ_MODELS_ROOT",
        "GOODQ_MODELS_DIR", "GOODQ_IDENTITY_PATH", "GOODQ_MINI_AGENT_HOME",
        "GOODQ_TOOL_AUDIT_LOG", "GOODQ_CACHE_ROOT", "TEMP", "TMP",
        "GOODQ_WSL_AUDIO_OUTPUT_ROOT",
    ):
        env[key] = str(tmp_path / "outside" / key.lower())
    env.update({
        "GOODQ_EPOCH_ID": "epoch_operator_do_not_touch",
        "GOODQ_HOST_PROFILE": "GPU_ENHANCED",
        "GOODQ_REQUIRE_GPU": "1",
        "GOODQ_REQUIRE_WSL_AUDIO": "1",
        "HF_HUB_OFFLINE": "0",
        "TRANSFORMERS_OFFLINE": "0",
        "HF_DATASETS_OFFLINE": "0",
    })
    return env


def test_environment_binding_is_pure_and_preserves_selected_capabilities(tmp_path):
    snapshot, config = _snapshot(tmp_path)
    parent = _hostile_environment(tmp_path)
    before = dict(parent)
    process_before = dict(os.environ)

    child = build_witness_environment(snapshot, parent)

    assert parent == before
    assert dict(os.environ) == process_before
    assert not (snapshot.parents[1] / "temp").exists()
    assert child["GOODQ_EPOCH_ID"] == config["epoch_id"]
    assert Path(child["GOODQ_WITNESS_CONFIG"]) == snapshot.resolve()
    assert Path(child["GOODQ_WSL_AUDIO_OUTPUT_ROOT"]) == Path(config["paths"]["processing"]) / "wsl_audio"
    for key, cfg_key in (
        ("GOODQ_DATA_ROOT", "data_root"), ("GOODQ_LOGS_ROOT", "log_dir"),
        ("GOODQ_TEMP_ROOT", "processing"), ("GOODQ_MODELS_ROOT", "models_cache"),
        ("GOODQ_MODELS_DIR", "models_cache"),
    ):
        assert child[key] == config["paths"][cfg_key]
    for key in ("GOODQ_HOST_PROFILE", "GOODQ_REQUIRE_GPU", "GOODQ_REQUIRE_WSL_AUDIO"):
        assert child[key] == parent[key]
    assert child["HF_HUB_OFFLINE"] == child["TRANSFORMERS_OFFLINE"] == child["HF_DATASETS_OFFLINE"] == "1"


@pytest.mark.parametrize("invalid", ["epoch", "models", "models_ancestor", "data", "roster", "promotion", "root"])
def test_invalid_binding_fails_before_environment_or_temp_mutation(tmp_path, invalid):
    snapshot, config = _snapshot(tmp_path)
    root = snapshot.parents[1]
    if invalid == "epoch":
        config["epoch_id"] = "epoch_witness_../operator"
    elif invalid == "models":
        config["paths"]["models_cache"] = str(root / "models")
    elif invalid == "models_ancestor":
        config["paths"]["models_cache"] = str(tmp_path)
    elif invalid == "data":
        config["paths"]["data_root"] = str(tmp_path / "operator")
    elif invalid == "roster":
        config["identity_search"]["roster_path"] = str(tmp_path / "operator.yaml")
    elif invalid == "promotion":
        config["witness"]["promotion_enabled"] = True
    else:
        config["witness"]["artifact_root"] = str(tmp_path / "other-root")
    snapshot.write_text(json.dumps(config), encoding="utf-8")
    before = dict(os.environ)

    with pytest.raises(ValueError):
        build_witness_environment(snapshot, before)
    with pytest.raises(ValueError):
        bootstrap_witness_environment(["--config", str(snapshot)])

    assert dict(os.environ) == before
    assert not (root / "temp").exists()


@pytest.mark.parametrize("arguments", [["--config"], ["--config="], ["--config", "--help"], ["--config=a", "--config=b"]])
def test_invalid_config_arguments_fail_without_mutation(arguments):
    before = dict(os.environ)
    with pytest.raises(ValueError):
        bootstrap_witness_environment(arguments)
    assert dict(os.environ) == before


def test_no_explicit_config_keeps_normal_caller_environment():
    before = dict(os.environ)
    assert bootstrap_witness_environment(["--help"]) is False
    assert dict(os.environ) == before


def test_inherited_witness_without_explicit_config_fails_before_imports(tmp_path, monkeypatch):
    monkeypatch.setenv("GOODQ_WITNESS_CONFIG", str(tmp_path / "previous-witness.json"))
    before = dict(os.environ)
    with pytest.raises(ValueError, match="explicit.*--config"):
        bootstrap_witness_environment(["--input-file", str(tmp_path / "asset.mp4")])
    assert dict(os.environ) == before
    assert not (tmp_path / "temp").exists()


def test_real_cli_bootstrap_contains_import_state_and_child_projection(tmp_path):
    snapshot, config = _snapshot(tmp_path)
    env = _hostile_environment(tmp_path)
    # The production module's --help exits before processing inputs or models,
    # but still exercises the real pre-import bootstrap and progress singleton.
    script = """
import json, runpy, sys
from pathlib import Path
snapshot = sys.argv[1]
sys.argv = ['cli.run_ingestion', '--config', snapshot, '--help']
try:
    runpy.run_module('cli.run_ingestion', run_name='__main__')
except SystemExit as exc:
    assert exc.code in (None, 0), exc.code
from cli.step_runner import load_step_config
from steps.common.config_loader import get_runtime_paths
from steps.common.progress_tracker import get_tracker
cfg = load_step_config(snapshot)
get_runtime_paths(cfg, 'models_cache')
print('WITNESS_RESULT=' + json.dumps({
    'paths': cfg['paths'],
    'epoch_id': cfg['epoch_id'],
    'identity_search': cfg['identity_search'],
    'progress_file': str(get_tracker().progress_file),
    'profile': cfg['host']['profile'],
}))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(snapshot)],
        cwd=Path(__file__).resolve().parents[2], env=env,
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    marker = next(line for line in result.stdout.splitlines() if line.startswith("WITNESS_RESULT="))
    actual = json.loads(marker.partition("=")[2])
    assert actual["epoch_id"] == config["epoch_id"]
    for key, value in config["identity_search"].items():
        assert actual["identity_search"][key] == value
    assert actual["profile"] == "PUBLIC_GPU_ENHANCED"
    for key, value in config["paths"].items():
        assert Path(actual["paths"][key]).resolve() == Path(value).resolve(), key
    assert Path(actual["progress_file"]) == Path(config["paths"]["log_dir"]) / "progress.json"
    assert not (tmp_path / "outside").exists()


def test_remote_witness_passes_bound_environment_to_runner(tmp_path, monkeypatch):
    from cli import remote_witness

    snapshot, config = _snapshot(tmp_path)
    root = snapshot.parents[1]
    remote_snapshot = root / "config" / "witness-config.json"
    remote_snapshot.write_text(snapshot.read_text(), encoding="utf-8")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fixture")
    for key, value in _hostile_environment(tmp_path).items():
        if key.startswith("GOODQ_"):
            monkeypatch.setenv(key, value)
    monkeypatch.setattr(remote_witness, "prepare_witness_run", lambda *_: {})
    monkeypatch.setattr(remote_witness, "seal_prepared_receipt", lambda *_: root / "prepared-receipt.json")
    monkeypatch.setattr(remote_witness, "_start_isolated_qdrant", lambda *_: type("Q", (), {"pid": 23})())
    monkeypatch.setattr(remote_witness, "_stop_isolated_qdrant", lambda *_: None)
    captured = {}

    class Process:
        pid = 42
        def wait(self):
            return 0

    def capture(*_args, **kwargs):
        captured.update(kwargs["env"])
        return Process()

    monkeypatch.setattr(remote_witness.subprocess, "Popen", capture)
    assert remote_witness.execute(root, source) == 0
    assert captured["GOODQ_LOGS_ROOT"] == config["paths"]["log_dir"]
    assert captured["GOODQ_DATA_ROOT"] == config["paths"]["data_root"]
    assert captured["GOODQ_EPOCH_ID"] == config["epoch_id"]
    assert captured["GOODQ_REQUIRE_WSL_AUDIO"] == "1"
