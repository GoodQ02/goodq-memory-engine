"""Sealed OpenCV Zoo object detection with a stable GoodQ payload contract.

The detector is intentionally independent of the retired AGPL model stack. NanoDet is the
bundled CPU-safe baseline; YOLOX is selected only on an available GPU when its
separate sealed capability asset is present.  Both emit COCO labels and the
same ``bbox`` / ``label`` / ``score`` dictionaries consumed by GoodQ.
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


_RUNTIMES: Dict[str, DetectorRuntime] = {}


def _force_cpu() -> bool:
    return os.getenv("GOODQ_OBJECT_DETECT_FORCE_CPU", "").strip() == "1"


def _select_model_id(cfg: Dict[str, Any]) -> str:
    """Choose the capability without allowing a runtime network acquisition."""

    if _force_cpu():
        return CPU_MODEL_ID
    device = str(setup_step_gpu("object_detect").get("device") or "cpu").casefold()
    return GPU_MODEL_ID if device.startswith("cuda") else CPU_MODEL_ID


def _sealed_model_path(model_id: str) -> Path:
    from steps.common.model_provisioner import ensure_model_cached

    result = ensure_model_cached(model_id, offline=True)
    if result.status != "cached" or not result.local_path:
        raise DetectorUnavailable(result.error or f"{model_id} is not installed as a sealed asset")
    path = Path(result.local_path)
    if not path.is_file():
        raise DetectorUnavailable(f"{model_id} resolved to a missing file")
    return path


def _load_detector(cfg: Dict[str, Any]) -> DetectorRuntime:
    selected = _select_model_id(cfg)
    if selected in _RUNTIMES:
        return _RUNTIMES[selected]

    try:
        import cv2  # type: ignore
    except Exception as exc:
        raise DetectorUnavailable(f"OpenCV DNN is unavailable: {exc}") from exc

    candidates = [selected]
    if selected == GPU_MODEL_ID:
        candidates.append(CPU_MODEL_ID)
    errors: list[str] = []
    for model_id in candidates:
        try:
            model_path = _sealed_model_path(model_id)
            net = cv2.dnn.readNet(str(model_path))
            device = "cpu"
            if model_id == GPU_MODEL_ID and not _force_cpu():
                try:
                    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
                    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA_FP16)
                    device = "cuda"
                except Exception as exc:
                    errors.append(f"{model_id} CUDA setup: {exc}")
            if device == "cpu":
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            runtime = DetectorRuntime(model_id=model_id, device=device, net=net)
            _RUNTIMES[model_id] = runtime
            return runtime
        except Exception as exc:
            errors.append(f"{model_id}: {exc}")
    raise DetectorUnavailable("; ".join(errors) or "no object detector could be initialized")


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
        net = cv2.dnn.readNet(str(_sealed_model_path(CPU_MODEL_ID)))
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    except Exception as exc:
        raise DetectorUnavailable(f"{CPU_MODEL_ID}: {exc}") from exc
    runtime = DetectorRuntime(model_id=CPU_MODEL_ID, device="cpu", net=net)
    _RUNTIMES[CPU_MODEL_ID] = runtime
    return runtime


def _runtime_metadata(runtime: DetectorRuntime) -> Dict[str, str]:
    return {"engine": ENGINE, "model": runtime.model_id, "device": runtime.device}


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
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"objects": [], "detect_meta": {"status": "no_file"}}
    try:
        selected = _select_model_id(cfg)
        model_loaded_now = selected not in _RUNTIMES
        runtime = _load_detector(cfg)
        metadata = _runtime_metadata(runtime)
        _log("before_inference", source_path=path, metadata=metadata, model_loaded_now=model_loaded_now)
        try:
            detections = _detect_with_runtime(runtime, path)
        except Exception as exc:
            if runtime.model_id != GPU_MODEL_ID:
                raise
            logger.warning("GPU object detection failed; retrying sealed CPU detector: %s", exc)
            runtime = _load_cpu_detector(cfg)
            metadata = {
                **_runtime_metadata(runtime),
                "fallback_from": GPU_MODEL_ID,
                "fallback_reason": str(exc),
            }
            detections = _detect_with_runtime(runtime, path)
        _log("after_inference", source_path=path, metadata=metadata, model_loaded_now=model_loaded_now)
        return {"objects": detections, "detect_meta": {"status": "ok", **metadata}}
    except DetectorUnavailable as exc:
        logger.warning("object detection unavailable: %s", exc)
        return {"objects": [], "detect_meta": {"status": "unavailable", "engine": ENGINE, "error": str(exc)}}
    except Exception as exc:
        logger.exception("object detection failed")
        GPUManager.clear_cache()
        return {"objects": [], "detect_meta": {"status": "error", "engine": ENGINE, "error": str(exc), "exc_type": type(exc).__name__}}
