"""Read-only Windows external-pin evidence for clean-memory authority."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
import hashlib
import json
import os
from typing import Any


EXTERNAL_PIN_EVIDENCE_SCHEMA = "goodq.clean-memory-external-pin-evidence.v1"

__all__ = (
    "EXTERNAL_PIN_EVIDENCE_SCHEMA",
    "ExternalPinReaderError",
    "ExternalPinEvidence",
    "read_external_pin",
)

_ERROR_MESSAGES = {
    "unsupported_platform": "Clean-memory external pin reading is unsupported",
    "unsupported_filesystem": "Clean-memory external pin storage is unsupported",
    "unsupported_security": (
        "Clean-memory external pin security inspection is unsupported"
    ),
    "untrusted_reader": "Clean-memory external pin reader is not authorized",
    "security_policy_mismatch": (
        "Clean-memory external pin security policy is invalid"
    ),
    "pin_missing": "Clean-memory external pin is missing",
    "malformed_pin": "Clean-memory external pin payload is invalid",
    "redirected_boundary": "Clean-memory external pin boundary is redirected",
    "unexpected_entry_type": (
        "Clean-memory external pin entry type is unsupported"
    ),
    "duplicate_identity": "Clean-memory external pin identity is ambiguous",
    "sharing_conflict": "Clean-memory external pin is not quiescent",
    "observation_raced": (
        "Clean-memory external pin changed during observation"
    ),
    "observation_failed": "Clean-memory external pin observation failed",
}

_EVIDENCE_KEYS = {
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

_DWORD = ctypes.c_uint32
_BOOL = ctypes.c_int32
_ENUM = ctypes.c_int32
_WORD = ctypes.c_uint16
_BYTE = ctypes.c_ubyte
_HANDLE = ctypes.c_void_p
_PVOID = ctypes.c_void_p
_LARGE_INTEGER = ctypes.c_int64


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", _DWORD),
        ("Data2", _WORD),
        ("Data3", _WORD),
        ("Data4", _BYTE * 8),
    ]


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", _DWORD), ("HighPart", ctypes.c_int32)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", _LUID), ("Attributes", _DWORD)]


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", _PVOID), ("Attributes", _DWORD)]


class _TOKEN_USER(ctypes.Structure):
    _fields_ = [("User", _SID_AND_ATTRIBUTES)]


class _TOKEN_GROUPS(ctypes.Structure):
    _fields_ = [("GroupCount", _DWORD), ("Groups", _SID_AND_ATTRIBUTES * 1)]


class _TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", _DWORD),
        ("Privileges", _LUID_AND_ATTRIBUTES * 1),
    ]


class _TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", _SID_AND_ATTRIBUTES)]


class _TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", _DWORD)]


class _TOKEN_STATISTICS(ctypes.Structure):
    _fields_ = [
        ("TokenId", _LUID),
        ("AuthenticationId", _LUID),
        ("ExpirationTime", _LARGE_INTEGER),
        ("TokenType", _ENUM),
        ("ImpersonationLevel", _ENUM),
        ("DynamicCharged", _DWORD),
        ("DynamicAvailable", _DWORD),
        ("GroupCount", _DWORD),
        ("PrivilegeCount", _DWORD),
        ("ModifiedId", _LUID),
    ]


class _GENERIC_MAPPING(ctypes.Structure):
    _fields_ = [
        ("GenericRead", _DWORD),
        ("GenericWrite", _DWORD),
        ("GenericExecute", _DWORD),
        ("GenericAll", _DWORD),
    ]


class _PRIVILEGE_SET(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", _DWORD),
        ("Control", _DWORD),
        ("Privilege", _LUID_AND_ATTRIBUTES * 1),
    ]


@dataclass(frozen=True)
class _NativeApi:
    kernel32: object
    shell32: object
    ole32: object
    advapi32: object


class ExternalPinReaderError(RuntimeError):
    """Fixed, path-free external-pin observation failure."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        try:
            message = _ERROR_MESSAGES[code]
        except (KeyError, TypeError) as exc:
            raise ValueError("Unknown external pin reader error code") from exc
        super().__init__(message)
        object.__setattr__(self, "_code", code)

    @property
    def code(self) -> str:
        return self._code

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"code", "_code"} and hasattr(self, "_code"):
            raise AttributeError("External pin reader error code is immutable")
        object.__setattr__(self, name, value)


