"""Pinned Paddle OCR evidence, with dates interpreted separately from recognition."""
from __future__ import annotations

from datetime import date
import hashlib
import math
from pathlib import Path
import re
import time
from typing import Any

from steps.image_ocr.native import (
    MODEL_IDENTITIES,
    OCRRuntimeError,
    resolve_ocr_device,
    run_native_ocr,
)


def _sanitize_error_message(exc: BaseException) -> str:
    message = str(exc).strip() or type(exc).__name__
    message = re.sub(r"\b[A-Za-z]:[\\/][^\s'\"\)]+", "<path>", message)
    message = re.sub(r"\\\\[^\s'\"\)]+", "<path>", message)
    return message[:300]


def _regions(raw: dict[str, Any], size: tuple[int, int]) -> list[dict[str, Any]]:
    """Validate native parallel arrays without filtering or reordering readings."""
    arrays = [raw.get(name) for name in ("rec_texts", "rec_boxes", "rec_polys", "rec_scores")]
    if any(not isinstance(value, list) for value in arrays):
        raise OCRRuntimeError("malformed_native_result", "Missing native OCR region arrays")
    if len({len(value) for value in arrays}) != 1:
        raise OCRRuntimeError("malformed_native_result", "Native OCR region arrays are misaligned")
    width, height = size
    regions = []
    for text, box, polygon, score in zip(*arrays):
        if not isinstance(text, str):
            raise OCRRuntimeError("malformed_native_result", "Native OCR text is not a string")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) or not 0 <= score <= 1:
            raise OCRRuntimeError("malformed_native_result", "Invalid native recognition score")
        if not isinstance(box, list) or len(box) != 4:
            raise OCRRuntimeError("malformed_native_result", "Invalid native OCR box")
        if not isinstance(polygon, list) or len(polygon) < 4 or any(not isinstance(point, list) or len(point) != 2 for point in polygon):
            raise OCRRuntimeError("malformed_native_result", "Invalid native OCR polygon")
        coordinates = [*box, *(coordinate for point in polygon for coordinate in point)]
        if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) for value in coordinates):
            raise OCRRuntimeError("malformed_native_result", "Non-finite native OCR coordinates")
        if not (0 <= box[0] <= box[2] <= width and 0 <= box[1] <= box[3] <= height):
            raise OCRRuntimeError("malformed_native_result", "Native OCR box is outside source pixels")
        if any(not (0 <= x <= width and 0 <= y <= height) for x, y in polygon):
            raise OCRRuntimeError("malformed_native_result", "Native OCR polygon is outside source pixels")
        regions.append({"text": text, "bbox": box, "polygon": polygon,
                        "confidence": float(score), "confidence_kind": "recognizer_sequence_score"})
    return regions


