from __future__ import annotations

import os
import sqlite3
import pytest
from pathlib import Path
from steps.common.memory import ensure_id_map_table_schema

def test_ensure_id_map_table_schema_creation(tmp_path):
    db_path = str(tmp_path / "test_sidecar.db")
    table_name = "clip_id_map"

    # 1. Test when the table does not exist
    ensure_id_map_table_schema(db_path, table_name)

    # Verify that the table was created with correct columns and composite primary key
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        info = cursor.fetchall()
        cols = {row[1] for row in info}
        pk_cols = {row[1] for row in info if row[5] > 0}
        
        canonical_cols = {
            "video_hash", "faiss_id", "hash", "source_path", "created_at",
            "epoch_id", "scene_id", "scene_hash", "worker_name", "vector_model_tag",
            "modality", "ucf_frame_id"
        }
        assert cols == canonical_cols
        assert pk_cols == {"video_hash", "faiss_id"}
    finally:
        conn.close()


def test_ensure_id_map_table_schema_migration_no_data_loss(tmp_path):
    db_path = str(tmp_path / "test_sidecar_migrate.db")
    table_name = "clap_id_map"

    # Create a legacy table (with faiss_id as primary key, missing columns)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"""
            CREATE TABLE {table_name} (
                faiss_id INTEGER PRIMARY KEY,
                hash TEXT,
                source_path TEXT,
                created_at TEXT
            )
        """)
        # Insert a sample row
        conn.execute(f"""
            INSERT INTO {table_name} (faiss_id, hash, source_path, created_at)
            VALUES (42, 'legacy_hash_abc', 'legacy/source/path.wav', '2026-06-17T12:00:00')
        """)
        conn.commit()
    finally:
        conn.close()

    # Now, run ensure_id_map_table_schema to migrate the legacy table
    ensure_id_map_table_schema(db_path, table_name)

    # Verify the migration was successful and did not lose the data
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        info = cursor.fetchall()
        cols = {row[1] for row in info}
        pk_cols = {row[1] for row in info if row[5] > 0}

        canonical_cols = {
            "video_hash", "faiss_id", "hash", "source_path", "created_at",
            "epoch_id", "scene_id", "scene_hash", "worker_name", "vector_model_tag",
            "modality", "ucf_frame_id"
        }
        assert cols == canonical_cols
        assert pk_cols == {"video_hash", "faiss_id"}

        # Fetch the migrated row
        cursor = conn.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        assert len(rows) == 1
        
        # Row description to map indices to column names
        col_names = [description[0] for description in cursor.description]
        row_dict = dict(zip(col_names, rows[0]))
        
        assert row_dict["faiss_id"] == 42
        assert row_dict["hash"] == "legacy_hash_abc"
        assert row_dict["source_path"] == "legacy/source/path.wav"
        assert row_dict["created_at"] == "2026-06-17T12:00:00"
        assert row_dict["video_hash"] == ""  # Default value for missing PK column
        assert row_dict["epoch_id"] is None
        assert row_dict["scene_id"] is None
        assert row_dict["scene_hash"] is None
        assert row_dict["worker_name"] is None
        assert row_dict["vector_model_tag"] is None
        assert row_dict["modality"] is None
        assert row_dict["ucf_frame_id"] is None
    finally:
        conn.close()


def test_ensure_id_map_table_schema_idempotent(tmp_path):
    db_path = str(tmp_path / "test_sidecar_idempotent.db")
    table_name = "dino_id_map"

    # Run ensure schema first time (should create table)
    ensure_id_map_table_schema(db_path, table_name)
    
    # Insert a canonical row
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(f"""
            INSERT INTO {table_name} (
                video_hash, faiss_id, hash, source_path, created_at,
                epoch_id, scene_id, scene_hash, worker_name, vector_model_tag,
                modality, ucf_frame_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "test_video", 100, "hash_123", "src/path", "2026-06-17T12:00:00",
            "epoch_1", "scene_2", "hash_123", "worker_dino", "dinov2",
            "video", 456
        ))
        conn.commit()
    finally:
        conn.close()

    # Run ensure schema second time (should be idempotent, no schema alteration, no row change)
    ensure_id_map_table_schema(db_path, table_name)

    # Verify everything remains exactly as before
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        assert len(rows) == 1
        col_names = [description[0] for description in cursor.description]
        row_dict = dict(zip(col_names, rows[0]))

        assert row_dict["video_hash"] == "test_video"
        assert row_dict["faiss_id"] == 100
        assert row_dict["hash"] == "hash_123"
        assert row_dict["source_path"] == "src/path"
        assert row_dict["created_at"] == "2026-06-17T12:00:00"
        assert row_dict["epoch_id"] == "epoch_1"
        assert row_dict["scene_id"] == "scene_2"
        assert row_dict["scene_hash"] == "hash_123"
        assert row_dict["worker_name"] == "worker_dino"
        assert row_dict["vector_model_tag"] == "dinov2"
        assert row_dict["modality"] == "video"
        assert row_dict["ucf_frame_id"] == 456
    finally:
        conn.close()
