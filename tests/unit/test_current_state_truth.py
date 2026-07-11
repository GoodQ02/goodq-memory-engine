from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from scripts.docs import build_current_state as current_state
from scripts.docs.build_current_state import (
    capture_evidence,
    extract_config_authority,
    project_current_state_json,
    read_sqlite_evidence,
    render_current_state_markdown,
    render_rag_context_pack,
    verify_projection_files,
)


EPOCH_ID = "epoch_2026_07_05_home_memory_clean_01"


def _seal_evidence(value):
    sealed = copy.deepcopy(value)
    sealed.pop("evidence_id", None)
    canonical = json.dumps(
        sealed,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    sealed["evidence_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return sealed


@pytest.fixture
def evidence():
    collections = {
        modality: {
            "name": f"goodq_{modality}_{EPOCH_ID}",
            "points_count": count,
            "dimensions": dim,
            "status": "green",
        }
        for modality, count, dim in (
            ("audio", 1453, 512),
            ("clip", 2913, 768),
            ("dino", 2913, 1024),
            ("text", 4292, 384),
        )
    }
    return _seal_evidence({
        "schema_version": 1,
        "captured_at_utc": "2026-07-11T12:19:07Z",
        "authority": {
            "epoch_id": EPOCH_ID,
            "profile": "GPU_ENHANCED",
            "config_source": "sanitized_resolved_config",
        },
        "completion": {
            "media_sources": 12,
            "distinct_videos": 12,
            "context_frames": 75094,
            "promotion_status": {"promoted": 75094},
            "processed_media": 12,
            "import_inbox_media": 0,
            "failed_media": 0,
        },
        "persistence": {
            "memory": {"scenes": 1648, "segments": 16535, "embeddings": 8736, "links": 42800},
            "knowledge_graph": {"nodes": 93293, "edges": 1928045, "events": 0},
            "ucf": {"transitions": 1, "validated_transitions": 1},
            "qdrant": {"state": "running_loopback", "collections": collections},
            "faiss": {"indexes": 4},
        },
        "configured_runtime": {
            "api": {"endpoint": "http://127.0.0.1:30000", "loopback_only": True},
            "qdrant": {"endpoint": "http://127.0.0.1:6333", "loopback_only": True},
            "vllm": {
                "endpoint": None,
                "location": "non_loopback_configured",
                "model": "Qwen2.5-0.5B-Instruct",
            },
            "ollama": {"endpoint": "http://127.0.0.1:11434/v1", "model": "llama3.2:latest"},
        },
        "observed_services": {
            "goodq_api": {"state": "stopped"},
            "qdrant": {"state": "running_loopback"},
            "vllm": {"state": "stopped_or_unavailable"},
            "ollama": {"state": "reachable", "loaded_models": []},
            "wsl": {"state": "not_probed", "reason": "passive audit does not start WSL"},
        },
        "limitations": [
            "Service observations are a point-in-time snapshot.",
            "Historical lifecycle events were not reconstructed.",
        ],
        "historical_evidence": [
            {"label": "June family-film pilot", "path": "docs/agent/UCF_CLEAN_REINGEST_VERIFICATION_REPORT.md"},
            {"label": "July promotion witness", "path": "docs/agent/birth_certificate.md"},
        ],
    })


def test_human_json_and_rag_render_from_one_evidence_source(evidence):
    markdown = render_current_state_markdown(evidence)
    projection = project_current_state_json(evidence)
    rag = render_rag_context_pack(evidence)

    for rendered in (markdown, json.dumps(projection, sort_keys=True), rag):
        assert evidence["evidence_id"] in rendered
        assert evidence["captured_at_utc"] in rendered
        assert EPOCH_ID in rendered

    assert projection["completion"]["context_frames"] == 75094
    assert projection["observed_services"]["goodq_api"]["state"] == "stopped"
    assert "5/12" not in markdown
    assert "actively ingesting" not in markdown.lower()
    assert "epoch_2026_06_21_family_clean_01" not in rag
    assert f"goodq_text_{EPOCH_ID}" in rag
    assert "configured" in markdown.lower()
    assert "observed" in markdown.lower()
    assert "## Next Work" not in markdown
    assert "R-20" not in markdown
    assert "redacted (non-loopback configured)" in markdown
    assert "`None`" not in markdown
    assert "| Processed media | 12 |" in markdown
    assert "| Import inbox media | 0 |" in markdown
    assert "| Failed media | 0 |" in markdown


def test_tampered_evidence_is_rejected_before_projection(evidence, tmp_path):
    tampered = copy.deepcopy(evidence)
    tampered["completion"]["context_frames"] += 1

    with pytest.raises(ValueError, match="evidence_id"):
        current_state.validate_evidence(tampered)
    with pytest.raises(ValueError, match="evidence_id"):
        render_current_state_markdown(tampered)
    with pytest.raises(ValueError, match="evidence_id"):
        verify_projection_files(
            tampered,
            tmp_path / "CURRENT_STATE.md",
            tmp_path / "current_state.json",
            tmp_path / "GOODQ_RAG_CONTEXT_PACK.md",
        )


def test_partial_lifecycle_never_renders_complete_or_promoted_claim(evidence):
    partial = copy.deepcopy(evidence)
    partial["completion"]["context_frames"] = 5
    partial["completion"]["promotion_status"] = {"promoted": 4, "staged": 1}
    partial = _seal_evidence(partial)

    markdown = render_current_state_markdown(partial)
    rag = render_rag_context_pack(partial)

    assert "complete and promoted" not in markdown.lower()
    assert "complete and promoted" not in rag.lower()
    assert "not proven complete or fully promoted" in markdown.lower()
    assert "not proven complete or fully promoted" in rag.lower()


def test_projection_verifier_detects_drift(tmp_path, evidence):
    md_path = tmp_path / "CURRENT_STATE.md"
    json_path = tmp_path / "current_state.json"
    rag_path = tmp_path / "GOODQ_RAG_CONTEXT_PACK.md"
    md_path.write_text(render_current_state_markdown(evidence), encoding="utf-8")
    json_path.write_text(
        json.dumps(project_current_state_json(evidence), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rag_path.write_text(render_rag_context_pack(evidence), encoding="utf-8")

    assert verify_projection_files(evidence, md_path, json_path, rag_path) == []
    md_path.write_text("stale\n", encoding="utf-8")
    assert verify_projection_files(evidence, md_path, json_path, rag_path) == [str(md_path)]


def test_config_authority_fails_closed_on_epoch_or_collection_mismatch(tmp_path):
    epoch_root = _canonical_epoch_root(tmp_path)
    config = _test_config(epoch_root)

    authority = extract_config_authority(config, epoch_root)
    assert authority["epoch_id"] == EPOCH_ID
    assert authority["profile"] == "GPU_ENHANCED"
    assert authority["configured_runtime"]["vllm"]["model"] == "Qwen2.5-0.5B-Instruct"

    config["qdrant"]["collections"]["text"] = "goodq_text_epoch_wrong"
    with pytest.raises(ValueError, match="collection authority mismatch"):
        extract_config_authority(config, epoch_root)


def test_config_authority_requires_exact_epoch_root_and_loopback_control_plane(tmp_path):
    explicit_epoch = _canonical_epoch_root(tmp_path / "explicit")
    other_epoch = _canonical_epoch_root(tmp_path / "other")
    config = _test_config(other_epoch)

    with pytest.raises(ValueError, match="exactly match"):
        extract_config_authority(config, explicit_epoch)

    config = _test_config(explicit_epoch)
    config["api"]["host"] = "192.0.2.20"
    with pytest.raises(ValueError, match="GoodQ API.*loopback"):
        extract_config_authority(config, explicit_epoch)

    config = _test_config(explicit_epoch)
    config["qdrant"]["host"] = "http://192.0.2.21:6333"
    with pytest.raises(ValueError, match="Qdrant.*loopback"):
        extract_config_authority(config, explicit_epoch)


def test_runtime_queues_follow_canonical_goodq_data_topology(tmp_path):
    epoch_root = _canonical_epoch_root(tmp_path)
    config = _test_config(epoch_root)

    authority = extract_config_authority(config, epoch_root)
    data_root = epoch_root.parent.parent.resolve()
    assert authority["runtime_paths"] == {
        "processed": data_root / "processed",
        "import_inbox": data_root / "import_inbox",
        "failed": data_root / "failed",
    }

    config["paths"]["processed"] = str(epoch_root / "processed")
    with pytest.raises(ValueError, match="canonical GoodQ_Data queue"):
        extract_config_authority(config, epoch_root)


def test_nonloopback_optional_models_are_not_probed(monkeypatch):
    monkeypatch.setattr(
        current_state,
        "_http_json",
        lambda *_args, **_kwargs: pytest.fail("non-loopback endpoint was contacted"),
    )

    assert current_state._probe_openai_models("http://192.0.2.25:38005/v1") == {
        "state": "not_probed_non_loopback",
        "models": [],
    }
    assert current_state._probe_ollama("http://192.0.2.26:11434/v1") == {
        "state": "not_probed_non_loopback",
        "loaded_models": [],
    }
    assert current_state._probe_tcp("http://192.0.2.27:30000") == {
        "state": "not_probed_non_loopback"
    }


def test_http_json_bypasses_ambient_proxy_and_refuses_redirect(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "http://192.0.2.99/escape")
                self.end_headers()
                return
            payload = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert current_state._http_json(f"{base}/ok") == (200, {"ok": True})
        with pytest.raises(urllib.error.HTTPError) as redirect:
            current_state._http_json(f"{base}/redirect")
        assert redirect.value.code == 302
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_sqlite_evidence_is_immutable_and_rejects_nonempty_wal(tmp_path):
    db_path = tmp_path / "memory.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE scenes (id TEXT)")
    connection.executemany("INSERT INTO scenes(id) VALUES (?)", [("a",), ("b",)])
    connection.commit()
    connection.close()
    before = db_path.read_bytes()

    evidence = read_sqlite_evidence(db_path, ("scenes",))
    assert evidence["tables"] == {"scenes": 2}
    assert db_path.read_bytes() == before
    assert not Path(f"{db_path}-wal").exists()
    assert not Path(f"{db_path}-shm").exists()

    Path(f"{db_path}-wal").write_bytes(b"not-empty")
    with pytest.raises(RuntimeError, match="non-empty WAL"):
        read_sqlite_evidence(db_path, ("scenes",))

    Path(f"{db_path}-wal").unlink()
    Path(f"{db_path}-journal").write_bytes(b"not-empty")
    with pytest.raises(RuntimeError, match="rollback journal"):
        read_sqlite_evidence(db_path, ("scenes",))


def test_required_qdrant_capture_fails_closed_when_unreachable(monkeypatch):
    monkeypatch.setattr(
        current_state,
        "_http_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )

    with pytest.raises(RuntimeError, match="required Qdrant evidence"):
        current_state._capture_qdrant(
            "http://127.0.0.1:6333",
            _expected_test_collections(),
            {"audio": 512, "clip": 768, "dino": 1024, "text": 384},
        )


def test_qdrant_dimensions_come_from_observed_collection_detail(monkeypatch):
    collections = _expected_test_collections()

    def fake_http(url, *, method="GET", body=None, **_kwargs):
        if url.endswith("/collections"):
            return 200, {
                "result": {"collections": [{"name": name} for name in collections.values()]}
            }
        if url.endswith("/points/scroll"):
            return 200, {"result": {"points": [{"id": "point"}]}}
        modality = next(key for key, name in collections.items() if url.endswith(f"/{name}"))
        observed = {"audio": 512, "clip": 768, "dino": 1024, "text": 384}[modality]
        return 200, {
            "result": {
                "points_count": 1,
                "status": "green",
                "config": {"params": {"vectors": {"size": observed}}},
            }
        }

    monkeypatch.setattr(current_state, "_http_json", fake_http)
    result = current_state._capture_qdrant(
        "http://127.0.0.1:6333",
        collections,
        {"audio": 512, "clip": 768, "dino": 1024, "text": 384},
    )

    assert result["collections"]["text"]["dimensions"] == 384

    with pytest.raises(RuntimeError, match="dimension mismatch"):
        current_state._capture_qdrant(
            "http://127.0.0.1:6333",
            collections,
            {modality: 1 for modality in collections},
        )


def test_endpoint_and_observed_model_metadata_are_redacted(monkeypatch, tmp_path):
    epoch_root = _canonical_epoch_root(tmp_path)
    config = _test_config(epoch_root)
    config["llm"]["vllm_url"] = "http://user:pass@127.0.0.1:38005/v1?token=secret"

    authority = extract_config_authority(config, epoch_root)
    serialized = json.dumps(authority["configured_runtime"])
    assert "user" not in serialized
    assert "pass" not in serialized
    assert "token" not in serialized
    assert authority["configured_runtime"]["qdrant"]["endpoint"] == "http://127.0.0.1:6333"

    config["qdrant"]["host"] = "http://user:pass@127.0.0.1:6333?token=secret"
    with pytest.raises(ValueError, match="credentials, query, or fragment"):
        extract_config_authority(config, epoch_root)

    monkeypatch.setattr(
        current_state,
        "_http_json",
        lambda *_args, **_kwargs: (
            200,
            {"data": [{"id": "C:\\private\\models\\secret-model"}]},
        ),
    )
    observed = current_state._probe_openai_models("http://127.0.0.1:38005/v1")
    assert observed["models"] == ["secret-model"]
    assert "private" not in json.dumps(observed)


def test_projection_transaction_rolls_back_all_files_on_replace_failure(
    tmp_path, evidence, monkeypatch
):
    paths = [
        tmp_path / "CURRENT_STATE.md",
        tmp_path / "current_state.json",
        tmp_path / "GOODQ_RAG_CONTEXT_PACK.md",
    ]
    for index, path in enumerate(paths):
        path.write_text(f"old-{index}\n", encoding="utf-8")
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    real_replace = os.replace
    target_paths = {path.resolve() for path in paths}
    commit_count = 0

    def fail_second_projection_replace(source, destination):
        nonlocal commit_count
        destination_path = Path(destination).resolve()
        if destination_path in target_paths and ".projection-" in Path(source).name:
            commit_count += 1
            if commit_count == 2:
                raise OSError("simulated projection replacement failure")
        return real_replace(source, destination)

    monkeypatch.setattr(current_state.os, "replace", fail_second_projection_replace)
    with pytest.raises(OSError, match="simulated projection"):
        current_state.render_projection_files(
            evidence,
            paths[0],
            paths[1],
            paths[2],
            evidence_path=evidence_path,
        )

    assert [path.read_text(encoding="utf-8") for path in paths] == [
        "old-0\n",
        "old-1\n",
        "old-2\n",
    ]
    assert not list(tmp_path.glob("*.projection-*"))
    assert not list(tmp_path.glob("*.backup-*"))
    assert not list(tmp_path.glob("*.lock"))


def test_projection_paths_must_be_distinct_and_not_collide_with_evidence(tmp_path, evidence):
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    output = tmp_path / "output.md"

    with pytest.raises(ValueError, match="distinct"):
        current_state.render_projection_files(
            evidence,
            output,
            output,
            tmp_path / "rag.md",
            evidence_path=evidence_path,
        )
    with pytest.raises(ValueError, match="evidence"):
        current_state.render_projection_files(
            evidence,
            evidence_path,
            tmp_path / "state.json",
            tmp_path / "rag.md",
            evidence_path=evidence_path,
        )


def test_cli_render_rejects_tampered_evidence_without_touching_outputs(tmp_path, evidence):
    tampered = copy.deepcopy(evidence)
    tampered["schema_version"] = 999
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(tampered), encoding="utf-8")
    paths = [tmp_path / "CURRENT_STATE.md", tmp_path / "current_state.json", tmp_path / "rag.md"]
    for path in paths:
        path.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        current_state.main(
            [
                "render",
                "--evidence",
                str(evidence_path),
                "--current-state-md",
                str(paths[0]),
                "--current-state-json",
                str(paths[1]),
                "--rag-context",
                str(paths[2]),
            ]
        )

    assert [path.read_text(encoding="utf-8") for path in paths] == ["sentinel\n"] * 3
    assert not list(tmp_path.glob("*.projection-*"))


def test_projection_records_supplied_evidence_source_and_current_historical_path(evidence):
    projection = project_current_state_json(
        evidence,
        evidence_source="docs/diagnostics/evidence/custom.json",
    )
    assert projection["generated_from"] == "docs/diagnostics/evidence/custom.json"

    historical = [item["path"] for item in current_state._historical_evidence()]
    assert "docs/archive/HANDOFF_BASEMENT_PHASE.md" in historical
    assert "docs/HANDOFF_BASEMENT_PHASE.md" not in historical


def test_capture_is_redacted_and_uses_only_explicit_epoch_authority(tmp_path, monkeypatch):
    epoch_root = _canonical_epoch_root(tmp_path)
    data_root = epoch_root.parent.parent
    (epoch_root / "ucf").mkdir(parents=True)
    (data_root / "processed").mkdir()
    (data_root / "import_inbox").mkdir()
    (data_root / "failed").mkdir()
    (data_root / "processed" / "one.mp4").write_bytes(b"media")
    (epoch_root / "faiss_text.index").write_bytes(b"index")

    ucf = sqlite3.connect(epoch_root / "ucf" / "ucf_ledger.db")
    ucf.executescript(
        """
        CREATE TABLE context_frames (
            video_hash TEXT, epoch_id TEXT, promotion_status TEXT
        );
        CREATE TABLE media_sources (video_hash TEXT);
        CREATE TABLE ucf_status_transitions (new_status TEXT);
        """
    )
    ucf.execute("INSERT INTO context_frames VALUES (?, ?, ?)", ("video", EPOCH_ID, "promoted"))
    ucf.execute("INSERT INTO media_sources VALUES ('video')")
    ucf.execute("INSERT INTO ucf_status_transitions VALUES ('validated')")
    ucf.commit()
    ucf.close()

    for name, schema in (
        ("memory.db", "CREATE TABLE scenes (id TEXT); CREATE TABLE segments (id TEXT); CREATE TABLE embeddings (id TEXT); CREATE TABLE links (id TEXT);"),
        ("knowledge_graph.db", "CREATE TABLE nodes (id TEXT); CREATE TABLE edges (id TEXT); CREATE TABLE events (id TEXT);"),
    ):
        connection = sqlite3.connect(epoch_root / name)
        connection.executescript(schema)
        connection.commit()
        connection.close()

    config = {
        "host": {"profile": "GPU_ENHANCED"},
        "paths": {
            "db_dir": str(epoch_root),
            "processed": str(data_root / "processed"),
            "import_inbox": str(data_root / "import_inbox"),
            "failed": str(data_root / "failed"),
        },
        "api": {"host": "127.0.0.1", "port": 30000},
        "qdrant": {
            "host": "http://127.0.0.1:6333",
            "collections": _expected_test_collections(),
            "embedding_dims": {"audio": 512, "clip": 768, "dino": 1024, "text": 384},
        },
        "llm": {
            "vllm_url": "http://127.0.0.1:38005/v1",
            "vllm_model": "/private/models/Qwen2.5-0.5B-Instruct",
            "ollama_url": "http://127.0.0.1:11434/v1",
            "ollama_model": "llama3.2:latest",
        },
    }
    qdrant_collections = {
        modality: {
            "name": name,
            "points_count": 1,
            "dimensions": config["qdrant"]["embedding_dims"][modality],
            "status": "green",
            "identity_only_sample": True,
        }
        for modality, name in config["qdrant"]["collections"].items()
    }
    monkeypatch.setattr(
        current_state,
        "_capture_qdrant",
        lambda *_args, **_kwargs: {"state": "running_loopback", "collections": qdrant_collections},
    )
    monkeypatch.setattr(current_state, "_probe_tcp", lambda *_args, **_kwargs: {"state": "stopped"})
    monkeypatch.setattr(current_state, "_probe_openai_models", lambda *_args, **_kwargs: {"state": "stopped_or_unavailable", "models": []})
    monkeypatch.setattr(current_state, "_probe_ollama", lambda *_args, **_kwargs: {"state": "reachable", "loaded_models": []})
    monkeypatch.setattr(current_state, "_git_state", lambda _root: {"commit": "deadbeef", "branch": "test", "dirty": False})

    captured = capture_evidence(
        config,
        epoch_root,
        captured_at_utc="2026-07-11T12:19:07Z",
        repo_root=tmp_path,
    )

    assert captured["completion"]["context_frames"] == 1
    assert captured["completion"]["processed_media"] == 1
    assert captured["persistence"]["ucf"] == {"transitions": 1, "validated_transitions": 1}
    assert captured["authority"]["epoch_id"] == EPOCH_ID
    assert captured["evidence_id"]
    assert str(tmp_path) not in json.dumps(captured)
    assert all("R-" not in item for item in captured["limitations"])
    assert "R-" not in json.dumps(captured["observed_services"])
    assert "branch" not in captured["repository"]


def _expected_test_collections():
    return {
        modality: f"goodq_{modality}_{EPOCH_ID}"
        for modality in ("audio", "clip", "dino", "text")
    }


def _test_config(epoch_root):
    data_root = epoch_root.parent.parent
    return {
        "host": {"profile": "GPU_ENHANCED"},
        "paths": {
            "db_dir": str(epoch_root),
            "processed": str(data_root / "processed"),
            "import_inbox": str(data_root / "import_inbox"),
            "failed": str(data_root / "failed"),
        },
        "api": {"host": "127.0.0.1", "port": 30000},
        "qdrant": {
            "host": "http://127.0.0.1:6333",
            "collections": _expected_test_collections(),
            "embedding_dims": {"audio": 512, "clip": 768, "dino": 1024, "text": 384},
        },
        "llm": {
            "vllm_url": "http://127.0.0.1:38005/v1",
            "vllm_model": "/models/Qwen2.5-0.5B-Instruct",
            "ollama_url": "http://127.0.0.1:11434/v1",
            "ollama_model": "llama3.2:latest",
        },
    }


def _canonical_epoch_root(root):
    epoch_root = root / "GoodQ_Data" / "epochs" / EPOCH_ID
    epoch_root.mkdir(parents=True)
    return epoch_root
