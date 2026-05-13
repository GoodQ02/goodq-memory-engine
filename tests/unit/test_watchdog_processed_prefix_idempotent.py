from __future__ import annotations

from pathlib import Path

import cli.watchdog as watchdog


def _watchdog_cfg(tmp_path: Path) -> dict:
    data_root = tmp_path / "data_root" / "GoodQ_Data"
    watch_dir = data_root / "import_inbox"
    processing_dir = data_root / "processing"
    processed_dir = data_root / "processed"
    failed_dir = data_root / "failed"
    log_dir = tmp_path / "logs"
    db_dir = data_root / "db"

    for path in (watch_dir, processing_dir, processed_dir, failed_dir, log_dir, db_dir):
        path.mkdir(parents=True, exist_ok=True)

    return {
        "paths": {
            "import_inbox": str(watch_dir),
            "processing": str(processing_dir),
            "processed": str(processed_dir),
            "failed": str(failed_dir),
            "data_root": str(data_root),
            "log_dir": str(log_dir),
            "watchdog_state_file": str(log_dir / "watchdog_state.json"),
            "db_dir": str(db_dir),
        }
    }


def test_mark_file_processed_is_idempotent_for_prefixed_names(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    cfg = _watchdog_cfg(tmp_path)
    processor = watchdog.WatchdogProcessor(cfg)

    watch_dir = Path(cfg["paths"]["import_inbox"])
    already_prefixed = watch_dir / "PROCESSED_clip.mp4"
    already_prefixed.write_bytes(b"payload")

    processor.mark_file_processed(already_prefixed)

    assert already_prefixed.exists()
    assert not (watch_dir / "PROCESSED_PROCESSED_clip.mp4").exists()


def test_scan_directory_ignores_prefixed_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(watchdog, "CONTROL_AGENT_AVAILABLE", False)
    cfg = _watchdog_cfg(tmp_path)
    processor = watchdog.WatchdogProcessor(cfg)

    watch_dir = Path(cfg["paths"]["import_inbox"])
    (watch_dir / "new_clip.mp4").write_bytes(b"new")
    (watch_dir / "PROCESSED_old_clip.mp4").write_bytes(b"old")
    (watch_dir / "FAILED_bad_clip.mp4").write_bytes(b"bad")

    found = processor.scan_directory()
    names = {p.name for p in found}

    assert "new_clip.mp4" in names
    assert "PROCESSED_old_clip.mp4" not in names
    assert "FAILED_bad_clip.mp4" not in names
