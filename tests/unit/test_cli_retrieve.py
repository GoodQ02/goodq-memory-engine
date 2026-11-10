"""Public retrieval callers must retain vector identity and UCF visibility."""

import csv
import hashlib
import json
import sqlite3
import sys

import faiss
import numpy as np
import pytest

from cli import retrieve


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    epoch = tmp_path / "epoch_retrieve"
    epoch.mkdir()
    ledger = epoch / "ucf" / "ucf_ledger.db"
    ledger.parent.mkdir()
    database = epoch / "memory.db"
    index_path = epoch / "text.index"
    with sqlite3.connect(database) as con:
        con.executescript("""
            CREATE TABLE embeddings (
                hash TEXT, faiss_id INTEGER, source_path TEXT, modality TEXT,
                scene_id TEXT, PRIMARY KEY(hash, modality)
            );
            CREATE TABLE scenes (
                id TEXT PRIMARY KEY, video_hash TEXT, start REAL, end REAL, meta TEXT
            );
            CREATE TABLE links (parent_hash TEXT, child_hash TEXT, relation TEXT);
            CREATE TABLE ucf_provenance_mapping (
                record_type TEXT, record_id TEXT, ucf_frame_id INTEGER,
                PRIMARY KEY(record_type, record_id, ucf_frame_id)
            );
        """)
    with sqlite3.connect(ledger) as con:
        con.execute("""CREATE TABLE context_frames (
            frame_id INTEGER PRIMARY KEY, epoch_id TEXT, video_hash TEXT,
            source_artifact_id TEXT, vector_key TEXT, payload TEXT,
            promotion_status TEXT
        )""")
    cfg = {"paths": {"db_dir": str(epoch), "db_path": str(database),
                     "faiss_index_path": str(index_path)},
           "qdrant": {"enabled": False}, "ingestion_isolation": True}
    monkeypatch.setattr(retrieve, "_load_cfg", lambda: cfg)
    monkeypatch.setattr(retrieve, "_embed_query", lambda text: (
        np.array([[0.0, 0.0]], dtype="float32"), np
    ))

    def seed(entries):
        """Input order is vector rank; SQLite insertion deliberately reverses it."""
        index = faiss.IndexIDMap2(faiss.IndexFlatL2(2))
        index.add_with_ids(
            np.array([[n + 1, 0] for n in range(len(entries))], dtype="float32"),
            np.array([e["id"] for e in entries], dtype="int64"),
        )
        faiss.write_index(index, str(index_path))
        with sqlite3.connect(database) as mem, sqlite3.connect(ledger) as ucf:
            for entry in reversed(entries):
                fid = entry["id"]
                key = entry.get("key", f"embedding-{fid}")
                scene = entry.get("scene", f"scene-hash-{fid}")
                video = entry.get("video", f"video-{fid}")
                path = str(tmp_path / f"source-{fid}.jpg")
                if entry.get("mapped", True):
                    mem.execute("INSERT INTO embeddings VALUES (?, ?, ?, ?, ?)",
                                (key, fid, path, entry.get("modality", "text"), scene))
                    mem.execute("INSERT OR IGNORE INTO scenes VALUES (?, ?, ?, ?, ?)",
                                (scene, video, fid, fid + 1, '{"scene_id":"scene_0000"}'))
                if entry.get("ledger", True):
                    ucf.execute("INSERT INTO context_frames VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (fid, entry.get("epoch", epoch.name), video,
                                 entry.get("ucf_scene", scene), entry.get("vector_key", key),
                                 json.dumps(entry.get("payload", {})),
                                 entry.get("status", "promoted")))
        return entries

    return cfg, seed, database, ledger, index_path


def run_caller(monkeypatch, capsys, caller, topk=10, extra=()):
    if caller == "programmatic":
        return retrieve.search_text_index("known query", topk)
    monkeypatch.setattr(sys, "argv", ["cli.retrieve", "--text", "known query",
                                     "--topk", str(topk), *extra])
    retrieve.main()
    output = capsys.readouterr().out
    return output if "--print-paths" in extra else json.loads(output)


