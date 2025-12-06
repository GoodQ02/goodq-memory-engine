from __future__ import annotations
import os
import json
from typing import Any, Dict

import yaml


def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _normalize_win_path(value: str) -> str:
    """
    Convert Windows drive paths (e.g., L:/foo) to WSL mount points (/mnt/l/foo) when needed.
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


def _normalize_paths(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _normalize_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_paths(v) for v in obj]
    if isinstance(obj, str):
        return _normalize_win_path(obj)
    return obj


def load_configs(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    # Optional: load a local .env.local file for secrets (no-ops if dotenv not installed)
    try:
        from dotenv import load_dotenv  # type: ignore
        # repo root is two levels up from this file's directory
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env_path = os.path.join(repo_root, ".env.local")
        if os.path.isfile(env_path):
            load_dotenv(env_path)
    except Exception as e:
        print(f'[ERROR] Exception in config_loader.py line 23: {str(e)}')
        pass

    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs")
    
    # Load unified config.yaml (primary configuration file)
    unified_config_path = os.path.join(base_dir, "config.yaml")
    if os.path.isfile(unified_config_path):
        cfg = _normalize_paths(_read_yaml(unified_config_path))
    else:
        # Fallback to legacy config files for backwards compatibility
        config_open = _read_yaml(os.path.join(base_dir, "config_open.yaml"))
        paths = _normalize_paths(_read_yaml(os.path.join(base_dir, "paths.yaml")))
        entities = _read_yaml(os.path.join(base_dir, "entities.yaml"))
        model_registry = _read_yaml(os.path.join(base_dir, "model_registry.yaml"))
        cfg = {"config": config_open, "paths": paths, "entities": entities, "models": model_registry}
    
    if overrides:
        # shallow merge only; keep deterministic and explicit
        for k, v in overrides.items():
            cfg[k] = v
    return cfg
