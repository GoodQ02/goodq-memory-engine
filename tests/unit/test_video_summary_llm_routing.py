"""Confirmed summary requests use the configured client and persist its identity."""
from contextlib import closing
import json
import sqlite3
from types import SimpleNamespace

import pytest

from lib import llm_client
from tests.unit.test_summary_persistence_boundary import (
    VIDEO_HASH, _prepare_and_confirm, _stored, summary_runtime,
)


@pytest.mark.parametrize("provider", ["vllm", "ollama", "unavailable", "empty"])
def test_confirmed_summary_uses_configured_llm_route(summary_runtime, monkeypatch, caplog, provider):
    client, cfg, memory, _graph, authority = summary_runtime
    cfg["llm"].update({
        "features": {"video_summarization": True},
        "api_url": "http://localhost:1234/v1/chat/completions",
        "model": "legacy-unused-model",
        "vllm_url": "http://127.0.0.1:38005/v1", "vllm_model": "goodq-qwen-speed",
        "ollama_url": "http://127.0.0.1:11434/v1", "ollama_model": "llama3.2:latest",
        "timeout": 12, "max_retries": 1,
    })
    with closing(sqlite3.connect(memory)) as db, db:
        db.execute(
            "INSERT INTO summaries (summary_type, category, content) VALUES (?,?,?)",
            ("scene", "scene_summary", json.dumps({
                "scene_id": "target-scene", "summary": "A bounded scene about a red truck."})),
        )
    monkeypatch.delenv("GOODQ_HOST_PROFILE", raising=False)
    if provider in {"vllm", "empty"}:
        from steps.video_summarizer import step
        original_builder = step.build_llm_models

        def quality_capable_fixture_models(config):
            models = original_builder(config)
            models[0].capabilities = ["chat", "quality"]
            return models

        monkeypatch.setattr(step, "build_llm_models", quality_capable_fixture_models)
    monkeypatch.setattr(llm_client.time, "sleep", lambda _: None)
    monkeypatch.setattr(llm_client.LLMClient, "_attempt_auto_activation",
                        lambda *_: pytest.fail("Summary must not activate model services"))
    requests = []

    class Session:
        def __init__(self):
            self.headers = {}
            self.trust_env = True
            self.closed = False

        def get(self, url, **_kwargs):
            if provider == "unavailable" or (provider == "ollama" and ":38005/" in url):
                raise llm_client.requests.ConnectionError("fixture provider unavailable")
            return SimpleNamespace(status_code=200)

        def post(self, url, **kwargs):
            assert self.trust_env is False
            requests.append({"url": url, **kwargs})
            return SimpleNamespace(status_code=200, json=lambda: {
                "choices": [{"message": {"content": "  " if provider == "empty" else "A discussion about a red truck."}}],
            })

        def close(self):
            self.closed = True

    session = Session()
    monkeypatch.setattr(llm_client.requests, "Session", lambda: session)

    def reject_legacy(*_args, **_kwargs):
        raise llm_client.requests.ConnectionError("Legacy localhost:1234 is unavailable")

    monkeypatch.setattr(llm_client.requests, "post", reject_legacy)
    _prepare_and_confirm(client)
    assert client.get(f"/api/summary/video/{VIDEO_HASH}/status").json()["status"] == "succeeded"
    persisted = _stored(memory)[0]
    readback = client.get(f"/api/summary/video/{VIDEO_HASH}").json()
    if provider in {"vllm", "ollama"}:
        expected_model = "goodq-qwen-speed" if provider == "vllm" else "llama3.2:latest"
        expected_url = cfg["llm"][f"{provider}_url"] + "/chat/completions"
        assert persisted["method"] == "llm"
        assert readback["method"] == "llm"
        assert requests[0]["url"] == expected_url
        assert requests[0]["json"]["model"] == expected_model
        assert requests[0]["timeout"] == 12
        assert "red truck" in requests[0]["json"]["messages"][1]["content"]
        assert persisted["provenance"]["model_id"] == expected_model
        assert persisted["provenance"]["api_url"] == expected_url
        assert persisted["provenance"]["provider"].startswith(provider + ":")
        assert readback["provenance"] == persisted["provenance"]
        assert "1234" not in persisted["provenance"]["model_backend"]
    else:
        assert persisted["method"] == readback["method"] == "template"
        assert persisted["provenance"]["model_backend"] == "template"
        assert persisted["provenance"]["fallback_reason"]
        assert "template fallback" in caplog.text
    assert session.closed is True
    assert authority.external_calls[-1]["side_effect_report"]["mutated"] is True


