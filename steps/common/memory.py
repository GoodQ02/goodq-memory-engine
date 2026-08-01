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


def _coerce_time(value: Any, default: float) -> float:
    """Coerce timestamp-like values without treating 0.0 as missing."""
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def to_faiss_id(raw_id: Any) -> int:
    """Map arbitrary IDs to deterministic signed-64-bit-safe FAISS IDs."""
    try:
        # Preserve legacy numeric behavior (bounded positive int space).
        return int(raw_id) % _FAISS_ID_MAX
    except (TypeError, ValueError):
        # Deterministic mapping for non-numeric scene IDs.
        return uuid.uuid5(_FAISS_ID_NAMESPACE, str(raw_id)).int & _FAISS_ID_MAX


_migrations_checked = set()


def _run_migrations(conn: sqlite3.Connection, db_path: str) -> None:
    global _migrations_checked
    abs_path = os.path.abspath(db_path)
    if abs_path in _migrations_checked:
        return

    # 1. Create schema_migrations table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # 2. Check if migration 'create_scene_text_fts' is applied
    cur = conn.execute("SELECT 1 FROM schema_migrations WHERE name = 'create_scene_text_fts'")
    if not cur.fetchone():
        now = datetime.utcnow().isoformat()
        
        # Check if the table already exists from a manual or legacy schema
        table_exists_cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='scene_text_fts'")
        if table_exists_cur.fetchone():
            conn.execute("INSERT INTO schema_migrations (name, applied_at) VALUES ('create_scene_text_fts', ?)", (now,))
            conn.commit()
            logger.info("Table scene_text_fts already exists; migration marked as applied.")
            _migrations_checked.add(abs_path)
            return

        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE scene_text_fts USING fts5(
                    scene_id,
                    video_hash,
                    content_type,
                    text
                )
                """
            )
            conn.execute("INSERT INTO schema_migrations (name, applied_at) VALUES ('create_scene_text_fts', ?)", (now,))
            conn.commit()
            logger.info("Successfully created FTS5 virtual table scene_text_fts")
        except sqlite3.OperationalError as e:
            if "no such module: fts5" in str(e).lower():
                logger.warning("FTS5 is not supported by this SQLite build. Falling back to standard table.")
                try:
                    conn.execute(
                        """
                        CREATE TABLE scene_text_fts (
                            scene_id TEXT,
                            video_hash TEXT,
                            content_type TEXT,
                            text TEXT
                        )
                        """
                    )
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_scene_text_fts_scene ON scene_text_fts(scene_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_scene_text_fts_video ON scene_text_fts(video_hash)")
                    conn.execute("INSERT INTO schema_migrations (name, applied_at) VALUES ('create_scene_text_fts', ?)", (now,))
                    conn.commit()
                    logger.info("Successfully created fallback standard table scene_text_fts")
                except Exception as e2:
                    logger.error(f"Failed to create fallback table scene_text_fts: {e2}")
                    conn.rollback()
            else:
                logger.error(f"Failed to create FTS5 table scene_text_fts: {e}")
                conn.rollback()

    _migrations_checked.add(abs_path)


def _connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            hash TEXT NOT NULL,
            faiss_id INTEGER,
            source_path TEXT,
            modality TEXT NOT NULL DEFAULT '',
            scene_id TEXT,
            created_at TEXT,
            sentiment_label TEXT,
            sentiment_score REAL,
            emotions_json TEXT,
            PRIMARY KEY (hash, modality)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_modality ON embeddings(modality)")
    try:
        cur = conn.execute("PRAGMA table_info('embeddings')")
        cols = {row[1] for row in cur.fetchall()}
        if 'scene_id' not in cols:
            conn.execute("ALTER TABLE embeddings ADD COLUMN scene_id TEXT")
        if 'vector' not in cols:
            conn.execute("ALTER TABLE embeddings ADD COLUMN vector BLOB")
        if 'tq_indices' not in cols:
            conn.execute("ALTER TABLE embeddings ADD COLUMN tq_indices BLOB")
        if 'tq_norm' not in cols:
            conn.execute("ALTER TABLE embeddings ADD COLUMN tq_norm REAL")
        if 'tq_qjl_sign' not in cols:
            conn.execute("ALTER TABLE embeddings ADD COLUMN tq_qjl_sign BLOB")
        if 'tq_norm_residual' not in cols:
            conn.execute("ALTER TABLE embeddings ADD COLUMN tq_norm_residual REAL")
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
    _run_migrations(conn, db_path)
    return conn



def _embeddings_use_modality_key(conn: sqlite3.Connection) -> bool:
    try:
        rows = conn.execute("PRAGMA table_info('embeddings')").fetchall()
    except Exception:
        return False
    pk_cols = [
        (int(row[5]), str(row[1]))
        for row in rows
        if len(row) > 5 and row[5]
    ]
    return [name for _order, name in sorted(pk_cols)] == ["hash", "modality"]


def _legacy_collision_hash(conn: sqlite3.Connection, hash_hex: str, modality: str) -> str:
    try:
        row = conn.execute("SELECT modality FROM embeddings WHERE hash=? LIMIT 1", (hash_hex,)).fetchone()
    except Exception:
        return hash_hex
    if not row:
        return hash_hex
    existing_modality = str(row[0] or "")
    if existing_modality == str(modality or ""):
        return hash_hex
    return f"{hash_hex}:{modality or 'unknown'}"


def embedding_persistence_allowed(cfg: Dict[str, Any]) -> bool:
    """Allow isolated embedding writes only for an explicit contained witness."""
    if not cfg.get("ingestion_isolation", False):
        return True

    witness = cfg.get("witness")
    paths = cfg.get("paths")
    if not isinstance(witness, dict) or not isinstance(paths, dict):
        return False
    if (
        witness.get("ingestion_isolation") is not True
        or witness.get("promotion_enabled") is not False
        or witness.get("allow_sqlite_embeddings") is not True
    ):
        return False

    artifact_root = witness.get("artifact_root")
    db_path = paths.get("db_path")
    if not isinstance(artifact_root, str) or not artifact_root.strip():
        return False
    if not isinstance(db_path, str) or not db_path.strip():
        return False
    try:
        Path(db_path).resolve().relative_to(Path(artifact_root).resolve())
    except (OSError, ValueError):
        return False
    return True


def upsert_embedding(cfg: Dict[str, Any], hash_hex: str, faiss_id: Optional[int], source_path: str, modality: str, scene_id: Optional[str] = None, vector: Optional[List[float]] = None) -> None:
    if not embedding_persistence_allowed(cfg):
        return

    db_path = (cfg.get("paths", {}) or {}).get("db_path")

    if not db_path:

        return

    conn = _connect(db_path)

    try:

        now = datetime.utcnow().isoformat()
        modality_value = str(modality or "")

        vector_bytes = None
        tq_indices_bytes = None
        tq_norm_val = None
        tq_qjl_sign_bytes = None
        tq_norm_residual_val = None

        if vector is not None:
            import numpy as np
            vector_bytes = np.array(vector, dtype=np.float32).tobytes()

            quant_routing = cfg.get("memory", {}).get("routing", {})
            quant_enabled = bool(quant_routing.get("quantization_enabled", False))
            if os.environ.get("GOODQ_QUANTIZATION_ENABLED", "").strip().lower() in ("1", "true", "yes", "y", "on"):
                quant_enabled = True

            if quant_enabled:
                try:
                    from steps.common.quantization import TurboQuantEncoder
                    encoder = TurboQuantEncoder()
                    tq_res = encoder.encode(np.array(vector, dtype=np.float32))
                    if tq_res["tq_indices"] is not None:
                         tq_indices_bytes = tq_res["tq_indices"].tobytes()
                         tq_norm_val = tq_res["tq_norm"]
                         tq_qjl_sign_bytes = tq_res["tq_qjl_sign"].tobytes()
                         tq_norm_residual_val = tq_res["tq_norm_residual"]
                except Exception as ex:
                    logger.warning(
                        "memory operation failed operation=%s exc_type=%s exc=%s",
                        "upsert_embedding.quantize",
                        type(ex).__name__,
                        ex,
                    )

        if _embeddings_use_modality_key(conn):
            conn.execute(

                """

                INSERT INTO embeddings(
                    hash, faiss_id, source_path, modality, scene_id, created_at,
                    vector, tq_indices, tq_norm, tq_qjl_sign, tq_norm_residual
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(hash, modality) DO UPDATE SET

                  faiss_id=excluded.faiss_id,

                  source_path=excluded.source_path,

                  scene_id=COALESCE(excluded.scene_id, embeddings.scene_id),

                  vector=COALESCE(excluded.vector, embeddings.vector),

                  tq_indices=COALESCE(excluded.tq_indices, embeddings.tq_indices),

                  tq_norm=COALESCE(excluded.tq_norm, embeddings.tq_norm),

                  tq_qjl_sign=COALESCE(excluded.tq_qjl_sign, embeddings.tq_qjl_sign),

                  tq_norm_residual=COALESCE(excluded.tq_norm_residual, embeddings.tq_norm_residual)

                """

                ,

                (
                    hash_hex, faiss_id, source_path, modality_value, scene_id, now,
                    vector_bytes, tq_indices_bytes, tq_norm_val, tq_qjl_sign_bytes, tq_norm_residual_val
                ),

            )
        else:
            storage_hash = _legacy_collision_hash(conn, hash_hex, modality_value)
            conn.execute(

                """

                INSERT INTO embeddings(
                    hash, faiss_id, source_path, modality, scene_id, created_at,
                    vector, tq_indices, tq_norm, tq_qjl_sign, tq_norm_residual
                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(hash) DO UPDATE SET

                  faiss_id=excluded.faiss_id,

                  source_path=excluded.source_path,

                  modality=excluded.modality,

                  scene_id=COALESCE(excluded.scene_id, embeddings.scene_id),

                  vector=COALESCE(excluded.vector, embeddings.vector),

                  tq_indices=COALESCE(excluded.tq_indices, embeddings.tq_indices),

                  tq_norm=COALESCE(excluded.tq_norm, embeddings.tq_norm),

                  tq_qjl_sign=COALESCE(excluded.tq_qjl_sign, embeddings.tq_qjl_sign),

                  tq_norm_residual=COALESCE(excluded.tq_norm_residual, embeddings.tq_norm_residual)

                """

                ,

                (
                    storage_hash, faiss_id, source_path, modality_value, scene_id, now,
                    vector_bytes, tq_indices_bytes, tq_norm_val, tq_qjl_sign_bytes, tq_norm_residual_val
                ),

            )

        conn.commit()

    finally:

        conn.close()




def update_fields(cfg: Dict[str, Any], hash_hex: str, *, emotions_json: Optional[str] = None, sentiment_label: Optional[str] = None, sentiment_score: Optional[float] = None) -> None:
    if cfg.get("ingestion_isolation", False):
        return
    db_path = (cfg.get("paths", {}) or {}).get("db_path")
    if not db_path:
        return
    conn = _connect(db_path)
    try:
        hash_pattern = f"{hash_hex}:%"
        if emotions_json is not None:
            conn.execute("UPDATE embeddings SET emotions_json=? WHERE hash=? OR hash LIKE ?", (emotions_json, hash_hex, hash_pattern))
        if sentiment_label is not None:
            conn.execute("UPDATE embeddings SET sentiment_label=? WHERE hash=? OR hash LIKE ?", (sentiment_label, hash_hex, hash_pattern))
        if sentiment_score is not None:
            conn.execute("UPDATE embeddings SET sentiment_score=? WHERE hash=? OR hash LIKE ?", (sentiment_score, hash_hex, hash_pattern))
        conn.commit()
    finally:
        conn.close()


def insert_link(cfg: Dict[str, Any], parent_hash: str, child_hash: str, relation: str, timestamp: float | None = None, meta: str | None = None) -> None:
    if cfg.get("ingestion_isolation", False):
        return
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



def ensure_scene(cfg: Dict[str, Any], video_hash: str, start: float, end: float, meta: Optional[Dict[str, Any]] = None, conn: Optional[sqlite3.Connection] = None) -> str:

    return upsert_scene(cfg, video_hash, start, end, meta, conn=conn)



def upsert_link(cfg: Dict[str, Any], parent_hash: Optional[str], child_hash: Optional[str], relation: str, *, timestamp: Optional[float] = None, meta: Optional[Any] = None) -> None:
    if cfg.get("ingestion_isolation", False):
        return

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
    epoch_id: Optional[str] = None,
    detection_meta: Optional[Dict[str, Any]] = None,
    frame: Optional[Dict[str, Any]] = None,
    audio: Optional[Dict[str, Any]] = None,
    errors: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    summary_text = None
    scene_start = _coerce_time(scene.get('start'), 0.0)
    scene_end = _coerce_time(scene.get('end'), scene_start)
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
    ocr_text = None
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
            ocr_text = frame_data.get('ocr_text')
            if frame_data.get('timestamp') is not None:
                frame_timestamp = float(frame_data.get('timestamp'))
        elif frame and frame.get('timestamp') is not None:
            frame_timestamp = float(frame.get('timestamp'))
        scene_meta['keyframe'] = frame_meta

    audio_hash = None
    audio_start = scene_start
    audio_end = scene_end
    diarization: List[Dict[str, Any]] = []
    transcript_text = None
    if isinstance(audio, dict):
        audio_path = audio.get('path')
        audio_hash = compute_file_hash(audio_path)
        audio_start = _coerce_time(audio.get('start'), scene_start)
        audio_end = _coerce_time(audio.get('end'), scene_end)
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
            transcript_text = audio_data.get('transcript')
            if audio_data.get('transcript_meta') is not None:
                audio_meta['transcript_meta'] = audio_data.get('transcript_meta')
            scene_meta['audio'] = audio_meta
            # FIX: Use speaker_transcript (has text) instead of diarization (speaker labels only)
            diarization = audio_data.get('speaker_transcript') or audio_data.get('diarization') or []

    segments_created: List[str] = []
    if cfg.get('ingestion_isolation', False):
        persisted_scene_id = _make_id("scene", [video_hash, f"{scene_start:.3f}", f"{scene_end:.3f}"])
        if isinstance(diarization, list):
            for seg in diarization:
                if not isinstance(seg, dict):
                    continue
                seg_start = _coerce_time(seg.get('start'), audio_start)
                seg_end = _coerce_time(seg.get('end'), audio_end)
                if not (0 <= seg_start < seg_end):
                    print(f'[WARN] Invalid segment times: start={seg_start}, end={seg_end}. Skipping.')
                    continue
                seg_id = _make_id("segment", [video_hash, f"{seg_start:.3f}", f"{seg_end:.3f}", seg.get('speaker') or ""])
                segments_created.append(seg_id)
    else:
        db_path = (cfg.get('paths', {}) or {}).get('db_path')
        if db_path:
            local_conn = False
            if conn is None:
                conn = _connect(db_path)
                local_conn = True
            try:
                import contextlib
                ctx = conn if local_conn else contextlib.nullcontext()
                with ctx:
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

                    # Update FTS text index inside the transaction
                    try:
                        conn.execute("DELETE FROM scene_text_fts WHERE scene_id=?", (persisted_scene_id,))
                        if ocr_text:
                            conn.execute(
                                "INSERT INTO scene_text_fts(scene_id, video_hash, content_type, text) VALUES (?,?,?,?)",
                                (persisted_scene_id, video_hash, 'ocr', str(ocr_text)),
                            )
                        if transcript_text:
                            conn.execute(
                                "INSERT INTO scene_text_fts(scene_id, video_hash, content_type, text) VALUES (?,?,?,?)",
                                (persisted_scene_id, video_hash, 'transcript', str(transcript_text)),
                            )
                    except Exception as e:
                        logger.warning(
                            "FTS index update failed for scene_id=%s exc=%s",
                            persisted_scene_id,
                            e
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
                            seg_start = _coerce_time(seg.get('start'), audio_start)
                            seg_end = _coerce_time(seg.get('end'), audio_end)
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
                if local_conn:
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
        
        # NOTE: CLIP, DINO, CLAP, and per-frame text embeddings are written
        # by their dedicated steps (image_embed_clip, image_embed_dino,
        # audio_embed_clap, text_embed) which route to the correct per-modality
        # Qdrant collections. The MemoryRouter used here routes ALL points
        # through build_text_stores() (384-dim text collection), so non-text
        # modality writes (768-dim CLIP, 1024-dim DINO, 512-dim CLAP) fail
        # silently due to dimension mismatch. Only summary text embedding
        # (384-dim) succeeds through this path.
        # Dead code removed: CLIP, DINO, CLAP, text embedding blocks.

        points = []

        # Extract summary text embedding (Phase 2)
        summary_mismatch = False
        if summary_text:
            try:
                from steps.text_embed.step import _load_st
                from steps.common.qdrant_client import build_qdrant_client
                
                model = _load_st()
                if model is not None:
                    vec = model.encode([summary_text], normalize_embeddings=True)
                    summary_vector = vec.astype("float32")[0].tolist()
                    
                    # Qdrant dimension guard
                    qdrant_dim = None
                    q_store = router.stores.get("qdrant")
                    q_client = getattr(q_store, "client", None) if q_store else None
                    if q_client and q_client.cfg.enabled:
                        try:
                            r = q_client.session.get(f"{q_client.cfg.host}/collections/{q_client.cfg.collection}", timeout=3)
                            if r.status_code == 200:
                                payload = r.json()
                                res = payload.get("result", {}) or {}
                                cfg_res = res.get("config", {}) or {}
                                params = cfg_res.get("params", {}) or {}
                                vectors = params.get("vectors", {}) or {}
                                if isinstance(vectors, dict) and isinstance(vectors.get("size"), int):
                                    qdrant_dim = int(vectors.get("size"))
                        except Exception as e:
                            logger.warning("Failed to retrieve Qdrant collection dimension: %s", e)
                            
                    # FAISS dimension guard
                    faiss_dim = None
                    f_store = router.stores.get("faiss")
                    if f_store and os.path.isfile(f_store.index_path):
                        try:
                            import faiss
                            idx = faiss.read_index(f_store.index_path)
                            faiss_dim = int(getattr(idx, "d", 0))
                        except Exception as e:
                            logger.warning("Failed to retrieve FAISS index dimension: %s", e)
                            
                    if qdrant_dim is not None and qdrant_dim != 384:
                        summary_mismatch = True
                        logger.warning(
                            "Qdrant collection %s dimension mismatch for summary: expected 384, got %s. Routing to fallback.",
                            q_client.cfg.collection if q_client else "",
                            qdrant_dim
                        )
                    if faiss_dim is not None and faiss_dim != 384:
                        summary_mismatch = True
                        logger.warning(
                            "FAISS index %s dimension mismatch for summary: expected 384, got %s. Routing to fallback.",
                            f_store.index_path if f_store else "",
                            faiss_dim
                        )
                        
                    # Compute the normalized point ID that Qdrant will use.
                    # The validator checks scene_hash == UCF vector_key, and
                    # both must be the UUID5-normalized form.
                    try:
                        from steps.common.qdrant_client import GOODQ_POINT_ID_NAMESPACE
                        import uuid as _uuid
                        _summary_raw_id = f"{scene_id}_summary"
                        _normalized_scene_hash = str(_uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, _summary_raw_id))
                    except ImportError:
                        _normalized_scene_hash = scene_id

                    summary_point = {
                        'id': f"{scene_id}_summary",
                        'vector': summary_vector,
                        'payload': {
                            'scene_id': scene_id,
                            'scene_hash': _normalized_scene_hash,
                            'video_id': canonical_video_id,
                            'video_hash': video_hash,
                            'modality': 'text',
                            'embedding_source': 'scene_summary',
                            'worker_name': 'text_embed',
                            'vector_model_tag': 'sentence-transformers/all-MiniLM-L6-v2',
                            'start': scene_start,
                            'end': scene_end,
                            'text': summary_text,
                            'ucf_promotion_status': 'staged',
                        }
                    }
                    if epoch_id:
                        summary_point['payload']['epoch_id'] = epoch_id
                    
                    if not summary_mismatch:
                        # Append as a standard text modality point in goodq_text
                        points.append(summary_point)
                    else:
                        # Route vector writes directly to the fallback collection
                        try:
                            fallback_cfg = dict(cfg)
                            fallback_cfg["qdrant"] = dict(fallback_cfg.get("qdrant", {}) or {})
                            fallback_cfg["qdrant"]["collections"] = dict(fallback_cfg["qdrant"].get("collections", {}) or {})
                            fallback_cfg["qdrant"]["collections"]["text"] = "goodq_scene_summaries_384"
                            
                            fallback_client = build_qdrant_client(fallback_cfg, dim=384, key="text")
                            if fallback_client:
                                fallback_client.upsert([summary_point])
                                logger.info("Successfully routed summary vector to fallback collection goodq_scene_summaries_384")
                                vector_store_results["qdrant_fallback"] = True
                        except Exception as fallback_err:
                            logger.warning("Failed to write to fallback Qdrant collection: %s", fallback_err)
                            
                    # Register summary embedding in SQLite
                    if not cfg.get("ingestion_isolation", False):
                        try:
                            f_id = to_faiss_id(summary_point["id"])
                            upsert_embedding(
                                cfg,
                                summary_point["id"],
                                f_id,
                                source_path="",
                                modality="text",
                                scene_id=scene_id,
                                vector=summary_point["vector"]
                            )
                        except Exception as sql_err:
                            logger.warning("Failed to register summary embedding in SQLite: %s", sql_err)
            except Exception as embed_err:
                logger.warning("Failed to generate and index summary embedding for scene_id=%s: %s", scene_id, embed_err)
        
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
                vector_store_results.update({str(k): bool(v) for k, v in insert_results.items()})
                qdrant_ok = bool(vector_store_results.get('qdrant', False))
                faiss_ok = bool(vector_store_results.get('faiss', False))
            success_count = sum(1 for v in vector_store_results.values() if v)
            print(f'[VECTOR] Inserted {success_count}/{len(points)} embeddings for scene {scene_id}')

        # Emit MemoryCommitEvent for the summary vector if it was generated (Phase 2)
        if summary_text and 'summary_point' in locals():
            try:
                from steps.common.memory_commit_events import MemoryCommitEvent, emit_memory_commit_event, utc_now_iso
                
                targets = {}
                if not summary_mismatch:
                    q_store = router.stores.get("qdrant")
                    q_ref = getattr(getattr(q_store, "client", None), "cfg", None).collection if q_store else None
                    f_store = router.stores.get("faiss")
                    f_ref = getattr(f_store, "index_path", None) if f_store else None
                    
                    targets["qdrant"] = {
                        "attempted": bool(q_store),
                        "committed": bool(vector_store_results.get("qdrant", False)),
                        "ref": q_ref,
                        "count": 1
                    }
                    targets["faiss"] = {
                        "attempted": bool(f_store),
                        "committed": bool(vector_store_results.get("faiss", False)),
                        "ref": f_ref,
                        "count": 1
                    }
                else:
                    targets["qdrant_fallback"] = {
                        "attempted": True,
                        "committed": bool(vector_store_results.get("qdrant_fallback", False)),
                        "ref": "goodq_scene_summaries_384",
                        "count": 1
                    }
                
                if not cfg.get("ingestion_isolation", False):
                    targets["sqlite_embeddings"] = {
                        "attempted": True,
                        "committed": True,
                        "ref": (cfg.get("paths", {}) or {}).get("db_path"),
                    }
                
                emit_memory_commit_event(
                    cfg,
                    MemoryCommitEvent(
                        ts_utc=utc_now_iso(),
                        scene_id=scene_id,
                        video_id=canonical_video_id,
                        modality="text",
                        model="all-MiniLM-L6-v2",
                        embedding_id=summary_point["id"],
                        component="register_scene_bundle",
                        targets=targets,
                        details={
                            "text_len": len(summary_text),
                            "is_summary": True,
                            "is_fallback": summary_mismatch,
                        }
                    )
                )
            except Exception as event_err:
                logger.warning("Failed to emit memory commit event for summary: %s", event_err)
        
    except Exception as e:
        logger.warning(
            "memory operation failed operation=%s scene_id=%s exc_type=%s exc=%s",
            "register_scene_bundle.insert_vectors",
            scene_id,
            type(e).__name__,
            e,
        )
    
    # Resolve Qdrant collection for summary point metadata
    summary_qdrant_collection = None
    summary_point_id = None
    if summary_text and 'summary_point' in locals():
        summary_point_id = summary_point.get('id')
        try:
            q_store = router.stores.get('qdrant') if 'router' in locals() else None
            q_client = getattr(q_store, 'client', None) if q_store else None
            summary_qdrant_collection = getattr(getattr(q_client, 'cfg', None), 'collection', None)
        except Exception:
            pass

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
        'summary_point_id': summary_point_id,
        'summary_qdrant_collection': summary_qdrant_collection,
        'summary_qdrant_committed': bool(vector_store_results.get('qdrant', False)) if summary_text else False,
    }
def store_short_term_summary(cfg: Dict[str, Any], summary: Dict[str, Any], *, category: str = "default") -> None:
    if cfg.get("ingestion_isolation", False):
        return
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
    if cfg.get("ingestion_isolation", False):
        return
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


def upsert_scene(cfg: Dict[str, Any], video_hash: str, start: float, end: float, meta: Optional[Dict[str, Any]] = None, conn: Optional[sqlite3.Connection] = None) -> str:
    sid = _make_id("scene", [video_hash, f"{start:.3f}", f"{end:.3f}"])
    if cfg.get("ingestion_isolation", False):
        return sid

    db_path = (cfg.get("paths", {}) or {}).get("db_path")

    if not db_path:

        return ""

    sid = _make_id("scene", [video_hash, f"{start:.3f}", f"{end:.3f}"])

    local_conn = False
    if conn is None:
        conn = _connect(db_path)
        local_conn = True

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

        if local_conn:
            conn.commit()

    finally:

        if local_conn:
            conn.close()

    return sid




def upsert_segment(cfg: Dict[str, Any], video_hash: str, start: float, end: float, speaker: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> str:
    # Validate segment times
    if not (0 <= start < end):
        print(f'[WARN] Invalid segment times: start={start}, end={end}. Skipping.')
        return ""

    sid = _make_id("segment", [video_hash, f"{start:.3f}", f"{end:.3f}", speaker or ""])
    if cfg.get("ingestion_isolation", False):
        return sid

    db_path = (cfg.get("paths", {}) or {}).get("db_path")

    if not db_path:

        return ""
    
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


def ensure_id_map_table_schema(db_path: str, table_name: str) -> None:
    """Idempotently ensure the sidecar SQLite table has the canonical schema:
    video_hash TEXT, faiss_id INTEGER, hash TEXT, source_path TEXT, created_at TEXT,
    epoch_id TEXT, scene_id TEXT, scene_hash TEXT, worker_name TEXT, vector_model_tag TEXT,
    modality TEXT, ucf_frame_id INTEGER
    with composite primary key PRIMARY KEY (video_hash, faiss_id).
    
    If the table does not exist, create it.
    If it exists but does not match, migrate it safely.
    """
    if not table_name.isidentifier():
        raise ValueError(f"Invalid table name: {table_name}")

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout=5000;")
    
    canonical_cols_list = [
        "video_hash", "faiss_id", "hash", "source_path", "created_at",
        "epoch_id", "scene_id", "scene_hash", "worker_name", "vector_model_tag",
        "modality", "ucf_frame_id"
    ]

    try:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        info = cursor.fetchall()
        
        if not info:
            # Table does not exist, create it
            conn.execute(f"""
                CREATE TABLE {table_name} (
                    video_hash TEXT,
                    faiss_id INTEGER,
                    hash TEXT,
                    source_path TEXT,
                    created_at TEXT,
                    epoch_id TEXT,
                    scene_id TEXT,
                    scene_hash TEXT,
                    worker_name TEXT,
                    vector_model_tag TEXT,
                    modality TEXT,
                    ucf_frame_id INTEGER,
                    PRIMARY KEY (video_hash, faiss_id)
                )
            """)
            conn.commit()
            logger.info(f"Created table {table_name} with canonical schema in {db_path}")
            return

        existing_cols = {row[1] for row in info}
        pk_cols = {row[1] for row in info if row[5] > 0}
        
        # Check if table matches canonical schema (column names and composite PK structure)
        mismatch = (existing_cols != set(canonical_cols_list)) or (pk_cols != {"video_hash", "faiss_id"})
        
        if mismatch:
            logger.info(f"Schema mismatch detected for table {table_name} in {db_path}. Migrating...")
            # Generate a unique temp table name
            temp_table_name = f"{table_name}_old_{uuid.uuid4().hex[:8]}"
            
            with conn:
                # Rename the old table
                conn.execute(f"ALTER TABLE {table_name} RENAME TO {temp_table_name}")
                
                # Create the new canonical table
                conn.execute(f"""
                    CREATE TABLE {table_name} (
                        video_hash TEXT,
                        faiss_id INTEGER,
                        hash TEXT,
                        source_path TEXT,
                        created_at TEXT,
                        epoch_id TEXT,
                        scene_id TEXT,
                        scene_hash TEXT,
                        worker_name TEXT,
                        vector_model_tag TEXT,
                        modality TEXT,
                        ucf_frame_id INTEGER,
                        PRIMARY KEY (video_hash, faiss_id)
                    )
                """)
                
                # Build the insert query with COALESCE for missing/null fields
                select_exprs = []
                for col in canonical_cols_list:
                    if col in existing_cols:
                        if col == "video_hash":
                            select_exprs.append("COALESCE(video_hash, '') AS video_hash")
                        elif col == "faiss_id":
                            select_exprs.append("COALESCE(faiss_id, 0) AS faiss_id")
                        else:
                            select_exprs.append(f"COALESCE({col}, NULL) AS {col}")
                    else:
                        if col == "video_hash":
                            select_exprs.append("'' AS video_hash")
                        elif col == "faiss_id":
                            select_exprs.append("0 AS faiss_id")
                        else:
                            select_exprs.append(f"NULL AS {col}")
                
                select_clause = ", ".join(select_exprs)
                insert_query = f"""
                    INSERT OR REPLACE INTO {table_name} ({', '.join(canonical_cols_list)})
                    SELECT {select_clause} FROM {temp_table_name}
                """
                conn.execute(insert_query)
                
                # Drop the temp table
                conn.execute(f"DROP TABLE {temp_table_name}")
            logger.info(f"Successfully migrated table {table_name} in {db_path}")
    except Exception as e:
        logger.error(f"Failed to ensure schema for table {table_name} in {db_path}: {e}")
        raise
    finally:
        conn.close()

