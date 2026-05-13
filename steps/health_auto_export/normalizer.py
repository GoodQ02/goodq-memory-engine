from __future__ import annotations

"""
Health Intake Normalizer (HIN v1) — schema-resilient, privacy-preserving, read-only.

This module MUST:
- tolerate unknown JSON schemas and partial payloads (never crash on drift)
- emit only derived, redacted CanonicalHealthEvent (CHE) objects

This module MUST NOT:
- write to any DBs
- call the network
- log or emit raw per-record health values, ECG waveforms, or raw timestamps

Raw health payloads are PHI-equivalent and vault-only; this normalizer produces
structure-first summaries suitable for later, explicit ingestion wiring.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import re
import uuid
from typing import Any, Iterable, Mapping, Optional, Sequence, TypedDict

from steps.common.canonical_sensitive_events import CanonicalHealthEvent, HealthCategory, HealthSource


class SchemaFingerprintV1(TypedDict):
    fingerprint_version: int
    top_level_keys_sha256: str
    top_level_key_count: int
    shape_signature_preview: str
    shape_signature_len: int
    shape_signature_sha256: str
    payload_size_bytes: int


class SourceFingerprintV1(TypedDict):
    fingerprint_version: int
    source_id: str
    received_day_utc: str


class TimeRangeV1(TypedDict, total=False):
    start_day_utc: str
    end_day_utc: str


class CanonicalHealthEventHIN(CanonicalHealthEvent, total=False):
    """
    HIN output type.

    Adds derived-only fields (safe by default):
    - time_range (day-granularity)
    - summary_stats (counts + min/max/avg only; no raw samples)
    - schema_fingerprint + source_fingerprint (structure-only fingerprints)
    - data_quality (non-interpretive flags)
    - raw_fields (structure-only metadata; no raw values)
    """

    metric_name: str
    present: bool
    time_range: TimeRangeV1
    summary_stats: dict[str, Any]
    schema_fingerprint: SchemaFingerprintV1
    source_fingerprint: SourceFingerprintV1
    data_quality: list[str]
    raw_fields: dict[str, Any]


_HIN_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "goodq4all.health_intake_normalizer.v1")

_DATE_KEY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T\\s].*)?$")
_NUMERIC_STRING_RE = re.compile(r"^\s*-?\d+(\.\d+)?\s*$")

_GENERIC_LIST_KEYS = {"data", "values", "entries", "items", "records", "measurements", "samples"}
_LIKELY_TIME_KEY_PARTS = ("time", "date", "timestamp", "ts", "start", "end", "from", "to")

_MAX_KEYS_CAPTURED = 60
_MAX_LIST_SCAN = 50_000


def normalize_health_payload(
    raw_json: dict,
    *,
    source_id: str,
    received_at_utc: str,
) -> list[CanonicalHealthEvent]:
    """
    Normalize an arbitrary JSON payload into privacy-preserving CHE summaries.

    - Never raises on schema drift (best-effort; returns [] on empty/unparseable input).
    - Emits *aggregated* CHE records (not per-sample).
    - Generalizes timestamps to day-level ranges only.
    """

    root = raw_json if isinstance(raw_json, Mapping) else None
    if not root:
        return []

    schema_fingerprint = _fingerprint_schema(root)
    received_day = _to_utc_day(received_at_utc) or "1970-01-01"
    source_fingerprint: SourceFingerprintV1 = {
        "fingerprint_version": 1,
        "source_id": str(source_id or "unknown_source"),
        "received_day_utc": received_day,
    }

    events: list[CanonicalHealthEventHIN] = []
    try:
        groups = _discover_groups(root, received_day=received_day)
    except Exception:
        groups = []

    for group in groups:
        try:
            events.append(
                _build_event(
                    group,
                    schema_fingerprint=schema_fingerprint,
                    source_fingerprint=source_fingerprint,
                    received_day=received_day,
                )
            )
        except Exception:
            # Drift tolerance: skip malformed group without failing the run.
            continue

    if events:
        return events

    # No detectable measurement arrays → emit one absence marker (not for empty payloads).
    absence = _build_absence_event(
        schema_fingerprint=schema_fingerprint,
        source_fingerprint=source_fingerprint,
        received_day=received_day,
    )
    return [absence]


def _hash_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _json_size_bytes(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    except Exception:
        return 0


def _shape_signature(value: Any, *, depth: int = 0, max_depth: int = 10) -> str:
    if depth >= max_depth:
        return "…"

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "num"
    if isinstance(value, str):
        return "str"
    if isinstance(value, Mapping):
        keys = sorted([str(k) for k in value.keys()])
        shown = keys[:_MAX_KEYS_CAPTURED]
        parts = [f"{k}:{_shape_signature(value.get(k), depth=depth + 1, max_depth=max_depth)}" for k in shown]
        suffix = f"+{len(keys) - len(shown)}" if len(keys) > len(shown) else ""
        return f"obj{{{','.join(parts)}{suffix}}}"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        length = len(value)
        sample = list(value[: min(length, 20)])
        elem_sigs: dict[str, int] = {}
        for item in sample:
            sig = _shape_signature(item, depth=depth + 1, max_depth=max_depth)
            elem_sigs[sig] = elem_sigs.get(sig, 0) + 1
        elem_parts = ",".join([f"{k}:{elem_sigs[k]}" for k in sorted(elem_sigs.keys())])
        return f"arr[len={length}]{{{elem_parts}}}"
    return f"other[{type(value).__name__}]"


def _fingerprint_schema(root: Mapping[str, Any]) -> SchemaFingerprintV1:
    top_keys = sorted([str(k) for k in root.keys()])
    top_hash = _hash_sha256("\n".join(top_keys))
    sig = _shape_signature(root)
    sig_hash = _hash_sha256(sig)
    sig_preview = sig
    if len(sig_preview) > 2048:
        sig_preview = sig_preview[:2048] + "…"
    return {
        "fingerprint_version": 1,
        "top_level_keys_sha256": top_hash,
        "top_level_key_count": len(top_keys),
        "shape_signature_preview": sig_preview,
        "shape_signature_len": len(sig),
        "shape_signature_sha256": sig_hash,
        "payload_size_bytes": _json_size_bytes(root),
    }


def _to_utc_day(value: Any) -> Optional[str]:
    dt = _to_utc_datetime(value)
    if dt is None:
        return None
    return dt.date().isoformat()


def _to_utc_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value)
        if seconds > 1_000_000_000_000:  # ms
            seconds = seconds / 1000.0
        if seconds < 1_000_000_000:  # avoid treating small numbers as epochs
            return None
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except Exception:
            return None

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None

        # Only parse strings that resemble dates/times; do not treat numeric strings as timestamps.
        if not _ISO_DATE_PREFIX_RE.match(raw):
            return None

        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        raw = raw.replace(" ", "T")
        try:
            dt = datetime.fromisoformat(raw)
        except Exception:
            try:
                d = date.fromisoformat(value.strip()[:10])
                return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            except Exception:
                return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    return None


def _path_template(path: Sequence[Any]) -> str:
    rendered: list[str] = []
    for seg in path:
        if isinstance(seg, int):
            if rendered:
                rendered[-1] = f"{rendered[-1]}[]"
            else:
                rendered.append("[]")
            continue
        if isinstance(seg, str) and _DATE_KEY_RE.match(seg):
            rendered.append("<date>")
            continue
        rendered.append(str(seg))
    return ".".join([p for p in rendered if p])


def _infer_source(source_id: str) -> HealthSource:
    src = (source_id or "").strip().lower()
    if "apple" in src or "health" in src:
        return "apple_health"
    return "other"


def _normalize_measurement_type(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "unknown"


def _infer_category(metric_name: str, path_hint: str) -> HealthCategory:
    text = f"{metric_name} {path_hint}".lower()
    if any(k in text for k in ("sleep", "bed", "asleep", "wake")):
        return "sleep"
    if any(k in text for k in ("step", "walk", "run", "distance", "energy", "exercise", "workout", "activity")):
        return "activity"
    if any(k in text for k in ("heart", "hrv", "bpm", "ecg", "blood", "pressure", "oxygen", "vo2")):
        return "heart"
    if any(k in text for k in ("calorie", "nutrition", "carb", "protein", "fat", "water")):
        return "nutrition"
    if any(k in text for k in ("mood", "stress", "mind", "mindfulness")):
        return "mood"
    return "other"


def _is_safe_label(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 80:
        return None
    if "\n" in text or "\r" in text:
        return None
    # Keep labels conservative: avoid arbitrary prose.
    if re.fullmatch(r"[A-Za-z0-9 _\\-/().]+", text) is None:
        return None
    return text


def _label_hints_from_mapping(obj: Mapping[str, Any]) -> list[str]:
    hints: list[str] = []
    for key in ("name", "title", "type", "metric", "measurement_type", "category", "group", "kind"):
        label = _is_safe_label(obj.get(key))
        if label:
            hints.append(label)
    return hints


def _date_range_hint_from_mapping(obj: Mapping[str, Any]) -> Optional[tuple[date, date]]:
    date_keys: list[date] = []
    for key in obj.keys():
        if not isinstance(key, str) or not _DATE_KEY_RE.match(key):
            continue
        try:
            date_keys.append(date.fromisoformat(key))
        except Exception:
            continue

    if len(date_keys) < 2:
        return None

    # Ensure the dict is plausibly date-grouped (values are containers).
    container_values = 0
    for val in obj.values():
        if isinstance(val, Mapping):
            container_values += 1
            continue
        if isinstance(val, Sequence) and not isinstance(val, (str, bytes, bytearray)):
            container_values += 1
            continue
    if container_values < max(2, int(len(obj) * 0.6)):
        return None

    return (min(date_keys), max(date_keys))


def _iter_numeric_values(record: Mapping[str, Any]) -> Iterable[tuple[str, float]]:
    for key, value in record.items():
        k = str(key).strip().lower()
        if any(part in k for part in _LIKELY_TIME_KEY_PARTS):
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            yield str(key), float(value)
            continue
        if isinstance(value, str) and _NUMERIC_STRING_RE.match(value):
            try:
                yield str(key), float(value.strip())
            except Exception:
                continue


def _extract_datetimes(record: Mapping[str, Any]) -> Iterable[datetime]:
    for key, value in record.items():
        key_l = str(key).strip().lower()
        dt: Optional[datetime] = None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            # Only treat numeric as timestamp if key suggests time and value is epoch-like.
            if any(part in key_l for part in _LIKELY_TIME_KEY_PARTS):
                dt = _to_utc_datetime(value)
        elif isinstance(value, str):
            dt = _to_utc_datetime(value)
        elif isinstance(value, datetime):
            dt = _to_utc_datetime(value)
        if dt is not None:
            yield dt


@dataclass(frozen=True)
class _Group:
    path_template: str
    metric_name: str
    record_count: int
    start_day_utc: str
    end_day_utc: str
    numeric_stats: dict[str, dict[str, float]]
    data_quality: list[str]
    raw_fields: dict[str, Any]


@dataclass(frozen=True)
class _Context:
    label_hints: tuple[str, ...]
    date_range_hint: Optional[tuple[date, date]]


def _discover_groups(root: Mapping[str, Any], *, received_day: str) -> list[_Group]:
    groups: list[_Group] = []

    def walk(node: Any, path: tuple[Any, ...], ctx: _Context) -> None:
        if isinstance(node, Mapping):
            grouping_hint = _date_range_hint_from_mapping(node)
            new_hint = grouping_hint or ctx.date_range_hint
            hints = list(ctx.label_hints)
            hints.extend(_label_hints_from_mapping(node))
            new_ctx = _Context(label_hints=tuple(hints[-5:]), date_range_hint=new_hint)
            for k, v in node.items():
                child_ctx = new_ctx
                # If this mapping appears to be date-grouped, pass a per-day hint down to children.
                if grouping_hint is not None and isinstance(k, str) and _DATE_KEY_RE.match(k):
                    try:
                        day = date.fromisoformat(k)
                        child_ctx = _Context(label_hints=new_ctx.label_hints, date_range_hint=(day, day))
                    except Exception:
                        child_ctx = new_ctx
                walk(v, path + (k,), child_ctx)
            return

        if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            group = _summarize_list(node, path=path, ctx=ctx, received_day=received_day)
            if group is not None:
                groups.append(group)
            for i, item in enumerate(node):
                walk(item, path + (i,), ctx)
            return

    walk(root, (), _Context(label_hints=(), date_range_hint=None))
    # Stable order: discovery order (preorder traversal).
    return groups


def _summarize_list(node_list: Sequence[Any], *, path: tuple[Any, ...], ctx: _Context, received_day: str) -> Optional[_Group]:
    if not node_list:
        return None

    path_template = _path_template(path)
    record_count = len(node_list)

    data_quality: list[str] = []
    if record_count < 3:
        data_quality.append("sparse")

    # Scan records (bounded) for numeric/time signals.
    scan_count = min(record_count, _MAX_LIST_SCAN)
    numeric_acc: dict[str, dict[str, float]] = {}
    observed_keys: set[str] = set()
    datetimes: list[datetime] = []

    any_mapping = False
    any_numeric = False

    for item in node_list[:scan_count]:
        if isinstance(item, Mapping):
            any_mapping = True
            observed_keys.update([str(k) for k in item.keys()])
            for k, num in _iter_numeric_values(item):
                any_numeric = True
                acc = numeric_acc.get(k)
                if acc is None:
                    numeric_acc[k] = {"count": 1.0, "sum": num, "min": num, "max": num}
                else:
                    acc["count"] += 1.0
                    acc["sum"] += num
                    acc["min"] = min(acc["min"], num)
                    acc["max"] = max(acc["max"], num)
            datetimes.extend(list(_extract_datetimes(item)))
            continue

        if isinstance(item, (int, float)) and not isinstance(item, bool):
            any_numeric = True
            acc = numeric_acc.get("_value")
            num = float(item)
            if acc is None:
                numeric_acc["_value"] = {"count": 1.0, "sum": num, "min": num, "max": num}
            else:
                acc["count"] += 1.0
                acc["sum"] += num
                acc["min"] = min(acc["min"], num)
                acc["max"] = max(acc["max"], num)

    if scan_count < record_count:
        data_quality.append("truncated")

    # Require some signal that this is a measurement list (numeric or timestamps).
    if not any_numeric and not datetimes and ctx.date_range_hint is None:
        return None

    # Derive day-range (generalized) from timestamps or date-key hints.
    start_day: str
    end_day: str
    if datetimes:
        start_day = min(datetimes).date().isoformat()
        end_day = max(datetimes).date().isoformat()
    elif ctx.date_range_hint is not None:
        start_day = ctx.date_range_hint[0].isoformat()
        end_day = ctx.date_range_hint[1].isoformat()
        data_quality.append("date_grouped")
    else:
        start_day = received_day
        end_day = received_day
        data_quality.append("partial")

    # Compute per-field avg, replacing sum with avg (derived-only).
    numeric_stats: dict[str, dict[str, float]] = {}
    for key, acc in numeric_acc.items():
        count = max(1.0, acc["count"])
        numeric_stats[key] = {
            "count": float(acc["count"]),
            "min": float(acc["min"]),
            "max": float(acc["max"]),
            "avg": float(acc["sum"] / count),
        }

    # Pick a best-effort metric name without hard schema coupling.
    metric_name = next(iter(ctx.label_hints), "") or _metric_name_from_path(path)
    if not metric_name:
        metric_name = "unknown_metric"
        data_quality.append("unknown_shape")

    raw_fields = {
        "path": path_template,
        "record_count": record_count,
        "scanned_count": scan_count,
        "record_kind": "object_array" if any_mapping else "numeric_array",
        "observed_keys": sorted(list(observed_keys))[:_MAX_KEYS_CAPTURED],
        "numeric_field_names": sorted(list(numeric_stats.keys()))[:_MAX_KEYS_CAPTURED],
    }

    return _Group(
        path_template=path_template,
        metric_name=metric_name,
        record_count=record_count,
        start_day_utc=start_day,
        end_day_utc=end_day,
        numeric_stats=numeric_stats,
        data_quality=data_quality,
        raw_fields=raw_fields,
    )


def _metric_name_from_path(path: Sequence[Any]) -> str:
    parts = [p for p in path if isinstance(p, str)]
    if not parts:
        return ""
    # Prefer the nearest non-generic key before the list, if possible.
    for key in reversed(parts):
        if key.strip().lower() not in _GENERIC_LIST_KEYS and not _DATE_KEY_RE.match(key):
            return key
    return parts[-1]


def _make_event_id(
    *,
    source_id: str,
    schema_fingerprint: SchemaFingerprintV1,
    group: _Group,
) -> str:
    stable = "|".join(
        [
            "hinv1",
            source_id,
            schema_fingerprint.get("shape_signature_sha256", ""),
            group.path_template,
            group.metric_name,
            group.start_day_utc,
            group.end_day_utc,
        ]
    )
    return str(uuid.uuid5(_HIN_NAMESPACE, stable))


def _build_event(
    group: _Group,
    *,
    schema_fingerprint: SchemaFingerprintV1,
    source_fingerprint: SourceFingerprintV1,
    received_day: str,
) -> CanonicalHealthEventHIN:
    event_id = _make_event_id(
        source_id=source_fingerprint["source_id"],
        schema_fingerprint=schema_fingerprint,
        group=group,
    )

    metric_name = group.metric_name
    measurement_type = _normalize_measurement_type(metric_name)
    category = _infer_category(metric_name, group.path_template)
    source = _infer_source(source_fingerprint["source_id"])

    time_range: TimeRangeV1 = {"start_day_utc": group.start_day_utc, "end_day_utc": group.end_day_utc}
    start_ts_utc = f"{group.start_day_utc}T00:00:00Z"
    end_ts_utc = f"{group.end_day_utc}T23:59:59Z"

    summary_stats = {
        "present": True,
        "count": group.record_count,
        "numeric_fields": group.numeric_stats,
    }
    if not group.numeric_stats:
        summary_stats["numeric_fields"] = {}

    che: CanonicalHealthEventHIN = {
        "schema_version": 1,
        "event_id": event_id,
        "source": source,
        "timestamp_utc": start_ts_utc,
        "category": category,
        "measurement_type": measurement_type,
        "value_ref": f"vaultref:v1/health/{event_id}",
        "start_ts_utc": start_ts_utc,
        "end_ts_utc": end_ts_utc,
        "metric_name": metric_name,
        "present": True,
        "time_range": time_range,
        "summary_stats": summary_stats,
        "schema_fingerprint": schema_fingerprint,
        "source_fingerprint": source_fingerprint,
        "data_quality": group.data_quality,
        "raw_fields": group.raw_fields,
    }

    # If time cannot be determined beyond receive-day, mark partial explicitly.
    if group.start_day_utc == received_day and group.end_day_utc == received_day and "partial" in group.data_quality:
        che["anomaly_flags"] = ["time_range_inferred_from_received_day"]

    return che


def _build_absence_event(
    *,
    schema_fingerprint: SchemaFingerprintV1,
    source_fingerprint: SourceFingerprintV1,
    received_day: str,
) -> CanonicalHealthEventHIN:
    stable = "|".join(
        [
            "hinv1_absence",
            source_fingerprint["source_id"],
            schema_fingerprint.get("shape_signature_sha256", ""),
            received_day,
        ]
    )
    event_id = str(uuid.uuid5(_HIN_NAMESPACE, stable))
    ts = f"{received_day}T00:00:00Z"
    return {
        "schema_version": 1,
        "event_id": event_id,
        "source": _infer_source(source_fingerprint["source_id"]),
        "timestamp_utc": ts,
        "category": "other",
        "measurement_type": "payload_unknown_shape",
        "value_ref": f"vaultref:v1/health/{event_id}",
        "metric_name": "unknown",
        "present": False,
        "time_range": {"start_day_utc": received_day, "end_day_utc": received_day},
        "summary_stats": {"present": False, "count": 0, "numeric_fields": {}},
        "schema_fingerprint": schema_fingerprint,
        "source_fingerprint": source_fingerprint,
        "data_quality": ["unknown_shape", "absent"],
        "raw_fields": {"note": "no detectable measurement arrays"},
    }
