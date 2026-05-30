import os
from typing import Any, Dict, List
from urllib.parse import urlparse

from lib.llm_client import ModelConfig


def _split_base_and_port(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError(f"Invalid LLM URL: {url}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{parsed.scheme}://{parsed.hostname}", port


def _build_llm_models(cfg: Dict[str, Any]) -> List[ModelConfig]:
    llm_cfg = cfg.get("llm", {}) or {}
    vllm_url = llm_cfg.get("vllm_url")
    ollama_url = llm_cfg.get("ollama_url")
    if not vllm_url or not ollama_url:
        raise ValueError("Missing llm.vllm_url or llm.ollama_url in config")

    vllm_base, vllm_port = _split_base_and_port(str(vllm_url))
    ollama_base, ollama_port = _split_base_and_port(str(ollama_url))

    vllm_model_id = (
        llm_cfg.get("vllm_model")
        or os.environ.get("GOODQ_WSL_MODEL_PATH")
        or "meta-llama/Llama-3.2-1B-Instruct"
    )
    ollama_model_id = llm_cfg.get("ollama_model", "phi4")

    return [
        ModelConfig(
            name="Llama-1B-Speed",
            base_url=vllm_base,
            port=vllm_port,
            model_id=vllm_model_id,
            backend="vllm",
            vram_gb=2.3,
            tokens_per_sec=178,
            context_length=131072,
            capabilities=["chat", "fast"],
            priority=100,
        ),
        ModelConfig(
            name="Llama3.2-Ollama",
            base_url=ollama_base,
            port=ollama_port,
            model_id=ollama_model_id,
            backend="ollama",
            vram_gb=2.0,
            tokens_per_sec=120,
            context_length=131072,
            capabilities=["chat", "fallback", "quality"],
            priority=90,
        ),
    ]


build_llm_models = _build_llm_models
