from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("step", "case", "meta_field", "expected_status", "expected_closure"),
    [
        ("object_detect", "missing_assets", "detect_meta", "skipped", "skipped"),
        ("face_embed", "missing_assets", "faces_meta", "skipped", "skipped"),
        ("face_embed", "fallback_output", "faces_meta", "ok", "ran_with_output"),
        ("face_embed", "fallback_error", "faces_meta", "error", "error"),
        ("object_detect", "primary_empty", "detect_meta", "not_applicable", "ran_content_appropriate_empty"),
        ("object_detect", "fallback_output", "detect_meta", "ok", "ran_with_output"),
        ("object_detect", "fallback_empty", "detect_meta", "not_applicable", "ran_content_appropriate_empty"),
        ("face_embed", "primary_empty", "faces_meta", "not_applicable", "ran_content_appropriate_empty"),
    ],
)
def test_vision_worker_cli_preserves_actual_outcome_in_terminal_receipt(
    monkeypatch, tmp_path: Path, step: str, case: str, meta_field: str,
    expected_status: str, expected_closure: str,
) -> None:
    from cli import run_ingestion, step_runner
    from steps.common import model_provisioner, step_logger
    from steps.face_embed import step as face_step
    from steps.object_detect import step as object_step

    cfg = {
        "paths": {"log_dir": str(tmp_path / "logs")},
        "run": {"id": "vision-capability-boundary"},
        "host": {"profile": "PERSONAL_AIR_GAP"},
        "gpu": {"clear_cache_before_step": False},
    }
    monkeypatch.setattr(step_runner, "load_step_config", lambda *_: cfg)
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "_CURRENT_RUN_CONTEXT", cfg["run"])
    gpu_module = types.ModuleType("common.gpu_manager")
    gpu_module.initialize_gpu_for_step = lambda **_: None
    monkeypatch.setitem(sys.modules, "common.gpu_manager", gpu_module)
    # Real worker/model-provisioning code sees an empty fixture cache. No model
    # or live GPU loads: OpenCV is not reached beyond the missing-asset check.
    cv2 = types.ModuleType("cv2")
    cv2.dnn = types.SimpleNamespace(
        DNN_BACKEND_CUDA=5, DNN_TARGET_CUDA=6, DNN_TARGET_CUDA_FP16=7,
        getAvailableTargets=lambda _: [6],
    )
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setattr(model_provisioner, "resolve_models_root", lambda: tmp_path / "models")
    monkeypatch.setattr(object_step, "setup_step_gpu", lambda _: {"device": "cuda"})
    monkeypatch.setattr(object_step, "_RUNTIMES", {})
    monkeypatch.delenv("GOODQ_OBJECT_DETECT_FORCE_CPU", raising=False)
    fallback_faces = [{"encoding": [0.1, 0.2], "embedding_dimension": 2}]

    def fallback(_path):
        if case == "fallback_error":
            raise RuntimeError("fixture fallback unavailable")
        return fallback_faces if case == "fallback_output" else []

    monkeypatch.setattr(face_step, "_face_recognition_embed", fallback)
    if case == "primary_empty":
        monkeypatch.setattr(face_step, "_opencv_yunet_sface_embed", lambda _: [])
        runtime = object_step.DetectorRuntime("opencv_yolox", "cuda", object(), engine="onnxruntime")
        monkeypatch.setattr(object_step, "_load_detector", lambda _: runtime)
        monkeypatch.setattr(object_step, "_detect_with_runtime", lambda *_: [])
    if step == "object_detect" and case.startswith("fallback_"):
        primary = object_step.DetectorRuntime("opencv_yolox", "cuda", object(), engine="onnxruntime")
        cpu = object_step.DetectorRuntime("opencv_yolox", "cpu", object(), engine="onnxruntime")
        monkeypatch.setattr(object_step, "_load_detector", lambda _: primary)
        monkeypatch.setattr(object_step, "_load_yolox_cpu", lambda: cpu)

        def detect(runtime, *_):
            if runtime is primary:
                raise RuntimeError("YOLOX CUDA inference failed")
            return [{"label": "person", "confidence": 0.9}] if case == "fallback_output" else []

        monkeypatch.setattr(object_step, "_detect_with_runtime", detect)

    source = tmp_path / "frame.jpg"
    source.write_bytes(b"fixture; inference is not invoked")
    item_path = tmp_path / "input.json"
    result_path = tmp_path / "result.json"
    item_path.write_text(json.dumps({"scene_id": "scene-1", "source_path": str(source)}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "step_runner", "--step", step, "--in", str(item_path), "--out", str(result_path),
    ])

    step_runner.main()
    receipt = run_ingestion._finalize_capability_receipt(
        terminal_status="completed", cfg=cfg,
        results=[{"scenes": [{"scene_id": "scene-1"}]}],
        output=tmp_path / "output" / "results.json",
    )

    worker = json.loads(result_path.read_text(encoding="utf-8"))
    row = json.loads((tmp_path / "logs" / "step_runs.jsonl").read_text(encoding="utf-8"))
    persisted = json.loads((tmp_path / "output" / "capability_receipt.json").read_text(encoding="utf-8"))
    capability = persisted["capabilities_by_step"][step]
    assert capability["status"] == expected_status
    assert capability["closure_status"] == expected_closure
    assert capability["status_surface"] == meta_field
    assert row["extra"]["result_meta"][meta_field] == worker[meta_field]
    assert receipt == persisted
    if case != "primary_empty":
        if not (step == "object_detect" and case.startswith("fallback_")):
            assert "Bundled-only external model" in str(worker[meta_field])
        assert receipt["outcome"] == "degraded"
    if step == "object_detect" and case.startswith("fallback_"):
        assert worker[meta_field]["fallback_from"] == "opencv_yolox:cuda"
        assert "CUDA" in worker[meta_field]["fallback_reason"]
        assert capability["requested_implementation"] == "opencv_yolox:cuda"
        assert capability["effective_implementation"] == "opencv_yolox:cpu"
        assert capability["fallback_chain"] == ["opencv_yolox:cpu"]
        assert receipt["summary"]["recovered_fallbacks"] == 1
        cfg["release_validation"] = {
            "content_truth_by_scene": {"scene-1": {"object": case == "fallback_output"}},
        }
        release = run_ingestion._finalize_capability_receipt(
            terminal_status="completed", cfg=cfg,
            results=[{"scenes": [{"scene_id": "scene-1"}]}],
            output=tmp_path / "release" / "results.json", input_count=1,
            release_validation=True,
        )
        assert release["capabilities_by_step"][step]["closure_status"] == (
            "ran_with_approved_fallback" if case == "fallback_output"
            else "ran_content_appropriate_empty"
        )
        assert release["summary"]["unapproved_fallbacks"] == 0
        assert release["summary"]["approved_fallbacks"] == 1
        # The partial worker probe still fails full-profile coverage.
        assert release["outcome"] == "failed"
        if case == "fallback_empty":
            cfg["release_validation"]["content_truth_by_scene"]["scene-1"]["object"] = True
            mismatch = run_ingestion._finalize_capability_receipt(
                terminal_status="completed", cfg=cfg,
                results=[{"scenes": [{"scene_id": "scene-1"}]}],
                output=tmp_path / "mismatch" / "results.json", input_count=1,
                release_validation=True,
            )
            assert mismatch["capabilities_by_step"][step]["closure_status"] == "content_truth_mismatch"
            assert mismatch["summary"]["approved_fallbacks"] == 0
            assert mismatch["outcome"] == "failed"
    if step == "face_embed" and case in {"missing_assets", "fallback_output"}:
        assert capability["requested_implementation"] == "opencv-yunet-sface"
        assert capability["effective_implementation"] == "face_recognition"
        assert capability["fallback_chain"] == ["face_recognition"]
        assert row["extra"]["embedding_emitted"] is (case == "fallback_output")
        release = run_ingestion._finalize_capability_receipt(
            terminal_status="completed", cfg=cfg,
            results=[{"scenes": [{"scene_id": "scene-1"}]}],
            output=tmp_path / "release" / "results.json", input_count=1,
            release_validation=True,
        )
        assert release["capabilities_by_step"][step]["closure_status"] == "unapproved_fallback"
        assert release["summary"]["approved_fallbacks"] == 0
        assert release["outcome"] == "failed"
