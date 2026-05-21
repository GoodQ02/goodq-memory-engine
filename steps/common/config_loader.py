from __future__ import annotations
import logging
import os
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict

import yaml
from steps.common.profile_config import log_runtime_profile_state


def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _normalize_win_path(value: str) -> str:
    """
    Convert Windows drive paths (e.g., <drive>:/foo) to WSL mount points (/mnt/<drive>/foo) when needed.
    Leaves non-drive strings untouched and preserves Windows paths on Windows hosts.
    """
    if not isinstance(value, str):
        return value
    if os.name == "nt":
        return value
    if len(value) >= 3 and value[1:3] == ":/":
        drive = value[0].lower()
        rest = value[3:]
        return f"/mnt/{drive}/{rest}"
    return value


_ENV_REF_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def _resolve_env_ref(value: str) -> str:
    if not isinstance(value, str):
        return value
    def replace_match(match: re.Match[str]) -> str:
        env_name = match.group(1)
        default_value = match.group(2)
        env_value = os.environ.get(env_name)
        if default_value is not None:
            return env_value if env_value not in (None, "") else default_value
        return env_value if env_value is not None else match.group(0)

    return _ENV_REF_PATTERN.sub(replace_match, value)


def _apply_env_aliases() -> None:
    """
    Normalize cross-surface token aliases without requiring duplicate .env entries.
    Canonical contract prefers HUGGINGFACE_TOKEN and mirrors it to legacy aliases when unset.
    """
    hf_primary = (os.environ.get("HUGGINGFACE_TOKEN") or "").strip()
    hf_legacy = (os.environ.get("HF_TOKEN") or "").strip()
    pyannote = (os.environ.get("PYANNOTE_TOKEN") or "").strip()

    if hf_primary and not hf_legacy:
        os.environ["HF_TOKEN"] = hf_primary
    elif hf_legacy and not hf_primary:
        os.environ["HUGGINGFACE_TOKEN"] = hf_legacy
        hf_primary = hf_legacy

    if hf_primary and not pyannote:
        os.environ["PYANNOTE_TOKEN"] = hf_primary


def _normalize_paths(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalize_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_paths(v) for v in obj]
    if isinstance(obj, str):
        return _normalize_win_path(_resolve_env_ref(obj))
    return obj


