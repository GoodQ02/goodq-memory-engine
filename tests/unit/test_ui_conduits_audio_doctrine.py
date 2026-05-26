from __future__ import annotations

import sqlite3

from cli import ui_conduits_rollup


def _source_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE scenes(id TEXT PRIMARY KEY, video_hash TEXT)")
    conn.execute(
        """
        CREATE TABLE memory_commit_events(
          scene_id TEXT,
          modality TEXT,
          committed INTEGER,
          ts_utc TEXT
        )
        """
    )
    return conn


def test_audio_clap_ui_conduit_labels_commit_presence_as_unverified_provenance() -> None:
    conn = _source_db()
    conn.executescript(ui_conduits_rollup._SCHEMA_SQL)
    conn.execute("INSERT INTO scenes(id, video_hash) VALUES ('scene_001', 'video_001')")
    conn.execute(
        """
        INSERT INTO memory_commit_events(scene_id, modality, committed, ts_utc)
        VALUES ('scene_001', 'audio', 1, '2026-05-01T00:00:00Z')
        """
    )

    assert ui_conduits_rollup._update_scene_modality_coverage(conn) == 1

    row = conn.execute(
        """
        SELECT has_audio_clap, audio_clap_basis, audio_vector_provenance_state
        FROM scene_modality_coverage
        WHERE video_id = 'video_001' AND scene_id = 'scene_001'
        """
    ).fetchone()

    assert row == (
        1,
        "memory_commit_events_only_not_current_run_qdrant_proof",
        "provenance_unverified_audio_vector_exists",
    )


def test_audio_clap_ui_conduit_migrates_old_table_with_doctrine_columns() -> None:
    conn = _source_db()
    conn.execute(
        """
        CREATE TABLE scene_modality_coverage (
          video_id TEXT NOT NULL,
          scene_id TEXT NOT NULL,
          has_clip INTEGER NOT NULL,
          has_dino INTEGER NOT NULL,
          has_audio_clap INTEGER NOT NULL,
          has_text_frame INTEGER NOT NULL,
          has_text_transcript INTEGER NOT NULL,
          provenance_coverage_pct REAL,
          last_commit_ts_utc TEXT,
          PRIMARY KEY (video_id, scene_id)
        )
        """
    )
    conn.execute("INSERT INTO scenes(id, video_hash) VALUES ('scene_002', 'video_001')")

    assert ui_conduits_rollup._update_scene_modality_coverage(conn) == 1

    row = conn.execute(
        """
        SELECT has_audio_clap, audio_clap_basis, audio_vector_provenance_state
        FROM scene_modality_coverage
        WHERE video_id = 'video_001' AND scene_id = 'scene_002'
        """
    ).fetchone()

    assert row == (
        0,
        "memory_commit_events_only_not_current_run_qdrant_proof",
        "audio_vector_absent",
    )
