from __future__ import annotations
import json
import os
import sqlite3
import hashlib
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


_FAISS_ID_NAMESPACE = uuid.UUID("2f7b3122-0d88-592e-8d42-4f7a271fd942")
_FAISS_ID_MAX = (1 << 63) - 1


def to_faiss_id(raw_id: Any) -> int:
    """Map arbitrary IDs to deterministic signed-64-bit-safe FAISS IDs."""
    try:
        # Preserve legacy numeric behavior (bounded positive int space).
        return int(raw_id) % _FAISS_ID_MAX
    except (TypeError, ValueError):
        # Deterministic mapping for non-numeric scene IDs.
        return uuid.uuid5(_FAISS_ID_NAMESPACE, str(raw_id)).int & _FAISS_ID_MAX


def _connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            hash TEXT NOT NULL PRIMARY KEY,
            faiss_id INTEGER,
            source_path TEXT,
            modality TEXT,
            scene_id TEXT,
            created_at TEXT,
            sentiment_label TEXT,
            sentiment_score REAL,
            emotions_json TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_modality ON embeddings(modality)")
    try:
        cur = conn.execute("PRAGMA table_info('embeddings')")
        cols = {row[1] for row in cur.fetchall()}
        if 'scene_id' not in cols:
            conn.execute("ALTER TABLE embeddings ADD COLUMN scene_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_scene ON embeddings(scene_id)")
    except Exception as e:
        logger.warning(
            "memory operation failed operation=%s table=%s exc_type=%s exc=%s",
            "schema_migration",
            "embeddings",
            type(e).__name__,
            e,
        )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS links (
            parent_hash TEXT,
            child_hash TEXT,
            relation TEXT,
            timestamp REAL,
            meta TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_parent ON links(parent_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_child ON links(child_hash)")
    # Scenes and segments for cross-modal linking
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scenes (
            id TEXT NOT NULL PRIMARY KEY,
            video_hash TEXT,
            start REAL,
            end REAL,
            meta TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_scenes_video ON scenes(video_hash)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS segments (
            id TEXT NOT NULL PRIMARY KEY,
            video_hash TEXT,
            start REAL,
            end REAL,
            speaker TEXT,
            meta TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_segments_video ON segments(video_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_parent ON links(parent_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_links_child ON links(child_hash)")
    conn.commit()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_type TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def upsert_embedding(cfg: Dict[str, Any], hash_hex: str, faiss_id: Optional[int], source_path: str, modality: str, scene_id: Optional[str] = None) -> None:

    db_path = (cfg.get("paths", {}) or {}).get("db_path")

    if not db_path:

        return

    conn = _connect(db_path)

    try:

        now = datetime.utcnow().isoformat()

        conn.execute(

            """

            INSERT INTO embeddings(hash, faiss_id, source_path, modality, scene_id, created_at)

            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(hash) DO UPDATE SET

              faiss_id=excluded.faiss_id,

              source_path=excluded.source_path,

              modality=excluded.modality,

              scene_id=COALESCE(excluded.scene_id, embeddings.scene_id)

            """

            ,

            (hash_hex, faiss_id, source_path, modality, scene_id, now),

        )

        conn.commit()

    finally:

        conn.close()




def update_fields(cfg: Dict[str, Any], hash_hex: str, *, emotions_json: Optional[str] = None, sentiment_label: Optional[str] = None, sentiment_score: Optional[float] = None) -> None:
    db_path = (cfg.get("paths", {}) or {}).get("db_path")
    if not db_path:
        return
    conn = _connect(db_path)
    try:
        if emotions_json is not None:
            conn.execute("UPDATE embeddings SET emotions_json=? WHERE hash=?", (emotions_json, hash_hex))
        if sentiment_label is not None:
            conn.execute("UPDATE embeddings SET sentiment_label=? WHERE hash=?", (sentiment_label, hash_hex))
        if sentiment_score is not None:
            conn.execute("UPDATE embeddings SET sentiment_score=? WHERE hash=?", (sentiment_score, hash_hex))
        conn.commit()
    finally:
        conn.close()


def insert_link(cfg: Dict[str, Any], parent_hash: str, child_hash: str, relation: str, timestamp: float | None = None, meta: str | None = None) -> None:
    db_path = (cfg.get("paths", {}) or {}).get("db_path")
    if not db_path:
        return
    conn = _connect(db_path)
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES(?,?,?,?,?,?)",
            (parent_hash, child_hash, relation, timestamp, meta, now),
        )
        conn.commit()
    finally:
        conn.close()


def compute_file_hash(path: Optional[str]) -> Optional[str]:

    if not path:

        print(f'[WARN] compute_file_hash returning None')
        return None

    file_path = Path(path)

    if not file_path.exists() or not file_path.is_file():

        print(f'[WARN] compute_file_hash returning None')
        return None

    digest = hashlib.sha256()

    with file_path.open('rb') as handle:

        for chunk in iter(lambda: handle.read(1024 * 1024), b''):

            if not chunk:

                break

            digest.update(chunk)

    return digest.hexdigest()



def ensure_scene(cfg: Dict[str, Any], video_hash: str, start: float, end: float, meta: Optional[Dict[str, Any]] = None) -> str:

    return upsert_scene(cfg, video_hash, start, end, meta)



def upsert_link(cfg: Dict[str, Any], parent_hash: Optional[str], child_hash: Optional[str], relation: str, *, timestamp: Optional[float] = None, meta: Optional[Any] = None) -> None:

    if not parent_hash or not child_hash or not relation:

        return

    db_path = (cfg.get('paths', {}) or {}).get('db_path')

    if not db_path:

        return

    conn = _connect(db_path)

    try:

        now = datetime.utcnow().isoformat()

        meta_payload: Optional[str]

        if meta is None or isinstance(meta, str):

            meta_payload = meta

        else:

            try:

                meta_payload = json.dumps(meta, ensure_ascii=False)

            except Exception as e:
                logger.warning(
                    "memory operation failed operation=%s relation=%s exc_type=%s exc=%s",
                    "upsert_link.meta_serialize",
                    relation,
                    type(e).__name__,
                    e,
                )

                meta_payload = json.dumps({'value': str(meta)}, ensure_ascii=False)

        with conn:

            conn.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (parent_hash, child_hash, relation))

            conn.execute(

                "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?,?,?,?,?,?)",

                (parent_hash, child_hash, relation, timestamp, meta_payload, now),

            )

    finally:

        conn.close()



def register_scene_bundle(
    cfg: Dict[str, Any],
    *,
    video_hash: str,
    scene: Dict[str, Any],
    scene_id: str,
    detection_meta: Optional[Dict[str, Any]] = None,
    frame: Optional[Dict[str, Any]] = None,
    audio: Optional[Dict[str, Any]] = None,
    errors: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scene_start = float(scene.get('start', 0.0) or 0.0)
    scene_end = float(scene.get('end', scene_start) or scene_start)
    scene_duration = max(0.0, scene_end - scene_start)
    scene_index = scene.get('index')
    scene_confidence = scene.get('confidence')

    scene_meta: Dict[str, Any] = {
        'index': scene_index,
        'start': scene_start,
        'end': scene_end,
        'duration': scene_duration,
    }
    if scene_confidence is not None:
        scene_meta['confidence'] = scene_confidence
    if detection_meta:
        scene_meta['detection'] = detection_meta
    if errors:
        scene_meta['errors'] = errors

    frame_hash = None
    frame_timestamp = scene_start + (scene_duration / 2.0) if scene_duration > 0 else scene_start
    if isinstance(frame, dict):
        frame_path = frame.get('path')
        frame_hash = compute_file_hash(frame_path)
        frame_data = frame.get('data') if isinstance(frame.get('data'), dict) else {}
        frame_meta = {'path': frame_path, 'hash': frame_hash}
        if isinstance(frame_data, dict):
            frame_meta.update({
                'tags': frame_data.get('tags'),
                'entities': frame_data.get('entities'),
                'objects': frame_data.get('objects'),
                'caption': frame_data.get('caption'),
                'ocr_text': frame_data.get('ocr_text'),
            })
            if frame_data.get('timestamp') is not None:
                frame_timestamp = float(frame_data.get('timestamp'))
        elif frame and frame.get('timestamp') is not None:
            frame_timestamp = float(frame.get('timestamp'))
        scene_meta['keyframe'] = frame_meta

    audio_hash = None
    audio_start = scene_start
    audio_end = scene_end
    diarization: List[Dict[str, Any]] = []
    if isinstance(audio, dict):
        audio_path = audio.get('path')
        audio_hash = compute_file_hash(audio_path)
        audio_start = float(audio.get('start', scene_start) or scene_start)
        audio_end = float(audio.get('end', scene_end) or scene_end)
        audio_data = audio.get('data') if isinstance(audio.get('data'), dict) else {}
        if isinstance(audio_data, dict):
            audio_meta = {
                'path': audio_path,
                'hash': audio_hash,
                'transcript': audio_data.get('transcript'),
                'sentiment': audio_data.get('sentiment'),
                'emotions': audio_data.get('emotions'),
                'tags': audio_data.get('tags'),
                'entities': audio_data.get('entities'),
                'audio_emotion': audio_data.get('audio_emotion'),
            }
            if audio_data.get('transcript_meta') is not None:
                audio_meta['transcript_meta'] = audio_data.get('transcript_meta')
            scene_meta['audio'] = audio_meta
            # FIX: Use speaker_transcript (has text) instead of diarization (speaker labels only)
            diarization = audio_data.get('speaker_transcript') or audio_data.get('diarization') or []

    segments_created: List[str] = []
    db_path = (cfg.get('paths', {}) or {}).get('db_path')
    if db_path:
        conn = _connect(db_path)
        try:
            with conn:
                now = datetime.utcnow().isoformat()
                persisted_scene_id = _make_id("scene", [video_hash, f"{scene_start:.3f}", f"{scene_end:.3f}"])
                merged_scene_meta: Dict[str, Any] = {}
                try:
                    cur = conn.execute("SELECT meta FROM scenes WHERE id=?", (persisted_scene_id,))
                    row = cur.fetchone()
                    if row and row[0]:
                        existing = json.loads(row[0]) if row[0] else {}
                        if isinstance(existing, dict):
                            merged_scene_meta.update(existing)
                except Exception as e:
                    logger.warning(
                        "memory operation failed operation=%s scene_id=%s exc_type=%s exc=%s",
                        "register_scene_bundle.scene_meta_merge",
                        scene_id,
                        type(e).__name__,
                        e,
                    )
                if isinstance(scene_meta, dict):
                    merged_scene_meta.update(scene_meta)
                merged_scene_meta_json = json.dumps(merged_scene_meta, ensure_ascii=False)
                conn.execute(
                    "INSERT OR REPLACE INTO scenes(id, video_hash, start, end, meta, created_at) VALUES (?,?,?,?,?,?)",
                    (persisted_scene_id, video_hash, float(scene_start), float(scene_end), merged_scene_meta_json, now),
                )

                scene_of_meta = {'duration': scene_duration, 'index': scene_index}
                scene_of_meta_payload = json.dumps(scene_of_meta, ensure_ascii=False)
                conn.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (video_hash, scene_id, 'scene_of'))
                conn.execute(
                    "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?,?,?,?,?,?)",
                    (video_hash, scene_id, 'scene_of', scene_start, scene_of_meta_payload, now),
                )

                if frame_hash:
                    frame_meta = {'path': frame.get('path') if isinstance(frame, dict) else None}
                    frame_meta_payload = json.dumps(frame_meta, ensure_ascii=False)
                    conn.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (scene_id, frame_hash, 'keyframe_of'))
                    conn.execute(
                        "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?,?,?,?,?,?)",
                        (scene_id, frame_hash, 'keyframe_of', None, frame_meta_payload, now),
                    )
                    frame_of_meta = {'scene_id': scene_id, 'scene_index': scene_index}
                    frame_of_meta_payload = json.dumps(frame_of_meta, ensure_ascii=False)
                    conn.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (video_hash, frame_hash, 'frame_of'))
                    conn.execute(
                        "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?,?,?,?,?,?)",
                        (video_hash, frame_hash, 'frame_of', frame_timestamp, frame_of_meta_payload, now),
                    )

                if audio_hash:
                    audio_scene_meta = {'path': audio.get('path') if isinstance(audio, dict) else None}
                    audio_scene_meta_payload = json.dumps(audio_scene_meta, ensure_ascii=False)
                    conn.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (scene_id, audio_hash, 'audio_of_scene'))
                    conn.execute(
                        "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?,?,?,?,?,?)",
                        (scene_id, audio_hash, 'audio_of_scene', None, audio_scene_meta_payload, now),
                    )
                    audio_of_meta = {'scene_id': scene_id, 'scene_index': scene_index}
                    audio_of_meta_payload = json.dumps(audio_of_meta, ensure_ascii=False)
                    conn.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (video_hash, audio_hash, 'audio_of'))
                    conn.execute(
                        "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?,?,?,?,?,?)",
                        (video_hash, audio_hash, 'audio_of', audio_start, audio_of_meta_payload, now),
                    )

                if isinstance(diarization, list):
                    for seg in diarization:
                        if not isinstance(seg, dict):
                            continue
                        seg_start = float(seg.get('start', audio_start) or audio_start)
                        seg_end = float(seg.get('end', audio_end) or audio_end)
                        if not (0 <= seg_start < seg_end):
                            print(f'[WARN] Invalid segment times: start={seg_start}, end={seg_end}. Skipping.')
                            continue
                        seg_meta = {k: v for k, v in seg.items() if k not in ('start', 'end')}
                        seg_id = _make_id("segment", [video_hash, f"{seg_start:.3f}", f"{seg_end:.3f}", seg.get('speaker') or ""])
                        merged_seg_meta: Dict[str, Any] = {}
                        try:
                            seg_cur = conn.execute("SELECT meta FROM segments WHERE id=?", (seg_id,))
                            seg_row = seg_cur.fetchone()
                            if seg_row and seg_row[0]:
                                seg_existing = json.loads(seg_row[0]) if seg_row[0] else {}
                                if isinstance(seg_existing, dict):
                                    merged_seg_meta.update(seg_existing)
                        except Exception as e:
                            logger.warning(
                                "memory operation failed operation=%s scene_id=%s segment_id=%s exc_type=%s exc=%s",
                                "register_scene_bundle.segment_meta_merge",
                                scene_id,
                                seg_id,
                                type(e).__name__,
                                e,
                            )
                        if isinstance(seg_meta, dict):
                            merged_seg_meta.update(seg_meta)
                        seg_meta_json = json.dumps(merged_seg_meta, ensure_ascii=False)
                        conn.execute(
                            "INSERT OR REPLACE INTO segments(id, video_hash, start, end, speaker, meta, created_at) VALUES (?,?,?,?,?,?,?)",
                            (seg_id, video_hash, float(seg_start), float(seg_end), seg.get('speaker') or "", seg_meta_json, now),
                        )
                        segments_created.append(seg_id)
                        segment_of_meta = {'scene_id': scene_id}
                        segment_of_meta_payload = json.dumps(segment_of_meta, ensure_ascii=False)
                        conn.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (video_hash, seg_id, 'segment_of'))
                        conn.execute(
                            "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?,?,?,?,?,?)",
                            (video_hash, seg_id, 'segment_of', seg_start, segment_of_meta_payload, now),
                        )
                        overlap = max(0.0, min(scene_end, seg_end) - max(scene_start, seg_start))
                        overlap_meta = {'overlap': overlap}
                        if seg.get('speaker') is not None:
                            overlap_meta['speaker'] = seg.get('speaker')
                        overlap_meta_payload = json.dumps(overlap_meta, ensure_ascii=False)
                        conn.execute("DELETE FROM links WHERE parent_hash=? AND child_hash=? AND relation=?", (scene_id, seg_id, 'overlaps'))
                        conn.execute(
                            "INSERT INTO links(parent_hash, child_hash, relation, timestamp, meta, created_at) VALUES (?,?,?,?,?,?)",
                            (scene_id, seg_id, 'overlaps', None, overlap_meta_payload, now),
                        )
        finally:
            conn.close()

    # Generate and save scene summary
    try:
        from steps.common.scene_summarizer import generate_scene_summary
        summary_text = generate_scene_summary(scene_meta, cfg, use_llm=False)  # Start with template only
        if summary_text:
            summary_data = {
                'scene_id': scene_id,
                'summary': summary_text,
                'index': scene_index,
                'start': scene_start,
                'end': scene_end,
                'duration': scene_duration
            }
            # Use append_long_term_summary to avoid deletion of previous summaries
            append_long_term_summary(
                cfg,
                summary_data,
                category='scene_summary',
                fields=['scene_id', 'summary', 'index', 'start', 'end', 'duration'],
                max_entries=1000  # Allow many scene summaries
            )
    except Exception as e:
        logger.warning(
            "memory operation failed operation=%s scene_id=%s exc_type=%s exc=%s",
            "register_scene_bundle.generate_scene_summary",
            scene_id,
            type(e).__name__,
            e,
        )

    # Insert embeddings into vector memory (Qdrant/FAISS)
    vector_store_results: Dict[str, bool] = {}
    qdrant_ok: Any = 'not_attempted'
    faiss_ok: Any = 'not_attempted'
    vector_points_attempted = 0
    try:
        from steps.common.memory_manager import build_memory_router
        router = build_memory_router(cfg)
        canonical_video_id = str(video_hash)
        
        points = []
        
        # Extract image embeddings (CLIP, DINO)
        if isinstance(frame, dict) and isinstance(frame.get('data'), dict):
            frame_data = frame['data']
            
            if 'clip_embedding' in frame_data and isinstance(frame_data['clip_embedding'], list):
                points.append({
                    'id': f"{scene_id}_clip",
                    'vector': frame_data['clip_embedding'],
                    'payload': {
                        'scene_id': scene_id,
                        'video_id': canonical_video_id,
                        'video_hash': video_hash,
                        'modality': 'clip',
                        'start': scene_start,
                        'end': scene_end,
                        'timestamp': frame_timestamp,
                    }
                })
            
            if 'dino_embedding' in frame_data and isinstance(frame_data['dino_embedding'], list):
                points.append({
                    'id': f"{scene_id}_dino",
                    'vector': frame_data['dino_embedding'],
                    'payload': {
                        'scene_id': scene_id,
                        'video_id': canonical_video_id,
                        'video_hash': video_hash,
                        'modality': 'dino',
                        'start': scene_start,
                        'end': scene_end,
                        'timestamp': frame_timestamp,
                    }
                })
        
        # Extract audio embeddings (CLAP)
        if isinstance(audio, dict) and isinstance(audio.get('data'), dict):
            audio_data = audio['data']
            
            if 'clap_embedding' in audio_data and isinstance(audio_data['clap_embedding'], list):
                points.append({
                    'id': f"{scene_id}_clap",
                    'vector': audio_data['clap_embedding'],
                    'payload': {
                        'scene_id': scene_id,
                        'video_id': canonical_video_id,
                        'video_hash': video_hash,
                        'modality': 'clap',
                        'start': audio_start,
                        'end': audio_end,
                        'transcript': audio_data.get('transcript', ''),
                    }
                })
        
        # Extract text embeddings
        if isinstance(frame, dict) and isinstance(frame.get('data'), dict):
            frame_data = frame['data']
            
            if 'text_embedding' in frame_data and isinstance(frame_data['text_embedding'], list):
                points.append({
                    'id': f"{scene_id}_text",
                    'vector': frame_data['text_embedding'],
                    'payload': {
                        'scene_id': scene_id,
                        'video_id': canonical_video_id,
                        'video_hash': video_hash,
                        'modality': 'text',
                        'start': scene_start,
                        'end': scene_end,
                        'text': frame_data.get('ocr_text', '') or frame_data.get('caption', ''),
                    }
                })
        
        if points:
            vector_points_attempted = len(points)
            # Once vectors exist, parity must resolve to concrete booleans.
            qdrant_ok = False
            faiss_ok = False
            if os.environ.get("GOODQ_VECTOR_DEBUG", "").strip().lower() in ("1", "true", "yes", "y", "on"):
                try:
                    mods: Dict[str, int] = {}
                    for p in points:
                        payload = p.get("payload") if isinstance(p.get("payload"), dict) else {}
                        mod = payload.get("modality") or payload.get("model") or "unknown"
                        mods[str(mod)] = mods.get(str(mod), 0) + 1
                    print(f"[VECTOR_DEBUG] scene_vectors scene_id={scene_id} total={len(points)} by_modality={mods}")
                except Exception as e:
                    logger.warning(
                        "memory operation failed operation=%s scene_id=%s exc_type=%s exc=%s",
                        "register_scene_bundle.vector_debug",
                        scene_id,
                        type(e).__name__,
                        e,
                    )
            insert_results = router.insert(points)
            if isinstance(insert_results, dict):
                vector_store_results = {str(k): bool(v) for k, v in insert_results.items()}
                qdrant_ok = bool(vector_store_results.get('qdrant', False))
                faiss_ok = bool(vector_store_results.get('faiss', False))
            success_count = sum(1 for v in vector_store_results.values() if v)
            print(f'[VECTOR] Inserted {success_count}/{len(points)} embeddings for scene {scene_id}')
        
    except Exception as e:
        logger.warning(
            "memory operation failed operation=%s scene_id=%s exc_type=%s exc=%s",
            "register_scene_bundle.insert_vectors",
            scene_id,
            type(e).__name__,
            e,
        )
    
    return {
        'scene_id': scene_id,
        'video_id': str(video_hash),
        'frame_hash': frame_hash,
        'audio_hash': audio_hash,
        'segments': segments_created,
        'vector_points_attempted': vector_points_attempted,
        'vector_store_results': vector_store_results,
        'qdrant_ok': qdrant_ok,
        'faiss_ok': faiss_ok,
    }