@pytest.mark.parametrize("caller", ["cli", "programmatic"])
def test_vector_scores_stay_with_ranked_rows_and_missing_mapping(
    corpus, monkeypatch, capsys, caller
):
    _, seed, database, ledger, index = corpus
    seed([{"id": 30}, {"id": 20, "mapped": False}, {"id": 10}])
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (database, ledger, index)}
    matches = run_caller(monkeypatch, capsys, caller, 2)["matches"]
    assert [(m["source_path"].split("source-")[-1], m["score"]) for m in matches] == [
        ("30.jpg", 1.0), ("10.jpg", 9.0)
    ]
    assert [m["scene"]["scene_id"] for m in matches] == ["scene-hash-30", "scene-hash-10"]
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}


@pytest.mark.parametrize("caller", ["cli", "programmatic"])
def test_only_exact_promoted_evidence_counts_toward_topk(corpus, monkeypatch, capsys, caller):
    _, seed, _, _, _ = corpus
    entries = [{"id": i, "status": "staged"} for i in range(1, 13)]
    entries += [{"id": 13, "status": "validated"}, {"id": 14, "status": "rejected"},
                {"id": 15, "status": "superseded"}, {"id": 16, "epoch": "other_epoch"},
                {"id": 17, "ledger": False}, {"id": 18, "ucf_scene": "other-scene"}]
    entries += [{"id": i, "modality": "audio_transcript" if i % 2 else "text"}
                for i in range(19, 32)]
    seed(entries)
    matches = run_caller(monkeypatch, capsys, caller, 13)["matches"]
    assert len(matches) == 13
    assert [m["score"] for m in matches] == [float(i * i) for i in range(19, 32)]
    assert [m["scene"]["video_hash"] for m in matches] == [f"video-{i}" for i in range(19, 32)]


@pytest.mark.parametrize("caller", ["cli", "programmatic"])
def test_original_embedding_identity_is_governed_even_when_vector_key_is_normalized(
    corpus, monkeypatch, capsys, caller
):
    _, seed, _, _, _ = corpus
    seed([{"id": 1, "key": "scene-hash-1_summary", "vector_key": "normalized-qdrant-id",
           "payload": {"embedding_id": "scene-hash-1_summary"}}])
    result = run_caller(monkeypatch, capsys, caller)["matches"]
    assert len(result) == 1
    assert result[0]["scene"]["scene_id"] == "scene-hash-1"


@pytest.mark.parametrize("caller", ["cli", "programmatic"])
@pytest.mark.parametrize("isolated", [True, False])
def test_governed_ledger_missing_is_not_reported_as_success(corpus, monkeypatch, capsys, caller, isolated):
    cfg, seed, _, ledger, _ = corpus
    cfg["ingestion_isolation"] = isolated
    seed([{"id": 1}])
    ledger.unlink()
    with pytest.raises((FileNotFoundError, RuntimeError), match="ledger"):
        run_caller(monkeypatch, capsys, caller)
    assert not ledger.exists()


@pytest.mark.parametrize("caller", ["cli", "programmatic"])
def test_corrupt_ledger_is_not_reported_as_empty_success(corpus, monkeypatch, capsys, caller):
    _, seed, _, ledger, _ = corpus
    seed([{"id": 1}])
    ledger.write_bytes(b"not a SQLite ledger")
    with pytest.raises(sqlite3.DatabaseError):
        run_caller(monkeypatch, capsys, caller)


@pytest.mark.parametrize("caller", ["cli", "programmatic"])
def test_missing_mapping_database_is_not_reported_as_empty_success(corpus, monkeypatch, capsys, caller):
    _, seed, database, _, _ = corpus
    seed([{"id": 1}])
    database.unlink()
    with pytest.raises(FileNotFoundError, match="memory database"):
        run_caller(monkeypatch, capsys, caller)
    assert not database.exists()


