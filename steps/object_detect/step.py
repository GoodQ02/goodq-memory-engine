"""Sealed OpenCV Zoo object detection with a stable GoodQ payload contract.

YOLOX (the sealed ``opencv_yolox`` ONNX asset) runs through ONNX Runtime on
CUDA when the detector runtime exposes it, otherwise on CPU; a CUDA failure
retries the same model on CPU and records the fallback. NanoDet is used only
when the YOLOX pack is not installed. Both emit COCO labels and the same
``bbox`` / ``label`` / ``score`` dictionaries consumed by GoodQ.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    from scripts.gpu_config import GPUManager, setup_step_gpu
except ImportError as exc:  # pragma: no cover - source-only resilience
    logger.warning("scripts.gpu_config unavailable; using CPU fallback: %s", exc)

    def setup_step_gpu(step_name: str) -> Dict[str, Any]:
        return {"device": "cpu", "step_name": step_name}

    class GPUManager:
        @staticmethod
        def clear_cache() -> None:
            return None


ENGINE = "opencv-dnn"
YOLOX_ENGINE = "onnxruntime"
CPU_MODEL_ID = "opencv_nanodet"
GPU_MODEL_ID = "opencv_yolox"
COCO_CLASSES = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard",
    "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
)


class DetectorUnavailable(RuntimeError):
    """Raised when a sealed detector asset or its local runtime is unavailable."""


@dataclass
class DetectorRuntime:
    model_id: str
    device: str
    net: Any
    engine: str = ENGINE
    fallback_from: str | None = None
    fallback_reason: str | None = None


_RUNTIMES: Dict[str, DetectorRuntime] = {}


def _force_cpu(env: Dict[str, str] | None = None) -> bool:
    active_env = env if env is not None else os.environ
    return (
        str(active_env.get("GOODQ_OBJECT_DETECT_FORCE_CPU", "")).strip() == "1"
        or str(active_env.get("GOODQ_FORCE_CPU", "")).strip() == "1"
        or str(active_env.get("GOODQ_NO_AUTO_GPU", "")).strip() == "1"
        or str(active_env.get("GOODQ_HOST_PROFILE", "")).strip().upper() == "BASELINE"
        or str(active_env.get("CUDA_VISIBLE_DEVICES", "0")).strip() in {"", "-1"}
        or str(active_env.get("GOODQ_DEVICE", "")).strip().lower() == "cpu"
    )


def _select_model_id(cfg: Dict[str, Any], *, env: Dict[str, str] | None = None) -> str:
    """Choose the capability without allowing a runtime network acquisition.

    YOLOX met the frozen detector criteria on both CPU and CUDA execution, so it
    is selected whenever its sealed asset is installed. NanoDet remains only for
    installs that do not carry the YOLOX pack.
    """

    try:
        _sealed_model_path(GPU_MODEL_ID)
    except DetectorUnavailable:
        return CPU_MODEL_ID
    return GPU_MODEL_ID


def _onnxruntime_cuda_available() -> bool:
    try:
        import onnxruntime as ort  # type: ignore
    except Exception:
        return False
    return "CUDAExecutionProvider" in ort.get_available_providers()


def _yolox_device(env: Dict[str, str] | None = None) -> str:
    if _force_cpu(env):
        return "cpu"
    return "cuda" if _onnxruntime_cuda_available() else "cpu"


def _sealed_model_path(model_id: str) -> Path:
    from steps.common.model_provisioner import ensure_model_cached

    result = ensure_model_cached(model_id, offline=True)
    if result.status != "cached" or not result.local_path:
        raise DetectorUnavailable(result.error or f"{model_id} is not installed as a sealed asset")
    path = Path(result.local_path)
    if not path.is_file():
        raise DetectorUnavailable(f"{model_id} resolved to a missing file")
    return path


_WORKER_ORT_CUDA_CACHE: Dict[str, bool] = {}

_GPU_ENV_OVERRIDE_KEYS = (
    "GOODQ_DEVICE",
    "GOODQ_FORCE_CPU",
    "GOODQ_NO_AUTO_GPU",
    "GOODQ_HOST_PROFILE",
    "CUDA_VISIBLE_DEVICES",
    "GOODQ_OBJECT_DETECT_FORCE_CPU",
    "GOODQ_EMOTION_FORCE_CPU",
)


def _build_worker_probe_env(env: Dict[str, str] | None) -> Dict[str, str]:
    probe_env = os.environ.copy()
    if isinstance(env, dict):
        for key in _GPU_ENV_OVERRIDE_KEYS:
            probe_env.pop(key, None)
        for key, value in env.items():
            if value is not None:
                probe_env[str(key)] = str(value)
    probe_env.setdefault("CUDA_VISIBLE_DEVICES", "0")
    return probe_env


def _onnxruntime_supports_cuda(
    *,
    conda_env: str | None = None,
    env: Dict[str, str] | None = None,
) -> bool | None:
    """Return whether the worker runtime's ONNX Runtime exposes CUDA, or None if unknown."""
    import subprocess

    target_env = (conda_env or (env or {}).get("GOODQ_WORKER_CONDA_ENV") or "goodq_object_detect").strip()
    python_exe = None
    try:
        from configs.python_paths import get_env_python

        python_exe = get_env_python(target_env)
    except Exception:
        python_exe = None
    if python_exe is None or not Path(python_exe).exists():
        return None
    resolved_exe = str(Path(python_exe).resolve())
    cached = _WORKER_ORT_CUDA_CACHE.get(resolved_exe)
    if cached is not None:
        return cached
    try:
        proc = subprocess.run(
            [
                resolved_exe,
                "-c",
                (
                    "import sys, onnxruntime as o; "
                    "sys.exit(0 if 'CUDAExecutionProvider' in o.get_available_providers() else 1)"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            env=_build_worker_probe_env(env),
        )
    except Exception:
        return None
    if proc.returncode == 0:
        _WORKER_ORT_CUDA_CACHE[resolved_exe] = True
        return True
    if proc.returncode == 1 and "Traceback" not in (proc.stderr or ""):
        _WORKER_ORT_CUDA_CACHE[resolved_exe] = False
        return False
    return None


def resolve_effective_device(
    cfg: Dict[str, Any] | None = None,
    *,
    env: Dict[str, str] | None = None,
    conda_env: str | None = None,
) -> str:
    """Return 'cuda', 'cpu', or 'unknown' when object_detect capability cannot be confirmed."""
    active_env = env if env is not None else os.environ
    if _force_cpu(active_env):
        return "cpu"
    try:
        _sealed_model_path(GPU_MODEL_ID)
    except DetectorUnavailable:
        return "cpu"
    except Exception:
        return "unknown"
    supported = _onnxruntime_supports_cuda(conda_env=conda_env, env=dict(active_env))
    if supported is None:
        return "unknown"
    return "cuda" if supported else "cpu"


class _OnnxRuntimeNet:
    """cv2.dnn.Net-compatible facade so the YOLOX decode is engine-independent."""

    def __init__(self, session: Any) -> None:
        self.session = session
        self.input_name = session.get_inputs()[0].name
        self.output_names = [output.name for output in session.get_outputs()]
        self._blob = None

    def setInput(self, blob: Any) -> None:  # noqa: N802 - mirrors cv2.dnn.Net
        import numpy as np

        self._blob = np.ascontiguousarray(blob, dtype=np.float32)

    def getUnconnectedOutLayersNames(self) -> list[str]:  # noqa: N802
        return self.output_names

    def forward(self, names: Any) -> list[Any]:
        return self.session.run(list(names), {self.input_name: self._blob})


def _create_yolox_runtime(device: str) -> DetectorRuntime:
    """Create a YOLOX ONNX Runtime session and verify the provider it actually uses."""
    try:
        import onnxruntime as ort  # type: ignore
    except Exception as exc:
        raise DetectorUnavailable(f"ONNX Runtime is unavailable: {exc}") from exc
    model_path = _sealed_model_path(GPU_MODEL_ID)
    provider = "CUDAExecutionProvider" if device == "cuda" else "CPUExecutionProvider"
    if provider not in ort.get_available_providers():
        raise DetectorUnavailable(f"Selected ONNX Runtime provider unavailable: {provider}")
    if device == "cuda":
        # CUDA 12 / cuDNN 9 libraries ship as pinned NVIDIA wheels in the
        # detector runtime; without preloading, ONNX Runtime silently creates a
        # CPU session on Windows.
        ort.preload_dlls()
    session = ort.InferenceSession(str(model_path), providers=[provider])
    if device == "cuda":
        session.disable_fallback()
    if session.get_providers()[0] != provider:
        raise DetectorUnavailable(f"YOLOX session did not initialize selected provider: {provider}")
    return DetectorRuntime(model_id=GPU_MODEL_ID, device=device, net=_OnnxRuntimeNet(session), engine=YOLOX_ENGINE)


def _load_detector(cfg: Dict[str, Any]) -> DetectorRuntime:
    selected = _select_model_id(cfg)
    if selected == CPU_MODEL_ID:
        return _load_cpu_detector(cfg)
    device = _yolox_device()
    key = f"{GPU_MODEL_ID}:{device}"
    if key in _RUNTIMES:
        return _RUNTIMES[key]
    if device == "cuda":
        try:
            runtime = _create_yolox_runtime("cuda")
        except Exception as exc:
            runtime = _load_yolox_cpu()
            runtime = DetectorRuntime(
                model_id=runtime.model_id, device=runtime.device, net=runtime.net, engine=runtime.engine,
                fallback_from=f"{GPU_MODEL_ID}:cuda", fallback_reason=f"YOLOX CUDA session unavailable: {exc}",
            )
        _RUNTIMES[key] = runtime
        return runtime
    return _load_yolox_cpu()


def _load_yolox_cpu() -> DetectorRuntime:
    key = f"{GPU_MODEL_ID}:cpu"
    cached = _RUNTIMES.get(key)
    if cached is not None:
        return cached
    runtime = _create_yolox_runtime("cpu")
    _RUNTIMES[key] = runtime
    return runtime


def _load_cpu_detector(cfg: Dict[str, Any]) -> DetectorRuntime:
    """Load the sealed baseline detector without changing caller configuration."""

    cached = _RUNTIMES.get(CPU_MODEL_ID)
    if cached is not None:
        return cached
    try:
        import cv2  # type: ignore
    except Exception as exc:
        raise DetectorUnavailable(f"OpenCV DNN is unavailable: {exc}") from exc
    try:
        model_path = _sealed_model_path(CPU_MODEL_ID)
        net = cv2.dnn.readNet(str(model_path))
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    except Exception as exc:
        raise DetectorUnavailable(f"{CPU_MODEL_ID}: {exc}") from exc
    runtime = DetectorRuntime(model_id=CPU_MODEL_ID, device="cpu", net=net)
    _RUNTIMES[CPU_MODEL_ID] = runtime
    return runtime


def _runtime_metadata(runtime: DetectorRuntime) -> Dict[str, str]:
    metadata = {"engine": runtime.engine, "model": runtime.model_id, "device": runtime.device}
    if runtime.fallback_from:
        metadata["fallback_from"] = runtime.fallback_from
    if runtime.fallback_reason:
        metadata["fallback_reason"] = runtime.fallback_reason
    return metadata


def _letterbox_nanodet(image: Any, cv2: Any) -> tuple[Any, tuple[int, int, int, int]]:
    height, width = image.shape[:2]
    target = 416
    if height == width:
        return cv2.resize(image, (target, target), interpolation=cv2.INTER_AREA), (0, 0, target, target)
    scale = target / max(height, width)
    new_width, new_height = int(width * scale), int(height * scale)
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    top, left = (target - new_height) // 2, (target - new_width) // 2
    padded = cv2.copyMakeBorder(
        resized, top, target - new_height - top, left, target - new_width - left, cv2.BORDER_CONSTANT, value=0
    )
    return padded, (top, left, new_height, new_width)


def _nanodet_predictions(runtime: DetectorRuntime, image: Any, cv2: Any, np: Any) -> list[dict[str, Any]]:
    original_height, original_width = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    prepared, (top, left, resized_height, resized_width) = _letterbox_nanodet(rgb, cv2)
    mean = np.array([103.53, 116.28, 123.675], dtype=np.float32).reshape(1, 1, 3)
    std = np.array([57.375, 57.12, 58.395], dtype=np.float32).reshape(1, 1, 3)
    runtime.net.setInput(cv2.dnn.blobFromImage((prepared.astype(np.float32) - mean) / std))
    outputs = runtime.net.forward(runtime.net.getUnconnectedOutLayersNames())
    strides = (8, 16, 32, 64)
    anchors: list[Any] = []
    for stride in strides:
        grid = 416 // stride
        xv, yv = np.meshgrid(np.arange(grid) * stride, np.arange(grid) * stride)
        anchors.append(np.column_stack((xv.flatten() + 0.5 * (stride - 1), yv.flatten() + 0.5 * (stride - 1))))
    boxes_all, scores_all = [], []
    project = np.arange(8)
    for stride, cls_score, bbox_pred, points in zip(strides, outputs[::2], outputs[1::2], anchors):
        cls_score = np.squeeze(cls_score, axis=0)
        bbox_pred = np.squeeze(bbox_pred, axis=0)
        distribution = np.exp(bbox_pred.reshape(-1, 8))
        distance = (distribution / distribution.sum(axis=1, keepdims=True)) @ project
        distance = distance.reshape(-1, 4) * stride
        max_scores = cls_score.max(axis=1)
        if cls_score.shape[0] > 1000:
            keep = max_scores.argsort()[::-1][:1000]
            points, distance, cls_score = points[keep], distance[keep], cls_score[keep]
        boxes_all.append(np.column_stack((
            np.clip(points[:, 0] - distance[:, 0], 0, 416),
            np.clip(points[:, 1] - distance[:, 1], 0, 416),
            np.clip(points[:, 0] + distance[:, 2], 0, 416),
            np.clip(points[:, 1] + distance[:, 3], 0, 416),
        )))
        scores_all.append(cls_score)
    boxes = np.concatenate(boxes_all, axis=0)
    scores = np.concatenate(scores_all, axis=0)
    class_ids, confidences = np.argmax(scores, axis=1), np.max(scores, axis=1)
    xywh = boxes.copy()
    xywh[:, 2:] -= xywh[:, :2]
    indices = cv2.dnn.NMSBoxes(xywh.tolist(), confidences.tolist(), 0.35, 0.6)
    detections: list[dict[str, Any]] = []
    for index in np.asarray(indices).reshape(-1):
        x1, y1, x2, y2 = boxes[int(index)]
        x1 = max((x1 - left) * original_width / resized_width, 0)
        y1 = max((y1 - top) * original_height / resized_height, 0)
        x2 = min((x2 - left) * original_width / resized_width, original_width)
        y2 = min((y2 - top) * original_height / resized_height, original_height)
        detections.append({"bbox": [float(x1), float(y1), float(x2), float(y2)], "label": COCO_CLASSES[int(class_ids[int(index)])], "score": float(confidences[int(index)])})
    return detections


def _yolox_predictions(runtime: DetectorRuntime, image: Any, cv2: Any, np: Any) -> list[dict[str, Any]]:
    height, width = image.shape[:2]
    ratio = min(640 / height, 640 / width)
    padded = np.ones((640, 640, 3), dtype=np.float32) * 114.0
    resized = cv2.resize(image, (int(width * ratio), int(height * ratio)), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    padded[: resized.shape[0], : resized.shape[1]] = resized
    runtime.net.setInput(np.transpose(padded, (2, 0, 1))[None, :, :, :])
    output = runtime.net.forward(runtime.net.getUnconnectedOutLayersNames())[0][0]
    grids, expanded = [], []
    for stride in (8, 16, 32):
        grid_width, grid_height = 640 // stride, 640 // stride
        xv, yv = np.meshgrid(np.arange(grid_width), np.arange(grid_height))
        grid = np.stack((xv, yv), axis=2).reshape(1, -1, 2)
        grids.append(grid)
        expanded.append(np.full((*grid.shape[:2], 1), stride))
    grid, expanded_strides = np.concatenate(grids, axis=1), np.concatenate(expanded, axis=1)
    output[:, :2] = (output[:, :2] + grid[0]) * expanded_strides[0]
    output[:, 2:4] = np.exp(output[:, 2:4]) * expanded_strides[0]
    scores = output[:, 4:5] * output[:, 5:]
    confidences, class_ids = np.amax(scores, axis=1), np.argmax(scores, axis=1)
    xywh = output[:, :4].copy()
    xywh[:, :2] -= xywh[:, 2:] / 2
    indices = cv2.dnn.NMSBoxesBatched(xywh.tolist(), confidences.tolist(), class_ids.tolist(), 0.5, 0.5)
    detections: list[dict[str, Any]] = []
    for index in np.asarray(indices).reshape(-1):
        x, y, box_width, box_height = xywh[int(index)] / ratio
        detections.append({"bbox": [float(x), float(y), float(x + box_width), float(y + box_height)], "label": COCO_CLASSES[int(class_ids[int(index)])], "score": float(confidences[int(index)])})
    return detections


def _detect_with_runtime(runtime: DetectorRuntime, path: str) -> list[dict[str, Any]]:
    try:
        import cv2  # type: ignore
        import numpy as np
    except Exception as exc:
        raise DetectorUnavailable(f"OpenCV DNN runtime is unavailable: {exc}") from exc
    image = cv2.imread(path)
    if image is None:
        raise DetectorUnavailable("OpenCV could not decode the source image")
    if runtime.model_id == CPU_MODEL_ID:
        return _nanodet_predictions(runtime, image, cv2, np)
    if runtime.model_id == GPU_MODEL_ID:
        return _yolox_predictions(runtime, image, cv2, np)
    raise DetectorUnavailable(f"unsupported sealed detector: {runtime.model_id}")


def _log(stage: str, *, source_path: str, metadata: Dict[str, str], model_loaded_now: bool) -> None:
    payload = {"event": "object_detect_diagnostics", "stage": stage, "source_path": source_path, "model_loaded_now": model_loaded_now, **metadata}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)
    logger.info("object_detect diagnostics %s", payload)


def object_detect(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    sample_provenance: Dict[str, Any] = {}
    if item.get("timestamp") is not None:
        sample_provenance["sample_timestamp"] = item.get("timestamp")
    if item.get("is_midpoint_sample") is not None:
        sample_provenance["is_midpoint_sample"] = bool(item.get("is_midpoint_sample"))
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"objects": [], "detect_meta": {"status": "no_file", **sample_provenance}}
    try:
        selected = _select_model_id(cfg)
        model_loaded_now = not any(key.split(":")[0] == selected for key in _RUNTIMES)
        runtime = _load_detector(cfg)
        metadata = _runtime_metadata(runtime)
        _log("before_inference", source_path=path, metadata=metadata, model_loaded_now=model_loaded_now)
        try:
            detections = _detect_with_runtime(runtime, path)
        except Exception as exc:
            if not (runtime.model_id == GPU_MODEL_ID and runtime.device == "cuda"):
                raise
            logger.warning("YOLOX CUDA inference failed; retrying the same model on CPU: %s", exc)
            runtime = _load_yolox_cpu()
            metadata = {
                **_runtime_metadata(runtime),
                "fallback_from": f"{GPU_MODEL_ID}:cuda",
                "fallback_reason": str(exc),
            }
            detections = _detect_with_runtime(runtime, path)
        _log("after_inference", source_path=path, metadata=metadata, model_loaded_now=model_loaded_now)
        return {"objects": detections, "detect_meta": {"status": "ok", **metadata, **sample_provenance}}
    except DetectorUnavailable as exc:
        logger.warning("object detection unavailable: %s", exc)
        return {"objects": [], "detect_meta": {"status": "unavailable", "engine": ENGINE, "error": str(exc), **sample_provenance}}
    except Exception as exc:
        logger.exception("object detection failed")
        GPUManager.clear_cache()
        return {"objects": [], "detect_meta": {"status": "error", "engine": ENGINE, "error": str(exc), "exc_type": type(exc).__name__, **sample_provenance}}