def _ensure_runtime_path_defaults(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(cfg, dict):
        return cfg

    paths_cfg = cfg.get("paths")
    if not isinstance(paths_cfg, dict):
        paths_cfg = {}
        cfg["paths"] = paths_cfg

    host_cfg = cfg.get("host")
    if not isinstance(host_cfg, dict):
        host_cfg = {}
        cfg["host"] = host_cfg

    config_cfg = cfg.get("config")
    if not isinstance(config_cfg, dict):
        config_cfg = {}
        cfg["config"] = config_cfg

    tools_cfg = config_cfg.get("tools")
    if not isinstance(tools_cfg, dict):
        tools_cfg = {}
        config_cfg["tools"] = tools_cfg

    wsl_user = host_cfg.get("wsl_user")
    if isinstance(wsl_user, str) and wsl_user.strip() and wsl_user.strip().lower() not in {"auto", "unset"}:
        resolved_wsl_user = wsl_user.strip()
    else:
        resolved_wsl_user = ""
        for candidate in (
            os.environ.get("GOODQ_WSL_USER"),
            os.environ.get("USER"),
            os.environ.get("USERNAME"),
            os.environ.get("LOGNAME"),
        ):
            if candidate:
                resolved_wsl_user = str(candidate).strip()
                if resolved_wsl_user:
                    break
        if not resolved_wsl_user:
            resolved_wsl_user = "user"
        host_cfg["wsl_user"] = resolved_wsl_user

    wsl_workspace = host_cfg.get("wsl_workspace")
    if not (isinstance(wsl_workspace, str) and wsl_workspace.strip() and wsl_workspace.strip().lower() not in {"auto", "unset"}):
        host_cfg["wsl_workspace"] = f"/home/{resolved_wsl_user}/goodq_audio"

    data_root = paths_cfg.get("data_root")
    host_data_root = host_cfg.get("data_root")
    if not data_root and isinstance(host_data_root, str) and host_data_root.strip():
        normalized_host_root = host_data_root.rstrip("/\\")
        data_root = f"{normalized_host_root}/GoodQ_Data"
        paths_cfg["data_root"] = data_root

    db_dir = paths_cfg.get("db_dir")
    if isinstance(db_dir, str) and db_dir.strip():
        base_db_dir = db_dir.rstrip("/\\")
        paths_cfg.setdefault("processing", f"{base_db_dir}/processing")
        paths_cfg.setdefault("log_dir", f"{base_db_dir}/logs")
        paths_cfg.setdefault("output_directory", f"{base_db_dir}/output")
        paths_cfg.setdefault("db_path", f"{base_db_dir}/memory.db")
        paths_cfg.setdefault("knowledge_graph_db", f"{base_db_dir}/knowledge_graph.db")
        paths_cfg.setdefault("faiss_dir", f"{base_db_dir}/faiss")

    faiss_dir = paths_cfg.get("faiss_dir")
    if isinstance(faiss_dir, str) and faiss_dir.strip():
        base_faiss_dir = faiss_dir.rstrip("/\\")

        def set_path_default(key: str, relative_path: str) -> None:
            existing = paths_cfg.get(key)
            if not (isinstance(existing, str) and existing.strip()):
                paths_cfg[key] = f"{base_faiss_dir}/{relative_path}"

        set_path_default("faiss_index_path", "text/faiss_text.index")
        set_path_default("faiss_clip_path", "clip/faiss_clip.index")
        set_path_default("faiss_dino_path", "dino/faiss_dino.index")
        set_path_default("clip_id_map_db", "clip/clip_id_map.sqlite")
        set_path_default("dino_id_map_db", "dino/dino_id_map.sqlite")
        set_path_default("clap_id_map_db", "audio/clap_id_map.sqlite")

    log_dir = paths_cfg.get("log_dir")
    if isinstance(log_dir, str) and log_dir.strip():
        base_log_dir = log_dir.rstrip("/\\")
        paths_cfg.setdefault("watchdog_state_file", f"{base_log_dir}/watchdog_state.json")
        paths_cfg.setdefault("watchdog_lock_file", f"{base_log_dir}/watchdog.lock")
        paths_cfg.setdefault("csv_path", f"{base_log_dir}/system_metrics.csv")

    if isinstance(data_root, str) and data_root.strip():
        base_data_root = data_root.rstrip("/\\")
        paths_cfg.setdefault("import_inbox", f"{base_data_root}/import_inbox")
        paths_cfg.setdefault("processed", f"{base_data_root}/processed")
        paths_cfg.setdefault("failed", f"{base_data_root}/failed")

    if isinstance(host_data_root, str) and host_data_root.strip():
        base_host_root = host_data_root.rstrip("/\\")
        paths_cfg.setdefault("models_cache", f"{base_host_root}/models")
        paths_cfg.setdefault("qdrant_storage", f"{base_host_root}/qdrant_storage")

        ffmpeg_cfg = tools_cfg.get("ffmpeg_exe")
        if not isinstance(ffmpeg_cfg, str) or ffmpeg_cfg.strip() in {"", "ffmpeg"}:
            ffmpeg_candidate = Path(base_host_root) / "_TOOLS" / "ffmpeg" / "bin" / "ffmpeg.exe"
            if ffmpeg_candidate.exists():
                tools_cfg["ffmpeg_exe"] = str(ffmpeg_candidate).replace("\\", "/")

        tesseract_cfg = tools_cfg.get("tesseract_exe")
        if not isinstance(tesseract_cfg, str) or tesseract_cfg.strip() in {"", "tesseract"}:
            tesseract_candidates = []
            tesseract_on_path = shutil.which("tesseract")
            if tesseract_on_path:
                tesseract_candidates.append(Path(tesseract_on_path))
            for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
                base_program_files = os.environ.get(env_name)
                if base_program_files:
                    tesseract_candidates.append(Path(base_program_files) / "Tesseract-OCR" / "tesseract.exe")
            for candidate_exe in tesseract_candidates:
                if candidate_exe.exists():
                    tools_cfg["tesseract_exe"] = str(candidate_exe).replace("\\", "/")
                    break

        poppler_cfg = tools_cfg.get("poppler_bin")
        if not isinstance(poppler_cfg, str) or not poppler_cfg.strip():
            poppler_candidates = []
            pdftotext_on_path = shutil.which("pdftotext")
            if pdftotext_on_path:
                poppler_candidates.append(Path(pdftotext_on_path).parent)
            for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
                base_program_files = os.environ.get(env_name)
                if base_program_files:
                    poppler_candidates.append(Path(base_program_files) / "Git" / "mingw64" / "bin")
            for candidate_dir in poppler_candidates:
                candidate_exe = candidate_dir / "pdftotext.exe"
                if candidate_exe.exists():
                    tools_cfg["poppler_bin"] = str(candidate_dir).replace("\\", "/")
                    break

    return cfg


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


CANONICAL_RUNTIME_PATH_KEYS = (
    "data_root",
    "import_inbox",
    "processing",
    "log_dir",
    "db_path",
    "knowledge_graph_db",
    "qdrant_storage",
)


def get_runtime_paths(
    cfg: Dict[str, Any],
    *extra_keys: str,
    require_canonical: bool = True,
) -> Dict[str, str]:
    if not isinstance(cfg, dict):
        raise KeyError("Config payload is not a dictionary")

    cfg = _ensure_runtime_path_defaults(cfg)
    paths_cfg = cfg.get("paths")
    if not isinstance(paths_cfg, dict):
        raise KeyError("Config missing paths section")

    resolved: Dict[str, str] = {}
    missing = []
    required_keys = (*CANONICAL_RUNTIME_PATH_KEYS, *extra_keys) if require_canonical else extra_keys
    for key in required_keys:
        value = paths_cfg.get(key)
        if isinstance(value, str) and value.strip():
            resolved[key] = value
        else:
            missing.append(key)

    if missing:
        raise KeyError(f"Config missing required runtime path(s): {', '.join(sorted(set(missing)))}")

    return resolved


def load_configs(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Load and validate the canonical GoodQ4All configuration.
    Uses Pydantic validation to ensure schema compliance.
    Returns a dictionary for backwards compatibility with existing code.
    """
    # Optional: load a local .env.local file for secrets (no-ops if dotenv not installed)
    try:
        from dotenv import load_dotenv  # type: ignore
        # repo root is two levels up from this file's directory
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env_path = os.path.join(repo_root, ".env.local")
        if os.path.isfile(env_path):
            load_dotenv(env_path)
    except Exception as e:
        print(f'[WARN] Could not load .env.local: {str(e)}')
        pass

    _apply_env_aliases()

    log_runtime_profile_state(
        logger=logging.getLogger(__name__),
        context="steps.common.config_loader",
        gpu_enabled=None,
        wsl_enabled=None,
    )

    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs")
    
    # Load unified config.yaml (primary configuration file)
    unified_config_path = os.path.join(base_dir, "config.yaml")
    if not os.path.isfile(unified_config_path):
        raise FileNotFoundError(f"Canonical config not found: {unified_config_path}")
    
    raw_cfg = _normalize_paths(_read_yaml(unified_config_path))

    local_config_path = os.path.join(base_dir, "config.local.yaml")
    if os.path.isfile(local_config_path):
        local_cfg = _normalize_paths(_read_yaml(local_config_path))
        if isinstance(local_cfg, dict):
            _deep_merge(raw_cfg, local_cfg)

    # Apply overrides before validation
    if overrides:
        _deep_merge(raw_cfg, overrides)

    raw_cfg = _ensure_runtime_path_defaults(raw_cfg)
    
    # Validate against Pydantic schema (optional - graceful degradation)
    try:
        from config_schema import GoodQConfig
        validated = GoodQConfig.model_validate(raw_cfg)
        return validated.model_dump()
    except ImportError:
        # Schema validation not available - use raw config (expected for now)
        pass
    except Exception as e:
        print(f"[WARN] Config validation failed: {str(e)}")
        print("[WARN] Falling back to unvalidated config (not recommended)")
    
    return raw_cfg
