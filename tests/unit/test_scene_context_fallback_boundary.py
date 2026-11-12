from __future__ import annotations

import json
import sys
import types

import pytest


@pytest.mark.parametrize("visual_source", ["caption", "objects"])
@pytest.mark.parametrize("transcript", ["Hello", "Please put the blue cushion on the chair beside the window."])
def test_room_curtains_preserve_context_generation(visual_source, transcript):
    from steps.video import cross_modal_harmonizer as harmonizer

    caption = "A furnished room with curtains" if visual_source == "caption" else "A furnished room"
    objects = [{"label": "chair"}]
    if visual_source == "objects":
        objects.append({"label": "curtain"})
    original_objects = [dict(obj) for obj in objects]
    scene = {"index": 0, "scene_id": "room", "keyframe": {"caption": caption, "objects": objects}}
    segment = {
        "scene_id": "room", "start": 0, "end": 12, "content_state": "signal",
        "full_transcript": transcript, "detected_objects": objects, "speaker_ids": ["SPEAKER_00"],
    }
    calls = []

    class Client:
        last_model_used = None
        last_provider_used = "fixture"

        def chat(self, **kwargs):
            calls.append(kwargs)
            return {"choices": [{"message": {"content": json.dumps({
                "narrative_summary": "A furnished room.", "key_moments": ["A chair is visible."],
                "emotional_arc": "", "context_tags": [], "activity_description": "A furnished room.",
            })}}]}

    cfg = {"llm": {"features": {"scene_context_analysis": True}}}
    counts = harmonizer._apply_scene_context_llm([segment], {"room": scene}, cfg, llm_client=Client())
    harmonizer._persist_harmonized_scene_fields({"scenes": [scene]}, [segment])

    assert counts == {"evaluated_count": 1, "reused_count": 0}
    assert len(calls) == 1
    assert "curtain" in calls[0]["messages"][1]["content"].lower()
    context = scene["scene_context_llm"]
    assert context == segment["scene_context_llm"]
    assert context["status"] == "ok"
    assert context["source"] == "scene_context_llm"
    assert context["reason"] == "model_output"
    assert scene["keyframe"]["objects"] == original_objects


@pytest.mark.parametrize("caption,objects,transcript,reason", [
    ("A person on a stage with curtains", [{"label": "curtain"}], "Hello", "low_signal"),
    ("A person on a stage with curtains", [{"label": "curtain"}],
     "Today I will tell you about the garden and its flowers.", "spoken_monologue"),
    ("a black background", [], "", "low_signal"),
])
def test_curtain_repair_preserves_stage_and_low_signal_controls(caption, objects, transcript, reason):
    from steps.common import context_analyzer_llm as analyzer

    class Client:
        def chat(self, **_kwargs):
            pytest.fail("Existing stage/low-signal control should not request a model")

    result = analyzer.analyze_scene_context_llm(
        {"caption": caption, "objects": objects, "transcript": transcript, "speakers": ["SPEAKER_00"]},
        {}, llm_client=Client(),
    )
    assert result["source"] == "scene_context_heuristic"
    assert result["reason"] == reason


