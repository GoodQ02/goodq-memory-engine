"""Establish a witness process environment before importing runtime modules.

Only the standard library is imported here. Models and VRAM coordination remain
shared; this helper isolates witness data and control files, not those resources.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Mapping, Sequence


def _absolute_path(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip() or not Path(value).is_absolute():
        raise ValueError(f"Witness {label} must be an absolute path")
    return Path(value).resolve()


def _contained_path(value: object, root: Path, label: str) -> Path:
    path = _absolute_path(value, label)
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"Witness {label} must stay inside its artifact root")
    return path


def build_witness_environment(
    snapshot_path: str | os.PathLike[str], parent_env: Mapping[str, str]
) -> dict[str, str]:
    """Validate raw witness bindings and return a copied child environment.

    This does not create paths, mutate the parent environment, select a backend,
    or replace the full runner's configuration validation.
    """
    snapshot = Path(snapshot_path).resolve()
    try:
        config = json.loads(snapshot.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Witness environment requires a readable JSON snapshot") from exc
    if not isinstance(config, dict):
        raise ValueError("Witness snapshot must be a JSON object")
    witness = config.get("witness")
    if (
        config.get("ingestion_isolation") is not True
        or not isinstance(witness, dict)
        or witness.get("ingestion_isolation") is not True
        or witness.get("promotion_enabled") is not False
    ):
        raise ValueError("Witness environment requires isolated, non-promoting ingestion")
    root = _absolute_path(witness.get("artifact_root"), "artifact_root")
    if root == Path(root.anchor) or snapshot == root or not snapshot.is_relative_to(root):
        raise ValueError("Witness snapshot must be inside a bounded artifact root")
    epoch = config.get("epoch_id")
    if not isinstance(epoch, str) or not re.fullmatch(r"epoch_witness_[A-Za-z0-9_-]+", epoch):
        raise ValueError("Witness environment requires an explicit witness epoch")
    paths = config.get("paths")
    identity = config.get("identity_search")
    host = config.get("host")
    if not isinstance(paths, dict) or not isinstance(identity, dict) or not isinstance(host, dict):
        raise ValueError("Witness environment requires paths, identity_search, and host bindings")
    contained = {
        key: _contained_path(paths.get(key), root, f"paths.{key}")
        for key in ("data_root", "log_dir", "processing")
    }
    if _contained_path(host.get("data_root"), root, "host.data_root") != contained["data_root"]:
        raise ValueError("Witness host and runtime data roots must agree")
    roster = _contained_path(identity.get("roster_path"), root, "identity_search.roster_path")
    models = _absolute_path(paths.get("models_cache"), "paths.models_cache")
    if models.is_relative_to(root) or root.is_relative_to(models):
        raise ValueError("Witness model cache and artifact root must not overlap")
    # Resolve derived locations too, so an existing junction cannot redirect them.
    temp = _contained_path(str(root / "temp"), root, "temp")
    cache = _contained_path(str(root / "cache"), root, "cache")
    authority = _contained_path(str(root / "authority"), root, "authority")
    audit = _contained_path(str(root / "audit" / "events.jsonl"), root, "audit")
    wsl_output = _contained_path(
        str(contained["processing"] / "wsl_audio"), root, "wsl_audio_output"
    )
    env = dict(parent_env)
    env.update({
        "GOODQ_WITNESS_CONFIG": str(snapshot),
        "GOODQ_DATA_ROOT": str(contained["data_root"]),
        "GOODQ_EPOCH_ID": epoch,
        "GOODQ_LOGS_ROOT": str(contained["log_dir"]),
        "GOODQ_TEMP_ROOT": str(contained["processing"]),
        "GOODQ_CACHE_ROOT": str(cache),
        "GOODQ_MODELS_ROOT": str(models),
        "GOODQ_MODELS_DIR": str(models),
        "GOODQ_IDENTITY_PATH": str(roster.parent),
        "GOODQ_MINI_AGENT_HOME": str(authority),
        "GOODQ_TOOL_AUDIT_LOG": str(audit),
        "GOODQ_WSL_AUDIO_OUTPUT_ROOT": str(wsl_output),
        "TEMP": str(temp),
        "TMP": str(temp),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return env


def bootstrap_witness_environment(argv: Sequence[str] | None = None) -> bool:
    """Apply an explicit CLI witness before any environment-sensitive imports."""
    args = list(sys.argv[1:] if argv is None else argv)
    snapshots: list[str] = []
    for index, argument in enumerate(args):
        if argument == "--config":
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                raise ValueError("--config requires a witness snapshot path")
            snapshots.append(args[index + 1])
        elif argument.startswith("--config="):
            snapshots.append(argument.partition("=")[2])
    if not snapshots:
        if "GOODQ_WITNESS_CONFIG" in os.environ:
            raise ValueError("Inherited witness environment requires an explicit --config snapshot")
        return False
    if len(snapshots) != 1 or not snapshots[0]:
        raise ValueError("Exactly one witness --config is required")
    env = build_witness_environment(snapshots[0], os.environ)
    Path(env["TEMP"]).mkdir(parents=True, exist_ok=True)
    os.environ.update(env)
    return True
