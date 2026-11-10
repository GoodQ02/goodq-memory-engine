from __future__ import annotations
from typing import Any, Dict, List
import logging
import os
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import GPU manager for centralized GPU configuration
try:
    from scripts.gpu_config import setup_step_gpu, GPUManager
except ImportError:
    try:
        from gpu_config import setup_step_gpu, GPUManager
    except ImportError:
        # Fallback if GPU manager not available
        def setup_step_gpu(step_name):
            return {"device": "cpu", "step_name": step_name}
        class GPUManager:
            @staticmethod
            def clear_cache():
                pass

# Import score_nrc_emotions at module level
try:
    from steps.common.lexicon import score_nrc_emotions
except ImportError:
    from steps.common.lexicon import score_nrc_emotions

_EMO = {
    "model": None,
    "tok": None,
    "labels": [],
    "device": "cpu",
    "error": None,
    "problem_type": None,
    "model_id": None,
    "model_revision": None,
    "requested_device": "cpu",
    "fallback_chain": [],
    "load_attempts": [],
}


def _ordered_model_labels(model: Any) -> List[str]:
    """Return labels in the loaded model's output-logit order."""

    id2label = getattr(getattr(model, "config", None), "id2label", None)
    if not isinstance(id2label, dict) or not id2label:
        raise ValueError("Loaded emotion model does not expose a non-empty config.id2label mapping")

    try:
        ordered = sorted(((int(index), str(label)) for index, label in id2label.items()), key=lambda item: item[0])
    except (TypeError, ValueError) as exc:
        raise ValueError("Loaded emotion model config.id2label keys must be integer-like") from exc

    return [label for _, label in ordered]


def _model_emotion_meta() -> Dict[str, Any]:
    return {
        "engine": "cardiffnlp",
        "status": "ok",
        "source": "model",
        "problem_type": _EMO["problem_type"],
        "label_count": len(_EMO["labels"]),
        "model_id": _EMO["model_id"],
        "model_revision": _EMO["model_revision"],
        "requested_implementation": f"cardiffnlp_{_EMO['requested_device']}",
        "effective_implementation": f"cardiffnlp_{_EMO['device']}",
        "fallback_chain": list(_EMO.get("fallback_chain") or []),
        "load_attempts": list(_EMO.get("load_attempts") or []),
    }


