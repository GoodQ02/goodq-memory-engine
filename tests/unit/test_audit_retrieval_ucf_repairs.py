"""Caller-level regression suite for Area 5 (Retrieval, Persistence & UCF) audit repairs.

Covers:
- RS-01: Summary Console scope & dashboard temporal_index promoted UCF gating
- RS-02: Whole-video supersede/reject durable outbox, fail-observable sync, and shared content-hash vector remapping
- RS-03: FTS search, DataLoader.is_search_result_active, and temporal_search promoted/retirement enforcement
- RS-04: MiniAgentClient qdrant_query default promoted+epoch must filter and faiss_search active membership filter
- RS-05: cli/nl_query read-only authority, retired-scene exclusion, and loopback/no-proxy LLM enforcement
- RS-06: retrieval_events dotted context regex normalization
- RS-07: QdrantClient.stats() passive check without collection creation & MiniAgentClient loopback transport
- ST-04: temporal_search dict object/entity extraction without source_path leakage + semantic_episode clustering
- ST-05 & VS-05: ASR restriction gating in UCF promotion FTS + narrative_summarizer markup stripping + Ollama unload
- AS-01 Gap 2: 0-turn scene speaker_change_review persistence on KG scene node during UCF promotion
- AS-05: UCF promotion audio_transcribe fallback cross-channel utterance deduplication
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from typing import Any, Dict, List
import uuid

import numpy as np
import pytest
import requests

from tests.unit.test_ucf_promotion_scene_identity import (
    confirmed,
    scene_promotion,
    stage_source,
)


def _canonical_retirement_scene_id(video_hash: str, start: float, end: float) -> str:
    return hashlib.sha256(
        f"scene{video_hash}|{start:.3f}|{end:.3f}|".encode()
    ).hexdigest()


def _make_epoch_cfg(epoch_dir: Path) -> Dict[str, Any]:
    processing_dir = epoch_dir / "processing"
    processing_dir.mkdir(parents=True, exist_ok=True)
    return {
        "epoch_id": epoch_dir.name,
        "paths": {
            "data_root": str(epoch_dir),
            "processing": str(processing_dir),
            "db_dir": str(epoch_dir),
            "db_path": str(epoch_dir / "memory.db"),
            "knowledge_graph_db": str(epoch_dir / "knowledge_graph.db"),
            "ucf_db_path": str(epoch_dir / "ucf" / "ucf_ledger.db"),
            "clip_id_map_db": str(epoch_dir / "clip_id_map.db"),
            "faiss_index": str(epoch_dir / "faiss_visual.index"),
        },
        "agent": {"execution_mode": "in_process"},
        "qdrant": {
            "enabled": True,
            "host": "http://127.0.0.1:6333",
            "collections": {
                "text": "goodq_text",
                "clip": "goodq_clip",
                "dino": "goodq_dino",
                "audio": "goodq_audio",
            },
        },
        "llm": {
            "api_url": "http://127.0.0.1:1234/v1/chat/completions",
            "features": {"video_summarization": False},
        },
    }


def _seed_promoted_scene_bundle(
    epoch_dir: Path,
    *,
    stem: str,
    video_bytes: bytes,
    scenes_spec: List[Dict[str, Any]],
) -> tuple[Path, str]:
    vid_dir = epoch_dir / "processing" / stem
    (vid_dir / "video" / "frames").mkdir(parents=True, exist_ok=True)
    (vid_dir / "audio" / "chunks").mkdir(parents=True, exist_ok=True)
    video_file = epoch_dir / f"{stem}.mp4"
    video_file.write_bytes(video_bytes)
    vhash = hashlib.sha256(video_bytes).hexdigest()

    temporal_segments = []
    manifest_scenes = []
    for idx, spec in enumerate(scenes_spec):
        sid = spec["scene_id"]
        start = float(spec.get("start", idx * 10.0))
        end = float(spec.get("end", (idx + 1) * 10.0))
        frame_path = vid_dir / "video" / "frames" / f"frame_{idx:04d}.jpg"
        frame_path.write_bytes(spec.get("frame_bytes", f"frame-{stem}-{idx}".encode()))
        audio_path = vid_dir / "audio" / "chunks" / f"scene_{idx:04d}.wav"
        audio_path.write_bytes(b"RIFF0000WAVEfmt ")
        seg = {
            "scene_id": sid,
            "index": idx,
            "start": start,
            "end": end,
            "representative_frame": str(frame_path),
            "frame_paths": [str(frame_path)],
            "summary": spec.get("summary", f"Scene {idx} summary"),
            "emotions": spec.get("emotions", [{"emotion": "happy", "confidence": 0.9}]),
            "sentiment": spec.get("sentiment", {"compound": 0.6, "label": "positive"}),
        }
        temporal_segments.append(seg)
        manifest_scenes.append(
            {
                "scene_id": sid,
                "video_id": vhash,
                "index": idx,
                "start": start,
                "end": end,
                "duration": end - start,
                "keyframe": {"path": str(frame_path)},
                "audio": {
                    "path": str(audio_path),
                    **spec.get("audio_meta", {}),
                },
                **spec.get("manifest_extra", {}),
            }
        )

    temporal_payload = {
        "video_id": vhash,
        "video_hash": vhash,
        "video_path": str(video_file),
        "total_scenes": len(temporal_segments),
        "total_duration": float(len(temporal_segments) * 10.0),
        "segments": temporal_segments,
    }
    (vid_dir / "temporal_index.json").write_text(
        json.dumps(temporal_payload), encoding="utf-8"
    )
    (vid_dir / "video" / "scene_manifest.json").write_text(
        json.dumps(
            {
                "video_id": vhash,
                "video_hash": vhash,
                "video_path": str(video_file),
                "scenes": manifest_scenes,
            }
        ),
        encoding="utf-8",
    )
    return vid_dir, vhash


# ---------------------------------------------------------------------------
# RS-01: Summary Console scope & dashboard temporal_index promoted UCF gating
# ---------------------------------------------------------------------------
def test_rs01_summary_scope_and_dashboard_require_promoted_ucf_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.utils import loaders
    from lib.knowledge_graph import KnowledgeGraph
    from lib.summary_aggregator import get_scope_metadata, get_summary_dashboard
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    epoch_dir = tmp_path / "epoch-rs01"
    cfg = _make_epoch_cfg(epoch_dir)

    _, vhash_promoted = _seed_promoted_scene_bundle(
        epoch_dir,
        stem="vid_promoted",
        video_bytes=b"promoted video bytes",
        scenes_spec=[
            {
                "scene_id": "sc_prom_0",
                "emotions": [{"emotion": "joy", "confidence": 0.92}],
                "sentiment": {"compound": 0.8, "label": "positive"},
            }
        ],
    )
    _, vhash_staged = _seed_promoted_scene_bundle(
        epoch_dir,
        stem="vid_staged",
        video_bytes=b"staged video bytes",
        scenes_spec=[
            {
                "scene_id": "sc_stage_0",
                "emotions": [{"emotion": "anger", "confidence": 0.95}],
                "sentiment": {"compound": -0.9, "label": "negative"},
            }
        ],
    )
    _, _vhash_foreign = _seed_promoted_scene_bundle(
        epoch_dir,
        stem="vid_foreign_zero_rows",
        video_bytes=b"foreign epoch residue bytes",
        scenes_spec=[
            {
                "scene_id": "sc_foreign_0",
                "emotions": [{"emotion": "fear", "confidence": 0.99}],
                "sentiment": {"compound": -0.7, "label": "negative"},
            }
        ],
    )

    kg_path = Path(cfg["paths"]["knowledge_graph_db"])
    with KnowledgeGraph(str(kg_path)) as kg:
        kg.add_node("person", "Speaker Alpha")

    ledger_path = Path(cfg["paths"]["ucf_db_path"])
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    ledger.log_frame(
        video_hash=vhash_promoted,
        epoch_id=epoch_dir.name,
        run_id="run-1",
        t_start=0.0,
        t_end=10.0,
        modality="video",
        worker_name="scene_summary",
        model_tag="test",
        source_artifact_id="sc_prom_0",
        promotion_status="promoted",
    )
    ledger.log_frame(
        video_hash=vhash_staged,
        epoch_id=epoch_dir.name,
        run_id="run-2",
        t_start=0.0,
        t_end=10.0,
        modality="video",
        worker_name="scene_summary",
        model_tag="test",
        source_artifact_id="sc_stage_0",
        promotion_status="staged",
    )
    ledger.close()

    for key in ("_DEFAULT_PROCESSING_ROOT", "_DEFAULT_PROCESSED_ROOT", "_DEFAULT_UCF_SCOPE"):
        monkeypatch.setattr(loaders, key, None, raising=False)
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", ())
    loaders.configure_from_cfg(cfg)
    loader = loaders.DataLoader()

    # Retro/Operator inspection still sees non-terminal staged/unregistered folders:
    assert set(loader.list_processed_videos()) == {
        "vid_promoted",
        "vid_staged",
        "vid_foreign_zero_rows",
    }

    # Summary Console scope & dashboard strictly admit only promoted active-epoch evidence:
    scope = get_scope_metadata(kg_path, loader)
    assert scope["video_ids"] == ["vid_promoted"]
    assert scope["video_count"] == 1
    assert scope["scene_count"] == 1

    dashboard = get_summary_dashboard(kg_path, loader)
    assert dashboard["scope_metadata"]["video_ids"] == ["vid_promoted"]
    emotion_names = {item["emotion"] for item in dashboard.get("top_emotions", [])}
    assert "anger" not in emotion_names
    assert "fear" not in emotion_names
    assert dashboard["built_in_highlights"]["negative_moments"] == []


# ---------------------------------------------------------------------------
# RS-02: Whole-video supersede/reject outbox, failure surfacing & reconciliation
# ---------------------------------------------------------------------------
def test_rs02_whole_video_supersede_outbox_surfaces_sync_failure_and_reconciles(
    scene_promotion: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    root, config, client = scene_promotion
    vh, sid = stage_source(root, config, "movie_alpha")
    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    ledger.log_frame(
        video_hash=vh,
        epoch_id=root.name,
        run_id="run-qdrant-vec",
        t_start=0.0,
        t_end=1.0,
        modality="text",
        worker_name="scene_summary",
        model_tag="fixture",
        source_artifact_id=sid,
        vector_key="11111111-1111-1111-1111-111111111111",
        vector_backend="qdrant",
        vector_collection="goodq_text",
        payload={"summary": "Alpha opening"},
    )
    ledger.close()
    scope = {"video_hash": vh, "epoch_id": root.name}

    val_res, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, val_res
    prom_res, _ = confirmed(client, "promote_ucf_to_memory", scope)
    assert prom_res["output"]["status"] == "promotion_committed_sync_pending", prom_res

    with closing(sqlite3.connect(root / "memory.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenes WHERE id = ?", (sid,)).fetchone()[0] == 1

    # Simulate Qdrant outage during whole-video supersede -> must record durable outbox
    # and return superseded_committed_sync_pending (rc == 1), NEVER superseded_complete!
    qdrant_healthy = {"ok": False}

    def flaky_status_sync(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
        if not qdrant_healthy["ok"]:
            return {
                "attempted": True,
                "status": "error",
                "points_attempted": 1,
                "points_verified": 0,
                "collections_attempted": ["goodq_text"],
                "failed_collections": ["goodq_text"],
            }
        return {
            "attempted": True,
            "status": "ok",
            "points_attempted": 1,
            "points_verified": 1,
            "collections_attempted": ["goodq_text"],
            "failed_collections": [],
        }

    def flaky_scope_sync(**_kwargs: Any) -> Dict[str, Any]:
        if not qdrant_healthy["ok"]:
            return {
                "status": "error",
                "collections_swept": ["goodq_text"],
                "points_updated": 0,
                "points_verified": 0,
                "failed_collections": ["goodq_text"],
            }
        return {
            "status": "ok",
            "collections_swept": ["goodq_text"],
            "points_updated": 1,
            "points_verified": 1,
            "failed_collections": [],
        }

    monkeypatch.setattr(client, "_sync_ucf_status_to_qdrant", flaky_status_sync)
    monkeypatch.setattr(client, "_sync_qdrant_by_scope", flaky_scope_sync)

    sup_res, rc = confirmed(client, "supersede_ucf_frames", scope)
    assert rc == 1, sup_res
    sup_out = sup_res["output"]
    assert sup_out["status"] == "superseded_committed_sync_pending"
    assert sup_out["outbox"]["delivery_state"] == "pending"

    with closing(sqlite3.connect(root / "ucf/ucf_ledger.db")) as conn:
        row = conn.execute(
            "SELECT operation, delivery_state, payload_json FROM ucf_qdrant_sync_outbox "
            "WHERE video_hash = ? AND operation = 'supersede_ucf_frames'",
            (vh,),
        ).fetchone()
        assert row is not None
        assert row[0] == "supersede_ucf_frames"
        assert row[1] == "pending"
        assert json.loads(row[2])["target_status"] == "superseded"

    # Restore Qdrant and reconcile via reconcile_ucf_qdrant -> transitions outbox to complete
    qdrant_healthy["ok"] = True
    rec_res, rc = confirmed(client, "reconcile_ucf_qdrant", scope)
    assert rc == 0, rec_res
    rec_out = rec_res["output"]
    assert rec_out["status"] == "qdrant_sync_reconciled"
    assert rec_out["outbox"]["delivery_state"] == "complete"

    with closing(sqlite3.connect(root / "memory.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenes WHERE id = ?", (sid,)).fetchone()[0] == 0


def test_rs02_whole_video_supersede_remaps_shared_content_hash_vectors(
    scene_promotion: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agents.mini_agent_client import MiniAgentClient
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from steps.common.memory import to_faiss_id
    from steps.common.qdrant_client import GOODQ_POINT_ID_NAMESPACE

    root, config, client = scene_promotion
    vh_retiring, sid_retiring = stage_source(root, config, "dup_movie_a")
    vh_survivor, sid_survivor = stage_source(root, config, "dup_movie_b")

    for vh in (vh_retiring, vh_survivor):
        sc = {"video_hash": vh, "epoch_id": root.name}
        res_v, rc = confirmed(client, "validate_ucf_frames", sc)
        assert rc == 0, res_v
        res_p, _ = confirmed(client, "promote_ucf_to_memory", sc)
        assert res_p["output"]["status"] == "promotion_committed_sync_pending", res_p

    artifact = root / "processing" / "shared_keyframe.png"
    artifact.write_bytes(b"identical decoded frame source bytes across two movies")
    key = hashlib.sha256(artifact.read_bytes()).hexdigest()
    point_id = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, key))
    collection = f"goodq_clip_{root.name}"

    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    fid_survivor = ledger.log_frame(
        video_hash=vh_survivor,
        epoch_id=root.name,
        run_id="run-survivor",
        t_start=0.0,
        t_end=1.0,
        modality="video",
        worker_name="image_embed_clip",
        model_tag="ViT-B-32",
        vector_model_tag="ViT-B-32",
        source_artifact_id=sid_survivor,
        vector_key=key,
        vector_backend="qdrant",
        vector_collection=collection,
        promotion_status="promoted",
    )
    fid_retiring = ledger.log_frame(
        video_hash=vh_retiring,
        epoch_id=root.name,
        run_id="run-retiring",
        t_start=0.0,
        t_end=1.0,
        modality="video",
        worker_name="image_embed_clip",
        model_tag="ViT-B-32",
        vector_model_tag="ViT-B-32",
        source_artifact_id=sid_retiring,
        vector_key=key,
        vector_backend="qdrant",
        vector_collection=collection,
        promotion_status="promoted",
    )
    ledger.close()

    with closing(sqlite3.connect(root / "memory.db")) as conn, conn:
        meta = json.loads(
            conn.execute("SELECT meta FROM scenes WHERE id=?", (sid_survivor,)).fetchone()[0]
        )
        meta.setdefault("keyframe", {})["path"] = str(artifact)
        conn.execute("UPDATE scenes SET meta=? WHERE id=?", (json.dumps(meta), sid_survivor))
        conn.execute("INSERT INTO ucf_provenance_mapping VALUES('scene',?,?)", (sid_survivor, fid_survivor))
        conn.execute("INSERT INTO ucf_provenance_mapping VALUES('scene',?,?)", (sid_retiring, fid_retiring))
        conn.execute(
            "INSERT INTO embeddings(hash,faiss_id,source_path,modality,scene_id,created_at,ucf_provenance) "
            "VALUES(?,?,?,'clip',?,'fixture',?)",
            (key, to_faiss_id(key), str(artifact), sid_retiring, json.dumps([fid_survivor, fid_retiring])),
        )
        for sup_fid in (fid_survivor, fid_retiring):
            conn.execute("INSERT INTO ucf_provenance_mapping VALUES('embedding',?,?)", (key, sup_fid))

    config["paths"]["clip_id_map_db"] = str(root / "clip-map.db")
    with closing(sqlite3.connect(root / "clip-map.db")) as conn, conn:
        conn.execute(
            "CREATE TABLE clip_id_map(hash TEXT,video_hash TEXT,epoch_id TEXT,scene_id TEXT,source_path TEXT,ucf_frame_id INTEGER)"
        )
        conn.execute(
            "INSERT INTO clip_id_map VALUES(?,?,?,?,?,?)",
            (key, vh_retiring, root.name, sid_retiring, "retired-frame.png", fid_retiring),
        )

    point = {
        "id": point_id,
        "payload": {
            "video_hash": vh_retiring,
            "epoch_id": root.name,
            "scene_id": sid_retiring,
            "ucf_promotion_status": "promoted",
            "caption": "Retired movie caption",
            "source_path": "retired-frame.png",
            "start": 0.0,
            "end": 1.0,
        },
    }

    def fake_response(value: Any) -> requests.Response:
        resp = requests.Response()
        resp.status_code = 200
        resp._content = json.dumps({"result": value}).encode()
        return resp

    def fake_post(url: str, *, json: Any = None, **_kwargs: Any) -> requests.Response:
        if "/scroll" in url:
            return fake_response({"points": [], "next_page_offset": None})
        if url.endswith("/points/payload"):
            patch = (json or {}).get("payload") or {}
            for pid in (json or {}).get("points") or []:
                if str(pid) == point_id:
                    point["payload"].update(patch)
            return fake_response({"status": "completed"})
        return fake_response([point] if point_id in ((json or {}).get("ids") or []) else [])

    def fake_put(url: str, *, json: Any = None, **_kwargs: Any) -> requests.Response:
        assert url.endswith("/points/payload?wait=true")
        point["payload"] = dict((json or {}).get("payload") or {})
        return fake_response({"status": "completed"})

    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "put", fake_put)
    monkeypatch.setattr(requests, "get", lambda *a, **k: fake_response({"collections": [{"name": collection}]}))
    for method_name in ("_sync_ucf_status_to_qdrant", "_sync_qdrant_by_scope"):
        monkeypatch.setattr(client, method_name, getattr(MiniAgentClient, method_name).__get__(client))

    # Whole-video supersede on movie A (without scene_id!) must remap shared vector to survivor movie B!
    res, rc = confirmed(client, "supersede_ucf_frames", {"video_hash": vh_retiring, "epoch_id": root.name})
    assert rc == 0, res
    assert res["output"]["status"] == "superseded_complete"

    assert point["payload"]["ucf_promotion_status"] == "promoted"
    assert point["payload"]["video_hash"] == vh_survivor
    assert point["payload"]["scene_id"] == sid_survivor
    assert "caption" not in point["payload"]

    with closing(sqlite3.connect(root / "memory.db")) as conn:
        assert conn.execute("SELECT scene_id FROM embeddings WHERE hash=?", (key,)).fetchone() == (sid_survivor,)
        assert conn.execute("SELECT COUNT(*) FROM scenes WHERE id=?", (sid_retiring,)).fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM scenes WHERE id=?", (sid_survivor,)).fetchone() == (1,)

    with closing(sqlite3.connect(root / "clip-map.db")) as conn:
        assert conn.execute(
            "SELECT video_hash, scene_id, ucf_frame_id FROM clip_id_map WHERE hash=?", (key,)
        ).fetchone() == (vh_survivor, sid_survivor, fid_survivor)


# ---------------------------------------------------------------------------
# RS-03: FTS search, DataLoader.is_search_result_active & temporal_search
# ---------------------------------------------------------------------------
def test_rs03_fts_and_search_result_active_exclude_superseded_and_retired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.utils import loaders
    from retrieval.multimodal_search import MultimodalSearchEngine
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from steps.common.memory import _connect

    epoch_dir = tmp_path / "epoch-rs03"
    cfg = _make_epoch_cfg(epoch_dir)

    _, vhash_sup = _seed_promoted_scene_bundle(
        epoch_dir,
        stem="stem_superseded",
        video_bytes=b"superseded source",
        scenes_spec=[{"scene_id": "sc_sup_0", "summary": "lantern festival celebration"}],
    )
    _, vhash_act = _seed_promoted_scene_bundle(
        epoch_dir,
        stem="stem_active",
        video_bytes=b"active source",
        scenes_spec=[
            {"scene_id": "sc_retired_0", "start": 0.0, "end": 10.0, "summary": "lantern festival retired"},
            {"scene_id": "sc_live_1", "start": 10.0, "end": 20.0, "summary": "lantern festival live"},
        ],
    )

    canonical_retired_sid = _canonical_retirement_scene_id(vhash_act, 0.0, 10.0)
    ledger_path = Path(cfg["paths"]["ucf_db_path"])
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    ledger.log_frame(
        video_hash=vhash_sup,
        epoch_id=epoch_dir.name,
        run_id="r-sup",
        t_start=0.0,
        t_end=10.0,
        modality="text",
        worker_name="scene_summary",
        model_tag="m1",
        source_artifact_id="sc_sup_0",
        promotion_status="superseded",
    )
    fid_ret = ledger.log_frame(
        video_hash=vhash_act,
        epoch_id=epoch_dir.name,
        run_id="r-act",
        t_start=0.0,
        t_end=10.0,
        modality="text",
        worker_name="scene_summary",
        model_tag="m1",
        source_artifact_id="sc_retired_0",
        promotion_status="promoted",
    )
    ledger.log_frame(
        video_hash=vhash_act,
        epoch_id=epoch_dir.name,
        run_id="r-act",
        t_start=10.0,
        t_end=20.0,
        modality="text",
        worker_name="scene_summary",
        model_tag="m1",
        source_artifact_id="sc_live_1",
        promotion_status="promoted",
    )
    ledger.close()

    with closing(sqlite3.connect(ledger_path)) as conn, conn:
        UCFLedgerClient.insert_status_transition(
            conn,
            old_status="promoted",
            new_status="rejected",
            tool_name="ucf_retire_scene",
            video_hash=vhash_act,
            epoch_id=epoch_dir.name,
            scope=f"scene_retirement:{canonical_retired_sid}",
            evidence={
                "kind": "scene_retirement",
                "version": 1,
                "scene_id": canonical_retired_sid,
                "aliases": [canonical_retired_sid, "sc_retired_0"],
                "video_hash": vhash_act,
                "epoch_id": epoch_dir.name,
                "start": 0.0,
                "end": 10.0,
                "frame_ids": [fid_ret],
                "vectors": [],
            },
            frame_ids=[fid_ret],
        )

    with closing(_connect(cfg["paths"]["db_path"])) as conn, conn:
        for sid, vh, st, en, txt in [
            ("sc_sup_0", vhash_sup, 0.0, 10.0, "lantern festival lantern lantern"),
            ("sc_retired_0", vhash_act, 0.0, 10.0, "lantern festival lantern"),
            ("sc_live_1", vhash_act, 10.0, 20.0, "lantern festival"),
        ]:
            conn.execute(
                "INSERT INTO scenes (id, video_hash, start, end, meta, created_at) VALUES (?, ?, ?, ?, '{}', 'now')",
                (sid, vh, st, en),
            )
            conn.execute(
                "INSERT INTO scene_text_fts (scene_id, video_hash, content_type, text) VALUES (?, ?, 'summary', ?)",
                (sid, vh, txt),
            )

    # 1. MultimodalSearchEngine.search_fts filters superseded & pending-retired scenes BEFORE top_k=1 truncation
    engine = object.__new__(MultimodalSearchEngine)
    engine.config = cfg
    engine.cfg = cfg
    engine.db_path = Path(cfg["paths"]["db_path"])
    engine._last_search_diagnostics = {}
    hits = engine.search_fts("lantern", top_k=1)
    assert [h["payload"]["scene_id"] for h in hits] == ["sc_live_1"]

    # 2. DataLoader.is_search_result_active blocks video_hash payloads when folder is processing/<video_stem>
    for key in ("_DEFAULT_PROCESSING_ROOT", "_DEFAULT_PROCESSED_ROOT", "_DEFAULT_UCF_SCOPE"):
        monkeypatch.setattr(loaders, key, None, raising=False)
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", ())
    loaders.configure_from_cfg(cfg)
    loader = loaders.DataLoader()

    assert loader.is_search_result_active({"video_id": vhash_sup, "video_hash": vhash_sup, "scene_id": "sc_sup_0"}) is False
    assert loader.is_search_result_active({"video_id": vhash_act, "video_hash": vhash_act, "scene_id": "sc_retired_0"}) is False
    assert loader.is_search_result_active({"video_id": vhash_act, "video_hash": vhash_act, "scene_id": "sc_live_1"}) is True


# ---------------------------------------------------------------------------
# RS-04: MiniAgentClient qdrant_query default must filter & faiss_search gating
# ---------------------------------------------------------------------------
def test_rs04_mini_agent_qdrant_query_and_faiss_search_require_promoted_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agents.mini_agent_client import MiniAgentClient
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from steps.common.memory import _connect

    monkeypatch.setenv("GOODQ_AGENT_EXECUTION_MODE", "in_process")
    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    epoch_dir = tmp_path / "epoch-rs04"
    cfg_data = _make_epoch_cfg(epoch_dir)

    vhash_ok = "a" * 64
    vhash_stage = "b" * 64
    ledger_path = Path(cfg_data["paths"]["ucf_db_path"])
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    ledger.log_frame(
        video_hash=vhash_ok,
        epoch_id=epoch_dir.name,
        run_id="r1",
        t_start=0.0,
        t_end=5.0,
        modality="video",
        worker_name="scene_visual_embeddings",
        model_tag="clip",
        source_artifact_id="sc_ok",
        promotion_status="promoted",
    )
    ledger.log_frame(
        video_hash=vhash_stage,
        epoch_id=epoch_dir.name,
        run_id="r2",
        t_start=0.0,
        t_end=5.0,
        modality="video",
        worker_name="scene_visual_embeddings",
        model_tag="clip",
        source_artifact_id="sc_staged",
        promotion_status="staged",
    )
    ledger.close()

    with closing(_connect(cfg_data["paths"]["db_path"])) as conn, conn:
        conn.execute(
            "INSERT INTO scenes (id, video_hash, start, end, meta, created_at) VALUES ('sc_ok', ?, 0.0, 5.0, '{}', 'now')",
            (vhash_ok,),
        )
        conn.execute(
            "INSERT INTO scenes (id, video_hash, start, end, meta, created_at) VALUES ('sc_staged', ?, 0.0, 5.0, '{}', 'now')",
            (vhash_stage,),
        )
        vec_blob = np.zeros(4, dtype=np.float32).tobytes()
        conn.execute(
            "INSERT INTO embeddings (hash, faiss_id, source_path, modality, scene_id, created_at, vector) "
            "VALUES ('emb_ok', 10, '', 'clip', 'sc_ok', 'now', ?)",
            (vec_blob,),
        )
        conn.execute(
            "INSERT INTO embeddings (hash, faiss_id, source_path, modality, scene_id, created_at, vector) "
            "VALUES ('emb_staged', 20, '', 'clip', 'sc_staged', 'now', ?)",
            (vec_blob,),
        )

    faiss_file = Path(cfg_data["paths"]["faiss_index"])
    faiss_file.write_bytes(b"placeholder faiss index")

    captured_filter: Dict[str, Any] = {}

    class FakeQdrantClient:
        def query(self, vector: Any, top_k: int = 5, payload_filter: Any = None, **kwargs: Any) -> List[Dict[str, Any]]:
            captured_filter.update(payload_filter or {})
            return [
                {
                    "id": "pt-1",
                    "score": 0.91,
                    "payload": {
                        "video_hash": vhash_ok,
                        "epoch_id": epoch_dir.name,
                        "scene_id": "sc_ok",
                        "ucf_promotion_status": "promoted",
                    },
                }
            ]

    monkeypatch.setattr(
        "steps.common.qdrant_client.build_qdrant_client",
        lambda *_a, **_kw: FakeQdrantClient(),
    )

    client = MiniAgentClient(profile="safe", config=cfg_data)
    q_out = client._execute_qdrant_query(
        {"collection": "clip", "query_vector": [0.1, 0.2, 0.3, 0.4], "top_k": 5}
    )
    assert len(q_out["matches"]) == 1
    must_clauses = captured_filter["must"]
    assert {"key": "ucf_promotion_status", "match": {"value": "promoted"}} in must_clauses
    assert {"key": "epoch_id", "match": {"value": epoch_dir.name}} in must_clauses

    class FakeFaissIndex:
        ntotal = 2

        def search(self, query_arr: Any, k: int) -> tuple[np.ndarray, np.ndarray]:
            return (
                np.array([[0.99, 0.88]], dtype=np.float32),
                np.array([[20, 10]], dtype=np.int64),
            )

    fake_faiss = SimpleNamespace(read_index=lambda _p: FakeFaissIndex())
    monkeypatch.setitem(__import__("sys").modules, "faiss", fake_faiss)

    f_out = client._execute_faiss_search(
        {
            "index_path": str(faiss_file),
            "query_vector": [0.1, 0.2, 0.3, 0.4],
            "top_k": 5,
        }
    )
    # faiss_id=20 belongs to staged scene sc_staged and must be excluded; faiss_id=10 survives!
    f_ids = [r.get("faiss_id", r.get("id")) for r in f_out.get("matches", f_out.get("results", []))]
    assert f_ids == [10]


# ---------------------------------------------------------------------------
# RS-05: cli/nl_query read-only authority, retirement & loopback LLM guard
# ---------------------------------------------------------------------------
def test_rs05_nl_query_read_only_authority_retirement_and_loopback_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cli.nl_query import KnowledgeGraphNLQuery
    from lib.knowledge_graph import KnowledgeGraph
    from scripts.ucf.ucf_ledger import UCFLedgerClient

    epoch_dir = tmp_path / "epoch-rs05"
    cfg = _make_epoch_cfg(epoch_dir)

    # 1. Missing DB fails closed without creating a new SQLite file on disk
    missing_kg = epoch_dir / "knowledge_graph.db"
    qi_missing = KnowledgeGraphNLQuery(cfg=cfg)
    with pytest.raises(FileNotFoundError):
        qi_missing.get_statistics()
    assert not missing_kg.exists()

    # 2. Populate KG with one retired-only person and one active person
    vhash = "c" * 64
    with KnowledgeGraph(str(missing_kg)) as kg:
        p_active = kg.add_node("person", "Active Speaker")
        p_retired = kg.add_node("person", "Retired Speaker")
        m_ret = kg.add_media_node(
            "video",
            str(epoch_dir / "vid.mp4"),
            scene_id="sc_ret_nl",
            timestamp_start=0.0,
            timestamp_end=10.0,
            properties={"video_hash": vhash},
        )
        m_act = kg.add_media_node(
            "video",
            str(epoch_dir / "vid.mp4"),
            scene_id="sc_act_nl",
            timestamp_start=10.0,
            timestamp_end=20.0,
            properties={"video_hash": vhash},
        )
        kg.link_node_to_media(p_retired, m_ret)
        kg.link_node_to_media(p_active, m_act)

    canonical_ret_sid = _canonical_retirement_scene_id(vhash, 0.0, 10.0)
    ledger_path = Path(cfg["paths"]["ucf_db_path"])
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    fid = ledger.log_frame(
        video_hash=vhash,
        epoch_id=epoch_dir.name,
        run_id="r-nl",
        t_start=0.0,
        t_end=10.0,
        modality="video",
        worker_name="scene_summary",
        model_tag="m1",
        source_artifact_id="sc_ret_nl",
        promotion_status="rejected",
    )
    ledger.log_frame(
        video_hash=vhash,
        epoch_id=epoch_dir.name,
        run_id="r-nl",
        t_start=10.0,
        t_end=20.0,
        modality="video",
        worker_name="scene_summary",
        model_tag="m1",
        source_artifact_id="sc_act_nl",
        promotion_status="promoted",
    )
    ledger.close()
    with closing(sqlite3.connect(ledger_path)) as conn, conn:
        UCFLedgerClient.insert_status_transition(
            conn,
            old_status="promoted",
            new_status="rejected",
            tool_name="ucf_retire_scene",
            video_hash=vhash,
            epoch_id=epoch_dir.name,
            scope=f"scene_retirement:{canonical_ret_sid}",
            evidence={
                "kind": "scene_retirement",
                "version": 1,
                "scene_id": canonical_ret_sid,
                "aliases": [canonical_ret_sid, "sc_ret_nl"],
                "video_hash": vhash,
                "epoch_id": epoch_dir.name,
                "start": 0.0,
                "end": 10.0,
                "frame_ids": [fid],
                "vectors": [],
            },
            frame_ids=[fid],
        )

    qi = KnowledgeGraphNLQuery(cfg=cfg)
    people = qi.entity_lookup(entity_type="person")
    assert [p["name"] for p in people] == ["Active Speaker"]

    # 3. Non-loopback LLM URL is rejected; loopback uses Session(trust_env=False)
    bad_cfg = {**cfg, "llm": {"api_url": "https://api.example.com/v1/chat/completions"}}
    qi_bad = KnowledgeGraphNLQuery(cfg=bad_cfg)
    with pytest.raises(ValueError, match="non-loopback"):
        qi_bad._call_llm("sys", "usr")

    observed_trust_env: List[bool] = []

    class DummySession:
        def __init__(self) -> None:
            self.trust_env = True

        def post(self, url: str, **kwargs: Any) -> Any:
            observed_trust_env.append(self.trust_env)
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "ok"}}]},
            )

        def close(self) -> None:
            return None

    monkeypatch.setattr("cli.nl_query.requests.Session", DummySession)
    assert qi._call_llm("sys", "usr") == "ok"
    assert observed_trust_env == [False]


# ---------------------------------------------------------------------------
# RS-06 & RS-07: retrieval_events regex + QdrantClient.stats passive + loopback
# ---------------------------------------------------------------------------
def test_rs06_retrieval_context_regex_accepts_dotted_and_rejects_backslash() -> None:
    from steps.common.retrieval_events import normalize_retrieval_context

    assert normalize_retrieval_context("human.custom_ui") == "human.custom_ui"
    assert normalize_retrieval_context("system.audit_job") == "system.audit_job"
    assert normalize_retrieval_context("agent.planner.v2") == "agent.planner.v2"
    assert normalize_retrieval_context(r"agent\.bad") == "unknown"


def test_rs07_qdrant_stats_is_passive_and_mini_agent_disables_env_proxies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agents.mini_agent_client import MiniAgentClient
    from steps.common.qdrant_client import QdrantClient, QdrantConfig

    monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))

    methods_called: List[str] = []

    class FakeSession:
        def get(self, url: str, timeout: float = 3.0) -> Any:
            methods_called.append("GET")
            return SimpleNamespace(status_code=404, json=lambda: {})

        def put(self, url: str, **kwargs: Any) -> Any:
            methods_called.append("PUT")
            raise AssertionError("QdrantClient.stats() must never PUT to create a collection")

    qc = QdrantClient(QdrantConfig(host="http://127.0.0.1:6333", collection="absent_col", dim=384))
    qc.session = FakeSession()  # type: ignore[assignment]
    st = qc.stats()
    assert st["available"] is False
    assert st["exists"] is False
    assert methods_called == ["GET"]

    # Verify MiniAgentClient._qdrant_http_request routes through build_qdrant_session (trust_env=False)
    captured_trust_env: List[bool] = []

    class CaptureAdapterSession:
        def __init__(self) -> None:
            self.trust_env = False

        def request(self, method: str, url: str, **kwargs: Any) -> Any:
            captured_trust_env.append(self.trust_env)
            return SimpleNamespace(status_code=200, text="{}", json=lambda: {"result": []})

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "steps.common.qdrant_client.build_qdrant_session",
        lambda host: CaptureAdapterSession(),
    )
    mac = MiniAgentClient(profile="safe", config=_make_epoch_cfg(tmp_path / "epoch-rs07"))
    resp = mac._qdrant_http_request("get", "http://127.0.0.1:6333", "http://127.0.0.1:6333/collections")
    assert resp.status_code == 200
    assert captured_trust_env == [False]


# ---------------------------------------------------------------------------
# ST-04, ST-05 & VS-05: temporal_search dict labels, semantic_episode,
# narrative_summarizer grounding/ASR restriction & Ollama unload
# ---------------------------------------------------------------------------
def test_st04_temporal_search_dict_labels_no_path_leak_and_semantic_episode_clustering(
    tmp_path: Path,
) -> None:
    from lib.knowledge_graph import KnowledgeGraph
    from retrieval.temporal_reasoning import temporal_search
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from steps.common.memory import _connect

    epoch_dir = tmp_path / "epoch-st04"
    cfg = _make_epoch_cfg(epoch_dir)
    cfg["qdrant"]["enabled"] = False

    vh_a = "1" * 64
    vh_b = "2" * 64
    ledger_path = Path(cfg["paths"]["ucf_db_path"])
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = UCFLedgerClient(str(ledger_path))
    ledger.init_schema()
    for vh, sid, st, en in [
        (vh_a, "sc_a1", 0.0, 10.0),
        (vh_a, "sc_a2", 12.0, 22.0),
        (vh_b, "sc_b1", 5.0, 15.0),
    ]:
        ledger.log_frame(
            video_hash=vh,
            epoch_id=epoch_dir.name,
            run_id="r-st04",
            t_start=st,
            t_end=en,
            modality="video",
            worker_name="scene_summary",
            model_tag="m1",
            source_artifact_id=sid,
            promotion_status="promoted",
        )
    ledger.close()

    with KnowledgeGraph(cfg["paths"]["knowledge_graph_db"]) as kg:
        kg.add_media_node("video", "video_a.mp4", scene_id="sc_a1", timestamp_start=0.0, timestamp_end=10.0)
        kg.add_media_node("video", "video_a.mp4", scene_id="sc_a2", timestamp_start=12.0, timestamp_end=22.0)
        kg.add_media_node("video", "video_b.mp4", scene_id="sc_b1", timestamp_start=5.0, timestamp_end=15.0)

    with closing(_connect(cfg["paths"]["db_path"])) as conn, conn:
        meta_a1 = json.dumps(
            {
                "summary": "<ref>Birthday cake</ref><box>[10,20,30,40]</box> on table",
                "objects": [
                    {"label": "cake", "confidence": 0.94, "source_path": "/private/secret/frame_0001.jpg"}
                ],
                "entities": [{"name": "candle", "source_path": "/private/secret/frame_0001.jpg"}],
            }
        )
        meta_a2 = json.dumps(
            {
                "summary": "Cutting the birthday cake together",
                "objects": [{"label": "cake", "confidence": 0.91}],
            }
        )
        meta_b1 = json.dumps(
            {
                "summary": "Unrelated outdoor bicycle scene with cake sign",
                "objects": [{"label": "cake", "confidence": 0.80}],
            }
        )
        conn.execute(
            "INSERT INTO scenes (id, video_hash, start, end, meta, created_at) VALUES ('sc_a1', ?, 0.0, 10.0, ?, 'now')",
            (vh_a, meta_a1),
        )
        conn.execute(
            "INSERT INTO scenes (id, video_hash, start, end, meta, created_at) VALUES ('sc_a2', ?, 12.0, 22.0, ?, 'now')",
            (vh_a, meta_a2),
        )
        conn.execute(
            "INSERT INTO scenes (id, video_hash, start, end, meta, created_at) VALUES ('sc_b1', ?, 5.0, 15.0, ?, 'now')",
            (vh_b, meta_b1),
        )
        vec_same = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32).tobytes()
        vec_diff = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32).tobytes()
        conn.execute(
            "INSERT INTO embeddings (hash, faiss_id, source_path, modality, scene_id, created_at, vector) "
            "VALUES ('e_a1', NULL, '', 'text', 'sc_a1', 'now', ?)",
            (vec_same,),
        )
        conn.execute(
            "INSERT INTO embeddings (hash, faiss_id, source_path, modality, scene_id, created_at, vector) "
            "VALUES ('e_a2', NULL, '', 'text', 'sc_a2', 'now', ?)",
            (vec_same,),
        )
        conn.execute(
            "INSERT INTO embeddings (hash, faiss_id, source_path, modality, scene_id, created_at, vector) "
            "VALUES ('e_b1', NULL, '', 'text', 'sc_b1', 'now', ?)",
            (vec_diff,),
        )

    # 1. Chronological interleaves strictly by start_time: sc_a1 (0s), sc_b1 (5s), sc_a2 (12s)
    chrono = temporal_search(entities=["cake"], grouping="chronological", config=cfg)
    assert [r["scene_id"] for r in chrono["results"]] == ["sc_a1", "sc_b1", "sc_a2"]

    # 2. Semantic episode keeps contiguous coherent episode [sc_a1, sc_a2] together ahead of sc_b1
    episodic = temporal_search(entities=["cake"], grouping="semantic_episode", config=cfg)
    assert [r["scene_id"] for r in episodic["results"]] == ["sc_a1", "sc_a2", "sc_b1"]

    # 3. No source_path or grounding markup leaks into entities, visual_tags, or summary
    first = episodic["results"][0]
    serialized = json.dumps(first)
    assert "/private/secret" not in serialized
    assert "<ref>" not in serialized
    assert "<box>" not in serialized
    assert "cake" in first["evidence"]["visual_tags"]


def test_st05_and_vs05_narrative_summarizer_withholds_restricted_asr_and_unloads_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import retrieval.narrative_summarizer as ns_mod

    fake_search_payload = {
        "results": [
            {
                "scene_id": "sc_narr_1",
                "timestamp_label": "00:00:00",
                "start_time": 0.0,
                "end_time": 8.0,
                "source_file": "clip.mp4",
                "entities": [{"label": "<ref>guitar</ref><box>[1,2,3,4]</box>"}],
                "summary": "<ref>Playing acoustic guitar</ref><box>[10,10,50,50]</box> indoors.",
                "transcript_restricted": True,
                "evidence": {
                    "transcript": "HALLUCINATED SECRET TRANSCRIPT THAT MUST BE WITHHELD",
                    "transcript_restricted": True,
                },
            }
        ],
        "warnings": [],
    }
    monkeypatch.setattr(ns_mod, "temporal_search", lambda **kwargs: fake_search_payload)

    captured_prompts: List[str] = []
    unload_calls: List[Any] = []

    class FakeLLMClient:
        def __init__(self, **kwargs: Any) -> None:
            self.available = True

        def check_all_health(self) -> Dict[str, Any]:
            return {"Llama3.2-Ollama": SimpleNamespace(is_healthy=True)}

        def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
            captured_prompts.append(messages[1]["content"])
            return {
                "choices": [
                    {
                        "message": {
                            "content": "[Scene 1] <ref>Playing acoustic guitar</ref><box>[1,2,3,4]</box> indoors."
                        }
                    }
                ]
            }

        def get_active_model(self) -> str:
            return "Llama3.2-Ollama"

    monkeypatch.setattr(ns_mod, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(ns_mod, "build_llm_models", lambda _cfg: [])
    monkeypatch.setattr(
        ns_mod, "_unload_ollama_model_if_used", lambda c: unload_calls.append(c)
    )

    out = ns_mod.synthesize_narrative(summary_style="narrative", config={})
    assert out["status"] == "success"
    assert len(captured_prompts) == 1
    assert "HALLUCINATED SECRET TRANSCRIPT" not in captured_prompts[0]
    assert "<ref>" not in captured_prompts[0]
    assert "<box>" not in captured_prompts[0]
    assert "<ref>" not in out["summary"]
    assert "<box>" not in out["summary"]
    assert len(unload_calls) == 1

    # Also verify _unload_ollama_model_if_used runs in finally when client.chat raises!
    class RaisingLLMClient(FakeLLMClient):
        def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
            raise RuntimeError("simulated ollama crash mid-generation")

    monkeypatch.setattr(ns_mod, "LLMClient", RaisingLLMClient)
    err_out = ns_mod.synthesize_narrative(summary_style="narrative", config={})
    assert err_out["status"] == "llm_unavailable"
    assert len(unload_calls) == 2


def test_rs02_reject_ucf_frames_surfaces_dematerialization_failure_and_reconciles(
    scene_promotion: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from steps.common.memory import _connect

    root, config, client = scene_promotion
    vh, sid = stage_source(root, config, "movie_reject_err")
    scope = {"video_hash": vh, "epoch_id": root.name}

    val_res, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, val_res

    # Seed a stale unpromoted scene row in memory.db so dematerialization has concrete work:
    with closing(_connect(str(root / "memory.db"))) as conn, conn:
        conn.execute(
            "INSERT INTO scenes (id, video_hash, start, end, meta, created_at) VALUES (?, ?, 0.0, 5.0, '{}', 'now')",
            (sid, vh),
        )

    orig_demat = client._dematerialize_active_views
    fail_demat = {"fail": True}

    def flaky_demat(*args: Any, **kwargs: Any) -> None:
        if fail_demat["fail"]:
            raise RuntimeError("simulated sqlite lock on memory.db")
        return orig_demat(*args, **kwargs)

    monkeypatch.setattr(client, "_dematerialize_active_views", flaky_demat)

    rej_res, rc = confirmed(client, "reject_ucf_frames", {**scope, "reason": "bad ingest"})
    assert rc == 1, rej_res
    assert rej_res["output"]["status"] == "rejected_committed_sync_pending"
    assert rej_res["output"]["outbox"]["delivery_state"] == "pending"
    # Scene is still in memory.db until dematerialization succeeds on reconcile:
    with closing(sqlite3.connect(root / "memory.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenes WHERE id = ?", (sid,)).fetchone()[0] == 1

    fail_demat["fail"] = False
    rec_res, rc = confirmed(client, "reconcile_ucf_qdrant", scope)
    assert rc == 0, rec_res
    assert rec_res["output"]["status"] == "qdrant_sync_reconciled"
    with closing(sqlite3.connect(root / "memory.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM scenes WHERE id = ?", (sid,)).fetchone()[0] == 0


# ---------------------------------------------------------------------------
# ST-05 (promotion FTS), AS-01 Gap 2 (0-turn speaker_change_review),
# and AS-05 (audio_transcribe fallback cross-channel deduplication)
# ---------------------------------------------------------------------------
def test_st05_as01_gap2_and_as05_ucf_promotion_contracts(
    scene_promotion: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from steps.common.memory import _make_id
    from steps.video_scene_detect import step as scene_step

    root, config, client = scene_promotion
    monkeypatch.setattr(
        scene_step,
        "_detect_with_scenedetect",
        lambda *_: {
            "duration": 20.0,
            "scenes": [
                {"index": 0, "start": 0.0, "end": 10.0, "duration": 10.0, "confidence": 1.0},
                {"index": 1, "start": 10.0, "end": 20.0, "duration": 10.0, "confidence": 1.0},
            ],
        },
    )
    monkeypatch.setattr(scene_step, "_get_video_dimensions", lambda _: (20.0, 10.0, 64, 48))

    source = root.parent / "prom_contracts.mp4"
    source.write_bytes(b"promotion contracts test media")
    vhash = hashlib.sha256(source.read_bytes()).hexdigest()
    out_detect = scene_step.video_scene_detect({"source_path": str(source), "video_hash": vhash}, config)
    assert out_detect["scene_meta"]["status"] == "ok"

    sid_0 = _make_id("scene", [vhash, "0.000", "10.000"])
    sid_1 = _make_id("scene", [vhash, "10.000", "20.000"])

    manifest_dir = root / "processing" / "prom_contracts" / "video"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "scene_manifest.json").write_text(
        json.dumps(
            {
                "video_hash": vhash,
                "scenes": [
                    {
                        "scene_id": sid_0,
                        "video_id": vhash,
                        "index": 0,
                        "start": 0.0,
                        "end": 10.0,
                        "duration": 10.0,
                        "keyframe": {"ocr_text": "<ref>Quiet room</ref><box>[0,0,10,10]</box>"},
                        "audio": {
                            "speaker_change_review": {
                                "required": True,
                                "reasons": ["diarization_turns_without_words"],
                            },
                            "transcription_coverage": {
                                "status": "completed",
                                "regions": [
                                    {
                                        "outcome": "text_returned",
                                        "quality_flags": ["high_no_speech_prob"],
                                    }
                                ],
                            },
                        },
                    },
                    {
                        "scene_id": sid_1,
                        "video_id": vhash,
                        "index": 1,
                        "start": 10.0,
                        "end": 20.0,
                        "duration": 10.0,
                        "keyframe": {"caption": "Conversation at table"},
                        "audio": {
                            "speaker_change_review": {
                                "required": False,
                                "reasons": [],
                            }
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    ledger = UCFLedgerClient(str(root / "ucf/ucf_ledger.db"))
    # Scene 0 summary + restricted raw transcript
    ledger.log_frame(
        video_hash=vhash,
        epoch_id=root.name,
        run_id="run-p",
        t_start=0.0,
        t_end=10.0,
        modality="video",
        worker_name="image_caption",
        model_tag="qwen-vl",
        source_artifact_id=sid_0,
        payload={"caption": "<ref>Quiet room</ref><box>[0,0,10,10]</box>"},
    )
    ledger.log_frame(
        video_hash=vhash,
        epoch_id=root.name,
        run_id="run-p",
        t_start=1.0,
        t_end=3.0,
        modality="audio",
        worker_name="audio_transcribe",
        model_tag="whisper",
        occurrence_id="utt-restricted-0",
        source_artifact_id=sid_0,
        payload={
            "utterance_id": "utt-restricted-0",
            "text": "UNVERIFIEDWHISPERNOISETOKEN",
            "asr_restricted": True,
        },
    )

    # Scene 1 stereo duplicate utterances on channel 0 and channel 1 + a second distinct utterance
    ledger.log_frame(
        video_hash=vhash,
        epoch_id=root.name,
        run_id="run-p",
        t_start=10.0,
        t_end=20.0,
        modality="video",
        worker_name="image_caption",
        model_tag="qwen-vl",
        source_artifact_id=sid_1,
        payload={"caption": "Conversation at table"},
    )
    ledger.log_frame(
        video_hash=vhash,
        epoch_id=root.name,
        run_id="run-p",
        t_start=11.0,
        t_end=13.0,
        modality="audio",
        worker_name="audio_transcribe",
        model_tag="whisper",
        occurrence_id="utt-ch0",
        source_artifact_id=sid_1,
        payload={
            "utterance_id": "utt-ch0",
            "channel": 0,
            "text": "Happy birthday everyone",
            "confidence": 0.92,
        },
    )
    ledger.log_frame(
        video_hash=vhash,
        epoch_id=root.name,
        run_id="run-p",
        t_start=11.05,
        t_end=13.02,
        modality="audio",
        worker_name="audio_transcribe",
        model_tag="whisper",
        occurrence_id="utt-ch1",
        source_artifact_id=sid_1,
        payload={
            "utterance_id": "utt-ch1",
            "channel": 1,
            "text": "Happy birthday everyone!",
            "confidence": 0.88,
        },
    )
    ledger.log_frame(
        video_hash=vhash,
        epoch_id=root.name,
        run_id="run-p",
        t_start=15.0,
        t_end=17.0,
        modality="audio",
        worker_name="audio_transcribe",
        model_tag="whisper",
        occurrence_id="utt-distinct",
        source_artifact_id=sid_1,
        payload={
            "utterance_id": "utt-distinct",
            "channel": 0,
            "text": "Thank you so much",
            "confidence": 0.95,
        },
    )
    ledger.close()

    scope = {"video_hash": vhash, "epoch_id": root.name}
    val_res, rc = confirmed(client, "validate_ucf_frames", scope)
    assert rc == 0, val_res
    prom_res, _ = confirmed(client, "promote_ucf_to_memory", scope)
    assert prom_res["output"]["status"] == "promotion_committed_sync_pending", prom_res

    # Verify ST-05: restricted transcript NOT indexed into scene_text_fts, grounding markup stripped
    with closing(sqlite3.connect(root / "memory.db")) as conn:
        fts_rows = conn.execute(
            "SELECT content_type, text FROM scene_text_fts WHERE scene_id = ?",
            (sid_0,),
        ).fetchall()
        fts_text_joined = " ".join(r[1] or "" for r in fts_rows)
        assert "Quiet room" in fts_text_joined
        assert "<ref>" not in fts_text_joined
        assert "UNVERIFIEDWHISPERNOISETOKEN" not in fts_text_joined

        # Verify AS-05: stereo duplicate collapsed into 1 row + 1 distinct utterance = 2 linear segments in scene 1
        seg_rows = conn.execute(
            "SELECT meta FROM segments WHERE video_hash = ? AND start >= 10.0 ORDER BY start ASC",
            (vhash,),
        ).fetchall()
        seg_texts = [json.loads(r[0]).get("text", "") for r in seg_rows]
        assert len(seg_texts) == 2
        assert "happy birthday everyone" in seg_texts[0].lower()
        assert "thank you so much" in seg_texts[1].lower()

    # Verify AS-01 Gap 2: 0-turn scene without speaker_merge frames still persists speaker_change_review on KG scene node
    with closing(sqlite3.connect(root / "knowledge_graph.db")) as conn:
        sc_node = conn.execute(
            "SELECT properties FROM nodes WHERE node_type = 'scene' AND name = ?",
            (sid_0,),
        ).fetchone()
        assert sc_node is not None
        props = json.loads(sc_node[0])
        assert props["speaker_change_review"] == {
            "required": True,
            "reasons": ["diarization_turns_without_words"],
        }
        speaker_nodes = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE node_type IN ('speaker', 'speaker_pattern')"
        ).fetchone()[0]
        assert speaker_nodes == 0