def store_short_term_summary(cfg: Dict[str, Any], summary: Dict[str, Any], *, category: str = "default") -> None:
    db_path = (cfg.get("paths", {}) or {}).get("db_path")
    if not db_path:
        return
    conn = _connect(db_path)
    try:
        now = datetime.utcnow().isoformat()
        payload = json.dumps(summary, ensure_ascii=False)
        with conn:
            # TTL expiry for short-term summaries
            try:
                ttl_env = os.environ.get("GOODQ_SUMMARY_TTL_HOURS")
                ttl_h = float(ttl_env) if ttl_env else 12.0
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM summaries WHERE summary_type='short_term' AND created_at < datetime('now', ?)",
                    (f"-{ttl_h} hours",),
                )
            except Exception as e:
                logger.warning(
                    "memory operation failed operation=%s category=%s exc_type=%s exc=%s",
                    "store_short_term_summary.ttl_cleanup",
                    category,
                    type(e).__name__,
                    e,
                )
            conn.execute(
                "DELETE FROM summaries WHERE summary_type=? AND category=?",
                ("short_term", category),
            )
            conn.execute(
                "INSERT INTO summaries(summary_type, category, content, created_at) VALUES (?,?,?,?)",
                ("short_term", category, payload, now),
            )
    finally:
        conn.close()


