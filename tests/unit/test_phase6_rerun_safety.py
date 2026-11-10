from __future__ import annotations

from pathlib import Path

from cli import run_ingestion
from steps.common import tool_paths
from steps.video import scene_frame_extractor


def test_step_timeout_defaults_to_builtin_when_omitted() -> None:
    assert run_ingestion._resolve_step_timeout_value(None) == run_ingestion.DEFAULT_STEP_TIMEOUT
    assert run_ingestion._resolve_step_timeout_value(45) == 45
    assert run_ingestion._resolve_step_timeout_value(0) is None


def test_merge_prior_phase6_manifest_state_preserves_existing_success() -> None:
    prior = {
        "phase6_complete": True,
        "phase6_status": "complete",
        "phase6_vector_commit": {"qdrant_ok": True},
        "embedding_stats": {"clip_scenes": 12},
        "scenes": [
            {
                "scene_id": "scene_0009",
                "index": 9,
                "frame_paths": ["frames/scene_0009_frame_00.jpg"],
                "representative_frame": "frames/scene_0009_frame_00.jpg",
                "clip_id": "clip_scene_video_9",
            }
        ],
    }
    new = {
        "video_id": "video_123",
        "scenes": [
            {
                "scene_id": "scene_0009",
                "index": 9,
                "start": 10.0,
                "end": 12.0,
            }
        ],
    }

    merged = run_ingestion._merge_prior_phase6_manifest_state(new, prior)

    assert merged["phase6_complete"] is True
    assert merged["phase6_status"] == "complete"
    assert merged["phase6_vector_commit"]["qdrant_ok"] is True
    assert merged["scenes"][0]["frame_paths"] == ["frames/scene_0009_frame_00.jpg"]
    assert merged["scenes"][0]["clip_id"] == "clip_scene_video_9"


def test_resolve_ffmpeg_accepts_directory_override(monkeypatch, tmp_path: Path) -> None:
    ffmpeg_dir = tmp_path / "ffmpeg_bin"
    ffmpeg_dir.mkdir()
    ffmpeg_exe = ffmpeg_dir / ("ffmpeg.exe" if tool_paths.os.name == "nt" else "ffmpeg")
    ffmpeg_exe.write_text("stub", encoding="utf-8")

    cfg = {"config": {"tools": {"ffmpeg_exe": f'"{ffmpeg_dir}"'}}}

    monkeypatch.setattr(tool_paths.shutil, "which", lambda *_args, **_kwargs: None)

    assert tool_paths.resolve_ffmpeg(cfg) == str(ffmpeg_exe)


def test_resolve_ffmpeg_uses_the_installed_bundled_runtime_before_imageio(monkeypatch, tmp_path: Path) -> None:
    bundled = tmp_path / ("ffmpeg.exe" if tool_paths.os.name == "nt" else "ffmpeg")
    bundled.write_text("stub", encoding="utf-8")

    monkeypatch.setattr(tool_paths.shutil, "which", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "steps.common.tool_resolver.ToolResolver.resolve_tool",
        lambda _name: {"found": True, "path": str(bundled)},
    )

    assert tool_paths.resolve_ffmpeg({}) == str(bundled)


