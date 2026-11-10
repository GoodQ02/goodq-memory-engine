"""Retained cue visibility must cross the real Summary read boundary safely."""
import hashlib
import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def cue_library(tmp_path, monkeypatch):
    from api.routes import summary
    from api.utils.loaders import DataLoader
    from api.route_effects import ROUTE_EFFECTS, install_route_effect_authority
    from lib.knowledge_graph import KnowledgeGraph
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    root = tmp_path / "epoch-cues"
    directory = root / "processing/source"
    directory.mkdir(parents=True)
    source = "a" * 64
    records = []
    ledger_path = root / "ucf/ucf_ledger.db"
    ledger_path.parent.mkdir()
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    frames = []
    graph = root / "knowledge_graph.db"
    with KnowledgeGraph(str(graph)) as kg:
        for i in range(2):
            start, end = i * 10, (i + 1) * 10
            sid = hashlib.sha256(f"scene{source}|{start:.3f}|{end:.3f}|".encode()).hexdigest()
            fid = ledger.log_frame(video_hash=source, epoch_id=root.name, run_id="fixture",
                                   t_start=start, t_end=end, modality="audio",
                                   worker_name="audio_transcribe", model_tag="fixture",
                                   source_artifact_id=sid, promotion_status="promoted")
            frames.append(fid)
            node = kg.add_node("scene", sid, {"ucf_provenance": [fid]})
            media = kg.add_media_node("video_scene", "source.mp4", scene_id=sid,
                                     timestamp_start=start, timestamp_end=end)
            kg.link_node_to_media(node, media)
            records.append({"scene_id": sid, "start": start, "end": end,
                            "music_events": [{"label": "birthday_song", "context": "Happy birthday",
                                              "start": 0, "end": 2, "confidence": .7}]})
        records[0]["music_events"].append({"label": "birthday_song", "context": "Again",
                                           "start": 4, "end": 6, "confidence": .7})
    ledger.close()
    temporal = directory / "temporal_index.json"
    payload = {"video_hash": source, "video_id": source, "segments": records}
    temporal.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(summary, "_get_kg_db_path", lambda: graph)
    monkeypatch.setattr(summary, "_data_loader", DataLoader(processing_root=str(directory.parent)))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    paths = {"/api/summary/dashboard", "/api/summary/entity/{entity_id:path}"}
    app.router.routes.extend(r for r in summary.router.routes if r.path in paths)
    install_route_effect_authority(app, registry={(m, r.path): ROUTE_EFFECTS[(m, r.path)]
                                                  for r in app.routes for m in r.methods})
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        yield dict(client=client, root=root, graph=graph, ledger=ledger_path,
                   temporal=temporal, payload=payload, records=records, frames=frames, source=source)


def cue_rows(f):
    response = f["client"].get("/api/summary/dashboard")
    assert response.status_code == 200, response.text
    return [r for r in response.json()["occasions"] if r["entity_id"].startswith("transcript_cue:")]


def test_summary_cue_dashboard_profile_and_repeated_reads(cue_library):
    f = cue_library
    before = {p: p.read_bytes() for p in (f["graph"], f["ledger"], f["temporal"])}
    # Duplicate scene rows/aliases do not multiply occurrences or playlist entries.
    f["payload"]["segments"].append(f["records"][0])
    f["temporal"].write_text(json.dumps(f["payload"]), encoding="utf-8")
    before[f["temporal"]] = f["temporal"].read_bytes()
    for _ in range(2):
        rows = cue_rows(f)
        assert len(rows) == 1
        assert (rows[0]["occurrence_count"], rows[0]["scene_count"]) == (3, 2)
        assert rows[0]["source"] == "retained_transcript_pattern"
        assert rows[0]["confidence"] is None
        response = f["client"].get("/api/summary/entity/transcript_cue:birthday_song")
        assert response.status_code == 200
        profile = response.json()
        assert profile["scene_count"] == 2 and profile["occurrence_count"] == 3
        assert {s["scene_id"] for s in profile["scenes"]} == {r["scene_id"] for r in f["records"]}
        assert profile["scenes"][0]["music_events"] == f["records"][0]["music_events"]
        assert profile["scenes"][0]["source_sha256"] == f["source"]
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize("fault", ["staged", "rejected", "wrong_epoch", "wrong_source",
                                  "missing_ledger", "unlinked_graph", "wrong_bounds", "wrong_id"])
def test_summary_cues_require_materialized_promoted_scene_authority(cue_library, fault):
    f = cue_library
    if fault == "missing_ledger":
        f["ledger"].unlink()
    elif fault in {"staged", "rejected", "wrong_epoch", "wrong_source"}:
        column, value = {"staged": ("promotion_status", "staged"),
                         "rejected": ("promotion_status", "rejected"),
                         "wrong_epoch": ("epoch_id", "foreign"),
                         "wrong_source": ("video_hash", "b" * 64)}[fault]
        with sqlite3.connect(f["ledger"]) as conn:
            conn.execute(f"UPDATE context_frames SET {column}=?", (value,))
    elif fault == "unlinked_graph":
        with sqlite3.connect(f["graph"]) as conn:
            conn.execute("DELETE FROM node_media")
    else:
        for row in f["records"]:
            row["end"] += 1 if fault == "wrong_bounds" else 0
            if fault == "wrong_id":
                row["scene_id"] = "foreign-scene"
        f["temporal"].write_text(json.dumps(f["payload"]), encoding="utf-8")
    assert cue_rows(f) == []
    assert f["client"].get("/api/summary/entity/transcript_cue:birthday_song").status_code == 404


def test_retirement_excludes_cue_before_graph_delivery(cue_library):
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    f = cue_library
    scene = f["records"][0]
    evidence = {"kind": "scene_retirement", "version": 1, "scene_id": scene["scene_id"],
                "aliases": [scene["scene_id"]], "video_hash": f["source"],
                "epoch_id": f["root"].name, "start": scene["start"], "end": scene["end"],
                "frame_ids": [f["frames"][0]], "vectors": []}
    with sqlite3.connect(f["ledger"]) as conn:
        UCFLedgerClient.insert_status_transition(conn, old_status="promoted", new_status="rejected",
            tool_name="ucf_retire_scene", video_hash=f["source"], epoch_id=f["root"].name,
            scope=f"scene_retirement:{scene['scene_id']}", evidence=evidence, frame_ids=[f["frames"][0]])
    rows = cue_rows(f)
    assert (rows[0]["occurrence_count"], rows[0]["scene_count"]) == (1, 1)
    result = f["client"].get("/api/summary/entity/transcript_cue:birthday_song").json()
    assert [s["scene_id"] for s in result["scenes"]] == [f["records"][1]["scene_id"]]


def test_empty_and_legacy_cues_are_not_promoted_event_claims(cue_library):
    f = cue_library
    f["records"][0]["music_events"] = []
    f["records"][1]["music_events"] = ["singing"]
    f["temporal"].write_text(json.dumps(f["payload"]), encoding="utf-8")
    rows = cue_rows(f)
    assert len(rows) == 1 and rows[0]["name"] == "singing"
    profile = f["client"].get("/api/summary/entity/transcript_cue:singing").json()
    assert profile["scenes"][0]["music_events"] == ["singing"]
