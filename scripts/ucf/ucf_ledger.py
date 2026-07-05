import sqlite3
import json
import time
import random
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Sequence
from pydantic import BaseModel, Field, field_validator, model_validator

class UCFRecord(BaseModel):
    video_hash: str = Field(..., description="Unique hash identifier of the video source")
    ucf_schema_version: str = Field("ucf.v0.1", description="UCF schema version for future-proof parsing")
    epoch_id: str = Field(..., description="Active epoch identity tracking")
    run_id: str = Field(..., description="Active ingestion run identity tracking")
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
    def validate_payload_flatness(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        allowed_types = (str, int, float, bool, type(None))
        for key, value in v.items():
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
                FOREIGN KEY (video_hash) REFERENCES media_sources(video_hash),
                UNIQUE(video_hash, epoch_id, modality, worker_name, t_start, t_end)
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
        promotion_status: str = "staged"
    ) -> int:
        """Logs a Unified Context Frame event to the ledger, enforcing strict Pydantic validation."""
        # Instantiate and validate record
        record = UCFRecord(
            video_hash=video_hash,
            epoch_id=epoch_id,
            run_id=run_id,
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
            source_artifact_id, raw_ref, payload, payload_hash, promotion_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_hash, epoch_id, modality, worker_name, t_start, t_end) DO UPDATE SET
            payload = excluded.payload,
            payload_hash = excluded.payload_hash,
            run_id = excluded.run_id,
            vector_key = excluded.vector_key,
            confidence = excluded.confidence,
            promotion_status = excluded.promotion_status,
            model_tag = excluded.model_tag,
            raw_ref = excluded.raw_ref,
            source_artifact_id = excluded.source_artifact_id
        """
        cursor = self.execute_with_retry(query, (
            record.video_hash, record.ucf_schema_version, record.epoch_id, record.run_id,
            record.t_start, record.t_end, record.modality, record.worker_name, record.model_tag,
            record.confidence, spatial_str, record.spatial_space, record.vector_key,
            record.vector_backend, record.vector_collection, record.vector_dim, record.vector_model_tag,
            record.source_artifact_id, record.raw_ref, payload_str, record.payload_hash,
            record.promotion_status
        ))
        return cursor.lastrowid

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

        Called by all HITL lifecycle tools after a status write completes.
        Does not raise on failure — transition logging must not block the
        primary write operation.

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
        try:
            frame_ids_json = json.dumps(frame_ids) if frame_ids else None
            evidence_json = json.dumps(evidence) if evidence else None
            transitioned_at = datetime.now(timezone.utc).isoformat()
            self.execute_with_retry(
                """
                INSERT INTO ucf_status_transitions
                    (frame_ids, video_hash, epoch_id, old_status, new_status,
                     tool_name, reason, scope, evidence, transitioned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (frame_ids_json, video_hash, epoch_id, old_status, new_status,
                 tool_name, reason, scope, evidence_json, transitioned_at),
            )
        except Exception:
            # Audit logging must not interrupt the primary write path
            pass

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
        query = "UPDATE context_frames SET promotion_status = 'validated' WHERE promotion_status = 'staged'"
        params: list = []
        if video_hash:
            query += " AND video_hash = ?"
            params.append(video_hash)
        if epoch_id:
            query += " AND epoch_id = ?"
            params.append(epoch_id)
        cursor = self.execute_with_retry(query, tuple(params))
        count = cursor.rowcount
        if log_audit and count > 0:
            scope_parts = []
            if video_hash:
                scope_parts.append(f"video_hash={video_hash}")
            if epoch_id:
                scope_parts.append(f"epoch_id={epoch_id}")
            self.log_status_transition(
                old_status="staged",
                new_status="validated",
                tool_name="validate_ucf_frames",
                video_hash=video_hash,
                epoch_id=epoch_id,
                scope=",".join(scope_parts) if scope_parts else None,
            )
        return count

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

        query = (
            "UPDATE context_frames SET promotion_status = 'rejected' "
            "WHERE promotion_status IN ('staged', 'validated')"
        )
        params: list = []
        if video_hash:
            query += " AND video_hash = ?"
            params.append(video_hash)
        if epoch_id:
            query += " AND epoch_id = ?"
            params.append(epoch_id)
        cursor = self.execute_with_retry(query, tuple(params))
        count = cursor.rowcount
        if log_audit and count > 0:
            scope_parts = []
            if video_hash:
                scope_parts.append(f"video_hash={video_hash}")
            if epoch_id:
                scope_parts.append(f"epoch_id={epoch_id}")
            self.log_status_transition(
                old_status="staged_or_validated",
                new_status="rejected",
                tool_name="reject_ucf_frames",
                video_hash=video_hash,
                epoch_id=epoch_id,
                reason=reason,
                scope=",".join(scope_parts) if scope_parts else None,
            )
        return count

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
        query = (
            "UPDATE context_frames SET promotion_status = 'superseded' "
            "WHERE promotion_status IN ('promoted', 'validated')"
        )
        params: list = []
        if video_hash:
            query += " AND video_hash = ?"
            params.append(video_hash)
        if epoch_id:
            query += " AND epoch_id = ?"
            params.append(epoch_id)
        cursor = self.execute_with_retry(query, tuple(params))
        count = cursor.rowcount
        if log_audit and count > 0:
            scope_parts = []
            if video_hash:
                scope_parts.append(f"video_hash={video_hash}")
            if epoch_id:
                scope_parts.append(f"epoch_id={epoch_id}")
            self.log_status_transition(
                old_status="promoted_or_validated",
                new_status="superseded",
                tool_name="supersede_ucf_frames",
                video_hash=video_hash,
                epoch_id=epoch_id,
                scope=",".join(scope_parts) if scope_parts else None,
            )
        return count

    def close(self):
        """Closes the connection."""
        self.conn.close()
