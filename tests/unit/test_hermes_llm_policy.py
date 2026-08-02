from datetime import datetime
from unittest.mock import MagicMock

from lib.llm_client import HealthStatus, LLMClient, ModelConfig
from steps.common.llm_model_factory import build_llm_models


def _base_config() -> dict:
    return {
        "llm": {
            "vllm_url": "http://127.0.0.1:38005/v1",
            "ollama_url": "http://127.0.0.1:31434/v1",
            "vllm_model": "meta-llama/Llama-3.2-1B-Instruct",
            "ollama_model": "phi4",
        }
    }


def test_vllm_speed_fallback_defaults_to_the_active_qwen_service(monkeypatch) -> None:
    monkeypatch.delenv("GOODQ_VLLM_SERVED_MODEL_NAME", raising=False)
    cfg = _base_config()
    del cfg["llm"]["vllm_model"]

    model = next(model for model in build_llm_models(cfg) if model.backend == "vllm")

    assert model.name == "Qwen-0.5B-Speed"
    assert model.model_id == "goodq-qwen-speed"


def test_gpu_enhanced_profile_selects_configured_hermes_model(monkeypatch) -> None:
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")

    models = build_llm_models(_base_config())

    assert models[0].model_id == "hermes-gemma4-64k:12b"
    assert models[0].priority > models[1].priority
    assert models[0].request_options == {"think": False}


