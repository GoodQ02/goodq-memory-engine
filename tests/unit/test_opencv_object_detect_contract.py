"""Contract tests for the sealed OpenCV Zoo object-detection replacement."""

from __future__ import annotations

from pathlib import Path

from steps.common.model_provisioner import lookup_model


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_opencv_object_models_are_bundled_only_pinned_registry_entries() -> None:
    """The public detector models must never be first-use downloads."""

    for model_id in ("opencv_nanodet", "opencv_yolox"):
        resolved_id, metadata = lookup_model(model_id)

        assert resolved_id == model_id
        assert metadata["is_external"] is True
        assert metadata["acquisition_policy"] == "bundled_only"
        assert len(metadata["sha256"]) == 64
        assert metadata["file_size_bytes"] > 1_000_000


def test_active_object_detection_seam_has_no_ultralytics_dependency() -> None:
    """AGPL Ultralytics must not be reintroduced into the distributable path."""

    active_paths = (
        REPO_ROOT / "steps" / "object_detect" / "step.py",
        REPO_ROOT / "scripts" / "bootstrap_models.py",
        REPO_ROOT / "envs" / "object_detect" / "requirements.txt",
        REPO_ROOT / "envs" / "locks" / "object_detect.lock.txt",
        REPO_ROOT / "scripts" / "diagnostics" / "native_model_stability_smoke.py",
    )
    for path in active_paths:
        assert "ultralytics" not in path.read_text(encoding="utf-8").casefold(), path


def test_object_detector_selects_cpu_nanodet_and_gpu_yolox(monkeypatch) -> None:
    """The CPU-safe baseline and GPU quality paths have explicit model identities."""

    from steps.object_detect import step

    monkeypatch.setattr(step, "setup_step_gpu", lambda _step: {"device": "cpu"})
    assert step._select_model_id({}) == "opencv_nanodet"

    monkeypatch.setattr(step, "setup_step_gpu", lambda _step: {"device": "cuda:0"})
    assert step._select_model_id({}) == "opencv_yolox"


def test_object_detector_emits_existing_payload_contract_with_engine_provenance(tmp_path, monkeypatch) -> None:
    """A detector result remains graph-compatible while identifying the producing model."""

    from steps.object_detect import step

    source = tmp_path / "frame.jpg"
    source.write_bytes(b"fixture")
    runtime = object()
    monkeypatch.setattr(step, "_load_detector", lambda _cfg: runtime)
    monkeypatch.setattr(
        step,
        "_detect_with_runtime",
        lambda _runtime, _path: [{"bbox": [1, 2, 30, 40], "label": "person", "score": 0.9}],
    )
    monkeypatch.setattr(step, "_runtime_metadata", lambda _runtime: {"engine": "opencv-dnn", "model": "opencv_nanodet", "device": "cpu"})

    result = step.object_detect({"source_path": str(source)}, {})

    assert result["objects"] == [{"bbox": [1, 2, 30, 40], "label": "person", "score": 0.9}]
    assert result["detect_meta"] == {
        "status": "ok",
        "engine": "opencv-dnn",
        "model": "opencv_nanodet",
        "device": "cpu",
    }


def test_gpu_inference_failure_retries_sealed_cpu_detector_with_receipt(tmp_path, monkeypatch) -> None:
    """A GPU execution error may degrade only through the visible NanoDet path."""

    from steps.object_detect import step

    source = tmp_path / "frame.jpg"
    source.write_bytes(b"fixture")
    gpu_runtime = step.DetectorRuntime(model_id=step.GPU_MODEL_ID, device="cuda", net=object())
    cpu_runtime = step.DetectorRuntime(model_id=step.CPU_MODEL_ID, device="cpu", net=object())
    monkeypatch.setattr(step, "_select_model_id", lambda _cfg: step.GPU_MODEL_ID)
    monkeypatch.setattr(step, "_load_detector", lambda _cfg: gpu_runtime)
    monkeypatch.setattr(step, "_load_cpu_detector", lambda _cfg: cpu_runtime)
    monkeypatch.setattr(
        step,
        "_runtime_metadata",
        lambda runtime: {
            "engine": "opencv-dnn",
            "model": step.GPU_MODEL_ID if runtime is gpu_runtime else step.CPU_MODEL_ID,
            "device": "cuda" if runtime is gpu_runtime else "cpu",
        },
    )
    calls = []

    def detect(runtime, _path):
        calls.append(runtime)
        if runtime is gpu_runtime:
            raise RuntimeError("CUDA inference failed")
        return [{"bbox": [1, 2, 30, 40], "label": "person", "score": 0.9}]

    monkeypatch.setattr(step, "_detect_with_runtime", detect)

    result = step.object_detect({"source_path": str(source)}, {})

    assert calls == [gpu_runtime, cpu_runtime]
    assert result["detect_meta"] == {
        "status": "ok",
        "engine": "opencv-dnn",
        "model": "opencv_nanodet",
        "device": "cpu",
        "fallback_from": "opencv_yolox",
        "fallback_reason": "CUDA inference failed",
    }
