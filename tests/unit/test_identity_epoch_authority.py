from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.routes import identity, runtime
from api.utils.identity_read_projection import (
    _context_frame,
    _representative_frame,
    epoch_authority_projection,
    project_face_cluster_images,
)


def _write_identity_artifacts(identity_root: Path, epoch_id: str) -> None:
    identity_root.mkdir(parents=True)
    (identity_root / "face_clusters.json").write_text(
        json.dumps({"epoch_id": epoch_id, "clusters": []}), encoding="utf-8"
    )
    (identity_root / "speaker_clusters.json").write_text(
        json.dumps({"epoch_id": epoch_id, "clusters": []}), encoding="utf-8"
    )
    (identity_root / "name_mentions.json").write_text(
        json.dumps({"epoch_id": epoch_id, "mentions": {}}), encoding="utf-8"
    )


def test_same_epoch_read_projection_is_ready(tmp_path: Path) -> None:
    epoch_root = tmp_path / "epochs" / "epoch_same"
    identity_root = tmp_path / "identity"
    _write_identity_artifacts(identity_root, "epoch_same")

    projection = epoch_authority_projection(
        {"epoch_id": "epoch_same", "paths": {"db_path": str(epoch_root / "memory.db")}},
        identity_root,
    )

    assert projection == {
        "configured_epoch_id": "epoch_same",
        "identity_epoch_id": "epoch_same",
        "identity_epoch_ids": {
            "face_clusters": "epoch_same",
            "speaker_clusters": "epoch_same",
            "name_mentions": "epoch_same",
        },
        "state": "ready",
        "ready": True,
        "message": "Identity artifacts match the configured epoch.",
    }


def test_epoch_mismatch_blocks_readiness(tmp_path: Path) -> None:
    identity_root = tmp_path / "identity"
    _write_identity_artifacts(identity_root, "epoch_other")

    projection = epoch_authority_projection(
        {"epoch_id": "epoch_active"},
        identity_root,
    )

    assert projection["ready"] is False
    assert projection["state"] == "epoch_mismatch"
    assert projection["configured_epoch_id"] == "epoch_active"
    assert projection["identity_epoch_id"] == "epoch_other"


def test_status_and_identity_get_share_same_epoch_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    identity_root = tmp_path / "identity"
    epoch_root = tmp_path / "epochs" / "epoch_same"
    _write_identity_artifacts(identity_root, "epoch_same")
    cfg = {
        "epoch_id": "epoch_same",
        "paths": {"db_path": str(epoch_root / "memory.db")},
        "identity_search": {"roster_path": str(identity_root / "family_roster.yaml")},
    }
    monkeypatch.setattr(identity, "_CFG", cfg)
    monkeypatch.setattr(runtime, "_CFG", cfg)
    monkeypatch.setattr(runtime, "_DB_PATH", epoch_root / "memory.db")

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        status_projection = client.get("/api/status").json()["epoch_authority"]
        identity_projection = client.get("/api/identity/face-clusters").json()[
            "epoch_authority"
        ]

    assert status_projection == identity_projection
    assert status_projection["ready"] is True


def test_face_projection_uses_workbench_representative_frame_url_shape(tmp_path: Path) -> None:
    epoch_root = tmp_path / "epochs" / "epoch_same"
    processing_root = epoch_root / "processing"
    frames_root = processing_root / "video_a" / "video" / "frames"
    frames_root.mkdir(parents=True)
    raw_ref = frames_root / "source_raw_faces.json"
    raw_ref.write_text(
        json.dumps(
            [
                {"bbox": [10, 20, 30, 40], "encoding": [0.1]},
                {"bbox": [50, 60, 70, 80], "encoding": [0.2]},
            ]
        ),
        encoding="utf-8",
    )
    representative = frames_root / "scene_0000_frame_00.jpg"
    representative.write_bytes(b"jpeg")
    (processing_root / "video_a" / "temporal_index.json").write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "start": 10.0,
                        "end": 20.0,
                        "representative_frame": str(representative),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    ucf_root = epoch_root / "ucf"
    ucf_root.mkdir()
    with sqlite3.connect(ucf_root / "ucf_ledger.db") as conn:
        conn.execute(
            "CREATE TABLE context_frames "
            "(frame_id INTEGER, raw_ref TEXT, t_start REAL)"
        )
        conn.execute(
            "INSERT INTO context_frames VALUES (?, ?, ?)",
            (101, str(raw_ref), 15.0),
        )

    data = {
        "epoch_id": "epoch_same",
        "clusters": [{"cluster_id": "face_1", "face_ids": ["101_0"]}],
    }
    context = _context_frame(epoch_root, 101)
    assert context is not None
    assert _representative_frame(epoch_root, *context) == ("video_a", representative)
    projected = project_face_cluster_images(
        data,
        {"epoch_id": "epoch_same", "paths": {"db_path": str(epoch_root / "memory.db")}},
        {
            "configured_epoch_id": "epoch_same",
            "identity_epoch_id": "epoch_same",
            "ready": True,
        },
    )

    assert projected["clusters"][0]["representative_frames"] == [
        {
            "frame_url": "/api/media/video/video_a/frame/scene_0000_frame_00.jpg",
            "target_face_id": "101_0",
            "target_face_index": 0,
            "source_face_count": 2,
            "bbox": [10, 20, 30, 40],
        }
    ]
