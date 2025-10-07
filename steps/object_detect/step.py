from __future__ import annotations
from typing import Any, Dict, List

import os


_YOLO = None


def _load_yolo(cfg: Dict[str, Any]):
    global _YOLO
    if _YOLO is not None:
        return _YOLO
    try:
        from ultralytics import YOLO  # type: ignore
        model_path = (
            cfg.get("models", {}).get("yolo_model_path")
            or cfg.get("config", {}).get("models", {}).get("yolo_model_path")
            or "yolov8n.pt"
        )
        _YOLO = YOLO(model_path)
    except Exception:
        _YOLO = None
    return _YOLO


def _run_yolo(model, path: str, device: str | None = None):
    try:
        # Prefer explicit predict API so we can choose device
        return model.predict(source=path, device=device, verbose=False)
    except Exception:
        # Fallback to callable interface
        if device:
            try:
                model.to(device)
            except Exception:
                pass
        return model(path)


def object_detect(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"objects": [], "detect_meta": {"status": "no_file"}}

    model = _load_yolo(cfg)
    if model is None:
        return {"objects": [], "detect_meta": {"status": "unavailable", "engine": "yolo"}}
    try:
        # First attempt: default device selection (GPU if available)
        results = _run_yolo(model, path)
    except Exception as e:
        msg = str(e)
        # Known failure: torchvision::nms CUDA op unavailable -> retry on CPU
        if "torchvision::nms" in msg or "nms" in msg.lower():
            try:
                results = _run_yolo(model, path, device="cpu")
            except Exception as e2:
                return {"objects": [], "detect_meta": {"status": "error", "error": str(e2), "engine": "yolo", "device": "cpu"}}
        else:
            return {"objects": [], "detect_meta": {"status": "error", "error": msg, "engine": "yolo"}}

    try:
        detections: List[Dict[str, Any]] = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            names = getattr(r, "names", {}) or {}
            if boxes is None:
                continue
            for b in boxes:
                xyxy = getattr(b, "xyxy", None)
                conf = getattr(b, "conf", None)
                cls = getattr(b, "cls", None)
                if xyxy is None or conf is None or cls is None:
                    continue
                try:
                    x1, y1, x2, y2 = [float(v) for v in xyxy[0].tolist()]
                except Exception:
                    vals = getattr(xyxy, "tolist", lambda: [])()
                    if vals and len(vals[0]) == 4:
                        x1, y1, x2, y2 = [float(v) for v in vals[0]]
                    else:
                        continue
                label = names.get(int(cls[0].item()) if hasattr(cls[0], "item") else int(cls[0])) if len(names) else None
                score = float(conf[0].item()) if hasattr(conf[0], "item") else float(conf[0])
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "label": label,
                    "score": score,
                })
        return {"objects": detections}
    except Exception as e:
        return {"objects": [], "detect_meta": {"status": "error", "error": str(e), "engine": "yolo"}}
