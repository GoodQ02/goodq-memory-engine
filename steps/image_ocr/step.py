from __future__ import annotations
# GPU Configuration - Auto-configured on import
from steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats


from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
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


_MONTH_ABBREVIATIONS = {
    "JAN": "JAN",
    "FEB": "FEB",
    "MAR": "MAR",
    "APR": "APR",
    "MAY": "MAY",
    "JUN": "JUN",
    "JUL": "JUL",
    "AUG": "AUG",
    "SEP": "SEP",
    "SEPT": "SEP",
    "OCT": "OCT",
    "NOV": "NOV",
    "DEC": "DEC",
}
_MONTH_FULL_NAMES = {
    "JAN": "january",
    "FEB": "february",
    "MAR": "march",
    "APR": "april",
    "MAY": "may",
    "JUN": "june",
    "JUL": "july",
    "AUG": "august",
    "SEP": "september",
    "OCT": "october",
    "NOV": "november",
    "DEC": "december",
}
_MONTH_NUMBERS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def _clean_ocr_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _dedupe_texts(values: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        cleaned = _clean_ocr_text(value)
        key = cleaned.upper()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


def _extract_vhs_date_candidates(texts: Iterable[str]) -> List[str]:
    """Extract conservative VHS-style date candidates from OCR variants."""
    candidates: List[str] = []
    for text in texts:
        normalized = re.sub(r"[^A-Z0-9]+", " ", text.upper())
        tokens = normalized.split()
        for idx in range(len(tokens) - 2):
            month_token = tokens[idx]
            month = _MONTH_ABBREVIATIONS.get(month_token)
            repair_prefix = False
            if month is None and month_token == "EC":
                # Tesseract commonly drops the leading D in noisy DEC overlays.
                month = "DEC"
                repair_prefix = True
            if month is None:
                continue

            day_token = tokens[idx + 1].replace("O", "0").replace("I", "1").replace("G", "6")
            year_token = tokens[idx + 2].replace("O", "0").replace("I", "1")
            if not day_token.isdigit() or not year_token.isdigit():
                continue
            day = int(day_token)
            if day < 1 or day > 31 or len(year_token) != 4:
                continue
            candidate = f"{month} {day:02d} {year_token}"
            if repair_prefix:
                candidate = f"{candidate}"
            candidates.append(candidate)
    return _dedupe_texts(candidates)


def _select_vhs_ocr_candidate(texts: Sequence[str]) -> Optional[str]:
    dates = _extract_vhs_date_candidates(texts)
    if dates:
        return dates[0]

    digitful = [text for text in texts if re.search(r"\d", text)]
    if digitful:
        return _clean_ocr_text(digitful[0])
    return None


def _time_hints_from_vhs_dates(dates: Sequence[str]) -> Dict[str, List[str]]:
    hints: Dict[str, List[str]] = {
        "explicit_dates": [],
        "times": [],
        "weekdays": [],
        "months": [],
        "relative_phrases": [],
    }
    for date in dates:
        match = re.match(r"\b([A-Z]{3})\s+(\d{1,2})\s+(\d{4})\b", str(date).strip().upper())
        if not match:
            continue
        month, day, year = match.groups()
        month_num = _MONTH_NUMBERS.get(month)
        month_name = _MONTH_FULL_NAMES.get(month)
        if not month_num or not month_name:
            continue
        iso = f"{int(year):04d}-{month_num:02d}-{int(day):02d}"
        if iso not in hints["explicit_dates"]:
            hints["explicit_dates"].append(iso)
        if month_name not in hints["months"]:
            hints["months"].append(month_name)
    return hints


def _vhs_timestamp_variants(image: Any) -> Iterable[Tuple[str, Any, str]]:
    """Yield lower-frame OCR variants tuned for small camcorder overlays."""
    from PIL import ImageEnhance, ImageFilter, ImageOps  # type: ignore

    width, height = image.size
    crop_boxes = (
        ("lower_right", (int(width * 0.42), int(height * 0.45), width, height)),
        ("timestamp_zone", (int(width * 0.50), int(height * 0.54), width, int(height * 0.96))),
        ("bottom_band", (0, int(height * 0.48), width, height)),
    )
    for crop_name, crop_box in crop_boxes:
        crop = image.crop(crop_box)
        gray = ImageOps.grayscale(crop)
        for scale in (2, 3, 4):
            upscaled = gray.resize((gray.width * scale, gray.height * scale))
            contrasted = ImageEnhance.Contrast(upscaled).enhance(2.8).filter(ImageFilter.SHARPEN)
            thresholded = contrasted.point(lambda pixel: 255 if pixel > 120 else 0)
            yield f"{crop_name}_gray_x{scale}", contrasted, "--psm 6"
            yield f"{crop_name}_binary_x{scale}", thresholded, "--psm 6"
            yield f"{crop_name}_sparse_x{scale}", thresholded, "--psm 11"


def _run_vhs_timestamp_fallback(image: Any, image_to_string: Callable[..., str]) -> Dict[str, Any]:
    attempts: List[str] = []
    for _variant_name, variant_image, config in _vhs_timestamp_variants(image):
        try:
            raw_text = image_to_string(variant_image, config=config)
        except Exception:
            continue
        if isinstance(raw_text, str) and raw_text.strip():
            attempts.append(raw_text)

    texts = _dedupe_texts(attempts)
    candidate = _select_vhs_ocr_candidate(texts)
    return {
        "text": candidate,
        "texts": texts[:8],
        "date_candidates": _extract_vhs_date_candidates(texts),
    }


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
        image = Image.open(img_path)
        raw_text = pytesseract.image_to_string(image)
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
    fallback: Dict[str, Any] = {"text": None, "texts": [], "date_candidates": []}
    try:
        fallback = _run_vhs_timestamp_fallback(image, pytesseract.image_to_string)
    except Exception as e:
        fallback = {
            "text": None,
            "texts": [],
            "date_candidates": [],
            "error": _sanitize_error_message(e),
            "exc_type": type(e).__name__,
        }
    if fallback.get("text"):
        fallback_text = str(fallback["text"])
        fallback_time_hints = _time_hints_from_vhs_dates(fallback.get("date_candidates") or [])
        return {
            "ocr_text": fallback_text,
            "ocr_meta": _meta(
                "ok",
                engine="tesseract",
                tesseract_configured=bool(tess),
                text_length=len(fallback_text),
                strategy="vhs_timestamp_fallback",
                candidates=fallback.get("texts"),
                date_candidates=fallback.get("date_candidates"),
            ),
            "time_hints": fallback_time_hints if any(fallback_time_hints.values()) else None,
        }
    return {
        "ocr_text": None,
        "ocr_meta": _meta(
            "no_text",
            reason="empty_ocr_text",
            engine="tesseract",
            tesseract_configured=bool(tess),
            fallback_candidates=fallback.get("texts"),
            fallback_error=fallback.get("error"),
            fallback_exc_type=fallback.get("exc_type"),
        ),
    }
