"""Standalone projection acceptance through the actual ASGI readers, without compute."""
from contextlib import closing
import hashlib
import json
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest


@pytest.fixture(params=[("image", ".png", "image/png"), ("document", ".txt", "text/plain"),
                       ("audio", ".wav", "audio/wav"),
                       pytest.param(("document", ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"), id="docx")])
def standalone_library(request, tmp_path, monkeypatch):
    from api.routes import media, scenes, search, system, timeline
    from api.utils import loaders

    kind, suffix, mime = request.param
    if suffix == ".docx":
        # Delivery must not depend on the host having Word MIME associations.
        monkeypatch.setattr(loaders.mimetypes, "guess_type", lambda *_args, **_kwargs: (None, None))
    content = b"retained standalone source bytes"
    digest = hashlib.sha256(content).hexdigest()
    data = tmp_path / "epoch-standalone"
    directory = data / "processing" / digest
    (directory / "video").mkdir(parents=True)
    source = directory / (digest + suffix)
    source.write_bytes(content)
    scene_id = "canonical-scene"
    document_meta = None
    if suffix == ".docx":
        document_meta = {
            "engine": "python_docx_xml", "status": "ok", "text_scope": "main_document_body",
            "parts_read": ["word/document.xml"], "omitted_parts": ["word/header1.xml"],
            "omitted_features": [], "limitations": ["supplementary_parts_not_extracted", "image_text_ocr"],
        }
    segment = {"scene_id": scene_id, "segment_id": 0, "start": 0,
               "end": 2 if kind == "audio" else 0, "source_kind": kind,
               "document_text": "Family picnic notes" if kind == "document" else None,
               "document_meta": ({**document_meta, "tool_path": str(tmp_path / "private-parser.exe")}
                                 if document_meta else None),
               "transcript": "Hello family" if kind == "audio" else None,
               "transcript_outcome": "transcript_available" if kind == "audio" else None,
               "transcript_outcome_reason": "transcript_emitted" if kind == "audio" else None,
               "transcript_meta": {"status": "success", "engine": "wsl_unified", "speech_detection": {
                   "status": "completed", "method": "silero_vad", "input_duration_seconds": 2,
                   "speech_duration_seconds": 1.5}} if kind == "audio" else None}
    identity = {"video_id": digest, "video_hash": digest, "video_path": str(source),
                "source_path": str(source), "source_kind": kind, "original_filename": "memory" + suffix}
    temporal = directory / "temporal_index.json"
    manifest = directory / "video/scene_manifest.json"
    temporal.write_text(json.dumps({**identity, "segments": [segment]}), encoding="utf-8")
    manifest.write_text(json.dumps({**identity, "scenes": [{**segment, "index": 0}]}), encoding="utf-8")
    ledger = data / "ucf/ucf_ledger.db"
    ledger.parent.mkdir()
    with closing(sqlite3.connect(ledger)) as conn, conn:
        conn.execute("CREATE TABLE context_frames (video_hash TEXT, epoch_id TEXT, promotion_status TEXT)")

    def status(value):
        with closing(sqlite3.connect(ledger)) as conn, conn:
            conn.execute("DELETE FROM context_frames")
            if value:
                conn.execute("INSERT INTO context_frames VALUES (?,?,?)", (digest, data.name, value))

    for key in ("_DEFAULT_PROCESSING_ROOT", "_DEFAULT_PROCESSED_ROOT", "_DEFAULT_UCF_SCOPE"):
        monkeypatch.setattr(loaders, key, None)
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", ())
    loaders.configure_from_cfg({"paths": {"data_root": str(data), "processing": str(directory.parent),
                                         "db_dir": str(data)}})
    class Engine:
        def search_text(self, *args, **kwargs):
            # Deliberately stale candidate: the reader must still apply lifecycle visibility.
            return [{"score": .9, "modality": "text", "payload": {
                "video_id": digest, "scene_id": scene_id, "source_kind": kind}}]

        def search_similar_scene(self, **kwargs):
            return self.search_text()

        def search_multimodal(self, query, *, top_k, modalities, retrieval_context):
            assert modalities == ['text'] and retrieval_context == 'human.ui.search'
            return self.search_text()

    monkeypatch.setattr(search, "_search_engine", Engine())
    monkeypatch.setattr(scenes, "_search_engine", Engine())
    app = FastAPI()
    for module in (media, scenes, search, system, timeline):
        monkeypatch.setattr(module, "_data_loader", None)
        app.include_router(module.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield {"client": client, "status": status, "kind": kind, "mime": mime,
               "document_meta": document_meta,
               "digest": digest, "scene_id": scene_id, "content": content, "source": source,
               "temporal": temporal, "manifest": manifest, "loaders": loaders}


def test_promoted_standalone_actual_readers_keep_source_semantics(standalone_library):
    f = standalone_library
    f["status"]("promoted")
    client, digest = f["client"], f["digest"]
    listing = client.get("/api/system/videos")
    assert listing.status_code == 200
    assert listing.json()[0]["source_kind"] == f["kind"]
    scene = client.get(f"/api/videos/{digest}/scenes/{f['scene_id']}")
    assert scene.status_code == 200
    body = scene.json()
    assert body["source_kind"] == f["kind"]
    assert body["document_meta"] == f["document_meta"]
    assert body["original_source_available"] is True
    assert body["original_video_available"] is False
    assert body["original_video_endpoint"] is None
    source = client.get(body["original_source_endpoint"])
    assert source.status_code == 200
    assert source.content == f["content"]
    assert source.headers["content-type"].split(";")[0] == f["mime"]
    ranged = client.get(body["original_source_endpoint"], headers={"Range": "bytes=0-7"})
    assert ranged.status_code == 206
    assert ranged.content == f["content"][:8]
    assert ranged.headers["content-range"] == f"bytes 0-7/{len(f['content'])}"
    assert body["original_source_media_type"] == f["mime"]
    if f["kind"] == "image":
        assert body["representative_frame_endpoint"] == body["original_source_endpoint"]
    timeline = client.get(f"/api/videos/{digest}/timeline/full").json()
    assert timeline["source_kind"] == f["kind"]
    assert timeline["segments"][0]["document_meta"] == f["document_meta"]
    result = client.get("/api/search/text", params={"q": "family"}).json()["results"][0]
    assert result["source_kind"] == f["kind"]
    assert result["document_meta"] == f["document_meta"]
    similar = client.get(f"/api/videos/{digest}/scenes/{f['scene_id']}/similar")
    assert similar.status_code == 200
    assert similar.json()[0]["original_source_endpoint"] == body["original_source_endpoint"]
    assert similar.json()[0]["document_meta"] == f["document_meta"]
    if f["kind"] == "audio":
        for projected in (body, timeline['segments'][0], result, similar.json()[0]):
            assert projected['transcript_outcome'] == 'transcript_available'
            assert projected['transcript_outcome_reason'] == 'transcript_emitted'
            assert projected['transcript_meta']['speech_detection']['speech_duration_seconds'] == 1.5
    if f["kind"] == "image":
        assert result["representative_frame_endpoint"] == timeline["segments"][0]["representative_frame_endpoint"] == body["original_source_endpoint"]
    if f["kind"] == "document":
        assert body["document_text"] == timeline["segments"][0]["document_text"] == result["document_text"] == "Family picnic notes"
        assert body["transcript"] is None and body["ocr_text"] is None


@pytest.mark.parametrize("standalone_library", [("audio", ".wav", "audio/wav")], indirect=True)
@pytest.mark.parametrize("status,note", [("not_applicable", "no_speech_detected"),
                                       ("error", "model failed"), ("skipped", "disabled by runtime config")])
def test_speech_enrichment_outcomes_survive_actual_readers(standalone_library, status, note):
    f = standalone_library
    f["status"]("promoted")
    temporal = json.loads(f["temporal"].read_text(encoding="utf-8"))
    fields = {"diarization_status": status, "diarization_note": note,
              "emotion_status": status, "emotion_note": note}
    temporal["segments"][0].update(fields)
    f["temporal"].write_text(json.dumps(temporal), encoding="utf-8")
    client, digest, scene = f["client"], f["digest"], f["scene_id"]
    results = [client.get(f"/api/videos/{digest}/scenes/{scene}").json(),
               client.get(f"/api/videos/{digest}/timeline/full").json()["segments"][0],
               client.get("/api/search/text", params={"q": "family"}).json()["results"][0],
               client.get(f"/api/videos/{digest}/scenes/{scene}/similar").json()[0]]
    for result in results:
        assert {key: result.get(key) for key in fields} == fields


@pytest.mark.parametrize("standalone_library", [("audio", ".wav", "audio/wav")], indirect=True)
def test_unreviewed_word_alignment_survives_actual_readers(standalone_library):
    f = standalone_library
    f['status']('promoted')
    temporal = json.loads(f['temporal'].read_text(encoding='utf-8'))
    alignment = {'method':'whisper_cross_attention_dtw', 'timebase':'input_audio_seconds',
                 'review_status':'unreviewed', 'status':'available', 'words':[
                     {'text':'hello','start':.4,'end':.7,'timing_status':'aligned'}]}
    temporal['segments'][0]['transcript_meta']['word_alignment'] = alignment
    f['temporal'].write_text(json.dumps(temporal), encoding='utf-8')
    client, digest, scene = f['client'], f['digest'], f['scene_id']
    results = [client.get(f'/api/videos/{digest}/scenes/{scene}').json(),
               client.get(f'/api/videos/{digest}/timeline/full').json()['segments'][0],
               client.get('/api/search/text',params={'q':'family'}).json()['results'][0]]
    assert all(r['transcript_meta']['word_alignment'] == alignment for r in results)


@pytest.mark.parametrize("status", [None, "staged", "validated", "rejected", "superseded"])
def test_standalone_requires_promotion_across_actual_readers(standalone_library, status):
    f = standalone_library
    f["status"](status)
    client, digest = f["client"], f["digest"]
    assert client.get("/api/system/videos").json() == []
    for path in (f"/api/videos/{digest}/scenes", f"/api/videos/{digest}/timeline/full",
                 f"/api/media/video/{digest}/source"):
        assert client.get(path).status_code == 404
    result = client.get("/api/search/text", params={"q": "family"})
    assert result.status_code == 200
    assert result.json()["results"] == []


def test_standalone_source_tamper_never_serves_wrong_bytes(standalone_library):
    f = standalone_library
    f["status"]("promoted")
    f["source"].write_bytes(b"different bytes")
    assert f["client"].get(f"/api/media/video/{f['digest']}/source").status_code == 404


def test_standalone_unconfigured_scope_does_not_become_legacy_visible(standalone_library):
    f = standalone_library
    f["status"]("promoted")
    f["loaders"].configure_from_cfg({"paths": {"processing": str(f["temporal"].parent.parent)}})
    assert f["client"].get("/api/system/videos").json() == []


@pytest.mark.parametrize("mismatch", ["kind", "path", "outside"])
def test_standalone_original_requires_agreeing_contained_identity(standalone_library, tmp_path, mismatch):
    f = standalone_library
    f["status"]("promoted")
    manifest = json.loads(f["manifest"].read_text(encoding="utf-8"))
    if mismatch == "kind":
        manifest["source_kind"] = "video"
    elif mismatch == "path":
        manifest["source_path"] = str(f["source"].with_name("other" + f["source"].suffix))
    else:
        outside = tmp_path / ("outside" + f["source"].suffix)
        outside.write_bytes(f["content"])
        temporal = json.loads(f["temporal"].read_text(encoding="utf-8"))
        for record in (manifest, temporal):
            record["source_path"] = record["video_path"] = str(outside)
        f["temporal"].write_text(json.dumps(temporal), encoding="utf-8")
    f["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    assert f["client"].get(f"/api/media/video/{f['digest']}/source").status_code == 404