def _rank_model_emotions(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Run the cached model and preserve every score with its model-owned label."""

    import json as _json
    import torch  # type: ignore

    from steps.common.memory import update_fields
    from steps.text_embed.step import _content_fingerprint

    inputs = _EMO["tok"](_gather_text(item), return_tensors="pt", truncation=True, max_length=512).to(_EMO["device"])
    with torch.no_grad():
        if _EMO.get("device") == "cuda":
            with torch.cuda.amp.autocast():
                logits = _EMO["model"](**inputs).logits
        else:
            logits = _EMO["model"](**inputs).logits

        if _EMO["problem_type"] == "multi_label_classification":
            probabilities = torch.sigmoid(logits)
        elif _EMO["problem_type"] == "single_label_classification":
            probabilities = torch.softmax(logits, dim=-1)
        else:
            raise ValueError(f"Unsupported emotion model problem_type: {_EMO['problem_type']!r}")

    scores = probabilities.cpu().numpy().tolist()[0]
    labels = _EMO["labels"]
    if len(scores) != len(labels):
        raise ValueError(
            f"Emotion model output has {len(scores)} logits but config.id2label defines {len(labels)} labels"
        )

    emotions = [
        {"label": label, "score": float(score)}
        for label, score in sorted(zip(labels, scores), key=lambda item: item[1], reverse=True)
    ]
    try:
        update_fields(cfg, _content_fingerprint(item), emotions_json=_json.dumps(emotions))
        logger.info("Successfully updated complete model emotion ranking for item: %s", item.get("path", "unknown")[:50])
    except Exception as exc:
        logger.error("Failed to persist model emotion ranking: %s", exc, exc_info=True)
    return {"emotions": emotions, "emotion_meta": _model_emotion_meta()}


def _resolve_emotion_snapshot() -> tuple[Path, str, str]:
    """Resolve only the registry-pinned local safetensors snapshot."""

    from steps.common.model_cache_inspector import resolve_pinned_model_snapshot
    from steps.common.model_provisioner import load_registry, resolve_models_root

    registry = load_registry()
    models = registry.get("huggingface_models") if isinstance(registry, dict) else None
    record = models.get("emotion_classify_model") if isinstance(models, dict) else None
    if not isinstance(record, dict):
        raise OSError("emotion_classify_model is absent from the model registry")
    repo_id = str(record.get("repo_id") or "").strip()
    revision = str(record.get("revision") or "").strip()
    if not repo_id or not revision:
        raise OSError("emotion_classify_model registry identity is incomplete")
    snapshot = resolve_pinned_model_snapshot(
        resolve_models_root(),
        "emotion_classify_model",
        required_files=("model.safetensors",),
    )
    if snapshot is None:
        raise OSError(
            "emotion_classify_model exact pinned safetensors snapshot is unavailable "
            f"for revision {revision}"
        )
    return snapshot.resolve(), repo_id, revision


_DEFAULT_RESOLVE_EMOTION_SNAPSHOT_CODE = _resolve_emotion_snapshot.__code__
_WORKER_EMOTION_CUDA_CACHE: Dict[str, bool] = {}

_GPU_ENV_OVERRIDE_KEYS = (
    "GOODQ_DEVICE",
    "GOODQ_FORCE_CPU",
    "GOODQ_NO_AUTO_GPU",
    "GOODQ_HOST_PROFILE",
    "CUDA_VISIBLE_DEVICES",
    "GOODQ_OBJECT_DETECT_FORCE_CPU",
    "GOODQ_EMOTION_FORCE_CPU",
)


def _force_cpu(env: Dict[str, str] | None = None) -> bool:
    active_env = env if env is not None else os.environ
    return (
        str(active_env.get("GOODQ_EMOTION_FORCE_CPU", "")).strip() == "1"
        or str(active_env.get("GOODQ_FORCE_CPU", "")).strip() == "1"
        or str(active_env.get("GOODQ_NO_AUTO_GPU", "")).strip() == "1"
        or str(active_env.get("GOODQ_HOST_PROFILE", "")).strip().upper() == "BASELINE"
        or str(active_env.get("CUDA_VISIBLE_DEVICES", "0")).strip() in {"", "-1"}
        or str(active_env.get("GOODQ_DEVICE", "")).strip().lower() == "cpu"
    )


def _build_worker_probe_env(env: Dict[str, str] | None) -> Dict[str, str]:
    probe_env = os.environ.copy()
    if isinstance(env, dict):
        for key in _GPU_ENV_OVERRIDE_KEYS:
            probe_env.pop(key, None)
        for key, value in env.items():
            if value is not None:
                probe_env[str(key)] = str(value)
    probe_env.setdefault("CUDA_VISIBLE_DEVICES", "0")
    return probe_env


def _resolve_emotion_snapshot_for_env(active_env: Dict[str, str]) -> tuple[Path, str, str]:
    """Resolve the pinned safetensors snapshot honoring worker environment path overrides."""
    if getattr(_resolve_emotion_snapshot, "__code__", None) is not _DEFAULT_RESOLVE_EMOTION_SNAPSHOT_CODE:
        return _resolve_emotion_snapshot()
    env_models_dir = str(active_env.get("GOODQ_MODELS_DIR") or "").strip()
    env_data_root = str(active_env.get("GOODQ_DATA_ROOT") or "").strip()
    if (
        env_models_dir == str(os.environ.get("GOODQ_MODELS_DIR") or "").strip()
        and env_data_root == str(os.environ.get("GOODQ_DATA_ROOT") or "").strip()
    ):
        return _resolve_emotion_snapshot()

    from steps.common.model_cache_inspector import resolve_pinned_model_snapshot
    from steps.common.model_provisioner import load_registry, resolve_models_root

    registry = load_registry()
    models = registry.get("huggingface_models") if isinstance(registry, dict) else None
    record = models.get("emotion_classify_model") if isinstance(models, dict) else None
    if not isinstance(record, dict):
        raise OSError("emotion_classify_model is absent from the model registry")
    repo_id = str(record.get("repo_id") or "").strip()
    revision = str(record.get("revision") or "").strip()
    if not repo_id or not revision:
        raise OSError("emotion_classify_model registry identity is incomplete")
    if env_models_dir:
        models_root = Path(env_models_dir).resolve()
    elif env_data_root:
        models_root = Path(env_data_root).resolve() / "models"
    else:
        models_root = resolve_models_root()
    snapshot = resolve_pinned_model_snapshot(
        models_root,
        "emotion_classify_model",
        required_files=("model.safetensors",),
    )
    if snapshot is None:
        raise OSError(
            "emotion_classify_model exact pinned safetensors snapshot is unavailable "
            f"for revision {revision}"
        )
    return snapshot.resolve(), repo_id, revision


def _emotion_worker_supports_cuda(
    *,
    conda_env: str | None = None,
    env: Dict[str, str] | None = None,
) -> bool | None:
    """Return True/False when the target worker environment's CUDA capability is confirmed, or None if unknown."""
    import subprocess
    import sys

    active_env = env if env is not None else os.environ
    device_override = str(active_env.get("GOODQ_DEVICE", "")).strip().lower()
    if device_override.startswith("cuda"):
        return True
    if device_override:
        return False

    torch_mod = sys.modules.get("torch")
    if conda_env is None and torch_mod is not None and not hasattr(torch_mod, "__file__"):
        try:
            return bool(torch_mod.cuda.is_available())
        except Exception:
            return None

    target_env = (conda_env or active_env.get("GOODQ_WORKER_CONDA_ENV") or "goodq_core").strip()
    current_env = os.environ.get("CONDA_DEFAULT_ENV", "").strip()
    python_exe = None
    if target_env:
        try:
            from configs.python_paths import get_env_python

            python_exe = get_env_python(target_env)
            if (
                python_exe is None
                and target_env in {"goodq_emotion", "goodq_emotion_classify"}
                and getattr(get_env_python, "__module__", "") == "configs.python_paths"
            ):
                python_exe = get_env_python("goodq_core")
        except Exception:
            python_exe = None

    if python_exe is not None and Path(python_exe).exists():
        resolved_exe = str(Path(python_exe).resolve())
        cached = _WORKER_EMOTION_CUDA_CACHE.get(resolved_exe)
        if cached is not None:
            return cached
        try:
            proc = subprocess.run(
                [
                    resolved_exe,
                    "-c",
                    "import sys, torch; sys.exit(0 if torch.cuda.is_available() else 1)",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                env=_build_worker_probe_env(env),
            )
        except Exception:
            return None
        if proc.returncode == 0:
            _WORKER_EMOTION_CUDA_CACHE[resolved_exe] = True
            return True
        if proc.returncode == 1 and "Traceback" not in (proc.stderr or ""):
            _WORKER_EMOTION_CUDA_CACHE[resolved_exe] = False
            return False
        return None

    if target_env and target_env != current_env:
        return None

    try:
        import torch  # type: ignore

        return bool(torch.cuda.is_available())
    except Exception:
        return None


def resolve_effective_device(
    *,
    env: Dict[str, str] | None = None,
    conda_env: str | None = None,
) -> str:
    """Return 'cuda', 'cpu', or 'unknown' based on the resolved worker environment."""
    active_env = env if env is not None else os.environ
    if _force_cpu(active_env):
        return "cpu"
    if env is None and conda_env is None and _EMO.get("model") is not None:
        return "cuda" if str(_EMO.get("device") or "cpu").strip().lower().startswith("cuda") else "cpu"
    try:
        _resolve_emotion_snapshot_for_env(active_env)
    except OSError:
        return "cpu"
    except Exception:
        return "unknown"
    supported = _emotion_worker_supports_cuda(conda_env=conda_env, env=dict(active_env))
    if supported is None:
        return "unknown"
    return "cuda" if supported else "cpu"


def _load_emotion():
    if _EMO["model"] is not None:
        return
    
    # Configure GPU using centralized manager (Phase 3)
    gpu_config = setup_step_gpu("emotion_classify")
    if _force_cpu():
        requested_device = "cpu"
    else:
        requested_device = str(gpu_config["device"] or "cpu").strip().lower()
    
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification  # type: ignore
        snapshot, repo_id, revision = _resolve_emotion_snapshot()
        attempts = [requested_device]
        if requested_device != "cpu":
            attempts.append("cpu")
        load_errors: list[str] = []
        for effective_device in attempts:
            try:
                tok = AutoTokenizer.from_pretrained(
                    snapshot,
                    local_files_only=True,
                )
                model = AutoModelForSequenceClassification.from_pretrained(
                    snapshot,
                    use_safetensors=True,
                    local_files_only=True,
                )
                model = model.to(effective_device).eval()
                labels = _ordered_model_labels(model)
                problem_type = str(
                    getattr(model.config, "problem_type", "") or ""
                ).strip()
                if problem_type not in {
                    "multi_label_classification",
                    "single_label_classification",
                }:
                    raise ValueError(
                        "Unsupported emotion model config.problem_type: "
                        f"{problem_type!r}"
                    )
                _EMO.update(
                    {
                        "model": model,
                        "tok": tok,
                        "labels": labels,
                        "device": effective_device,
                        "error": None,
                        "problem_type": problem_type,
                        "model_id": repo_id,
                        "model_revision": revision,
                        "requested_device": requested_device,
                        "fallback_chain": (
                            ["cpu_fallback"]
                            if effective_device == "cpu" and requested_device != "cpu"
                            else []
                        ),
                        "load_attempts": list(attempts[: attempts.index(effective_device) + 1]),
                    }
                )
                break
            except Exception as exc:
                load_errors.append(
                    f"{effective_device}:{type(exc).__name__}:{exc}"
                )
                GPUManager.clear_cache()
        else:
            raise RuntimeError(
                "emotion model load attempts failed: " + " | ".join(load_errors)
            )

        memory_fraction = gpu_config.get("memory_fraction")
        if isinstance(memory_fraction, (int, float)):
            logger.info(f"[OK] Emotion model loaded on {_EMO['device']} (GPU config: {memory_fraction:.1%} memory)")
        else:
            logger.info(f"[OK] Emotion model loaded on {_EMO['device']}")
    except Exception as e:
        logger.error(f"[FAIL] Failed to load emotion model: {str(e)}")
        logger.warning("Emotion model unavailable after bounded load attempts")
        _EMO.update(
            {
                "model": None,
                "tok": None,
                "labels": [],
                "device": "cpu",
                "error": str(e),
                "problem_type": None,
                "model_id": None,
                "model_revision": None,
                "requested_device": requested_device,
                "fallback_chain": [],
                "load_attempts": (
                    [requested_device, "cpu"]
                    if requested_device != "cpu"
                    else ["cpu"]
                ),
            }
        )
        # Clear any partial GPU allocations
        GPUManager.clear_cache()


def _gather_text(item: Dict[str, Any]) -> str:
    for k in ("document_text", "transcript", "ocr_text", "caption"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def emotion_classify(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    text = _gather_text(item)
    if not text:
        return {"emotions": None, "emotion_meta": {"status": "no_text"}}
    _load_emotion()
    use_nrc_cfg = bool(((cfg.get("config", {}) or {}).get("analysis", {}) or {}).get("use_nrc_lexicon", False))
    # A verified local model remains usable in offline mode; only provisioning may
    # be offline-constrained.
    model_failed = False
    model_error: Exception | None = None
    if _EMO["model"] is not None:
        try:
            return _rank_model_emotions(item, cfg)
        except Exception as exc:
            model_failed = True
            model_error = exc
            logger.error("Emotion classification failed: %s", exc, exc_info=True)

    # NRC is a distinct lexicon fallback, never a blended model result.
    if use_nrc_cfg or model_failed or _EMO["model"] is None:
        try:
            scr = score_nrc_emotions(text, cfg)
        except Exception as e:
            scr = None
        if scr:
            pairs = sorted(scr.items(), key=lambda x: x[1], reverse=True)
            emotions = [{"label": label, "score": float(f"{score:.4f}")} for label, score in pairs]
            requested_device = str(_EMO.get("requested_device") or "cpu")
            fallback_error = model_error if model_failed else _EMO.get("error")
            fallback_meta = {
                "engine": "nrc-lex",
                "status": "fallback",
                "source": "lexicon",
                "label_count": len(emotions),
                "reason": "model_inference_failed" if model_failed else "model_unavailable",
                "requested_implementation": f"cardiffnlp_{requested_device}",
                "effective_implementation": "nrc_lexicon",
                "fallback_chain": ["nrc_lexicon"],
            }
            if fallback_error:
                fallback_meta["model_error"] = str(fallback_error)[:500]
            return {
                "emotions": emotions,
                "emotion_meta": fallback_meta,
            }

    # If nothing else worked
    if _EMO["model"] is None:
        meta = {"status": "unavailable", "engine": "cardiffnlp", "reason": "model_load_failed"}
        if _EMO.get("error"):
            meta["error"] = str(_EMO.get("error"))[:500]
        return {"emotions": None, "emotion_meta": meta}

    return {
        "emotions": None,
        "emotion_meta": {
            "engine": "cardiffnlp",
            "status": "error",
            "reason": "model_inference_failed",
            "error": str(model_error or "reason unknown")[:500],
        },
    }
