"""Use real summary routes, the template worker and separate SQLite stores."""
from __future__ import annotations

import copy
from contextlib import closing
import json
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.routes import summary as summary_route
from tests.unit.test_summary_routes import StubSummaryAuthority


VIDEO_HASH = "a" * 64


@pytest.fixture
def summary_runtime(tmp_path, monkeypatch):
    memory = tmp_path / "memory.db"
    graph = tmp_path / "knowledge_graph.db"
    with sqlite3.connect(memory) as db:
        db.executescript("""
            CREATE TABLE scenes (id TEXT PRIMARY KEY, video_hash TEXT,
                start REAL, end REAL, meta TEXT, created_at TEXT);
            CREATE TABLE summaries (id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_type TEXT, category TEXT, content TEXT, created_at TEXT);
        """)
        db.execute("INSERT INTO scenes VALUES (?,?,?,?,?,?)", (
            "target-scene", VIDEO_HASH, 0, 10,
            json.dumps({"video_path": "fixture.mp4", "transcript": "A bounded scene"}),
            "2026-10-08"))
    with sqlite3.connect(graph) as db:
        db.execute("CREATE TABLE nodes (id TEXT PRIMARY KEY)")
    cfg = {
        "ingestion_isolation": True,
        "paths": {"data_root": str(tmp_path / "GoodQ_Data"),
                  "db_path": str(memory), "knowledge_graph_db": str(graph)},
        "llm": {"features": {"video_summarization": False}},
    }
    monkeypatch.setattr("steps.common.config_loader.load_configs", lambda *_a, **_kw: cfg)
    authority = StubSummaryAuthority()
    monkeypatch.setattr(summary_route, "_get_summary_authority", lambda _cfg: authority)
    app = FastAPI()
    app.include_router(summary_route.router)
    return TestClient(app), cfg, memory, graph, authority


def _stored(memory):
    with sqlite3.connect(memory) as db:
        return [json.loads(row[0]) for row in db.execute(
            "SELECT content FROM summaries WHERE category='video_summary'")]


def _prepare_and_confirm(client):
    endpoint = f"/api/summary/video/{VIDEO_HASH}/generate"
    prepared = client.post(endpoint, json={"action": "prepare"})
    assert prepared.status_code == 200
    payload = prepared.json()
    confirmed = client.post(endpoint, json={
        "action": "confirm", "job_id": payload["job"]["job_id"],
        "confirmation_token": payload["confirmation_token"],
    })
    assert confirmed.status_code == 202
    return payload["job"]["job_id"]


def test_confirmed_summary_persists_under_governed_ingestion(summary_runtime):
    client, cfg, memory, graph, authority = summary_runtime
    original_cfg = copy.deepcopy(cfg)
    graph_before = graph.read_bytes()
    prepared = client.post(f"/api/summary/video/{VIDEO_HASH}/generate", json={"action": "prepare"})
    assert prepared.status_code == 200
    assert _stored(memory) == []
    payload = prepared.json()
    confirmed = client.post(f"/api/summary/video/{VIDEO_HASH}/generate", json={
        "action": "confirm", "job_id": payload["job"]["job_id"],
        "confirmation_token": payload["confirmation_token"],
    })
    assert confirmed.status_code == 202
    status = client.get(f"/api/summary/video/{VIDEO_HASH}/status").json()
    assert status["status"] == "succeeded"
    persisted = _stored(memory)
    assert len(persisted) == 1
    assert persisted[0]["video_hash"] == VIDEO_HASH
    assert persisted[0]["method"] == "template"
    response = client.get(f"/api/summary/video/{VIDEO_HASH}")
    assert response.status_code == 200
    assert response.json()["summary"] == persisted[0]["summary"]
    assert response.json()["summary"]
    assert cfg == original_cfg
    assert graph.read_bytes() == graph_before
    assert authority.external_calls[-1]["side_effect_report"]["mutated"] is True


def test_summary_storage_failure_is_not_success(summary_runtime):
    client, cfg, memory, _graph, authority = summary_runtime
    with sqlite3.connect(memory) as db:
        db.executescript("""CREATE TRIGGER reject_summary BEFORE INSERT ON summaries
            BEGIN SELECT RAISE(FAIL, 'fixture storage failure'); END;""")
    _prepare_and_confirm(client)
    status = client.get(f"/api/summary/video/{VIDEO_HASH}/status").json()
    assert status["status"] == "failed"
    assert status["job"]["outcome"]["code"] == "summary_generation_failed"
    assert _stored(memory) == []
    assert cfg["ingestion_isolation"] is True
    assert authority.external_calls[-1]["side_effect_report"]["mutated"] is False


def test_existing_scene_without_summary_uses_memory_database(summary_runtime):
    client, _cfg, _memory, _graph, _authority = summary_runtime
    response = client.get(f"/api/summary/video/{VIDEO_HASH}")
    assert response.status_code == 200
    assert response.json()["method"] == "none"


