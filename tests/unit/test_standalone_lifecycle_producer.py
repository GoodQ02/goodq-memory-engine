"""Real Watchdog/JSON dispatcher/UCF persistence with deterministic compute."""
from contextlib import closing
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import wave

from PIL import Image
import pytest

from steps.common.memory import _make_id
from tests.unit.test_watchdog_safety import standalone_audio_dispatch


@pytest.fixture
def standalone_runtime(standalone_audio_dispatch, monkeypatch, tmp_path):
    from cli import step_runner
    from cli import run_ingestion
    from configs import python_paths
    from steps.common import progress_tracker

    processor, _audio, observed, cfg, bridge = standalone_audio_dispatch
    processor._cfg_base["ingestion_isolation"] = True
    monkeypatch.setattr(progress_tracker, "LOGS_DIR", tmp_path / "progress")
    tracker = object.__new__(progress_tracker.ProgressTracker)
    tracker.__init__()
    monkeypatch.setattr(progress_tracker, "_tracker", tracker)
    monkeypatch.setattr(progress_tracker, "get_tracker", lambda: tracker)
    for method in ("start_processing", "finish_processing", "add_error"):
        monkeypatch.setattr(progress_tracker, method, getattr(tracker, method))
    calls = []

    def compute(step, item, resolved):
        calls.append((step, dict(item), resolved))
        if step == "image_caption":
            return {"caption": "A red box", "caption_meta": {"status": "ok"}}
        if step == "object_detect":
            return {"objects": [{"label": "box", "score": .8, "bbox": [0, 0, 4, 4]},
                                {"label": "chair", "score": .7, "bbox": [4, 4, 8, 8]}]}
        if step == "text_embed":
            return {"embedding_meta": {"status": "ok", "embedding_id": "a" * 64,
                "faiss_id": 1, "vector_collection": "test_text", "qdrant_committed": False}}
        if step == "audio_embed_clap":
            return {"clap_meta": {"status": "ok", "embedding_id": "b" * 64,
                "faiss_id": 2, "faiss_committed": True, "qdrant_committed": False}}
        if step == "pdf_text":
            return {"pdf_text": "A document parsed as text."}
        if step == "audio_transcribe_local":
            return {"transcript": "A bounded audio transcript", "segments": [{"start": 0, "end": 1, "text": "A bounded audio transcript"}],
                    "transcript_meta": {"status": "ok"}}
        return {}

    monkeypatch.setattr(step_runner, "run_step", compute)
    # OCR and object detection use the dedicated direct-interpreter launcher. Retain the real
    # JSON dispatcher boundary in this compute-fixture test, as the conda
    # transport fixture does for every other worker. Never invoke real models.
    monkeypatch.setattr(python_paths, "get_env_python", lambda _: Path(sys.executable))
    monkeypatch.setattr(run_ingestion, "_observer", lambda: None)
    monkeypatch.setattr(run_ingestion, "_control_agent_runtime_enabled", lambda: False)

    class OCRChild:
        pid = 424242
        returncode = None

        def __init__(self, cmd, **kwargs):
            assert cmd[cmd.index("--step") + 1] in {"image_ocr", "object_detect", "image_caption"}
            self.cmd = cmd

        def communicate(self, timeout=None):
            output = io.StringIO()
            with monkeypatch.context() as child, contextlib.redirect_stdout(output):
                child.setattr(sys, "argv", ["step_runner", *self.cmd[2:]])
                try:
                    step_runner.main()
                except Exception as exc:
                    self.returncode = 1
                    return output.getvalue(), str(exc)
            self.returncode = 0
            return output.getvalue(), ""

    monkeypatch.setattr(run_ingestion.subprocess, "Popen", OCRChild)
    return processor, calls, cfg, bridge


