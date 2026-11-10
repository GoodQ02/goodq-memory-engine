import sqlite3
import json
import time
import random
import hashlib
import math
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Sequence
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator


from steps.common.ucf_retirement import _read_scene_retirements, assert_scene_write_allowed


def audio_occurrence_id(video_hash, scene_id, worker_name, payload):
    """Identity within a retained recording projection, independent of display rounding."""
    if worker_name == 'audio_transcribe':
        key = payload.get('utterance_id')
        if not isinstance(key, str) or not key.strip():
            raise ValueError('Recording transcript occurrence requires its native utterance ID')
    elif worker_name == 'speaker_merge':
        key = payload.get('turn_index')
        if type(key) is not int or key < 0:
            raise ValueError('Recording speaker occurrence requires its retained turn index')
    else:
        raise ValueError('Unsupported recording occurrence producer')
    if not scene_id:
        raise ValueError('Recording occurrence requires a source scene')
    value = ['recording_occurrence_v1', video_hash, scene_id, worker_name, key]
    return hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()


def read_scene_retirements(db_path, *, video_hash, epoch_id=None):
    """Read durable scene exclusions without creating a database or schema."""
    path = Path(db_path)
    if not path.exists():
        return []
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return _read_scene_retirements(conn, video_hash=video_hash, epoch_id=epoch_id)
    finally:
        conn.close()


