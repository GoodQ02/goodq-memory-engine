"""Pure configuration authority for the governed clean-memory plan path.

This module intentionally has no command surface yet.  It projects one already
loaded configuration mapping into deterministic, secret-free logical authority
for later passive filesystem and Qdrant observers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any
import unicodedata
from urllib.parse import urlsplit

from steps.common.clean_memory import PROTECTED_BOUNDARY_ROLES as _PROTECTED_BOUNDARY_ROLES


CONFIGURATION_SCHEMA = "goodq.clean-memory-configuration.v1"

__all__ = (
    "CONFIGURATION_SCHEMA",
    "ResolvedPlanConfiguration",
    "resolve_plan_configuration",
)

_EPOCH_ID_RE = re.compile(r"^epoch_[A-Za-z0-9][A-Za-z0-9._-]{0,121}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^([A-Za-z]):/(.+)$")
_UNRESOLVED_ENV_RE = re.compile(
    r"(?:\$\{[A-Za-z_][A-Za-z0-9_]*(?::-[^}]*)?\}|%[A-Za-z_][A-Za-z0-9_]*%)"
)
_QDRANT_ROLES = ("text", "clip", "dino", "audio")
_FAISS_DECLARATION_KEYS = (
    "clap_id_map_db",
    "clip_id_map_db",
    "dino_id_map_db",
    "faiss_audio_path",
    "faiss_clip_path",
    "faiss_dino_path",
    "faiss_index_path",
)
_RECOGNIZED_FAISS_PATH_KEYS = frozenset(("faiss_dir", *_FAISS_DECLARATION_KEYS))
_CONFIGURED_PROTECTED_ROLES = (
    "archive_root",
    "control_root",
    "data_root",
    "failed_media",
    "import_media",
    "model_cache",
    "processed_media",
    "processing_media",
    "qdrant_storage",
    "watchdog_state",
)
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True, init=False)
class ResolvedPlanConfiguration:
    """Immutable canonical configuration projection with a detached view."""

    _projection_json: str
    configuration_scope_sha256: str

    @classmethod
    def _from_projection(cls, projection: dict[str, Any]) -> "ResolvedPlanConfiguration":
        projection_json = _canonical_json_text(projection)
        instance = object.__new__(cls)
        object.__setattr__(instance, "_projection_json", projection_json)
        object.__setattr__(
            instance,
            "configuration_scope_sha256",
            hashlib.sha256(projection_json.encode("utf-8")).hexdigest(),
        )
        return instance

    @property
    def projection(self) -> dict[str, Any]:
        """Return a detached configuration projection."""

        value = json.loads(self._projection_json)
        if not isinstance(value, dict):
            raise ValueError("Clean-memory configuration projection is not an object")
        return value


def _canonical_json_text(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Clean-memory configuration projection is not canonical JSON") from exc


def _section(config: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = config.get(name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _required_value(section: Mapping[str, Any], key: str, *, label: str) -> Any:
    if key not in section:
        raise ValueError(f"{label} is required")
    return section[key]


def _required_text(section: Mapping[str, Any], key: str, *, label: str) -> str:
    value = _required_value(section, key, label=label)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be an exact non-empty string")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{label} must use canonical Unicode")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} contains a control character")
    return value


def _validate_path_component(component: str, *, windows: bool, label: str) -> None:
    if component in {"", ".", ".."}:
        raise ValueError(f"{label} is not lexically canonical")
    if windows:
        if component.endswith((".", " ")) or any(
            character in '<>:"|?*' for character in component
        ):
            raise ValueError(f"{label} is ambiguous on Windows")
        if component.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise ValueError(f"{label} uses a reserved Windows name")


def _canonical_absolute_path(value: Any, *, label: str) -> tuple[str, str]:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be an exact absolute path")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{label} must use canonical Unicode")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} contains a control character")
    if _UNRESOLVED_ENV_RE.search(value):
        raise ValueError(f"{label} contains an unresolved environment reference")

    normalized = value.replace("\\", "/")
    if normalized.startswith("//") or normalized.endswith("/") or "//" in normalized:
        raise ValueError(f"{label} is not a canonical local absolute path")

    windows_match = _WINDOWS_ABSOLUTE_RE.fullmatch(normalized)
    if windows_match:
        drive, remainder = windows_match.groups()
        parts = remainder.split("/")
        for component in parts:
            _validate_path_component(component, windows=True, label=label)
        return f"{drive.upper()}:/{'/'.join(parts)}", "windows"

    if normalized.startswith("/") and normalized != "/":
        parts = normalized[1:].split("/")
        for component in parts:
            _validate_path_component(component, windows=False, label=label)
        return f"/{'/'.join(parts)}", "posix"

    raise ValueError(f"{label} must be a canonical local absolute path")


def _join_path(root: str, *parts: str) -> str:
    return f"{root}/{'/'.join(parts)}"


def _configured_path(
    section: Mapping[str, Any],
    key: str,
    *,
    expected_flavor: str,
) -> str:
    value = _required_value(section, key, label=f"paths.{key}")
    canonical, flavor = _canonical_absolute_path(value, label=f"paths.{key}")
    if flavor != expected_flavor:
        raise ValueError(f"paths.{key} uses a different path flavor")
    return canonical


def _require_exact_path(actual: str, expected: str, *, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} does not match canonical topology")


def _path_comparison_key(path: str, *, flavor: str) -> str:
    return path.casefold() if flavor == "windows" else path


def _paths_overlap(left: str, right: str, *, flavor: str) -> bool:
    left_key = _path_comparison_key(left, flavor=flavor)
    right_key = _path_comparison_key(right, flavor=flavor)
    return (
        left_key == right_key
        or left_key.startswith(f"{right_key}/")
        or right_key.startswith(f"{left_key}/")
    )


def _canonical_qdrant_endpoint(value: Any) -> tuple[str, int]:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("qdrant.host must be an exact endpoint")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("qdrant.host is malformed") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or port is None
        or not 1 <= port <= 65535
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != ""
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("qdrant.host must be canonical loopback HTTP")
    host = "127.0.0.1" if parsed.hostname == "127.0.0.1" else "[::1]"
    canonical = f"http://{host}:{port}"
    if value != canonical:
        raise ValueError("qdrant.host spelling is not canonical")
    return canonical, port


def _resolve_paths(
    host: Mapping[str, Any],
    paths: Mapping[str, Any],
    *,
    epoch_id: str,
) -> tuple[dict[str, str], dict[str, str], list[dict[str, Any]], str]:
    storage_value = _required_value(host, "data_root", label="host.data_root")
    storage_root, flavor = _canonical_absolute_path(storage_value, label="host.data_root")
    data_root = _configured_path(paths, "data_root", expected_flavor=flavor)
    _require_exact_path(
        data_root,
        _join_path(storage_root, "GoodQ_Data"),
        label="host.data_root and paths.data_root",
    )

    configured_epoch_root = _configured_path(paths, "db_dir", expected_flavor=flavor)
    epochs_root = _join_path(data_root, "epochs")
    configured_epoch_parent, separator, configured_epoch = configured_epoch_root.rpartition("/")
    if not separator or configured_epoch_parent != epochs_root:
        raise ValueError("paths.db_dir does not match canonical topology")
    if configured_epoch != epoch_id:
        raise ValueError("requested epoch does not match configured epoch")

    epoch_root = _join_path(data_root, "epochs", epoch_id)
    strict_topology_paths = {
        "db_path": _join_path(epoch_root, "memory.db"),
        "knowledge_graph_db": _join_path(epoch_root, "knowledge_graph.db"),
        "faiss_dir": _join_path(epoch_root, "faiss"),
        "import_inbox": _join_path(data_root, "import_inbox"),
        "processed": _join_path(data_root, "processed"),
        "failed": _join_path(data_root, "failed"),
    }
    configured: dict[str, str] = {"db_dir": configured_epoch_root}
    for key, expected in strict_topology_paths.items():
        actual = _configured_path(paths, key, expected_flavor=flavor)
        _require_exact_path(actual, expected, label=f"paths.{key}")
        configured[key] = actual

    for key in (
        "processing",
        "models_cache",
        "qdrant_storage",
        "watchdog_state_file",
        "watchdog_lock_file",
        "nas_path",
    ):
        configured[key] = _configured_path(paths, key, expected_flavor=flavor)

    for key in paths:
        if not isinstance(key, str):
            raise ValueError("paths keys must be strings")
        is_faiss_path_authority = (
            "faiss" in key.casefold()
            or key.endswith("_index_path")
            or key.endswith("_id_map_db")
        )
        if is_faiss_path_authority and key not in _RECOGNIZED_FAISS_PATH_KEYS:
            raise ValueError(f"paths.{key} is an unrecognized FAISS path authority")

    faiss_root = configured["faiss_dir"]
    declared_faiss_paths: dict[str, str] = {}
    for key in _FAISS_DECLARATION_KEYS:
        if key not in paths or paths[key] is None:
            continue
        actual = _configured_path(paths, key, expected_flavor=flavor)
        if not actual.startswith(f"{faiss_root}/"):
            raise ValueError(f"paths.{key} must remain below paths.faiss_dir")
        for previous_key, previous_path in declared_faiss_paths.items():
            if _paths_overlap(actual, previous_path, flavor=flavor):
                raise ValueError(f"paths.{key} overlaps paths.{previous_key}")
        declared_faiss_paths[key] = actual

    candidate_evidence_root = _join_path(data_root, "control", "clean_memory")
    logical_paths = {
        "storage_root": storage_root,
        "data_root": data_root,
        "memory_database": configured["db_path"],
        "memory_database_wal": f"{configured['db_path']}-wal",
        "memory_database_shm": f"{configured['db_path']}-shm",
        "knowledge_graph_database": configured["knowledge_graph_db"],
        "knowledge_graph_database_wal": f"{configured['knowledge_graph_db']}-wal",
        "knowledge_graph_database_shm": f"{configured['knowledge_graph_db']}-shm",
        "faiss_root": faiss_root,
        "candidate_evidence_root": candidate_evidence_root,
    }
    protected_sources = {
        "archive_root": ((configured["nas_path"], "paths.nas_path"),),
        "control_root": ((_join_path(data_root, "control"), "derived control root"),),
        "data_root": ((data_root, "paths.data_root"),),
        "failed_media": ((configured["failed"], "paths.failed"),),
        "import_media": ((configured["import_inbox"], "paths.import_inbox"),),
        "model_cache": ((configured["models_cache"], "paths.models_cache"),),
        "processed_media": ((configured["processed"], "paths.processed"),),
        "processing_media": ((configured["processing"], "paths.processing"),),
        "qdrant_storage": ((configured["qdrant_storage"], "paths.qdrant_storage"),),
        "watchdog_state": tuple(
            sorted(
                (
                    (configured["watchdog_state_file"], "paths.watchdog_state_file"),
                    (configured["watchdog_lock_file"], "paths.watchdog_lock_file"),
                )
            )
        ),
    }

    cleanup_and_evidence_scope = (
        (configured["db_path"], "memory database"),
        (f"{configured['db_path']}-wal", "memory database WAL"),
        (f"{configured['db_path']}-shm", "memory database SHM"),
        (configured["knowledge_graph_db"], "knowledge graph database"),
        (f"{configured['knowledge_graph_db']}-wal", "knowledge graph database WAL"),
        (f"{configured['knowledge_graph_db']}-shm", "knowledge graph database SHM"),
        (faiss_root, "FAISS root"),
        (candidate_evidence_root, "candidate evidence root"),
    )
    for role, entries in protected_sources.items():
        if role in {"control_root", "data_root"}:
            continue
        for protected_path, source_label in entries:
            for target_path, target_label in cleanup_and_evidence_scope:
                if _paths_overlap(protected_path, target_path, flavor=flavor):
                    raise ValueError(f"{source_label} overlaps the clean-memory {target_label}")

    seen_protected_paths: dict[str, tuple[str, str]] = {}
    for role, entries in protected_sources.items():
        for protected_path, source_label in entries:
            comparison_key = _path_comparison_key(protected_path, flavor=flavor)
            previous = seen_protected_paths.get(comparison_key)
            if previous is not None:
                previous_role, previous_label = previous
                raise ValueError(
                    f"{source_label} duplicates {previous_label} across protected roles "
                    f"{role} and {previous_role}"
                )
            seen_protected_paths[comparison_key] = (role, source_label)

    protected = {
        role: tuple(path for path, _source_label in protected_sources[role])
        for role in _CONFIGURED_PROTECTED_ROLES
    }
    configured_protected_paths = [
        {"role": role, "paths": list(protected[role])}
        for role in _CONFIGURED_PROTECTED_ROLES
    ]
    return logical_paths, declared_faiss_paths, configured_protected_paths, flavor


def _resolve_qdrant(
    qdrant: Mapping[str, Any],
    phase6: Mapping[str, Any],
    *,
    epoch_id: str,
) -> dict[str, Any]:
    enabled = _required_value(qdrant, "enabled", label="qdrant.enabled")
    if enabled is not True:
        raise ValueError("qdrant.enabled must be exactly true")

    endpoint_value = _required_value(qdrant, "host", label="qdrant.host")
    endpoint, endpoint_port = _canonical_qdrant_endpoint(endpoint_value)
    if "port" in qdrant and qdrant["port"] is not None:
        configured_port = qdrant["port"]
        if (
            not isinstance(configured_port, int)
            or isinstance(configured_port, bool)
            or not 1 <= configured_port <= 65535
            or configured_port != endpoint_port
        ):
            raise ValueError("qdrant.port must exactly match qdrant.host")

    collections_value = _required_value(
        qdrant,
        "collections",
        label="qdrant.collections",
    )
    if not isinstance(collections_value, Mapping):
        raise ValueError("qdrant.collections must be a mapping")
    if set(collections_value) != set(_QDRANT_ROLES):
        raise ValueError("qdrant.collections must contain exactly four roles")
    collection_records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    expected_names: dict[str, str] = {}
    for role in _QDRANT_ROLES:
        expected = f"goodq_{role}_{epoch_id}"
        actual = collections_value.get(role)
        if actual != expected or not isinstance(actual, str):
            raise ValueError("qdrant.collections do not match the configured epoch")
        if actual in seen_names:
            raise ValueError("qdrant.collections contain duplicate names")
        seen_names.add(actual)
        expected_names[role] = actual
        collection_records.append({"role": role, "collection_name": actual})

    for role in ("clip", "dino"):
        key = f"{role}_collection"
        value = _required_text(phase6, key, label=f"phase6.{key}")
        if value != expected_names[role]:
            raise ValueError(f"phase6.{key} does not match qdrant.collections.{role}")

    return {
        "enabled": True,
        "endpoint": endpoint,
        "port": endpoint_port,
        "collections": collection_records,
    }


def resolve_plan_configuration(
    config: Mapping[str, Any],
    *,
    requested_epoch_id: str,
) -> ResolvedPlanConfiguration:
    """Resolve deterministic cleanup-plan configuration without observation."""

    if not isinstance(config, Mapping):
        raise TypeError("config must be a mapping")
    if not isinstance(requested_epoch_id, str):
        raise TypeError("requested_epoch_id must be a string")
    if not _EPOCH_ID_RE.fullmatch(requested_epoch_id):
        raise ValueError("requested_epoch_id must be one exact epoch identifier")

    host = _section(config, "host")
    paths = _section(config, "paths")
    qdrant = _section(config, "qdrant")
    phase6 = _section(config, "phase6")

    logical_paths, declared_faiss_paths, configured_protected_paths, flavor = _resolve_paths(
        host,
        paths,
        epoch_id=requested_epoch_id,
    )
    configured_roles = {item["role"] for item in configured_protected_paths}
    if configured_roles != set(_CONFIGURED_PROTECTED_ROLES):
        raise ValueError("configured protected-role mapping is incomplete")
    unresolved_roles = tuple(sorted(set(_PROTECTED_BOUNDARY_ROLES) - configured_roles))
    if configured_roles | set(unresolved_roles) != set(_PROTECTED_BOUNDARY_ROLES):
        raise ValueError("protected-role census does not match candidate-plan authority")

    projection = {
        "schema": CONFIGURATION_SCHEMA,
        "path_flavor": flavor,
        "epoch": {
            "epoch_id": requested_epoch_id,
            "root": logical_paths["memory_database"].rsplit("/", 1)[0],
        },
        "logical_paths": logical_paths,
        "declared_faiss_paths": dict(sorted(declared_faiss_paths.items())),
        "qdrant": _resolve_qdrant(qdrant, phase6, epoch_id=requested_epoch_id),
        "configured_protected_paths": configured_protected_paths,
        "unresolved_protected_roles": list(unresolved_roles),
    }
    return ResolvedPlanConfiguration._from_projection(projection)
