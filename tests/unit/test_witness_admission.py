"""Fresh witness admission rejects retained stores before production writes."""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import subprocess
import sys

import pytest
import requests

from cli import golden_witness, run_ingestion


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    root = tmp_path / "witness"
    models = tmp_path / "shared-models"
    models.mkdir()
    cfg = golden_witness._isolated_runtime_snapshot({
        "epoch_id": "epoch_witness_admission",
        "preflight": {"config": {"paths": {"models_cache": str(models)},
                                   "host": {"profile": "PERSONAL_AIR_GAP"}}},
    }, root)
    cfg["qdrant"].update(enabled=True, embedding_dims={"clip": 3, "dino": 4, "text": 5, "audio": 6})
    snapshot = root / "config" / "witness-config.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text(json.dumps(cfg), encoding="utf-8")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"test source; never decoded")
    monkeypatch.setattr(run_ingestion, "load_configs", lambda _: {})
    return cfg, snapshot, source


def test_production_caller_rejects_reused_witness_before_creating_workspace(candidate):
    from cli.witness_environment import build_witness_environment

    cfg, snapshot, source = candidate
    root = Path(cfg["witness"]["artifact_root"])
    (root / "witness-admission.json").write_text("prior admission", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-B", "-m", "cli.run_ingestion", "--config", str(snapshot),
         "--input-file", str(source)],
        cwd=Path(__file__).resolve().parents[2],
        env=build_witness_environment(snapshot, os.environ),
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0
    assert "already admitted" in result.stdout + result.stderr
    assert not (Path(cfg["paths"]["processing"]) / "_workspace").exists()
    assert not Path(cfg["paths"]["db_path"]).exists()


@pytest.fixture
def qdrant_transport(monkeypatch):
    state = {"requests": [], "status": 404, "raise": None, "created": {},
             "verify_override": {}, "put_fail": None, "host": "http://127.0.0.1:6333"}

    def send(session, request, **kwargs):
        assert request.method in {"GET", "PUT"}
        assert request.url.startswith(f"{state['host']}/collections/")
        assert session.trust_env is False
        assert kwargs["allow_redirects"] is False
        state["requests"].append((request.method, request.url))
        if state["raise"]:
            raise state["raise"]
        response = requests.Response()
        response.request = request
        name = request.url.rsplit("/", 1)[-1]
        response.status_code = state["status"]
        body = {"status": {"error": "Not found"}}
        if request.method == "PUT":
            if state["put_fail"] in {name, "all"}:
                response.status_code = 500
            else:
                assert name not in state["created"], "existing collection was overwritten"
                state["created"][name] = json.loads(request.body)["vectors"]
                response.status_code = 200
                body = {"result": True, "status": "ok"}
        elif name in state["created"]:
            response.status_code = 200
            result = {"points_count": 0, "config": {"params": {"vectors": state["created"][name]}}}
            result.update(state["verify_override"])
            body = {"result": result, "status": "ok"}
        response._content = json.dumps(body).encode()
        return response

    monkeypatch.setattr(requests.Session, "send", send)
    return state


def test_admission_checks_exact_collections_once_and_records_explicit_exceptions(candidate, qdrant_transport):
    cfg, snapshot, _ = candidate
    receipt = golden_witness.admit_witness_run(cfg, snapshot)
    assert receipt["status"] == "admitted"
    assert receipt["epoch_id"] == cfg["epoch_id"]
    expected_urls = {f"http://127.0.0.1:6333/collections/{name}" for name in cfg["qdrant"]["collections"].values()}
    assert {url for method, url in qdrant_transport["requests"] if method == "PUT"} == expected_urls
    assert len(qdrant_transport["requests"]) == 16
    assert receipt["shared_exceptions"]["models_cache"]["path"] == cfg["paths"]["models_cache"]
    assert "vram_coordination" in receipt["shared_exceptions"]
    marker = Path(cfg["witness"]["artifact_root"]) / "witness-admission.json"
    assert json.loads(marker.read_text(encoding="utf-8")) == receipt
    with pytest.raises(golden_witness.WitnessAuthorityError, match="already admitted"):
        golden_witness.admit_witness_run(cfg, snapshot)
    assert len(qdrant_transport["requests"]) == 16
    assert not Path(cfg["paths"]["db_dir"]).exists()