def source_file(tmp_path, kind, name=None):
    extension = {"image": ".png", "document": ".txt", "audio": ".wav"}[kind]
    path = tmp_path / (name or f"evidence{extension}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "image":
        Image.new("RGB", (8, 8), "red").save(path)
    elif kind == "audio":
        with wave.open(str(path), "wb") as stream:
            stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            stream.writeframes(b"\0\0" * 16000)
    else:
        path.write_text("UNIQUE DOCUMENT CONTENT", encoding="utf-8")
    return path


def ledger_rows(cfg):
    with closing(sqlite3.connect(Path(cfg["paths"]["db_dir"]) / "ucf" / "ucf_ledger.db")) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute("SELECT * FROM context_frames")]


@pytest.mark.parametrize("kind", ["image", "document", "audio"])
def test_standalone_actual_caller_retains_source_artifacts_and_staged_evidence(standalone_runtime, tmp_path, kind):
    processor, calls, cfg, _bridge = standalone_runtime
    source = source_file(tmp_path, kind)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    duration = 1.0 if kind == "audio" else 0.0
    scene_id = _make_id("scene", [digest, "0.000", f"{duration:.3f}"])

    assert getattr(processor, f"ingest_{kind}")(source, f"standalone-{kind}") is True

    root = Path(cfg["paths"]["processing"]) / digest
    retained = root / f"{digest}{source.suffix}"
    assert retained.read_bytes() == source.read_bytes()
    assert all(item["scene_id"] == scene_id and item["video_hash"] == digest for _, item, _ in calls)
    assert all(resolved["ingestion_isolation"] is True for _, _, resolved in calls)
    manifest = json.loads((root / "video" / "scene_manifest.json").read_text(encoding="utf-8"))
    temporal = json.loads((root / "temporal_index.json").read_text(encoding="utf-8"))
    assert manifest["scenes"][0]["scene_id"] == temporal["segments"][0]["scene_id"] == scene_id
    assert manifest["source_kind"] == kind
    rows = ledger_rows(cfg)
    anchor, = [r for r in rows if r["worker_name"] == "standalone_source"]
    assert anchor["video_hash"] == digest and anchor["source_artifact_id"] == scene_id
    assert anchor["modality"] == {"image": "multimodal", "document": "text", "audio": "audio"}[kind]
    assert anchor["t_start"] == 0 and anchor["t_end"] == duration
    assert all(r["promotion_status"] == "staged" for r in rows)
    assert all(json.loads(r["payload"])["source_kind"] == kind for r in rows)
    assert all(Path(r["raw_ref"]).exists() for r in rows)
    assert not (Path(cfg["paths"]["db_dir"]) / "memory.db").exists()
    if kind == "document":
        assert manifest["scenes"][0]["document_text"] == "UNIQUE DOCUMENT CONTENT"
        assert "transcript" not in manifest["scenes"][0] and "ocr_text" not in manifest["scenes"][0]
        assert json.loads(anchor["payload"])["document_text"] == "UNIQUE DOCUMENT CONTENT"
    if kind == "image":
        assert len(manifest["scenes"][0]["keyframe"]["objects"]) == 2
        assert all(r["t_start"] == r["t_end"] == 0 for r in rows)
        assert not any(r["modality"] == "video" for r in rows)


