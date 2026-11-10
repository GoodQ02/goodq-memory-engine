"""Actual readers must honor durable scene retirement before projection delivery."""
from contextlib import closing
import hashlib
import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.unit.test_ucf_promotion_scene_identity import scene_promotion, confirmed
from tests.unit.test_scene_scoped_retirement import prepare


@pytest.fixture
def scene_library(tmp_path, monkeypatch):
    from api.routes import media, scenes, search, summary, system, timeline
    from api.utils import loaders
    from retrieval import temporal_reasoning
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from lib.knowledge_graph import KnowledgeGraph

    data = tmp_path / "epoch-retirement"
    directory = data / "processing" / "sample"
    (directory / "video/frames").mkdir(parents=True)
    (directory / "audio/chunks").mkdir(parents=True)
    source = data / "sample.mp4"
    source.write_bytes(b"original source retained with both scenes")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    records = []
    for index in range(2):
        frame = directory / f"video/frames/scene_{index:04d}.jpg"
        audio = directory / f"audio/chunks/scene_{index:04d}.wav"
        frame.write_bytes(f"frame {index}".encode())
        audio.write_bytes(f"audio {index}".encode())
        records.append({"scene_id": f"canonical-{index}", "index": index,
                        "start": index * 10, "end": (index + 1) * 10,
                        "representative_frame": str(frame), "frame_paths": [str(frame)],
                        "audio": {"path": str(audio)}, "summary": f"scene {index}"})
    identity = {"video_id": digest, "video_hash": digest, "video_path": str(source)}
    temporal = directory / "temporal_index.json"
    manifest = directory / "video/scene_manifest.json"
    temporal.write_text(json.dumps({**identity, "segments": records, "total_scenes": 2,
                                    "top_candidate_visible_people": [{"entity": "retired only"}]}))
    manifest.write_text(json.dumps({**identity, "scenes": records}))
    ledger_path = data / "ucf/ucf_ledger.db"
    ledger_path.parent.mkdir()
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    frame_ids = [ledger.log_frame(
        video_hash=digest, epoch_id=data.name, run_id="fresh", t_start=i * 10,
        t_end=(i + 1) * 10, modality="video", worker_name="scene_summary",
        model_tag="fixture", source_artifact_id=f"canonical-{i}", promotion_status="promoted",
    ) for i in range(2)]
    ledger.close()

    def retire(index=0, *, corrupt=False, epoch=None, source_hash=None):
        canonical_id = hashlib.sha256(
            f"scene{source_hash or digest}|{index * 10:.3f}|{(index + 1) * 10:.3f}|".encode()
        ).hexdigest()
        evidence = {"kind": "scene_retirement", "version": 1,
                    "scene_id": canonical_id, "aliases": [canonical_id, f"canonical-{index}", f"legacy-{index}"],
                    "video_hash": source_hash or digest, "epoch_id": epoch or data.name,
                    "start": index * 10, "end": (index + 1) * 10,
                    "frame_ids": [frame_ids[index]], "vectors": []}
        if corrupt:
            evidence["aliases"] = None
        with closing(sqlite3.connect(ledger_path)) as conn, conn:
            UCFLedgerClient.insert_status_transition(
                conn, old_status="promoted", new_status="rejected", tool_name="ucf_retire_scene",
                video_hash=source_hash or digest, epoch_id=epoch or data.name,
                scope=f"scene_retirement:{canonical_id}", evidence=evidence, frame_ids=[frame_ids[index]],
            )
            if not epoch and not source_hash:
                conn.execute("UPDATE context_frames SET promotion_status='rejected' WHERE frame_id=?", (frame_ids[index],))

    for key in ("_DEFAULT_PROCESSING_ROOT", "_DEFAULT_PROCESSED_ROOT", "_DEFAULT_UCF_SCOPE"):
        monkeypatch.setattr(loaders, key, None)
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", ())
    memory = data / "memory.db"
    with closing(sqlite3.connect(memory)) as conn, conn:
        conn.executescript("CREATE TABLE scenes(id TEXT,video_hash TEXT,start REAL,end REAL,meta TEXT);"
                           "CREATE TABLE summaries(id INTEGER PRIMARY KEY,summary_type TEXT,category TEXT,content TEXT,created_at TEXT);")
        for record in records:
            conn.execute("INSERT INTO scenes VALUES(?,?,?,?,?)", (record["scene_id"], digest, record["start"], record["end"], "{}"))
            conn.execute("INSERT INTO summaries(summary_type,category,content,created_at) VALUES('scene','scene_summary',?,'now')",
                         (json.dumps({"scene_id": record["scene_id"], "summary": record["summary"]}),))
        conn.execute("INSERT INTO summaries(summary_type,category,content,created_at) VALUES('video','video_summary',?,'now')",
                     (json.dumps({"video_hash": digest, "summary": "scene 0 and scene 1", "method": "template",
                                  "provenance": {"source_artifact_versions": [{"scene_id": row["scene_id"]} for row in records]}}),))
    graph = data / "knowledge_graph.db"
    with KnowledgeGraph(str(graph)) as kg:
        person = kg.add_node("person", "Shared person")
        retired_person = kg.add_node("person", "Retired person")
        for index, record in enumerate(records):
            media_id = kg.add_media_node("video", str(source), scene_id=record["scene_id"],
                                        timestamp_start=record["start"], timestamp_end=record["end"],
                                        properties={"video_hash": digest})
            kg.link_node_to_media(person, media_id)
            if index == 0:
                kg.link_node_to_media(retired_person, media_id)
    cfg = {"paths": {"data_root": str(data), "processing": str(directory.parent), "db_dir": str(data), "db_path": str(memory), "knowledge_graph_db": str(graph)},
           "llm": {"features": {"video_summarization": False}}}
    loaders.configure_from_cfg(cfg)
    monkeypatch.setattr("steps.common.config_loader.load_configs", lambda *_a, **_kw: cfg)
    monkeypatch.setattr(temporal_reasoning, "load_configs", lambda *_a, **_kw: cfg)
    class Engine:
        weight_text = .5
        weight_visual = .5
        weight_audio = 0

        def _reset_search_diagnostics(self):
            pass

        def search_text(self, *args, **kwargs):
            return [{"score": .9, "modality": "text", "payload": {
                "video_id": "sample", "video_hash": digest, "scene_id": record["scene_id"],
                "start": record["start"], "end": record["end"],
            }} for record in records]
        search_visual = search_text
        search_multimodal = search_text
        search_similar_scene = search_text

    monkeypatch.setattr(search, "_search_engine", Engine())
    monkeypatch.setattr(search, "_config", {})
    monkeypatch.setattr(scenes, "_search_engine", Engine())
    app = FastAPI()
    for module in (media, scenes, search, summary, system, timeline):
        monkeypatch.setattr(module, "_data_loader", None)
        app.include_router(module.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield {"client": client, "retire": retire, "loader": loaders.DataLoader(), "records": records,
               "source": source, "temporal": temporal, "manifest": manifest, "ledger": ledger_path,
               "digest": digest, "data": data, "cfg": cfg, "memory": memory, "graph": graph}


@pytest.mark.parametrize("surface", ["scenes", "timeline", "manifest", "text", "visual", "multimodal", "similar"])
def test_retired_scene_disappears_before_outbox_delivery(scene_library, surface):
    f = scene_library
    client = f["client"]
    assert len(client.get("/api/videos/sample/scenes").json()) == 2
    before = {path: path.read_bytes() for path in (f["source"], f["temporal"], f["manifest"])}
    f["retire"]()
    if surface == "manifest":
        rows = f["loader"].load_scene_manifest("sample")["scenes"]
    elif surface in {"text", "visual", "multimodal"}:
        response = (client.post("/api/search/multimodal", json={"query": "family"})
                    if surface == "multimodal" else client.get(f"/api/search/{surface}", params={"q": "family"}))
        assert response.status_code == 200, response.text
        rows = response.json()["results"]
    else:
        route = {"scenes": "/api/videos/sample/scenes", "timeline": "/api/videos/sample/timeline/full",
                 "similar": "/api/videos/sample/scenes/canonical-1/similar"}[surface]
        response = client.get(route)
        assert response.status_code == 200, response.text
        rows = response.json()["segments"] if surface == "timeline" else response.json()
    assert [row["scene_id"] for row in rows] == ["canonical-1"]
    assert before == {path: path.read_bytes() for path in before}


@pytest.mark.parametrize("route", [
    "/api/videos/sample/scenes/canonical-0",
    "/api/videos/sample/scenes/canonical-0/similar",
    "/api/media/video/sample/scene/canonical-0/audio",
    "/api/media/audio/sample/0.wav",
    "/api/media/video/sample/frame/scene_0000.jpg",
])
def test_retired_scene_direct_routes_cannot_bypass_exclusion(scene_library, route):
    f = scene_library
    assert f["client"].get(route).status_code == 200
    f["retire"]()
    assert f["client"].get(route).status_code == 404
    assert f["client"].get("/api/videos/sample/scenes/canonical-1").status_code == 200
    assert f["client"].get("/api/media/video/sample/frame/scene_0001.jpg").content == b"frame 1"
    assert f["client"].get("/api/media/audio/sample/1.wav").content == b"audio 1"
    assert f["client"].get("/api/media/video/sample/source").content == f["source"].read_bytes()


def test_retirement_updates_listing_and_omits_stale_video_aggregates(scene_library):
    f = scene_library
    f["retire"]()
    listing = f["client"].get("/api/system/videos").json()
    assert listing[0]["total_scenes"] == 1
    assert listing[0]["thumbnail_endpoint"].endswith("scene_0001.jpg")
    metadata = f["client"].get("/api/videos/sample/timeline/full").json()["metadata"]
    assert "top_candidate_visible_people" not in metadata


def test_corrupt_relevant_retirement_is_observable(scene_library):
    f = scene_library
    f["retire"](corrupt=True)
    assert f["client"].get("/api/videos/sample/scenes").status_code == 500


def test_cached_video_summary_excludes_retired_scene_before_projection_delivery(scene_library):
    f = scene_library
    endpoint = f"/api/summary/video/{f['digest']}"
    assert f["client"].get(endpoint).json()["summary"] == "scene 0 and scene 1"
    f["retire"]()
    result = f["client"].get(endpoint)
    assert result.status_code == 200, result.text
    assert result.json()["method"] == "none"
    assert "scene 0" not in result.json()["summary"]


def test_regeneration_uses_only_surviving_scene_evidence_before_delivery(scene_library):
    from steps.video_summarizer.step import run_step
    f = scene_library
    f["retire"]()
    generated = run_step(f["cfg"], f["digest"])
    assert generated["success"] is True, generated
    assert "scene 0" not in generated["summary"]
    assert "scene 1" in generated["summary"] and "1 active scenes" in generated["summary"]
    assert [row["scene_id"] for row in generated["provenance"]["source_artifact_versions"]] == ["canonical-1"]
    assert f["client"].get(f"/api/summary/video/{f['digest']}").json()["summary"] == generated["summary"]


def test_summary_graph_counts_and_cooccurrence_ignore_retired_media(scene_library):
    f = scene_library
    assert f["client"].get("/api/summary/dashboard").status_code == 200
    f["retire"]()
    dashboard = f["client"].get("/api/summary/dashboard")
    assert dashboard.status_code == 200, dashboard.text
    assert [row["name"] for row in dashboard.json()["people"]] == ["Shared person"]
    profile = f["client"].get("/api/summary/entity/person:Shared person")
    assert profile.status_code == 200, profile.text
    assert profile.json()["co_occurrences"] == []
    assert profile.json()["occurrence_count"] == 1


def test_actual_chronological_search_omits_retirement_before_projection_delivery(scene_library):
    f = scene_library
    endpoint = "/api/search/temporal"
    before = f["client"].post(endpoint, json={"grouping": "chronological"})
    assert before.status_code == 200, before.text
    assert len(before.json()["results"]) == 2
    f["retire"]()
    response = f["client"].post(endpoint, json={"grouping": "chronological"})
    assert response.status_code == 200, response.text
    assert [row["scene_id"] for row in response.json()["results"]] == ["canonical-1"]


def test_saved_collection_projects_survivors_without_editing_bookmarks(scene_library):
    from lib import summary_aggregator
    f = scene_library
    refs = [{"video_id": "sample", "scene_id": f"canonical-{i}"} for i in range(2)]
    summary_aggregator.add_collection(f["graph"], {"name": "Two windows", "scene_refs": refs})
    persisted = summary_aggregator._collections_file(f["graph"])
    before = persisted.read_bytes()
    assert f["client"].get("/api/summary/collections").json()[0]["scene_refs"] == refs
    f["retire"]()
    response = f["client"].get("/api/summary/collections")
    assert response.status_code == 200, response.text
    assert response.json()[0]["scene_refs"] == refs[1:]
    assert persisted.read_bytes() == before


@pytest.mark.parametrize("other_scope", ["epoch", "video"])
def test_other_retirement_scope_preserves_neighbors(scene_library, other_scope):
    f = scene_library
    f["retire"](**({"epoch": "other-epoch"} if other_scope == "epoch" else {"source_hash": "a" * 64}))
    assert len(f["client"].get("/api/videos/sample/scenes").json()) == 2


def test_legacy_numeric_timeline_matches_exact_retired_bounds(scene_library):
    f = scene_library
    temporal = json.loads(f["temporal"].read_text())
    for index, row in enumerate(temporal["segments"]):
        row["scene_id"] = index
    f["temporal"].write_text(json.dumps(temporal))
    f["retire"]()
    assert [row["scene_id"] for row in f["client"].get("/api/videos/sample/scenes").json()] == [1]
    assert f["client"].get("/api/media/video/sample/scene/0/frame/0").status_code == 404
    assert f["client"].get("/api/media/video/sample/scene/1/frame/0").content == b"frame 1"


def test_all_scenes_retired_hides_source_without_removing_bytes(scene_library):
    f = scene_library
    f["retire"](0)
    f["retire"](1)
    assert f["client"].get("/api/system/videos").json() == []
    assert f["client"].get("/api/media/video/sample/source").status_code == 404
    assert f["source"].read_bytes() == b"original source retained with both scenes"
    assert f["client"].get(f"/api/summary/video/{f['digest']}").status_code == 404


def test_actual_confirmed_retirement_with_pending_outbox_is_immediately_hidden(scene_promotion, monkeypatch):
    from api.routes import scenes
    from api.utils import loaders

    root, cfg, authority, scope, ids = prepare(scene_promotion, monkeypatch)
    directory = root / "processing/three_windows"
    manifest = json.loads((directory / "video/scene_manifest.json").read_text())
    (directory / "temporal_index.json").write_text(json.dumps({
        "video_id": scope["video_hash"], "video_hash": scope["video_hash"], "segments": manifest["scenes"],
    }))
    for key in ("_DEFAULT_PROCESSING_ROOT", "_DEFAULT_PROCESSED_ROOT", "_DEFAULT_UCF_SCOPE"):
        monkeypatch.setattr(loaders, key, None)
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", ())
    loaders.configure_from_cfg(cfg)
    monkeypatch.setattr(scenes, "_data_loader", None)
    app = FastAPI()
    app.include_router(scenes.router)
    client = TestClient(app)
    assert len(client.get("/api/videos/three_windows/scenes").json()) == 3
    monkeypatch.setattr(authority, "_dematerialize_scene_views", lambda _: (_ for _ in ()).throw(RuntimeError("interrupted delivery")))
    result, rc = confirmed(authority, "supersede_ucf_frames", {**scope, "scene_id": ids[1]})
    assert rc == 1 and result["output"]["ledger_retirement_committed"] is True, result
    with closing(sqlite3.connect(root / "memory.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenes").fetchone() == (3,)
    assert [row["scene_id"] for row in client.get("/api/videos/three_windows/scenes").json()] == [ids[0], ids[2]]
    assert client.get(f"/api/videos/three_windows/scenes/{ids[1]}").status_code == 404