def test_extract_frame_at_timestamp_reuses_existing_frame(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "scene_0009_frame_00.jpg"
    output_path.write_bytes(b"existing-frame")

    def _unexpected_run(*_args, **_kwargs):
        raise AssertionError("subprocess.run should not be invoked for reusable frames")

    monkeypatch.setattr(scene_frame_extractor.subprocess, "run", _unexpected_run)

    ok = scene_frame_extractor.extract_frame_at_timestamp(
        video_path=str(tmp_path / "video.mp4"),
        timestamp=1.23,
        output_path=str(output_path),
        ffmpeg_exe="ffmpeg",
    )

    assert ok is True
    assert output_path.read_bytes() == b"existing-frame"


def test_merge_prior_phase6_manifest_state_preserves_scene_context_llm() -> None:
    prior = {
        "phase6_complete": True,
        "scenes": [
            {
                "scene_id": "scene_0001",
                "index": 1,
                "scene_context_llm": {"narrative_summary": "Prior window summary."},
                "scene_context_epistemic": {"status": "grounded"},
                "scene_context_arbitration": {"winner": "llm"},
            }
        ],
    }
    new = {
        "video_id": "video_123",
        "scenes": [{"scene_id": "scene_0001", "index": 1, "start": 0.0, "end": 5.0}],
    }
    merged = run_ingestion._merge_prior_phase6_manifest_state(new, prior)
    assert merged["scenes"][0]["scene_context_llm"] == {"narrative_summary": "Prior window summary."}
    assert merged["scenes"][0]["scene_context_epistemic"] == {"status": "grounded"}
    assert merged["scenes"][0]["scene_context_arbitration"] == {"winner": "llm"}


def test_unload_ollama_model_if_used_validates_http_status_and_logs_warning_on_failure(caplog) -> None:
    import logging
    from types import SimpleNamespace
    from steps.video import cross_modal_harmonizer as cmh

    model = SimpleNamespace(backend="ollama", endpoint="http://127.0.0.1:11434/v1", model_id="hermes-gemma4-64k:12b")

    # 1. HTTP 500 must return False, log WARNING, and NOT log "Unloaded Ollama model"
    resp_500 = SimpleNamespace(status_code=500, text="internal server error")
    client_500 = SimpleNamespace(last_model_used=model, session=SimpleNamespace(post=lambda *_a, **_k: resp_500))
    with caplog.at_level(logging.INFO):
        caplog.clear()
        assert cmh._unload_ollama_model_if_used(client_500) is False
        assert not any("Unloaded Ollama model" in rec.message for rec in caplog.records)
        assert any(rec.levelname == "WARNING" and "HTTP 500" in rec.message for rec in caplog.records)

    # 2. Connection error must return False and log WARNING
    def _raise_conn(*_a, **_k):
        raise RuntimeError("connection refused")

    client_err = SimpleNamespace(last_model_used=model, session=SimpleNamespace(post=_raise_conn))
    with caplog.at_level(logging.INFO):
        caplog.clear()
        assert cmh._unload_ollama_model_if_used(client_err) is False
        assert any(rec.levelname == "WARNING" and "connection refused" in rec.message for rec in caplog.records)

    # 3. HTTP 302 (non-2xx redirect) returns False and logs WARNING
    resp_302 = SimpleNamespace(status_code=302, text="Found", raise_for_status=lambda: None)
    client_302 = SimpleNamespace(last_model_used=model, session=SimpleNamespace(post=lambda *_a, **_k: resp_302))
    with caplog.at_level(logging.INFO):
        caplog.clear()
        assert cmh._unload_ollama_model_if_used(client_302) is False
        assert any(rec.levelname == "WARNING" and "HTTP 302" in rec.message for rec in caplog.records)
        assert not any("Unloaded Ollama model" in rec.message for rec in caplog.records)

    # 4. HTTP 200 returns True and logs INFO
    resp_200 = SimpleNamespace(status_code=200, text="{}", raise_for_status=lambda: None)
    client_200 = SimpleNamespace(last_model_used=model, session=SimpleNamespace(post=lambda *_a, **_k: resp_200))
    with caplog.at_level(logging.INFO):
        caplog.clear()
        assert cmh._unload_ollama_model_if_used(client_200) is True
        assert any(rec.levelname == "INFO" and "Unloaded Ollama model" in rec.message for rec in caplog.records)


def test_apply_scene_context_llm_with_force_scene_ids_only_recomputes_current_window(monkeypatch) -> None:
    from steps.video import cross_modal_harmonizer as cmh

    called_scenes: list[str] = []

    def _fake_analyze(evidence, _cfg, llm_client=None):
        called_scenes.append(str(evidence.get("caption") or ""))
        return {
            "narrative_summary": f"Summary for {evidence.get('caption')}.",
            "key_moments": [f"Moment for {evidence.get('caption')}."],
            "emotional_arc": "neutral",
            "context_tags": [],
            "activity_description": f"Activity for {evidence.get('caption')}.",
        }

    monkeypatch.setattr(cmh, "SCENE_CONTEXT_LLM_AVAILABLE", True)
    monkeypatch.setattr(cmh, "_scene_context_llm_enabled", lambda _cfg: True)
    monkeypatch.setattr(cmh, "analyze_scene_context_llm", _fake_analyze)

    scene_lookup = {
        f"scene_{i:03d}": {"scene_id": f"scene_{i:03d}", "keyframe": {"caption": f"scene_{i:03d}"}, "audio": {}}
        for i in range(4)
    }
    segments = [
        {"scene_id": f"scene_{i:03d}", "content_state": "signal", "full_transcript": "Hello there.", "scene_context_llm": None}
        for i in range(4)
    ]
    cfg = {"force_reprocess": True}

    # Window 1 processes scene_000 and scene_001
    cmh._apply_scene_context_llm(
        segments[:2],
        scene_lookup,
        cfg,
        force_scene_ids={"scene_000", "scene_001"},
    )
    assert called_scenes == ["scene_000", "scene_001"]

    # Window 2 has all 4 segments, with force_scene_ids={"scene_002", "scene_003"}
    cmh._apply_scene_context_llm(
        segments,
        scene_lookup,
        cfg,
        force_scene_ids={"scene_002", "scene_003"},
    )
    # Total LLM calls across both windows is 4 (1 per scene), NOT 2 + 4 = 6
    assert called_scenes == ["scene_000", "scene_001", "scene_002", "scene_003"]


def test_extract_keyframe_retries_same_timestamp_with_strict_unofficial_on_mjpeg_yuv_error(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    outfile = tmp_path / "scene_0041_face_04.jpg"

    class _FakeProc:
        def __init__(self, cmd):
            self.cmd = list(cmd)
            self.pid = 12345
            calls.append(self.cmd)
            self.returncode = 0 if "-strict" in self.cmd else 1

        def communicate(self):
            if "-strict" in self.cmd:
                outfile.write_bytes(b"jpeg-bytes")
                return ("", "")
            return ("", "[mjpeg] Non full-range YUV is non-standard, set strict_std_compliance to at most unofficial to use it.")

    monkeypatch.setattr(run_ingestion.subprocess, "Popen", lambda cmd, **_kw: _FakeProc(cmd))
    monkeypatch.setattr(run_ingestion, "_observer", lambda: None)

    res_path = run_ingestion._extract_keyframe(
        "ffmpeg",
        tmp_path / "video.mp4",
        {"index": 41, "start": 1358.065, "duration": 10.969},
        tmp_path,
        sample_timestamp=1368.984,
        sample_suffix="_face_04",
    )
    assert res_path == outfile
    assert len(calls) == 2
    # Both initial attempt and -strict unofficial retry use the exact same timestamp
    assert calls[0][calls[0].index("-ss") + 1] == "1368.984"
    assert calls[1][calls[1].index("-ss") + 1] == "1368.984"
    assert "-strict" in calls[1] and "unofficial" in calls[1]


def test_process_audio_async_serializes_wsl_unified_audio_with_lock(monkeypatch, tmp_path: Path) -> None:
    import asyncio
    import time

    audio_file = tmp_path / "chunk.wav"
    audio_file.write_bytes(b"RIFF")
    cfg_json = tmp_path / "cfg.json"
    cfg_json.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(run_ingestion, "_extract_audio_chunk", lambda *_a, **_k: audio_file)
    monkeypatch.setattr(
        run_ingestion,
        "_run_step_async",
        lambda *_a, **_k: asyncio.sleep(0, result={"status": "ok", "outputs": {}}),
    )

    active = 0
    max_active = 0

    def _fake_wsl_audio(_path: str, *, scene_id=None, duration=None,
                        transcription_temperature=0., transcription_vocabulary=None):
        nonlocal active, max_active
        assert transcription_temperature == 0. and transcription_vocabulary is None
        active += 1
        max_active = max(max_active, active)
        time.sleep(0.05)
        active -= 1
        return {"status": "ok", "transcript": f"transcript-{scene_id}", "segments": []}

    monkeypatch.setattr("steps.audio.audio_wsl2_bridge.audio_unified_wsl2", _fake_wsl_audio)

    async def _run_both():
        db_lock = asyncio.Lock()
        faiss_lock = asyncio.Lock()
        wsl_lock = asyncio.Lock()
        contract = {"selected": "wsl", "reason": "test"}
        await asyncio.gather(
            run_ingestion._process_audio_async(
                cfg_json, "ffmpeg", tmp_path / "v.mp4",
                {"index": 0, "start": 0.0, "end": 5.0},
                tmp_path, tmp_path, "vhash", "scene_0",
                db_lock, faiss_lock, audio_runtime_contract=contract, wsl_audio_lock=wsl_lock,
            ),
            run_ingestion._process_audio_async(
                cfg_json, "ffmpeg", tmp_path / "v.mp4",
                {"index": 1, "start": 5.0, "end": 10.0},
                tmp_path, tmp_path, "vhash", "scene_1",
                db_lock, faiss_lock, audio_runtime_contract=contract, wsl_audio_lock=wsl_lock,
            ),
        )

    asyncio.run(_run_both())
    assert max_active == 1


def test_rehydrate_video_result_scenes_from_manifest_preserves_errors_and_backend_fields(tmp_path: Path) -> None:
    import json

    scene_outputs = [
        {
            "scene_id": "vhash_scene_0000",
            "index": 0,
            "start": 0.0,
            "end": 12.5,
            "duration": 12.5,
            "content_state": "processing_error",
            "errors": {"audio_transcribe": "wsl bridge timeout"},
            "persistence": {"sqlite_persisted": True, "kg_persisted": True},
            "audio_backend_selected": "wsl",
            "audio_backend_effective": "windows",
            "audio_backend_downgraded": True,
            "audio_backend_reason": "wsl_failed",
            "keyframe": {"path": "kf0.jpg", "caption": "two people talking"},
            "audio": {"transcript": ""},
        }
    ]
    # Narrower manifest representation omitting persistence and top-level audio_backend_*
    manifest_path = tmp_path / "scene_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "video_id": "vhash",
                "scenes": [
                    {
                        "scene_id": "vhash_scene_0000",
                        "index": 0,
                        "start": 0.0,
                        "end": 12.5,
                        "duration": 12.5,
                        "content_state": "processing_error",
                        "keyframe": {"path": "kf0.jpg", "caption": "two people talking"},
                        "audio": {"transcript": ""},
                        "scene_context_llm": {
                            "narrative_summary": "Two people converse indoors.",
                            "key_moments": ["Two people converse indoors."],
                            "context_tags": ["indoors", "conversation"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert run_ingestion._rehydrate_video_result_scenes_from_manifest(
        {"scenes": scene_outputs},
        str(manifest_path),
    )
    rehydrated = scene_outputs[0]
    assert rehydrated["errors"] == {"audio_transcribe": "wsl bridge timeout"}
    assert rehydrated["persistence"] == {"sqlite_persisted": True, "kg_persisted": True}
    assert rehydrated["audio_backend_selected"] == "wsl"
    assert rehydrated["audio_backend_effective"] == "windows"
    assert rehydrated["audio_backend_downgraded"] is True
    assert rehydrated["audio_backend_reason"] == "wsl_failed"
    assert rehydrated["summary"] == "Two people converse indoors."
    assert rehydrated["key_moments"] == ["Two people converse indoors."]
    assert rehydrated["tags"] == ["indoors", "conversation"]
    assert any(
        isinstance(s, dict) and ((s.get("errors") or {}) or s.get("keyframe_error"))
        for s in scene_outputs
    )


def test_progressive_window_phase6_disabled_initializes_window_scene_context_meta(tmp_path: Path) -> None:
    import textwrap

    src = Path(run_ingestion.__file__).read_text(encoding="utf-8")
    marker = src.index("                p6b_duration = 0.0")
    init_idx = src.index("window_scene_context_meta = None", marker)
    branch_idx = src.index("if phase6_enabled:", marker)
    read_idx = src.index("isinstance(window_scene_context_meta, dict)", marker)
    assert init_idx < branch_idx < read_idx

    end_marker = "'total_window_duration_seconds': window_total_duration,\n                }"
    end_idx = src.index(end_marker, read_idx) + len(end_marker)
    block = textwrap.dedent(src[marker:end_idx])
    ns = {
        "phase6_enabled": False,
        "time": run_ingestion.time,
        "window_start_time": 0.0,
        "processing_dir": tmp_path,
        "video_hash": "vhash",
        "video_path": tmp_path / "video.mp4",
        "w_idx": 0,
        "step_val": 6,
        "chunk_size_val": 6,
        "window_results": [{"scene_id": "s0"}],
        "audio_timings": 1.0,
        "frame_timings": 1.0,
        "sqlite_duration": 0.1,
        "kg_duration": 0.1,
        "p6a_duration": 0.0,
        "manifest_duration": 0.1,
        "json": run_ingestion.json,
        "logger": run_ingestion.logger,
    }
    exec(block, ns)
    assert ns["timings_data"]["windows"]["0"]["scene_context_meta"] is None