class UCFRecord(BaseModel):
    video_hash: str = Field(..., description="Unique hash identifier of the video source")
    ucf_schema_version: str = Field("ucf.v0.1", description="UCF schema version for future-proof parsing")
    epoch_id: str = Field(..., description="Active epoch identity tracking")
    run_id: str = Field(..., description="Active ingestion run identity tracking")
    occurrence_id: str = Field("", description="Stable producer occurrence; empty preserves legacy timestamp identity")
    t_start: float = Field(..., description="Start timestamp in seconds relative to video start")
    t_end: float = Field(..., description="End timestamp in seconds relative to video start")
    modality: str = Field(..., description="Modality category (audio, video, text, multimodal)")
    worker_name: str = Field(..., description="Name of the isolated pipeline worker step")
    model_tag: str = Field(..., description="Model version or architecture tag")
    confidence: float = Field(1.0, description="Confidence score from 0.0 to 1.0")
    spatial_region: Optional[List[float]] = Field(None, description="Spatial bounding box [ymin, xmin, ymax, xmax] normalized between 0.0 and 1.0")
    spatial_space: str = Field("normalized_yxyx_top_left", description="Spatial coordinate format representation")
    vector_key: Optional[str] = Field(None, description="Pointer to vector database embedding UUID")
    vector_backend: Optional[str] = Field(None, description="Active vector backend database (e.g., qdrant, faiss)")
    vector_collection: Optional[str] = Field(None, description="Target vector database collection name")
    vector_dim: Optional[int] = Field(None, description="Embedding vector dimensionality")
    vector_model_tag: Optional[str] = Field(None, description="Model tag used to generate the vector embedding")
    source_artifact_id: Optional[str] = Field(None, description="Downstream artifact link (e.g., scene_id, segment_id)")
    raw_ref: Optional[str] = Field(None, description="Reference file path for full un-flattened raw output")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Modality-specific flat attributes dict")
    payload_hash: str = Field("", description="SHA-256 hash of serialized payload to detect silent mutation")
    promotion_status: str = Field("staged", description="Task execution status (staged, validated, promoted, rejected, superseded)")

    @field_validator("modality")
    @classmethod
    def validate_modality(cls, v: str) -> str:
        allowed = {"audio", "video", "text", "multimodal"}
        if v not in allowed:
            raise ValueError(f"modality must be one of {allowed}")
        return v

    @field_validator("promotion_status")
    @classmethod
    def validate_promotion(cls, v: str) -> str:
        allowed = {"staged", "validated", "promoted", "rejected", "superseded"}
        if v not in allowed:
            raise ValueError(f"promotion_status must be one of {allowed}")
        return v

    @field_validator("spatial_region")
    @classmethod
    def validate_spatial_region(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is None:
            return v
        if len(v) != 4:
            raise ValueError("spatial_region must be a list of exactly 4 floats [ymin, xmin, ymax, xmax]")
        for val in v:
            if not (0.0 <= val <= 1.0):
                raise ValueError("spatial_region values must be normalized between 0.0 and 1.0")
        # ymin <= ymax, xmin <= xmax
        if v[0] > v[2]:
            raise ValueError("ymin (index 0) must be less than or equal to ymax (index 2)")
        if v[1] > v[3]:
            raise ValueError("xmin (index 1) must be less than or equal to xmax (index 3)")
        return v

    @field_validator("t_start", "t_end")
    @classmethod
    def validate_timestamps(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError("timestamps must be non-negative double-precision floats")
        return round(v, 3)

    @field_validator("worker_name", "model_tag", "video_hash", "epoch_id", "run_id")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("fields must be non-empty strings")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v

    @field_validator("payload")
    @classmethod
    def validate_payload_flatness(cls, v: Dict[str, Any], info: ValidationInfo) -> Dict[str, Any]:
        if "embedding_chunks" in v:
            from steps.common.embedding_references import expand_embedding_references
            expand_embedding_references({**info.data, "payload": v})
        allowed_types = (str, int, float, bool, type(None))
        for key, value in v.items():
            if key == "embedding_chunks":
                continue  # The complete document-only group was validated above.
            if not isinstance(value, allowed_types):
                raise ValueError(f"payload value for key '{key}' must be flat (str, int, float, bool, None); got type {type(value)}")
        return v

    @model_validator(mode="after")
    def validate_range_and_hash(self) -> 'UCFRecord':
        if self.t_start > self.t_end:
            raise ValueError("t_start must be less than or equal to t_end")
        
        # Calculate payload_hash dynamically if not provided or empty
        if not self.payload_hash:
            canonical_str = json.dumps(self.payload, sort_keys=True)
            self.payload_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
            
        return self


class UCFLedgerClient:
    def __init__(self, db_path: str, timeout: float = 30.0):
        self.db_path = db_path
        self.timeout = timeout
        
        # Open connection and enable WAL mode immediately
        self.conn = sqlite3.connect(self.db_path, timeout=self.timeout)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.commit()

    def init_schema(self):
        """Initializes the media_sources and context_frames tables."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS media_sources (
                video_hash TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                duration REAL NOT NULL,
                fps REAL NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS context_frames (
                frame_id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_hash TEXT NOT NULL,
                ucf_schema_version TEXT NOT NULL,
                epoch_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                t_start REAL NOT NULL,
                t_end REAL NOT NULL,
                modality TEXT NOT NULL,
                worker_name TEXT NOT NULL,
                model_tag TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                spatial_region TEXT,
                spatial_space TEXT NOT NULL DEFAULT 'normalized_yxyx_top_left',
                vector_key TEXT,
                vector_backend TEXT,
                vector_collection TEXT,
                vector_dim INTEGER,
                vector_model_tag TEXT,
                source_artifact_id TEXT,
                raw_ref TEXT,
                payload TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                promotion_status TEXT NOT NULL DEFAULT 'staged',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                occurrence_id TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (video_hash) REFERENCES media_sources(video_hash),
                UNIQUE(video_hash, epoch_id, modality, worker_name, t_start, t_end, occurrence_id)
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_cf_temporal ON context_frames(video_hash, t_start, t_end);",
            "CREATE INDEX IF NOT EXISTS idx_cf_worker ON context_frames(video_hash, modality, worker_name);",
            """
            CREATE TABLE IF NOT EXISTS ucf_status_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frame_ids TEXT,
                video_hash TEXT,
                epoch_id TEXT,
                old_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                reason TEXT,
                scope TEXT,
                evidence TEXT,
                transitioned_at TEXT NOT NULL
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_ust_scope ON ucf_status_transitions(video_hash, epoch_id);"
        ]

        for q in queries:
            self.execute_with_retry(q)
        self._migrate_occurrences()

    def _migrate_occurrences(self):
        """Atomically extend the old unique key, retaining IDs, audit links and a backup.

        Uses SQLite's create/copy/drop/rename migration, never writable_schema.
        Unknown constraints or dependent views fail visibly and roll back.
        """
        if 'occurrence_id' in {r[1] for r in self.conn.execute('PRAGMA table_info(context_frames)')}:
            return
        foreign_keys = self.conn.execute('PRAGMA foreign_keys').fetchone()[0]
        self.conn.execute('PRAGMA foreign_keys=OFF')
        try:
            self.conn.execute('BEGIN IMMEDIATE')
            if 'occurrence_id' in {r[1] for r in self.conn.execute('PRAGMA table_info(context_frames)')}:
                self.conn.commit()
                return
            sql = self.conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='context_frames'").fetchone()[0]
            pattern = r'UNIQUE\s*\(\s*video_hash\s*,\s*epoch_id\s*,\s*modality\s*,\s*worker_name\s*,\s*t_start\s*,\s*t_end\s*\)'
            sql, count = re.subn(pattern, 'UNIQUE(video_hash, epoch_id, modality, worker_name, t_start, t_end, occurrence_id)', sql, flags=re.I)
            if count != 1:
                raise ValueError('Unrecognized legacy context_frames uniqueness constraint')
            sql, count = re.subn(r'^CREATE TABLE\s+(?:"context_frames"|context_frames)\s*\(',
                'CREATE TABLE context_frames_occurrences (', sql, count=1, flags=re.I)
            if count != 1:
                raise ValueError('Unrecognized legacy context_frames table definition')
            sql, count = re.subn(r'FOREIGN\s+KEY\s*\(\s*video_hash\s*\)',
                "occurrence_id TEXT NOT NULL DEFAULT '', FOREIGN KEY (video_hash)", sql, count=1, flags=re.I)
            if count != 1:
                raise ValueError('Unrecognized legacy context_frames source constraint')
            # A second read connection sees the committed WAL snapshot while this
            # writer lock prevents concurrent changes until migration commits.
            backup = Path(self.db_path).with_name(Path(self.db_path).name+'.pre-occurrence-v1.'+uuid.uuid4().hex+'.sqlite')
            with backup.open('xb'):
                pass
            source = sqlite3.connect(f'{Path(self.db_path).resolve().as_uri()}?mode=ro', uri=True)
            destination = sqlite3.connect(str(backup))
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
            objects = self.conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name='context_frames' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()
            sequence = self.conn.execute("SELECT seq FROM sqlite_sequence WHERE name='context_frames'").fetchone()
            columns = [r[1] for r in self.conn.execute('PRAGMA table_info(context_frames)')]
            quoted = ','.join('"'+name.replace('"', '""')+'"' for name in columns)
            self.conn.execute(sql)
            self.conn.execute(f'INSERT INTO context_frames_occurrences ({quoted}) SELECT {quoted} FROM context_frames')
            rows = self.conn.execute("SELECT frame_id,video_hash,source_artifact_id,worker_name,payload FROM context_frames WHERE model_tag='recording_audio_v1' AND worker_name IN ('audio_transcribe','speaker_merge')").fetchall()
            for frame, video, scene, worker, payload in rows:
                occurrence = audio_occurrence_id(video, scene, worker, json.loads(payload))
                self.conn.execute('UPDATE context_frames_occurrences SET occurrence_id=? WHERE frame_id=?', (occurrence, frame))
            self.conn.execute('DROP TABLE context_frames')
            self.conn.execute('ALTER TABLE context_frames_occurrences RENAME TO context_frames')
            for (statement,) in objects:
                self.conn.execute(statement)
            if sequence:
                self.conn.execute("UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name='context_frames'", sequence)
            if foreign_keys and self.conn.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Foreign key check failed during occurrence migration')
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self.conn.execute(f'PRAGMA foreign_keys={foreign_keys}')

    def execute_with_retry(self, query: str, params: tuple = (), max_retries: int = 5) -> sqlite3.Cursor:
        """Executes a query with retry logic on database locks."""
        for attempt in range(max_retries):
            try:
                # Use context manager for transactions
                with self.conn:
                    return self.conn.execute(query, params)
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    # Random backoff
                    time.sleep(0.05 + random.uniform(0, 0.05))
                else:
                    raise e
        raise sqlite3.OperationalError("Database is locked after maximum retries.")

    def register_media(
        self,
        video_hash: str,
        file_path: str,
        duration: float,
        fps: float,
        width: int,
        height: int
    ):
        """Registers a media source in the ledger database."""
        # Check for pre-existing records to prevent silent override with conflicting attributes
        cursor = self.execute_with_retry(
            "SELECT duration, fps, width, height FROM media_sources WHERE video_hash = ?",
            (video_hash,)
        )
        row = cursor.fetchone()
        if row:
            existing_dur, existing_fps, existing_w, existing_h = row
            if (abs(existing_dur - duration) > 0.050 or
                abs(existing_fps - fps) > 0.050 or
                existing_w != width or
                existing_h != height):
                raise ValueError(
                    f"Conflict in structural attributes for video_hash {video_hash}. "
                    f"Existing: duration={existing_dur}, fps={existing_fps}, width={existing_w}, height={existing_h}. "
                    f"New: duration={duration}, fps={fps}, width={width}, height={height}."
                )

        query = """
        INSERT INTO media_sources (video_hash, file_path, duration, fps, width, height)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_hash) DO UPDATE SET
            file_path=excluded.file_path,
            duration=excluded.duration,
            fps=excluded.fps,
            width=excluded.width,
            height=excluded.height;
        """
        self.execute_with_retry(query, (video_hash, file_path, duration, fps, width, height))

    def delete_frames(self, frame_ids: List[int]):
        """Deletes context frames by their IDs in a transaction-safe manner using retry logic."""
        if not frame_ids:
            return
        placeholders = ",".join("?" for _ in frame_ids)
        query = f"DELETE FROM context_frames WHERE frame_id IN ({placeholders})"
        self.execute_with_retry(query, tuple(frame_ids))

    def log_frame(
        self,
        video_hash: str,
        epoch_id: str,
        run_id: str,
        t_start: float,
        t_end: float,
        modality: str,
        worker_name: str,
        model_tag: str,
        confidence: float = 1.0,
        spatial_region: Optional[List[float]] = None,
        spatial_space: str = "normalized_yxyx_top_left",
        vector_key: Optional[str] = None,
        vector_backend: Optional[str] = None,
        vector_collection: Optional[str] = None,
        vector_dim: Optional[int] = None,
        vector_model_tag: Optional[str] = None,
        source_artifact_id: Optional[str] = None,
        raw_ref: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        promotion_status: str = "staged",
        occurrence_id: str = "",
    ) -> int:
        """Logs a Unified Context Frame event to the ledger, enforcing strict Pydantic validation."""
        # Instantiate and validate record
        record = UCFRecord(
            video_hash=video_hash,
            epoch_id=epoch_id,
            run_id=run_id,
            occurrence_id=occurrence_id,
            t_start=t_start,
            t_end=t_end,
            modality=modality,
            worker_name=worker_name,
            model_tag=model_tag,
            confidence=confidence,
            spatial_region=spatial_region,
            spatial_space=spatial_space,
            vector_key=vector_key,
            vector_backend=vector_backend,
            vector_collection=vector_collection,
            vector_dim=vector_dim,
            vector_model_tag=vector_model_tag,
            source_artifact_id=source_artifact_id,
            raw_ref=raw_ref,
            payload=payload or {},
            promotion_status=promotion_status
        )

        # Serialize fields for SQLite
        spatial_str = json.dumps(record.spatial_region) if record.spatial_region is not None else None
        payload_str = json.dumps(record.payload)
        
        query = """
        INSERT INTO context_frames (
            video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
            modality, worker_name, model_tag, confidence, spatial_region, spatial_space,
            vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
            source_artifact_id, raw_ref, payload, payload_hash, promotion_status, occurrence_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_hash, epoch_id, modality, worker_name, t_start, t_end, occurrence_id) DO UPDATE SET
            payload = excluded.payload,
            payload_hash = excluded.payload_hash,
            run_id = excluded.run_id,
            vector_key = excluded.vector_key,
            vector_backend = excluded.vector_backend,
            vector_collection = excluded.vector_collection,
            vector_dim = excluded.vector_dim,
            vector_model_tag = excluded.vector_model_tag,
            confidence = excluded.confidence,
            promotion_status = excluded.promotion_status,
            model_tag = excluded.model_tag,
            raw_ref = excluded.raw_ref,
            source_artifact_id = excluded.source_artifact_id
        """
        params = (
            record.video_hash, record.ucf_schema_version, record.epoch_id, record.run_id,
            record.t_start, record.t_end, record.modality, record.worker_name, record.model_tag,
            record.confidence, spatial_str, record.spatial_space, record.vector_key,
            record.vector_backend, record.vector_collection, record.vector_dim, record.vector_model_tag,
            record.source_artifact_id, record.raw_ref, payload_str, record.payload_hash,
            record.promotion_status, record.occurrence_id
        )
        # Serialize replay admission with retirement. A retried producer may not
        # reopen a retired scene, including newly emitted workers for its alias.
        for attempt in range(5):
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                conflict = self.conn.execute(
                    "SELECT frame_id FROM context_frames WHERE video_hash=? AND epoch_id=? AND modality=? AND worker_name=? AND t_start=? AND t_end=? AND occurrence_id=?",
                    (video_hash, epoch_id, modality, worker_name, record.t_start, record.t_end, record.occurrence_id),
                ).fetchone()
                assert_scene_write_allowed(
                    self.conn, video_hash=video_hash, epoch_id=epoch_id,
                    source_artifact_id=source_artifact_id, payload=payload,
                    conflict_frame_id=conflict[0] if conflict else None,
                )
                cursor = self.conn.execute(query, params)
                self.conn.commit()
                return conflict[0] if conflict else cursor.lastrowid
            except sqlite3.OperationalError as exc:
                self.conn.rollback()
                if "locked" in str(exc).lower() and attempt < 4:
                    time.sleep(0.05 + random.uniform(0, 0.05))
                    continue
                raise
            except Exception:
                self.conn.rollback()
                raise

    def query_overlap(
        self,
        video_hash: str,
        t_start: float,
        t_end: float,
        modality: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Queries the ledger for context frames overlapping the given range."""
        if modality:
            query = """
            SELECT frame_id, t_start, t_end, modality, worker_name, model_tag,
                   confidence, spatial_region, spatial_space, vector_key, vector_backend,
                   vector_collection, vector_dim, vector_model_tag, source_artifact_id,
                   raw_ref, payload, payload_hash, promotion_status, created_at,
                   ucf_schema_version, epoch_id, run_id
            FROM context_frames
            WHERE video_hash = ? AND t_start < ? AND t_end > ? AND modality = ?
            ORDER BY t_start ASC
            """
            params = (video_hash, t_end, t_start, modality)
        else:
            query = """
            SELECT frame_id, t_start, t_end, modality, worker_name, model_tag,
                   confidence, spatial_region, spatial_space, vector_key, vector_backend,
                   vector_collection, vector_dim, vector_model_tag, source_artifact_id,
                   raw_ref, payload, payload_hash, promotion_status, created_at,
                   ucf_schema_version, epoch_id, run_id
            FROM context_frames
            WHERE video_hash = ? AND t_start < ? AND t_end > ?
            ORDER BY t_start ASC
            """
            params = (video_hash, t_end, t_start)
            
        cursor = self.execute_with_retry(query, params)
        results = []
        for row in cursor.fetchall():
            results.append({
                "frame_id": row[0],
                "t_start": row[1],
                "t_end": row[2],
                "modality": row[3],
                "worker_name": row[4],
                "model_tag": row[5],
                "confidence": row[6],
                "spatial_region": json.loads(row[7]) if row[7] is not None else None,
                "spatial_space": row[8],
                "vector_key": row[9],
                "vector_backend": row[10],
                "vector_collection": row[11],
                "vector_dim": row[12],
                "vector_model_tag": row[13],
                "source_artifact_id": row[14],
                "raw_ref": row[15],
                "payload": json.loads(row[16]),
                "payload_hash": row[17],
                "promotion_status": row[18],
                "created_at": row[19],
                "ucf_schema_version": row[20],
                "epoch_id": row[21],
                "run_id": row[22]
            })
        return results

    def log_status_transition(
        self,
        old_status: str,
        new_status: str,
        tool_name: str,
        video_hash: Optional[str] = None,
        epoch_id: Optional[str] = None,
        reason: Optional[str] = None,
        scope: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
        frame_ids: Optional[Sequence[int]] = None,
    ) -> None:
        """Records a lifecycle status transition in the ucf_status_transitions audit table.

        This standalone entry point commits one audit row. Lifecycle status
        mutations use ``_transition_frames`` so the mutation and its audit
        evidence share a transaction.

        Args:
            old_status: The promotion_status before the transition.
            new_status: The promotion_status after the transition.
            tool_name: The MiniAgentClient tool name that triggered the transition.
            video_hash: Optional scope (video). Recorded as-is.
            epoch_id: Optional scope (epoch). Recorded as-is.
            reason: Human-readable justification (required for reject_ucf_frames).
            scope: Optional free-form scope string (e.g. "video_hash=vh_001,epoch_id=ep_001").
            evidence: Optional dict of supporting evidence (e.g. report path, commit hash).
            frame_ids: Optional list of affected frame IDs. Stored as JSON array string.
        """
        for attempt in range(5):
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                self.insert_status_transition(
                    self.conn,
                    old_status=old_status,
                    new_status=new_status,
                    tool_name=tool_name,
                    video_hash=video_hash,
                    epoch_id=epoch_id,
                    reason=reason,
                    scope=scope,
                    evidence=evidence,
                    frame_ids=frame_ids,
                )
                self.conn.commit()
                return
            except sqlite3.OperationalError as exc:
                self.conn.rollback()
                if "locked" in str(exc).lower() and attempt < 4:
                    time.sleep(0.05 + random.uniform(0, 0.05))
                    continue
                raise
            except Exception:
                self.conn.rollback()
                raise

    @staticmethod
    def insert_status_transition(
        conn: sqlite3.Connection,
        *,
        old_status: str,
        new_status: str,
        tool_name: str,
        video_hash: Optional[str] = None,
        epoch_id: Optional[str] = None,
        reason: Optional[str] = None,
        scope: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
        frame_ids: Optional[Sequence[int]] = None,
    ) -> None:
        """Insert transition evidence without committing the caller's transaction."""
        frame_ids_json = json.dumps(list(frame_ids)) if frame_ids is not None else None
        evidence_json = json.dumps(evidence) if evidence is not None else None
        transitioned_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO ucf_status_transitions
                (frame_ids, video_hash, epoch_id, old_status, new_status,
                 tool_name, reason, scope, evidence, transitioned_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                frame_ids_json,
                video_hash,
                epoch_id,
                old_status,
                new_status,
                tool_name,
                reason,
                scope,
                evidence_json,
                transitioned_at,
            ),
        )

    def _transition_frames(
        self,
        *,
        old_statuses: Sequence[str],
        new_status: str,
        tool_name: str,
        video_hash: Optional[str] = None,
        epoch_id: Optional[str] = None,
        reason: Optional[str] = None,
        log_audit: bool = True,
    ) -> int:
        """Atomically update statuses and record exact pre-transition evidence."""
        if not old_statuses:
            raise ValueError("old_statuses must not be empty")

        placeholders = ",".join("?" for _ in old_statuses)
        where = f"promotion_status IN ({placeholders})"
        where_params: List[Any] = list(old_statuses)
        scope_parts = []
        if video_hash:
            where += " AND video_hash = ?"
            where_params.append(video_hash)
            scope_parts.append(f"video_hash={video_hash}")
        if epoch_id:
            where += " AND epoch_id = ?"
            where_params.append(epoch_id)
            scope_parts.append(f"epoch_id={epoch_id}")
        scope = ",".join(scope_parts) if scope_parts else None

        for attempt in range(5):
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                rows = self.conn.execute(
                    f"SELECT frame_id, promotion_status FROM context_frames WHERE {where} "
                    "ORDER BY frame_id",
                    tuple(where_params),
                ).fetchall()
                if not rows:
                    self.conn.commit()
                    return 0

                cursor = self.conn.execute(
                    f"UPDATE context_frames SET promotion_status = ? WHERE {where}",
                    (new_status, *where_params),
                )
                if cursor.rowcount != len(rows):
                    raise RuntimeError(
                        "lifecycle transition row count changed inside transaction"
                    )

                if log_audit:
                    frame_ids_by_status: Dict[str, List[int]] = {}
                    for frame_id, old_status in rows:
                        frame_ids_by_status.setdefault(str(old_status), []).append(
                            int(frame_id)
                        )
                    for old_status, exact_frame_ids in frame_ids_by_status.items():
                        self.insert_status_transition(
                            self.conn,
                            old_status=old_status,
                            new_status=new_status,
                            tool_name=tool_name,
                            video_hash=video_hash,
                            epoch_id=epoch_id,
                            reason=reason,
                            scope=scope,
                            evidence={"affected_count": len(exact_frame_ids)},
                            frame_ids=exact_frame_ids,
                        )

                self.conn.commit()
                return cursor.rowcount
            except sqlite3.OperationalError as exc:
                self.conn.rollback()
                if "locked" in str(exc).lower() and attempt < 4:
                    time.sleep(0.05 + random.uniform(0, 0.05))
                    continue
                raise
            except Exception:
                self.conn.rollback()
                raise

    def mark_frames_validated(
        self,
        video_hash: Optional[str] = None,
        epoch_id: Optional[str] = None,
        log_audit: bool = True,
    ) -> int:
        """Transitions context frames from 'staged' to 'validated'.

        Only frames currently in 'staged' status are updated. Frames already
        in 'validated', 'promoted', 'rejected', or 'superseded' are untouched.
        The operation is idempotent: calling it twice has no additional effect.

        Args:
            video_hash: Optional scope limiter.
            epoch_id: Optional scope limiter.
            log_audit: If True (default), writes a ucf_status_transitions entry.

        Returns:
            The number of rows updated (0 if already validated or no match).
        """
        return self._transition_frames(
            old_statuses=("staged",),
            new_status="validated",
            tool_name="validate_ucf_frames",
            video_hash=video_hash,
            epoch_id=epoch_id,
            log_audit=log_audit,
        )

    def mark_frames_rejected(
        self,
        reason: str,
        video_hash: Optional[str] = None,
        epoch_id: Optional[str] = None,
        log_audit: bool = True,
    ) -> int:
        """Transitions context frames from 'staged' or 'validated' to 'rejected'.

        'promoted' and 'superseded' frames cannot be rejected — they are already
        terminal or canonical. The transition is idempotent for frames already
        in 'rejected' status (rowcount returns 0 for those).

        Requires a non-empty reason string. This is a terminal state: rejected
        frames cannot be promoted.

        Args:
            reason: Human-readable justification for the rejection (required).
            video_hash: Optional scope limiter.
            epoch_id: Optional scope limiter.
            log_audit: If True (default), writes a ucf_status_transitions entry.

        Returns:
            The number of rows transitioned to 'rejected'.

        Raises:
            ValueError: If reason is empty.
        """
        if not reason or not reason.strip():
            raise ValueError("reason is required and must be a non-empty string for mark_frames_rejected")

        return self._transition_frames(
            old_statuses=("staged", "validated"),
            new_status="rejected",
            tool_name="reject_ucf_frames",
            video_hash=video_hash,
            epoch_id=epoch_id,
            reason=reason,
            log_audit=log_audit,
        )

    def mark_frames_superseded(
        self,
        video_hash: Optional[str] = None,
        epoch_id: Optional[str] = None,
        log_audit: bool = True,
    ) -> int:
        """Transitions context frames from 'promoted' or 'validated' to 'superseded'.

        Used when a previously promoted epoch is replaced by a new ingestion run.
        'staged' and 'rejected' frames cannot be superseded — staged frames must
        be explicitly validated or rejected first, and rejected frames are already
        terminal. The transition is idempotent for already-superseded frames.

        Superseded frames cannot be promoted.

        Args:
            video_hash: Optional scope limiter.
            epoch_id: Optional scope limiter.
            log_audit: If True (default), writes a ucf_status_transitions entry.

        Returns:
            The number of rows transitioned to 'superseded'.
        """
        return self._transition_frames(
            old_statuses=("promoted", "validated"),
            new_status="superseded",
            tool_name="supersede_ucf_frames",
            video_hash=video_hash,
            epoch_id=epoch_id,
            log_audit=log_audit,
        )

    def close(self):
        """Closes the connection."""
        self.conn.close()