def _raise(code: str) -> None:
    raise ExternalPinReaderError(code) from None


def _pointer_size() -> int:
    return ctypes.sizeof(ctypes.c_void_p)


def _verify_win64_layouts() -> None:
    expected = (
        (ctypes.sizeof(_GUID), 16),
        (ctypes.sizeof(_LUID), 8),
        (ctypes.sizeof(_LUID_AND_ATTRIBUTES), 12),
        (ctypes.sizeof(_SID_AND_ATTRIBUTES), 16),
        (_SID_AND_ATTRIBUTES.Attributes.offset, 8),
        (ctypes.sizeof(_TOKEN_USER), 16),
        (_TOKEN_GROUPS.Groups.offset, 8),
        (_TOKEN_PRIVILEGES.Privileges.offset, 4),
        (ctypes.sizeof(_TOKEN_MANDATORY_LABEL), 16),
        (ctypes.sizeof(_TOKEN_ELEVATION), 4),
        (ctypes.sizeof(_TOKEN_STATISTICS), 56),
        (_TOKEN_STATISTICS.GroupCount.offset, 40),
        (_TOKEN_STATISTICS.PrivilegeCount.offset, 44),
        (_TOKEN_STATISTICS.ModifiedId.offset, 48),
        (ctypes.sizeof(_GENERIC_MAPPING), 16),
        (_PRIVILEGE_SET.Privilege.offset, 8),
        (ctypes.sizeof(_PRIVILEGE_SET), 20),
    )
    if _pointer_size() != 8 or any(actual != required for actual, required in expected):
        _raise("unsupported_security")


def _bind_native() -> _NativeApi:
    _verify_win64_layouts()
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    except (AttributeError, OSError):
        _raise("unsupported_platform")
    try:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    except (AttributeError, OSError):
        _raise("unsupported_security")

    try:
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(_GUID),
            _DWORD,
            _HANDLE,
            ctypes.POINTER(_PVOID),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_int32
        ole32.CoTaskMemFree.argtypes = [_PVOID]
        ole32.CoTaskMemFree.restype = None
    except (AttributeError, OSError):
        _raise("unsupported_platform")

    try:
        kernel32.GetCurrentThread.argtypes = []
        kernel32.GetCurrentThread.restype = _HANDLE
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = _HANDLE
        kernel32.CloseHandle.argtypes = [_HANDLE]
        kernel32.CloseHandle.restype = _BOOL
        kernel32.LocalFree.argtypes = [_PVOID]
        kernel32.LocalFree.restype = _PVOID

        advapi32.OpenThreadToken.argtypes = [
            _HANDLE,
            _DWORD,
            _BOOL,
            ctypes.POINTER(_HANDLE),
        ]
        advapi32.OpenThreadToken.restype = _BOOL
        advapi32.OpenProcessToken.argtypes = [
            _HANDLE,
            _DWORD,
            ctypes.POINTER(_HANDLE),
        ]
        advapi32.OpenProcessToken.restype = _BOOL
        advapi32.GetTokenInformation.argtypes = [
            _HANDLE,
            _ENUM,
            _PVOID,
            _DWORD,
            ctypes.POINTER(_DWORD),
        ]
        advapi32.GetTokenInformation.restype = _BOOL
        advapi32.LookupPrivilegeValueW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.POINTER(_LUID),
        ]
        advapi32.LookupPrivilegeValueW.restype = _BOOL
        advapi32.DuplicateTokenEx.argtypes = [
            _HANDLE,
            _DWORD,
            _PVOID,
            _ENUM,
            _ENUM,
            ctypes.POINTER(_HANDLE),
        ]
        advapi32.DuplicateTokenEx.restype = _BOOL
        advapi32.MapGenericMask.argtypes = [
            ctypes.POINTER(_DWORD),
            ctypes.POINTER(_GENERIC_MAPPING),
        ]
        advapi32.MapGenericMask.restype = None
        advapi32.AccessCheck.argtypes = [
            _PVOID,
            _HANDLE,
            _DWORD,
            ctypes.POINTER(_GENERIC_MAPPING),
            _PVOID,
            ctypes.POINTER(_DWORD),
            ctypes.POINTER(_DWORD),
            ctypes.POINTER(_BOOL),
        ]
        advapi32.AccessCheck.restype = _BOOL

        pointer_to_void = ctypes.POINTER(_PVOID)
        advapi32.GetSecurityInfo.argtypes = [
            _PVOID,
            _ENUM,
            _DWORD,
            pointer_to_void,
            pointer_to_void,
            pointer_to_void,
            pointer_to_void,
            pointer_to_void,
        ]
        advapi32.GetSecurityInfo.restype = _DWORD
        advapi32.IsValidSecurityDescriptor.argtypes = [_PVOID]
        advapi32.IsValidSecurityDescriptor.restype = _BOOL
        advapi32.GetSecurityDescriptorControl.argtypes = [
            _PVOID,
            ctypes.POINTER(_WORD),
            ctypes.POINTER(_DWORD),
        ]
        advapi32.GetSecurityDescriptorControl.restype = _BOOL
        advapi32.GetSecurityDescriptorLength.argtypes = [_PVOID]
        advapi32.GetSecurityDescriptorLength.restype = _DWORD
    except (AttributeError, OSError):
        _raise("unsupported_security")

    return _NativeApi(
        kernel32=kernel32,
        shell32=shell32,
        ole32=ole32,
        advapi32=advapi32,
    )


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("External pin evidence projection is invalid") from exc


