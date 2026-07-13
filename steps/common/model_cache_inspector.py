"""Side-effect-free inspection of pinned Hugging Face model snapshots."""

from __future__ import annotations

import re
import stat
from pathlib import Path
from typing import Iterable

import yaml


_DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "configs" / "model_registry.yaml"
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_WINDOWS_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)


def _safe_repo_id(repo_id: str) -> bool:
    parts = repo_id.split("/")
    return len(parts) >= 2 and all(_SAFE_COMPONENT.fullmatch(part) for part in parts)


def _safe_revision(revision: str) -> bool:
    return bool(_SAFE_COMPONENT.fullmatch(revision)) and revision not in {".", ".."}


def _safe_required_paths(required_files: Iterable[str]) -> tuple[Path, ...] | None:
    paths: list[Path] = []
    for raw_name in required_files:
        if not isinstance(raw_name, str) or not raw_name.strip():
            return None
        path = Path(raw_name)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            return None
        paths.append(path)
    return tuple(paths)


def _snapshot_is_complete(snapshot: Path, required_files: tuple[Path, ...]) -> bool:
    if not snapshot.is_dir():
        return False
    if not ((snapshot / "config.json").is_file() or (snapshot / "config.yaml").is_file()):
        return False
    if not all((snapshot / relative_path).is_file() for relative_path in required_files):
        return False
    weight_patterns = ("*.safetensors", "pytorch_model*.bin")
    return any(
        candidate.is_file()
        for pattern in weight_patterns
        for candidate in snapshot.glob(pattern)
    )


def _has_redirected_directory(root: Path, snapshot: Path) -> bool:
    current = root
    for component in snapshot.relative_to(root).parts:
        current = current / component
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            return True
        file_attributes = getattr(metadata, "st_file_attributes", 0)
        if _WINDOWS_REPARSE_POINT and file_attributes & _WINDOWS_REPARSE_POINT:
            return True
    return False


def resolve_pinned_model_snapshot(
    models_root: Path | str,
    registry_key: str,
    *,
    registry_path: Path | str | None = None,
    required_files: Iterable[str] = (),
) -> Path | None:
    """Return an existing exact registry-pinned snapshot without mutating state."""

    if not isinstance(registry_key, str) or not registry_key.strip():
        return None
    required_paths = _safe_required_paths(required_files)
    if required_paths is None:
        return None

    try:
        root = Path(models_root).expanduser().resolve(strict=False)
        source = (
            Path(registry_path).expanduser().resolve(strict=False)
            if registry_path is not None
            else _DEFAULT_REGISTRY_PATH
        )
        if not source.is_file():
            return None
        parsed = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except (OSError, RuntimeError, TypeError, ValueError, yaml.YAMLError):
        return None

    if not isinstance(parsed, dict):
        return None
    models = parsed.get("huggingface_models")
    if not isinstance(models, dict):
        return None
    model = models.get(registry_key)
    if not isinstance(model, dict):
        return None

    repo_id = model.get("repo_id")
    revision = model.get("revision")
    if not isinstance(repo_id, str) or not isinstance(revision, str):
        return None
    repo_id = repo_id.strip()
    revision = revision.strip()
    if not _safe_repo_id(repo_id) or not _safe_revision(revision):
        return None

    try:
        snapshot = (
            root
            / "hub"
            / f"models--{repo_id.replace('/', '--')}"
            / "snapshots"
            / revision
        )
        snapshot.relative_to(root)
        if _has_redirected_directory(root, snapshot):
            return None
        complete = _snapshot_is_complete(snapshot, required_paths)
    except (OSError, RuntimeError, ValueError):
        return None
    return snapshot if complete else None