def test_admission_requires_real_snapshot_before_any_request(candidate, qdrant_transport):
    cfg, snapshot, _ = candidate
    missing_snapshot = snapshot.with_name("absent-snapshot.json")
    with pytest.raises(golden_witness.WitnessAuthorityError, match="snapshot.*file"):
        golden_witness.admit_witness_run(cfg, missing_snapshot)
    assert qdrant_transport["requests"] == []
    assert not (snapshot.parent.parent / "witness-admission.json").exists()


@pytest.mark.parametrize("key", [
    "db_path", "knowledge_graph_db", "faiss_audio_path", "faiss_index_path",
    "faiss_clip_path", "faiss_dino_path", "clip_id_map_db", "dino_id_map_db", "clap_id_map_db",
])
@pytest.mark.parametrize("suffix", ["", "-wal", "-shm", "-journal"])
def test_admission_rejects_existing_file_stores_and_sidecars(candidate, qdrant_transport, key, suffix):
    cfg, snapshot, _ = candidate
    stale = Path(cfg["paths"][key] + suffix)
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"retained")
    with pytest.raises(golden_witness.WitnessAuthorityError, match="not fresh"):
        golden_witness.admit_witness_run(cfg, snapshot)
    assert stale.read_bytes() == b"retained"
    assert qdrant_transport["requests"] == []
    assert not (snapshot.parent.parent / "witness-admission.json").exists()


@pytest.mark.parametrize("status", [200, 301, 401, 500])
def test_existing_or_unverified_collection_refuses_admission(candidate, qdrant_transport, status):
    cfg, snapshot, _ = candidate
    qdrant_transport["status"] = status
    with pytest.raises(golden_witness.WitnessAuthorityError, match="collection"):
        golden_witness.admit_witness_run(cfg, snapshot)
    assert not (snapshot.parent.parent / "witness-admission.json").exists()


def test_unreachable_collection_refuses_admission(candidate, qdrant_transport):
    cfg, snapshot, _ = candidate
    qdrant_transport["raise"] = requests.ConnectionError("unavailable")
    with pytest.raises(golden_witness.WitnessAuthorityError, match="collection"):
        golden_witness.admit_witness_run(cfg, snapshot)
    assert not (snapshot.parent.parent / "witness-admission.json").exists()


@pytest.mark.parametrize("result_override", [
    {"points_count": 1},
    {"points_count": None},
    {"config": {"params": {"vectors": {"size": 999, "distance": "Cosine"}}}},
    {"config": {"params": {"vectors": {"size": 3, "distance": "Dot"}}}},
])
def test_verification_failure_preserves_one_use_marker(candidate, qdrant_transport, result_override):
    cfg, snapshot, _ = candidate
    qdrant_transport["verify_override"] = result_override
    with pytest.raises(golden_witness.WitnessAuthorityError, match="preserve partial run"):
        golden_witness.admit_witness_run(cfg, snapshot)
    marker = snapshot.parent.parent / "witness-admission.json"
    assert json.loads(marker.read_text())["status"] == "failed"
    assert len(qdrant_transport["created"]) == 1
    with pytest.raises(golden_witness.WitnessAuthorityError, match="already admitted"):
        golden_witness.admit_witness_run(cfg, snapshot)


def test_partial_initialization_preserves_created_collection_and_stops(candidate, qdrant_transport):
    cfg, snapshot, _ = candidate
    qdrant_transport["put_fail"] = cfg["qdrant"]["collections"]["dino"]
    with pytest.raises(golden_witness.WitnessAuthorityError, match="preserve partial run"):
        golden_witness.admit_witness_run(cfg, snapshot)
    assert set(qdrant_transport["created"]) == {cfg["qdrant"]["collections"]["clip"]}
    receipt = json.loads((snapshot.parent.parent / "witness-admission.json").read_text())
    assert receipt["status"] == "failed"
    assert set(receipt["collections_verified"]) == {"clip"}


