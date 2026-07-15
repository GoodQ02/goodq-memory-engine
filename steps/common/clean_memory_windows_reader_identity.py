"""Import-pure clean-memory Windows reader-identity policy and digest."""

from __future__ import annotations

import hashlib
import json

from steps.common.windows_security_mechanics import (
    WINDOWS_TOKEN_PROFILE_BASE,
    WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
    WindowsTokenSnapshot,
)


__all__ = (
    "CleanMemoryWindowsReaderIdentityError",
    "validate_clean_memory_windows_reader_identity",
    "clean_memory_windows_reader_identity_sha256",
)


_TOKEN_PRIMARY = 1
_SE_GROUP_ENABLED = 0x00000004
_SE_GROUP_USE_FOR_DENY_ONLY = 0x00000010
_SE_PRIVILEGE_ENABLED = 0x00000002
_ADMIN_SID = bytes.fromhex("01020000000000052000000020020000")
_MEDIUM_INTEGRITY_SID = bytes.fromhex("010100000000001000200000")
_READER_IDENTITY_SCHEMA = "goodq.clean-memory-windows-reader-identity.v1"
_ERROR_MESSAGE = "Clean-memory Windows reader identity is not authorized"


class CleanMemoryWindowsReaderIdentityError(ValueError):
    """Fixed, path-free ordinary-reader policy rejection."""

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__(_ERROR_MESSAGE)


def _validate_arguments(
    snapshot: object,
    *,
    profile: object,
    change_notify_luid: object,
) -> tuple[WindowsTokenSnapshot, str, int]:
    if type(snapshot) is not WindowsTokenSnapshot:
        raise TypeError("snapshot must be exact WindowsTokenSnapshot")
    if type(profile) is not str:
        raise TypeError("profile must be exact str")
    if profile not in {
        WINDOWS_TOKEN_PROFILE_BASE,
        WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
    }:
        raise ValueError("profile is unsupported")
    if type(change_notify_luid) is not int:
        raise TypeError("change_notify_luid must be exact int")
    if not 0 <= change_notify_luid <= 2**64 - 1:
        raise ValueError("change_notify_luid is outside the unsigned 64-bit boundary")
    return snapshot, profile, change_notify_luid


def _reject() -> None:
    raise CleanMemoryWindowsReaderIdentityError()


def validate_clean_memory_windows_reader_identity(
    snapshot: WindowsTokenSnapshot,
    *,
    profile: str,
    change_notify_luid: int,
) -> None:
    """Validate the frozen ordinary-reader policy over a detached snapshot."""

    snapshot, profile, change_notify_luid = _validate_arguments(
        snapshot,
        profile=profile,
        change_notify_luid=change_notify_luid,
    )
    if profile == WINDOWS_TOKEN_PROFILE_BASE:
        if snapshot.mandatory_policy is not None:
            _reject()
    elif (
        type(snapshot.mandatory_policy) is not int
        or snapshot.mandatory_policy not in {1, 3}
    ):
        _reject()

    if (
        snapshot.statistics.token_type != _TOKEN_PRIMARY
        or snapshot.elevation_type not in {1, 3}
        or snapshot.is_elevated
        or snapshot.restricted_sids
        or snapshot.integrity.sid.binary != _MEDIUM_INTEGRITY_SID
        or snapshot.ui_access
        or snapshot.is_app_container
        or snapshot.has_restrictions != (snapshot.elevation_type == 3)
    ):
        _reject()
    for record in snapshot.groups:
        if record.sid.binary == _ADMIN_SID and (
            not (record.attributes & _SE_GROUP_USE_FOR_DENY_ONLY)
            or (record.attributes & _SE_GROUP_ENABLED)
        ):
            _reject()
    for record in snapshot.privileges:
        if (
            record.attributes & _SE_PRIVILEGE_ENABLED
            and record.luid != change_notify_luid
        ):
            _reject()


def _reader_identity_projection(
    snapshot: WindowsTokenSnapshot,
) -> dict[str, object]:
    statistics = snapshot.statistics
    return {
        "elevation": {
            "is_elevated": snapshot.is_elevated,
            "type": "default" if snapshot.elevation_type == 1 else "limited",
        },
        "groups": [
            {
                "attributes": f"{record.attributes:08x}",
                "sid": record.sid.numeric,
            }
            for record in snapshot.groups
        ],
        "has_restrictions": snapshot.has_restrictions,
        "impersonation_level": None,
        "integrity_rid": "00002000",
        "integrity_sid": snapshot.integrity.sid.numeric,
        "is_app_container": snapshot.is_app_container,
        "privileges": [
            {
                "attributes": f"{record.attributes:08x}",
                "luid": f"{record.luid:016x}",
            }
            for record in snapshot.privileges
        ],
        "restricted_sids": [
            {
                "attributes": f"{record.attributes:08x}",
                "sid": record.sid.numeric,
            }
            for record in snapshot.restricted_sids
        ],
        "schema": _READER_IDENTITY_SCHEMA,
        "token_source": "process",
        "token_statistics": {
            "authentication_id": f"{statistics.authentication_id:016x}",
            "expiration_time": str(statistics.expiration_time),
            "group_count": str(statistics.group_count),
            "modified_id": f"{statistics.modified_id:016x}",
            "privilege_count": str(statistics.privilege_count),
            "token_id": f"{statistics.token_id:016x}",
        },
        "token_type": "primary",
        "ui_access": snapshot.ui_access,
        "user_sid": snapshot.user_sid.numeric,
    }


def clean_memory_windows_reader_identity_sha256(
    snapshot: WindowsTokenSnapshot,
    *,
    profile: str,
    change_notify_luid: int,
) -> str:
    """Revalidate and return only the frozen lowercase v1 SHA-256 digest."""

    validate_clean_memory_windows_reader_identity(
        snapshot,
        profile=profile,
        change_notify_luid=change_notify_luid,
    )
    canonical = json.dumps(
        _reader_identity_projection(snapshot),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
