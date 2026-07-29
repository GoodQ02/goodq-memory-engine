from unittest.mock import MagicMock

import pytest

from lib.llm_client import ModelConfig


def _ollama_model(*, base_url: str = "http://127.0.0.1", port: int = 31434) -> ModelConfig:
    return ModelConfig(
        name="configured-ollama",
        base_url=base_url,
        port=port,
        model_id="hermes-gemma4-64k:12b",
        backend="ollama",
        vram_gb=1.0,
        tokens_per_sec=1,
        context_length=1024,
    )


def test_ollama_endpoint_uses_configured_port_without_opportunistic_probe(monkeypatch) -> None:
    probe = MagicMock()
    monkeypatch.delenv("GOODQ_OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.setattr("lib.llm_client.requests.get", probe)

    endpoint = _ollama_model().endpoint

    assert endpoint == "http://127.0.0.1:31434/v1"
    probe.assert_not_called()


def test_goodq_ollama_url_environment_override_beats_configured_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("GOODQ_OLLAMA_URL", "http://127.0.0.1:11434/v1")

    assert _ollama_model().endpoint == "http://127.0.0.1:11434/v1"


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1:31434", "http://127.0.0.1:31434/v1"),
        ("http://127.0.0.1:31434/v1", "http://127.0.0.1:31434/v1"),
        ("http://127.0.0.1:31434/v1/", "http://127.0.0.1:31434/v1"),
    ],
)
def test_ollama_host_override_normalizes_openai_v1_suffix(monkeypatch, host, expected) -> None:
    monkeypatch.delenv("GOODQ_OLLAMA_URL", raising=False)
    monkeypatch.setenv("OLLAMA_HOST", host)

    assert _ollama_model().endpoint == expected