def _validate_evidence_projection(projection: object) -> dict[str, Any]:
    if type(projection) is not dict or set(projection) != _EVIDENCE_KEYS:
        raise ValueError("External pin evidence projection is invalid")
    if (
        projection.get("schema") != EXTERNAL_PIN_EVIDENCE_SCHEMA
        or projection.get("platform") != "windows"
        or projection.get("source_id")
        != "goodq.clean-memory-protected-authority-pin.primary.v1"
        or projection.get("source_schema")
        != "goodq.clean-memory-external-pin-source.v1"
        or type(projection.get("dedicated_directory_identities")) is not list
        or len(projection["dedicated_directory_identities"]) != 3
    ):
        raise ValueError("External pin evidence projection is invalid")
    return projection


@dataclass(frozen=True, init=False)
class ExternalPinEvidence:
    """Immutable external-pin evidence with a detached public projection."""

    _projection_bytes: bytes = field(repr=False)
    external_pin_evidence_sha256: str

    def __new__(cls):
        raise TypeError("ExternalPinEvidence has no public constructor")

    @classmethod
    def _from_projection(cls, projection: dict[str, Any]) -> "ExternalPinEvidence":
        validated = _validate_evidence_projection(projection)
        projection_bytes = _canonical_json_bytes(validated)
        instance = object.__new__(cls)
        object.__setattr__(instance, "_projection_bytes", projection_bytes)
        object.__setattr__(
            instance,
            "external_pin_evidence_sha256",
            hashlib.sha256(projection_bytes).hexdigest(),
        )
        return instance

    @property
    def projection(self) -> dict[str, Any]:
        value = json.loads(self._projection_bytes.decode("utf-8"))
        if type(value) is not dict:
            raise ValueError("External pin evidence projection is invalid")
        return value


def read_external_pin() -> ExternalPinEvidence:
    """Read and authenticate the fixed Windows clean-memory authority pin."""

    if os.name != "nt":
        _raise("unsupported_platform")
    _bind_native()
    _raise("unsupported_platform")
