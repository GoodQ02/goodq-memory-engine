from __future__ import annotations

from unittest.mock import MagicMock

from lib.llm_client import LLMClient, ModelConfig


def _model() -> ModelConfig:
    return ModelConfig(
        name="local-test",
        base_url="http://127.0.0.1",
        port=38005,
        model_id="local-test-model",
        backend="vllm",
        vram_gb=1.0,
        tokens_per_sec=1,
        context_length=1024,
    )


def test_health_check_does_not_activate_service_when_policy_forbids_it(
    monkeypatch,
) -> None:
    client = LLMClient(
        models=[_model()],
        health_check_interval=60,
        max_retries=1,
        timeout=5,
        cache_ttl=60,
        enable_health_checks=False,
        allow_auto_activation=False,
    )
    monkeypatch.setattr(
        client.session,
        "get",
        MagicMock(side_effect=ConnectionError("offline")),
    )
    activation = MagicMock(return_value=True)
    monkeypatch.setattr(client, "_attempt_auto_activation", activation)

    status = client.check_all_health(force=True)

    assert status["local-test"].is_healthy is False
    activation.assert_not_called()


def test_health_check_retains_activation_for_explicitly_allowed_policy(
    monkeypatch,
) -> None:
    client = LLMClient(
        models=[_model()],
        health_check_interval=60,
        max_retries=1,
        timeout=5,
        cache_ttl=60,
        enable_health_checks=False,
        allow_auto_activation=True,
    )
    monkeypatch.setattr(
        client.session,
        "get",
        MagicMock(side_effect=ConnectionError("offline")),
    )
    activation = MagicMock(return_value=False)
    monkeypatch.setattr(client, "_attempt_auto_activation", activation)

    status = client.check_all_health(force=True)

    assert status["local-test"].is_healthy is False
    activation.assert_called_once_with(client.models[0])


def test_local_client_can_ignore_hostile_environment_proxies(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://203.0.113.20:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://203.0.113.20:8080")
    monkeypatch.delenv("NO_PROXY", raising=False)

    client = LLMClient(
        models=[_model()],
        health_check_interval=60,
        max_retries=1,
        timeout=5,
        cache_ttl=60,
        enable_health_checks=False,
        allow_auto_activation=False,
        allow_environment_proxies=False,
    )

    assert client.session.trust_env is False
