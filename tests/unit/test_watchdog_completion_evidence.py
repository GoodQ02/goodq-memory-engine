"""Only matching, complete persistence evidence may skip an inbox video."""
import json
import sqlite3
from pathlib import Path

import pytest

import cli.watchdog as watchdog
from tests.unit.test_watchdog_processed_prefix_idempotent import _watchdog_cfg


@pytest.mark.parametrize(
    "case,expected",
    [
        ("complete", True),
        ("wrong_content", False),
        ("partial_scene_set", False),
        ("missing_ledger", False),
        ("unreadable_ledger", False),
        ("missing_manifest", False),
        ("failed_vector_commit", False),
        ("inconsistent_scene_count", False),
    ],
)
@pytest.mark.parametrize("filename", ["clip.mp4", "video.mp4"])
def test_completion_requires_source_and_store_evidence(tmp_path, monkeypatch, case, expected, filename):
    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    cfg = _watchdog_cfg(tmp_path)
    processor = watchdog.WatchdogProcessor(cfg)
    source = Path(cfg["paths"]["import_inbox"]) / filename
    source.write_bytes(b"new content")
    file_hash = watchdog.FileState(source).compute_hash()
    identity = "stale-content" if case == "wrong_content" else file_hash
    processing = Path(cfg["paths"]["processing"]) / source.stem
    (processing / "video").mkdir(parents=True)
    index = {"video_hash": identity, "video_id": identity, "phase6_complete": True,
             "total_scenes": 2 if case == "inconsistent_scene_count" else 1,
             "segments": [{"scene_id": "scene-0"}]}
    (processing / "temporal_index.json").write_text(json.dumps(index), encoding="utf-8")
    if case != "missing_manifest":
        committed = case != "failed_vector_commit"
        manifest = {
            "video_id": identity, "phase6_complete": committed,
            "phase6_status": "complete" if committed else "failed",
            "phase6_vector_commit": {"enabled": True, "qdrant_ok": committed},
            "scenes": [{"scene_id": "scene-0", "clip_id": "clip-0", "dino_id": "dino-0",
                        "qdrant_ok": committed}],
        }
        (processing / "video" / "scene_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ledger = Path(cfg["paths"]["db_dir"]) / "ucf" / "ucf_ledger.db"
    if case != "missing_ledger":
        ledger.parent.mkdir()
        if case == "unreadable_ledger":
            ledger.write_bytes(b"invalid sqlite")
        else:
            with sqlite3.connect(ledger) as connection:
                connection.execute("CREATE TABLE context_frames (video_hash TEXT, worker_name TEXT)")
                count = 3 if case == "partial_scene_set" else 1
                connection.executemany("INSERT INTO context_frames VALUES (?, ?)",
                                       [(identity, "video_scene_detect")] * count)

    assert processor.check_video_completion_on_disk(source, file_hash) is expected
    assert source.read_bytes() == b"new content"
    assert not (Path(cfg["paths"]["db_dir"]) / "ucf_ledger.db").exists()
    if case == "missing_ledger":
        assert not ledger.exists()
