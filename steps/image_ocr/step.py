from __future__ import annotations
# GPU Configuration - Auto-configured on import
from steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats


from typing import Any, Dict, Optional
import os
import re

from steps.common.tool_paths import resolve_tesseract


def _sanitize_error_message(exc: BaseException) -> str:
    msg = str(exc).strip()
    if not msg:
        return type(exc).__name__
    msg = re.sub(r"\b[A-Za-z]:[\\/][^\s'\"\)]+", "<path>", msg)
    msg = re.sub(r"\\\\[^\s'\"\)]+", "<path>", msg)
    return msg[:300]


def _meta(status: str, **fields: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"status": status}
    payload.update({k: v for k, v in fields.items() if v is not None})
    return payload


def image_ocr(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Extract text from images using Tesseract OCR.
    
    Gracefully handles missing dependencies (pytesseract/Pillow).
    Returns None for ocr_text if extraction fails or tools unavailable.
    """
    text: Optional[str] = None
    img_path = item.get("source_path")
    if not isinstance(img_path, str) or not os.path.isfile(img_path):
        return {
            "ocr_text": None,
            "ocr_meta": _meta(
                "no_source_path",
                reason="source_image_missing",
                source_path_present=isinstance(img_path, str) and bool(img_path.strip()),
            ),
        }

    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except (ImportError, ModuleNotFoundError) as exc:
        return {
            "ocr_text": None,
            "ocr_meta": _meta(
                "dependency_missing",
                reason=getattr(exc, "name", None) or type(exc).__name__,
                exc_type=type(exc).__name__,
                error=_sanitize_error_message(exc),
            ),
        }

    try:
        tess = resolve_tesseract(cfg)
        if tess:
            pytesseract.pytesseract.tesseract_cmd = tess
        raw_text = pytesseract.image_to_string(Image.open(img_path))
        text = raw_text.strip() if isinstance(raw_text, str) and raw_text.strip() else None
    except Exception as e:
        return {
            "ocr_text": None,
            "ocr_meta": _meta(
                "error",
                reason="ocr_exception",
                exc_type=type(e).__name__,
                error=_sanitize_error_message(e),
            ),
        }

    if text:
        return {
            "ocr_text": text,
            "ocr_meta": _meta(
                "ok",
                engine="tesseract",
                tesseract_configured=bool(tess),
                text_length=len(text),
            ),
        }
    return {
        "ocr_text": None,
        "ocr_meta": _meta(
            "no_text",
            reason="empty_ocr_text",
            engine="tesseract",
            tesseract_configured=bool(tess),
        ),
    }
