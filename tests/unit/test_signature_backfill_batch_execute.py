import json
import subprocess
from pathlib import Path

import pytest


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _scene(scene_id: str, index: int, audio: Path) -> dict:
    return {
        "scene_id": scene_id,
        "index": index,
        "audio": {
            "path": str(audio),
            "diarization_status": "success",
            "diarization": [
                {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.1},
                {"speaker": "SPEAKER_00", "start": 3.0, "end": 5.2},
            ],
            "speaker_voice_signature_meta": {"status": "error", "reason": "embedding_step_failed"},
        },
    }


def _fixture(tmp_path: Path) -> tuple[Path, list[str]]:
    processing = tmp_path / "epoch" / "processing"
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")
    ids = ["scene-a", "scene-b", "scene-c"]
    manifest = processing / "video-a" / "video" / "scene_manifest.json"
    temporal = processing / "video-a" / "temporal_index.json"
    _write(manifest, {"video_id": "video-a", "scenes": [_scene(scene_id, index, audio) for index, scene_id in enumerate(ids)]})
    _write(temporal, {"segments": [{"scene_id": scene_id} for scene_id in ids]})
    return processing, ids


def _proof(scene_id: str) -> dict:
    return {
        "status": "success",
        "mode": "signature_only",
        "speaker_voice_signatures": [{"speaker": "SPEAKER_00", "embedding_dim": 768}],
        "speaker_voice_signature_meta": {"status": "ok", "scene_id": scene_id},
    }


def test_batch_plan_is_token_bound_and_deterministic(tmp_path: Path) -> None:
    from cli.signature_backfill_batch_execute import build_execution_plan, plan_digest

    processing, ids = _fixture(tmp_path)
    plan = build_execution_plan(processing, batch_index=1, batch_size=2)

    assert plan["scene_ids"] == ids[:2]
    assert plan["scene_count"] == 2
    assert plan["execution_policy"]["stop_on_first_error"] is True
    assert plan == build_execution_plan(processing, batch_index=1, batch_size=2)
    assert len(plan_digest(plan)) == 64


def test_executor_refuses_rebased_batch_index_that_would_skip_eligible_scenes(tmp_path: Path) -> None:
    from cli.signature_backfill_batch_execute import BatchExecutionError, build_execution_plan

    processing, _ = _fixture(tmp_path)

    with pytest.raises(BatchExecutionError, match="batch_index=1"):
        build_execution_plan(processing, batch_index=2, batch_size=2)


def test_batch_executor_rejects_wrong_token_without_running_proofs(tmp_path: Path) -> None:
    from cli.signature_backfill_batch_execute import BatchExecutionError, build_execution_plan, execute_batch

    processing, _ = _fixture(tmp_path)
    plan = build_execution_plan(processing, batch_index=1, batch_size=2)
    calls: list[str] = []

    with pytest.raises(BatchExecutionError, match="confirmation token"):
        execute_batch(plan, "wrong", proof_runner=lambda request: calls.append(request["scene_id"]))
    assert calls == []


def test_batch_executor_stops_on_first_proof_failure_without_promoting_later_scene(tmp_path: Path) -> None:
    from cli.signature_backfill_batch_execute import BatchExecutionError, build_execution_plan, execute_batch, plan_digest

    processing, ids = _fixture(tmp_path)
    plan = build_execution_plan(processing, batch_index=1, batch_size=3)
    calls: list[str] = []

    def runner(request: dict) -> dict:
        calls.append(request["scene_id"])
        if request["scene_id"] == ids[1]:
            raise RuntimeError("proof failed")
        return _proof(request["scene_id"])

    with pytest.raises(BatchExecutionError, match="stopped after scene failure"):
        execute_batch(plan, plan_digest(plan), proof_runner=runner)
    assert calls == ids[:2]
    manifest = json.loads((processing / "video-a" / "video" / "scene_manifest.json").read_text(encoding="utf-8"))
    assert manifest["scenes"][0]["audio"]["speaker_voice_signature_meta"]["status"] == "ok"
    assert manifest["scenes"][1]["audio"]["speaker_voice_signature_meta"]["status"] == "error"
    assert manifest["scenes"][2]["audio"]["speaker_voice_signature_meta"]["status"] == "error"


def test_batch_executor_records_all_scene_receipts_on_success(tmp_path: Path) -> None:
    from cli.signature_backfill_batch_execute import build_execution_plan, execute_batch, plan_digest

    processing, ids = _fixture(tmp_path)
    plan = build_execution_plan(processing, batch_index=1, batch_size=2)
    receipt = execute_batch(plan, plan_digest(plan), proof_runner=lambda request: _proof(request["scene_id"]))

    assert receipt["status"] == "signature_backfill_batch_committed"
    assert receipt["completed_scene_ids"] == ids[:2]
    assert len(receipt["scene_receipts"]) == 2
    assert Path(receipt["batch_root"]).is_dir()


def test_wsl_proof_sources_the_managed_cuda_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from cli.signature_backfill_batch_execute import _run_wsl_signature_proof

    proof_path = tmp_path / "proof.json"
    request = {
        "scene_id": "scene-a",
        "audio_path": str(tmp_path / "audio.wav"),
        "diarization_segments": [{"speaker": "SPEAKER_00", "start": 0.0, "end": 1.0}],
        "proof_result_path": str(proof_path),
    }
    Path(request["audio_path"]).write_bytes(b"audio")

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        assert "source ./setup_cuda_env.sh >/dev/null" in command[-1]
        proof_path.write_text(json.dumps({**_proof("scene-a"), "device": "cuda"}), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("cli.signature_backfill_batch_execute.subprocess.run", fake_run)
    proof = _run_wsl_signature_proof(request, {"wsl_distro": "Ubuntu-22.04", "wsl_workspace": "/home/test/goodq_audio"})

    assert proof["device"] == "cuda"
