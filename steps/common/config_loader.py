from __future__ import annotations
import os
import json
from typing import Any, Dict

import yaml


def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_configs(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    # Optional: load a local .env.local file for secrets (no-ops if dotenv not installed)
    try:
        from dotenv import load_dotenv  # type: ignore
        # repo root is two levels up from this file's directory
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env_path = os.path.join(repo_root, ".env.local")
        if os.path.isfile(env_path):
            load_dotenv(env_path)
    except Exception:
        pass

    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs")
    config_open = _read_yaml(os.path.join(base_dir, "config_open.yaml"))
    paths = _read_yaml(os.path.join(base_dir, "paths.yaml"))
    entities = _read_yaml(os.path.join(base_dir, "entities.yaml"))
    model_registry = _read_yaml(os.path.join(base_dir, "model_registry.yaml"))

    cfg = {"config": config_open, "paths": paths, "entities": entities, "models": model_registry}
    if overrides:
        # shallow merge only; keep deterministic and explicit
        for k, v in overrides.items():
            cfg[k] = v
    return cfg