@pytest.mark.parametrize("caller", ["cli", "programmatic"])
def test_another_promoted_embedding_does_not_authorize_staged_row(corpus, monkeypatch, capsys, caller):
    _, seed, _, _, _ = corpus
    seed([{"id": 1, "status": "staged", "scene": "same-scene", "video": "same-video"},
          {"id": 2, "scene": "same-scene", "video": "same-video"}])
    matches = run_caller(monkeypatch, capsys, caller)["matches"]
    assert len(matches) == 1
    assert matches[0]["score"] == 4.0


@pytest.mark.parametrize("caller", ["cli", "programmatic"])
def test_materialized_text_alias_does_not_duplicate_audio_hit(corpus, monkeypatch, capsys, caller):
    _, seed, database, _, _ = corpus
    seed([{"id": 1, "modality": "audio_transcript"}, {"id": 2}])
    with sqlite3.connect(database) as con:
        con.execute("INSERT INTO embeddings SELECT hash, faiss_id, '', 'text', scene_id "
                    "FROM embeddings WHERE faiss_id=1")
    matches = run_caller(monkeypatch, capsys, caller, 2)["matches"]
    assert [m["score"] for m in matches] == [1.0, 4.0]
    assert matches[0]["source_path"].endswith("source-1.jpg")


@pytest.mark.parametrize("caller", ["cli", "programmatic"])
def test_explicit_legacy_database_keeps_frame_link_compatibility(corpus, monkeypatch, capsys, caller):
    cfg, seed, database, ledger, _ = corpus
    seed([{"id": 1, "modality": "frame_text"}])
    cfg["paths"].pop("db_dir")
    cfg["ingestion_isolation"] = False
    ledger.unlink()
    path = database.parent / "legacy.jpg"
    path.write_bytes(b"legacy frame fixture")
    with sqlite3.connect(database) as con:
        con.execute("UPDATE embeddings SET source_path=?, scene_id=NULL", (str(path),))
        con.execute("INSERT INTO links VALUES (?, ?, 'keyframe_of')",
                    ("scene-hash-1", hashlib.sha256(path.read_bytes()).hexdigest()))
    matches = run_caller(monkeypatch, capsys, caller)["matches"]
    assert matches[0]["scene"]["video_hash"] == "video-1"


def test_cli_csv_and_print_paths_use_the_same_ranked_projection(corpus, monkeypatch, capsys, tmp_path):
    _, seed, _, _, _ = corpus
    seed([{"id": 30}, {"id": 10}])
    output = tmp_path / "matches.csv"
    assert run_caller(monkeypatch, capsys, "cli", 2, ("--csv", str(output))) == {
        "matches": 2, "csv": str(output)
    }
    with output.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [(row["score"], row["scene_start"]) for row in rows] == [("1.0", "30.0"), ("4.0", "10.0")]
    paths = run_caller(monkeypatch, capsys, "cli", 2, ("--print-paths",)).splitlines()
    assert paths == [row["source_path"] for row in rows]


def test_programmatic_qdrant_requests_promoted_evidence(corpus, monkeypatch):
    cfg, _, database, _, _ = corpus
    from steps.common import qdrant_client

    with sqlite3.connect(database) as con:
        con.execute("INSERT INTO scenes VALUES ('exact-scene', 'video', 4, 6, '{}')")

    class Client:
        def query(self, vector, **kwargs):
            assert kwargs["payload_filter"] == {"must": [
                {"key": "ucf_promotion_status", "match": {"value": "promoted"}},
                {"key": "epoch_id", "match": {"value": "epoch_retrieve"}},
            ]}
            assert kwargs["retrieval_context"] == "human.cli.retrieve"
            return [{"score": 0.75, "payload": {"scene_id": "exact-scene",
                     "video_hash": "video", "modality": "text", "source_path": "frame.jpg"}}]

    monkeypatch.setattr(qdrant_client, "build_qdrant_client", lambda *a, **kw: Client())
    result = retrieve.search_text_index("known query", 1)["matches"]
    assert result[0]["score"] == 0.75
    assert result[0]["scene"]["scene_id"] == "exact-scene"
