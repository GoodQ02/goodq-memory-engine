"""Document passage groups cross ledger admission and every vector check."""
from copy import deepcopy
import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from scripts.ucf.ucf_ledger import UCFRecord
from scripts.ucf.validate_ucf_epoch import normalize_qdrant_id, run_validation
from tests.unit.test_standalone_ucf_promotion import standalone, stage_document_chunks


def _stored_group(root, fid):
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        conn.row_factory = sqlite3.Row
        return dict(conn.execute("SELECT * FROM context_frames WHERE frame_id=?", (fid,)).fetchone())


def _rewrite_payload(root, fid, payload):
    encoded = json.dumps(payload)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        conn.execute("UPDATE context_frames SET payload=?,payload_hash=? WHERE frame_id=?", (encoded, digest, fid))


def test_document_group_admission_and_offline_validation_preserve_original_record(standalone):
    root, cfg, _client = standalone
    cfg["qdrant"] = {"collections": {"text": "goodq_text"}}
    _, _, chunks, fid = stage_document_chunks(root)
    before = _stored_group(root, fid)
    assert before["vector_key"] is None
    assert len(json.loads(before["payload"])["embedding_chunks"]) == len(chunks)
    assert run_validation(config=cfg) == 0
    assert _stored_group(root, fid) == before
    report = json.loads((root / "reports/ucf_validation_report.json").read_text())
    assert report["summary"]["total_context_frames_checked"] == 2
    assert report["payload_hash"]["status"] == "passed"


@pytest.mark.parametrize("bad", ["group_nested", "chunk_nested", "wrong_kind", "wrong_worker", "scalar_and_group", "duplicate_faiss"])
def test_document_group_admission_does_not_weaken_flatness_or_source_contract(standalone, bad):
    root, _cfg, _client = standalone
    _, _, _chunks, fid = stage_document_chunks(root)
    record = _stored_group(root, fid)
    record["payload"] = json.loads(record["payload"])
    if bad == "group_nested":
        record["payload"]["unrelated"] = {"nested": True}
    elif bad == "chunk_nested":
        record["payload"]["embedding_chunks"][1]["unrelated"] = [1, 2]
    elif bad == "wrong_kind":
        record["payload"]["source_kind"] = "image"
    elif bad == "wrong_worker":
        record["worker_name"] = "audio_transcribe"
    elif bad == "duplicate_faiss":
        from steps.common.memory import to_faiss_id
        for chunk, key in zip(record["payload"]["embedding_chunks"], ("0" * 64, str((1 << 63) - 1).zfill(64))):
            chunk.update(embedding_id=key, faiss_id=to_faiss_id(key))
        assert len({chunk["faiss_id"] for chunk in record["payload"]["embedding_chunks"]}) == 1
    else:
        record["vector_key"] = "d" * 64
    with pytest.raises(ValidationError):
        UCFRecord(**record)