def append_long_term_summary(
    cfg: Dict[str, Any],
    summary: Dict[str, Any],
    *,
    category: str = "default",
    fields: Optional[list[str]] = None,
    max_entries: int = 20,
) -> None:
    db_path = (cfg.get("paths", {}) or {}).get("db_path")
    if not db_path:
        return
    conn = _connect(db_path)
    try:
        now = datetime.utcnow().isoformat()
        if fields:
            payload = {k: summary.get(k) for k in fields if k in summary}
        else:
            payload = summary.copy()
        payload["_timestamp"] = now
        # compute simple deltas vs last long_term entry for this category if top_tags present
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT content FROM summaries WHERE summary_type='long_term' AND category=? ORDER BY id DESC LIMIT 1",
                (category,),
            )
            row = cur.fetchone()
            prev = json.loads(row[0]) if row and row[0] else None
            if prev and isinstance(prev, dict):
                def _tags_map(obj):
                    m = {}
                    for t in (obj.get("top_tags") or []):
                        if isinstance(t, dict) and "tag" in t and "count" in t:
                            m[str(t["tag"])]=int(t["count"])
                    return m
                curm = _tags_map(payload)
                prevm = _tags_map(prev)
                deltas = []
                keys = set(list(curm.keys()) + list(prevm.keys()))
                for k in keys:
                    deltas.append({"tag": k, "delta": int(curm.get(k,0) - prevm.get(k,0))})
                payload["deltas"] = {"top_tags": deltas}
        except Exception as e:
            logger.warning(
                "memory operation failed operation=%s category=%s exc_type=%s exc=%s",
                "append_long_term_summary.compute_deltas",
                category,
                type(e).__name__,
                e,
            )
        data = json.dumps(payload, ensure_ascii=False)
        with conn:
            conn.execute(
                "INSERT INTO summaries(summary_type, category, content, created_at) VALUES (?,?,?,?)",
                ("long_term", category, data, now),
            )
            cur = conn.execute(
                "SELECT id FROM summaries WHERE summary_type=? AND category=? ORDER BY id DESC",
                ("long_term", category),
            )
            rows = cur.fetchall()
            if rows and len(rows) > max_entries:
                # delete oldest beyond max_entries
                for rid, in rows[max_entries:]:
                    conn.execute("DELETE FROM summaries WHERE id=?", (rid,))
    finally:
        conn.close()


