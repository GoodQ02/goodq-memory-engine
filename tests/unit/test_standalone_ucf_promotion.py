"""Standalone anchors cross the real validator and governed materializer."""
import hashlib
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("goodq_mini_agent")

from agents.mini_agent_client import MiniAgentClient
from scripts.ucf.ucf_ledger import UCFLedgerClient
from scripts.ucf.validate_ucf_epoch import make_scene_hash, run_validation
from tests.unit.test_ucf_promotion_scene_identity import confirmed
from tests.unit.test_standalone_lifecycle_producer import standalone_runtime, source_file
from tests.unit.test_watchdog_safety import standalone_audio_dispatch


@pytest.fixture
def standalone(tmp_path, monkeypatch):
    root = tmp_path / "epoch_standalone"
    cfg = {"agent": {"execution_mode": "in_process"}, "ingestion_isolation": True,
           "paths": {"db_dir": str(root), "data_root": str(tmp_path),
                     "db_path": str(root / "memory.db"),
                     "knowledge_graph_db": str(root / "knowledge_graph.db"),
                     "processing": str(root / "processing"), "reports_dir": str(root / "reports")}}
    monkeypatch.setenv("GOODQ_AGENT_EXECUTION_MODE", "in_process")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
    client = MiniAgentClient(profile="safe", config=cfg)
    # No vector compute/transport in the anchor-only fixture. Do not fabricate
    # delivery completion; local materialization reports sync pending honestly.
    monkeypatch.setattr(client, "_sync_ucf_status_to_qdrant", lambda *a, **k: {
        "status": "ok", "points_attempted": 0, "points_verified": 0,
        "collections_attempted": [], "failed_collections": []})
    monkeypatch.setattr(client, "_sync_qdrant_by_scope", lambda **k: {
        "status": "ok", "points_verified": 0, "failed_collections": []})
    return root, cfg, client


def stage_standalone(root, kind, content=b"source fixture", *, audio_duration=2.5):
    source_hash = hashlib.sha256(content).hexdigest()
    folder = root / "processing" / source_hash
    folder.mkdir(parents=True)
    suffix = {"image": ".png", "document": ".txt", "audio": ".wav"}[kind]
    source = folder / f"{source_hash}{suffix}"
    source.write_bytes(content)
    duration = audio_duration if kind == "audio" else 0.0
    scene_id = make_scene_hash(source_hash, 0.0, duration)
    raw = folder / "raw_result.json"
    document_text = "Nebula archive entry with distinct document semantics."
    raw.write_text(json.dumps({"source_kind": kind, "document_text": document_text if kind == "document" else None}))
    payload = {"source_kind": kind, "source_hash": source_hash, "source_path": str(source),
               "original_filename": "original" + suffix, "scene_id": scene_id, "scene_index": 0,
               "start": 0.0, "end": duration, "duration": duration, "width": 0, "height": 0}
    if kind == "document":
        payload["document_text"] = document_text
    (root / "ucf").mkdir(exist_ok=True)
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    ledger.init_schema()
    ledger.register_media(video_hash=source_hash, file_path=str(source), duration=duration, fps=0, width=0, height=0)
    ledger.log_frame(video_hash=source_hash, epoch_id=root.name, run_id="standalone-test",
                     t_start=0.0, t_end=duration, modality={"image": "multimodal", "document": "text", "audio": "audio"}[kind],
                     worker_name="standalone_source", model_tag="source_sha256", source_artifact_id=scene_id,
                     raw_ref=str(raw), payload=payload)
    ledger.close()
    scene = {"scene_id": scene_id, "video_id": source_hash, "index": 0, "start": 0.0,
             "end": duration, "duration": duration, "source_kind": kind,
             "source_path": str(source), "original_filename": "original" + suffix}
    if kind == "document":
        scene.update(document_text=document_text, document_meta={"parser": "fixture-parser"})
    manifest = {"video_hash": source_hash, "video_id": source_hash, "video_path": str(source),
                "source_path": str(source), "source_kind": kind, "phase5_complete": True,
                "total_scenes": 1, "scenes": [scene]}
    manifest_path = folder / "video/scene_manifest.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (folder / "temporal_index.json").write_text(json.dumps({
        key: value for key, value in {**manifest, "segments": [scene]}.items() if key != "scenes"
    }))
    return source_hash, scene_id, manifest_path, source