@pytest.mark.parametrize("candidate_scope", ["speed_only", "quality_unavailable"])
def test_confirmed_summary_rejects_speed_only_and_preserves_scene_evidence(
    summary_runtime, monkeypatch, candidate_scope,
):
    from steps.video_summarizer import step

    client, cfg, memory, _graph, authority = summary_runtime
    cfg["llm"].update({
        "features": {"video_summarization": True},
        "vllm_url": "http://127.0.0.1:38005/v1", "vllm_model": "goodq-qwen-speed",
        "ollama_url": "http://127.0.0.1:11434/v1", "ollama_model": "llama3.2:latest",
        "timeout": 1, "max_retries": 1,
    })
    monkeypatch.delenv("GOODQ_HOST_PROFILE", raising=False)
    if candidate_scope == "speed_only":
        original_builder = step.build_llm_models
        monkeypatch.setattr(step, "build_llm_models", lambda config: original_builder(config)[:1])
    first_evidence = 'Caption: a red truck. Transcript: "Can I touch it, Matt?" Entity mentions: Jose.'
    with closing(sqlite3.connect(memory)) as db, db:
        for i in range(1, 22):
            scene_id = "target-scene" if i == 1 else f"target-scene-{i}"
            if i > 1:
                db.execute("INSERT INTO scenes VALUES (?,?,?,?,?,?)", (
                    scene_id, VIDEO_HASH, (i - 1) * 10, i * 10, "{}", "2026-10-08"))
            db.execute("INSERT INTO summaries (summary_type,category,content,created_at) VALUES (?,?,?,?)", (
                "scene", "scene_summary", json.dumps({"scene_id": scene_id,
                    "summary": first_evidence if i == 1 else f"Exact scene evidence {i:02d}."}), "2026-10-08"))
        db.execute("INSERT INTO scenes VALUES (?,?,?,?,?,?)", (
            "unrelated-scene", "b" * 64, 0, 50, "{}", "2026-10-08"))
        db.execute("INSERT INTO summaries (summary_type,category,content) VALUES (?,?,?)", (
            "scene", "scene_summary", json.dumps({"scene_id": "unrelated-scene", "summary": "UNRELATED VIDEO EVIDENCE"})))
    calls = []
    sessions = []

    class Session:
        def __init__(self):
            self.headers = {}
            self.trust_env = True
            self.closed = False
            sessions.append(self)

        def get(self, url, **_kwargs):
            calls.append(("get", url))
            if ":38005/" in url:
                return SimpleNamespace(status_code=200)
            raise llm_client.requests.ConnectionError("Quality-capable provider unavailable")

        def post(self, url, **_kwargs):
            calls.append(("post", url))
            return SimpleNamespace(status_code=200, json=lambda: {
                "choices": [{"message": {"content": "Matt touched the truck with Jose inside it."}}],
            })

        def close(self):
            self.closed = True

    monkeypatch.setattr(llm_client.requests, "Session", Session)
    monkeypatch.setattr(llm_client.LLMClient, "_attempt_auto_activation",
                        lambda *_: pytest.fail("Summary must not activate model services"))
    monkeypatch.setattr(llm_client.time, "sleep", lambda _: None)
    _prepare_and_confirm(client)
    stored = _stored(memory)[0]
    readback = client.get(f"/api/summary/video/{VIDEO_HASH}").json()

    assert stored["method"] == readback["method"] == "template"
    assert stored["provenance"]["fallback_reason"]
    assert stored["provenance"]["model_selection_policy"] == "quality_or_reasoning"
    assert stored["provenance"]["model_backend"] == "template"
    text = stored["summary"]
    assert text == readback["summary"]
    assert first_evidence in text
    assert "Machine-generated scene evidence" in text
    assert "target-scene" in text and "0.0-10.0 seconds" in text
    assert "Exact scene evidence 20." in text
    assert "Exact scene evidence 21." not in text
    assert "1 additional scene summary omitted" in text
    assert "UNRELATED VIDEO EVIDENCE" not in text
    assert "Matt touched" not in text and "indexed for semantic search" not in text
    assert [r["summary_id"] for r in stored["provenance"]["source_artifact_versions"]] == list(range(1, 21))
    assert all(method != "post" and ":38005/" not in url for method, url in calls)
    assert all(session.closed for session in sessions)
    assert authority.external_calls[-1]["side_effect_report"]["mutated"] is True