def test_standalone_image_projects_ocr_provenance_and_dates_to_temporal_and_ledger(standalone_runtime, monkeypatch, tmp_path):
    from cli import step_runner

    processor, _calls, cfg, _bridge = standalone_runtime
    source = source_file(tmp_path, "image")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    original = step_runner.run_step
    evidence = {"status": "ok", "engine": "paddleocr-3.7-onnxruntime-cpu",
                "model_revision": "pinned-recognizer", "detector_revision": "pinned-detector",
                "accepted_regions": [{"text": "MAY 19 2002", "bbox": [0, 0, 7, 7],
                                      "confidence": 0.91, "confidence_kind": "recognizer_sequence_score"}],
                "date_evidence": [{"status": "explicit", "date": "2002-05-19",
                                   "raw_text": "MAY 19 2002", "region_index": 0, "sample_timestamp": 0.0}]}
    hints = {"explicit_dates": ["2002-05-19"], "months": ["may"], "first_seen_ts": {"2002-05-19": 0.0}}

    def compute(step, item, resolved):
        if step == "image_ocr":
            return {"ocr_text": "MAY 19 2002", "ocr_meta": evidence, "time_hints": hints}
        return original(step, item, resolved)

    monkeypatch.setattr(step_runner, "run_step", compute)
    assert processor.ingest_image(source, "paddle-image-projection") is True
    root = Path(cfg["paths"]["processing"]) / digest
    temporal = json.loads((root / "temporal_index.json").read_text(encoding="utf-8"))["segments"][0]
    manifest = json.loads((root / "video/scene_manifest.json").read_text(encoding="utf-8"))["scenes"][0]
    assert temporal["ocr_meta"] == manifest["keyframe"]["ocr_meta"] == evidence
    assert temporal["time_hints"] == hints
    row, = [row for row in ledger_rows(cfg) if row["worker_name"] == "image_ocr"]
    assert row["model_tag"] == evidence["engine"] and row["confidence"] == 0.91
    assert json.loads(row["payload"])["confidence_kind"] == "mean_recognizer_sequence_score"
    assert json.loads(row["payload"])["confidence_observation_count"] == 1
    assert json.loads(Path(row["raw_ref"]).read_text(encoding="utf-8")) == evidence


def test_same_name_different_bytes_separate_and_renamed_identical_share_identity(standalone_runtime, tmp_path):
    processor, _calls, cfg, _bridge = standalone_runtime
    first = source_file(tmp_path / "first", "document", "same.txt")
    second = source_file(tmp_path / "second", "document", "same.txt")
    second.write_text("DIFFERENT DOCUMENT", encoding="utf-8")
    renamed = tmp_path / "renamed.txt"
    renamed.write_bytes(first.read_bytes())
    for index, path in enumerate((first, second, renamed)):
        assert processor.ingest_document(path, f"identity-{index}") is True
    anchors = [r for r in ledger_rows(cfg) if r["worker_name"] == "standalone_source"]
    assert len(anchors) == 2
    assert len({r["source_artifact_id"] for r in anchors}) == 2
    assert {r["video_hash"] for r in anchors} == {hashlib.sha256(p.read_bytes()).hexdigest() for p in (first, second)}


