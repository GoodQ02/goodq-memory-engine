from __future__ import annotations
from typing import Any, Dict, List

import re


def _normalize_text(t: str | None) -> str:
    return (t or "").lower()


MUSIC_EVENT_PATTERNS: List[Dict[str, Any]] = [
    {"label": "birthday_song", "regex": re.compile(r"\bhappy\s+birthday\b", re.I)},
    {"label": "christmas", "regex": re.compile(r"\b(christmas|jingle\s+bells|silent\s+night|merry\s+christmas)\b", re.I)},
    {"label": "halloween", "regex": re.compile(r"\b(halloween|trick\s+or\s+treat)\b", re.I)},
    {"label": "new_year", "regex": re.compile(r"\b(new\s+year|countdown)\b", re.I)},
    {"label": "wedding", "regex": re.compile(r"\b(wedding|here\s+comes\s+the\s+bride)\b", re.I)},
    {"label": "applause", "regex": re.compile(r"\b\[?applause\]?\b", re.I)},
    {"label": "laughter", "regex": re.compile(r"\b\[?laughter\]?\b", re.I)},
    {"label": "singing", "regex": re.compile(r"\bsinging\b", re.I)},
]


def audio_music_events(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Detect simple music/events cues from transcript and segments.

    Returns
    -------
    {
      "music_events": [{label, start?, end?, context, confidence}],
      "music_events_meta": {status}
    }
    """
    # Config
    audio_cfg = (cfg.get("audio", {}) or {})
    events_cfg = (audio_cfg.get("events", {}) or {})
    if events_cfg.get("enabled") is False:
        return {"music_events": [], "music_events_meta": {"status": "disabled"}}
    min_conf = float(events_cfg.get("min_confidence")) if events_cfg.get("min_confidence") is not None else 0.6

    # Load custom patterns if provided
    patterns: List[Dict[str, Any]] = []
    try:
        for p in (events_cfg.get("patterns") or []):
            lbl = p.get("label"); rg = p.get("regex")
            if not lbl or not rg:
                continue
            patterns.append({"label": str(lbl), "regex": re.compile(str(rg), re.I)})
    except Exception:
        patterns = []
    if not patterns:
        patterns = MUSIC_EVENT_PATTERNS

    text = _normalize_text(item.get("transcript"))
    segs = (item.get("transcript_meta") or {}).get("segments") if isinstance(item.get("transcript_meta"), dict) else None
    events: List[Dict[str, Any]] = []

    # If segments exist, search per segment to get timestamps.
    if isinstance(segs, list) and segs:
        for seg in segs:
            seg_text = _normalize_text(seg.get("text")) if isinstance(seg, dict) else ""
            if not seg_text:
                continue
            for pat in patterns:
                if pat["regex"].search(seg_text):
                    events.append({
                        "label": pat["label"],
                        "start": float(seg.get("start") or 0.0) if isinstance(seg, dict) else None,
                        "end": float(seg.get("end") or 0.0) if isinstance(seg, dict) else None,
                        "context": (seg.get("text") or "")[:200] if isinstance(seg, dict) else "",
                        "confidence": max(0.7, min_conf),
                    })
    else:
        # Fallback: whole-text scan
        for pat in patterns:
            if pat["regex"].search(text):
                # no timestamps available
                # include short excerpt around the first match
                m = pat["regex"].search(text)
                ctx = text[max(0, (m.start() if m else 0) - 40): (m.end() if m else 0) + 40]
                events.append({
                    "label": pat["label"],
                    "context": ctx.strip(),
                    "confidence": max(0.6, min_conf),
                })

    return {
        "music_events": events,
        "music_events_meta": {"status": "ok" if events else "none"},
    }
