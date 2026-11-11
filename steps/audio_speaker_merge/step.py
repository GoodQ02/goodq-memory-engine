from __future__ import annotations
from typing import Any, Dict, List
import math


def _timed(start, end):
    return all(type(v) in (int, float) and math.isfinite(v) for v in (start, end)) and 0 <= start < end


def _attribution(start, end, diar):
    """Attribute only fully supported intervals; retain overlap as evidence."""
    active = [d for d in diar if _timed(start, end)
              and _overlap(start, end, d['start'], d['end']) > 0]
    candidates = sorted({d['speaker'] for d in active})
    overlaps = sorted({(max(start, a['start'], b['start']), min(end, a['end'], b['end']),
                        tuple(sorted((a['speaker'], b['speaker']))))
                       for i, a in enumerate(active) for b in active[i+1:]
                       if a['speaker'] != b['speaker']
                       and _overlap(a['start'], a['end'], b['start'], b['end']) > 0})
    covered_until = start
    if len(candidates) == 1:
        for track in sorted(active, key=lambda d: (d['start'], d['end'])):
            if track['start'] > covered_until:
                break
            covered_until = max(covered_until, track['end'])
    speaker = candidates[0] if len(candidates) == 1 and covered_until >= end else None
    reason = ('timing_unavailable' if not _timed(start, end) else
              'overlapping_speakers' if overlaps else
              'multiple_speakers' if len(candidates) > 1 else
              'incomplete_speaker_support' if speaker is None else None)
    return {'speaker': speaker, 'speaker_candidates': candidates,
            'attribution_status': 'unreviewed' if speaker else 'unresolved',
            'attribution_reason': reason,
            'overlap_intervals': [{'start': a, 'end': b, 'speakers': list(speakers),
                                   'review_status': 'unreviewed'} for a, b, speakers in overlaps]}


def _word_turns(segment, diar):
    turns = []
    for word in segment["words"]:
        if not isinstance(word, dict):
            continue
        start, end = word.get("start"), word.get("end")
        timed = _timed(start, end)
        attribution = _attribution(start, end, diar)
        speaker = attribution['speaker']
        row = {"start": start if timed else segment.get("start"),
               "end": end if timed else segment.get("end"), "text": word.get("text", ""),
               **attribution, "words": [word],
               "timing_scope": "word_alignment" if timed else "containing_segment",
               }
        prev = turns[-1] if turns else None
        if (timed and speaker and prev and prev["speaker"] == speaker
                and prev["timing_scope"] == "word_alignment" and 0 <= start-prev["end"] <= .35
                and _attribution(prev['start'], end, diar)['speaker'] == speaker):
            prev["end"] = end
            prev["text"] += " " + row["text"]
            prev["words"].append(word)
        elif (not timed and prev and prev["timing_scope"] == "containing_segment"
              and prev["speaker"] == speaker
              and prev["start"] == row["start"] and prev["end"] == row["end"]):
            if prev["text"] and row["text"]:
                prev["text"] += " " + row["text"]
            elif row["text"]:
                prev["text"] = row["text"]
            prev["words"].append(word)
        else:
            turns.append(row)
    return turns


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def audio_speaker_merge(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Merge diarization speakers with transcript segments by temporal overlap."""
    if item.get('audio_evidence') is not None:
        from wsl2_audio.scene_projection import legacy_audio
        return legacy_audio(item['audio_evidence'])
    tmeta = item.get("transcript_meta")
    meta: Dict[str, Any] = dict(tmeta) if isinstance(tmeta, dict) else {}
    segs = (
        meta.get("segments")
        or item.get("segments")
        or item.get("word_timestamps")
        or []
    )
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

    diar = [d for d in diar if isinstance(d, dict) and _timed(d.get('start'), d.get('end'))
            and isinstance(d.get('speaker'), str) and d['speaker'].strip()]
    merged: List[Dict[str, Any]] = []
    for seg in segs:
        if not isinstance(seg, dict):
            continue
        if isinstance(seg.get("words"), list) and seg["words"]:
            merged.extend(_word_turns(seg, diar))
            continue
        s_start, s_end = seg.get('start'), seg.get('end')
        merged_seg: Dict[str, Any] = {
            "start": s_start,
            "end": s_end,
            "text": str(seg.get("text") or ""),
            **_attribution(s_start, s_end, diar),
            "timing_scope": "containing_segment",
        }
        if isinstance(seg.get("words"), list):
            merged_seg["words"] = seg["words"]
        merged.append(merged_seg)

    speakers = sorted({str(seg.get("speaker")) for seg in merged if seg.get("speaker")})
    meta["segments"] = merged
    meta["segment_count"] = len(merged)
    meta["speakers"] = speakers
    return {"speaker_transcript": merged, "transcript_meta": meta}