def stage_document_chunks(root):
    from steps.common.memory import to_faiss_id

    source_hash, scene_id, manifest, source = stage_standalone(root, "document")
    text = json.loads(manifest.read_text())["scenes"][0]["document_text"]
    chunks = []
    for index, (start, end) in enumerate(((0, 30), (24, len(text)))):
        embedding_id = hashlib.sha256(f"{source_hash}:{scene_id}:{start}:{end}".encode()).hexdigest()
        chunks.append({"embedding_id": embedding_id, "faiss_id": to_faiss_id(embedding_id),
                       "chunk_index": index, "char_start": start, "char_end": end,
                       "text": text[start:end], "token_count": 8})
    payload = {"source_kind": "document", "embedding_source": "document_text", "origin_modality": "document",
               "embedding_chunks": chunks, "text_length": len(text),
               "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "chunk_count": len(chunks),
               "chunk_token_limit": 254}
    raw = source.parent / "text_chunks.json"
    raw.write_text(json.dumps(payload), encoding="utf-8")
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    fid = ledger.log_frame(video_hash=source_hash, epoch_id=root.name, run_id="chunk-test",
        t_start=0.0, t_end=0.0, modality="text", worker_name="text_embed",
        model_tag="sentence-transformers/all-MiniLM-L6-v2", source_artifact_id=scene_id,
        raw_ref=str(raw), payload=payload, vector_backend="qdrant", vector_collection="goodq_text",
        vector_dim=384, vector_model_tag="sentence-transformers/all-MiniLM-L6-v2")
    ledger.close()
    return source_hash, scene_id, chunks, fid


@pytest.mark.parametrize("scene_retirement", [False, True])
def test_document_chunk_vectors_cross_real_promotion_replay_and_retirement(standalone, monkeypatch, scene_retirement):
    root, cfg, client = standalone
    cfg["qdrant"] = {"collections": {"text": "goodq_text"}}
    client.config["qdrant"] = cfg["qdrant"]
    source_hash, scene_id, chunks, fid = stage_document_chunks(root)
    scope = {"video_hash": source_hash, "epoch_id": root.name}
    validated, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, validated
    fetched = []
    synced = []
    monkeypatch.setattr(client, "_fetch_vector_from_qdrant", lambda collection, key: (
        fetched.append((collection, key)) or [1.0] + [0.0] * 383))
    def sync(frames, status, **kwargs):
        synced.append((status, list(frames)))
        return {"status": "ok", "points_attempted": len(frames), "points_verified": len(frames),
                "collections_attempted": ["goodq_text"], "failed_collections": []}
    monkeypatch.setattr(client, "_sync_ucf_status_to_qdrant", sync)
    monkeypatch.setattr(client, "_sync_qdrant_by_scope", lambda **kwargs: {
        "status": "ok", "points_verified": len(chunks), "failed_collections": []})
    for _ in range(2):
        promoted, rc = confirmed(client, "promote_ucf_to_memory", scope)
        assert rc == 0, json.dumps(promoted)
    ids = {chunk["embedding_id"] for chunk in chunks}
    assert {key for _, key in fetched} == ids
    assert all({key for key, _, _ in refs} == ids for status, refs in synced if status == "promoted")
    with sqlite3.connect(root / "memory.db") as conn:
        rows = conn.execute("SELECT hash,scene_id,ucf_provenance FROM embeddings").fetchall()
        assert {row[0] for row in rows} == ids
        assert all(row[1] == scene_id and json.loads(row[2]) == [fid] for row in rows)
        assert conn.execute("SELECT count(*) FROM scenes").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM segments").fetchone()[0] == 0
    from cli import retrieve
    import faiss
    import numpy as np
    index_path = root / "text.index"
    index = faiss.IndexIDMap2(faiss.IndexFlatL2(384))
    index.add_with_ids(np.array([[1.0] + [0.0] * 383, [2.0] + [0.0] * 383], dtype="float32"),
                       np.array([chunk["faiss_id"] for chunk in chunks], dtype="int64"))
    faiss.write_index(index, str(index_path))
    cfg["paths"]["faiss_index_path"] = str(index_path)
    cfg["qdrant"]["enabled"] = False
    monkeypatch.setattr(retrieve, "_load_cfg", lambda: cfg)
    monkeypatch.setattr(retrieve, "_embed_query", lambda text: (np.zeros((1, 384), dtype="float32"), np))
    matches = retrieve.search_text_index("fixture query", 2)["matches"]
    assert [match["score"] for match in matches] == [1.0, 4.0]
    assert all(match["scene"]["scene_id"] == scene_id for match in matches)
    retirement = client._resolve_scene_retirement({**scope, "scene_id": scene_id})
    assert {vector["key"] for vector in retirement["vectors"]} == ids
    retired, rc = confirmed(client, "supersede_ucf_frames", {
        **scope, **({"scene_id": scene_id} if scene_retirement else {}),
    })
    assert rc == 0, retired
    assert {key for key, _, _ in synced[-1][1]} == ids
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT count(*) FROM embeddings").fetchone()[0] == 0
    assert retrieve.search_text_index("fixture query", 2)["matches"] == []
    replay, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc != 0 or replay["output"]["status"] == "nothing_to_promote", replay
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT count(*) FROM embeddings").fetchone()[0] == 0


