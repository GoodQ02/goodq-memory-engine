from __future__ import annotations
from typing import Any, Dict, List, Optional

import os
import sqlite3
import time
import json

from goodq4all.lib.memory_management.diagnostics import run_all_diagnostics


def _tally(tokens: List[Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    display: Dict[str, str] = {}
    for token in tokens:
        if token is None:
            continue
        text = str(token).strip()
        if not text:
            continue
        key = text.casefold()
        if key not in display:
            display[key] = text
        counts[key] = counts.get(key, 0) + 1
    return {display[k]: counts[k] for k in display}



def _safe_int(x: Optional[int]) -> int:
    try:
        return int(x or 0)
    except Exception as e:
        return 0


def _get_faiss_ntotal(env_name: str, index_path: Optional[str]) -> Optional[int]:
    if not index_path or not os.path.isfile(index_path):
        print(f'[WARN] _get_faiss_ntotal returning None')
        return None
    import subprocess
    code = "import faiss,sys; print(faiss.read_index(sys.argv[1]).ntotal)"
    try:
        out = subprocess.run([
            "conda","run","--no-plugins","-n",env_name,
            "python","-c",code,index_path
        ], capture_output=True, text=True, check=True)
        s = (out.stdout or "").strip()
        return int(s) if s.isdigit() else None
    except Exception as e:
        print(f'[WARN] _get_faiss_ntotal returning None')
        return None


def _db_counts(db_path: Optional[str]) -> Dict[str, int]:
    counts = {"embeddings": 0, "links": 0}
    if not db_path or not os.path.isfile(db_path):
        return counts
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM embeddings"); counts["embeddings"] = _safe_int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM links"); counts["links"] = _safe_int(cur.fetchone()[0])
        con.close()
    except Exception as e:
        print(f'[ERROR] Exception in step.py line 64: {str(e)}')
        pass
    return counts


def overview(results: List[Dict[str, Any]] | None, video_summary: Dict[str, Any] | None, cfg: Dict[str, Any]) -> Dict[str, Any]:
    paths = cfg.get("paths", {}) or {}
    # Run comprehensive diagnostics and include in report
    try:
        memory_health = run_all_diagnostics(paths)
        try:
            # Also write a standalone JSON in logs for easy access
            log_dir = paths.get("log_dir")
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
                with open(os.path.join(log_dir, "memory_health_report.json"), "w", encoding="utf-8") as f:
                    json.dump(memory_health, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 82: {str(e)}')
            pass
    except Exception as e:
        memory_health = {"status": "error", "error": "diagnostics_failed"}
    # DB / FAISS status
    dbp = paths.get("db_path")
    db = _db_counts(dbp)
    faiss = {
        "text": _get_faiss_ntotal("goodq_text_embed", paths.get("faiss_index_path")),
        "dino": _get_faiss_ntotal("goodq_image_caption", paths.get("faiss_dino_path")),
        "clip": _get_faiss_ntotal("goodq_image_caption", paths.get("faiss_clip_path")),
        "audio": _get_faiss_ntotal("goodq_audio_embed", paths.get("faiss_audio_path")),
    }

    # Aggregate modalities, tags, entities across results
    mod_counts: Dict[str, int] = {}
    tags: Dict[str, int] = {}
    entities: Dict[str, int] = {}
    frames_total = 0
    # Audio insights aggregations
    music_events_counts: Dict[str, int] = {}
    time_rel_counts: Dict[str, int] = {}
    time_month_counts: Dict[str, int] = {}
    time_weekday_counts: Dict[str, int] = {}
    time_explicit_dates: Dict[str, int] = {}
    time_clock: Dict[str, int] = {}

    if results:
        for it in results:
            m = it.get("modality");
            if m: mod_counts[m] = mod_counts.get(m, 0) + 1
            if isinstance(it.get("frames"), list):
                frames_total += len(it["frames"])  # type: ignore[index]
            tag_counts = _tally(list(it.get("tags") or []))
            for lbl, cnt in tag_counts.items():
                tags[lbl] = tags.get(lbl, 0) + cnt

            entity_counts = _tally(list(it.get("entities") or []))
            for lbl, cnt in entity_counts.items():
                entities[lbl] = entities.get(lbl, 0) + cnt

            # Audio-specific rollups
            if (it.get("modality") == "audio"):
                try:
                    music_counts = _tally([ev.get("label") for ev in (it.get("music_events") or []) if isinstance(ev, dict)])
                    for lbl, cnt in music_counts.items():
                        music_events_counts[lbl] = music_events_counts.get(lbl, 0) + cnt
                except Exception as e:
                    print(f'[ERROR] Exception in step.py line 130: {str(e)}')
                    pass
                try:
                    th = it.get("time_hints") or {}
                    rel_counts = _tally(th.get("relative_phrases") or [])
                    month_counts = _tally(th.get("months") or [])
                    weekday_counts = _tally(th.get("weekdays") or [])
                    explicit_counts = _tally(th.get("explicit_dates") or [])
                    clock_counts = _tally(th.get("times") or [])
                    for lbl, cnt in rel_counts.items():
                        time_rel_counts[lbl] = time_rel_counts.get(lbl, 0) + cnt
                    for lbl, cnt in month_counts.items():
                        time_month_counts[lbl] = time_month_counts.get(lbl, 0) + cnt
                    for lbl, cnt in weekday_counts.items():
                        time_weekday_counts[lbl] = time_weekday_counts.get(lbl, 0) + cnt
                    for lbl, cnt in explicit_counts.items():
                        time_explicit_dates[lbl] = time_explicit_dates.get(lbl, 0) + cnt
                    for lbl, cnt in clock_counts.items():
                        time_clock[lbl] = time_clock.get(lbl, 0) + cnt
                except Exception as e:
                    print(f'[ERROR] Exception in step.py line 150: {str(e)}')
                    pass

    # Aggregate advisories across videos, plus scenes/segments
    advisories: Dict[str, int] = {}
    scenes_total = 0
    segments_total = 0
    speakers: Dict[str, int] = {}
    video_summaries = (video_summary or {}).get("video_summaries") or []
    for vs in video_summaries:
        for adv in (vs.get("advisories") or []):
            advisories[str(adv)] = advisories.get(str(adv), 0) + 1
        sc_count = int(vs.get("scene_count") or 0)
        scenes_total += sc_count
        # segments from diarization length if present at raw level
        segs = (vs.get("segments") or []) or []
        if isinstance(segs, list) and segs:
            segments_total += len(segs)
            for s in segs:
                sp = s.get("speaker")
                if sp:
                    speakers[str(sp)] = speakers.get(str(sp), 0) + 1

    top = lambda d: [{"label": k, "count": v} for k, v in sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:10]]

    top = lambda d: [{"label": k, "count": v} for k, v in sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:10]]

    audio_insights = {
        "top_music_events": top(music_events_counts),
        "time_hints_top": {
            "relative": top(time_rel_counts),
            "months": top(time_month_counts),
            "weekdays": top(time_weekday_counts),
            "explicit_dates": top(time_explicit_dates),
            "times": top(time_clock),
        },
    }

    return {
        "timestamp": int(time.time()),
        "memory_health_report": memory_health,
        "db": db,
        "faiss": faiss,
        "modalities": mod_counts,
        "frames_total": frames_total,
        "top_tags": top(tags),
        "top_entities": top(entities),
        "video_advisories": top(advisories),
        "scenes_total": scenes_total,
        "segments_total": segments_total,
        "top_speakers": top(speakers),
        "audio_insights": audio_insights,
    }
