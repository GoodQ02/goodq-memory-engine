from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPO_ROOT / "scripts" / "ucf" / "ucf_ledger.py"


def _load_ledger_module():
    spec = importlib.util.spec_from_file_location("ucf_ledger_atomicity", LEDGER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _add_frame(client, *, video_hash: str, status: str, t_start: float):
    client.register_media(
        video_hash=video_hash,
        file_path=f"{video_hash}.mp4",
        duration=10.0,
        fps=30.0,
        width=1920,
        height=1080,
    )
    client.log_frame(
        video_hash=video_hash,
        epoch_id="epoch_atomic",
        run_id="run_atomic",
        t_start=t_start,
        t_end=t_start + 1.0,
        modality="video",
        worker_name="image_caption",
        model_tag="test-model",
        payload={"label": video_hash},
        promotion_status=status,
    )


def test_validation_rejection_and_supersession_record_exact_frame_evidence(tmp_path):
    mod = _load_ledger_module()
    db_path = tmp_path / "ucf_ledger.db"
    client = mod.UCFLedgerClient(str(db_path))
    client.init_schema()
    _add_frame(client, video_hash="video-validate", status="staged", t_start=0.0)
    _add_frame(client, video_hash="video-reject", status="staged", t_start=0.0)
    _add_frame(client, video_hash="video-reject", status="validated", t_start=2.0)
    _add_frame(client, video_hash="video-supersede", status="validated", t_start=0.0)
    _add_frame(client, video_hash="video-supersede", status="promoted", t_start=2.0)
    before_rows = client.conn.execute(
        "SELECT frame_id, video_hash, promotion_status FROM context_frames "
        "ORDER BY frame_id"
    ).fetchall()
    expected_frame_ids = {
        (video_hash, old_status): [
            frame_id
            for frame_id, row_video_hash, row_status in before_rows
            if row_video_hash == video_hash and row_status == old_status
        ]
        for video_hash, old_status in {
            ("video-validate", "staged"),
            ("video-reject", "staged"),
            ("video-reject", "validated"),
            ("video-supersede", "validated"),
            ("video-supersede", "promoted"),
        }
    }

    assert client.mark_frames_validated("video-validate", "epoch_atomic") == 1
    assert client.mark_frames_rejected(
        "operator rejection", "video-reject", "epoch_atomic"
    ) == 2
    assert client.mark_frames_superseded("video-supersede", "epoch_atomic") == 2
    transition_count = client.conn.execute(
        "SELECT COUNT(*) FROM ucf_status_transitions"
    ).fetchone()[0]
    assert transition_count == 5
    assert client.mark_frames_validated("video-validate", "epoch_atomic") == 0
    assert client.mark_frames_rejected(
        "operator rejection", "video-reject", "epoch_atomic"
    ) == 0
    assert client.mark_frames_superseded("video-supersede", "epoch_atomic") == 0
    assert client.conn.execute(
        "SELECT COUNT(*) FROM ucf_status_transitions"
    ).fetchone()[0] == transition_count
    client.close()

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT frame_ids, video_hash, epoch_id, old_status, new_status, "
        "tool_name, reason, scope, evidence FROM ucf_status_transitions ORDER BY id"
    ).fetchall()
    frame_statuses = dict(
        conn.execute("SELECT frame_id, promotion_status FROM context_frames").fetchall()
    )
    conn.close()

    assert len(rows) == 5
    expected = {
        ("video-validate", "staged", "validated", "validate_ucf_frames"),
        ("video-reject", "staged", "rejected", "reject_ucf_frames"),
        ("video-reject", "validated", "rejected", "reject_ucf_frames"),
        ("video-supersede", "validated", "superseded", "supersede_ucf_frames"),
        ("video-supersede", "promoted", "superseded", "supersede_ucf_frames"),
    }
    observed = {(row[1], row[3], row[4], row[5]) for row in rows}
    assert observed == expected
    all_recorded_frame_ids = []
    for (
        frame_ids_json,
        video_hash,
        epoch_id,
        old_status,
        new_status,
        tool_name,
        reason,
        scope,
        evidence_json,
    ) in rows:
        frame_ids = json.loads(frame_ids_json)
        assert frame_ids == expected_frame_ids[(video_hash, old_status)]
        all_recorded_frame_ids.extend(frame_ids)
        assert all(frame_statuses[frame_id] == new_status for frame_id in frame_ids)
        assert epoch_id == "epoch_atomic"
        assert scope == f"video_hash={video_hash},epoch_id=epoch_atomic"
        assert json.loads(evidence_json) == {"affected_count": len(frame_ids)}
        if tool_name == "reject_ucf_frames":
            assert reason == "operator rejection"
        else:
            assert reason is None
    assert sorted(all_recorded_frame_ids) == sorted(
        frame_id for frame_id, _, _ in before_rows
    )
    assert len(all_recorded_frame_ids) == len(set(all_recorded_frame_ids))


def test_audit_insert_failure_rolls_back_status_mutation(tmp_path):
    mod = _load_ledger_module()
    db_path = tmp_path / "ucf_ledger.db"
    client = mod.UCFLedgerClient(str(db_path))
    client.init_schema()
    _add_frame(client, video_hash="video-rollback", status="staged", t_start=0.0)
    client.conn.execute(
        "CREATE TRIGGER force_transition_failure "
        "BEFORE INSERT ON ucf_status_transitions "
        "BEGIN SELECT RAISE(ABORT, 'forced transition failure'); END"
    )
    client.conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="forced transition failure"):
        client.mark_frames_validated("video-rollback", "epoch_atomic")

    status = client.conn.execute(
        "SELECT promotion_status FROM context_frames WHERE video_hash = 'video-rollback'"
    ).fetchone()[0]
    transition_count = client.conn.execute(
        "SELECT COUNT(*) FROM ucf_status_transitions"
    ).fetchone()[0]
    client.close()
    assert status == "staged"
    assert transition_count == 0