def test_document_caller_retains_all_chunk_references_in_one_static_frame(standalone_runtime, monkeypatch, tmp_path):
    from cli import step_runner
    from steps.common.memory import to_faiss_id
    processor, _calls, cfg, _bridge = standalone_runtime
    source = source_file(tmp_path, "document")
    text = source.read_text()
    chunks = [{"chunk_index": index, "char_start": start, "char_end": end,
               "text": text[start:end], "token_count": 2,
               "embedding_id": key, "faiss_id": to_faiss_id(key)}
              for index, (start, end, key) in enumerate(((0, 15, "1" * 64), (7, len(text), "2" * 64)))]
    original = step_runner.run_step
    def compute(step, item, resolved):
        if step == "text_embed":
            return {"embedding_meta": {"status": "ok", "engine": "all-MiniLM-L6-v2",
                "embedding_chunks": chunks, "chunk_count": 2, "chunk_token_limit": 254,
                "text_length": len(text), "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "vector_collection": "test_text", "qdrant_committed": False}}
        return original(step, item, resolved)
    monkeypatch.setattr(step_runner, "run_step", compute)
    assert processor.ingest_document(source, "document-chunks") is True
    frame, = [row for row in ledger_rows(cfg) if row["worker_name"] == "text_embed"]
    assert frame["t_start"] == frame["t_end"] == 0 and frame["vector_key"] is None
    assert json.loads(frame["payload"])["embedding_chunks"] == chunks
    assert frame["promotion_status"] == "staged"
    assert frame["source_artifact_id"] == _make_id("scene", [hashlib.sha256(source.read_bytes()).hexdigest(), "0.000", "0.000"])


def test_document_embedding_error_is_not_persisted_as_completed_memory(standalone_runtime, monkeypatch, tmp_path):
    from cli import step_runner
    processor, _calls, cfg, _bridge = standalone_runtime
    source = source_file(tmp_path, "document")
    original = step_runner.run_step
    monkeypatch.setattr(step_runner, "run_step", lambda step, item, resolved:
        {"embedding_meta": {"status": "error", "error": "chunk write failed"}} if step == "text_embed"
        else original(step, item, resolved))
    with pytest.raises(RuntimeError, match="Document text embedding failed"):
        processor.ingest_document(source, "document-chunk-failure")
    root = Path(cfg["paths"]["processing"]) / hashlib.sha256(source.read_bytes()).hexdigest()
    assert (root / "failed_result.json").is_file()
    assert not (root / "temporal_index.json").exists()


def test_wsl_audio_continues_clap_text_and_staged_persistence(standalone_runtime, monkeypatch, tmp_path):
    from cli import watchdog
    processor, calls, cfg, bridge = standalone_runtime
    source = source_file(tmp_path, "audio")
    monkeypatch.setattr(watchdog, "wsl_audio_auto_enabled", lambda: True)
    monkeypatch.setattr(watchdog.shutil, "which", lambda _: "fixture-wsl")
    bridge.audio_unified_wsl2 = lambda *_a, **_k: {"status": "success", "transcript": "Speech from WSL",
        "segments": [{"start": 0, "end": 1, "text": "Speech from WSL"}], "transcript_meta": {"status": "success"}}
    assert processor.ingest_audio(source, "wsl-continuity") is True
    steps = [step for step, _, _ in calls]
    assert "audio_embed_clap" in steps and "text_embed" in steps
    assert "audio_transcribe_local" not in steps
    assert {"standalone_source", "audio_embed_clap", "text_embed", "audio_transcribe"}.issubset({r["worker_name"] for r in ledger_rows(cfg)})


@pytest.mark.parametrize("failure", ["worker", "ledger", "manifest"])
def test_failures_raise_and_preserve_retained_source_and_partial_evidence(standalone_runtime, monkeypatch, tmp_path, failure):
    from cli import step_runner, standalone_persistence
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    processor, _calls, cfg, _bridge = standalone_runtime
    source = source_file(tmp_path, "document")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    def fail(*_a, **_kw):
        raise RuntimeError(f"fixture {failure} failure")
    if failure == "worker":
        monkeypatch.setattr(step_runner, "run_step", fail)
    elif failure == "ledger":
        monkeypatch.setattr(UCFLedgerClient, "log_frame", fail)
    else:
        real_write = standalone_persistence.atomic_write_json
        def fail_manifest(path, payload):
            if Path(path).name == "scene_manifest.json":
                fail()
            return real_write(path, payload)
        monkeypatch.setattr(standalone_persistence, "atomic_write_json", fail_manifest)
    with pytest.raises(Exception, match="fixture"):
        processor.ingest_document(source, f"failed-{failure}")
    root = Path(cfg["paths"]["processing"]) / digest
    assert (root / f"{digest}.txt").read_bytes() == source.read_bytes()
    assert (root / "failed_result.json").exists()
    assert not (root / "temporal_index.json").exists()


def test_process_file_content_identity_survives_name_collisions_and_cleanup(standalone_runtime, tmp_path):
    processor, _calls, cfg, _bridge = standalone_runtime
    first = source_file(tmp_path / "first", "document", "same.txt")
    second = source_file(tmp_path / "second", "document", "same.txt")
    second.write_text("SECOND FILE WITH SAME NAME", encoding="utf-8")
    renamed = tmp_path / "renamed.txt"
    renamed.write_bytes(first.read_bytes())
    digests = []
    for source in (first, second, renamed):
        original = source.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        digests.append(digest)
        assert processor.process_file(source, digest) is True
        assert processor.registry.processed[digest]["status"] == "success"
        root = processor.processing_dir / digest
        assert (root / f"{digest}.txt").read_bytes() == original
        assert (root / "raw_result.json").exists()
        assert (root / "video" / "scene_manifest.json").exists()
        assert (root / "temporal_index.json").exists()
        assert not (processor.processing_dir / source.name).exists()
    assert digests[0] == digests[2] != digests[1]
    anchors = [r for r in ledger_rows(cfg) if r["worker_name"] == "standalone_source"]
    assert len(anchors) == 2


@pytest.mark.parametrize("failure", ["raw", "manifest", "ucf"])
def test_process_file_persistence_failures_are_failed_not_processed(standalone_runtime, monkeypatch, tmp_path, failure):
    from cli import standalone_persistence
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    processor, _calls, _cfg, _bridge = standalone_runtime
    source = source_file(tmp_path, "document")
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if failure == "ucf":
        def fail(*_a, **_kw):
            raise OSError("fixture ledger failure")
        monkeypatch.setattr(UCFLedgerClient, "log_frame", fail)
    else:
        real_write = standalone_persistence.atomic_write_json
        def fail_write(path, payload):
            if Path(path).name == {"raw": "raw_result.json", "manifest": "scene_manifest.json"}[failure]:
                raise OSError("fixture artifact failure")
            real_write(path, payload)
        monkeypatch.setattr(standalone_persistence, "atomic_write_json", fail_write)
    assert processor.process_file(source, digest) is False
    assert processor.registry.processed[digest]["status"] == "failed"
    root = processor.processing_dir / digest
    assert (root / f"{digest}.txt").read_bytes() == original
    assert (root / "failed_result.json").exists()
    assert not (root / "temporal_index.json").exists()


@pytest.mark.parametrize("kind,extension,total_steps", [
    ("image", "png", 13), ("document", "md", 7), ("document", "pdf", 7),
])
@pytest.mark.parametrize("failure", [None, "worker", "persistence"])
def test_standalone_process_file_reports_actual_progress(
    standalone_runtime, monkeypatch, tmp_path, kind, extension, total_steps, failure,
):
    from cli import standalone_persistence, step_runner
    from steps.common import progress_tracker

    processor, _calls, _cfg, _bridge = standalone_runtime
    tracker = progress_tracker.get_tracker()
    snapshots = []

    def record(stage):
        snapshots.append((stage, json.loads(tracker.progress_file.read_text(encoding="utf-8"))))

    prepare = standalone_persistence.prepare_source
    def prepare_source(*args):
        record("retain_source")
        return prepare(*args)
    monkeypatch.setattr(standalone_persistence, "prepare_source", prepare_source)

    compute = step_runner.run_step
    def run_step(step, item, resolved):
        record(step)
        if failure == "worker" and step == "text_embed":
            raise RuntimeError("fixture worker failure")
        return compute(step, item, resolved)
    monkeypatch.setattr(step_runner, "run_step", run_step)

    persist = standalone_persistence.persist_result
    def persist_result(*args):
        record("persist_result")
        if failure == "persistence":
            raise RuntimeError("fixture persistence failure")
        return persist(*args)
    monkeypatch.setattr(standalone_persistence, "persist_result", persist_result)

    source = source_file(tmp_path, kind, f"evidence.{extension}")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert processor.process_file(source, digest) is (failure is None)
    assert snapshots
    for stage, state in snapshots:
        assert state["status"] == "processing"
        assert state["current_file"] == source.name
        assert state["run_id"]
        assert state["current_step"] == stage
        assert state["total_steps"] == total_steps
        assert state["current_step_index"] == len(state["steps_completed"])
        assert state["progress_percent"] == int(len(state["steps_completed"]) / total_steps * 100)
        assert state["progress_percent"] < 100
    assert any(state["progress_percent"] > 0 for _, state in snapshots)

    final = json.loads(tracker.progress_file.read_text(encoding="utf-8"))
    completed = [step["name"] for step in final["steps_completed"]]
    assert completed[0] == "retain_source"
    if kind == "document":
        assert completed[1] == ("pdf_text" if extension == "pdf" else "read_document_text")
    if failure:
        assert final["status"] == "failed"
        assert final["progress_percent"] < 100
        assert final["errors"]
        assert "persist_result" not in completed
        if failure == "worker":
            assert "text_embed" not in completed
    else:
        assert final["status"] == "completed"
        assert final["progress_percent"] == 100
        assert len(completed) == total_steps
        assert completed[-1] == "persist_result"


@pytest.mark.parametrize("extension", ["txt", "md", "pdf"])
def test_process_file_empty_document_rejected_with_retained_evidence(standalone_runtime, monkeypatch, tmp_path, extension):
    from cli import step_runner
    processor, _calls, _cfg, _bridge = standalone_runtime
    source = tmp_path / f"empty.{extension}"
    source.write_bytes(b" \n")
    if extension == "pdf":
        monkeypatch.setattr(step_runner, "run_step", lambda *_a, **_kw: {"pdf_text": ""})
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert processor.process_file(source, digest) is False
    root = processor.processing_dir / digest
    assert (root / f"{digest}.{extension}").exists()
    assert (root / "failed_result.json").exists()
    assert not (root / "temporal_index.json").exists()
    assert "no usable text" in processor.registry.processed[digest]["error"]


def test_compressed_audio_duration_uses_resolved_ffprobe_path_before_dispatch(standalone_runtime, monkeypatch, tmp_path):
    from cli import standalone_persistence
    from steps.common.tool_resolver import ToolResolver
    import subprocess
    processor, calls, cfg, _bridge = standalone_runtime
    source = tmp_path / "compressed.mp3"
    source.write_bytes(b"compressed audio fixture; decoding is mocked")
    real_run = standalone_persistence.subprocess.run
    probes = []
    def run(cmd, **kwargs):
        if cmd[0] == "fixture-ffprobe":
            probes.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, '{"format":{"duration":"2.5"}}', "")
        return real_run(cmd, **kwargs)
    monkeypatch.setattr(ToolResolver, "resolve_tool", lambda _: {"found": True, "path": "fixture-ffprobe"})
    monkeypatch.setattr(standalone_persistence.subprocess, "run", run)
    assert processor.ingest_audio(source, "compressed-audio") is True
    assert len(probes) == 1
    assert all(item["end"] == 2.5 for _, item, _ in calls)
    anchor, = [r for r in ledger_rows(cfg) if r["worker_name"] == "standalone_source"]
    assert anchor["t_end"] == 2.5


@pytest.mark.parametrize("kind,visual_outcome", [
    ("image", "ok"), ("image", "no_objects"), ("image", "unavailable"),
    ("audio", None), ("document", None),
])
def test_watchdog_artifacts_reach_actual_scene_and_timeline_readers(
    standalone_runtime, monkeypatch, tmp_path, kind, visual_outcome,
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routes import scenes, timeline
    from api.utils import loaders

    processor, _calls, cfg, bridge = standalone_runtime
    if kind == "image":
        from cli import step_runner
        compute = step_runner.run_step
        visual_status = "unavailable" if visual_outcome == "unavailable" else "ok"
        caption_meta = {"status": visual_status, "engine": "blip"}
        detect_meta = {"status": visual_status, "engine": "opencv-dnn"}
        if visual_outcome == "unavailable":
            detect_meta["error"] = "fixture detector is unavailable"
        else:
            detect_meta["model"] = "fixture-detector"
        expected_caption = None if visual_outcome == "unavailable" else "A red image"
        expected_objects = ["box", "chair"] if visual_outcome == "ok" else []

        def visual_compute(step, item, resolved):
            result = compute(step, item, resolved)
            if step == "image_caption":
                return {"caption": expected_caption, "caption_meta": caption_meta}
            if step == "object_detect":
                return {"objects": result["objects"] if expected_objects else [], "detect_meta": detect_meta}
            return result

        monkeypatch.setattr(step_runner, "run_step", visual_compute)
    if kind == "audio":
        from cli import watchdog, step_runner
        monkeypatch.setattr(watchdog, "wsl_audio_auto_enabled", lambda: True)
        monkeypatch.setattr(watchdog.shutil, "which", lambda _: "fixture-wsl")
        bridge.audio_unified_wsl2 = lambda *_a, **_kw: {
            "status": "success", "transcript": "Claire asked about the party.",
            "segments": [{"start": 0, "end": 1, "text": "Claire asked about the party."}],
            "transcript_meta": {"status": "success"}, "emotion": "happy",
            "emotion_scores": {"happy": .4, "neutral": .35}, "emotion_status": "success",
            "speakers": ["speaker_0"], "speaker_count": 1, "diarization_status": "success",
            "speaker_voice_signatures": [{"speaker": "speaker_0"}],
            "speaker_voice_signature_meta": {"status": "success"},
        }
    if kind in {"audio", "document"}:
        from cli import step_runner
        compute = step_runner.run_step
        def enriched(step, item, resolved):
            if step == "sentiment":
                return {"sentiment": {"label": "POSITIVE", "score": .91}, "sentiment_meta": {"status": "ok"}}
            if step == "emotion_classify":
                return {"emotions": {"joy": .8}, "emotion_meta": {"status": "ok"}}
            if step == "audio_time_hints":
                return {"time_hints": {"explicit_dates": ["2001-12-16"]}}
            if step == "tagger":
                return {"ner_entities": [{"text": "Claire", "type": "PERSON", "score": .95}]}
            return compute(step, item, resolved)
        monkeypatch.setattr(step_runner, "run_step", enriched)
    source = source_file(tmp_path, kind)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert processor.process_file(source, digest) is True
    anchor, = [row for row in ledger_rows(cfg) if row["worker_name"] == "standalone_source"]
    for key in ("_DEFAULT_PROCESSING_ROOT", "_DEFAULT_PROCESSED_ROOT", "_DEFAULT_UCF_SCOPE"):
        monkeypatch.setattr(loaders, key, None)
    monkeypatch.setattr(loaders, "_DEFAULT_MEDIA_ROOTS", ())
    loaders.configure_from_cfg(cfg)
    app = FastAPI()
    for module in (scenes, timeline):
        monkeypatch.setattr(module, "_data_loader", None)
        app.include_router(module.router)
    with TestClient(app) as client:
        scene_url = f"/api/videos/{digest}/scenes/{anchor['source_artifact_id']}"
        assert client.get(scene_url).status_code == 404
        # Simulated promotion gate only; the real MiniAgent transition is tested separately.
        with closing(sqlite3.connect(Path(cfg["paths"]["db_dir"]) / "ucf/ucf_ledger.db")) as db, db:
            db.execute("UPDATE context_frames SET promotion_status='promoted' WHERE video_hash=?", (digest,))
        scene = client.get(scene_url)
        assert scene.status_code == 200
        segment = client.get(f"/api/videos/{digest}/timeline/full").json()["segments"][0]
        for result in (scene.json(), segment):
            if kind == "image":
                assert result["visual_caption"] == expected_caption
                assert result["objects"] == expected_objects
                assert result["caption_meta"] == caption_meta
                assert result["detect_meta"] == detect_meta
            else:
                assert result["sentiment_label"] == "POSITIVE"
                assert result["text_emotion_ranking"][0]["label"] == "joy"
                assert result["entities"][0]["text"] == "Claire"
                assert result["visible_people"] == []
                if kind == "document":
                    assert result["document_text"] == "UNIQUE DOCUMENT CONTENT"
                    assert result["transcript"] is None and result["audio_emotion"] is None
                    continue
                assert result["clap_meta"]["status"] == "ok"
                assert result["audio_emotion"] is None  # Below the existing promotion threshold.
                assert result["audio_emotion_scores"] == {"happy": .4, "neutral": .35}
                assert result["audio_emotion_ranking"][0]["promoted"] is False
                assert result["emotion_status"] == result["diarization_status"] == "success"
                assert result["speaker_count"] == result["speaker_voice_signature_count"] == 1
                assert result["time_hints"]["explicit_dates"] == ["2001-12-16"]
                assert result["mentioned_people"] == [{"text": "Claire", "type": "PERSON"}]
        temporal = json.loads((processor.processing_dir / digest / "temporal_index.json").read_text(encoding="utf-8"))
        if kind == "image":
            assert len(temporal["segments"][0]["detected_objects"]) == len(expected_objects)