def test_document_chunk_rejection_syncs_every_reference(standalone, monkeypatch):
    root, cfg, client = standalone
    source_hash, _, chunks, _ = stage_document_chunks(root)
    synced = []
    monkeypatch.setattr(client, "_sync_ucf_status_to_qdrant", lambda refs, status, **kwargs: (
        synced.append((status, list(refs))) or {"status": "ok"}))
    result, rc = confirmed(client, "reject_ucf_frames", {
        "video_hash": source_hash, "epoch_id": root.name, "reason": "fixture rejection",
    })
    assert rc == 0, result
    assert synced[-1][0] == "rejected"
    assert {key for key, _, _ in synced[-1][1]} == {chunk["embedding_id"] for chunk in chunks}


@pytest.mark.parametrize("bad_vector", [None, [1.0], [float("nan")] * 384])
def test_document_chunk_missing_or_invalid_vector_prevents_promotion(standalone, monkeypatch, bad_vector):
    root, cfg, client = standalone
    cfg["qdrant"] = {"collections": {"text": "goodq_text"}}
    client.config["qdrant"] = cfg["qdrant"]
    source_hash, _, chunks, _ = stage_document_chunks(root)
    scope = {"video_hash": source_hash, "epoch_id": root.name}
    validated, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, validated
    monkeypatch.setattr(client, "_fetch_vector_from_qdrant", lambda collection, key:
                        bad_vector if key == chunks[-1]["embedding_id"] else [1.0] + [0.0] * 383)
    promoted, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc != 0 and "Document chunk vector is missing or invalid" in json.dumps(promoted), promoted
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute("SELECT DISTINCT promotion_status FROM context_frames").fetchall() == [("validated",)]
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT count(*) FROM embeddings").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["image", "document", "audio"])
def test_explicit_standalone_anchor_validates_through_miniagent(standalone, kind):
    root, cfg, client = standalone
    stage_standalone(root, kind)
    result, rc = client.execute_tool("validate_ucf_epoch", {})
    assert rc == 0 and result["output"]["success"], result


@pytest.mark.parametrize('duration', [5.0,45.0133125,20.0106875])
def test_standalone_audio_bounds_use_ledger_millisecond_precision(standalone, duration):
    root,cfg,client=standalone
    stage_standalone(root,'audio',audio_duration=duration)
    result,rc=client.execute_tool('validate_ucf_epoch',{})
    assert rc==0 and result['output']['success'],result


@pytest.mark.parametrize('extra_ms,valid', [(0,True),(1,False)])
def test_derived_audio_frames_obey_the_same_millisecond_bounds(standalone, extra_ms, valid):
    root,cfg,client=standalone
    duration=20.0106875
    source_hash,scene_id,_,_=stage_standalone(root,'audio',audio_duration=duration)
    ledger=UCFLedgerClient(str(root/'ucf/ucf_ledger.db'))
    ledger.log_frame(video_hash=source_hash,epoch_id=root.name,run_id='derived-endpoint',
                     t_start=0.0,t_end=round(duration,3)+extra_ms/1000,
                     modality='audio',worker_name='audio_metadata',model_tag='measured',
                     source_artifact_id=scene_id,
                     raw_ref=str(root/'processing'/source_hash/'raw_result.json'),
                     payload={'source_kind':'audio'})
    ledger.close()
    result,rc=client.execute_tool('validate_ucf_epoch',{})
    assert rc==0
    assert result['output']['success'] is valid,result


