from __future__ import annotations

import contextlib
import importlib
import importlib.util
import io
import logging
import os
import warnings
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

PRIMARY_ENGINE = "opencv-yunet-sface"
FALLBACK_ENGINE = "face_recognition"
_PRIMARY_MODELS = ("opencv_yunet", "opencv_sface")


class PrimaryFaceEngineUnavailable(RuntimeError):
    """The sealed YuNet/SFace capability is unavailable or invalid."""


def _face_recognition_stack_available() -> bool:
    if not importlib.util.find_spec("face_recognition"):
        return False
    if not importlib.util.find_spec("face_recognition_models"):
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                importlib.import_module("face_recognition_models")
        return True
    except Exception as exc:
        logger.warning("face_recognition fallback import failed: %s", exc)
        return False


def _sealed_model_paths() -> tuple[Path, Path]:
    """Resolve the primary models without allowing a runtime network fetch."""
    from steps.common.model_provisioner import ensure_model_cached

    resolved: list[Path] = []
    for model_id in _PRIMARY_MODELS:
        result = ensure_model_cached(model_id, offline=True)
        if result.status != "cached" or not result.local_path:
            raise PrimaryFaceEngineUnavailable(result.error or f"{model_id} is not available")
        candidate = Path(result.local_path)
        if not candidate.is_file():
            raise PrimaryFaceEngineUnavailable(f"{model_id} resolved to a missing file")
        resolved.append(candidate)
    return resolved[0], resolved[1]


def _opencv_yunet_sface_embed(path: str) -> List[Dict[str, Any]]:
    try:
        import cv2  # type: ignore
        import numpy as np
    except Exception as exc:
        raise PrimaryFaceEngineUnavailable(f"OpenCV primary engine is unavailable: {exc}") from exc

    detector_path, recognizer_path = _sealed_model_paths()
    image = cv2.imread(path)
    if image is None:
        raise PrimaryFaceEngineUnavailable("OpenCV could not decode the source image")
    height, width = image.shape[:2]
    if not width or not height:
        raise PrimaryFaceEngineUnavailable("OpenCV decoded an empty source image")
    try:
        detector = cv2.FaceDetectorYN.create(str(detector_path), "", (width, height))
        recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")
        detector.setInputSize((width, height))
        _count, detections = detector.detect(image)
    except Exception as exc:
        raise PrimaryFaceEngineUnavailable(f"YuNet/SFace initialization failed: {exc}") from exc
    if detections is None:
        return []

    faces: List[Dict[str, Any]] = []
    for detection in detections:
        x, y, box_width, box_height = (int(round(float(value))) for value in detection[:4])
        try:
            aligned = recognizer.alignCrop(image, detection)
            vector = np.asarray(recognizer.feature(aligned), dtype=float).reshape(-1)
        except Exception as exc:
            raise PrimaryFaceEngineUnavailable(f"SFace feature extraction failed: {exc}") from exc
        if vector.size == 0:
            raise PrimaryFaceEngineUnavailable("SFace returned an empty embedding")
        faces.append(
            {
                "bbox": [x, y, x + box_width, y + box_height],
                "encoding": vector.tolist(),
                "engine": PRIMARY_ENGINE,
                "embedding_dimension": int(vector.size),
            }
        )
    return faces


def _face_recognition_embed(path: str) -> List[Dict[str, Any]]:
    if not _face_recognition_stack_available():
        raise RuntimeError("dlib/face_recognition fallback is unavailable")
    import face_recognition  # type: ignore

    image = face_recognition.load_image_file(path)
    locations = face_recognition.face_locations(image)
    encodings = face_recognition.face_encodings(image, locations)
    faces: List[Dict[str, Any]] = []
    for (top, right, bottom, left), encoding in zip(locations, encodings):
        values = [float(value) for value in (encoding.tolist() if hasattr(encoding, "tolist") else list(encoding))]
        faces.append(
            {
                "bbox": [int(left), int(top), int(right), int(bottom)],
                "encoding": values,
                "engine": FALLBACK_ENGINE,
                "embedding_dimension": len(values),
            }
        )
    return faces


def _face_meta(*, status: str, engine: str, faces: List[Dict[str, Any]], **extra: Any) -> Dict[str, Any]:
    dimensions = {int(face.get("embedding_dimension", len(face.get("encoding", [])))) for face in faces}
    if len(dimensions) > 1:
        raise RuntimeError(f"face engine returned mixed embedding dimensions: {sorted(dimensions)}")
    return {"status": status, "engine": engine, **extra, "embedding_dimension": next(iter(dimensions), 0)}


def face_embed(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"faces": [], "faces_meta": {"status": "no_file"}}

    try:
        faces = _opencv_yunet_sface_embed(path)
        return {
            "faces": faces,
            "faces_meta": _face_meta(status="ok", engine=PRIMARY_ENGINE, faces=faces, fallback_used=False),
        }
    except PrimaryFaceEngineUnavailable as primary_error:
        logger.warning("YuNet/SFace primary unavailable; using dlib fallback: %s", primary_error)
        try:
            faces = _face_recognition_embed(path)
            return {
                "faces": faces,
                "faces_meta": _face_meta(
                    status="degraded",
                    engine=FALLBACK_ENGINE,
                    faces=faces,
                    primary_engine=PRIMARY_ENGINE,
                    fallback_used=True,
                    fallback_reason=str(primary_error),
                ),
            }
        except Exception as fallback_error:
            logger.error("face embedding unavailable: primary=%s; fallback=%s", primary_error, fallback_error)
            return {
                "faces": [],
                "faces_meta": {
                    "status": "error",
                    "primary_engine": PRIMARY_ENGINE,
                    "fallback_engine": FALLBACK_ENGINE,
                    "primary_error": str(primary_error),
                    "fallback_error": str(fallback_error),
                },
            }
    except Exception as primary_error:
        logger.error("YuNet/SFace primary failed: %s", primary_error)
        return {
            "faces": [],
            "faces_meta": {"status": "error", "engine": PRIMARY_ENGINE, "error": str(primary_error)},
        }
