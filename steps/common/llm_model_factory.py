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

    models_list = [
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

    # Dynamically integrate profile-selected reasoning models if profile is set
    host_profile = (os.environ.get("GOODQ_HOST_PROFILE") or cfg.get("host", {}).get("profile") or "").strip().upper()
    
    if host_profile in ("GPU_16GB_INGEST_QUALITY", "GPU_16GB_INTERACTIVE_LIGHT"):
        import yaml
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        models_config_path = os.path.join(repo_root, "configs", "models_config.yaml")
        model_registry_path = os.path.join(repo_root, "configs", "model_registry.yaml")
        
        try:
            if os.path.isfile(models_config_path):
                with open(models_config_path, "r", encoding="utf-8") as f:
                    models_cfg = yaml.safe_load(f) or {}
                
                profile_info = models_cfg.get("profiles", {}).get(host_profile, {})
                reasoning_model_key = profile_info.get("reasoning")
                
                if reasoning_model_key:
                    model_entry = models_cfg.get("models", {}).get(reasoning_model_key, {})
                    if model_entry:
                        # Load registry to get exact VRAM estimate
                        vram_estimate = 2.0
                        if os.path.isfile(model_registry_path):
                            with open(model_registry_path, "r", encoding="utf-8") as rf:
                                registry_cfg = yaml.safe_load(rf) or {}
                            registry_models = registry_cfg.get("huggingface_models", {}) or {}
                            registry_entry = registry_models.get(reasoning_model_key, {})
                            if not registry_entry:
                                # Fallback fuzzy key matching
                                for k, entry in registry_models.items():
                                    if (k.startswith(reasoning_model_key) or 
                                        reasoning_model_key.startswith(k) or 
                                        k.replace("_distill_qwen", "") == reasoning_model_key or
                                        reasoning_model_key.replace("_", "") in k.replace("_", "")):
                                        registry_entry = entry
                                        break
                            vram_estimate = float(registry_entry.get("vram_estimate_gb", 2.0))
                        
                        raw_base_url = model_entry.get("base_url", "http://localhost:11434/v1")
                        m_base, m_port = _split_base_and_port(raw_base_url)
                        
                        profile_model = ModelConfig(
                            name=model_entry.get("name", reasoning_model_key),
                            base_url=m_base,
                            port=m_port,
                            model_id=model_entry.get("model_id", reasoning_model_key),
                            backend=model_entry.get("engine", "ollama"),
                            vram_gb=vram_estimate,
                            tokens_per_sec=150,
                            context_length=int(model_entry.get("max_tokens", 16384)),
                            capabilities=["chat", "reasoning", "profile_primary"],
                            priority=200,  # Ensure it is prioritized
                        )
                        # Insert at the beginning of the list to be primary
                        models_list.insert(0, profile_model)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to dynamically load models from models_config.yaml: %s", e)

    return models_list


build_llm_models = _build_llm_models