@pytest.mark.parametrize('fault', [None, 'clap_failed', 'text_failed', 'words_present', 'transport_failed'])
def test_silent_audio_promotes_without_inventing_vector_delivery(standalone, monkeypatch, fault):
    root, cfg, client = standalone
    source_hash, scene_id, _, _ = stage_standalone(root, 'audio')
    raw = {'source_kind':'audio','video_hash':source_hash,'scene_id':scene_id,
           'transcript_outcome':'no_speech','transcript':'',
           'clap_meta':{'status':'skipped','reason':'audio_silent','input_policy':'full_scene'},
           'audio_text_embed_meta':{'status':'no_text'}}
    if fault == 'clap_failed': raw['clap_meta']['status']='error'
    if fault == 'text_failed': raw['audio_text_embed_meta']['status']='error'
    if fault == 'words_present': raw['transcript']='words'
    (root/'processing'/source_hash/'raw_result.json').write_text(json.dumps(raw))
    monkeypatch.setattr(client, '_sync_ucf_status_to_qdrant', lambda *a, **k: {
        'status':'skipped','points_attempted':0,'points_verified':0,'failed_collections':[]})
    monkeypatch.setattr(client, '_sync_qdrant_by_scope', lambda **k: {
        'status':'warning','reason':'no_scoped_points_verified','points_verified':0,
        'failed_collections':['offline'] if fault=='transport_failed' else []})
    scope={'video_hash':source_hash,'epoch_id':root.name}
    confirmed(client,'validate_ucf_frames',scope)
    result, rc=confirmed(client,'promote_ucf_to_memory',scope)
    if fault is None:
        assert rc == 0, result
        assert result['output']['status']=='promoted_complete'
        assert result['output']['scope_sync']['reason']=='supported_audio_vector_absence'
        assert result['output']['scope_sync']['points_verified']==0
    else:
        assert rc != 0
        assert result['output']['status']=='promotion_committed_sync_pending'


def test_document_promotes_distinct_text_projection_and_retires_scope(standalone):
    root, cfg, client = standalone
    target = stage_standalone(root, "document")
    other = stage_standalone(root, "document", b"other document")
    for source_hash, scene_id, _, _ in (target, other):
        scope = {"video_hash": source_hash, "epoch_id": root.name}
        validated, rc = confirmed(client, "validate_ucf_frames", scope)
        assert rc == 0, validated
        promoted, _ = confirmed(client, "promote_ucf_to_memory", scope)
        assert promoted["output"]["status"] == "promotion_committed_sync_pending", promoted
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT content_type FROM scene_text_fts ORDER BY scene_id").fetchall() == [("document_text",), ("document_text",)]
        assert {row[0] for row in conn.execute("SELECT scene_id FROM scene_text_fts WHERE scene_text_fts MATCH 'Nebula'")} == {target[1], other[1]}
        meta = json.loads(conn.execute("SELECT meta FROM scenes WHERE id=?", (target[1],)).fetchone()[0])
        assert meta["source_kind"] == "document"
        assert meta["document_text"].startswith("Nebula")
        assert meta["document_meta"] == {"parser": "fixture-parser"}
        assert conn.execute("SELECT count(*) FROM segments").fetchone()[0] == 0
    with sqlite3.connect(root / "knowledge_graph.db") as conn:
        media_type, properties = conn.execute("SELECT media_type,properties FROM media_nodes WHERE scene_id=?", (target[1],)).fetchone()
        assert media_type == "document"
        assert json.loads(properties)["source_kind"] == "document"
    replay, _ = confirmed(client, "promote_ucf_to_memory", {"video_hash": target[0], "epoch_id": root.name})
    assert replay["output"]["status"] == "promotion_committed_sync_pending", replay
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT count(*) FROM scene_text_fts").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM scenes").fetchone()[0] == 2
    result, rc = confirmed(client, "supersede_ucf_frames", {"video_hash": target[0], "epoch_id": root.name})
    assert rc == 0, result
    with sqlite3.connect(root / "memory.db") as conn:
        assert conn.execute("SELECT scene_id FROM scene_text_fts").fetchall() == [(other[1],)]
    with sqlite3.connect(root / "knowledge_graph.db") as conn:
        assert conn.execute("SELECT scene_id FROM media_nodes").fetchall() == [(other[1],)]
    assert target[3].exists() and other[3].exists()


