from __future__ import annotations
from typing import Any, Dict, List


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def audio_speaker_merge(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Merge diarization speakers with transcript segments by temporal overlap."""
    tmeta = item.get("transcript_meta")
    meta: Dict[str, Any] = dict(tmeta) if isinstance(tmeta, dict) else {}
    segs = meta.get("segments") or []
    if not isinstance(segs, list):
        segs = []
    diar = item.get("diarization") or []
    if not isinstance(diar, list):
        diar = []

    # Nothing to merge; propagate meta if available.
    if not segs:
        out: Dict[str, Any] = {"speaker_transcript": None}
        if meta:
            speakers = sorted({str(seg.get("speaker")) for seg in segs if isinstance(seg, dict) and seg.get("speaker")})
            if speakers:
                meta["speakers"] = speakers
            out["transcript_meta"] = meta
        return out

    # If diarization is missing, surface existing segments as-is.
    if not diar:
        speakers = sorted({str(seg.get("speaker")) for seg in segs if isinstance(seg, dict) and seg.get("speaker")})
        if speakers:
            meta["speakers"] = speakers
            meta["segment_count"] = len(segs)
        if meta:
            return {"speaker_transcript": segs, "transcript_meta": meta}
        return {"speaker_transcript": segs}

    merged: List[Dict[str, Any]] = []
    for seg in segs:
        if not isinstance(seg, dict):
            continue
        try:
            s_start = float(seg.get("start") or 0.0)
        except Exception:
            s_start = 0.0
        try:
            s_end = float(seg.get("end") or s_start)
        except Exception:
            s_end = s_start
        best_speaker = seg.get("speaker")
        best_ov = 0.0
        for d in diar:
            if not isinstance(d, dict):
                continue
            try:
                d_start = float(d.get("start") or 0.0)
            except Exception:
                d_start = 0.0
            try:
                d_end = float(d.get("end") or d_start)
            except Exception:
                d_end = d_start
            ov = _overlap(s_start, s_end, d_start, d_end)
            if ov > best_ov:
                best_ov = ov
                best_speaker = d.get("speaker")
        merged_seg: Dict[str, Any] = {
            "start": s_start,
            "end": s_end if s_end >= s_start else s_start,
            "text": str(seg.get("text") or ""),
            "speaker": best_speaker,
        }
        if isinstance(seg.get("words"), list):
            merged_seg["words"] = seg["words"]
        merged.append(merged_seg)

    speakers = sorted({str(seg.get("speaker")) for seg in merged if seg.get("speaker")})
    meta["segments"] = merged
    meta["segment_count"] = len(merged)
    if speakers:
        meta["speakers"] = speakers
    return {"speaker_transcript": merged, "transcript_meta": meta}

