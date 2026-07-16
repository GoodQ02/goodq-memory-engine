"""Canonical validation for supplied protected-manifest bytes."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any
import unicodedata


PROTECTED_MANIFEST_SCHEMA = "goodq.clean-memory-protected-authority.v1"
PROTECTED_MANIFEST_CHILD_NAME = "protected-boundaries.json"
PROTECTED_MANIFEST_MAX_BYTES = 4_194_304
PROTECTED_MANIFEST_ROLE_ORDER = (
    "backup_root",
    "download_cache",
    "public_checkout",
    "qdrant_service_logs",
    "recovery_root",
    "reports_root",
    "repository",
    "source_media",
)

__all__ = (
    "PROTECTED_MANIFEST_SCHEMA",
    "PROTECTED_MANIFEST_CHILD_NAME",
    "PROTECTED_MANIFEST_MAX_BYTES",
    "PROTECTED_MANIFEST_ROLE_ORDER",
    "CanonicalProtectedManifest",
    "validate_protected_manifest",
)

_MAX_PATH_BYTES = 4_096
_MAX_MEMBERS_PER_ROLE = 64
_MAX_MEMBERS_TOTAL = 512
_MEMBER_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^([A-Z]):/(.+)$")
_UNRESOLVED_ENV_RE = re.compile(
    r"(?:\$\{|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%)"
)
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CONIN$",
    "CONOUT$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
    *(f"COM{index}" for index in ("\u00b9", "\u00b2", "\u00b3")),
    *(f"LPT{index}" for index in ("\u00b9", "\u00b2", "\u00b3")),
}


class _DuplicateJsonKey(ValueError):
    pass


@dataclass(frozen=True, init=False)
class CanonicalProtectedManifest:
    """Immutable validated manifest with a detached public view."""

    _manifest_bytes: bytes = field(repr=False)
    manifest_sha256: str

    def __new__(cls) -> "CanonicalProtectedManifest":
        raise TypeError("CanonicalProtectedManifest cannot be constructed directly")

    @property
    def manifest(self) -> dict[str, Any]:
        """Return a fresh detached manifest object."""

        value = json.loads(self._manifest_bytes.decode("utf-8"))
        if type(value) is not dict:
            raise ValueError("Manifest is not a JSON object")
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
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("Protected-membership value is not canonical JSON") from exc


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey
        value[key] = item
    return value


def _reject_nonfinite(_value: str) -> None:
    raise ValueError


def _strict_json_text(value: str, *, source: str) -> dict[str, Any]:
    try:
        parsed = json.loads(
            value,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_nonfinite,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        _DuplicateJsonKey,
        ValueError,
        RecursionError,
    ):
        raise ValueError(f"{source} is not canonical JSON") from None
    if type(parsed) is not dict:
        raise ValueError(f"{source} is not a JSON object")
    try:
        _validate_json_strings(parsed, source=source)
        canonical_value = _canonical_json_text(parsed)
    except RecursionError:
        raise ValueError(f"{source} is not canonical JSON") from None
    if canonical_value != value:
        raise ValueError(f"{source} bytes are not canonical")
    return parsed


def _validate_json_strings(value: object, *, source: str) -> None:
    if type(value) is str:
        if unicodedata.normalize("NFC", value) != value or _contains_control(value):
            raise ValueError(f"{source} contains a noncanonical string")
        return
    if type(value) is list:
        for item in value:
            _validate_json_strings(item, source=source)
        return
    if type(value) is dict:
        for key, item in value.items():
            _validate_json_strings(key, source=source)
            _validate_json_strings(item, source=source)


def _contains_control(value: str) -> bool:
    return any(unicodedata.category(character) == "Cc" for character in value)


def _canonical_absolute_path(value: object, *, expected_flavor: str) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or "\\" in value
        or value.endswith("/")
        or "//" in value
        or unicodedata.normalize("NFC", value) != value
        or _contains_control(value)
        or _UNRESOLVED_ENV_RE.search(value)
    ):
        raise ValueError("Protected-membership path is not canonical")

    windows_match = _WINDOWS_ABSOLUTE_RE.fullmatch(value)
    if windows_match is not None:
        if expected_flavor != "windows":
            raise ValueError("Protected-membership path uses the wrong flavor")
        parts = windows_match.group(2).split("/")
        for component in parts:
            if (
                component in {"", ".", ".."}
                or component.endswith((".", " "))
                or any(character in '<>:"|?*' for character in component)
                or component.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
            ):
                raise ValueError("Protected-membership path is not canonical")
        return value

    if value.startswith("/") and value != "/":
        if expected_flavor != "posix":
            raise ValueError("Protected-membership path uses the wrong flavor")
        if any(component in {"", ".", ".."} for component in value[1:].split("/")):
            raise ValueError("Protected-membership path is not canonical")
        return value

    raise ValueError("Protected-membership path is not a canonical local absolute path")


def validate_protected_manifest(
    manifest_bytes: bytes,
    *,
    path_flavor: str,
) -> CanonicalProtectedManifest:
    """Validate supplied canonical bytes without observing any runtime surface."""

    if type(manifest_bytes) is not bytes:
        raise TypeError("manifest_bytes must be exact bytes")
    if not 1 <= len(manifest_bytes) <= PROTECTED_MANIFEST_MAX_BYTES:
        raise ValueError("Manifest bytes exceed the protocol size boundary")
    if type(path_flavor) is not str:
        raise TypeError("path_flavor must be exact str")
    if path_flavor not in {"windows", "posix"}:
        raise ValueError("path_flavor must be 'windows' or 'posix'")
    try:
        manifest_text = manifest_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ValueError("Manifest bytes are not canonical UTF-8") from None
    manifest = _strict_json_text(manifest_text, source="Manifest")
    if manifest_text.encode("utf-8") != manifest_bytes:
        raise ValueError("Manifest bytes are not canonical UTF-8")
    if (
        set(manifest) != {"roles", "schema"}
        or manifest.get("schema") != PROTECTED_MANIFEST_SCHEMA
    ):
        raise ValueError("Manifest has an invalid schema envelope")
    roles = manifest.get("roles")
    if type(roles) is not list or len(roles) != len(PROTECTED_MANIFEST_ROLE_ORDER):
        raise ValueError("Manifest has an invalid role census")
    if tuple(
        record.get("role") if type(record) is dict else None for record in roles
    ) != PROTECTED_MANIFEST_ROLE_ORDER:
        raise ValueError("Manifest has an invalid role order")

    total_members = 0
    for record in roles:
        if type(record) is not dict or set(record) != {"members", "role"}:
            raise ValueError("Manifest has an invalid role record")
        members = record["members"]
        if (
            type(members) is not list
            or not 1 <= len(members) <= _MAX_MEMBERS_PER_ROLE
        ):
            raise ValueError("Manifest has an invalid member count")
        total_members += len(members)
        if total_members > _MAX_MEMBERS_TOTAL:
            raise ValueError("Manifest has too many members")
        previous_id: str | None = None
        for member in members:
            if type(member) is not dict or set(member) != {
                "absolute_path",
                "member_id",
                "object_kind",
                "presence",
            }:
                raise ValueError("Manifest has an invalid member record")
            member_id = member["member_id"]
            if type(member_id) is not str or not _MEMBER_ID_RE.fullmatch(member_id):
                raise ValueError("Manifest has an invalid member identifier")
            if previous_id is not None and member_id <= previous_id:
                raise ValueError("Manifest member identifiers are not strictly ordered")
            previous_id = member_id
            if member["object_kind"] != "directory" or member["presence"] not in {
                "required",
                "allow_absent",
            }:
                raise ValueError("Manifest has an invalid member policy")
            path = _canonical_absolute_path(
                member["absolute_path"],
                expected_flavor=path_flavor,
            )
            if len(path.encode("utf-8")) > _MAX_PATH_BYTES:
                raise ValueError("Manifest member path exceeds the protocol boundary")

    instance = object.__new__(CanonicalProtectedManifest)
    object.__setattr__(instance, "_manifest_bytes", manifest_bytes)
    object.__setattr__(
        instance,
        "manifest_sha256",
        hashlib.sha256(manifest_bytes).hexdigest(),
    )
    return instance