_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december")
_MONTH_NUMBER = {name: index for index, full in enumerate(_MONTHS, 1) for name in (full, full[:3])}
_MONTH_NUMBER["sept"] = 9
_MONTH_PATTERN = "|".join(sorted(_MONTH_NUMBER, key=len, reverse=True))
_DATE_PATTERNS = (
    ("named", re.compile(rf"\b(?P<month>{_MONTH_PATTERN})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s+(?P<year>\d{{4}}|\d{{2}})\b", re.I)),
    # A named month makes compact day/year overlays separable without changing
    # the native reading. A two-digit year still has an unresolved century.
    ("named", re.compile(rf"\b(?P<month>{_MONTH_PATTERN})\.?(?P<day>\d{{1,2}})(?P<year>\d{{4}}|\d{{2}})\b", re.I)),
    ("named", re.compile(rf"\b(?P<day>\d{{1,2}})\s+(?P<month>{_MONTH_PATTERN})\.?\s*,?\s+(?P<year>\d{{4}}|\d{{2}})\b", re.I)),
    ("iso", re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")),
    ("numeric", re.compile(r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4}|\d{2})\b")),
)


def _date_hints(regions: list[dict[str, Any]], timestamp: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Interpret calendar-valid observations, never repair recognition characters."""
    hints: dict[str, Any] = {key: [] for key in ("explicit_dates", "ambiguous_dates", "times", "weekdays", "months", "relative_phrases")}
    evidence = []
    first_seen = {}
    for index, region in enumerate(regions):
        for kind, pattern in _DATE_PATTERNS:
            for match in pattern.finditer(region["text"]):
                month_text, day_text, year_text = match.group("month", "day", "year")
                month = _MONTH_NUMBER[month_text.lower()] if kind == "named" else int(month_text)
                day, year = int(day_text), int(year_text)
                short_year = len(year_text) == 2
                row = {"raw_text": region["text"], "matched_text": match.group(), "region_index": index,
                       "bbox": region["bbox"], "polygon": region["polygon"], "sample_timestamp": timestamp}
                # Slash dates can use either order; retain uncertainty if both work.
                possibilities = []
                for mm, dd in ([(month, day), (day, month)] if kind == "numeric" else [(month, day)]):
                    try:
                        value = date(2000 + year if short_year else year, mm, dd)
                    except ValueError:
                        continue
                    if value not in possibilities:
                        possibilities.append(value)
                if not possibilities:
                    row.update(status="invalid", reason="invalid_calendar_date")
                elif short_year or len(possibilities) != 1:
                    literal = match.group()
                    row.update(status="ambiguous", reason="unresolved_century" if short_year else "unresolved_numeric_date_order")
                    if literal not in hints["ambiguous_dates"]:
                        hints["ambiguous_dates"].append(literal)
                    if timestamp is not None:
                        first_seen.setdefault(literal, timestamp)
                else:
                    value = possibilities[0]
                    iso = value.isoformat()
                    row.update(status="explicit", date=iso)
                    if iso not in hints["explicit_dates"]:
                        hints["explicit_dates"].append(iso)
                    month_name = _MONTHS[value.month - 1]
                    if month_name not in hints["months"]:
                        hints["months"].append(month_name)
                    if timestamp is not None:
                        first_seen.setdefault(iso, timestamp)
                evidence.append(row)
    if first_seen:
        hints["first_seen_ts"] = first_seen
    return hints, evidence


def image_ocr(item: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Run the selected Paddle backend once; empty text and failure remain distinct."""
    started = time.perf_counter()
    detector, recognizer = MODEL_IDENTITIES.values()
    meta: dict[str, Any] = {
        "engine": "paddleocr-3.7-onnxruntime", "model": recognizer[0], "model_revision": recognizer[1],
        "detector_model": detector[0], "detector_revision": detector[1],
        "requested_implementation": recognizer[0], "effective_implementation": None,
        "strategy": "single_model_native_inference", "fallback_chain": [],
    }
    for key, source in (("sample_timestamp", "timestamp"), ("is_midpoint_sample", "is_midpoint_sample")):
        if source in item:
            meta[key] = bool(item[source]) if source == "is_midpoint_sample" else item[source]
    source = item.get("source_path")
    if not isinstance(source, str) or not Path(source).is_file():
        meta.update(status="no_source_path", reason="source_image_missing")
        return {"ocr_text": None, "ocr_meta": meta}
    try:
        device = resolve_ocr_device(cfg)
        meta.update(device=device, engine=f"paddleocr-3.7-onnxruntime-{'cpu' if device == 'cpu' else 'cuda'}")
        from PIL import Image

        with Image.open(source) as original:
            size = original.size
        meta["input_sha256"] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
        raw, runtime = run_native_ocr(source, cfg, device)
        meta.update(runtime, raw_result=raw)
        regions = _regions(raw, size)
        text = "\n".join(region["text"] for region in regions if region["text"].strip()) or None
        hints, dates = _date_hints(regions, item.get("timestamp"))
        meta.update(status="ok" if text else "no_text", accepted_text=text, accepted_regions=regions,
                    date_evidence=dates, text_length=len(text or ""), effective_implementation=recognizer[0])
        if text is None:
            meta["reason"] = "empty_ocr_text"
        return {"ocr_text": text, "ocr_meta": meta, "time_hints": hints if any(hints.values()) else None}
    except (ImportError, ModuleNotFoundError) as exc:
        meta.update(status="dependency_missing", reason="ocr_dependency_missing", exc_type=type(exc).__name__, error=_sanitize_error_message(exc))
    except Exception as exc:
        meta.update(status="error", reason=exc.reason if isinstance(exc, OCRRuntimeError) else "ocr_exception",
                    exc_type=type(exc).__name__, error=_sanitize_error_message(exc))
    finally:
        meta["duration_seconds"] = time.perf_counter() - started
    return {"ocr_text": None, "ocr_meta": meta}
