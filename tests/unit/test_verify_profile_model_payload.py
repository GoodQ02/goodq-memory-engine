from __future__ import annotations

import hashlib
import json
import socket
import types
from pathlib import Path

import pytest
import yaml

from scripts.install import verify_profile_model_payload as verifier


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_fixture(
    root: Path,
    *,
    probe: str = "fixture_probe",
    hardware_profile: str = "cpu_gpu",
    model_filename: str = "model.safetensors",
) -> tuple[Path, Path, Path]:
    install_dir = root / "install"
    models_root = root / "data" / "models"
    config_root = install_dir / "configs"
    runtime_root = models_root / "hub" / "models--example--model" / "snapshots" / "rev-1"
    config_root.mkdir(parents=True)
    runtime_root.mkdir(parents=True)
    payload = b"installed-model"
    model_path = runtime_root / model_filename
    model_path.write_bytes(payload)
    relative = model_path.relative_to(models_root).as_posix()
    member_manifest = {
        "schema_version": 2,
        "profile": "PUBLIC_GPU_ENHANCED",
        "member_count": 1,
        "members": [
            {
                "path": relative,
                "size_bytes": len(payload),
                "sha256": _sha256(payload),
                "asset_id": "example_model",
                "source_manifest_sha256": "a" * 64,
                "provenance": {
                    "type": "sealed_source_copy",
                    "source_path": model_filename,
                    "source_sha256": _sha256(payload),
                },
            }
        ],
    }
    member_manifest["inventory_sha256"] = hashlib.sha256(
        json.dumps(
            member_manifest["members"], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    member_path = config_root / "model_member_manifest.json"
    member_path.write_text(
        json.dumps(member_manifest, sort_keys=True) + "\n", encoding="utf-8"
    )
    selected = {
        "schema_version": 2,
        "profile": "PUBLIC_GPU_ENHANCED",
        "distribution": "public",
        "selected_asset_ids": ["example_model"],
        "selector_sha256": "1" * 64,
        "asset_inventory_sha256": "2" * 64,
        "payload_asset_ids": ["example_model"],
        "payloads": [
            {
                "asset_id": "example_model",
                "delivery": "huggingface_cache",
                "repo_id": "example/model",
                "revision": "rev-1",
                "runtime_path": runtime_root.relative_to(models_root).as_posix(),
            }
        ],
        "asset_closure": {
            "capability_dispositions": {
                "local_vlm": {"status": "policy_excluded"},
                "local_llm_serving": {"status": "policy_excluded"},
            },
            "assets_by_id": {
                "example_model": {
                    "asset_id": "example_model",
                    "kind": "model",
                    "revision": "rev-1",
                    "probe": probe,
                    "runtime_owner": "fixture.owner",
                    "hardware_profile": hardware_profile,
                }
            },
        },
        "model_member_manifest": {
            "path": "model_member_manifest.json",
            "sha256": verifier._sha256(member_path),
            "inventory_sha256": member_manifest["inventory_sha256"],
            "member_count": 1,
        },
    }
    (config_root / "selected_capabilities.json").write_text(
        json.dumps(selected, sort_keys=True) + "\n", encoding="utf-8"
    )
    return install_dir, models_root, model_path


def test_shallow_cache_resolution_is_not_a_load_probe(tmp_path: Path) -> None:
    install_dir, models_root, _model_path = _write_fixture(tmp_path)

    with pytest.raises(ValueError, match="missing installed model probe"):
        verifier.verify(
            install_dir=install_dir,
            models_root=models_root,
            probe_loaders={},
        )


def test_exact_installed_path_is_loaded_offline_and_recorded(tmp_path: Path) -> None:
    install_dir, models_root, model_path = _write_fixture(tmp_path)
    observed: list[tuple[Path, str]] = []

    def fixture_probe(path: Path, device: str) -> dict[str, object]:
        observed.append((path, device))
        assert verifier._offline_environment_is_set()
        return {"device": device, "output": {"classification": "fixture-ok"}}

    receipt = verifier.verify(
        install_dir=install_dir,
        models_root=models_root,
        probe_loaders={"fixture_probe": fixture_probe},
    )

    assert observed == [(model_path.parent, "cpu")]
    assert receipt["status"] == "ok"
    assert receipt["network_attempt_count"] == 0
    assert receipt["probes"][0]["asset_id"] == "example_model"
    assert receipt["probes"][0]["runtime_path"] == model_path.parent.relative_to(
        models_root
    ).as_posix()
    assert receipt["probes"][0]["output"] == {"classification": "fixture-ok"}


def test_member_hash_drift_fails_before_probe(tmp_path: Path) -> None:
    install_dir, models_root, model_path = _write_fixture(tmp_path)
    model_path.write_bytes(b"drifted")
    called = False

    def fixture_probe(path: Path, device: str) -> dict[str, object]:
        nonlocal called
        called = True
        return {"device": device, "output": {}}

    with pytest.raises(ValueError, match="installed member (size|hash) mismatch"):
        verifier.verify(
            install_dir=install_dir,
            models_root=models_root,
            probe_loaders={"fixture_probe": fixture_probe},
        )
    assert called is False


def test_transformer_probe_rejects_bin_only_installed_weights(tmp_path: Path) -> None:
    install_dir, models_root, _model_path = _write_fixture(
        tmp_path,
        probe="transformers_text_classification",
        model_filename="pytorch_model.bin",
    )

    with pytest.raises(ValueError, match="requires installed safetensors weights"):
        verifier.verify(
            install_dir=install_dir,
            models_root=models_root,
            probe_loaders={
                "transformers_text_classification": lambda path, device: {
                    "device": device,
                    "output": {},
                }
            },
        )


def test_gpu_required_probe_rejects_effective_cpu_device(tmp_path: Path) -> None:
    install_dir, models_root, _model_path = _write_fixture(
        tmp_path,
        hardware_profile="gpu",
    )

    with pytest.raises(ValueError, match="required cuda but reported cpu"):
        verifier.verify(
            install_dir=install_dir,
            models_root=models_root,
            probe_loaders={
                "fixture_probe": lambda path, device: {
                    "device": "cpu",
                    "output": {},
                }
            },
        )


def test_network_attempt_is_terminal(tmp_path: Path) -> None:
    install_dir, models_root, _model_path = _write_fixture(tmp_path)

    def network_probe(path: Path, device: str) -> dict[str, object]:
        socket.create_connection(("example.com", 443), timeout=0.1)
        return {"device": device, "output": {}}

    with pytest.raises(ValueError, match="network access blocked during offline model probe"):
        verifier.verify(
            install_dir=install_dir,
            models_root=models_root,
            probe_loaders={"fixture_probe": network_probe},
        )


def test_pyannote_probe_uses_exact_installed_path_in_preserved_wsl(
    monkeypatch,
    tmp_path: Path,
) -> None:
    installed_path = tmp_path / "models" / "pyannote"
    installed_path.mkdir(parents=True)
    calls: list[list[str]] = []
    responses = [
        types.SimpleNamespace(
            returncode=0,
            stdout="/mnt/c/ProgramData/GoodQ4All/models/pyannote\n",
            stderr="",
        ),
        types.SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "device": "cpu",
                    "output": {
                        "classification": "pipeline_open",
                        "type": "SpeakerDiarization",
                    },
                }
            )
            + "\n",
            stderr="",
        ),
    ]

    def fake_run(command, **kwargs):
        calls.append(list(command))
        return responses.pop(0)

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", "/home/goodq/goodq_audio")

    result = verifier._probe_pyannote_via_wsl(
        installed_path,
        "cpu",
        kind="pipeline",
    )

    assert calls[0][:4] == ["wsl", "-d", "Ubuntu-22.04", "--"]
    assert calls[0][4:8] == ["wslpath", "-a", "-u", str(installed_path.resolve())]
    assert calls[1][:5] == ["wsl", "-d", "Ubuntu-22.04", "--", "env"]
    bash_index = calls[1].index("bash")
    assert calls[1][bash_index + 1] == "-lc"
    assert "GOODQ_PROBE_WORKSPACE=/home/goodq/goodq_audio" in calls[1][:bash_index]
    assert "HF_HUB_OFFLINE=1" in calls[1][:bash_index]
    assert calls[1][-3:] == [
        "/mnt/c/ProgramData/GoodQ4All/models/pyannote",
        "pipeline",
        "cpu",
    ]
    assert "/mnt/c/ProgramData/GoodQ4All/models/pyannote" not in calls[1][bash_index + 2]
    assert result["output"]["classification"] == "pipeline_open"


