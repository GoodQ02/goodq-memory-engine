from steps.video_ingest.step import _summarize_video


def test_video_ingest_summary_filters_placeholder_audio_entities():
    result = _summarize_video(
        {
            "video": "sample.mp4",
            "video_hash": "video_hash",
            "frames": [],
            "scenes": [],
            "audio": {
                "tags": ["Apartment", "Well"],
                "entities": ["SPEAKER_00", "FACE_1", "Jerry", "Well"],
            },
        }
    )

    assert result["tags_top"] == [("Apartment", 1)]
    assert result["entities_top"] == [("Jerry", 1)]


def test_ingestion_preserves_transcript_and_summary_vectors_for_same_scene(monkeypatch, tmp_path):
    import json
    import sqlite3
    import uuid
    from types import SimpleNamespace

    import numpy as np

    from cli import run_ingestion
    from steps.common.memory import to_faiss_id
    from steps.common.qdrant_client import GOODQ_POINT_ID_NAMESPACE

    for name in ("GOODQ_REQUIRE_WSL_AUDIO", "GOODQ_REQUIRE_GPU"):
        monkeypatch.setenv(name, "0")
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "BASELINE")
    monkeypatch.setenv("GOODQ_RUN_ID", "same-scene-vectors")
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"synthetic media extraction fixture")
    audio = tmp_path / "scene.wav"
    audio.write_bytes(b"synthetic transcription worker fixture")
    db_dir = tmp_path / "epoch"
    cfg = {
        "paths": {
            "data_root": str(tmp_path),
            "db_dir": str(db_dir),
            "db_path": str(db_dir / "memory.db"),
            "processing": str(tmp_path / "processing"),
        },
        "phase6": {"enabled": False},
        "knowledge_graph": {"enabled": False},
        "qdrant": {"host": "http://fixture.invalid", "collections": {"text": "test_text"}},
    }
    stored_scenes = {
        "scenes": [{"id": "scene_0000", "start": 0.0, "end": 5.0,
                    "meta": {"index": 0, "duration": 5.0, "confidence": 1.0}}],
        "detection_meta": {},
    }
    inserted = []
    qdrant_points = {}
    worker_calls = []
    transcript_id = "a" * 64

    class SummaryEncoder:
        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 384), dtype="float32")

    class Router:
        stores = {"qdrant": SimpleNamespace(client=SimpleNamespace(
            cfg=SimpleNamespace(collection="test_text", enabled=False)))}

        def insert(self, points):
            inserted.extend(points)
            for point in points:
                point_id = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, point["id"]))
                qdrant_points[point_id] = {"id": point_id, "payload": dict(point["payload"])}
            return {"qdrant": True, "faiss": False}

    async def model_worker(env_name, step_name, item, cfg_json, **kwargs):
        worker_calls.append(step_name)
        outputs = {}
        if step_name == "audio_transcribe_local":
            outputs = {"transcript": "A person says hello.", "transcript_meta": {"status": "ok"}}
        elif step_name == "text_embed":
            assert item["modality"] == "audio_transcript"
            outputs = {"embedding_meta": {
                "status": "ok", "embedding_id": transcript_id,
                "faiss_id": to_faiss_id(transcript_id), "qdrant_committed": True,
                "vector_collection": "test_text",
            }}
        return {"status": "ok", "step_name": step_name, "outputs": outputs}

    async def extract_frame(*args, **kwargs):
        return {"path": str(tmp_path / "frame.jpg"), "data": {"caption": "A person waves."}}

    def qdrant_request(url, json, **kwargs):
        if url.endswith("/payload"):
            for point_id in json["points"]:
                if point_id in qdrant_points:
                    qdrant_points[point_id]["payload"].update(json["payload"])
            result = {}
        elif url.endswith("/scroll"):
            result = {"points": list(qdrant_points.values()) if "/test_text/" in url else [],
                      "next_page_offset": None}
        else:
            result = [qdrant_points[point_id] for point_id in json["ids"] if point_id in qdrant_points]
        return SimpleNamespace(status_code=200, json=lambda: {"result": result})

    monkeypatch.setattr(run_ingestion, "CONTROL_AGENT_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "PROGRESS_TRACKING_AVAILABLE", False)
    monkeypatch.setattr(run_ingestion, "resolve_ffmpeg", lambda *_: "fixture-ffmpeg")
    monkeypatch.setattr(run_ingestion, "list_scenes_for_video", lambda *a, **k: stored_scenes)
    monkeypatch.setattr(run_ingestion, "_detect_scenes", lambda *a, **k: {
        "scenes": [{"index": 0, "start": 0.0, "end": 5.0, "duration": 5.0, "confidence": 1.0}], "meta": {},
    })
    monkeypatch.setattr(run_ingestion, "_is_video_phase6_complete", lambda *a, **k: True)
    monkeypatch.setattr(run_ingestion, "_extract_audio_chunk", lambda *a, **k: audio)
    monkeypatch.setattr(run_ingestion, "_process_frame_async", extract_frame)
    monkeypatch.setattr(run_ingestion, "_run_step_async", model_worker)
    monkeypatch.setattr("steps.text_embed.step._load_st", lambda: SummaryEncoder())
    monkeypatch.setattr("steps.common.memory_manager.build_memory_router", lambda _cfg: Router())
    monkeypatch.setattr("requests.post", qdrant_request)

    output = tmp_path / "results.json"
    run_ingestion.run_with_config(
        cfg=cfg, input_file=video, output=output, workspace=tmp_path / "workspace", max_videos=1,
    )

    result = json.loads(output.read_text(encoding="utf-8"))[0]
    assert "audio_transcribe_local" in worker_calls
    assert "text_embed" in worker_calls
    assert result["scenes"][0]["audio"]["transcript"] == "A person says hello."
    summary = next(point for point in inserted if point["payload"].get("embedding_source") == "scene_summary")
    with sqlite3.connect(db_dir / "ucf" / "ucf_ledger.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM context_frames WHERE vector_dim = 384 ORDER BY frame_id").fetchall()
    assert len(rows) == 2, "same-span transcript and scene summary must retain separate UCF vector rows"
    by_worker = {row["worker_name"]: row for row in rows}
    assert set(by_worker) == {"text_embed", "scene_summary_embed"}
    assert {row["modality"] for row in rows} == {"text"}
    assert {(row["t_start"], row["t_end"]) for row in rows} == {(0.0, 5.0)}
    assert by_worker["text_embed"]["vector_key"] == transcript_id
    assert json.loads(by_worker["text_embed"]["payload"])["faiss_id"] == to_faiss_id(transcript_id)
    assert by_worker["scene_summary_embed"]["vector_key"] == str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, summary["id"]))
    assert json.loads(by_worker["scene_summary_embed"]["payload"])["embedding_id"] == summary["id"]
    assert summary["payload"]["worker_name"] == "scene_summary_embed"

    # Recreate the historical collision in this disposable ledger, then resume
    # through the real cached-audio path without migrating or relogging audio.
    ledger_path = db_dir / "ucf" / "ucf_ledger.db"
    with sqlite3.connect(ledger_path) as conn:
        conn.execute("DELETE FROM context_frames WHERE worker_name = 'text_embed'")
        conn.execute("UPDATE context_frames SET worker_name = 'text_embed' WHERE worker_name = 'scene_summary_embed'")
    checkpoint_path = tmp_path / "processing/sample/progressive_ingestion_state.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["windows"]["0"]["window_status"] = "failed"
    checkpoint["windows"]["0"]["persistence_targets"]["vectors"] = "failed"
    checkpoint["windows"]["0"]["failed_targets"] = ["vectors"]
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    worker_calls.clear()
    run_ingestion.run_with_config(
        cfg=cfg, input_file=video, output=output, workspace=tmp_path / "workspace", max_videos=1,
    )
    assert "audio_transcribe_local" not in worker_calls
    assert "text_embed" not in worker_calls
    with sqlite3.connect(ledger_path) as conn:
        resumed_rows = conn.execute(
            "SELECT worker_name, vector_key FROM context_frames WHERE vector_dim = 384"
        ).fetchall()
    summary_key = str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, summary["id"]))
    assert set(resumed_rows) == {("text_embed", summary_key), ("scene_summary_embed", summary_key)}

    # Media discovery is mocked above; register its fixture metadata so the
    # real strict validator can reconcile the resumed producer records.
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from scripts.ucf.validate_ucf_epoch import run_validation

    ledger = UCFLedgerClient(str(ledger_path))
    ledger.register_media(video_hash=result["video_id"], file_path=str(video), duration=5.0,
                          fps=1.0, width=1, height=1)
    ledger.log_frame(
        video_hash=result["video_id"], epoch_id="epoch", run_id="fixture-discovery",
        t_start=0.0, t_end=5.0, modality="video", worker_name="video_scene_detect",
        model_tag="fixture", source_artifact_id=summary["payload"]["scene_id"],
        raw_ref=str(tmp_path / "processing/sample/video/scene_manifest.json"),
        payload={"scene_index": 0, "duration": 5.0}, promotion_status="staged",
    )
    ledger.close()
    assert run_validation(mode="strict", config=cfg, report_dir=tmp_path / "validation") == 0
