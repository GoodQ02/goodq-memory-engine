"""Version-bound native Paddle adapter; no alternate engine or remote provisioning."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


MODEL_IDENTITIES = {
    "paddle_ocr_det": ("PaddlePaddle/PP-OCRv6_medium_det_onnx", "61323801669c338b7891481ec7bac61ce31b576a"),
    "paddle_ocr_rec": ("PaddlePaddle/PP-OCRv6_medium_rec_onnx", "50c7eacafc52fa7bcf4194e8cd08e46f8558504b"),
}
RUNTIME_VERSIONS = {"paddleocr": "3.7.0", "paddlex": "3.7.2"}
logger = logging.getLogger(__name__)


class OCRRuntimeError(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def resolve_ocr_device(cfg: dict[str, Any]) -> str:
    device = (cfg.get("image_ocr") or {}).get("device", "cpu")
    if device not in {"cpu", "cuda:0"}:
        raise OCRRuntimeError("unsupported_device", "image_ocr.device must be cpu or cuda:0")
    return device


def _resolve_assets(cfg: dict[str, Any]) -> dict[str, Path]:
    from steps.common.model_provisioner import load_registry, resolve_models_root

    configured = (cfg.get("paths") or {}).get("models_cache")
    root = Path(configured).resolve() if configured else resolve_models_root()
    registry = load_registry().get("huggingface_models", {})
    assets = {}
    for key, (repo, revision) in MODEL_IDENTITIES.items():
        entry = registry.get(key, {})
        if entry.get("repo_id") != repo or entry.get("revision") != revision:
            raise OCRRuntimeError("model_identity_mismatch", f"Pinned OCR registry identity does not match: {key}")
        local = entry.get("local_path")
        if not isinstance(local, str) or Path(local).is_absolute():
            raise OCRRuntimeError("model_asset_invalid", f"Invalid relative OCR asset path: {key}")
        directory = (root / local).resolve()
        if not directory.is_relative_to(root.resolve()):
            raise OCRRuntimeError("model_asset_invalid", f"OCR asset escapes model root: {key}")
        files = entry.get("files", {})
        if not isinstance(files, dict) or not {"inference.onnx", "inference.yml", "inference.json"}.issubset(files):
            raise OCRRuntimeError("model_asset_invalid", f"OCR asset hash manifest incomplete: {key}")
        for name, expected in files.items():
            path = (directory / name).resolve()
            if not path.is_relative_to(directory):
                raise OCRRuntimeError("model_asset_invalid", f"Invalid OCR manifest file: {key}")
            if not path.is_file():
                raise OCRRuntimeError("model_asset_missing", f"Required local OCR file missing: {key}/{name}")
            if path.stat().st_size != expected["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != expected["sha256"]:
                raise OCRRuntimeError("model_asset_hash_mismatch", f"Local OCR file failed verification: {key}/{name}")
        assets[key] = directory
    return assets


def _create_ocr(assets: dict[str, Path], device: str, profile_root: Path):
    # Official offline flags must precede importing PaddleX's model registry.
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ["PADDLE_PDX_DISABLE_DEVICE_FALLBACK"] = "True"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    for package, required in RUNTIME_VERSIONS.items():
        if version(package) != required:
            raise OCRRuntimeError("runtime_version_mismatch", f"OCR requires {package}=={required}")
    import onnxruntime as ort

    if ort.__version__ != "1.23.2":
        raise OCRRuntimeError("runtime_version_mismatch", "OCR requires ONNX Runtime 1.23.2")
    if device != "cpu":
        ort.preload_dlls(directory="")
    provider = "CPUExecutionProvider" if device == "cpu" else "CUDAExecutionProvider"
    if provider not in ort.get_available_providers():
        raise OCRRuntimeError("selected_provider_unavailable", f"Selected OCR provider unavailable: {provider}")
    from paddleocr import PaddleOCR
    from paddlex.inference import load_pipeline_config

    native_config = deepcopy(load_pipeline_config("OCR"))
    for module, name in (("TextDetection", "detector"), ("TextRecognition", "recognizer")):
        native_config["SubModules"][module]["engine_config"] = {
            "session_options": {"enable_profiling": True, "profile_file_prefix": str(profile_root / name)}
        }
    # Frozen A settings: native preprocessing, thresholds and decoding unchanged.
    ocr = PaddleOCR(
        text_detection_model_name="PP-OCRv6_medium_det", text_detection_model_dir=str(assets["paddle_ocr_det"]),
        text_recognition_model_name="PP-OCRv6_medium_rec", text_recognition_model_dir=str(assets["paddle_ocr_rec"]),
        use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
        engine="onnxruntime", device="cpu" if device == "cpu" else "gpu:0", paddlex_config=native_config,
    )
    sessions = {}
    try:
        # Version-bound RunnerPredictor access; never replace InferenceSession.
        sessions = {name: getattr(ocr.paddlex_pipeline, attribute).runner.session
                    for name, attribute in (("detector", "text_det_model"), ("recognizer", "text_rec_model"))}
        for session in sessions.values():
            session.disable_fallback()
            if session.get_providers()[0] != provider:
                raise OCRRuntimeError("selected_provider_unavailable", f"OCR session did not initialize selected provider: {provider}")
    except Exception:
        # Failed CUDA initialization can still create CPU sessions. End their
        # profile writers before temporary-directory cleanup on Windows.
        for session in sessions.values():
            try:
                session.end_profiling()
            except Exception as cleanup_error:
                logger.warning("OCR failed-session profile cleanup: %s", cleanup_error)
        ocr.close()
        raise
    return ocr, sessions, provider


def _execution_receipt(session: Any, provider: str, *, required: bool) -> dict[str, Any]:
    events = json.loads(Path(session.end_profiling()).read_text(encoding="utf-8"))
    counts = Counter(event.get("args", {}).get("provider") for event in events
                     if event.get("cat") == "Node" and event.get("args", {}).get("provider"))
    if required and counts.get(provider, 0) == 0:
        raise OCRRuntimeError("selected_provider_not_executed", f"No executed OCR kernels on selected provider: {provider}")
    if counts and not counts.get(provider, 0):
        raise OCRRuntimeError("selected_provider_not_executed", f"OCR executed on another provider instead of {provider}")
    return {"session_providers": session.get_providers(), "executed_kernel_counts": dict(counts),
            "status": "executed" if counts else "not_run_no_regions",
            "cpu_node_assignment": provider != "CPUExecutionProvider" and bool(counts.get("CPUExecutionProvider")),
            "runtime_fallback_enabled": False}


def run_native_ocr(source: str, cfg: dict[str, Any], device: str) -> tuple[dict[str, Any], dict[str, Any]]:
    assets = _resolve_assets(cfg)
    with TemporaryDirectory(prefix="goodq-ocr-profile-") as profile_dir:
        ocr, sessions, provider = _create_ocr(assets, device, Path(profile_dir))
        try:
            result = list(ocr.predict(source))
            if len(result) != 1:
                raise OCRRuntimeError("malformed_native_result", "OCR must return exactly one source image result")
            raw = result[0].json.get("res")
            if not isinstance(raw, dict):
                raise OCRRuntimeError("malformed_native_result", "OCR result has no native result object")
            execution = {name: _execution_receipt(session, provider, required=name == "detector" or bool(raw.get("rec_texts")))
                         for name, session in sessions.items()}
            settings = {key: raw.get(key) for key in ("model_settings", "text_det_params", "text_type", "text_rec_score_thresh", "return_word_box")}
            fingerprint = hashlib.sha256(json.dumps({"models": MODEL_IDENTITIES, "versions": RUNTIME_VERSIONS,
                "onnxruntime": "1.23.2", "device": device, "settings": settings}, sort_keys=True).encode()).hexdigest()
            return raw, {"providers": [session.get_providers() for session in sessions.values()],
                         "provider_execution": execution, "config_sha256": fingerprint,
                         "runtime_versions": {**RUNTIME_VERSIONS, "onnxruntime": "1.23.2"}}
        finally:
            # Profiling may not have been consumed when prediction/validation
            # failed. Ending twice is supported by ORT and returns an empty path.
            for session in sessions.values():
                try:
                    session.end_profiling()
                except Exception as cleanup_error:
                    logger.warning("OCR session profile cleanup: %s", cleanup_error)
            ocr.close()
            sessions.clear()