def test_pyannote_probe_keeps_shell_metacharacters_in_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Workspace and model paths must never become executable shell source."""

    installed_path = tmp_path / "models" / "pyannote"
    installed_path.mkdir(parents=True)
    workspace = '/home/good q/"quoted";$(touch /tmp/workspace);`id`'
    translated_path = '/mnt/c/Good Q/"model";$(touch /tmp/model);`id`'
    calls: list[list[str]] = []
    responses = [
        types.SimpleNamespace(
            returncode=0,
            stdout=translated_path + "\n",
            stderr="",
        ),
        types.SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "device": "cuda",
                    "output": {
                        "classification": "model_open",
                        "type": "Model",
                    },
                }
            )
            + "\n",
            stderr="",
        ),
    ]

    def fake_run(command, **kwargs):
        calls.append(list(command))
        return responses.pop(0)

    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    monkeypatch.setenv("GOODQ_WSL_DISTRO", "Ubuntu-22.04")
    monkeypatch.setenv("GOODQ_WSL_WORKSPACE", workspace)

    result = verifier._probe_pyannote_via_wsl(
        installed_path,
        "cuda",
        kind="model",
    )

    command = calls[1]
    bash_index = command.index("bash")
    static_shell = command[bash_index + 2]
    assert f"GOODQ_PROBE_WORKSPACE={workspace}" in command[:bash_index]
    assert command[-3:] == [translated_path, "model", "cuda"]
    assert workspace not in static_shell
    assert translated_path not in static_shell
    assert result["output"]["classification"] == "model_open"


def test_repository_model_probe_contract_is_fully_implemented() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    contract = yaml.safe_load(
        (repo_root / "configs" / "installer_profile_contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    model_probes = {
        str(record["probe"])
        for record in contract["asset_contracts"].values()
        if str(record["probe"]).startswith(
            ("transformers_", "faster_whisper_", "opencv_", "pyannote_", "sentence_", "silero_")
        )
    }

    assert model_probes <= set(verifier.DEFAULT_PROBE_LOADERS)
    assert "local_vlm" not in verifier.DEFAULT_PROBE_LOADERS