@pytest.mark.parametrize("bad", ["missing_source", "changed_bytes", "wrong_kind", "wrong_scene", "document_text_mismatch", "no_anchor",
                                "missing_temporal", "invalid_temporal", "temporal_source", "temporal_scene", "temporal_bounds", "temporal_text"])
def test_invalid_standalone_evidence_fails_validator_and_promotion_before_writes(standalone, bad):
    root, cfg, client = standalone
    source_hash, scene_id, path, source = stage_standalone(root, "document")
    manifest = json.loads(path.read_text())
    if bad == "missing_source":
        source.unlink()
    elif bad == "changed_bytes":
        source.write_bytes(b"changed")
    elif bad == "wrong_kind":
        manifest["source_kind"] = "image"
    elif bad == "wrong_scene":
        manifest["scenes"][0]["scene_id"] = "wrong"
    elif bad == "document_text_mismatch":
        manifest["scenes"][0]["document_text"] = "substitute text"
    elif bad == "no_anchor":
        with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
            conn.execute("UPDATE context_frames SET worker_name='document_parser'")
    elif bad.endswith("temporal") or bad.startswith("temporal_"):
        temporal_path = source.parent / "temporal_index.json"
        if bad == "missing_temporal":
            temporal_path.unlink()
        elif bad == "invalid_temporal":
            temporal_path.write_text("incomplete {")
        else:
            temporal = json.loads(temporal_path.read_text())
            if bad == "temporal_source":
                temporal["source_kind"] = "audio"
            elif bad == "temporal_scene":
                temporal["segments"][0]["scene_id"] = "wrong"
            elif bad == "temporal_bounds":
                temporal["segments"][0]["end"] = 1.0
            elif bad == "temporal_text":
                temporal["segments"][0]["document_text"] = "substitute text"
            temporal_path.write_text(json.dumps(temporal))
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert run_validation(config=cfg) == 1
    scope = {"video_hash": source_hash, "epoch_id": root.name}
    confirmed(client, "validate_ucf_frames", scope)
    result, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc != 0 and "Standalone" in json.dumps(result), result
    assert not (root / "memory.db").exists()
    with sqlite3.connect(root / "ucf/ucf_ledger.db") as conn:
        assert conn.execute("SELECT promotion_status FROM context_frames").fetchone() == ("validated",)


@pytest.mark.parametrize("kind", ["image", "document", "audio"])
def test_watchdog_output_crosses_real_validator_and_promoter(standalone_runtime, monkeypatch, tmp_path, kind):
    processor, _calls, cfg, _bridge = standalone_runtime
    root = Path(cfg["paths"]["db_dir"])
    cfg["qdrant"] = {"collections": {"text": "test_text"}}
    cfg["paths"].update(db_path=str(root / "memory.db"), knowledge_graph_db=str(root / "knowledge_graph.db"),
                        reports_dir=str(root / "reports"))
    source = source_file(tmp_path, kind)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assert getattr(processor, f"ingest_{kind}")(source, f"real-caller-{kind}") is True
    monkeypatch.setenv("GOODQ_AGENT_EXECUTION_MODE", "in_process")
    client = MiniAgentClient(profile="safe", config=cfg)
    monkeypatch.setattr(client, "_sync_ucf_status_to_qdrant", lambda *a, **k: {
        "status": "ok", "points_attempted": 0, "points_verified": 0,
        "collections_attempted": [], "failed_collections": []})
    monkeypatch.setattr(client, "_sync_qdrant_by_scope", lambda **k: {
        "status": "ok", "points_verified": 0, "failed_collections": []})
    validated, rc = client.execute_tool("validate_ucf_epoch", {})
    assert rc == 0 and validated["output"]["success"], validated
    scope = {"video_hash": source_hash, "epoch_id": root.name}
    marked, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, marked
    promoted, _rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert promoted["output"]["status"] == "promotion_committed_sync_pending", promoted
    with sqlite3.connect(root / "memory.db") as conn:
        rows = conn.execute("SELECT meta FROM scenes WHERE video_hash=?", (source_hash,)).fetchall()
        assert len(rows) == 1
        scene = json.loads(rows[0][0])
        assert scene["source_kind"] == kind
        if kind == "image":
            assert len(scene["keyframe"]["objects"]) == 2
        elif kind == "document":
            assert scene["document_text"] == source.read_text()
            assert scene["document_meta"]["engine"] == "python_utf8"
            assert conn.execute("SELECT content_type,text FROM scene_text_fts").fetchall() == [("document_text", source.read_text())]
        else:
            segments = [json.loads(row[0]) for row in conn.execute("SELECT meta FROM segments")]
            assert [seg["text"] for seg in segments] == ["A bounded audio transcript"]
        if kind != "audio":
            assert conn.execute("SELECT count(*) FROM segments").fetchone()[0] == 0


