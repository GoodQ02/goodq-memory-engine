from __future__ import annotations

import logging
import os
import sys
import time
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Ensure dependencies (filelock) are importable
_REPO_ROOT = Path(__file__).resolve().parents[2]
_VENDOR_DIR = _REPO_ROOT / "vendor"
if _VENDOR_DIR.exists() and str(_VENDOR_DIR) not in sys.path:
    sys.path.append(str(_VENDOR_DIR))

from filelock import FileLock
from steps.common.config_loader import get_runtime_paths, load_configs

logger = logging.getLogger(__name__)


def _emit_first_use_model_status(message: str) -> None:
    """Make on-demand model provisioning visible in an operator console."""
    print(f"[MODEL] {message}", flush=True)
    logger.info(message)

# Fallback registry matching configs/model_registry.yaml and bootstrap fallback list
_FALLBACK_REGISTRY = {
    "Salesforce/blip-image-captioning-base": {
        "key": "blip_caption",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "nlpconnect/vit-gpt2-image-captioning": {
        "key": "vit_gpt2_caption",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "OPTIONAL_FEATURE",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "WARN_DEGRADED"
    },
    "laion/CLIP-ViT-L-14-DataComp.XL-s13B-b90K": {
        "key": "clip_vit",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "facebook/dinov2-large": {
        "key": "dinov2",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "facebook/dinov2-base": {
        "key": "dinov2_base",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "DEV_TEST_ONLY",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "WARN_DEGRADED"
    },
    "sentence-transformers/all-MiniLM-L6-v2": {
        "key": "sentence_transformer",
        "tier_scope": ["baseline", "cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "laion/clap-htsat-unfused": {
        "key": "clap_audio",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "pyannote/speaker-diarization-3.1": {
        "key": "pyannote_diarization",
        "tier_scope": ["wsl_audio"],
        "classification": "OPTIONAL_FEATURE",
        "gated": True,
        "requires_token": True,
        "token_env": "PYANNOTE_TOKEN",
        "failure_behavior": "WARN_DEGRADED"
    },
    "pyannote/segmentation-3.0": {
        "key": "pyannote_segmentation",
        "tier_scope": ["wsl_audio"],
        "classification": "OPTIONAL_FEATURE",
        "gated": True,
        "requires_token": True,
        "token_env": "PYANNOTE_TOKEN",
        "failure_behavior": "WARN_DEGRADED"
    },
    "pyannote/wespeaker-voxceleb-resnet34-LM": {
        "key": "pyannote_wespeaker",
        "tier_scope": ["wsl_audio"],
        "classification": "OPTIONAL_FEATURE",
        "gated": True,
        "requires_token": True,
        "token_env": "PYANNOTE_TOKEN",
        "failure_behavior": "WARN_DEGRADED"
    },
    "Systran/faster-whisper-medium": {
        "key": "faster_whisper_medium",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "Systran/faster-whisper-small": {
        "key": "faster_whisper_small",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "Systran/faster-whisper-large-v3": {
        "key": "faster_whisper_large_v3",
        "tier_scope": ["gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "superb/hubert-large-superb-er": {
        "key": "hubert_emotion",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition": {
        "key": "wav2vec2_emotion",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "facebook/wav2vec2-base-960h": {
        "key": "wav2vec2_base_960h",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "dslim/bert-base-NER": {
        "key": "bert_ner",
        "tier_scope": ["baseline", "cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "Qwen/Qwen2.5-VL-7B-Instruct": {
        "key": "qwen2_5_vl_7b",
        "tier_scope": ["gpu_enhanced"],
        "classification": "OPTIONAL_FEATURE",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "WARN_DEGRADED"
    },
    "Qwen/Qwen2.5-VL-3B-Instruct": {
        "key": "qwen2_5_vl_3b",
        "tier_scope": ["gpu_enhanced"],
        "classification": "OPTIONAL_FEATURE",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "WARN_DEGRADED"
    },
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B": {
        "key": "deepseek_r1_distill_qwen_14b",
        "tier_scope": ["gpu_enhanced"],
        "classification": "OPTIONAL_FEATURE",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "WARN_DEGRADED"
    },
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B": {
        "key": "deepseek_r1_distill_qwen_7b",
        "tier_scope": ["gpu_enhanced"],
        "classification": "OPTIONAL_FEATURE",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "WARN_DEGRADED"
    },
    "google/gemma-4-12b-it": {
        "key": "gemma_4_12b_unified",
        "tier_scope": ["gpu_enhanced"],
        "classification": "OPTIONAL_FEATURE",
        "gated": True,
        "requires_token": True,
        "token_env": "HF_TOKEN",
        "failure_behavior": "WARN_DEGRADED"
    },
    "snakers4/silero-vad": {
        "key": "silero_vad",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "cardiffnlp/twitter-roberta-base-emotion-latest": {
        "key": "emotion_classify_model",
        "tier_scope": ["baseline", "cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "distilbert-base-uncased-finetuned-sst-2-english": {
        "key": "sentiment_model",
        "tier_scope": ["baseline", "cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "yolo_v8n": {
        "key": "yolo_v8n",
        "is_external": True,
        "local_path": "yolo/yolov8n.pt",
        "source_url": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "REQUIRED_FIRST_LAUNCH",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "FATAL_HALT"
    },
    "facenet_vggface2": {
        "key": "facenet_vggface2",
        "is_external": True,
        "local_path": "checkpoints/20180402-114759-vggface2.pt",
        "source_url": "https://github.com/timesler/facenet-pytorch/releases/download/v2.2.9/20180402-114759-vggface2.pt",
        "tier_scope": ["cpu_only", "gpu_enhanced"],
        "classification": "DEV_TEST_ONLY",
        "gated": False,
        "requires_token": False,
        "token_env": None,
        "failure_behavior": "WARN_DEGRADED"
    }
}

def redact_sensitive_info(text: str, repo_id: Optional[str] = None) -> str:
    if not text:
        return text
    tokens_to_redact = []
    try:
        t = resolve_hf_token(repo_id)
        if t and len(t) > 5:
            tokens_to_redact.append(t)
    except Exception:
        pass
        
    for tok in tokens_to_redact:
        if tok in text:
            text = text.replace(tok, "<REDACTED>")
            
    import re
    hf_pat = re.compile(r"hf_[a-zA-Z0-9]+")
    text = hf_pat.sub("hf_***", text)
    return text

def log_download_event(message: str, repo_id: Optional[str] = None):
    try:
        models_root = resolve_models_root()
        data_root = models_root.parent
        logs_dir = data_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = logs_dir / "model_downloads.log"
        
        redacted_message = redact_sensitive_info(message, repo_id)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {redacted_message}\n")
    except Exception as e:
        logger.warning(f"Failed to write to model_downloads.log: {e}")

@dataclass
class ModelProvisionResult:
    status: str  # 'cached', 'downloaded', 'offline_missing', 'gated_unauthorized', 'failed'
    repo_id: str
    revision: Optional[str]
    local_path: Optional[str]
    gated: bool
    required: bool
    elapsed_seconds: float
    files_checked: List[str] = field(default_factory=list)
    error: Optional[str] = None
    attempts_made: int = 1

    def __post_init__(self):
        if self.error:
            self.error = redact_sensitive_info(self.error, self.repo_id)


def resolve_models_root() -> Path:
    explicit = os.environ.get("GOODQ_MODELS_DIR")
    if explicit:
        return Path(explicit).resolve()
    try:
        cfg = load_configs({})
        models_cache = (((cfg.get("paths", {}) or {}).get("models_cache")) or "").strip()
        if models_cache:
            return Path(models_cache).resolve()
    except Exception:
        pass
    fallback_data_root = os.environ.get("GOODQ_DATA_ROOT")
    if fallback_data_root:
        return Path(fallback_data_root).resolve() / "models"
    return _REPO_ROOT / "models"

def resolve_hf_token(repo_id: Optional[str] = None) -> Optional[str]:
    # Check pyannote token if applicable
    if repo_id and repo_id.startswith("pyannote/"):
        val = os.environ.get("PYANNOTE_TOKEN")
        if val:
            return val.strip()

    for var in ("HF_TOKEN", "HF_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HUGGINGFACE_TOKEN"):
        val = os.environ.get(var)
        if val:
            return val.strip()
            
    # Load from .env.local
    for env_path in (_REPO_ROOT / ".env.local", resolve_models_root().parent / ".env.local"):
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    if k == "HF_TOKEN" or (repo_id and repo_id.startswith("pyannote/") and k == "PYANNOTE_TOKEN"):
                        v_clean = v.strip().strip('"').strip("'")
                        if v_clean:
                            return v_clean
            except Exception:
                pass
    return None
def load_registry() -> Dict[str, Any]:
    registry_path = _REPO_ROOT / "configs" / "model_registry.yaml"
    if registry_path.is_file():
        try:
            import yaml
            with open(registry_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to load model registry YAML: {e}")
    return {}

VALID_CLASSIFICATIONS = {"REQUIRED_INSTALL_BLOCKER", "REQUIRED_FIRST_LAUNCH", "OPTIONAL_FEATURE", "DEV_TEST_ONLY", "DEFERRED_EXTERNAL_PAYLOAD"}
VALID_FAILURE_BEHAVIORS = {"FATAL_HALT", "WARN_DEGRADED"}

def _validate_and_normalize_metadata(info: Dict[str, Any], repo_id_or_key: str) -> Dict[str, Any]:
    # 1. Resolve and validate tier_scope
    tier_scope = info.get("tier_scope")
    if tier_scope is None:
        fb = _FALLBACK_REGISTRY.get(repo_id_or_key) or next((v for k, v in _FALLBACK_REGISTRY.items() if v.get("key") == repo_id_or_key), None)
        if fb:
            tier_scope = fb.get("tier_scope")
    if tier_scope is None:
        raise ValueError(f"Model '{repo_id_or_key}' has missing tier_scope.")
    if not isinstance(tier_scope, list):
        raise ValueError(f"Model '{repo_id_or_key}' has invalid tier_scope: {tier_scope} (must be list of strings)")
    for scope in tier_scope:
        if not isinstance(scope, str):
            raise ValueError(f"Model '{repo_id_or_key}' has invalid scope item: {scope} (must be str)")

    # 2. Resolve and validate classification
    classification = info.get("classification")
    if classification is None:
        fb = _FALLBACK_REGISTRY.get(repo_id_or_key) or next((v for k, v in _FALLBACK_REGISTRY.items() if v.get("key") == repo_id_or_key), None)
        if fb:
            classification = fb.get("classification")
    if classification not in VALID_CLASSIFICATIONS:
        raise ValueError(f"Model '{repo_id_or_key}' has invalid or missing classification: {classification} (must be in {VALID_CLASSIFICATIONS})")

    # 3. Resolve and validate gated
    gated = info.get("gated")
    if gated is None:
        fb = _FALLBACK_REGISTRY.get(repo_id_or_key) or next((v for k, v in _FALLBACK_REGISTRY.items() if v.get("key") == repo_id_or_key), None)
        if fb:
            gated = fb.get("gated")
        else:
            gated = info.get("requires_auth", False) or info.get("access_control", {}).get("requires_hf_token", False)
    if not isinstance(gated, bool):
        raise ValueError(f"Model '{repo_id_or_key}' has invalid gated value: {gated} (must be boolean)")

    # 4. Resolve and validate requires_token
    requires_token = info.get("requires_token")
    if requires_token is None:
        fb = _FALLBACK_REGISTRY.get(repo_id_or_key) or next((v for k, v in _FALLBACK_REGISTRY.items() if v.get("key") == repo_id_or_key), None)
        if fb:
            requires_token = fb.get("requires_token")
        else:
            requires_token = gated
    if not isinstance(requires_token, bool):
        raise ValueError(f"Model '{repo_id_or_key}' has invalid requires_token value: {requires_token} (must be boolean)")

    # 5. Resolve and validate token_env
    token_env = info.get("token_env")
    if token_env is None and (info.get("token_env") is not None or "token_env" in info):
        token_env = None
    if token_env is None:
        fb = _FALLBACK_REGISTRY.get(repo_id_or_key) or next((v for k, v in _FALLBACK_REGISTRY.items() if v.get("key") == repo_id_or_key), None)
        if fb:
            token_env = fb.get("token_env")
    if token_env is not None and not isinstance(token_env, str):
        raise ValueError(f"Model '{repo_id_or_key}' has invalid token_env: {token_env} (must be string or null)")

    # 6. Resolve and validate failure_behavior
    failure_behavior = info.get("failure_behavior")
    if failure_behavior is None:
        fb = _FALLBACK_REGISTRY.get(repo_id_or_key) or next((v for k, v in _FALLBACK_REGISTRY.items() if v.get("key") == repo_id_or_key), None)
        if fb:
            failure_behavior = fb.get("failure_behavior")
    if failure_behavior not in VALID_FAILURE_BEHAVIORS:
        raise ValueError(f"Model '{repo_id_or_key}' has invalid or missing failure_behavior: {failure_behavior} (must be in {VALID_FAILURE_BEHAVIORS})")

    revision = info.get("revision") or info.get("version")
    
    return {
        "tier_scope": tier_scope,
        "classification": classification,
        "gated": gated,
        "requires_token": requires_token,
        "token_env": token_env,
        "failure_behavior": failure_behavior,
        "revision": revision,
        "is_external": info.get("is_external", False),
        "source_url": info.get("source_url"),
        "local_path": info.get("local_path"),
        "required": info.get("required", classification in ("REQUIRED_INSTALL_BLOCKER", "REQUIRED_FIRST_LAUNCH")),
    }

def lookup_model(repo_id_or_key: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """Look up repo_id and access metadata from the model registry or fallbacks."""
    registry = load_registry()
    
    # 1. Check HF models
    hf_models = registry.get("huggingface_models", {})
    if repo_id_or_key in hf_models:
        info = hf_models[repo_id_or_key]
        repo_id = info.get("repo_id")
        return repo_id, _validate_and_normalize_metadata(info, repo_id_or_key)
        
    for key, info in hf_models.items():
        if info.get("repo_id") == repo_id_or_key:
            return repo_id_or_key, _validate_and_normalize_metadata(info, key)

    # 2. Check external models
    external_models = registry.get("external_models", {})
    if repo_id_or_key in external_models:
        info = external_models[repo_id_or_key]
        info_with_ext = dict(info)
        info_with_ext["is_external"] = True
        return repo_id_or_key, _validate_and_normalize_metadata(info_with_ext, repo_id_or_key)

    # 3. Check fallbacks
    if repo_id_or_key in _FALLBACK_REGISTRY:
        fb = _FALLBACK_REGISTRY[repo_id_or_key]
        key = fb.get("key") or repo_id_or_key
        return key, _validate_and_normalize_metadata(fb, repo_id_or_key)
        
    for r_id, fb in _FALLBACK_REGISTRY.items():
        if fb.get("key") == repo_id_or_key or r_id == repo_id_or_key:
            return r_id, _validate_and_normalize_metadata(fb, r_id)
            
    return None, {}

def verify_snapshot_files(snapshot_path: Path, repo_id: str) -> List[str]:
    if not snapshot_path.is_dir():
        return []
    
    files = [p for p in snapshot_path.glob("**/*") if p.is_file()]
    file_names = [p.name for p in files]
    
    # Silero VAD specific checks
    if "silero-vad" in repo_id:
        if any(name.endswith((".onnx", ".pt", ".jit")) for name in file_names):
            return file_names
        return []

    # CTranslate2 / faster-whisper specific checks
    if "faster-whisper" in repo_id:
        has_bin = "model.bin" in file_names
        has_config = "config.json" in file_names
        if has_bin and has_config:
            return file_names
        return []

    # PyAnnote speaker diarization specific checks (pipeline config only)
    if "speaker-diarization" in repo_id:
        if "config.yaml" in file_names:
            return file_names
        return []

    # Standard HF model checks
    has_config = any(name in ("config.json", "config.yaml", "preprocessor_config.json") for name in file_names)
    has_weights = any(name.endswith((".bin", ".safetensors", ".pt", ".onnx", ".gguf")) for name in file_names)
    
    if has_config and has_weights:
        return file_names
        
    return []

def ensure_model_cached(
    repo_id_or_key: str,
    revision: Optional[str] = None,
    gated: Optional[bool] = None,
    required: Optional[bool] = None,
    offline: bool = False
) -> ModelProvisionResult:
    start_time = time.time()
    attempts_made = 1
    
    # 1. Lookup in allowlist
    repo_id, metadata = lookup_model(repo_id_or_key)
    if not repo_id:
        # Unknown/unallowed model ID
        elapsed = time.time() - start_time
        err_msg = redact_sensitive_info(f"Refused unknown or unallowlisted model repository ID: '{repo_id_or_key}'", repo_id_or_key)
        logger.error(err_msg)
        log_download_event(err_msg, repo_id_or_key)
        return ModelProvisionResult(
            status="failed",
            repo_id=repo_id_or_key,
            revision=revision,
            local_path=None,
            gated=False,
            required=True,
            elapsed_seconds=elapsed,
            error=err_msg,
            attempts_made=attempts_made
        )
        
    # Use resolved metadata if not overridden
    is_gated = metadata["gated"] if gated is None else gated
    is_required = metadata["required"] if required is None else required
    resolved_revision = revision or metadata["revision"]
    
    # Respect global offline environment flags
    env_offline = (
        os.environ.get("HF_HUB_OFFLINE", "").strip() in ("1", "true", "TRUE") or
        os.environ.get("GOODQ_OFFLINE", "").strip() in ("1", "true", "TRUE")
    )
    is_offline = offline or env_offline
    
    models_root = resolve_models_root()
    
    is_external = metadata.get("is_external", False)
    if is_external:
        local_rel_path = metadata.get("local_path")
        if not local_rel_path:
            local_rel_path = f"external/{repo_id}"
        target_path = models_root / local_rel_path
        
        # Check if cached
        if target_path.is_file() and target_path.stat().st_size > 1024:
            elapsed = time.time() - start_time
            res = ModelProvisionResult(
                status="cached",
                repo_id=repo_id,
                revision=resolved_revision,
                local_path=str(target_path.absolute()),
                gated=is_gated,
                required=is_required,
                elapsed_seconds=elapsed,
                files_checked=[target_path.name],
                attempts_made=attempts_made
            )
            msg = f"External model {repo_id} retrieved from cache (status={res.status})"
            logger.info(msg)
            log_download_event(msg, repo_id)
            return res
            
        # If offline and missing, fail/degrade cleanly
        if is_offline:
            elapsed = time.time() - start_time
            status = "offline_missing"
            if is_required:
                err_msg = redact_sensitive_info(f"Offline mode: required external model '{repo_id}' is missing from local cache. To download, connect to the internet and run: python scripts/bootstrap_models.py", repo_id)
                logger.error(err_msg)
            else:
                err_msg = redact_sensitive_info(f"Offline mode: optional external model '{repo_id}' is missing from local cache. Skipping optional step.", repo_id)
                logger.warning(err_msg)
                
            log_download_event(err_msg, repo_id)
            return ModelProvisionResult(
                status=status,
                repo_id=repo_id,
                revision=resolved_revision,
                local_path=None,
                gated=is_gated,
                required=is_required,
                elapsed_seconds=elapsed,
                error=err_msg,
                attempts_made=attempts_made
            )
            
        # Online download under lock
        lock_file = models_root / f"{repo_id.replace('/', '--')}.lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Acquiring lock for external model {repo_id} download...")
        lock = FileLock(str(lock_file), timeout=300)
        
        try:
            with lock:
                # Recheck cache inside lock
                if target_path.is_file() and target_path.stat().st_size > 1024:
                    elapsed = time.time() - start_time
                    res = ModelProvisionResult(
                        status="cached",
                        repo_id=repo_id,
                        revision=resolved_revision,
                        local_path=str(target_path.absolute()),
                        gated=is_gated,
                        required=is_required,
                        elapsed_seconds=elapsed,
                        files_checked=[target_path.name],
                        attempts_made=attempts_made
                    )
                    return res
                
                # Perform download
                import urllib.request
                source_url = metadata.get("source_url")
                if not source_url:
                    raise ValueError(f"No source_url specified for external model '{repo_id}'")
                    
                target_path.parent.mkdir(parents=True, exist_ok=True)
                temp_target = target_path.with_suffix(".tmp")
                
                attempts = 4
                for attempt in range(1, attempts + 1):
                    attempts_made = attempt
                    try:
                        _emit_first_use_model_status(
                            f"First-use fetch: downloading external model '{repo_id}' "
                            f"(attempt {attempt}/{attempts}); this can take a few minutes."
                        )
                        logger.info(f"Downloading external model '{repo_id}' from '{source_url}' (attempt {attempt}/{attempts})...")
                        req = urllib.request.Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=120) as response, open(temp_target, "wb") as handle:
                            while True:
                                chunk = response.read(1024 * 1024)
                                if not chunk:
                                    break
                                handle.write(chunk)
                        os.replace(temp_target, target_path)
                        break
                    except Exception as e:
                        try:
                            temp_target.unlink(missing_ok=True)
                        except Exception:
                            pass
                        if attempt < attempts:
                            logger.warning(f"Transient download error for external model '{repo_id}': {e}. Retrying...")
                            time.sleep(3 * attempt)
                            continue
                        raise
                        
                elapsed = time.time() - start_time
                res = ModelProvisionResult(
                    status="downloaded",
                    repo_id=repo_id,
                    revision=resolved_revision,
                    local_path=str(target_path.absolute()),
                    gated=is_gated,
                    required=is_required,
                    elapsed_seconds=elapsed,
                    files_checked=[target_path.name],
                    attempts_made=attempts_made
                )
                msg = f"External model {repo_id} downloaded successfully"
                _emit_first_use_model_status(f"First-use fetch complete: {repo_id} is cached locally.")
                logger.info(msg)
                log_download_event(msg, repo_id)
                return res
        except Exception as e:
            elapsed = time.time() - start_time
            err_msg = f"Failed to download external model '{repo_id}': {e}"
            logger.error(err_msg)
            log_download_event(err_msg, repo_id)
            return ModelProvisionResult(
                status="failed",
                repo_id=repo_id,
                revision=resolved_revision,
                local_path=None,
                gated=is_gated,
                required=is_required,
                elapsed_seconds=elapsed,
                error=err_msg,
                attempts_made=attempts_made
            )
            
    repo_cache_name = repo_id.replace("/", "--")
    repo_cache_dir = models_root / "hub" / f"models--{repo_cache_name}"
    snapshots_dir = repo_cache_dir / "snapshots"
    
    # Check for existing snapshots
    local_path = None
    files_checked = []
    
    # Special-case check for Silero VAD locally
    if repo_id == "snakers4/silero-vad":
        custom_dir = models_root / "hub" / "snakers4_silero-vad_master"
        if custom_dir.is_dir():
            files_checked = verify_snapshot_files(custom_dir, repo_id)
            if files_checked:
                local_path = custom_dir
                resolved_revision = "master"
                
    if not local_path and resolved_revision:
        candidate_snapshot = snapshots_dir / resolved_revision
        files_checked = verify_snapshot_files(candidate_snapshot, repo_id)
        if files_checked:
            local_path = candidate_snapshot
    if not local_path:
        # Check refs/main first
        refs_main = repo_cache_dir / "refs" / "main"
        if refs_main.is_file():
            try:
                rev = refs_main.read_text(encoding="utf-8").strip()
                if rev:
                    candidate_snapshot = snapshots_dir / rev
                    files_checked = verify_snapshot_files(candidate_snapshot, repo_id)
                    if files_checked:
                        local_path = candidate_snapshot
                        resolved_revision = rev
            except Exception:
                pass
                
        # Fallback to scanning snapshots folder
        if not local_path and snapshots_dir.is_dir():
            candidates = sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            for cand in candidates:
                if cand.is_dir():
                    files_checked = verify_snapshot_files(cand, repo_id)
                    if files_checked:
                        local_path = cand
                        resolved_revision = cand.name
                        break
                        
    # 2. If cached locally, return success
    if local_path:
        elapsed = time.time() - start_time
        res = ModelProvisionResult(
            status="cached",
            repo_id=repo_id,
            revision=resolved_revision,
            local_path=str(local_path.absolute()),
            gated=is_gated,
            required=is_required,
            elapsed_seconds=elapsed,
            files_checked=files_checked,
            attempts_made=attempts_made
        )
        msg = f"Model {repo_id} retrieved from cache (status={res.status}, revision={res.revision})"
        logger.info(msg)
        log_download_event(msg, repo_id)
        return res
        
    # 3. If offline and missing, fail/degrade cleanly
    if is_offline:
        elapsed = time.time() - start_time
        status = "offline_missing"
        if is_required:
            err_msg = redact_sensitive_info(f"Offline mode: required model '{repo_id}' is missing from local cache. To download, connect to the internet and run: python scripts/bootstrap_models.py", repo_id)
            logger.error(err_msg)
        else:
            err_msg = redact_sensitive_info(f"Offline mode: optional model '{repo_id}' is missing from local cache. Skipping optional step.", repo_id)
            logger.warning(err_msg)
            
        log_download_event(err_msg, repo_id)
        return ModelProvisionResult(
            status=status,
            repo_id=repo_id,
            revision=resolved_revision,
            local_path=None,
            gated=is_gated,
            required=is_required,
            elapsed_seconds=elapsed,
            error=err_msg,
            attempts_made=attempts_made
        )
        
    # 4. Online missing - Download with lock
    lock_file = models_root / f"{repo_cache_name}.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure HuggingFace environment cache paths
    os.environ["HF_HOME"] = str(models_root)
    os.environ["HF_HUB_CACHE"] = str(models_root / "hub")
    
    token = resolve_hf_token(repo_id)
    if is_gated and not token:
        elapsed = time.time() - start_time
        err_msg = redact_sensitive_info(f"Authentication token missing for gated model '{repo_id}'. Please run 'python scripts/login_hf.py' or 'python -m cli.auth_models --enable-gated'.", repo_id)
        logger.error(err_msg)
        log_download_event(err_msg, repo_id)
        return ModelProvisionResult(
            status="gated_unauthorized",
            repo_id=repo_id,
            revision=resolved_revision,
            local_path=None,
            gated=is_gated,
            required=is_required,
            elapsed_seconds=elapsed,
            error=err_msg,
            attempts_made=attempts_made
        )
        
    # Acquire file lock to prevent concurrent downloads
    logger.info(f"Acquiring lock for model {repo_id} download...")
    lock = FileLock(str(lock_file), timeout=300) # 5 minute timeout
    
    try:
        with lock:
            # Recheck cache inside lock (idempotency check)
            if repo_id == "snakers4/silero-vad":
                custom_dir = models_root / "hub" / "snakers4_silero-vad_master"
                if custom_dir.is_dir():
                    files_checked = verify_snapshot_files(custom_dir, repo_id)
                    if files_checked:
                        elapsed = time.time() - start_time
                        res = ModelProvisionResult(
                            status="cached",
                            repo_id=repo_id,
                            revision="master",
                            local_path=str(custom_dir.absolute()),
                            gated=is_gated,
                            required=is_required,
                            elapsed_seconds=elapsed,
                            files_checked=files_checked,
                            attempts_made=attempts_made
                        )
                        msg = f"Model {repo_id} retrieved from cache after locking (status=cached, revision=master)"
                        logger.info(msg)
                        log_download_event(msg, repo_id)
                        return res
            elif resolved_revision:
                candidate_snapshot = snapshots_dir / resolved_revision
                files_checked = verify_snapshot_files(candidate_snapshot, repo_id)
                if files_checked:
                    elapsed = time.time() - start_time
                    res = ModelProvisionResult(
                        status="cached",
                        repo_id=repo_id,
                        revision=resolved_revision,
                        local_path=str(candidate_snapshot.absolute()),
                        gated=is_gated,
                        required=is_required,
                        elapsed_seconds=elapsed,
                        files_checked=files_checked,
                        attempts_made=attempts_made
                    )
                    msg = f"Model {repo_id} retrieved from cache after locking (status=cached, revision={resolved_revision})"
                    logger.info(msg)
                    log_download_event(msg, repo_id)
                    return res
            
            # Special check/download for Silero VAD from GitHub
            if repo_id == "snakers4/silero-vad":
                import urllib.request
                import zipfile
                import io
                import shutil
                import ssl
                
                attempts = 4
                target_dir = models_root / "hub" / "snakers4_silero-vad_master"
                
                for attempt in range(1, attempts + 1):
                    attempts_made = attempt
                    try:
                        logger.info(f"Downloading Silero VAD from GitHub (attempt {attempt}/{attempts})...")
                        rev_part = resolved_revision if resolved_revision and resolved_revision != "master" else "master"
                        url = f"https://github.com/snakers4/silero-vad/archive/{rev_part}.zip"
                        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                        
                        ctx = ssl._create_unverified_context()
                        with urllib.request.urlopen(req, context=ctx) as response:
                            zip_data = response.read()
                        
                        with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                            zip_ref.extractall(str(models_root / "hub"))
                        
                        extracted_dir = models_root / "hub" / f"silero-vad-{rev_part}"
                        if not extracted_dir.exists():
                            clean_rev = rev_part.lstrip("v")
                            alt_dir = models_root / "hub" / f"silero-vad-{clean_rev}"
                            if alt_dir.exists():
                                extracted_dir = alt_dir
                            else:
                                cands = list(models_root.glob("hub/silero-vad-*"))
                                if cands:
                                    extracted_dir = cands[0]
                                
                        if target_dir.exists():
                            shutil.rmtree(target_dir)
                        extracted_dir.rename(target_dir)
                        break
                    except Exception as e:
                        err_msg = str(e)
                        if attempt < attempts:
                            logger.warning(f"Transient download error for Silero VAD: {err_msg}. Retrying...")
                            time.sleep(3 * attempt)
                            continue
                        raise
                        
                files_downloaded = verify_snapshot_files(target_dir, repo_id)
                if not files_downloaded:
                    raise OSError("cache layout incomplete: Downloaded Silero VAD from GitHub but weights were missing.")
                    
                elapsed = time.time() - start_time
                res = ModelProvisionResult(
                    status="downloaded",
                    repo_id=repo_id,
                    revision=resolved_revision or "master",
                    local_path=str(target_dir.absolute()),
                    gated=is_gated,
                    required=is_required,
                    elapsed_seconds=elapsed,
                    files_checked=files_downloaded,
                    attempts_made=attempts_made
                )
                msg = f"Model {repo_id} downloaded from GitHub successfully (revision={res.revision}, files={len(files_downloaded)})"
                logger.info(msg)
                log_download_event(msg, repo_id)
                return res
            
            # Retry loop for transient failures
            attempts = 4
            resolved_dir = None
            for attempt in range(1, attempts + 1):
                attempts_made = attempt
                try:
                    _emit_first_use_model_status(
                        f"First-use fetch: downloading model '{repo_id}' "
                        f"(attempt {attempt}/{attempts}); this can take a few minutes."
                    )
                    logger.info(f"Downloading model '{repo_id}' snapshot (attempt {attempt}/{attempts})...")
                    from huggingface_hub import snapshot_download
                    
                    resolved_dir = snapshot_download(
                        repo_id=repo_id,
                        cache_dir=str(models_root / "hub"),
                        revision=resolved_revision,
                        token=token,
                        local_files_only=False
                    )
                    break
                except Exception as e:
                    err_msg = str(e)
                    is_transient = any(
                        t in err_msg.lower()
                        for t in (
                            "connection", "timeout", "timed out", "502", "503", "504",
                            "read timed out", "dns", "unreachable", "reset", "broken",
                            "aborted"
                        )
                    )
                    if attempt < attempts and is_transient:
                        logger.warning(f"Transient download error for '{repo_id}': {err_msg}. Retrying...")
                        time.sleep(min(3 * attempt, 15))
                        continue
                    raise
            
            # Normalize main ref
            downloaded_path = Path(resolved_dir)
            files_downloaded = verify_snapshot_files(downloaded_path, repo_id)
            
            if not files_downloaded:
                raise OSError(f"cache layout incomplete: Downloaded model directory layout was invalid for '{repo_id}' under '{resolved_dir}'")
                
            # Write refs/main
            if not resolved_revision:
                resolved_revision = downloaded_path.name
            refs_dir = repo_cache_dir / "refs"
            refs_dir.mkdir(parents=True, exist_ok=True)
            (refs_dir / "main").write_text(resolved_revision, encoding="utf-8")
            
            elapsed = time.time() - start_time
            res = ModelProvisionResult(
                status="downloaded",
                repo_id=repo_id,
                revision=resolved_revision,
                local_path=str(downloaded_path.absolute()),
                gated=is_gated,
                required=is_required,
                elapsed_seconds=elapsed,
                files_checked=files_downloaded,
                attempts_made=attempts_made
            )
            msg = f"Model {repo_id} downloaded successfully (revision={res.revision}, files={len(files_downloaded)})"
            _emit_first_use_model_status(f"First-use fetch complete: {repo_id} is cached locally.")
            logger.info(msg)
            log_download_event(msg, repo_id)
            return res
            
    except Exception as e:
        elapsed = time.time() - start_time
        err_msg = str(e)
        status = "failed"
        
        # Check for authentication or gated access issues
        err_lower = err_msg.lower()
        if "401" in err_lower or "unauthorized" in err_lower:
            status = "gated_unauthorized"
            err_msg = f"Access denied to gated model '{repo_id}': Invalid or unauthorized token."
        elif "403" in err_lower or "gated" in err_lower:
            status = "gated_unauthorized"
            err_msg = f"Access denied to gated model '{repo_id}': User agreement/terms not accepted or unauthorized."
        elif "connection" in err_lower or "dns" in err_lower or "offline" in err_lower or "max retries" in err_lower or "unreachable" in err_lower:
            err_msg = f"Network connection error while trying to download model '{repo_id}': {err_msg}"
            
        logger.error(redact_sensitive_info(f"Failed to provision model '{repo_id}': {err_msg}", repo_id))
        log_download_event(f"Failed to provision model '{repo_id}': {err_msg}", repo_id)
        return ModelProvisionResult(
            status=status,
            repo_id=repo_id,
            revision=resolved_revision,
            local_path=None,
            gated=is_gated,
            required=is_required,
            elapsed_seconds=elapsed,
            error=err_msg,
            attempts_made=attempts_made
        )