def _make_id(prefix: str, parts: list[str]) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(prefix.encode("utf-8"))
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


def upsert_scene(cfg: Dict[str, Any], video_hash: str, start: float, end: float, meta: Optional[Dict[str, Any]] = None) -> str:

    db_path = (cfg.get("paths", {}) or {}).get("db_path")

    if not db_path:

        return ""

    sid = _make_id("scene", [video_hash, f"{start:.3f}", f"{end:.3f}"])

    conn = _connect(db_path)

    try:

        now = datetime.utcnow().isoformat()

        merged_meta: Dict[str, Any] = {}

        try:

            cur = conn.execute("SELECT meta FROM scenes WHERE id=?", (sid,))

            row = cur.fetchone()

            if row and row[0]:

                existing = json.loads(row[0]) if row[0] else {}

                if isinstance(existing, dict):

                    merged_meta.update(existing)

        except Exception as e:
            logger.warning(
                "memory operation failed operation=%s scene_id=%s exc_type=%s exc=%s",
                "upsert_scene.merge_existing_meta",
                sid,
                type(e).__name__,
                e,
            )

        if isinstance(meta, dict):

            merged_meta.update(meta)

        m = json.dumps(merged_meta, ensure_ascii=False)

        conn.execute(

            "INSERT OR REPLACE INTO scenes(id, video_hash, start, end, meta, created_at) VALUES (?,?,?,?,?,?)",

            (sid, video_hash, float(start), float(end), m, now),

        )

        conn.commit()

    finally:

        conn.close()

    return sid




