#!/usr/bin/env python3
"""
Integration test for UCF ingestion.
Verifies that media sources and context frames are properly logged
to the UCF database, and range overlap queries function correctly.
"""

import hashlib
import sqlite3
import sys
from pathlib import Path
import pytest

from steps.common.config_loader import load_configs
from tests.runtime_profile import (
    require_live_profile,
    require_runtime_evidence,
    selected_runtime_epoch,
)

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _file_evidence(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


def _ledger_evidence(db_path: Path) -> dict:
    return {
        candidate.name: _file_evidence(candidate)
        for candidate in (
            db_path,
            Path(f"{db_path}-wal"),
            Path(f"{db_path}-shm"),
        )
    }

@pytest.mark.live_runtime
def test_ucf_ingestion_ledger(goodq_test_profile):
    require_live_profile(goodq_test_profile, "live UCF ledger witness")
    cfg = load_configs({})
    db_dir = cfg.get('paths', {}).get('db_dir')
    require_runtime_evidence(
        goodq_test_profile,
        bool(db_dir),
        "paths.db_dir is not configured",
    )
    ucf_db_path = Path(db_dir) / 'ucf' / 'ucf_ledger.db'
    require_runtime_evidence(
        goodq_test_profile,
        ucf_db_path.exists(),
        "resolved UCF ledger database does not exist",
    )
    epoch_id = selected_runtime_epoch(goodq_test_profile)
    evidence_before = _ledger_evidence(ucf_db_path)
    wal_evidence = evidence_before.get(f"{ucf_db_path.name}-wal", {})
    require_runtime_evidence(
        goodq_test_profile,
        not wal_evidence.get("exists") or wal_evidence.get("size") == 0,
        "UCF ledger has a non-empty WAL and is not safe for an immutable witness",
    )

    connection = sqlite3.connect(
        f"{ucf_db_path.resolve().as_uri()}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        connection.execute("PRAGMA query_only = ON")
        # Check media_sources
        cursor = connection.execute(
            "SELECT video_hash, file_path, duration, fps, width, height FROM media_sources"
        )
        media_sources = cursor.fetchall()
        require_runtime_evidence(
            goodq_test_profile,
            bool(media_sources),
            "UCF ledger has no registered media sources",
        )

        target_video_hash = None
        target_duration = None
        context_frames = []
        for row in media_sources:
            video_hash, file_path, duration, fps, width, height = row
            cursor_cf = connection.execute(
                """
                SELECT video_hash, ucf_schema_version, t_start, t_end, modality, worker_name, promotion_status
                FROM context_frames
                WHERE video_hash = ? AND epoch_id = ? AND ucf_schema_version = 'ucf.v0.1'
                  AND modality = 'video' AND worker_name = 'video_scene_detect'
                  AND promotion_status IN ('staged', 'validated', 'promoted')
                ORDER BY t_start
                """,
                (video_hash, epoch_id),
            )
            candidate_frames = cursor_cf.fetchall()
            if candidate_frames:
                target_video_hash = video_hash
                target_duration = duration
                assert duration > 0, f"Duration must be greater than 0, got {duration}"
                assert fps > 0, f"FPS must be greater than 0, got {fps}"
                assert width > 0, f"Width must be greater than 0, got {width}"
                assert height > 0, f"Height must be greater than 0, got {height}"
                context_frames = candidate_frames
                break

        require_runtime_evidence(
            goodq_test_profile,
            target_video_hash is not None,
            "no registered media source has a lifecycle-visible video_scene_detect frame",
        )

        found_staged_video_frame = False
        test_start = None
        test_end = None
        for cf in context_frames:
            v_hash, version, t_start, t_end, modality, worker, status = cf
            if version == "ucf.v0.1" and modality == "video" and worker == "video_scene_detect" and status in ("staged", "validated", "promoted"):
                found_staged_video_frame = True
                assert t_start >= 0.0, f"Start timestamp must be non-negative, got {t_start}"
                assert t_end >= t_start, f"End timestamp must be after start timestamp, got t_start={t_start}, t_end={t_end}"
                test_start = t_start
                test_end = t_end
                break
                
        assert found_staged_video_frame, "No context frame found matching the required criteria (ucf.v0.1, video, video_scene_detect, staged/validated/promoted)"
        
        # Reproduce the ledger overlap predicate directly so this witness never
        # constructs a write-capable UCFLedgerClient against operator state.
        query_start = test_start
        query_end = test_end

        overlap_results = connection.execute(
            """
            SELECT video_hash, ucf_schema_version, t_start, t_end, modality,
                   worker_name, promotion_status
            FROM context_frames
            WHERE video_hash = ? AND epoch_id = ?
              AND t_start <= ? AND t_end >= ? AND modality = ?
            ORDER BY t_start
            """,
            (target_video_hash, epoch_id, query_end, query_start, "video"),
        ).fetchall()
        assert len(overlap_results) >= 1, f"Overlap query failed to retrieve overlapping frames in [{query_start}, {query_end}]"

        # Verify the retrieved frame details
        retrieved_frame = overlap_results[0]
        assert retrieved_frame[1] == "ucf.v0.1"
        assert retrieved_frame[4] == "video"
        assert retrieved_frame[5] == "video_scene_detect"
        assert retrieved_frame[6] in ("staged", "validated", "promoted")
        assert retrieved_frame[2] == test_start
        assert retrieved_frame[3] == test_end

        no_overlap_start = float(target_duration) + 1.0
        no_overlap_end = float(target_duration) + 11.0
        no_overlap_results = connection.execute(
            """
            SELECT frame_id
            FROM context_frames
            WHERE video_hash = ? AND epoch_id = ?
              AND t_start <= ? AND t_end >= ? AND modality = ?
            """,
            (target_video_hash, epoch_id, no_overlap_end, no_overlap_start, "video"),
        ).fetchall()
        assert len(no_overlap_results) == 0, f"Overlap query returned results for non-overlapping range"

    finally:
        connection.close()
        assert _ledger_evidence(ucf_db_path) == evidence_before, (
            "read-only UCF witness changed the operator ledger or SQLite sidecars"
        )
