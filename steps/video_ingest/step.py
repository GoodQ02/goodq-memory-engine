from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import hashlib
import json
import os
import subprocess

from GoodQ_4_All.steps.common.memory import append_long_term_summary, store_short_term_summary
from GoodQ_4_All.steps.common.tag_utils import canonicalize_taxonomy


def _default(val, d):
    return val if val is not None else d


def _histogram(items: List[str]) -> Dict[str, int]:
    h: Dict[str, int] = {}
    display_by_key: Dict[str, str] = {}
    for it in items:
        if not it:
            continue
        text = str(it).strip()
        if not text:
            continue
        key = text.casefold()
        display = display_by_key.get(key)
        if display is None:
            display = text
            display_by_key[key] = display
        h[display] = h.get(display, 0) + 1
    return h


def _summarize_video(entry: Dict[str, Any]) -> Dict[str, Any]:
    frames: List[Dict[str, Any]] = entry.get("frames") or []
    scenes: List[Dict[str, Any]] = entry.get("scenes") or []
    audio_info: Dict[str, Any] = entry.get("audio") or {}
    frame_count = len(frames)
    captioned = sum(1 for f in frames if (f.get("caption") or "").strip())
    ocrd = sum(1 for f in frames if (f.get("ocr_text") or "").strip())
    face_total = sum(len(f.get("faces") or []) for f in frames)
    faces_frames = sum(1 for f in frames if (f.get("faces") or []))
    objects = []
    objects_frames = 0
    for f in frames:
        fo = (f.get("objects") or [])
        if fo:
            objects_frames += 1
        for o in fo:
            label = o.get("label")
            if label:
                objects.append(str(label))
    tags = []
    tags_frames = 0
    for f in frames:
        ft = [str(t) for t in (f.get("tags") or [])]
        if ft:
            tags_frames += 1
        tags.extend(ft)
    ents = []
    for f in frames:
        ents.extend([str(t) for t in (f.get("entities") or [])])
    for t in (audio_info.get("tags") or []):
        tags.append(str(t))
    for e in (audio_info.get("entities") or []):
        ents.append(str(e))

    scene_summaries: List[Dict[str, Any]] = []
    for sc in scenes:
        scene_tags = [str(t) for t in (sc.get("tags") or [])]
        scene_entities = [str(t) for t in (sc.get("entities") or [])]
        scene_objects = []
        for obj in (sc.get("objects") or []):
            label = obj.get("label")
            if label:
                scene_objects.append(str(label))
        scene_summaries.append({
            "index": sc.get("index"),
            "start": sc.get("start"),
            "end": sc.get("end"),
            "duration": sc.get("duration"),
            "tags": scene_tags[:5],
            "entities": scene_entities[:5],
            "objects": [{"label": k, "count": v} for k, v in sorted(_histogram(scene_objects).items(), key=lambda kv: kv[1], reverse=True)[:5]],
        })
        tags.extend(scene_tags)
        ents.extend(scene_entities)
    ts = [float(_default(f.get("timestamp"), 0.0)) for f in frames]
    ts_range = [min(ts), max(ts)] if ts else [0.0, 0.0]
    speakers = set()
    for seg in (entry.get("speaker_transcript") or []) or []:
        sp = seg.get("speaker")
        if sp:
            speakers.add(str(sp))
    for seg in (entry.get("diarization") or []) or []:
        sp = seg.get("speaker")
        if sp:
            speakers.add(str(sp))
    tr = entry.get("transcript") or ""
    transcript_len = len(tr)
    transcript_words = len(tr.split()) if tr else 0
    audio_emotion = entry.get("audio_emotion") or []
    top_audio_emotion = audio_emotion[0]["label"] if audio_emotion else None
    seg_sent = entry.get("segments_sentiment") or []
    segment_count = len(seg_sent) if isinstance(seg_sent, list) else 0

    return {
        "video": entry.get("video"),
        "video_hash": entry.get("video_hash"),
        "frame_count": frame_count,
        "captioned_frames": captioned,
        "caption_coverage": (captioned / frame_count) if frame_count else 0.0,
        "ocr_frames": ocrd,
        "ocr_coverage": (ocrd / frame_count) if frame_count else 0.0,
        "faces_total": face_total,
        "faces_frames": faces_frames,
        "faces_coverage": (faces_frames / frame_count) if frame_count else 0.0,
        "objects_frames": objects_frames,
        "objects_top": sorted(_histogram(objects).items(), key=lambda kv: kv[1], reverse=True)[:10],
        "tags_frames": tags_frames,
        "tags_coverage": (tags_frames / frame_count) if frame_count else 0.0,
        "tags_top": sorted(_histogram(tags).items(), key=lambda kv: kv[1], reverse=True)[:10],
        "entities_top": sorted(_histogram(ents).items(), key=lambda kv: kv[1], reverse=True)[:10],
        "unique_entities_count": len(set(ents)),
        "transcript_chars": transcript_len,
        "transcript_words": transcript_words,
        "speaker_count": len(speakers),
        "top_audio_emotion": top_audio_emotion,
        "timestamp_range": ts_range,
        "scene_count": len(scenes),
        "segment_count": segment_count,
        "scene_summaries": scene_summaries,
    }