def test_gpu_enhanced_profile_uses_resolved_ollama_overlay_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    monkeypatch.delenv("GOODQ_OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    cfg = _base_config()
    cfg["llm"]["ollama_url"] = "http://127.0.0.1:40123/v1"

    model = build_llm_models(cfg)[0]

    assert model.endpoint == "http://127.0.0.1:40123/v1"


def test_only_gpu_enhanced_profile_uses_resolved_ollama_overlay_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("GOODQ_OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    cfg = _base_config()
    cfg["llm"]["ollama_url"] = "http://127.0.0.1:40123/v1"

    expected = {
        "GPU_ENHANCED": ("hermes-gemma4-64k:12b", "http://127.0.0.1:40123/v1"),
        "GPU_16GB_INGEST_QUALITY": ("deepseek-r1:14b", "http://localhost:11434/v1"),
        "GPU_16GB_INTERACTIVE_LIGHT": ("deepseek-r1:7b", "http://localhost:11434/v1"),
    }
    for profile, (model_id, endpoint) in expected.items():
        monkeypatch.setenv("GOODQ_HOST_PROFILE", profile)
        selected = build_llm_models(cfg)[0]

        assert selected.model_id == model_id
        assert selected.endpoint == endpoint


def test_gpu_enhanced_profile_replaces_matching_generic_ollama_model(monkeypatch) -> None:
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    cfg = _base_config()
    cfg["llm"]["ollama_model"] = "hermes-gemma4-64k:12b"

    models = build_llm_models(cfg)
    hermes_models = [
        model
        for model in models
        if model.backend == "ollama" and model.model_id == "hermes-gemma4-64k:12b"
    ]

    assert len(hermes_models) == 1
    assert hermes_models[0].vram_gb == 12.0
    assert hermes_models[0].request_options == {"think": False}


def test_chat_for_hermes_model_sends_non_thinking_request_option(monkeypatch) -> None:
    monkeypatch.setenv("GOODQ_HOST_PROFILE", "GPU_ENHANCED")
    model = build_llm_models(_base_config())[0]
    client = LLMClient(
        models=[model],
        health_check_interval=60,
        max_retries=1,
        timeout=5,
        cache_ttl=60,
        enable_health_checks=False,
        allow_auto_activation=False,
    )
    client.health_status[model.name] = HealthStatus(True, datetime.now(), 0)
    client.last_health_check = datetime.now()
    response = MagicMock(status_code=200)
    response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    client.session.post = MagicMock(return_value=response)

    client.chat([{"role": "user", "content": "hello"}])

    assert client.session.post.call_args.kwargs["json"]["think"] is False


def test_chat_rebuilds_model_options_for_failover_and_keeps_caller_kwargs(monkeypatch) -> None:
    primary = ModelConfig(
        name="vllm-primary",
        base_url="http://127.0.0.1",
        port=38005,
        model_id="meta-llama/Llama-3.2-1B-Instruct",
        backend="vllm",
        vram_gb=1.0,
        tokens_per_sec=1,
        context_length=1024,
        capabilities=["chat"],
        priority=200,
    )
    hermes = ModelConfig(
        name="hermes-failover",
        base_url="http://127.0.0.1",
        port=31434,
        model_id="hermes-gemma4-64k:12b",
        backend="ollama",
        vram_gb=12.0,
        tokens_per_sec=1,
        context_length=65536,
        capabilities=["chat"],
        priority=100,
        request_options={"think": False},
    )
    client = LLMClient(
        models=[primary, hermes],
        health_check_interval=60,
        max_retries=2,
        timeout=5,
        cache_ttl=60,
        enable_health_checks=False,
        allow_auto_activation=False,
    )
    client.health_status[primary.name] = HealthStatus(True, datetime.now(), 0)
    client.health_status[hermes.name] = HealthStatus(True, datetime.now(), 0)
    client.last_health_check = datetime.now()
    failed = MagicMock(status_code=500, text="primary failed")
    succeeded = MagicMock(status_code=200)
    succeeded.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    payloads = []

    def post(*_args, **request_kwargs):
        payloads.append(dict(request_kwargs["json"]))
        return [failed, succeeded][len(payloads) - 1]

    client.session.post = MagicMock(side_effect=post)
    monkeypatch.setattr("lib.llm_client.time.sleep", lambda _delay: None)

    client.chat([{"role": "user", "content": "hello"}], top_p=0.9)

    first_payload, second_payload = payloads
    assert first_payload["model"] == "meta-llama/Llama-3.2-1B-Instruct"
    assert "think" not in first_payload
    assert second_payload["model"] == "hermes-gemma4-64k:12b"
    assert second_payload["think"] is False
    assert first_payload["top_p"] == second_payload["top_p"] == 0.9


def test_chat_caller_kwargs_override_model_request_options() -> None:
    model = ModelConfig(
        name="hermes",
        base_url="http://127.0.0.1",
        port=31434,
        model_id="hermes-gemma4-64k:12b",
        backend="ollama",
        vram_gb=12.0,
        tokens_per_sec=1,
        context_length=65536,
        capabilities=["chat"],
        request_options={"think": False},
    )
    client = LLMClient(
        models=[model],
        health_check_interval=60,
        max_retries=1,
        timeout=5,
        cache_ttl=60,
        enable_health_checks=False,
        allow_auto_activation=False,
    )
    client.health_status[model.name] = HealthStatus(True, datetime.now(), 0)
    client.last_health_check = datetime.now()
    response = MagicMock(status_code=200)
    response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    client.session.post = MagicMock(return_value=response)

    client.chat([{"role": "user", "content": "hello"}], think=True)

    assert client.session.post.call_args.kwargs["json"]["think"] is True


def test_chat_does_not_leak_hermes_options_when_failing_over_to_phi(monkeypatch) -> None:
    hermes = ModelConfig(
        name="hermes-primary",
        base_url="http://127.0.0.1",
        port=31434,
        model_id="hermes-gemma4-64k:12b",
        backend="ollama",
        vram_gb=12.0,
        tokens_per_sec=1,
        context_length=65536,
        capabilities=["chat"],
        priority=200,
        request_options={"think": False},
    )
    phi = ModelConfig(
        name="phi-failover",
        base_url="http://127.0.0.1",
        port=31434,
        model_id="phi4",
        backend="ollama",
        vram_gb=2.0,
        tokens_per_sec=1,
        context_length=1024,
        capabilities=["chat"],
        priority=100,
    )
    client = LLMClient(
        models=[hermes, phi],
        health_check_interval=60,
        max_retries=2,
        timeout=5,
        cache_ttl=60,
        enable_health_checks=False,
        allow_auto_activation=False,
    )
    client.health_status[hermes.name] = HealthStatus(True, datetime.now(), 0)
    client.health_status[phi.name] = HealthStatus(True, datetime.now(), 0)
    client.last_health_check = datetime.now()
    failed = MagicMock(status_code=500, text="primary failed")
    succeeded = MagicMock(status_code=200)
    succeeded.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    payloads = []

    def post(*_args, **request_kwargs):
        payloads.append(dict(request_kwargs["json"]))
        return [failed, succeeded][len(payloads) - 1]

    client.session.post = MagicMock(side_effect=post)
    monkeypatch.setattr("lib.llm_client.time.sleep", lambda _delay: None)

    client.chat([{"role": "user", "content": "hello"}])

    assert payloads[0]["think"] is False
    assert payloads[1]["model"] == "phi4"
    assert "think" not in payloads[1]
