from __future__ import annotations

"""
Health Auto Export adapter (healthyapps.dev) — schema-first, non-strict, read-only.

This module parses a *parsed* Health Auto Export JSON object and emits CanonicalHealthEvent
records without coupling to exact field shapes.

Safety constraints (non-negotiable):
- Do not write to memory.db.
- Do not create embeddings.
- Do not surface raw per-record health values into UI conduits.
- Treat the source JSON as vault-only; derived outputs must not contain raw measurements.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import uuid
from typing import Any, DefaultDict, Iterable, Mapping, Optional, Sequence, TypedDict

from steps.common.canonical_sensitive_events import CanonicalHealthEvent, HealthCategory, HealthSource


class CanonicalHealthEventCHE(CanonicalHealthEvent, total=False):
    """
    Adapter output type.

    `raw_fields` is a *sanitized* preservation of unknown source fields (structure-first).
    Numeric/raw measurement values must be redacted (stored as None), and only field names/types
    are preserved.
    """

    raw_fields: dict[str, Any]


_HEALTH_AUTO_EXPORT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "goodq4all.health_auto_export.v1")

_NUMERIC_STRING_RE = re.compile(r"^\s*-?\d+(\.\d+)?\s*$")
_SAFE_STRING_KEYS = {
    "unit",
    "units",
    "source",
    "sources",
    "device",
    "platform",
    "category",
    "group",
    "type",
    "subtype",
    "name",
    "title",
}


def _as_mapping(value: Any) -> Optional[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return value
    return None


def _as_sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return []


def _first_str(obj: Mapping[str, Any], keys: Sequence[str]) -> Optional[str]:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
    return None


def _normalize_measurement_type(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "unknown"


def _split_sources(source_value: Any) -> list[str]:
    if not isinstance(source_value, str):
        return []
    parts = re.split(r"[|,]", source_value)
    return [p.strip() for p in parts if p and p.strip()]


def _to_utc_iso(ts_value: Any) -> Optional[str]:
    if ts_value is None:
        return None

    if isinstance(ts_value, (int, float)) and not isinstance(ts_value, bool):
        seconds = float(ts_value)
        if seconds > 1_000_000_000_000:  # ms
            seconds = seconds / 1000.0
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    if isinstance(ts_value, datetime):
        dt = ts_value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    if isinstance(ts_value, date):
        dt = datetime(ts_value.year, ts_value.month, ts_value.day, tzinfo=timezone.utc)
        return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    if isinstance(ts_value, str):
        raw = ts_value.strip()
        if not raw:
            return None

        if _NUMERIC_STRING_RE.match(raw):
            return _to_utc_iso(float(raw))

        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        raw = raw.replace(" ", "T")
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except Exception:
            pass

        try:
            d = date.fromisoformat(ts_value.strip())
            return _to_utc_iso(d)
        except Exception:
            return None

    return None


def _detect_numeric_keys(entry: Mapping[str, Any]) -> set[str]:
    numeric_keys: set[str] = set()
    for key, value in entry.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric_keys.add(key)
            continue
        if isinstance(value, str) and _NUMERIC_STRING_RE.match(value):
            numeric_keys.add(key)
            continue
    return numeric_keys


def _sanitize_unknown_fields(entry: Mapping[str, Any], *, redacted_numeric_keys: set[str]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in entry.items():
        if key in redacted_numeric_keys:
            sanitized[key] = None
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            sanitized[key] = None
            continue
        if isinstance(value, str):
            v = value.strip()
            if key.strip().lower() in _SAFE_STRING_KEYS and len(v) <= 200:
                sanitized[key] = v
            else:
                sanitized[key] = {"_type": "str", "len": len(v)}
            continue
        if isinstance(value, bool) or value is None:
            sanitized[key] = value
            continue
        # Lists/dicts can easily contain raw values; preserve structure only.
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            sanitized[key] = {"_type": "list", "len": len(value)}
            continue
        if isinstance(value, Mapping):
            sanitized[key] = {"_type": "dict", "keys": sorted([str(k) for k in value.keys()])[:50]}
            continue
        sanitized[key] = {"_type": type(value).__name__}
    return sanitized


def _infer_category(metric_name: str, group_hint: Optional[str]) -> HealthCategory:
    if isinstance(group_hint, str):
        g = group_hint.strip().lower()
        if g in ("sleep", "activity", "heart", "nutrition", "mood", "other"):
            return g  # type: ignore[return-value]

    n = metric_name.strip().lower()
    if any(k in n for k in ("sleep", "bed", "asleep", "wake")):
        return "sleep"
    if any(k in n for k in ("step", "walk", "run", "distance", "energy", "exercise", "workout")):
        return "activity"
    if any(k in n for k in ("heart", "hr", "bpm", "ecg", "blood", "pressure", "oxygen", "vo2")):
        return "heart"
    if any(k in n for k in ("calorie", "nutrition", "carb", "protein", "fat", "water")):
        return "nutrition"
    if any(k in n for k in ("mood", "stress", "mindfulness")):
        return "mood"
    return "other"


def _make_event_id(*, kind: str, name: str, timestamp_utc: str, uid_hint: str) -> str:
    stable = f"health_auto_export|{kind}|{name}|{timestamp_utc}|{uid_hint}"
    return str(uuid.uuid5(_HEALTH_AUTO_EXPORT_NAMESPACE, stable))


def _extract_time_fields(entry: Mapping[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    start_raw = _first_str(
        entry,
        ("start_ts_utc", "startDate", "start_date", "start", "startTime", "start_time", "from", "begin"),
    )
    end_raw = _first_str(
        entry,
        ("end_ts_utc", "endDate", "end_date", "end", "endTime", "end_time", "to", "finish"),
    )
    ts_raw = _first_str(entry, ("timestamp_utc", "timestamp", "ts", "date", "datetime", "time", "createdAt", "created_at"))

    start_ts_utc = _to_utc_iso(start_raw) if start_raw else None
    end_ts_utc = _to_utc_iso(end_raw) if end_raw else None
    timestamp_utc = _to_utc_iso(ts_raw) if ts_raw else None

    if timestamp_utc is None:
        timestamp_utc = start_ts_utc or end_ts_utc

    return timestamp_utc, start_ts_utc, end_ts_utc


def _build_metric_events(metric_obj: Mapping[str, Any], *, metric_index: int) -> list[CanonicalHealthEventCHE]:
    metric_name = _first_str(metric_obj, ("name", "metric_name", "metric", "title", "type")) or "unknown_metric"
    group_hint = _first_str(metric_obj, ("group", "category", "metric_group"))
    category = _infer_category(metric_name, group_hint)
    source: HealthSource = "apple_health"

    raw_entries = metric_obj.get("data")
    if raw_entries is None:
        raw_entries = metric_obj.get("values")
    if raw_entries is None:
        raw_entries = metric_obj.get("entries")

    events: list[CanonicalHealthEventCHE] = []
    for entry_index, entry_any in enumerate(_as_sequence(raw_entries)):
        entry = _as_mapping(entry_any)
        if entry is None:
            continue

        timestamp_utc, start_ts_utc, end_ts_utc = _extract_time_fields(entry)
        if timestamp_utc is None:
            continue

        uid_hint = _first_str(entry, ("id", "uuid", "hk_uuid", "record_id", "recordId", "identifier", "guid")) or ""
        if not uid_hint:
            uid_hint = f"pos:{metric_index}:{entry_index}"

        event_id = _make_event_id(kind="metric", name=metric_name, timestamp_utc=timestamp_utc, uid_hint=uid_hint)
        numeric_keys = _detect_numeric_keys(entry)
        sources = _split_sources(entry.get("source"))

        raw_fields = {
            "record_kind": "metric",
            "metric_name": metric_name,
            "metric_group": group_hint,
            "sources": sources,
            "numeric_field_names": sorted(numeric_keys),
            "raw_field_names": sorted([str(k) for k in entry.keys()]),
            "unknown_fields": _sanitize_unknown_fields(entry, redacted_numeric_keys=numeric_keys),
        }

        che: CanonicalHealthEventCHE = {
            "schema_version": 1,
            "event_id": event_id,
            "source": source,
            "timestamp_utc": timestamp_utc,
            "category": category,
            "measurement_type": _normalize_measurement_type(metric_name),
            "value_ref": f"vaultref:v1/health/{event_id}",
            "raw_fields": raw_fields,
        }
        if start_ts_utc:
            che["start_ts_utc"] = start_ts_utc
        if end_ts_utc:
            che["end_ts_utc"] = end_ts_utc

        events.append(che)

    return events


def _build_medication_events(med_obj: Mapping[str, Any], *, med_index: int) -> list[CanonicalHealthEventCHE]:
    med_name = _first_str(med_obj, ("name", "medication", "title")) or "unknown_medication"
    source: HealthSource = "apple_health"

    raw_entries = med_obj.get("data")
    if raw_entries is None:
        raw_entries = med_obj.get("entries")

    entries: Iterable[Any]
    if raw_entries is None:
        entries = [med_obj]
    else:
        entries = _as_sequence(raw_entries)

    events: list[CanonicalHealthEventCHE] = []
    for entry_index, entry_any in enumerate(entries):
        entry = _as_mapping(entry_any)
        if entry is None:
            continue

        timestamp_utc, start_ts_utc, end_ts_utc = _extract_time_fields(entry)
        if timestamp_utc is None:
            continue

        uid_hint = _first_str(entry, ("id", "uuid", "record_id", "recordId", "identifier", "guid")) or ""
        if not uid_hint:
            uid_hint = f"pos:{med_index}:{entry_index}"

        event_id = _make_event_id(kind="medication", name=med_name, timestamp_utc=timestamp_utc, uid_hint=uid_hint)
        numeric_keys = _detect_numeric_keys(entry)

        raw_fields = {
            "record_kind": "medication",
            "medication_name": med_name,
            "numeric_field_names": sorted(numeric_keys),
            "raw_field_names": sorted([str(k) for k in entry.keys()]),
            "unknown_fields": _sanitize_unknown_fields(entry, redacted_numeric_keys=numeric_keys),
        }

        che: CanonicalHealthEventCHE = {
            "schema_version": 1,
            "event_id": event_id,
            "source": source,
            "timestamp_utc": timestamp_utc,
            "category": "other",
            "measurement_type": f"medication/{_normalize_measurement_type(med_name)}",
            "value_ref": f"vaultref:v1/health/{event_id}",
            "raw_fields": raw_fields,
        }
        if start_ts_utc:
            che["start_ts_utc"] = start_ts_utc
        if end_ts_utc:
            che["end_ts_utc"] = end_ts_utc
        events.append(che)

    return events


def parse_health_auto_export(json_obj: Any) -> list[CanonicalHealthEventCHE]:
    """
    Parse a *parsed* Health Auto Export JSON object into CanonicalHealthEvent records.
    """
    root = _as_mapping(json_obj) or {}
    data = _as_mapping(root.get("data")) or {}

    metrics = _as_sequence(data.get("metrics"))
    medications = _as_sequence(data.get("medications"))

    events: list[CanonicalHealthEventCHE] = []
    for i, metric_any in enumerate(metrics):
        metric = _as_mapping(metric_any)
        if metric is None:
            continue
        events.extend(_build_metric_events(metric, metric_index=i))

    for i, med_any in enumerate(medications):
        med = _as_mapping(med_any)
        if med is None:
            continue
        events.extend(_build_medication_events(med, med_index=i))

    return events


@dataclass(frozen=True)
class DryRunSummary:
    total_events: int
    total_metrics: int
    total_medications: int
    overall_min_ts_utc: Optional[str]
    overall_max_ts_utc: Optional[str]
    by_kind_and_name: dict[tuple[str, str], dict[str, Any]]


def dry_run_summary(json_obj: Any) -> DryRunSummary:
    events = parse_health_auto_export(json_obj)
    by_kind_and_name: DefaultDict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"count": 0, "min": None, "max": None})

    overall_min: Optional[str] = None
    overall_max: Optional[str] = None
    total_metrics = 0
    total_medications = 0

    for ev in events:
        ts = ev.get("timestamp_utc")
        raw_fields = ev.get("raw_fields") if isinstance(ev, Mapping) else None
        kind = "unknown"
        name = ev.get("measurement_type", "unknown")
        if isinstance(raw_fields, Mapping):
            rk = raw_fields.get("record_kind")
            if rk in ("metric", "medication"):
                kind = rk
            if kind == "metric" and isinstance(raw_fields.get("metric_name"), str):
                name = raw_fields["metric_name"]
            if kind == "medication" and isinstance(raw_fields.get("medication_name"), str):
                name = raw_fields["medication_name"]

        bucket = by_kind_and_name[(kind, name)]
        bucket["count"] += 1
        if isinstance(ts, str):
            bucket["min"] = ts if bucket["min"] is None or ts < bucket["min"] else bucket["min"]
            bucket["max"] = ts if bucket["max"] is None or ts > bucket["max"] else bucket["max"]
            overall_min = ts if overall_min is None or ts < overall_min else overall_min
            overall_max = ts if overall_max is None or ts > overall_max else overall_max

        if kind == "metric":
            total_metrics += 1
        elif kind == "medication":
            total_medications += 1

    return DryRunSummary(
        total_events=len(events),
        total_metrics=total_metrics,
        total_medications=total_medications,
        overall_min_ts_utc=overall_min,
        overall_max_ts_utc=overall_max,
        by_kind_and_name=dict(by_kind_and_name),
    )


def print_dry_run_report(json_obj: Any) -> None:
    summary = dry_run_summary(json_obj)
    print("Health Auto Export — dry run (read-only)")
    print(f"- total_events: {summary.total_events}")
    print(f"- metrics: {summary.total_metrics}")
    print(f"- medications: {summary.total_medications}")
    if summary.overall_min_ts_utc and summary.overall_max_ts_utc:
        print(f"- date_range_utc: {summary.overall_min_ts_utc} → {summary.overall_max_ts_utc}")
    print("")
    print("Counts by category (metric/medication) and name:")
    for (kind, name), stats in sorted(summary.by_kind_and_name.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        c = stats.get("count", 0)
        mn = stats.get("min")
        mx = stats.get("max")
        if isinstance(mn, str) and isinstance(mx, str):
            print(f"- {kind}\t{name}\tcount={c}\trange={mn} → {mx}")
        else:
            print(f"- {kind}\t{name}\tcount={c}")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _main(argv: Sequence[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("Usage: python -m steps.health_auto_export.adapter <health_auto_export.json> [--dry-run]")
        return 2
    json_path = Path(argv[1])
    obj = _load_json(json_path)
    # Default behavior is dry-run only (no persistence).
    print_dry_run_report(obj)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(__import__("sys").argv))