@pytest.mark.parametrize("kind,worker,modality,collection,dim,tag", [
    ("image", "image_embed_dino", "multimodal", "dino", 1024, "facebook/dinov2-large"),
    ("document", "text_embed", "text", "text", 384, "sentence-transformers/all-MiniLM-L6-v2"),
    ("audio", "audio_embed_clap", "audio", "audio", 512, "laion/clap-htsat-unfused"),
])
@pytest.mark.parametrize("point_kind", ["matches", "wrong"])
def test_standalone_strict_vector_identity(standalone, monkeypatch, kind, worker, modality, collection, dim, tag, point_kind):
    root, cfg, client = standalone
    source_hash, scene_id, _manifest, source = stage_standalone(root, kind)
    key = "d" * 64
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    fid = ledger.log_frame(video_hash=source_hash, epoch_id=root.name, run_id="vector-test",
        t_start=0.0, t_end=2.5 if kind == "audio" else 0.0, modality=modality,
        worker_name=worker, model_tag=tag, source_artifact_id=scene_id,
        raw_ref=str(source.parent / "raw_result.json"), vector_key=key,
        vector_backend="qdrant", vector_collection=collection, vector_dim=dim,
        vector_model_tag=tag, payload={"source_kind": kind})
    ledger.close()
    point = {"id": key, "payload": {"video_hash": source_hash, "scene_id": scene_id,
        "scene_hash": key, "modality": modality, "worker_name": worker,
        "vector_model_tag": tag, "epoch_id": root.name, "ucf_frame_id": fid,
        "source_kind": kind if point_kind == "matches" else "video"}}
    def post(url, json, **kwargs):
        body = {"result": {"points": [], "next_page_offset": None}} if url.endswith("scroll") else {"result": [point]}
        return SimpleNamespace(status_code=200, json=lambda: body)
    monkeypatch.setattr("scripts.ucf.validate_ucf_epoch.requests.post", post)
    assert run_validation(mode="strict", config=cfg) == (0 if point_kind == "matches" else 1)
    if point_kind == "wrong":
        report = json.loads((root / "reports/ucf_validation_report.json").read_text())
        assert any("source_kind mismatch" in error for error in report["vector_integrity"]["errors"])


@pytest.mark.parametrize("bad", ["video_modality", "outside_static_bounds", "wrong_scene", "wrong_kind"])
def test_derived_image_frame_cannot_escape_anchor_contract(standalone, bad):
    root, cfg, client = standalone
    source_hash, scene_id, _manifest, source = stage_standalone(root, "image")
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    ledger.log_frame(video_hash=source_hash, epoch_id=root.name, run_id="derived-test",
        t_start=0.0, t_end=.001 if bad == "outside_static_bounds" else 0.0,
        modality="video" if bad == "video_modality" else "multimodal",
        worker_name="object_detect", model_tag="fixture-detector",
        source_artifact_id="wrong" if bad == "wrong_scene" else scene_id,
        raw_ref=str(source.parent / "raw_result.json"),
        payload={"source_kind": "document" if bad == "wrong_kind" else "image"})
    ledger.close()
    assert run_validation(config=cfg) == 1
    scope = {"video_hash": source_hash, "epoch_id": root.name}
    confirmed(client, "validate_ucf_frames", scope)
    result, rc = confirmed(client, "promote_ucf_to_memory", scope)
    assert rc != 0 and "Standalone" in json.dumps(result), result
    assert not (root / "memory.db").exists()
