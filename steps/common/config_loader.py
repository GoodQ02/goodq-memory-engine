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

    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs")
    
    # Load unified config.yaml (primary configuration file)
    unified_config_path = os.path.join(base_dir, "config.yaml")
    if not os.path.isfile(unified_config_path):
        raise FileNotFoundError(f"Canonical config not found: {unified_config_path}")
    
    raw_cfg = _normalize_paths(_read_yaml(unified_config_path))
    
    # Apply overrides before validation
    if overrides:
        # Deep merge for nested overrides
        def deep_merge(base, override):
            for k, v in override.items():
                if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                    deep_merge(base[k], v)
                else:
                    base[k] = v
        deep_merge(raw_cfg, overrides)
    
    # Validate against Pydantic schema
    try:
        from config_schema import GoodQConfig
        validated = GoodQConfig.model_validate(raw_cfg)
        return validated.model_dump()
    except Exception as e:
        print(f"[ERROR] Config validation failed: {str(e)}")
        print("[WARN] Falling back to unvalidated config (not recommended)")
        return raw_cfg