@pytest.mark.parametrize("bad", ["missing_last", "wrong_text", "gap", "over_budget", "nested", "wrong_anchor"])
def test_offline_validator_rejects_tampered_group_even_with_updated_payload_hash(standalone, bad):
    root, cfg, _client = standalone
    cfg["qdrant"] = {"collections": {"text": "goodq_text"}}
    _, _, _chunks, fid = stage_document_chunks(root)
    payload = json.loads(_stored_group(root, fid)["payload"])
    if bad == "missing_last":
        payload["embedding_chunks"].pop()
        payload["chunk_count"] -= 1
    elif bad == "wrong_text":
        payload["embedding_chunks"][1]["text"] = "x" + payload["embedding_chunks"][1]["text"][1:]
    elif bad == "gap":
        payload["embedding_chunks"][1]["char_start"] = 31
    elif bad == "over_budget":
        payload["embedding_chunks"][1]["token_count"] = payload["chunk_token_limit"] + 1
    elif bad == "nested":
        payload["embedding_chunks"][1]["unrelated"] = {"bad": "nested"}
    else:
        text = "Substitute passage with the same content hash provenance?"
        payload["text_length"] = len(text)
        payload["text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        for chunk, (start, end) in zip(payload["embedding_chunks"], ((0, 30), (24, len(text)))):
            chunk.update(char_start=start, char_end=end, text=text[start:end])
    _rewrite_payload(root, fid, payload)
    assert run_validation(config=cfg) == 1
    report = json.loads((root / "reports/ucf_validation_report.json").read_text())
    errors = report["flatness"]["errors"] + report["manifest_reconciliation"]["errors"]
    assert any("Document embedding group" in error for error in errors)


@pytest.mark.parametrize("condition", ["matches", "missing_last", "wrong_video", "wrong_scene", "wrong_kind",
                                       "wrong_epoch", "wrong_frame", "missing_frame", "wrong_chunk", "missing_chunk", "wrong_chunk_type"])
def test_strict_document_group_checks_every_vector_and_original_ownership(standalone, monkeypatch, condition):
    root, cfg, _client = standalone
    cfg["qdrant"] = {"collections": {"text": "goodq_text"}}
    source_hash, scene_id, chunks, fid = stage_document_chunks(root)
    before = _stored_group(root, fid)
    points = {}
    for chunk in chunks:
        key = chunk["embedding_id"]
        span = {name: chunk[name] for name in ("chunk_index", "char_start", "char_end", "text", "token_count")}
        points[normalize_qdrant_id(key)] = {"id": normalize_qdrant_id(key), "payload": {
            "video_hash": source_hash, "scene_id": scene_id, "scene_hash": key,
            "modality": "text", "worker_name": "text_embed",
            "vector_model_tag": "sentence-transformers/all-MiniLM-L6-v2",
            "epoch_id": root.name, "ucf_frame_id": fid, "source_kind": "document", "document_chunk": span}}
    last_key = normalize_qdrant_id(chunks[-1]["embedding_id"])
    if condition == "missing_last":
        points.pop(last_key)
    elif condition in {"wrong_video", "wrong_scene", "wrong_kind", "wrong_epoch", "wrong_frame"}:
        field = {"wrong_video": "video_hash", "wrong_scene": "scene_id", "wrong_kind": "source_kind",
                 "wrong_epoch": "epoch_id", "wrong_frame": "ucf_frame_id"}[condition]
        points[last_key]["payload"][field] = 9999 if field == "ucf_frame_id" else "wrong"
    elif condition == "wrong_chunk":
        points[last_key]["payload"]["document_chunk"]["text"] = "wrong passage"
    elif condition == "missing_chunk":
        points[last_key]["payload"].pop("document_chunk")
    elif condition == "missing_frame":
        points[last_key]["payload"].pop("ucf_frame_id")
    elif condition == "wrong_chunk_type":
        points[last_key]["payload"]["document_chunk"]["chunk_index"] = True
    checked = []
    def post(url, json, **kwargs):
        if url.endswith("scroll"):
            body = {"result": {"points": list(points.values()) if "/goodq_text/" in url else [],
                               "next_page_offset": None}}
        else:
            checked.extend(json["ids"])
            body = {"result": [deepcopy(points[key]) for key in json["ids"] if key in points]}
        return SimpleNamespace(status_code=200, json=lambda: body)
    monkeypatch.setattr("scripts.ucf.validate_ucf_epoch.requests.post", post)
    assert run_validation(mode="strict", config=cfg) == (0 if condition == "matches" else 1)
    assert checked == [normalize_qdrant_id(chunk["embedding_id"]) for chunk in chunks]
    assert _stored_group(root, fid) == before
    if condition != "matches":
        report = json.loads((root / "reports/ucf_validation_report.json").read_text())
        assert report["vector_integrity"]["errors"]


def test_scalar_record_still_rejects_arbitrary_nested_payload():
    base = {"video_hash": "source", "epoch_id": "epoch", "run_id": "run", "t_start": 0,
            "t_end": 0, "modality": "text", "worker_name": "text_embed", "model_tag": "model"}
    scalar = UCFRecord(**base, payload={"text": "scalar remains supported"}, vector_key="a" * 64)
    assert scalar.vector_key == "a" * 64
    with pytest.raises(ValidationError, match="must be flat"):
        UCFRecord(**base, payload={"unrelated": {"nested": True}})


def test_offline_scalar_empty_vector_key_is_still_rejected(standalone):
    root, cfg, _client = standalone
    cfg["qdrant"] = {"collections": {"text": "goodq_text"}}
    _, _, _chunks, fid = stage_document_chunks(root)
    _rewrite_payload(root, fid, {"source_kind": "document"})
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        conn.execute("UPDATE context_frames SET vector_key='' WHERE frame_id=?", (fid,))
    assert run_validation(config=cfg) == 1
    report = json.loads((root / "reports/ucf_validation_report.json").read_text())
    assert any("Malformed vector key" in error for error in report["vector_integrity"]["errors"])
