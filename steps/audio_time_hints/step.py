from __future__ import annotations
from typing import Any, Dict, List

import re
from datetime import datetime


MONTHS = (
    "january","february","march","april","may","june",
    "july","august","september","october","november","december"
)
WEEKDAYS = ("monday","tuesday","wednesday","thursday","friday","saturday","sunday")


def _collect_time_hints(text: str) -> Dict[str, Any]:
    t = (text or "").lower()
    hints: Dict[str, Any] = {
        "explicit_dates": [],
        "times": [],
        "weekdays": [],
        "months": [],
        "relative_phrases": [],
    }

    # times like 3pm, 7:30 pm, 19:45
    for m in re.finditer(r"\b((?:[01]?\d|2[0-3]):[0-5]\d(?:\s?[ap]m)?)\b|\b((?:1[0-2]|0?[1-9])\s?[ap]m)\b", t):
        val = m.group(1) or m.group(2)
        if val and val not in hints["times"]:
            hints["times"].append(val)

    # dates like 12/25/2017 or 2017-12-25
    for m in re.finditer(r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4})\b", t):
        raw = m.group(1)
        try:
            iso = None
            if "/" in raw:
                mm, dd, yy = raw.split("/")
                if len(yy) == 2:
                    yy = "20" + yy  # naive 2-digit year handling
                dt = datetime(int(yy), int(mm), int(dd))
                iso = dt.date().isoformat()
            else:
                dt = datetime.fromisoformat(raw)
                iso = dt.date().isoformat()
            if iso and iso not in hints["explicit_dates"]:
                hints["explicit_dates"].append(iso)
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 47: {str(e)}')
            continue

    # month names and weekdays
    for i, name in enumerate(MONTHS):
        if name in t and name not in hints["months"]:
            hints["months"].append(name)
    for name in WEEKDAYS:
        if name in t and name not in hints["weekdays"]:
            hints["weekdays"].append(name)

    # simple relative phrases
    rel_patterns = [
        r"\btoday\b", r"\byesterday\b", r"\btomorrow\b",
        r"\blast\s+(night|week|month|year)\b",
        r"\bthis\s+(morning|afternoon|evening|weekend|week|month|year)\b",
        r"\bnext\s+(week|month|year)\b",
        r"\bon\s+(christmas|halloween|new\s+year\'?s?)\b",
    ]
    for rp in rel_patterns:
        for m in re.finditer(rp, t):
            phrase = m.group(0)
            if phrase and phrase not in hints["relative_phrases"]:
                hints["relative_phrases"].append(phrase)

    return hints


def audio_time_hints(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Extract time/date hints from transcript text.

    Returns {"time_hints": {...}, "time_hints_meta": {status}}
    """
    # Config
    audio_cfg = (cfg.get("audio", {}) or {})
    th_cfg = (audio_cfg.get("time_hints", {}) or {})
    if th_cfg.get("enabled") is False:
        return {"time_hints": {}, "time_hints_meta": {"status": "disabled"}}
    # Extend relative phrases from config
    rel_extra = [str(x).lower() for x in (th_cfg.get("relative_phrases") or [])]

    text = item.get("transcript") or ""
    segs = (item.get("transcript_meta") or {}).get("segments") if isinstance(item.get("transcript_meta"), dict) else None
    hints = _collect_time_hints(text)
    # Merge extra relative phrases that appear in text
    if rel_extra:
        t = (text or "").lower()
        for phrase in rel_extra:
            if phrase in t and phrase not in hints["relative_phrases"]:
                hints["relative_phrases"].append(phrase)

    # If we have segments, try to attach a first-seen timestamp for each hint type
    timestamps: Dict[str, float] = {}
    if isinstance(segs, list) and segs:
        for seg in segs:
            stext = (seg.get("text") or "").lower() if isinstance(seg, dict) else ""
            if not stext:
                continue
            for phrase in hints.get("relative_phrases", []):
                if phrase in stext and phrase not in timestamps:
                    timestamps[phrase] = float(seg.get("start") or 0.0)
            # crude mapping for month/weekday words
            for mon in hints.get("months", []):
                if mon in stext and mon not in timestamps:
                    timestamps[mon] = float(seg.get("start") or 0.0)
            for wd in hints.get("weekdays", []):
                if wd in stext and wd not in timestamps:
                    timestamps[wd] = float(seg.get("start") or 0.0)

    out: Dict[str, Any] = {"time_hints": hints}
    if timestamps:
        out["time_hints"]["first_seen_ts"] = timestamps
    out["time_hints_meta"] = {"status": "ok" if any(hints.values()) else "none"}
    return out
