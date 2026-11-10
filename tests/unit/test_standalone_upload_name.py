"""Preserve upload display names without changing staged-file authority."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from tests.unit.test_standalone_lifecycle_producer import standalone_runtime
from tests.unit.test_watchdog_safety import standalone_audio_dispatch


def staged_document(tmp_path, cfg):
    request_id = "ingest_20261015T173543Z_e59bfc65"
    name = f"{request_id}__3fa19d81f9084182ae7bd753247b5a99.md"
    source = Path(cfg["paths"]["import_inbox"]) / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("Family picnic notes for Saturday.", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    requests = tmp_path / "ingest_requests"
    requests.mkdir()
    cfg["paths"]["ingest_requests"] = str(requests)
    record = {
        "request_id": request_id, "status": "staged", "original_name": "Family picnic.md",
        "staged_name": name, "staged_path": str(source), "file_sha256": digest,
        "authorization_confirmed_at": "2026-10-15T17:35:52+00:00",
    }
    record_path = requests / f"{request_id}.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    return source, digest, record, record_path


def test_uploaded_name_survives_watchdog_persistence_and_library_reader(
    standalone_runtime, tmp_path, monkeypatch,
):
    from api.routes import system
    from api.utils import loaders

    processor, _calls, cfg, _bridge = standalone_runtime
    source, digest, _record, _record_path = staged_document(tmp_path, cfg)
    staged_name = source.name
    content = source.read_bytes()
    assert processor.process_file(source, digest) is True
    directory = processor.processing_dir / digest
    raw = json.loads((directory / "raw_result.json").read_text(encoding="utf-8"))
    assert raw["original_filename"] == raw["filename"] == "Family picnic.md"
    retained = Path(raw["source_path"])
    assert retained == directory / f"{digest}.md"
    assert retained.read_bytes() == content
    assert (processor.processed_dir / f"PROCESSED_{staged_name}").read_bytes() == content
    assert processor.registry.processed[digest]["original_name"] == staged_name
    for artifact in ("temporal_index.json", "video/scene_manifest.json"):
        record = json.loads((directory / artifact).read_text(encoding="utf-8"))
        assert record["original_filename"] == "Family picnic.md"
        assert record["source_path"] == str(retained)

    for key in ("_DEFAULT_PROCESSING_ROOT", "_DEFAULT_PROCESSED_ROOT", "_DEFAULT_UCF_SCOPE"):
        monkeypatch.setattr(loaders, key, None)
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", ())
    loaders.configure_from_cfg(cfg)
    monkeypatch.setattr(system, "_data_loader", None)
    app = FastAPI()
    app.include_router(system.router)
    with TestClient(app) as client:
        assert client.get("/api/system/videos").json() == []
        # Simulate only the visibility gate; this test does not qualify promotion.
        ledger = Path(cfg["paths"]["db_dir"]) / "ucf/ucf_ledger.db"
        with closing(sqlite3.connect(ledger)) as connection, connection:
            connection.execute(
                "UPDATE context_frames SET promotion_status='promoted' WHERE video_hash=?", (digest,),
            )
        response = client.get("/api/system/videos")
        assert response.status_code == 200
        assert [(row["video_id"], row["title"]) for row in response.json()] == [(digest, "Family picnic")]


@pytest.mark.parametrize("status", ["staging", "staged", "processing", "completed"])
def test_prepare_source_preserves_exact_authorized_upload_name(tmp_path, status):
    from cli.standalone_persistence import prepare_source

    cfg = {"paths": {"import_inbox": str(tmp_path / "inbox"), "processing": str(tmp_path / "processing")}}
    source, digest, record, record_path = staged_document(tmp_path, cfg)
    record["status"] = status
    record_path.write_text(json.dumps(record), encoding="utf-8")
    item = prepare_source(cfg, source, "document")
    assert item["original_filename"] == item["filename"] == "Family picnic.md"
    assert item["source_hash"] == digest
    assert source.name.startswith(record["request_id"] + "__")


@pytest.mark.parametrize("mismatch", [
    "missing", "malformed", "not_object", "request_id", "staged_name", "staged_path", "hash",
    "pending_confirmation", "canceled", "failed", "no_authorization", "posix_path", "windows_path",
    "empty_name", "control_character", "malformed_status",
])
def test_prepare_source_keeps_staged_name_when_request_evidence_does_not_match(tmp_path, mismatch):
    from cli.standalone_persistence import prepare_source

    cfg = {"paths": {"import_inbox": str(tmp_path / "inbox"), "processing": str(tmp_path / "processing")}}
    source, digest, record, record_path = staged_document(tmp_path, cfg)
    changes = {
        "request_id": ("request_id", "ingest_20261015T173543Z_00000000"),
        "staged_name": ("staged_name", "other.md"),
        "staged_path": ("staged_path", str(source.with_name("other.md"))),
        "hash": ("file_sha256", "0" * 64),
        "pending_confirmation": ("status", "pending_confirmation"),
        "canceled": ("status", "canceled"), "failed": ("status", "failed"),
        "no_authorization": ("authorization_confirmed_at", None),
        "posix_path": ("original_name", "../notes.md"),
        "windows_path": ("original_name", "C:\\private\\notes.md"),
        "empty_name": ("original_name", ""), "control_character": ("original_name", "notes\n.md"),
        "malformed_status": ("status", []),
    }
    if mismatch in changes:
        key, value = changes[mismatch]
        record[key] = value
    record_path.write_text(json.dumps(record), encoding="utf-8")
    if mismatch == "missing":
        record_path.unlink()
    elif mismatch == "malformed":
        record_path.write_text("{", encoding="utf-8")
    elif mismatch == "not_object":
        record_path.write_text("[]", encoding="utf-8")
    item = prepare_source(cfg, source, "document")
    assert item["original_filename"] == item["filename"] == source.name
    assert item["source_hash"] == digest


def test_prepare_source_keeps_manual_filename_without_request_storage(tmp_path):
    from cli.standalone_persistence import prepare_source

    source = tmp_path / "manual.md"
    source.write_text("Manual inbox notes", encoding="utf-8")
    cfg = {"paths": {"processing": str(tmp_path / "processing")}}
    item = prepare_source(cfg, source, "document")
    assert item["original_filename"] == item["filename"] == source.name