def upsert_segment(cfg: Dict[str, Any], video_hash: str, start: float, end: float, speaker: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> str:

    db_path = (cfg.get("paths", {}) or {}).get("db_path")

    if not db_path:

        return ""
    
    # Validate segment times
    if not (0 <= start < end):
        print(f'[WARN] Invalid segment times: start={start}, end={end}. Skipping.')
        return ""

    sid = _make_id("segment", [video_hash, f"{start:.3f}", f"{end:.3f}", speaker or ""])

    conn = _connect(db_path)

    try:

        now = datetime.utcnow().isoformat()

        merged_meta: Dict[str, Any] = {}

        try:

            cur = conn.execute("SELECT meta FROM segments WHERE id=?", (sid,))

            row = cur.fetchone()

            if row and row[0]:

                existing = json.loads(row[0]) if row[0] else {}

                if isinstance(existing, dict):

                    merged_meta.update(existing)

        except Exception as e:
            logger.warning(
                "memory operation failed operation=%s segment_id=%s exc_type=%s exc=%s",
                "upsert_segment.merge_existing_meta",
                sid,
                type(e).__name__,
                e,
            )

        if isinstance(meta, dict):

            merged_meta.update(meta)

        m = json.dumps(merged_meta, ensure_ascii=False)

        conn.execute(

            "INSERT OR REPLACE INTO segments(id, video_hash, start, end, speaker, meta, created_at) VALUES (?,?,?,?,?,?,?)",

            (sid, video_hash, float(start), float(end), speaker or "", m, now),

        )

        conn.commit()

    finally:

        conn.close()

    return sid




def get_scene_meta(cfg: Dict[str, Any], scene_id: str) -> Optional[Dict[str, Any]]:
    db_path = (cfg.get("paths", {}) or {}).get("db_path")
    if not db_path:
        print(f'[WARN] get_scene_meta returning None')
        return None
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT meta FROM scenes WHERE id=?", (scene_id,))
        row = cur.fetchone()
        if not row:
            print(f'[WARN] get_scene_meta returning None')
            return None
        try:
            meta = json.loads(row[0]) if row[0] else None
        except Exception as e:
            logger.warning(
                "memory operation failed operation=%s scene_id=%s exc_type=%s exc=%s",
                "get_scene_meta.deserialize",
                scene_id,
                type(e).__name__,
                e,
            )
            meta = None
        return meta if isinstance(meta, dict) else None
    finally:
        conn.close()


def scene_has_materialized(cfg: Dict[str, Any], scene_id: str, components: Optional[List[str]] = None) -> Dict[str, bool]:
    comps = components or ["keyframe", "audio"]
    meta = get_scene_meta(cfg, scene_id) or {}
    result: Dict[str, bool] = {}
    for c in comps:
        present = False
        try:
            comp = meta.get(c)
            if isinstance(comp, dict):
                h = comp.get('hash')
                present = isinstance(h, str) and len(h) > 0
        except Exception as e:
            logger.warning(
                "memory operation failed operation=%s scene_id=%s component=%s exc_type=%s exc=%s",
                "scene_has_materialized.check_component",
                scene_id,
                c,
                type(e).__name__,
                e,
            )
            present = False
        result[c] = present
    return result



def list_scenes_for_video(cfg: Dict[str, Any], video_hash: str) -> Dict[str, Any]:
    db_path = (cfg.get("paths", {}) or {}).get("db_path")
    if not db_path:
        return {"scenes": [], "detection_meta": None}
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT id, start, end, meta FROM scenes WHERE video_hash=? ORDER BY start", (video_hash,))
        rows = cur.fetchall()
    finally:
        conn.close()
    scenes: List[Dict[str, Any]] = []
    detection_meta: Optional[Dict[str, Any]] = None
    for sid, start, end, meta_json in rows:
        meta: Dict[str, Any] = {}
        if meta_json:
            try:
                meta = json.loads(meta_json)
            except Exception as e:
                logger.warning(
                    "memory operation failed operation=%s video_hash=%s scene_id=%s exc_type=%s exc=%s",
                    "list_scenes_for_video.deserialize",
                    video_hash,
                    sid,
                    type(e).__name__,
                    e,
                )
                meta = {}
        if detection_meta is None and isinstance(meta, dict):
            det = meta.get('detection')
            if isinstance(det, dict):
                detection_meta = det
        start_val = float(start or 0.0)
        end_val = float(end or start_val)
        scene_entry: Dict[str, Any] = {
            'id': sid,
            'start': start_val,
            'end': end_val,
            'meta': meta,
        }
        if isinstance(meta, dict):
            if 'index' in meta:
                scene_entry['index'] = meta.get('index')
            if 'confidence' in meta:
                scene_entry['confidence'] = meta.get('confidence')
        duration = None
        if isinstance(meta, dict):
            duration = meta.get('duration')
        if duration is None:
            duration = max(0.0, end_val - start_val)
        scene_entry['duration'] = duration
        scenes.append(scene_entry)
    return {"scenes": scenes, "detection_meta": detection_meta}