def test_regenerated_summary_readback_returns_latest_content(summary_runtime):
    client, _cfg, memory, _graph, _authority = summary_runtime
    _prepare_and_confirm(client)
    first = client.get(f"/api/summary/video/{VIDEO_HASH}").json()["summary"]
    with sqlite3.connect(memory) as db:
        db.execute("UPDATE scenes SET end=20 WHERE video_hash=?", (VIDEO_HASH,))
    _prepare_and_confirm(client)
    summaries = _stored(memory)
    assert len(summaries) == 2
    assert summaries[0]["summary"] != summaries[1]["summary"]
    latest = client.get(f"/api/summary/video/{VIDEO_HASH}").json()["summary"]
    assert latest == summaries[-1]["summary"]
    assert latest != first


def test_summary_prepare_does_not_create_missing_memory_database(summary_runtime):
    client, cfg, memory, _graph, _authority = summary_runtime
    missing = memory.parent / "absent.db"
    cfg["paths"]["db_path"] = str(missing)
    response = client.post(f"/api/summary/video/{VIDEO_HASH}/generate", json={"action": "prepare"})
    assert response.status_code == 404
    assert not missing.exists()


def test_summary_removed_during_generation_fails_without_orphan(summary_runtime, monkeypatch):
    client, cfg, memory, _graph, authority = summary_runtime
    from steps.video_summarizer import step

    original = step.generate_video_summary_template

    def remove_active_scope_during_generation(*args):
        text = original(*args)
        with closing(sqlite3.connect(memory)) as db, db:
            db.execute("DELETE FROM scenes WHERE video_hash=?", (VIDEO_HASH,))
            db.execute("DELETE FROM summaries WHERE category='video_summary'")
        return text

    monkeypatch.setattr(step, "generate_video_summary_template", remove_active_scope_during_generation)
    _prepare_and_confirm(client)

    status = client.get(f"/api/summary/video/{VIDEO_HASH}/status").json()
    assert status["status"] == "failed"
    assert status["job"]["outcome"]["code"] == "summary_generation_failed"
    assert authority.external_calls[-1]["side_effect_report"]["mutated"] is False
    assert _stored(memory) == []
    assert client.get(f"/api/summary/video/{VIDEO_HASH}").status_code == 404
    assert cfg["ingestion_isolation"] is True


@pytest.mark.parametrize("existing_summary", ["generated", "historical"])
def test_summary_read_hides_rows_without_active_scene(summary_runtime, existing_summary):
    client, _cfg, memory, graph, _authority = summary_runtime
    if existing_summary == "generated":
        _prepare_and_confirm(client)
    else:
        with closing(sqlite3.connect(memory)) as db, db:
            db.execute(
                "INSERT INTO summaries (summary_type, category, content) VALUES (?,?,?)",
                ("video", "video_summary", json.dumps({"video_hash": VIDEO_HASH,
                    "summary": "Historical orphan"})),
            )
    with closing(sqlite3.connect(memory)) as db, db:
        db.execute("DELETE FROM scenes WHERE video_hash=?", (VIDEO_HASH,))
    retained = _stored(memory)
    graph_before = graph.read_bytes()

    assert client.get(f"/api/summary/video/{VIDEO_HASH}").status_code == 404
    assert _stored(memory) == retained
    assert graph.read_bytes() == graph_before


def test_summary_read_active_scene_database_error_is_observable(summary_runtime, caplog):
    client, _cfg, memory, _graph, _authority = summary_runtime
    _prepare_and_confirm(client)
    with closing(sqlite3.connect(memory)) as db, db:
        db.execute("DROP TABLE scenes")

    response = client.get(f"/api/summary/video/{VIDEO_HASH}")

    assert response.status_code == 500
    assert response.json()["detail"] == "Database query failed"
    assert "no such table: scenes" in caplog.text


def test_summary_active_recheck_holds_write_lock_until_insert(summary_runtime, monkeypatch):
    client, _cfg, memory, _graph, _authority = summary_runtime
    from steps.video_summarizer import step

    real_connect = sqlite3.connect
    original = step.generate_video_summary_template
    generation_finished = False
    competing_writes = []

    def mark_generated(*args):
        nonlocal generation_finished
        text = original(*args)
        generation_finished = True
        return text

    def tracked_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        if generation_finished and str(args[0]) == str(memory):
            def trace(statement):
                if statement.startswith("SELECT id FROM scenes WHERE video_hash="):
                    with closing(real_connect(memory, timeout=0)) as competitor:
                        try:
                            competitor.execute("DELETE FROM scenes WHERE video_hash=?", (VIDEO_HASH,))
                        except sqlite3.OperationalError as exc:
                            competing_writes.append(str(exc))
                        else:
                            competing_writes.append("unexpectedly writable")
                        finally:
                            competitor.rollback()
            conn.set_trace_callback(trace)
        return conn

    monkeypatch.setattr(step, "generate_video_summary_template", mark_generated)
    monkeypatch.setattr(sqlite3, "connect", tracked_connect)
    _prepare_and_confirm(client)

    assert competing_writes == ["database is locked"]
    assert len(_stored(memory)) == 1
    # The worker released its lock; a later removal can now commit normally.
    with closing(real_connect(memory, timeout=0)) as db, db:
        db.execute("DELETE FROM scenes WHERE video_hash=?", (VIDEO_HASH,))
        db.execute("DELETE FROM summaries WHERE category='video_summary'")
    assert _stored(memory) == []