def _sha256(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _faiss_ntotal_via_env(env_name: str, index_path: Optional[str]) -> Optional[int]:
    if not index_path or not os.path.isfile(index_path):
        return None
    code = (
        "import faiss,sys; p=sys.argv[1]; "
        "print(faiss.read_index(p).ntotal)"
    )
    try:
        out = subprocess.run(
            ["conda", "run", "--no-plugins", "-n", env_name, "python", "-c", code, index_path],
            capture_output=True,
            text=True,
            check=True,
        )
        s = (out.stdout or "").strip()
        return int(s) if s.isdigit() else None
    except Exception:
        return None


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            return float(value.strip())
    except Exception:
        return None
    return None


def _segment_key(start: float, end: float) -> Tuple[float, float]:
    return (round(float(start), 3), round(float(end), 3))


def _build_segment_id(start: Optional[float], end: Optional[float], speaker: Any, text: Any) -> str:
    base = f"{'' if start is None else round(float(start), 3)}|{'' if end is None else round(float(end), 3)}|{speaker or ''}|{text or ''}"
    return hashlib.sha1(base.encode('utf-8')).hexdigest()


def _dedupe_sources(items: List[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _link_frames_audio(entry: Dict[str, Any], tolerance: float = 0.5) -> bool:
    frames = entry.get('frames')
    if not isinstance(frames, list) or not frames:
        return False

    segments_map: Dict[Tuple[float, float], Dict[str, Any]] = {}

    def ensure_segment(start: float, end: float) -> Dict[str, Any]:
        if end < start:
            start, end = end, start
        key = _segment_key(start, end)
        seg = segments_map.get(key)
        if seg is None:
            seg = {
                'start': round(float(start), 3),
                'end': round(float(end), 3),
                'sources': [],
            }
            segments_map[key] = seg
        return seg

    for raw in entry.get('speaker_transcript') or []:
        if not isinstance(raw, dict):
            continue
        start = _coerce_float(raw.get('start'))
        end = _coerce_float(raw.get('end'))
        if start is None:
            continue
        if end is None:
            end = start
        seg = ensure_segment(start, end)
        speaker = raw.get('speaker')
        if speaker and not seg.get('speaker'):
            seg['speaker'] = speaker
        text = raw.get('text')
        if text:
            seg['text'] = text
        if raw.get('words'):
            seg['words'] = raw['words']
        if raw.get('segments'):
            seg['transcript_segments'] = raw['segments']
        if raw.get('engine'):
            seg['engine'] = raw['engine']
        seg.setdefault('type', seg.get('type') or 'transcript')
        sources = seg.setdefault('sources', [])
        if 'speaker_transcript' not in sources:
            sources.append('speaker_transcript')

    for raw in entry.get('diarization') or []:
        if not isinstance(raw, dict):
            continue
        start = _coerce_float(raw.get('start'))
        end = _coerce_float(raw.get('end'))
        if start is None:
            continue
        if end is None:
            end = start
        seg = ensure_segment(start, end)
        speaker = raw.get('speaker')
        if speaker and not seg.get('speaker'):
            seg['speaker'] = speaker
        seg.setdefault('type', seg.get('type') or 'diarization')
        sources = seg.setdefault('sources', [])
        if 'diarization' not in sources:
            sources.append('diarization')

    for raw in entry.get('segments_sentiment') or []:
        if not isinstance(raw, dict):
            continue
        start = _coerce_float(raw.get('start'))
        end = _coerce_float(raw.get('end'))
        if start is None:
            continue
        if end is None:
            end = start
        seg = ensure_segment(start, end)
        if raw.get('sentiment') is not None:
            seg['sentiment'] = raw.get('sentiment')
        if raw.get('emotions') is not None:
            seg['emotions'] = raw.get('emotions')
        if raw.get('text') and not seg.get('text'):
            seg['text'] = raw.get('text')
        seg.setdefault('type', seg.get('type') or 'sentiment')
        sources = seg.setdefault('sources', [])
        if 'sentiment' not in sources:
            sources.append('sentiment')

    segments_list: List[Dict[str, Any]] = []
    for key, seg in sorted(segments_map.items(), key=lambda kv: kv[0]):
        start_val = _coerce_float(seg.get('start'))
        end_val = _coerce_float(seg.get('end'))
        if start_val is not None:
            seg['start'] = round(float(start_val), 3)
        if end_val is not None:
            seg['end'] = round(float(end_val), 3)
        seg['segment_id'] = _build_segment_id(seg.get('start'), seg.get('end'), seg.get('speaker'), seg.get('text'))
        if 'sources' in seg and isinstance(seg['sources'], list):
            seg['sources'] = _dedupe_sources(seg['sources'])
        segments_list.append(seg)

    changed = False
    any_audio_context = False
    for idx, frame in enumerate(frames):
        if not isinstance(frame, dict):
            continue
        ts = _coerce_float(frame.get('timestamp'))
        if ts is None:
            continue
        ts = round(float(ts), 3)
        if frame.get('timestamp') != ts:
            frame['timestamp'] = ts
            changed = True
        frame_hash = frame.get('hash')
        source_path = frame.get('source_path')
        if not frame_hash and isinstance(source_path, str) and os.path.isfile(source_path):
            frame_hash = _sha256(source_path)
            if frame_hash:
                frame['hash'] = frame_hash
                changed = True
        matches: List[Dict[str, Any]] = []
        for seg in segments_list:
            start_val = _coerce_float(seg.get('start'))
            end_val = _coerce_float(seg.get('end'))
            if start_val is None:
                continue
            if end_val is None:
                end_val = start_val
            if start_val - tolerance <= ts <= end_val + tolerance:
                match = {
                    'segment_id': seg['segment_id'],
                    'start': start_val,
                    'end': end_val,
                }
                if seg.get('speaker') is not None:
                    match['speaker'] = seg.get('speaker')
                if seg.get('text'):
                    match['text'] = seg.get('text')
                if seg.get('sentiment') is not None:
                    match['sentiment'] = seg.get('sentiment')
                if seg.get('emotions') is not None:
                    match['emotions'] = seg.get('emotions')
                matches.append(match)
                seg_frames = seg.setdefault('frames', [])
                frame_ref = {'index': idx, 'timestamp': ts}
                if frame_hash:
                    frame_ref['frame_hash'] = frame_hash
                if isinstance(source_path, str):
                    frame_ref['source_path'] = source_path
                if not any((ref.get('index') == frame_ref['index'] and abs(ref.get('timestamp', -9999) - frame_ref['timestamp']) < 1e-6) for ref in seg_frames):
                    seg_frames.append(frame_ref)
                    changed = True
        if matches:
            frame['audio_segments'] = matches
            any_audio_context = True
            changed = True
        elif 'audio_segments' in frame:
            frame.pop('audio_segments', None)
            changed = True

    if segments_list:
        entry['audio_segments'] = segments_list
        entry['has_audio_frame_links'] = any_audio_context
        changed = True
    else:
        removed = False
        if entry.pop('audio_segments', None) is not None:
            removed = True
        if entry.pop('has_audio_frame_links', None) is not None:
            removed = True
        if removed:
            changed = True

    return changed


def video_ingest_and_summarize(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Runs the PowerShell video ingest and emits per‑video summaries as JSON."""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    # Resolve thresholds
    scene_thresh = None
    try:
        scene_thresh = float(((cfg.get("config", {}) or {}).get("video", {}) or {}).get("scene_threshold"))
    except Exception:
        pass
    args = ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(repo_root, "scripts", "ingest_videos.ps1")]
    if scene_thresh is not None:
        args.extend(["-SceneThresh", str(scene_thresh)])
    # Limit frames a bit when running from pipeline
    args.extend(["-MaxFrames", "50"])  # safe default; configurable later
    try:
        subprocess.run(args, check=True, cwd=repo_root)
    except Exception:
        # proceed to look for last results even if process non-zero
        pass
    out_path = os.path.join(repo_root, "logs", "video_ingest_results.json")
    results: List[Dict[str, Any]] = []
    if os.path.isfile(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                results = json.load(f)
        except Exception:
            results = []
    mutated = False
    summaries = []
    db_path = (((cfg.get("paths", {}) or {}).get("db_path")) or "")
    # Global FAISS sizes via a faiss-capable env
    fe = (cfg.get("paths", {}) or {})
    faiss_text = _faiss_ntotal_via_env("goodq_text_embed", fe.get("faiss_index_path"))
    faiss_dino = _faiss_ntotal_via_env("goodq_image_caption", fe.get("faiss_dino_path"))
    faiss_clip = _faiss_ntotal_via_env("goodq_image_caption", fe.get("faiss_clip_path"))
    faiss_audio = _faiss_ntotal_via_env("goodq_audio_embed", fe.get("faiss_audio_path"))

    # Per-video enrich from DB and id_map DBs
    import sqlite3
    clip_map_db = (cfg.get("paths", {}) or {}).get("clip_id_map_db")
    dino_map_db = (cfg.get("paths", {}) or {}).get("dino_id_map_db")
    clap_map_db = (cfg.get("paths", {}) or {}).get("clap_id_map_db")
    for entry in (results or []):
        if _link_frames_audio(entry):
            mutated = True
        canonicalize_taxonomy(entry)
        summ = _summarize_video(entry)
        # Compute frame hashes from file paths
        frame_hashes = []
        for f in (entry.get("frames") or []):
            sp = f.get("source_path")
            if isinstance(sp, str) and os.path.isfile(sp):
                h = _sha256(sp)
                if h:
                    frame_hashes.append(h)
        # DB counts
        links_count = None
        embeds_count = None
        try:
            if db_path:
                con = sqlite3.connect(db_path)
                cur = con.cursor()
                # links for this video hash (frame_of)
                vh = entry.get("video_hash")
                if vh:
                    cur.execute("SELECT COUNT(*) FROM links WHERE parent_hash=? AND relation='frame_of'", (vh,))
                    r = cur.fetchone()
                    links_count = int(r[0]) if r else 0
                if frame_hashes:
                    # embeddings rows for frame hashes (text embeddings)
                    qmarks = ",".join(["?"] * len(frame_hashes))
                    cur.execute(f"SELECT COUNT(*) FROM embeddings WHERE hash IN ({qmarks})", frame_hashes)
                    r2 = cur.fetchone()
                    embeds_count = int(r2[0]) if r2 else 0
                con.close()
        except Exception:
            pass
        # Count id_map contributions for frames (CLIP/DINO) and for audio (CLAP)
        def _count_map(dbfile: Optional[str], table: str, key: str, values: List[str]) -> Optional[int]:
            if not dbfile or not os.path.isfile(dbfile) or not values:
                return None
            try:
                con = sqlite3.connect(dbfile)
                cur = con.cursor()
                q = ",".join(["?"] * len(values))
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {key} IN ({q})", values)
                c = cur.fetchone()
                con.close()
                return int(c[0]) if c else 0
            except Exception:
                return None

        clip_count = _count_map(clip_map_db, "clip_id_map", "hash", frame_hashes)
        dino_count = _count_map(dino_map_db, "dino_id_map", "hash", frame_hashes)
        # Audio CLAP count via hash of audio file
        audio_hash: Optional[str] = None
        audio_field = entry.get("audio")
        if isinstance(audio_field, str):
            audio_hash = _sha256(audio_field)
        elif isinstance(audio_field, dict):
            ah = audio_field.get("hash")
            if isinstance(ah, str):
                audio_hash = ah
            else:
                audio_path = audio_field.get("path")
                if isinstance(audio_path, str):
                    audio_hash = _sha256(audio_path)
        if not audio_hash:
            ah = entry.get("audio_hash")
            if isinstance(ah, str):
                audio_hash = ah
        clap_count = _count_map(clap_map_db, "clap_id_map", "hash", [audio_hash] if audio_hash else [])
        has_audio = bool(audio_hash)
        # Coverage ratios for ID maps
        clip_cov = (clip_count / summ["frame_count"]) if (summ["frame_count"] and clip_count is not None) else None
        dino_cov = (dino_count / summ["frame_count"]) if (summ["frame_count"] and dino_count is not None) else None
        clap_cov = 1.0 if (clap_count and clap_count > 0) else (0.0 if has_audio else None)

        # Add advisory hints for visibility (not errors)
        advisories: List[str] = []
        if summ["caption_coverage"] < 0.15:
            advisories.append("Low caption coverage (<15%)")
        if summ["ocr_coverage"] < 0.10:
            advisories.append("Low OCR coverage (<10%)")
        if (clip_cov or 0) < 0.50:
            advisories.append("CLIP coverage <50% of frames")
        if (dino_cov or 0) < 0.50:
            advisories.append("DINO coverage <50% of frames")
        if has_audio and (clap_count or 0) == 0:
            advisories.append("No CLAP embedding for audio track")

        audio_info = entry.get("audio") or {}
        audio_meta = audio_info.get("metadata") or {}
        audio_sentiment = entry.get("sentiment") or audio_info.get("sentiment")
        audio_text_emotions = entry.get("emotions") or audio_info.get("emotions") or []
        audio_tags = [str(t) for t in (audio_info.get("tags") or [])]
        audio_entities = [str(t) for t in (audio_info.get("entities") or [])]
        audio_summary = {
            "duration_sec": audio_meta.get("duration_sec"),
            "sentiment": audio_sentiment,
            "top_emotions": audio_text_emotions[:5] if isinstance(audio_text_emotions, list) else audio_text_emotions,
            "audio_emotion": summ.get("top_audio_emotion"),
            "clap_count": clap_count,
            "clap_coverage": clap_cov,
            "speaker_count": summ.get("speaker_count"),
            "transcript_words": summ.get("transcript_words"),
            "top_tags": [{"label": k, "count": v} for k, v in sorted(_histogram(audio_tags).items(), key=lambda kv: kv[1], reverse=True)[:5]],
            "top_entities": [{"label": k, "count": v} for k, v in sorted(_histogram(audio_entities).items(), key=lambda kv: kv[1], reverse=True)[:5]],
        }

        summ.update({
            "db_links_frame_of": links_count,
            "db_frame_embeddings": embeds_count,
            "id_map_counts": {"clip": clip_count, "dino": dino_count, "clap": clap_count},
            "id_map_coverage": {"clip": clip_cov, "dino": dino_cov, "clap": clap_cov},
            "faiss_sizes": {
                "text": faiss_text,
                "dino": faiss_dino,
                "clip": faiss_clip,
                "audio": faiss_audio,
            },
            "advisories": advisories,
            "audio_summary": audio_summary,
        })
        summaries.append(summ)
    if mutated:
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    try:
        store_short_term_summary(cfg, {"video_summaries": summaries}, category="video_ingest")
        condensed: List[Dict[str, Any]] = []
        for vs in summaries[:5]:
            condensed.append({
                "video": vs.get("video"),
                "frame_count": vs.get("frame_count"),
                "caption_coverage": vs.get("caption_coverage"),
                "ocr_coverage": vs.get("ocr_coverage"),
                "speaker_count": vs.get("speaker_count"),
                "advisories": vs.get("advisories"),
                "audio_summary": vs.get("audio_summary"),
            })
        append_long_term_summary(
            cfg,
            {"video_summaries": condensed},
            category="video_ingest",
            fields=["video_summaries"],
        )
    except Exception:
        pass
    return {"results_path": out_path, "video_summaries": summaries}