@pytest.mark.parametrize("llm_failure", ["http_error", "invalid_json", "timeout", "unreachable", "vllm_success", "ollama_success"])
def test_harmonizer_fallback_keeps_dialogue_presence_in_persisted_context(
    monkeypatch, tmp_path, llm_failure,
):
    from steps.common import context_analyzer_llm as analyzer
    from steps.video import cross_modal_harmonizer as harmonizer
    from cli import step_runner
    from steps.common import step_logger
    from lib import llm_client

    transcript = (
        "Look at this beautiful red truck. Can I touch it? "
        "Don't get fingerprints all over the place. What do you think of it?"
    )
    processing = tmp_path / "processing"
    scene_dir = processing / "video-1"
    manifest_path = scene_dir / "video" / "scene_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({
        "video_id": "video-1", "phase5_complete": True,
        "scenes": [{
            "scene_id": "scene-1", "start": 0, "end": 20, "duration": 20,
            "content_state": "signal",
            "keyframe": {"caption": "a person standing next to a red truck", "objects": [], "faces": []},
            "audio": {"transcript": transcript, "speakers": ["SPEAKER_00", "SPEAKER_01"]},
        }],
    }), encoding="utf-8")
    requests = []

    class Response:
        status_code = 503 if llm_failure == "http_error" else 200
        text = "fixture unavailable"

        def json(self):
            content = json.dumps({
                "narrative_summary": "A person stands next to a red truck.",
                "key_moments": ["A person stands next to a red truck."],
                "emotional_arc": "", "context_tags": ["red truck"],
                "activity_description": "A person stands next to a red truck.",
            }) if llm_failure.endswith("success") else "not JSON"
            return {"choices": [{"message": {"content": content}}]}

    def post(url, **kwargs):
        requests.append({"url": url, **kwargs})
        if llm_failure == "timeout":
            raise analyzer.requests.Timeout("fixture timeout")
        return Response()

    class Session:
        def __init__(self):
            self.headers = {}
            self.trust_env = True
            self.closed = False

        def get(self, url, **_kwargs):
            if llm_failure == "unreachable" or (llm_failure == "ollama_success" and ":38005/" in url):
                raise analyzer.requests.ConnectionError("fixture unavailable")
            return types.SimpleNamespace(status_code=200)

        def post(self, url, **kwargs):
            assert self.trust_env is False
            return post(url, **kwargs)

        def close(self):
            self.closed = True

    session = Session()
    monkeypatch.setattr(llm_client.requests, "Session", lambda: session)
    monkeypatch.setattr(llm_client.time, "sleep", lambda _: None)
    monkeypatch.setattr(llm_client.LLMClient, "_attempt_auto_activation", lambda *_: pytest.fail("Ingestion must not start model services"))
    monkeypatch.setattr(analyzer.requests, "post", lambda *_args, **_kwargs: pytest.fail("Scene context bypassed injected LLMClient"))
    monkeypatch.delenv("GOODQ_HOST_PROFILE", raising=False)
    # Entity extraction is an independent model lane; exercise the real context
    # analyzer and persisted harmonizer output without loading those models.
    monkeypatch.setattr(harmonizer, "ENTITY_EXTRACTION_AVAILABLE", False)
    cfg = {
        "ingestion_isolation": True,
        "paths": {"processing": str(processing), "log_dir": str(tmp_path / "logs")},
        "llm": {
            "features": {"scene_context_analysis": True},
            "api_url": "http://localhost:1234/v1/chat/completions",
            "model_id": "LM_STUDIO_GOODQ",
            "vllm_url": "http://127.0.0.1:38005/v1", "vllm_model": "goodq-qwen-speed",
            "ollama_url": "http://127.0.0.1:11434/v1", "ollama_model": "llama3.2:latest",
            "timeout": 12, "max_retries": 1,
        },
        "gpu": {"clear_cache_before_step": False},
    }
    item = {
        "id": "video-1", "source_path": str(tmp_path / "video.mp4"),
        "scene_manifest_path": str(manifest_path),
    }
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "result.json"
    input_path.write_text(json.dumps(item), encoding="utf-8")
    monkeypatch.setattr(step_runner, "load_step_config", lambda *_: cfg)
    monkeypatch.setattr(step_logger, "MISSION_LOGGER_AVAILABLE", False)
    gpu = types.ModuleType("common.gpu_manager")
    gpu.initialize_gpu_for_step = lambda **_: None
    monkeypatch.setitem(sys.modules, "common.gpu_manager", gpu)
    monkeypatch.setattr(sys, "argv", [
        "step_runner", "--step", "cross_modal_harmonization",
        "--in", str(input_path), "--out", str(output_path),
    ])

    step_runner.main()
    result = json.loads(output_path.read_text(encoding="utf-8"))

    temporal = json.loads((scene_dir / "temporal_index.json").read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    segment = temporal["segments"][0]
    context = segment["scene_context_llm"]
    assert result["harmonization_status"] == "complete"
    assert session.closed is True
    expected_request_count = 0 if llm_failure == "unreachable" else (2 if llm_failure == "ollama_success" else 1)
    assert len(requests) == expected_request_count
    if requests:
        expected_model = "llama3.2:latest" if llm_failure == "ollama_success" else "goodq-qwen-speed"
        expected_endpoint = "http://127.0.0.1:11434/v1" if llm_failure == "ollama_success" else "http://127.0.0.1:38005/v1"
        assert requests[0]["url"] == expected_endpoint + "/chat/completions"
        assert requests[0]["json"]["model"] == expected_model
        assert requests[0]["timeout"] == 12
        assert transcript in requests[0]["json"]["messages"][1]["content"]
        if llm_failure == "ollama_success":
            assert requests[1]["url"] == "http://127.0.0.1:11434/api/generate"
            assert requests[1]["json"] == {"model": expected_model, "keep_alive": 0}
    assert segment["full_transcript"] == transcript
    assert manifest["scenes"][0]["scene_context_llm"] == context
    logged = json.loads((tmp_path / "logs" / "step_runs.jsonl").read_text(encoding="utf-8"))
    if llm_failure.endswith("success"):
        assert context["status"] == "ok"
        assert context["source"] == "scene_context_llm"
        assert context["model_id"] == expected_model
        assert context["api_url"] == expected_endpoint
        assert result["scene_context_meta"]["status"] == "ok"
        assert logged["status"] == "ok"
        return
    assert context["narrative_summary"] == "Spoken or dialogue evidence present."
    assert context["activity_description"] == "Spoken or dialogue evidence present."
    assert context["key_moments"] == ["Spoken or dialogue evidence present."]
    expected_reason = {
        "http_error": "llm_error:Exception", "invalid_json": "llm_invalid_json",
        "timeout": "llm_error:Exception", "unreachable": "llm_error:Exception",
    }[llm_failure]
    assert context["status"] == "fallback"
    assert context["source"] == "scene_context_fallback"
    assert context["reason"] == expected_reason
    epistemic = segment["scene_context_epistemic"]
    assert epistemic["fallback_mode"] == "llm_failure"
    assert expected_reason in epistemic["limits"]
    assert epistemic["dominant_evidence"] == "fallback"
    meta = result["scene_context_meta"]
    assert meta["status"] == "degraded"
    assert meta["observations"] == [{
        "scene_id": "scene-1", "status": "fallback",
        "source": "scene_context_fallback", "reason": expected_reason,
    }]
    assert temporal["scene_context_meta"] == meta
    assert logged["status"] == "degraded"
    assert logged["extra"]["reason"] == "scene_context_fallback"
    assert logged["extra"]["result_meta"]["scene_context_meta"] == meta


def test_unload_ollama_model_if_used_unloads_all_attempted_ollama_models_on_failover(monkeypatch):
    from lib import llm_client
    from steps.video import cross_modal_harmonizer as harmonizer

    unload_calls = []
    chat_calls = []

    class DummySession:
        def __init__(self):
            self.headers = {}
            self.trust_env = True

        def get(self, _url, **_kwargs):
            return types.SimpleNamespace(status_code=200)

        def post(self, url, **kwargs):
            if url.endswith("/api/generate"):
                unload_calls.append({"url": url, "json": kwargs.get("json")})
                return types.SimpleNamespace(status_code=200, raise_for_status=lambda: None)
            payload = kwargs.get("json") or {}
            chat_calls.append(payload.get("model"))
            if payload.get("model") == "qwen2.5:14b":
                raise llm_client.requests.Timeout("primary ollama timed out after loading")
            return types.SimpleNamespace(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "{}"}}]},
            )

        def close(self):
            pass

    monkeypatch.setattr(llm_client.requests, "Session", DummySession)
    monkeypatch.setattr(llm_client.time, "sleep", lambda *_: None)

    models = [
        llm_client.ModelConfig(
            name="Primary-14B",
            base_url="http://127.0.0.1",
            port=11434,
            model_id="qwen2.5:14b",
            backend="ollama",
            vram_gb=9.5,
            tokens_per_sec=80,
            context_length=16384,
            capabilities=["chat"],
            priority=200,
        ),
        llm_client.ModelConfig(
            name="Fallback-3B",
            base_url="http://127.0.0.1",
            port=11434,
            model_id="llama3.2:latest",
            backend="ollama",
            vram_gb=2.0,
            tokens_per_sec=120,
            context_length=16384,
            capabilities=["chat"],
            priority=90,
        ),
    ]
    client = llm_client.LLMClient(
        models=models,
        health_check_interval=60,
        max_retries=2,
        timeout=10,
        cache_ttl=300,
        enable_health_checks=False,
        allow_auto_activation=False,
        allow_environment_proxies=False,
    )
    client.chat(messages=[{"role": "user", "content": "hi"}])

    assert chat_calls == ["qwen2.5:14b", "llama3.2:latest"]
    assert client.last_model_used.model_id == "llama3.2:latest"
    assert harmonizer._unload_ollama_model_if_used(client) is True
    assert unload_calls == [
        {"url": "http://127.0.0.1:11434/api/generate", "json": {"model": "qwen2.5:14b", "keep_alive": 0}},
        {"url": "http://127.0.0.1:11434/api/generate", "json": {"model": "llama3.2:latest", "keep_alive": 0}},
    ]