def test_admission_rejects_store_symlink_escape(candidate, qdrant_transport, tmp_path):
    cfg, snapshot, _ = candidate
    outside = tmp_path / "retained.sqlite"
    outside.write_bytes(b"retained")
    path = Path(cfg["paths"]["db_path"])
    path.parent.mkdir(parents=True)
    try:
        path.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink capability unavailable: {exc}")
    with pytest.raises(golden_witness.WitnessAuthorityError, match="escapes root"):
        golden_witness.admit_witness_run(cfg, snapshot)
    assert outside.read_bytes() == b"retained"
    assert qdrant_transport["requests"] == []


def test_import_created_logs_and_empty_dirs_are_not_stale_stores(candidate, qdrant_transport):
    cfg, snapshot, _ = candidate
    logs = Path(cfg["paths"]["log_dir"])
    logs.mkdir(parents=True)
    (logs / "bootstrap.log").write_text("module bootstrap", encoding="utf-8")
    Path(cfg["paths"]["processing"]).mkdir()
    assert golden_witness.admit_witness_run(cfg, snapshot)["status"] == "admitted"


def test_admission_rejects_dangling_store_symlink(candidate, qdrant_transport):
    cfg, snapshot, _ = candidate
    path = Path(cfg["paths"]["db_path"])
    path.parent.mkdir(parents=True)
    try:
        path.symlink_to(path.with_name("absent.sqlite"))
    except OSError as exc:
        pytest.skip(f"symlink capability unavailable: {exc}")
    with pytest.raises(golden_witness.WitnessAuthorityError, match="not fresh"):
        golden_witness.admit_witness_run(cfg, snapshot)
    assert path.is_symlink()
    assert qdrant_transport["requests"] == []


def test_only_one_concurrent_caller_can_claim_fresh_run(candidate, qdrant_transport, monkeypatch):
    cfg, snapshot, _ = candidate
    marker = snapshot.parent.parent / "witness-admission.json"
    original_open = Path.open
    claim_barrier = threading.Barrier(2)

    def synchronized_claim(path, mode="r", *args, **kwargs):
        if path == marker and mode == "x":
            claim_barrier.wait(timeout=5)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", synchronized_claim)

    def admit():
        try:
            return golden_witness.admit_witness_run(cfg, snapshot)["status"]
        except golden_witness.WitnessAuthorityError as exc:
            assert "already admitted" in str(exc)
            return "refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: admit(), range(2)))
    assert sorted(outcomes) == ["admitted", "refused"]
    assert len(qdrant_transport["created"]) == 4
    assert json.loads(marker.read_text())["status"] == "admitted"


@pytest.mark.parametrize("host", ["http://127.0.0.1:6334", "http://localhost:6333/"])
def test_explicit_loopback_port_and_trailing_slash_are_preserved(candidate, qdrant_transport, host):
    cfg, snapshot, _ = candidate
    cfg["qdrant"]["host"] = host
    qdrant_transport["host"] = host.rstrip("/")
    assert golden_witness.admit_witness_run(cfg, snapshot)["status"] == "admitted"
    assert cfg["qdrant"]["host"] == host


@pytest.mark.parametrize("host", [
    "http://127.0.0.1", "http://127.0.0.1:0", "http://127.0.0.1:65536",
    "https://127.0.0.1:6333", "http://example.com:6333", "http://127.0.0.1:6333/other",
])
def test_invalid_admission_endpoint_refuses_before_network(candidate, qdrant_transport, host):
    cfg, snapshot, _ = candidate
    cfg["qdrant"]["host"] = host
    with pytest.raises(golden_witness.WitnessAuthorityError, match="loopback"):
        golden_witness.admit_witness_run(cfg, snapshot)
    assert qdrant_transport["requests"] == []
