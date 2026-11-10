"""Contract tests for the sealed OpenCV Zoo object-detection replacement."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

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


def test_object_detector_selects_yolox_when_installed_and_nanodet_otherwise(monkeypatch) -> None:
    """YOLOX met the frozen criteria on CPU and CUDA; NanoDet covers only missing packs."""

    from steps.object_detect import step

    monkeypatch.setattr(step, "_sealed_model_path", lambda model: Path(model))
    assert step._select_model_id({}) == "opencv_yolox"

    def missing(model):
        if model == step.GPU_MODEL_ID:
            raise step.DetectorUnavailable("not installed")
        return Path(model)

    monkeypatch.setattr(step, "_sealed_model_path", missing)
    assert step._select_model_id({}) == "opencv_nanodet"


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


def test_cuda_inference_failure_retries_same_yolox_model_on_cpu_with_receipt(tmp_path, monkeypatch) -> None:
    """A CUDA execution error degrades only to the same model on CPU, visibly."""

    from steps.object_detect import step

    source = tmp_path / "frame.jpg"
    source.write_bytes(b"fixture")
    gpu_runtime = step.DetectorRuntime(model_id=step.GPU_MODEL_ID, device="cuda", net=object(), engine=step.YOLOX_ENGINE)
    cpu_runtime = step.DetectorRuntime(model_id=step.GPU_MODEL_ID, device="cpu", net=object(), engine=step.YOLOX_ENGINE)
    monkeypatch.setattr(step, "_select_model_id", lambda _cfg: step.GPU_MODEL_ID)
    monkeypatch.setattr(step, "_load_detector", lambda _cfg: gpu_runtime)
    monkeypatch.setattr(step, "_load_yolox_cpu", lambda: cpu_runtime)
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
        "engine": "onnxruntime",
        "model": "opencv_yolox",
        "device": "cpu",
        "fallback_from": "opencv_yolox:cuda",
        "fallback_reason": "CUDA inference failed",
    }


class _FakeSession:
    def __init__(self, providers):
        self._providers = providers
        self.fallback_disabled = False

    def disable_fallback(self):
        self.fallback_disabled = True

    def get_providers(self):
        return self._providers

    def get_inputs(self):
        return [SimpleNamespace(name="images")]

    def get_outputs(self):
        return [SimpleNamespace(name="output")]


def _fake_ort(available, session_providers, preloads):
    sessions = []

    def inference_session(path, providers):
        session = _FakeSession(session_providers(providers))
        sessions.append((path, providers, session))
        return session

    return SimpleNamespace(
        get_available_providers=lambda: available,
        preload_dlls=lambda: preloads.append(True),
        InferenceSession=inference_session,
    ), sessions


@pytest.mark.parametrize("available,session_providers,expected_device,expect_fallback", [
    (["CUDAExecutionProvider", "CPUExecutionProvider"], lambda requested: requested + ["CPUExecutionProvider"], "cuda", False),
    (["CPUExecutionProvider"], lambda requested: requested, "cpu", False),
    # CUDA requested but the session silently initialized on CPU: never accepted as CUDA.
    (["CUDAExecutionProvider", "CPUExecutionProvider"], lambda requested: ["CPUExecutionProvider"], "cpu", True),
])
def test_yolox_runtime_verifies_the_provider_it_actually_uses(
    tmp_path, monkeypatch, available, session_providers, expected_device, expect_fallback,
):
    """A provider list is not proof of CUDA execution; the session must confirm it."""
    from steps.object_detect import step

    source = tmp_path / "frame.jpg"
    source.write_bytes(b"fixture")
    preloads = []
    ort, sessions = _fake_ort(available, session_providers, preloads)
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setattr(step, "_RUNTIMES", {})
    monkeypatch.delenv("GOODQ_OBJECT_DETECT_FORCE_CPU", raising=False)
    monkeypatch.setattr(step, "_force_cpu", lambda env=None: False)
    monkeypatch.setattr(step, "_sealed_model_path", lambda model: Path(model))
    monkeypatch.setattr(step, "_detect_with_runtime",
                        lambda runtime, path: [{"bbox": [1, 2, 30, 40], "label": "person", "score": 0.9}])

    result = step.object_detect({"source_path": str(source)}, {})
    meta = result["detect_meta"]

    assert meta["status"] == "ok"
    assert meta["model"] == "opencv_yolox"
    assert meta["engine"] == "onnxruntime"
    assert meta["device"] == expected_device
    if "CUDAExecutionProvider" in available:
        assert preloads, "CUDA libraries must be preloaded before creating a CUDA session"
        assert sessions[0][1] == ["CUDAExecutionProvider"]
        assert sessions[0][2].fallback_disabled
    if expect_fallback:
        assert meta["fallback_from"] == "opencv_yolox:cuda"
        assert "did not initialize selected provider" in meta["fallback_reason"]
    else:
        assert "fallback_from" not in meta
