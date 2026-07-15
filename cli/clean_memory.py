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
_COMPOSITION_ERROR_MESSAGES = {
    "invalid_configuration": (
        "Clean-memory authenticated composition configuration is invalid"
    ),
    "invalid_protected_membership": (
        "Clean-memory authenticated protected membership is invalid"
    ),
    "pin_member_overlap": (
        "Clean-memory protected membership overlaps the external pin chain"
    ),
    "observation_raced": (
        "Clean-memory authenticated protected authority changed during composition"
    ),
    "composition_failed": (
        "Clean-memory authenticated protected-membership composition failed"
    ),
}


class _ProtectedMembershipCompositionError(RuntimeError):
    """Closed path-free failure for private authenticated composition."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in _COMPOSITION_ERROR_MESSAGES:
            raise ValueError(
                "Unknown clean-memory authenticated composition error code"
            ) from None
        super().__init__(_COMPOSITION_ERROR_MESSAGES[code])
        object.__setattr__(self, "_code", code)

    @property
    def code(self) -> str:
        return object.__getattribute__(self, "_code")

    def __getattribute__(self, name: str):
        if name == "__dict__":
            return {}
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("Authenticated composition errors are immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("Authenticated composition errors are immutable")

    def add_note(self, note: str) -> None:
        del note
        raise TypeError("Authenticated composition errors cannot carry notes")

    def __copy__(self):
        raise TypeError("Authenticated composition errors cannot be copied")

    def __deepcopy__(self, memo: object):
        del memo
        raise TypeError("Authenticated composition errors cannot be copied")

    def __reduce__(self):
        raise TypeError("Authenticated composition errors cannot be serialized")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("Authenticated composition errors cannot be serialized")


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
    if any(
        character in "/\\" or ord(character) < 32 or ord(character) == 127
        for character in component
    ):
        raise ValueError(f"{label} is not one complete path component")
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


def _compose_authenticated_protected_membership(
    configuration: ResolvedPlanConfiguration,
) -> tuple[ProtectedBoundaryEvidence, ...]:
    """Compose authenticated protected authority for later private planning."""

    class _DuplicateKey(ValueError):
        pass

    named_controls = (KeyboardInterrupt, SystemExit, GeneratorExit)
    digest_pattern = re.compile(r"^[0-9a-f]{64}$")
    member_id_pattern = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
    configured_member_policy = {
        "archive_root": ("directory", "allow_absent", 1),
        "control_root": ("directory", "required", 1),
        "data_root": ("directory", "required", 1),
        "failed_media": ("directory", "allow_absent", 1),
        "import_media": ("directory", "allow_absent", 1),
        "model_cache": ("directory", "allow_absent", 1),
        "processed_media": ("directory", "allow_absent", 1),
        "processing_media": ("directory", "allow_absent", 1),
        "qdrant_storage": ("directory", "allow_absent", 1),
        "watchdog_state": ("regular_file", "allow_absent", 2),
    }

    def new_error(code: str) -> _ProtectedMembershipCompositionError:
        error = _ProtectedMembershipCompositionError(code)
        object.__setattr__(error, "__cause__", None)
        object.__setattr__(error, "__context__", None)
        object.__setattr__(error, "__suppress_context__", True)
        return error

    def raise_closed(code: str) -> None:
        raise new_error(code) from None

    def reraise_control(error: BaseException, traceback) -> None:
        replacements: dict[int, _ProtectedMembershipCompositionError] = {}

        def replacement(value: BaseException | None):
            if value is None:
                return None
            identity = id(value)
            if identity not in replacements:
                replacements[identity] = new_error("composition_failed")
            return replacements[identity]

        object.__setattr__(error, "__cause__", replacement(error.__cause__))
        object.__setattr__(error, "__context__", replacement(error.__context__))
        object.__setattr__(error, "__suppress_context__", error.__cause__ is not None)
        raise error.with_traceback(traceback)

    def reraise_public(error: BaseException, traceback) -> None:
        canonical_failure: BaseException | None = None
        canonical_traceback = None
        canonical_args: tuple[str, ...] | None = None
        try:
            code = object.__getattribute__(error, "_code")
            if type(code) is not str:
                raise ValueError
            canonical = type(error)(code)
            candidate_args = object.__getattribute__(canonical, "args")
            if (
                type(candidate_args) is not tuple
                or len(candidate_args) != 1
                or type(candidate_args[0]) is not str
            ):
                raise ValueError
            canonical_args = candidate_args
        except BaseException as failure:
            canonical_failure = failure
            canonical_traceback = failure.__traceback__
        if canonical_failure is not None:
            if type(canonical_failure) in named_controls:
                reraise_control(canonical_failure, canonical_traceback)
            raise_closed("composition_failed")
        attributes = object.__getattribute__(error, "__dict__")
        replacements: dict[int, _ProtectedMembershipCompositionError] = {}

        def replacement(value: BaseException | None):
            if value is None:
                return None
            identity = id(value)
            if identity not in replacements:
                replacements[identity] = new_error("composition_failed")
            return replacements[identity]

        cause = replacement(error.__cause__)
        context = replacement(error.__context__)
        attributes.clear()
        object.__setattr__(error, "args", canonical_args)
        object.__setattr__(error, "__cause__", cause)
        object.__setattr__(error, "__context__", context)
        object.__setattr__(error, "__suppress_context__", cause is not None)
        raise error.with_traceback(traceback)

    def canonical_object_from_text(value: object) -> dict[str, Any]:
        if type(value) is not str:
            raise ValueError

        def pairs_without_duplicates(
            pairs: list[tuple[str, Any]],
        ) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in pairs:
                if key in result:
                    raise _DuplicateKey
                result[key] = item
            return result

        def reject_constant(_value: str) -> None:
            raise ValueError

        parsed = json.loads(
            value,
            object_pairs_hook=pairs_without_duplicates,
            parse_constant=reject_constant,
        )
        if type(parsed) is not dict:
            raise ValueError

        def validate_strings(item: object) -> None:
            if type(item) is str:
                if unicodedata.normalize("NFC", item) != item or any(
                    unicodedata.category(character) == "Cc" for character in item
                ):
                    raise ValueError
                return
            if type(item) is list:
                for child in item:
                    validate_strings(child)
                return
            if type(item) is dict:
                for key, child in item.items():
                    validate_strings(key)
                    validate_strings(child)

        validate_strings(parsed)
        if _canonical_json_text(parsed) != value:
            raise ValueError
        return parsed

    def canonical_object_from_bytes(value: object) -> dict[str, Any]:
        if type(value) is not bytes:
            raise ValueError
        text = value.decode("utf-8", errors="strict")
        if text.encode("utf-8") != value:
            raise ValueError
        return canonical_object_from_text(text)

    def is_digest(value: object) -> bool:
        return type(value) is str and digest_pattern.fullmatch(value) is not None

    def windows_components(value: object) -> tuple[str, tuple[str, ...]]:
        canonical, flavor = _canonical_absolute_path(value, label="protected path")
        if flavor != "windows" or canonical != value:
            raise ValueError
        match = _WINDOWS_ABSOLUTE_RE.fullmatch(canonical)
        if match is None:
            raise ValueError
        drive, remainder = match.groups()
        return f"{drive.upper()}:", tuple(remainder.split("/"))

    def snapshot_configuration() -> tuple[str, str, dict[str, Any]]:
        if type(configuration) is not ResolvedPlanConfiguration:
            raise ValueError
        projection_json = configuration._projection_json
        digest = configuration.configuration_scope_sha256
        if (
            type(projection_json) is not str
            or not is_digest(digest)
            or hashlib.sha256(projection_json.encode("utf-8")).hexdigest() != digest
        ):
            raise ValueError
        projection = canonical_object_from_text(projection_json)
        configuration_keys = {
            "configured_protected_paths",
            "declared_faiss_paths",
            "epoch",
            "logical_paths",
            "path_flavor",
            "qdrant",
            "schema",
            "unresolved_protected_roles",
        }
        logical_keys = {
            "candidate_evidence_root",
            "data_root",
            "faiss_root",
            "knowledge_graph_database",
            "knowledge_graph_database_shm",
            "knowledge_graph_database_wal",
            "memory_database",
            "memory_database_shm",
            "memory_database_wal",
            "storage_root",
        }
        if (
            set(projection) != configuration_keys
            or projection.get("schema") != CONFIGURATION_SCHEMA
            or projection.get("path_flavor") != "windows"
            or type(projection.get("logical_paths")) is not dict
            or set(projection["logical_paths"]) != logical_keys
        ):
            raise ValueError
        logical = projection["logical_paths"]
        for path in logical.values():
            windows_components(path)
        storage_root = logical["storage_root"]
        data_root = f"{storage_root}/GoodQ_Data"
        epoch = projection.get("epoch")
        if (
            logical["data_root"] != data_root
            or type(epoch) is not dict
            or set(epoch) != {"epoch_id", "root"}
            or type(epoch.get("epoch_id")) is not str
            or _EPOCH_ID_RE.fullmatch(epoch["epoch_id"]) is None
        ):
            raise ValueError
        epoch_root = f"{data_root}/epochs/{epoch['epoch_id']}"
        expected_logical = {
            "candidate_evidence_root": f"{data_root}/control/clean_memory",
            "data_root": data_root,
            "faiss_root": f"{epoch_root}/faiss",
            "knowledge_graph_database": f"{epoch_root}/knowledge_graph.db",
            "knowledge_graph_database_shm": f"{epoch_root}/knowledge_graph.db-shm",
            "knowledge_graph_database_wal": f"{epoch_root}/knowledge_graph.db-wal",
            "memory_database": f"{epoch_root}/memory.db",
            "memory_database_shm": f"{epoch_root}/memory.db-shm",
            "memory_database_wal": f"{epoch_root}/memory.db-wal",
            "storage_root": storage_root,
        }
        if logical != expected_logical or epoch["root"] != epoch_root:
            raise ValueError

        declared = projection.get("declared_faiss_paths")
        if type(declared) is not dict or list(declared) != sorted(declared):
            raise ValueError
        if not set(declared).issubset(_FAISS_DECLARATION_KEYS):
            raise ValueError
        declared_paths: list[str] = []
        for key, path in declared.items():
            if type(key) is not str:
                raise ValueError
            windows_components(path)
            if not path.startswith(f"{logical['faiss_root']}/"):
                raise ValueError
            if any(
                _paths_overlap(path, previous, flavor="windows")
                for previous in declared_paths
            ):
                raise ValueError
            declared_paths.append(path)

        records = projection.get("configured_protected_paths")
        if type(records) is not list or len(records) != len(
            _CONFIGURED_PROTECTED_ROLES
        ):
            raise ValueError
        if tuple(
            record.get("role") if type(record) is dict else None
            for record in records
        ) != _CONFIGURED_PROTECTED_ROLES:
            raise ValueError
        protected: dict[str, tuple[str, ...]] = {}
        seen_paths: set[str] = set()
        for record in records:
            if type(record) is not dict or set(record) != {"paths", "role"}:
                raise ValueError
            role = record["role"]
            paths = record["paths"]
            expected_count = 2 if role == "watchdog_state" else 1
            if type(paths) is not list or len(paths) != expected_count:
                raise ValueError
            canonical_paths: list[str] = []
            for path in paths:
                windows_components(path)
                comparison = path.casefold()
                if comparison in seen_paths:
                    raise ValueError
                seen_paths.add(comparison)
                canonical_paths.append(path)
            if role == "watchdog_state" and canonical_paths != sorted(canonical_paths):
                raise ValueError
            protected[role] = tuple(canonical_paths)
        if (
            protected["data_root"] != (data_root,)
            or protected["control_root"] != (f"{data_root}/control",)
            or protected["failed_media"] != (f"{data_root}/failed",)
            or protected["import_media"] != (f"{data_root}/import_inbox",)
            or protected["processed_media"] != (f"{data_root}/processed",)
        ):
            raise ValueError
        cleanup_scope = tuple(
            expected_logical[key]
            for key in (
                "memory_database",
                "memory_database_wal",
                "memory_database_shm",
                "knowledge_graph_database",
                "knowledge_graph_database_wal",
                "knowledge_graph_database_shm",
                "faiss_root",
                "candidate_evidence_root",
            )
        )
        for role, paths in protected.items():
            if role in {"control_root", "data_root"}:
                continue
            if any(
                _paths_overlap(path, target, flavor="windows")
                for path in paths
                for target in cleanup_scope
            ):
                raise ValueError
        unresolved = tuple(
            sorted(set(_PROTECTED_BOUNDARY_ROLES) - set(_CONFIGURED_PROTECTED_ROLES))
        )
        if projection.get("unresolved_protected_roles") != list(unresolved):
            raise ValueError

        qdrant = projection.get("qdrant")
        if (
            type(qdrant) is not dict
            or set(qdrant) != {"collections", "enabled", "endpoint", "port"}
            or qdrant.get("enabled") is not True
            or type(qdrant.get("port")) is not int
            or isinstance(qdrant.get("port"), bool)
        ):
            raise ValueError
        endpoint, port = _canonical_qdrant_endpoint(qdrant.get("endpoint"))
        if endpoint != qdrant["endpoint"] or port != qdrant["port"]:
            raise ValueError
        collections = qdrant.get("collections")
        if type(collections) is not list or len(collections) != len(_QDRANT_ROLES):
            raise ValueError
        for role, record in zip(_QDRANT_ROLES, collections, strict=True):
            if (
                type(record) is not dict
                or set(record) != {"collection_name", "role"}
                or record.get("role") != role
                or record.get("collection_name")
                != f"goodq_{role}_{epoch['epoch_id']}"
            ):
                raise ValueError
        if (
            configuration._projection_json != projection_json
            or configuration.configuration_scope_sha256 != digest
        ):
            raise ValueError
        return projection_json, digest, projection

    configuration_failure: BaseException | None = None
    configuration_traceback = None
    try:
        configuration_snapshot = snapshot_configuration()
    except BaseException as error:
        configuration_failure = error
        configuration_traceback = error.__traceback__
    if configuration_failure is not None:
        if type(configuration_failure) in named_controls:
            reraise_control(configuration_failure, configuration_traceback)
        if isinstance(configuration_failure, Exception):
            raise_closed("invalid_configuration")
        raise_closed("composition_failed")
    configuration_json, configuration_digest, configuration_projection = (
        configuration_snapshot
    )

    dependency_failure: BaseException | None = None
    dependency_traceback = None
    try:
        import ctypes

        from cli.clean_memory_external_pin import (
            EXTERNAL_PIN_EVIDENCE_SCHEMA,
            ExternalPinEvidence,
            ExternalPinReaderError,
            read_external_pin,
        )
        from cli.clean_memory_protected_boundary import (
            PROTECTED_BOUNDARY_IDENTITY_SCHEMA,
            ProtectedBoundaryObservationError,
            observe_protected_boundaries,
        )
        from cli.clean_memory_protected_manifest import (
            PROTECTED_MANIFEST_EVIDENCE_SCHEMA,
            ProtectedManifestEvidence,
            ProtectedManifestReaderError,
            read_protected_manifest,
        )
        from cli.clean_memory_protected_membership import (
            PROTECTED_MEMBERSHIP_SCHEMA,
            ProtectedMembershipProjection,
            project_protected_membership,
        )
        from steps.common.clean_memory import (
            PROTECTED_BOUNDARY_ROLES,
            ProtectedBoundaryEvidence,
        )
        from steps.common.clean_memory_windows_program_data_locator import (
            CleanMemoryWindowsProgramDataLocation,
            CleanMemoryWindowsProgramDataLocator,
            CleanMemoryWindowsProgramDataLocatorError,
            bind_clean_memory_windows_program_data_locator,
            verify_clean_memory_windows_program_data_locator_abi,
        )
    except BaseException as error:
        dependency_failure = error
        dependency_traceback = error.__traceback__
    if dependency_failure is not None:
        if type(dependency_failure) in named_controls:
            reraise_control(dependency_failure, dependency_traceback)
        raise_closed("composition_failed")

    def safe_check(call) -> bool:
        failure: BaseException | None = None
        traceback = None
        try:
            result = call()
        except BaseException as error:
            failure = error
            traceback = error.__traceback__
        if failure is None:
            return result is True
        if type(failure) in named_controls:
            reraise_control(failure, traceback)
        if isinstance(failure, Exception):
            return False
        raise_closed("composition_failed")

    def configuration_unchanged() -> bool:
        return safe_check(
            lambda: (
                type(configuration) is ResolvedPlanConfiguration
                and type(configuration._projection_json) is str
                and type(configuration.configuration_scope_sha256) is str
                and configuration._projection_json == configuration_json
                and configuration.configuration_scope_sha256 == configuration_digest
            )
        )

    def invoke(
        call,
        *,
        ordinary_code: str,
        public_errors: tuple[type[BaseException], ...] = (),
        stable=None,
    ):
        failure: BaseException | None = None
        traceback = None
        result = None
        try:
            result = call()
        except BaseException as error:
            failure = error
            traceback = error.__traceback__
        if failure is None:
            return result
        if type(failure) in named_controls:
            reraise_control(failure, traceback)
        if stable is not None and not stable():
            raise_closed("observation_raced")
        if type(failure) in public_errors:
            reraise_public(failure, traceback)
        if isinstance(failure, Exception):
            raise_closed(ordinary_code)
        raise_closed("composition_failed")

    def accept(call, *, code: str, stable):
        failure: BaseException | None = None
        traceback = None
        result = None
        try:
            result = call()
        except BaseException as error:
            failure = error
            traceback = error.__traceback__
        if failure is None:
            return result
        if type(failure) in named_controls:
            reraise_control(failure, traceback)
        if not stable():
            raise_closed("observation_raced")
        if isinstance(failure, Exception):
            raise_closed(code)
        raise_closed("composition_failed")

    def identity_key(
        value: object,
        *,
        object_kind: str,
        volume_serial: str | None = None,
    ) -> tuple[str, str, str]:
        if (
            type(value) is not dict
            or set(value)
            != {"file_id", "file_id_kind", "object_kind", "schema", "volume_serial"}
            or value.get("schema") != "goodq.windows-file-identity.v1"
            or value.get("object_kind") != object_kind
        ):
            raise ValueError
        volume = value.get("volume_serial")
        file_id_kind = value.get("file_id_kind")
        file_id = value.get("file_id")
        if (
            type(volume) is not str
            or re.fullmatch(r"[0-9a-f]{16}", volume) is None
            or int(volume, 16) == 0
            or type(file_id_kind) is not str
            or type(file_id) is not str
            or volume_serial is not None
            and volume != volume_serial
        ):
            raise ValueError
        if file_id_kind == "ntfs_file_index_64":
            if re.fullmatch(r"[0-9a-f]{16}", file_id) is None:
                raise ValueError
        elif file_id_kind == "refs_file_id_128":
            if re.fullmatch(r"[0-9a-f]{32}", file_id) is None:
                raise ValueError
        else:
            raise ValueError
        if int(file_id, 16) == 0:
            raise ValueError
        return volume, file_id_kind, file_id

    def snapshot_pin(value: object) -> tuple[bytes, str, dict[str, Any]]:
        if type(value) is not ExternalPinEvidence:
            raise ValueError
        projection_bytes = value._projection_bytes
        digest = value.external_pin_evidence_sha256
        if (
            type(projection_bytes) is not bytes
            or not is_digest(digest)
            or hashlib.sha256(projection_bytes).hexdigest() != digest
        ):
            raise ValueError
        projection = canonical_object_from_bytes(projection_bytes)
        pin_keys = {
            "anchor_identity",
            "dedicated_directory_identities",
            "enrolled_reader_identity_sha256",
            "manifest_sha256",
            "pin_file_identity",
            "platform",
            "schema",
            "security_policy_sha256",
            "source_id",
            "source_schema",
        }
        dedicated = projection.get("dedicated_directory_identities")
        if (
            set(projection) != pin_keys
            or projection.get("schema") != EXTERNAL_PIN_EVIDENCE_SCHEMA
            or projection.get("platform") != "windows"
            or projection.get("source_id")
            != "goodq.clean-memory-protected-authority-pin.primary.v1"
            or projection.get("source_schema")
            != "goodq.clean-memory-external-pin-source.v1"
            or type(dedicated) is not list
            or len(dedicated) != 3
            or not all(
                is_digest(projection.get(key))
                for key in (
                    "enrolled_reader_identity_sha256",
                    "manifest_sha256",
                    "security_policy_sha256",
                )
            )
            or value._projection_bytes != projection_bytes
            or value.external_pin_evidence_sha256 != digest
        ):
            raise ValueError
        anchor_key = identity_key(
            projection.get("anchor_identity"), object_kind="directory"
        )
        dedicated_keys = tuple(
            identity_key(
                item,
                object_kind="directory",
                volume_serial=anchor_key[0],
            )
            for item in dedicated
        )
        pin_file_key = identity_key(
            projection.get("pin_file_identity"),
            object_kind="regular_file",
            volume_serial=anchor_key[0],
        )
        identity_keys = (anchor_key, *dedicated_keys, pin_file_key)
        if (
            len(set(identity_keys)) != 5
            or len({item[1] for item in identity_keys}) != 1
        ):
            raise ValueError
        return projection_bytes, digest, projection

    def pin_unchanged(value: object, snapshot) -> bool:
        return safe_check(
            lambda: (
                type(value) is ExternalPinEvidence
                and type(value._projection_bytes) is bytes
                and type(value.external_pin_evidence_sha256) is str
                and value._projection_bytes == snapshot[0]
                and value.external_pin_evidence_sha256 == snapshot[1]
            )
        )

    def snapshot_manifest(
        value: object,
        pin_snapshot,
    ) -> tuple[bytes, bytes, str, dict[str, Any]]:
        if type(value) is not ProtectedManifestEvidence:
            raise ValueError
        manifest_bytes = value._manifest_bytes
        projection_bytes = value._projection_bytes
        digest = value.protected_manifest_evidence_sha256
        if (
            type(manifest_bytes) is not bytes
            or type(projection_bytes) is not bytes
            or not is_digest(digest)
            or hashlib.sha256(projection_bytes).hexdigest() != digest
            or value.manifest_bytes is not manifest_bytes
        ):
            raise ValueError
        projection = canonical_object_from_bytes(projection_bytes)
        manifest_keys = {
            "anchor_identity",
            "configuration_scope_sha256",
            "external_pin_evidence_sha256",
            "manifest_file_identity",
            "manifest_sha256",
            "platform",
            "route_directory_identities",
            "schema",
            "security_policy_sha256",
        }
        route = projection.get("route_directory_identities")
        _candidate_drive, candidate_components = windows_components(
            configuration_projection["logical_paths"]["candidate_evidence_root"]
        )
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        if (
            set(projection) != manifest_keys
            or projection.get("schema") != PROTECTED_MANIFEST_EVIDENCE_SCHEMA
            or projection.get("platform") != "windows"
            or projection.get("configuration_scope_sha256") != configuration_digest
            or projection.get("external_pin_evidence_sha256") != pin_snapshot[1]
            or projection.get("manifest_sha256") != manifest_sha256
            or pin_snapshot[2].get("manifest_sha256") != manifest_sha256
            or not is_digest(projection.get("security_policy_sha256"))
            or type(route) is not list
            or len(route) != len(candidate_components)
            or value._manifest_bytes is not manifest_bytes
            or value._projection_bytes != projection_bytes
            or value.protected_manifest_evidence_sha256 != digest
        ):
            raise ValueError
        anchor_key = identity_key(
            projection.get("anchor_identity"), object_kind="directory"
        )
        route_keys = tuple(
            identity_key(
                item,
                object_kind="directory",
                volume_serial=anchor_key[0],
            )
            for item in route
        )
        manifest_file_key = identity_key(
            projection.get("manifest_file_identity"),
            object_kind="regular_file",
            volume_serial=anchor_key[0],
        )
        identities = (anchor_key, *route_keys, manifest_file_key)
        if len(set(identities)) != len(identities):
            raise ValueError
        return manifest_bytes, projection_bytes, digest, projection

    def manifest_unchanged(value: object, snapshot) -> bool:
        return safe_check(
            lambda: (
                type(value) is ProtectedManifestEvidence
                and type(value._manifest_bytes) is bytes
                and type(value._projection_bytes) is bytes
                and type(value.protected_manifest_evidence_sha256) is str
                and value._manifest_bytes is snapshot[0]
                and value._projection_bytes == snapshot[1]
                and value.protected_manifest_evidence_sha256 == snapshot[2]
            )
        )

    def snapshot_membership(
        value: object,
        manifest_snapshot,
    ) -> tuple[str, str, dict[str, Any], tuple[str, ...]]:
        if type(value) is not ProtectedMembershipProjection:
            raise ValueError
        projection_json = value._projection_json
        digest = value.protected_membership_scope_sha256
        if (
            type(projection_json) is not str
            or not is_digest(digest)
            or hashlib.sha256(projection_json.encode("utf-8")).hexdigest() != digest
        ):
            raise ValueError
        projection = canonical_object_from_text(projection_json)
        membership_keys = {
            "configuration_scope_sha256",
            "manifest",
            "path_flavor",
            "protected_roles",
            "schema",
        }
        manifest_record = projection.get("manifest")
        roles = projection.get("protected_roles")
        configured_paths = {
            record["role"]: tuple(record["paths"])
            for record in configuration_projection["configured_protected_paths"]
        }
        if (
            set(projection) != membership_keys
            or projection.get("schema") != PROTECTED_MEMBERSHIP_SCHEMA
            or projection.get("path_flavor") != "windows"
            or projection.get("configuration_scope_sha256") != configuration_digest
            or type(manifest_record) is not dict
            or set(manifest_record) != {"child_name", "sha256"}
            or manifest_record.get("child_name") != "protected-boundaries.json"
            or manifest_record.get("sha256")
            != manifest_snapshot[3].get("manifest_sha256")
            or type(roles) is not list
            or tuple(
                record.get("role") if type(record) is dict else None
                for record in roles
            )
            != tuple(PROTECTED_BOUNDARY_ROLES)
        ):
            raise ValueError
        paths: list[str] = []
        full_paths: set[str] = set()
        prefix_spellings: dict[str, str] = {}
        manifest_member_count = 0
        for record in roles:
            if type(record) is not dict or set(record) != {"members", "role"}:
                raise ValueError
            role = record["role"]
            members = record["members"]
            if type(members) is not list:
                raise ValueError
            policy = configured_member_policy.get(role)
            if policy is None:
                if not 1 <= len(members) <= 64:
                    raise ValueError
                manifest_member_count += len(members)
                if manifest_member_count > 512:
                    raise ValueError
            elif len(members) != policy[2]:
                raise ValueError
            previous_id: str | None = None
            for index, member in enumerate(members):
                if (
                    type(member) is not dict
                    or set(member)
                    != {"absolute_path", "member_id", "object_kind", "presence"}
                ):
                    raise ValueError
                member_id = member.get("member_id")
                if (
                    type(member_id) is not str
                    or member_id_pattern.fullmatch(member_id) is None
                    or previous_id is not None
                    and member_id <= previous_id
                ):
                    raise ValueError
                previous_id = member_id
                if policy is None:
                    if (
                        member.get("object_kind") != "directory"
                        or member.get("presence")
                        not in {"required", "allow_absent"}
                    ):
                        raise ValueError
                elif (
                    member_id != f"configured_{index:02d}"
                    or member.get("object_kind") != policy[0]
                    or member.get("presence") != policy[1]
                ):
                    raise ValueError
                path = member.get("absolute_path")
                drive, components = windows_components(path)
                if policy is not None and path != configured_paths[role][index]:
                    raise ValueError
                comparison = path.casefold()
                if comparison in full_paths:
                    raise ValueError
                full_paths.add(comparison)
                for component_index in range(1, len(components) + 1):
                    prefix = f"{drive}/{'/'.join(components[:component_index])}"
                    prefix_key = prefix.casefold()
                    prior = prefix_spellings.setdefault(prefix_key, prefix)
                    if prior != prefix:
                        raise ValueError
                paths.append(path)
        if (
            value._projection_json != projection_json
            or value.protected_membership_scope_sha256 != digest
        ):
            raise ValueError
        return projection_json, digest, projection, tuple(paths)

    def membership_unchanged(value: object, snapshot) -> bool:
        return safe_check(
            lambda: (
                type(value) is ProtectedMembershipProjection
                and type(value._projection_json) is str
                and type(value.protected_membership_scope_sha256) is str
                and value._projection_json == snapshot[0]
                and value.protected_membership_scope_sha256 == snapshot[1]
            )
        )

    def snapshot_location(value: object) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
        if type(value) is not CleanMemoryWindowsProgramDataLocation:
            raise ValueError
        drive_root = value.drive_root
        program_data = value.program_data_components
        fixed = value.fixed_directory_components
        pin_name = value.pin_name
        if (
            type(drive_root) is not str
            or re.fullmatch(r"[A-Z]:\\", drive_root) is None
            or type(program_data) is not tuple
            or not program_data
            or type(fixed) is not tuple
            or fixed != ("GoodQ", "authority", "clean-memory")
            or pin_name != "protected-boundaries.sha256"
        ):
            raise ValueError
        for component in (*program_data, *fixed, pin_name):
            if type(component) is not str:
                raise ValueError
            _validate_path_component(component, windows=True, label="ProgramData")
            if unicodedata.normalize("NFC", component) != component:
                raise ValueError
        return drive_root, program_data, fixed, pin_name

    def location_matches(value: object, snapshot) -> bool:
        return safe_check(lambda: snapshot_location(value) == snapshot)

    def lexical_overlap(location_snapshot, member_paths: tuple[str, ...]) -> bool:
        drive, program_data, fixed, pin_name = location_snapshot
        prefixes = (
            program_data,
            (*program_data, fixed[0]),
            (*program_data, *fixed[:2]),
            (*program_data, *fixed),
            (*program_data, *fixed, pin_name),
        )
        comparison_drive = drive[:2].casefold()
        comparison_prefixes = tuple(
            tuple(component.casefold() for component in prefix) for prefix in prefixes
        )
        for member_path in member_paths:
            member_drive, member_components = windows_components(member_path)
            if member_drive.casefold() != comparison_drive:
                continue
            member_key = tuple(component.casefold() for component in member_components)
            for prefix in comparison_prefixes:
                common = min(len(prefix), len(member_key))
                if prefix[:common] == member_key[:common]:
                    return True
        return False

    def snapshot_boundaries(
        value: object,
        membership_snapshot,
    ) -> tuple[tuple[object, str, str, str], ...]:
        if type(value) is not tuple or len(value) != len(PROTECTED_BOUNDARY_ROLES):
            raise ValueError
        snapshots: list[tuple[object, str, str, str]] = []
        membership_roles = membership_snapshot[2]["protected_roles"]
        for role, role_record, evidence in zip(
            PROTECTED_BOUNDARY_ROLES,
            membership_roles,
            value,
            strict=True,
        ):
            if type(evidence) is not ProtectedBoundaryEvidence:
                raise ValueError
            logical_id = f"protected:{role}"
            if (
                type(evidence.role) is not str
                or type(evidence.logical_id) is not str
                or type(evidence.identity_json) is not str
                or evidence.role != role
                or evidence.logical_id != logical_id
            ):
                raise ValueError
            envelope = canonical_object_from_text(evidence.identity_json)
            if (
                set(envelope)
                != {
                    "logical_id",
                    "members",
                    "protected_membership_scope_sha256",
                    "role",
                    "schema",
                }
                or envelope.get("schema") != PROTECTED_BOUNDARY_IDENTITY_SCHEMA
                or envelope.get("role") != role
                or envelope.get("logical_id") != logical_id
                or envelope.get("protected_membership_scope_sha256")
                != membership_snapshot[1]
                or type(envelope.get("members")) is not list
                or len(envelope["members"]) != len(role_record["members"])
            ):
                raise ValueError
            for observed, selected in zip(
                envelope["members"],
                role_record["members"],
                strict=True,
            ):
                if (
                    type(observed) is not dict
                    or set(observed)
                    != {
                        "absence",
                        "child_comparison_sha256",
                        "logical_id",
                        "member_id",
                        "object_identity",
                        "object_kind",
                        "parent_identity",
                        "state",
                    }
                    or observed.get("member_id") != selected["member_id"]
                    or observed.get("logical_id")
                    != f"protected:{role}:{selected['member_id']}"
                    or observed.get("object_kind") != selected["object_kind"]
                ):
                    raise ValueError
                child_name = selected["absolute_path"].rsplit("/", 1)[-1]
                child_digest = hashlib.sha256(
                    unicodedata.normalize("NFC", child_name)
                    .casefold()
                    .encode("utf-8")
                ).hexdigest()
                if observed.get("child_comparison_sha256") != child_digest:
                    raise ValueError
                parent_key = identity_key(
                    observed.get("parent_identity"),
                    object_kind="directory",
                )
                state = observed.get("state")
                if state == "present":
                    object_key = identity_key(
                        observed.get("object_identity"),
                        object_kind=selected["object_kind"],
                        volume_serial=parent_key[0],
                    )
                    if (
                        observed.get("absence") is not None
                        or object_key[1] != parent_key[1]
                    ):
                        raise ValueError
                elif state == "absent":
                    absence = observed.get("absence")
                    if (
                        selected["presence"] != "allow_absent"
                        or observed.get("object_identity") is not None
                        or type(absence) is not dict
                        or set(absence)
                        != {
                            "after_membership_sha256",
                            "before_membership_sha256",
                            "schema",
                        }
                        or absence.get("schema")
                        != "goodq.clean-memory-stable-absence.v1"
                        or not is_digest(absence.get("before_membership_sha256"))
                        or absence.get("after_membership_sha256")
                        != absence.get("before_membership_sha256")
                    ):
                        raise ValueError
                else:
                    raise ValueError
            snapshots.append((evidence, role, logical_id, evidence.identity_json))
        return tuple(snapshots)

    def boundaries_unchanged(value: object, snapshots) -> bool:
        return safe_check(
            lambda: (
                type(value) is tuple
                and len(value) == len(snapshots)
                and all(
                    type(evidence) is ProtectedBoundaryEvidence
                    and evidence is snapshot[0]
                    and type(evidence.role) is str
                    and type(evidence.logical_id) is str
                    and type(evidence.identity_json) is str
                    and evidence.role == snapshot[1]
                    and evidence.logical_id == snapshot[2]
                    and evidence.identity_json == snapshot[3]
                    for evidence, snapshot in zip(value, snapshots, strict=True)
                )
            )
        )

    verify_result = invoke(
        verify_clean_memory_windows_program_data_locator_abi,
        ordinary_code="composition_failed",
        public_errors=(CleanMemoryWindowsProgramDataLocatorError,),
    )
    del verify_result
    shell32 = invoke(
        lambda: ctypes.WinDLL("shell32", use_last_error=True),
        ordinary_code="composition_failed",
    )
    ole32 = invoke(
        lambda: ctypes.WinDLL("ole32", use_last_error=True),
        ordinary_code="composition_failed",
    )
    locator = invoke(
        lambda: bind_clean_memory_windows_program_data_locator(
            shell32=shell32,
            ole32=ole32,
        ),
        ordinary_code="composition_failed",
        public_errors=(CleanMemoryWindowsProgramDataLocatorError,),
    )
    if type(locator) is not CleanMemoryWindowsProgramDataLocator:
        if not configuration_unchanged():
            raise_closed("observation_raced")
        raise_closed("composition_failed")
    baseline = invoke(
        locator.resolve,
        ordinary_code="composition_failed",
        public_errors=(CleanMemoryWindowsProgramDataLocatorError,),
    )
    baseline_snapshot = accept(
        lambda: snapshot_location(baseline),
        code="composition_failed",
        stable=configuration_unchanged,
    )

    pin = invoke(
        read_external_pin,
        ordinary_code="composition_failed",
        public_errors=(ExternalPinReaderError,),
        stable=configuration_unchanged,
    )
    pin_snapshot = accept(
        lambda: snapshot_pin(pin),
        code="composition_failed",
        stable=configuration_unchanged,
    )

    second = invoke(
        locator.resolve,
        ordinary_code="observation_raced",
    )
    if not location_matches(second, baseline_snapshot):
        raise_closed("observation_raced")
    if not configuration_unchanged() or not pin_unchanged(pin, pin_snapshot):
        raise_closed("observation_raced")

    manifest = invoke(
        lambda: read_protected_manifest(
            configuration,
            external_pin_evidence=pin,
        ),
        ordinary_code="composition_failed",
        public_errors=(ProtectedManifestReaderError,),
        stable=lambda: configuration_unchanged()
        and pin_unchanged(pin, pin_snapshot),
    )
    manifest_snapshot = accept(
        lambda: snapshot_manifest(manifest, pin_snapshot),
        code="composition_failed",
        stable=lambda: configuration_unchanged()
        and pin_unchanged(pin, pin_snapshot),
    )

    membership = invoke(
        lambda: project_protected_membership(
            configuration,
            manifest_bytes=manifest_snapshot[0],
        ),
        ordinary_code="invalid_protected_membership",
        stable=lambda: configuration_unchanged()
        and pin_unchanged(pin, pin_snapshot)
        and manifest_unchanged(manifest, manifest_snapshot),
    )
    membership_snapshot = accept(
        lambda: snapshot_membership(membership, manifest_snapshot),
        code="invalid_protected_membership",
        stable=lambda: configuration_unchanged()
        and pin_unchanged(pin, pin_snapshot)
        and manifest_unchanged(manifest, manifest_snapshot),
    )

    third = invoke(
        locator.resolve,
        ordinary_code="observation_raced",
    )
    if not location_matches(third, baseline_snapshot):
        raise_closed("observation_raced")
    if not (
        configuration_unchanged()
        and pin_unchanged(pin, pin_snapshot)
        and manifest_unchanged(manifest, manifest_snapshot)
        and membership_unchanged(membership, membership_snapshot)
    ):
        raise_closed("observation_raced")
    stable_inputs = lambda: (
        configuration_unchanged()
        and pin_unchanged(pin, pin_snapshot)
        and manifest_unchanged(manifest, manifest_snapshot)
        and membership_unchanged(membership, membership_snapshot)
    )
    overlap = invoke(
        lambda: lexical_overlap(baseline_snapshot, membership_snapshot[3]),
        ordinary_code="composition_failed",
        stable=stable_inputs,
    )
    if not stable_inputs():
        raise_closed("observation_raced")
    if overlap is not True and overlap is not False:
        if not stable_inputs():
            raise_closed("observation_raced")
        raise_closed("composition_failed")
    if overlap:
        raise_closed("pin_member_overlap")

    boundaries = invoke(
        lambda: observe_protected_boundaries(
            membership,
            external_pin_evidence=pin,
        ),
        ordinary_code="composition_failed",
        public_errors=(ProtectedBoundaryObservationError,),
        stable=stable_inputs,
    )
    boundary_snapshot = accept(
        lambda: snapshot_boundaries(boundaries, membership_snapshot),
        code="composition_failed",
        stable=stable_inputs,
    )

    fourth = invoke(
        locator.resolve,
        ordinary_code="observation_raced",
    )
    if not location_matches(fourth, baseline_snapshot):
        raise_closed("observation_raced")
    if not (
        stable_inputs()
        and boundaries_unchanged(boundaries, boundary_snapshot)
    ):
        raise_closed("observation_raced")
    return boundaries
