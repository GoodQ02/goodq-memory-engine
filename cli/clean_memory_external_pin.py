"""Read-only Windows external-pin evidence for clean-memory authority."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
import hashlib
import json
import os
import struct
import unicodedata
from typing import Any

from steps.common.windows_held_handle import (
    WindowsDirectoryEntry,
    WindowsHeldHandleBackend,
    WindowsHeldHandleError,
    WindowsObjectSnapshot,
)


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

_TOKEN_QUERY = 0x0008
_TOKEN_DUPLICATE = 0x0002
_ERROR_INSUFFICIENT_BUFFER = 122
_ERROR_NO_TOKEN = 1008
_MAX_TOKEN_BUFFER = 1_048_576
_MAX_TOKEN_RECORDS = 4096
_MAX_SID_SUBAUTHORITIES = 15
_MAX_SID_BYTES = 68

_TOKEN_USER_CLASS = 1
_TOKEN_GROUPS_CLASS = 2
_TOKEN_PRIVILEGES_CLASS = 3
_TOKEN_STATISTICS_CLASS = 10
_TOKEN_RESTRICTED_SIDS_CLASS = 11
_TOKEN_ELEVATION_TYPE_CLASS = 18
_TOKEN_ELEVATION_CLASS = 20
_TOKEN_HAS_RESTRICTIONS_CLASS = 21
_TOKEN_INTEGRITY_LEVEL_CLASS = 25
_TOKEN_UI_ACCESS_CLASS = 26
_TOKEN_IS_APP_CONTAINER_CLASS = 29

_TOKEN_PRIMARY = 1
_TOKEN_IMPERSONATION = 2
_SECURITY_IMPERSONATION = 2

_SE_GROUP_ENABLED = 0x00000004
_SE_GROUP_USE_FOR_DENY_ONLY = 0x00000010
_SE_PRIVILEGE_ENABLED = 0x00000002

_PROGRAM_DATA_GUID_FIELDS = (
    0x62AB5D82,
    0xFDC1,
    0x4DC3,
    (0xA9, 0xDD, 0x07, 0x0D, 0x1D, 0x49, 0x5D, 0x97),
)
_PIN_NAME = "protected-boundaries.sha256"
_FIXED_CHILDREN = ("GoodQ", "authority", "clean-memory")

_SYSTEM_SID = bytes.fromhex("010100000000000512000000")
_ADMIN_SID = bytes.fromhex("01020000000000052000000020020000")
_MEDIUM_INTEGRITY_SID = bytes.fromhex("010100000000001000200000")

_FILE_GENERIC_MAPPING_VALUES = (
    0x00120089,
    0x00120116,
    0x001200A0,
    0x001F01FF,
)
_DIRECTORY_RIGHTS = (
    ("file_delete_child", 0x00000040),
    ("write_dac", 0x00040000),
    ("write_owner", 0x00080000),
)
_PIN_RIGHTS = (
    ("delete", 0x00010000),
    ("file_write_data", 0x00000002),
    ("file_append_data", 0x00000004),
    ("file_write_ea", 0x00000010),
    ("file_write_attributes", 0x00000100),
    ("write_dac", 0x00040000),
    ("write_owner", 0x00080000),
)

_ACCESS_ALLOWED_ACE_TYPE = 0
_ACCESS_DENIED_ACE_TYPE = 1
_ORDINARY_ACE_FLAG_MASK = 0x1F
_INHERIT_ONLY_ACE = 0x08
_SE_OWNER_DEFAULTED = 0x0001
_SE_GROUP_DEFAULTED = 0x0002
_SE_DACL_PRESENT = 0x0004
_SE_DACL_DEFAULTED = 0x0008
_SE_DACL_AUTO_INHERIT_REQ = 0x0100
_SE_DACL_AUTO_INHERITED = 0x0400
_SE_DACL_PROTECTED = 0x1000
_SE_SELF_RELATIVE = 0x8000
_PRIVILEGE_SET_ALL_NECESSARY = 0x00000001
_DANGEROUS_DIRECTORY_MASK = 0x00000040 | 0x00040000 | 0x00080000


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


@dataclass(frozen=True)
class _Sid:
    binary: bytes
    numeric: str


@dataclass(frozen=True)
class _SidRecord:
    sid: _Sid
    attributes: int


@dataclass(frozen=True)
class _Privilege:
    luid: int
    attributes: int


@dataclass(frozen=True)
class _PrimaryStatistics:
    token_id: int
    authentication_id: int
    expiration_time: int
    token_type: int
    dynamic_charged: int
    dynamic_available: int
    group_count: int
    privilege_count: int
    modified_id: int


@dataclass(frozen=True)
class _TokenSnapshot:
    statistics: _PrimaryStatistics
    user_sid: _Sid
    groups: tuple[_SidRecord, ...]
    privileges: tuple[_Privilege, ...]
    restricted_sids: tuple[_SidRecord, ...]
    elevation_type: int
    is_elevated: bool
    has_restrictions: bool
    integrity: _SidRecord
    ui_access: bool
    is_app_container: bool


@dataclass(frozen=True)
class _Ace:
    ace_type: int
    flags: int
    mask: int
    sid: _Sid


@dataclass(frozen=True)
class _SecurityDescriptor:
    control: int
    owner: _Sid
    group: _Sid
    dacl_revision: int
    aces: tuple[_Ace, ...]


@dataclass(frozen=True)
class _PinnedDescriptor:
    held: _HeldObject
    raw: bytes
    storage: Any
    address: int
    parsed: _SecurityDescriptor


class _OwnedNativeHandle:
    __slots__ = ("_cleanup_error", "_storage")

    def __init__(self, value: int | None) -> None:
        self._storage = _HANDLE(value)
        self._cleanup_error = ExternalPinReaderError("observation_failed")

    @property
    def value(self) -> int | None:
        value = self._storage.value
        return None if value is None else int(value)

    @value.setter
    def value(self, value: int | None) -> None:
        self._storage.value = value

    def output_pointer(self):
        return ctypes.byref(self._storage)


@dataclass(frozen=True)
class _KnownFolder:
    root: str
    components: tuple[str, ...]


@dataclass(frozen=True)
class _HeldObject:
    role: str
    handle: object
    entry: WindowsDirectoryEntry | None
    snapshot: WindowsObjectSnapshot
    object_kind: str


@dataclass(frozen=True)
class _ParentMembership:
    role: str
    handle: object
    entries: tuple[WindowsDirectoryEntry, ...]


@dataclass
class _ReadState:
    backend: object
    native: _NativeApi
    baseline: _OwnedNativeHandle
    baseline_snapshot: _TokenSnapshot
    filesystem: str | None = None
    root: _HeldObject | None = None
    held: list[_HeldObject] = field(default_factory=list)
    parents: list[_ParentMembership] = field(default_factory=list)


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


def _clone_public_error(
    error: ExternalPinReaderError,
    seen: set[int] | None = None,
) -> ExternalPinReaderError:
    visited = set() if seen is None else seen
    if id(error) in visited:
        return ExternalPinReaderError("observation_failed")
    visited.add(id(error))
    code = error.code if error.code in _ERROR_MESSAGES else "observation_failed"
    clone = ExternalPinReaderError(code)
    if type(error.__cause__) is ExternalPinReaderError:
        clone.__cause__ = _clone_public_error(error.__cause__, visited)
        clone.__suppress_context__ = True
    if type(error.__context__) is ExternalPinReaderError:
        clone.__context__ = _clone_public_error(error.__context__, visited)
    return clone


def _is_sanitized_public_error_graph(error: ExternalPinReaderError) -> bool:
    visiting: set[int] = set()
    complete: set[int] = set()

    def visit(node: BaseException) -> bool:
        identity = id(node)
        if identity in visiting:
            return False
        if identity in complete:
            return True
        if type(node) is not ExternalPinReaderError:
            return False
        try:
            code = node.code
            message = _ERROR_MESSAGES[code]
        except (AttributeError, KeyError, TypeError):
            return False
        if node.args != (message,) or vars(node):
            return False
        visiting.add(identity)
        for linked in (node.__cause__, node.__context__):
            if linked is not None and not visit(linked):
                return False
        visiting.discard(identity)
        complete.add(identity)
        return True

    return visit(error)


def _sanitize_windows_error_graph(
    error: WindowsHeldHandleError,
) -> ExternalPinReaderError:
    head: ExternalPinReaderError | None = None
    current = error
    remaining = 256
    while remaining:
        remaining -= 1
        code = current.code if current.code in _ERROR_MESSAGES else "observation_failed"
        head = _append_cleanup(head, ExternalPinReaderError(code))
        cause = current.__cause__
        context = current.__context__
        if isinstance(cause, WindowsHeldHandleError) and cause is not current:
            current = cause
            continue
        if isinstance(context, WindowsHeldHandleError) and context is not current:
            current = context
            continue
        break
    assert head is not None
    return head


def _sanitize_error(error: BaseException) -> ExternalPinReaderError:
    if type(error) is ExternalPinReaderError:
        if _is_sanitized_public_error_graph(error):
            return error
        return _clone_public_error(error)
    if isinstance(error, WindowsHeldHandleError):
        return _sanitize_windows_error_graph(error)
    return ExternalPinReaderError("observation_failed")


def _raise_collected(
    primary: ExternalPinReaderError | None,
    cleanup: ExternalPinReaderError | None,
) -> None:
    if primary is None:
        if cleanup is not None:
            raise cleanup
        return
    _attach_cleanup(primary, cleanup)
    raise primary from primary.__cause__


def _append_cleanup(
    head: ExternalPinReaderError | None,
    later: ExternalPinReaderError | None,
) -> ExternalPinReaderError | None:
    if later is None:
        return head
    if head is None:
        return later
    if head is later:
        return head
    tail = head
    while True:
        if tail is later:
            return head
        linked = tail.__cause__
        if type(linked) is ExternalPinReaderError:
            tail = linked
            continue
        context = tail.__context__
        if type(context) is ExternalPinReaderError:
            tail = context
            continue
        if linked is None:
            tail.__cause__ = later
            tail.__suppress_context__ = True
        elif context is None:
            tail.__context__ = later
        return head


def _attach_cleanup(
    primary: BaseException,
    cleanup: ExternalPinReaderError | None,
) -> None:
    if cleanup is None:
        return
    if primary.__cause__ is None:
        primary.__cause__ = cleanup
        primary.__suppress_context__ = True
        return
    if primary.__context__ is None:
        primary.__context__ = cleanup
        return
    if type(primary.__context__) is ExternalPinReaderError:
        _append_cleanup(primary.__context__, cleanup)
        return
    if type(primary.__cause__) is ExternalPinReaderError:
        _append_cleanup(primary.__cause__, cleanup)
        return
    preserved = primary.__context__
    primary.__context__ = cleanup
    _preserve_context(cleanup, preserved)


def _preserve_context(
    cleanup: ExternalPinReaderError,
    preserved: BaseException,
) -> None:
    tail: BaseException = cleanup
    remaining = 256
    while remaining:
        remaining -= 1
        if tail is preserved:
            return
        cause = tail.__cause__
        if type(cause) is ExternalPinReaderError:
            tail = cause
            continue
        context = tail.__context__
        if type(context) is ExternalPinReaderError:
            tail = context
            continue
        if context is None:
            tail.__context__ = preserved
            return
        tail = context


def _next_windows_cleanup(
    error: BaseException | None,
) -> WindowsHeldHandleError | None:
    if error is None:
        return None
    cause = error.__cause__
    if isinstance(cause, WindowsHeldHandleError):
        return cause
    context = error.__context__
    if isinstance(context, WindowsHeldHandleError):
        return context
    return None


def _sanitize_cleanup_chain(
    error: BaseException,
    *,
    cleanup_fallback: ExternalPinReaderError,
    processing_fallback: ExternalPinReaderError,
) -> ExternalPinReaderError:
    head: ExternalPinReaderError | None = None
    current: BaseException | None = error
    slow: BaseException | None = error
    fast: BaseException | None = error
    fallback_used = False
    processing_failed = False
    remaining = 256
    while current is not None and remaining:
        remaining -= 1
        later = _next_windows_cleanup(current)
        try:
            sanitized = _sanitize_error(current)
            if isinstance(current, WindowsHeldHandleError):
                sanitized.__cause__ = None
                sanitized.__context__ = None
                sanitized.__suppress_context__ = False
            if sanitized.code != "observation_failed":
                sanitized = ExternalPinReaderError("observation_failed")
        except BaseException:
            processing_failed = True
            if not fallback_used:
                head = _append_cleanup(head, cleanup_fallback)
                fallback_used = True
        else:
            head = _append_cleanup(head, sanitized)
        current = later
        if current is None:
            break
        slow = _next_windows_cleanup(slow)
        fast = _next_windows_cleanup(_next_windows_cleanup(fast))
        if slow is not None and slow is fast:
            processing_failed = True
            current = None
    if current is not None:
        processing_failed = True
    if processing_failed:
        head = _append_cleanup(head, processing_fallback)
    if head is None:
        return cleanup_fallback
    return head


def _raise_after_cleanup(
    primary: BaseException | None,
    cleanup: ExternalPinReaderError | None,
    *,
    fallback: ExternalPinReaderError | None = None,
) -> None:
    if primary is None:
        _raise_collected(None, cleanup)
        return
    if isinstance(primary, Exception):
        try:
            sanitized = _sanitize_error(primary)
        except BaseException:
            sanitized = fallback or ExternalPinReaderError("observation_failed")
        _raise_collected(sanitized, cleanup)
        return
    traceback = primary.__traceback__
    if isinstance(primary.__cause__, WindowsHeldHandleError):
        try:
            primary.__cause__ = _sanitize_error(primary.__cause__)
        except BaseException:
            primary.__cause__ = fallback or ExternalPinReaderError(
                "observation_failed"
            )
    if isinstance(primary.__context__, WindowsHeldHandleError):
        try:
            primary.__context__ = _sanitize_error(primary.__context__)
        except BaseException:
            primary.__context__ = fallback or ExternalPinReaderError(
                "observation_failed"
            )
    _attach_cleanup(primary, cleanup)
    if primary.__cause__ is not None:
        raise primary.with_traceback(traceback) from primary.__cause__
    raise primary.with_traceback(traceback)


def _load_windows_backend() -> WindowsHeldHandleBackend:
    backend: WindowsHeldHandleBackend | None = None
    failure: ExternalPinReaderError | None = None
    try:
        backend = WindowsHeldHandleBackend(access_profile="security_read")
    except Exception as error:
        failure = _sanitize_error(error)
    if failure is not None:
        raise failure from failure.__cause__
    if backend is None:
        _raise("observation_failed")
    return backend


def _last_error() -> int:
    return int(ctypes.get_last_error())


def _close_native_handle(
    native: _NativeApi,
    owned: _OwnedNativeHandle,
) -> ExternalPinReaderError | None:
    value = owned.value
    if value is None:
        return None
    owned.value = None
    try:
        closed = native.kernel32.CloseHandle(_HANDLE(value))
        if not closed:
            _last_error()
            return owned._cleanup_error
    except BaseException:
        return owned._cleanup_error
    return None


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


def _luid_value(value: _LUID) -> int:
    return ((int(value.HighPart) & 0xFFFFFFFF) << 32) | int(value.LowPart)


def _parse_sid(raw: bytes, offset: int) -> tuple[_Sid, tuple[int, int]]:
    if offset < 0 or offset + 8 > len(raw):
        _raise("observation_failed")
    revision = raw[offset]
    count = raw[offset + 1]
    size = 8 + 4 * count
    if (
        revision != 1
        or count > _MAX_SID_SUBAUTHORITIES
        or size > _MAX_SID_BYTES
        or offset + size > len(raw)
    ):
        _raise("observation_failed")
    binary = raw[offset : offset + size]
    authority = int.from_bytes(binary[2:8], "big")
    subauthorities = tuple(
        int.from_bytes(binary[8 + index * 4 : 12 + index * 4], "little")
        for index in range(count)
    )
    numeric = "-".join(
        ("S", "1", str(authority), *(str(value) for value in subauthorities))
    )
    return _Sid(binary=binary, numeric=numeric), (offset, offset + size)


def _sid_from_pointer(
    raw: bytes,
    base: int,
    pointer: int,
) -> tuple[_Sid, tuple[int, int]]:
    if pointer < base or pointer - base >= len(raw):
        _raise("observation_failed")
    return _parse_sid(raw, pointer - base)


def _reject_overlapping_intervals(intervals: tuple[tuple[int, int], ...]) -> None:
    ordered = sorted(intervals)
    for index in range(1, len(ordered)):
        if ordered[index][0] < ordered[index - 1][1]:
            _raise("observation_failed")


def _query_variable_token(
    native: _NativeApi,
    handle: int,
    info_class: int,
) -> tuple[bytes, int]:
    required = _DWORD(0xFFFFFFFF)
    try:
        succeeded = native.advapi32.GetTokenInformation(
            _HANDLE(handle),
            info_class,
            None,
            0,
            ctypes.byref(required),
        )
        if succeeded:
            _raise("observation_failed")
        error = _last_error()
    except ExternalPinReaderError:
        raise
    except Exception:
        _raise("observation_failed")
    if error != _ERROR_INSUFFICIENT_BUFFER:
        _raise("observation_failed")
    size = int(required.value)
    if size < 1 or size > _MAX_TOKEN_BUFFER:
        _raise("observation_failed")
    storage = (_BYTE * size)()
    ctypes.memset(ctypes.addressof(storage), 0xA5, size)
    returned = _DWORD(0xFFFFFFFF)
    try:
        succeeded = native.advapi32.GetTokenInformation(
            _HANDLE(handle),
            info_class,
            ctypes.cast(storage, _PVOID),
            size,
            ctypes.byref(returned),
        )
        if not succeeded:
            _last_error()
            _raise("observation_failed")
    except ExternalPinReaderError:
        raise
    except Exception:
        _raise("observation_failed")
    if int(returned.value) != size:
        _raise("observation_failed")
    return bytes(storage), ctypes.addressof(storage)


def _query_statistics(native: _NativeApi, handle: int) -> _PrimaryStatistics:
    value = _TOKEN_STATISTICS()
    ctypes.memset(ctypes.addressof(value), 0, ctypes.sizeof(value))
    value.TokenType = -1
    value.GroupCount = 0xFFFFFFFF
    value.PrivilegeCount = 0xFFFFFFFF
    returned = _DWORD(0xFFFFFFFF)
    try:
        succeeded = native.advapi32.GetTokenInformation(
            _HANDLE(handle),
            _TOKEN_STATISTICS_CLASS,
            ctypes.byref(value),
            ctypes.sizeof(value),
            ctypes.byref(returned),
        )
        if not succeeded:
            _last_error()
            _raise("observation_failed")
    except ExternalPinReaderError:
        raise
    except Exception:
        _raise("observation_failed")
    if int(returned.value) != ctypes.sizeof(value):
        _raise("observation_failed")
    token_type = int(value.TokenType)
    group_count = int(value.GroupCount)
    privilege_count = int(value.PrivilegeCount)
    if (
        token_type not in {_TOKEN_PRIMARY, _TOKEN_IMPERSONATION}
        or group_count > _MAX_TOKEN_RECORDS
        or privilege_count > _MAX_TOKEN_RECORDS
    ):
        _raise("observation_failed")
    return _PrimaryStatistics(
        token_id=_luid_value(value.TokenId),
        authentication_id=_luid_value(value.AuthenticationId),
        expiration_time=int(value.ExpirationTime),
        token_type=token_type,
        dynamic_charged=int(value.DynamicCharged),
        dynamic_available=int(value.DynamicAvailable),
        group_count=group_count,
        privilege_count=privilege_count,
        modified_id=_luid_value(value.ModifiedId),
    )


def _query_fixed_value(
    native: _NativeApi,
    handle: int,
    info_class: int,
    accepted: tuple[int, ...],
) -> int:
    value = _ENUM(-1)
    returned = _DWORD(0xFFFFFFFF)
    try:
        succeeded = native.advapi32.GetTokenInformation(
            _HANDLE(handle),
            info_class,
            ctypes.byref(value),
            4,
            ctypes.byref(returned),
        )
        if not succeeded:
            _last_error()
            _raise("observation_failed")
    except ExternalPinReaderError:
        raise
    except Exception:
        _raise("observation_failed")
    result = int(value.value)
    if int(returned.value) != 4 or result not in accepted:
        _raise("observation_failed")
    return result


def _parse_token_user(raw: bytes, base: int) -> _Sid:
    if len(raw) < 16:
        _raise("observation_failed")
    pointer = struct.unpack_from("<Q", raw, 0)[0]
    attributes = struct.unpack_from("<I", raw, 8)[0]
    if attributes != 0:
        _raise("observation_failed")
    sid, _interval = _sid_from_pointer(raw, base, pointer)
    return sid


def _parse_sid_records(
    raw: bytes,
    base: int,
) -> tuple[_SidRecord, ...]:
    if len(raw) < 8:
        _raise("observation_failed")
    count = struct.unpack_from("<I", raw, 0)[0]
    if count > _MAX_TOKEN_RECORDS or 8 + 16 * count > len(raw):
        _raise("observation_failed")
    records: list[_SidRecord] = []
    intervals: list[tuple[int, int]] = []
    for index in range(count):
        offset = 8 + 16 * index
        pointer = struct.unpack_from("<Q", raw, offset)[0]
        attributes = struct.unpack_from("<I", raw, offset + 8)[0]
        sid, interval = _sid_from_pointer(raw, base, pointer)
        records.append(_SidRecord(sid=sid, attributes=attributes))
        intervals.append(interval)
    _reject_overlapping_intervals(tuple(intervals))
    identities = [record.sid.binary for record in records]
    if len(set(identities)) != len(identities):
        _raise("observation_failed")
    return tuple(sorted(records, key=lambda record: record.sid.binary))


def _parse_privileges(raw: bytes) -> tuple[_Privilege, ...]:
    if len(raw) < 4:
        _raise("observation_failed")
    count = struct.unpack_from("<I", raw, 0)[0]
    if count > _MAX_TOKEN_RECORDS or 4 + 12 * count > len(raw):
        _raise("observation_failed")
    records = []
    for index in range(count):
        low, high, attributes = struct.unpack_from("<IiI", raw, 4 + 12 * index)
        luid = ((high & 0xFFFFFFFF) << 32) | low
        records.append(_Privilege(luid=luid, attributes=attributes))
    identities = [record.luid for record in records]
    if len(set(identities)) != len(identities):
        _raise("observation_failed")
    return tuple(sorted(records, key=lambda record: record.luid))


def _parse_integrity(raw: bytes, base: int) -> _SidRecord:
    if len(raw) < 16:
        _raise("observation_failed")
    pointer = struct.unpack_from("<Q", raw, 0)[0]
    attributes = struct.unpack_from("<I", raw, 8)[0]
    sid, _interval = _sid_from_pointer(raw, base, pointer)
    return _SidRecord(sid=sid, attributes=attributes)


def _parse_security_descriptor(raw: bytes) -> _SecurityDescriptor:
    if len(raw) < 20:
        _raise("observation_failed")
    (
        revision,
        reserved,
        control,
        owner_offset,
        group_offset,
        sacl_offset,
        dacl_offset,
    ) = struct.unpack_from("<BBHIIII", raw, 0)
    if revision != 1 or reserved != 0 or not (control & _SE_SELF_RELATIVE):
        _raise("observation_failed")
    if sacl_offset != 0:
        _raise("unsupported_security")
    if (
        owner_offset == 0
        or group_offset == 0
        or dacl_offset == 0
        or not (control & _SE_DACL_PRESENT)
    ):
        _raise("unsupported_security")
    for offset in (owner_offset, group_offset, dacl_offset):
        if offset < 20 or offset % 4 or offset >= len(raw):
            _raise("observation_failed")

    owner, owner_interval = _parse_sid(raw, owner_offset)
    group, group_interval = _parse_sid(raw, group_offset)
    if (
        owner_interval[0] <= dacl_offset < owner_interval[1]
        or group_interval[0] <= dacl_offset < group_interval[1]
    ):
        _raise("observation_failed")

    if dacl_offset + 8 > len(raw):
        _raise("observation_failed")
    acl_revision, acl_reserved, acl_size, ace_count, acl_reserved_word = (
        struct.unpack_from("<BBHHH", raw, dacl_offset)
    )
    if acl_revision not in {2, 4}:
        _raise("unsupported_security")
    if acl_reserved != 0 or acl_reserved_word != 0:
        _raise("observation_failed")
    if (
        acl_size < 8
        or dacl_offset + acl_size > len(raw)
        or ace_count > _MAX_TOKEN_RECORDS
    ):
        _raise("observation_failed")
    dacl_end = dacl_offset + acl_size
    cursor = dacl_offset + 8
    aces: list[_Ace] = []
    for _index in range(ace_count):
        if cursor + 8 > dacl_end:
            _raise("observation_failed")
        ace_type, flags, ace_size, mask = struct.unpack_from("<BBHI", raw, cursor)
        if ace_type not in {_ACCESS_ALLOWED_ACE_TYPE, _ACCESS_DENIED_ACE_TYPE}:
            _raise("unsupported_security")
        if flags & ~_ORDINARY_ACE_FLAG_MASK:
            _raise("unsupported_security")
        if ace_size < 8 or cursor + ace_size > dacl_end:
            _raise("observation_failed")
        sid, sid_interval = _parse_sid(raw, cursor + 8)
        if sid_interval[1] != cursor + ace_size:
            _raise("observation_failed")
        aces.append(_Ace(ace_type=ace_type, flags=flags, mask=mask, sid=sid))
        cursor += ace_size
    if any(raw[cursor:dacl_end]):
        _raise("observation_failed")
    dacl_interval = (dacl_offset, dacl_end)

    components = (
        ("owner", owner_interval),
        ("group", group_interval),
        ("dacl", dacl_interval),
    )
    for left_index, (left_name, left_interval) in enumerate(components):
        for right_name, right_interval in components[left_index + 1 :]:
            overlaps = (
                left_interval[0] < right_interval[1]
                and right_interval[0] < left_interval[1]
            )
            if not overlaps:
                continue
            owner_group_alias = (
                {left_name, right_name} == {"owner", "group"}
                and left_interval == right_interval
                and owner.binary == group.binary
            )
            if not owner_group_alias:
                _raise("observation_failed")

    intervals = sorted(set((owner_interval, group_interval, dacl_interval)))
    cursor = 20
    for start, end in intervals:
        if start < cursor or any(raw[cursor:start]):
            _raise("observation_failed")
        cursor = end
    if any(raw[cursor:]):
        _raise("observation_failed")
    return _SecurityDescriptor(
        control=control,
        owner=owner,
        group=group,
        dacl_revision=acl_revision,
        aces=tuple(aces),
    )


def _file_generic_mapping() -> _GENERIC_MAPPING:
    return _GENERIC_MAPPING(*_FILE_GENERIC_MAPPING_VALUES)


def _mapped_mask(native: _NativeApi, raw_mask: int) -> int:
    value = _DWORD(raw_mask)
    mapping = _file_generic_mapping()
    try:
        native.advapi32.MapGenericMask(
            ctypes.byref(value),
            ctypes.byref(mapping),
        )
    except Exception:
        _raise("observation_failed")
    return int(value.value)


def _validate_anchor_policy(
    native: _NativeApi,
    descriptor: _SecurityDescriptor,
) -> None:
    if (
        descriptor.control != (_SE_SELF_RELATIVE | _SE_DACL_PRESENT)
        or descriptor.owner.binary not in {_SYSTEM_SID, _ADMIN_SID}
        or descriptor.group.binary not in {_SYSTEM_SID, _ADMIN_SID}
    ):
        _raise("security_policy_mismatch")
    for ace in descriptor.aces:
        if (
            ace.ace_type == _ACCESS_ALLOWED_ACE_TYPE
            and not (ace.flags & _INHERIT_ONLY_ACE)
            and ace.sid.binary not in {_SYSTEM_SID, _ADMIN_SID}
            and _mapped_mask(native, ace.mask) & _DANGEROUS_DIRECTORY_MASK
        ):
            _raise("security_policy_mismatch")


def _validate_dedicated_policy(
    descriptor: _SecurityDescriptor,
    *,
    pin: bool,
) -> _Sid:
    reader_mask = 0x00120089 if pin else 0x001200A1
    if (
        descriptor.control
        != (_SE_SELF_RELATIVE | _SE_DACL_PROTECTED | _SE_DACL_PRESENT)
        or descriptor.owner.binary != _ADMIN_SID
        or descriptor.group.binary != _ADMIN_SID
        or descriptor.dacl_revision != 2
        or len(descriptor.aces) != 3
    ):
        _raise("security_policy_mismatch")
    expected = (
        (_SYSTEM_SID, 0x001F01FF),
        (_ADMIN_SID, 0x001F01FF),
        (descriptor.aces[2].sid.binary, reader_mask),
    )
    for ace, (sid, mask) in zip(descriptor.aces, expected):
        if (
            ace.ace_type != _ACCESS_ALLOWED_ACE_TYPE
            or ace.flags != 0
            or ace.mask != mask
            or ace.sid.binary != sid
        ):
            _raise("security_policy_mismatch")
    if len({ace.sid.binary for ace in descriptor.aces}) != 3:
        _raise("security_policy_mismatch")
    return descriptor.aces[2].sid


def _token_snapshot(native: _NativeApi, handle: int) -> _TokenSnapshot:
    before = _query_statistics(native, handle)
    user_raw, user_base = _query_variable_token(native, handle, _TOKEN_USER_CLASS)
    user_sid = _parse_token_user(user_raw, user_base)
    groups_raw, groups_base = _query_variable_token(native, handle, _TOKEN_GROUPS_CLASS)
    groups = _parse_sid_records(groups_raw, groups_base)
    privileges_raw, _privileges_base = _query_variable_token(
        native, handle, _TOKEN_PRIVILEGES_CLASS
    )
    privileges = _parse_privileges(privileges_raw)
    restricted_raw, restricted_base = _query_variable_token(
        native, handle, _TOKEN_RESTRICTED_SIDS_CLASS
    )
    restricted = _parse_sid_records(restricted_raw, restricted_base)
    elevation_type = _query_fixed_value(
        native, handle, _TOKEN_ELEVATION_TYPE_CLASS, (1, 2, 3)
    )
    is_elevated = _query_fixed_value(
        native, handle, _TOKEN_ELEVATION_CLASS, (0, 1)
    )
    has_restrictions = _query_fixed_value(
        native, handle, _TOKEN_HAS_RESTRICTIONS_CLASS, (0, 1)
    )
    integrity_raw, integrity_base = _query_variable_token(
        native, handle, _TOKEN_INTEGRITY_LEVEL_CLASS
    )
    integrity = _parse_integrity(integrity_raw, integrity_base)
    ui_access = _query_fixed_value(native, handle, _TOKEN_UI_ACCESS_CLASS, (0, 1))
    is_app_container = _query_fixed_value(
        native, handle, _TOKEN_IS_APP_CONTAINER_CLASS, (0, 1)
    )
    after = _query_statistics(native, handle)
    if (
        before != after
        or before.group_count != len(groups)
        or before.privilege_count != len(privileges)
    ):
        _raise("observation_failed")
    return _TokenSnapshot(
        statistics=before,
        user_sid=user_sid,
        groups=groups,
        privileges=privileges,
        restricted_sids=restricted,
        elevation_type=elevation_type,
        is_elevated=bool(is_elevated),
        has_restrictions=bool(has_restrictions),
        integrity=integrity,
        ui_access=bool(ui_access),
        is_app_container=bool(is_app_container),
    )


def _resolve_change_notify_luid(native: _NativeApi) -> int:
    value = _LUID()
    try:
        succeeded = native.advapi32.LookupPrivilegeValueW(
            None,
            "SeChangeNotifyPrivilege",
            ctypes.byref(value),
        )
        if not succeeded:
            _last_error()
            _raise("observation_failed")
    except ExternalPinReaderError:
        raise
    except Exception:
        _raise("observation_failed")
    return _luid_value(value)


def _intrinsically_validate_token(
    snapshot: _TokenSnapshot,
    change_notify_luid: int,
) -> None:
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
        _raise("untrusted_reader")
    for record in snapshot.groups:
        if record.sid.binary == _ADMIN_SID and (
            not (record.attributes & _SE_GROUP_USE_FOR_DENY_ONLY)
            or (record.attributes & _SE_GROUP_ENABLED)
        ):
            _raise("untrusted_reader")
    for record in snapshot.privileges:
        if (
            record.attributes & _SE_PRIVILEGE_ENABLED
            and record.luid != change_notify_luid
        ):
            _raise("untrusted_reader")


def _open_baseline_token(
    native: _NativeApi,
    baseline: _OwnedNativeHandle,
) -> None:
    thread_owner = _OwnedNativeHandle(None)
    try:
        thread_result = native.advapi32.OpenThreadToken(
            native.kernel32.GetCurrentThread(),
            _TOKEN_QUERY,
            1,
            thread_owner.output_pointer(),
        )
        if not thread_result:
            thread_error = _last_error()
            thread_owner.value = None
        else:
            thread_error = 0
    except BaseException as error:
        cleanup = _close_native_handle(native, thread_owner)
        _raise_after_cleanup(error, cleanup)
    if thread_result:
        if thread_owner.value is None:
            _raise("observation_failed")
        cleanup = _close_native_handle(native, thread_owner)
        _raise_after_cleanup(ExternalPinReaderError("untrusted_reader"), cleanup)
    if thread_error != _ERROR_NO_TOKEN:
        _raise("observation_failed")

    try:
        process_result = native.advapi32.OpenProcessToken(
            native.kernel32.GetCurrentProcess(),
            _TOKEN_QUERY | _TOKEN_DUPLICATE,
            baseline.output_pointer(),
        )
        if not process_result:
            _last_error()
            baseline.value = None
            _raise("observation_failed")
    except BaseException as error:
        cleanup = _close_native_handle(native, baseline)
        _raise_after_cleanup(error, cleanup)
    if baseline.value is None:
        _raise("observation_failed")


def _compare_effective_token(
    native: _NativeApi,
    baseline: _TokenSnapshot,
) -> None:
    owned_thread = _OwnedNativeHandle(None)
    try:
        thread_result = native.advapi32.OpenThreadToken(
            native.kernel32.GetCurrentThread(),
            _TOKEN_QUERY,
            1,
            owned_thread.output_pointer(),
        )
        if not thread_result:
            thread_error = _last_error()
            owned_thread.value = None
        else:
            thread_error = 0
    except BaseException as error:
        cleanup = _close_native_handle(native, owned_thread)
        _raise_after_cleanup(error, cleanup)
    if thread_result:
        if owned_thread.value is None:
            _raise("observation_failed")
        cleanup = _close_native_handle(native, owned_thread)
        _raise_after_cleanup(ExternalPinReaderError("observation_raced"), cleanup)
    if thread_error != _ERROR_NO_TOKEN:
        _raise("observation_failed")

    owned_process = _OwnedNativeHandle(None)
    try:
        process_result = native.advapi32.OpenProcessToken(
            native.kernel32.GetCurrentProcess(),
            _TOKEN_QUERY,
            owned_process.output_pointer(),
        )
        if not process_result:
            _last_error()
            owned_process.value = None
            _raise("observation_failed")
    except BaseException as error:
        cleanup = _close_native_handle(native, owned_process)
        _raise_after_cleanup(error, cleanup)
    if owned_process.value is None:
        _raise("observation_failed")
    primary: BaseException | None = None
    try:
        current = _token_snapshot(native, owned_process.value)
        if current != baseline:
            _raise("observation_raced")
    except BaseException as error:
        primary = error
    cleanup = _close_native_handle(native, owned_process)
    _raise_after_cleanup(primary, cleanup)


def _reader_identity_projection(snapshot: _TokenSnapshot) -> dict[str, Any]:
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
        "schema": "goodq.clean-memory-windows-reader-identity.v1",
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


def _validate_known_folder_text(value: str) -> _KnownFolder:
    try:
        utf16_units = len(value.encode("utf-16-le")) // 2
    except UnicodeError:
        _raise("redirected_boundary")
    if (
        not value
        or utf16_units > 32767
        or unicodedata.normalize("NFC", value) != value
        or len(value) < 4
        or not ("A" <= value[0] <= "Z")
        or value[1:3] != ":\\"
        or value.endswith("\\")
        or "/" in value
        or "%" in value
    ):
        _raise("redirected_boundary")
    components = tuple(value[3:].split("\\"))
    if not components or len(components) > 64:
        _raise("redirected_boundary")
    for component in components:
        if (
            not component
            or component in {".", ".."}
            or component.endswith((".", " "))
            or ":" in component
            or any(ord(character) < 32 or ord(character) == 127 for character in component)
        ):
            _raise("redirected_boundary")
    return _KnownFolder(root=value[:3], components=components)


def _resolve_known_folder(native: _NativeApi) -> _KnownFolder:
    cleanup_fallback = ExternalPinReaderError("observation_failed")
    processing_fallback = ExternalPinReaderError("observation_failed")
    primary_fallback = ExternalPinReaderError("observation_failed")
    data4 = (_BYTE * 8)(*_PROGRAM_DATA_GUID_FIELDS[3])
    guid = _GUID(
        _PROGRAM_DATA_GUID_FIELDS[0],
        _PROGRAM_DATA_GUID_FIELDS[1],
        _PROGRAM_DATA_GUID_FIELDS[2],
        data4,
    )
    output = _PVOID()
    primary: BaseException | None = None
    result: _KnownFolder | None = None
    try:
        hresult = int(
            native.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid),
                0,
                None,
                ctypes.byref(output),
            )
        )
        if hresult < 0 or output.value is None:
            _raise("observation_failed")
        text = ctypes.wstring_at(output.value)
        result = _validate_known_folder_text(text)
    except BaseException as error:
        primary = error
    raw_cleanup: BaseException | None = None
    if output.value is not None:
        try:
            native.ole32.CoTaskMemFree(_PVOID(output.value))
        except BaseException as error:
            raw_cleanup = error
    cleanup = (
        _sanitize_cleanup_chain(
            raw_cleanup,
            cleanup_fallback=cleanup_fallback,
            processing_fallback=processing_fallback,
        )
        if raw_cleanup is not None
        else None
    )
    _raise_after_cleanup(primary, cleanup, fallback=primary_fallback)
    if result is None:
        _raise("observation_failed")
    return result


def _enumerate_entries(
    backend: object,
    handle: object,
    filesystem: str,
) -> tuple[WindowsDirectoryEntry, ...]:
    entries: object | None = None
    failure: ExternalPinReaderError | None = None
    try:
        entries = backend.enumerate_directory(handle, filesystem)
    except Exception as error:
        failure = _sanitize_error(error)
    if failure is not None:
        raise failure from failure.__cause__
    if type(entries) is not tuple or any(
        type(entry) is not WindowsDirectoryEntry for entry in entries
    ):
        _raise("observation_failed")
    return entries


def _snapshot_object(
    backend: object,
    item: _HeldObject,
    filesystem: str,
) -> WindowsObjectSnapshot:
    snapshot: object | None = None
    failure: ExternalPinReaderError | None = None
    try:
        snapshot = backend.snapshot(
            item.handle,
            filesystem=filesystem,
            expected=item.entry,
            object_kind=item.object_kind,
            require_stream_contract=True,
        )
    except Exception as error:
        failure = _sanitize_error(error)
    if failure is not None:
        raise failure from failure.__cause__
    if type(snapshot) is not WindowsObjectSnapshot:
        _raise("observation_failed")
    return snapshot


def _acquire_root(state: _ReadState, root_path: str) -> None:
    _compare_effective_token(state.native, state.baseline_snapshot)
    failure: ExternalPinReaderError | None = None
    try:
        handle = state.backend.open_root(root_path)
        root = _HeldObject(
            role="root",
            handle=handle,
            entry=None,
            snapshot=WindowsObjectSnapshot(0, "", 0, "directory", 0, None, 0, 0, 0, 0, 0, 0, ()),
            object_kind="directory",
        )
        state.held.append(root)
        filesystem = state.backend.volume_filesystem(handle)
        if filesystem not in {"NTFS", "ReFS"}:
            _raise("unsupported_filesystem")
        state.filesystem = filesystem
        snapshot = _snapshot_object(state.backend, root, filesystem)
        state.root = _HeldObject(
            role="root",
            handle=handle,
            entry=None,
            snapshot=snapshot,
            object_kind="directory",
        )
        state.held[0] = state.root
    except ExternalPinReaderError:
        raise
    except Exception as error:
        failure = _sanitize_error(error)
    if failure is not None:
        raise failure from failure.__cause__
    _compare_effective_token(state.native, state.baseline_snapshot)


def _matching_entries(
    entries: tuple[WindowsDirectoryEntry, ...],
    component: str,
) -> tuple[WindowsDirectoryEntry, ...]:
    key = unicodedata.normalize("NFC", component).casefold()
    return tuple(
        entry
        for entry in entries
        if unicodedata.normalize("NFC", entry.name).casefold() == key
    )


def _select_child(
    state: _ReadState,
    parent: _HeldObject,
    component: str,
    role: str,
    *,
    directory: bool,
) -> _HeldObject:
    if state.root is None or state.filesystem is None:
        _raise("observation_failed")
    _compare_effective_token(state.native, state.baseline_snapshot)
    entries = _enumerate_entries(state.backend, parent.handle, state.filesystem)
    matches = _matching_entries(entries, component)
    if len(matches) > 1:
        _raise("duplicate_identity")
    if not matches:
        before = _snapshot_object(state.backend, parent, state.filesystem)
        first_proof = _enumerate_entries(
            state.backend,
            parent.handle,
            state.filesystem,
        )
        second_proof = _enumerate_entries(
            state.backend,
            parent.handle,
            state.filesystem,
        )
        after = _snapshot_object(state.backend, parent, state.filesystem)
        _compare_effective_token(state.native, state.baseline_snapshot)
        if (
            before != after
            or entries != first_proof
            or entries != second_proof
            or _matching_entries(first_proof, component)
            or _matching_entries(second_proof, component)
        ):
            _raise("observation_raced")
        _raise("pin_missing")
    entry = matches[0]
    if entry.is_reparse:
        _raise("redirected_boundary")
    if entry.is_device or entry.is_directory != directory:
        _raise("unexpected_entry_type")
    handle: object | None = None
    failure: ExternalPinReaderError | None = None
    try:
        handle = state.backend.open_by_id(
            state.root.handle,
            entry,
            directory=directory,
        )
    except Exception as error:
        failure = _sanitize_error(error)
    if failure is not None:
        raise failure from failure.__cause__
    provisional = _HeldObject(
        role=role,
        handle=handle,
        entry=entry,
        snapshot=state.root.snapshot,
        object_kind="directory" if directory else "regular_file",
    )
    state.held.append(provisional)
    snapshot = _snapshot_object(state.backend, provisional, state.filesystem)
    if snapshot.volume_serial != state.root.snapshot.volume_serial:
        _raise("redirected_boundary")
    selected = _HeldObject(
        role=role,
        handle=handle,
        entry=entry,
        snapshot=snapshot,
        object_kind=provisional.object_kind,
    )
    state.held[-1] = selected
    state.parents.append(
        _ParentMembership(role=parent.role, handle=parent.handle, entries=entries)
    )
    _compare_effective_token(state.native, state.baseline_snapshot)
    return selected


def _read_and_pin_descriptor(
    state: _ReadState,
    held: _HeldObject,
) -> _PinnedDescriptor:
    raw: object | None = None
    failure: ExternalPinReaderError | None = None
    try:
        raw = state.backend.read_security_descriptor(held.handle)
    except Exception as error:
        failure = _sanitize_error(error)
    if failure is not None:
        raise failure from failure.__cause__
    if type(raw) is not bytes or not raw:
        _raise("observation_failed")
    storage = (_BYTE * len(raw)).from_buffer_copy(raw)
    pinned = bytes(storage)
    parsed = _parse_security_descriptor(pinned)
    return _PinnedDescriptor(
        held=held,
        raw=pinned,
        storage=storage,
        address=ctypes.addressof(storage),
        parsed=parsed,
    )


def _observe_descriptor(
    state: _ReadState,
    held: _HeldObject,
    *,
    anchor: bool,
    pin: bool = False,
) -> tuple[_PinnedDescriptor, _Sid | None]:
    _compare_effective_token(state.native, state.baseline_snapshot)
    pinned = _read_and_pin_descriptor(state, held)
    reader: _Sid | None = None
    if anchor:
        _validate_anchor_policy(state.native, pinned.parsed)
    else:
        reader = _validate_dedicated_policy(pinned.parsed, pin=pin)
    _compare_effective_token(state.native, state.baseline_snapshot)
    return pinned, reader


def _ace_projection(ace: _Ace) -> dict[str, str]:
    return {
        "flags": f"{ace.flags:02x}",
        "mask": f"{ace.mask:08x}",
        "sid": ace.sid.numeric,
        "type": (
            "access_allowed"
            if ace.ace_type == _ACCESS_ALLOWED_ACE_TYPE
            else "access_denied"
        ),
    }


def _denied_access_projection(
    rights: tuple[tuple[str, int], ...],
) -> list[dict[str, object]]:
    return [
        {"denied": True, "mask": f"{mask:08x}", "name": name}
        for name, mask in rights
    ]


def _descriptor_projection(
    pinned: _PinnedDescriptor,
    *,
    role: str,
    rights: tuple[tuple[str, int], ...],
) -> dict[str, object]:
    descriptor = pinned.parsed
    return {
        "dacl": [_ace_projection(ace) for ace in descriptor.aces],
        "dacl_revision": descriptor.dacl_revision,
        "denied_access_checks": _denied_access_projection(rights),
        "descriptor_control": f"{descriptor.control:04x}",
        "owner_sid": descriptor.owner.numeric,
        "physical_identity": pinned.held.snapshot.identity_projection,
        "primary_group_sid": descriptor.group.numeric,
        "role": role,
    }


def _duplicate_access_token(
    state: _ReadState,
    duplicate: _OwnedNativeHandle,
) -> None:
    if state.baseline.value is None:
        _raise("observation_failed")
    try:
        succeeded = state.native.advapi32.DuplicateTokenEx(
            _HANDLE(state.baseline.value),
            _TOKEN_QUERY,
            None,
            _SECURITY_IMPERSONATION,
            _TOKEN_IMPERSONATION,
            duplicate.output_pointer(),
        )
        if not succeeded:
            _last_error()
            duplicate.value = None
            _raise("observation_failed")
    except BaseException as error:
        cleanup = _close_native_handle(state.native, duplicate)
        _raise_after_cleanup(error, cleanup)
    if duplicate.value is None:
        _raise("observation_failed")


def _validate_privilege_output(
    storage: Any,
    returned_length: int,
    capacity: int,
    accepted_count: int,
) -> tuple[int, int]:
    if returned_length < 8 or returned_length > capacity:
        _raise("observation_failed")
    raw = bytes(storage[:returned_length])
    privilege_count, control = struct.unpack_from("<II", raw, 0)
    if (
        privilege_count > _MAX_TOKEN_RECORDS
        or privilege_count > accepted_count
        or control & ~_PRIVILEGE_SET_ALL_NECESSARY
    ):
        _raise("observation_failed")
    records_end = 8 + 12 * privilege_count
    if records_end > returned_length or any(raw[records_end:]):
        _raise("observation_failed")
    return privilege_count, control


def _check_denied_right(
    state: _ReadState,
    pinned: _PinnedDescriptor,
    duplicate: int,
    raw_mask: int,
) -> None:
    desired = _DWORD(raw_mask)
    mapping = _file_generic_mapping()
    try:
        state.native.advapi32.MapGenericMask(
            ctypes.byref(desired),
            ctypes.byref(mapping),
        )
    except Exception:
        _raise("observation_failed")
    mapped = int(desired.value)
    accepted_count = state.baseline_snapshot.statistics.privilege_count
    capacity = 8 + 12 * max(1, accepted_count)
    if capacity > 49_160:
        _raise("observation_failed")
    privilege_storage = (_BYTE * capacity)()
    ctypes.memset(ctypes.addressof(privilege_storage), 0, capacity)
    privilege_length = _DWORD(capacity)
    granted = _DWORD(0xFFFFFFFF)
    access_status = _BOOL(-1)
    try:
        succeeded = state.native.advapi32.AccessCheck(
            _PVOID(pinned.address),
            _HANDLE(duplicate),
            mapped,
            ctypes.byref(mapping),
            ctypes.cast(privilege_storage, _PVOID),
            ctypes.byref(privilege_length),
            ctypes.byref(granted),
            ctypes.byref(access_status),
        )
        if not succeeded:
            _last_error()
            _raise("observation_failed")
    except ExternalPinReaderError:
        raise
    except Exception:
        _raise("observation_failed")
    status = int(access_status.value)
    if status not in {0, 1}:
        _raise("observation_failed")
    privilege_count, control = _validate_privilege_output(
        privilege_storage,
        int(privilege_length.value),
        capacity,
        accepted_count,
    )
    granted_mask = int(granted.value)
    if (
        status == 0
        and granted_mask == 0
        and privilege_count == 0
        and control == 0
    ):
        return
    if status == 1 and granted_mask == mapped:
        _raise("security_policy_mismatch")
    _raise("observation_failed")


def _check_effective_access(
    state: _ReadState,
    pinned: _PinnedDescriptor,
    rights: tuple[tuple[str, int], ...],
) -> None:
    _compare_effective_token(state.native, state.baseline_snapshot)
    duplicate = _OwnedNativeHandle(None)
    primary: BaseException | None = None
    try:
        _duplicate_access_token(state, duplicate)
        if duplicate.value is None:
            _raise("observation_failed")
        for _name, mask in rights:
            _check_denied_right(state, pinned, duplicate.value, mask)
    except BaseException as error:
        primary = error
    cleanup = _close_native_handle(state.native, duplicate)
    _raise_after_cleanup(primary, cleanup)
    _compare_effective_token(state.native, state.baseline_snapshot)


def _validate_pin_snapshot(snapshot: WindowsObjectSnapshot) -> None:
    if (
        snapshot.object_kind != "regular_file"
        or snapshot.size_bytes != 65
        or snapshot.link_count != 1
        or snapshot.reparse_tag != 0
        or snapshot.streams
        != (("::$DATA", 65, snapshot.allocation_size),)
    ):
        _raise("observation_failed")


def _read_pin_payload(
    state: _ReadState,
    pin: _HeldObject,
) -> str:
    _compare_effective_token(state.native, state.baseline_snapshot)
    result: object | None = None
    failure: ExternalPinReaderError | None = None
    try:
        result = state.backend.read_file_bounded(
            pin.handle,
            maximum_bytes=66,
        )
    except Exception as error:
        failure = _sanitize_error(error)
    if failure is not None:
        raise failure from failure.__cause__
    if (
        type(result) is not tuple
        or len(result) != 2
        or type(result[0]) is not bytes
        or type(result[1]) is not bool
    ):
        _raise("observation_failed")
    payload, explicit_eof = result
    repeated = _snapshot_object(state.backend, pin, state.filesystem or "")
    _compare_effective_token(state.native, state.baseline_snapshot)
    if repeated != pin.snapshot:
        _raise("observation_raced")
    hexadecimal = b"0123456789abcdef"
    if (
        not explicit_eof
        or len(payload) != 65
        or payload[64:] != b"\n"
        or any(value not in hexadecimal for value in payload[:64])
    ):
        _raise("malformed_pin")
    try:
        return payload[:64].decode("ascii")
    except UnicodeError:
        _raise("malformed_pin")


def _final_authority_recheck(
    state: _ReadState,
    descriptors: tuple[_PinnedDescriptor, ...],
) -> None:
    if state.filesystem is None:
        _raise("observation_failed")
    _compare_effective_token(state.native, state.baseline_snapshot)
    raced = False
    for pinned in descriptors:
        current: object | None = None
        failure: ExternalPinReaderError | None = None
        try:
            current = state.backend.read_security_descriptor(pinned.held.handle)
        except Exception as error:
            failure = _sanitize_error(error)
        if failure is not None:
            raise failure from failure.__cause__
        if type(current) is not bytes:
            _raise("observation_failed")
        if current != pinned.raw:
            raced = True
    for held in state.held:
        current_snapshot = _snapshot_object(state.backend, held, state.filesystem)
        if current_snapshot != held.snapshot:
            raced = True
    for parent in state.parents:
        current_entries = _enumerate_entries(
            state.backend,
            parent.handle,
            state.filesystem,
        )
        if current_entries != parent.entries:
            raced = True
    _compare_effective_token(state.native, state.baseline_snapshot)
    if raced:
        _raise("observation_raced")


def _security_policy_projection(
    anchor: _PinnedDescriptor,
    dedicated: tuple[_PinnedDescriptor, ...],
    enrolled_reader: _Sid,
) -> dict[str, object]:
    roles = (
        "goodq_directory",
        "authority_directory",
        "clean_memory_directory",
        "pin_file",
    )
    return {
        "anchor": _descriptor_projection(
            anchor,
            role="program_data_anchor",
            rights=_DIRECTORY_RIGHTS,
        ),
        "dedicated_objects": [
            _descriptor_projection(
                descriptor,
                role=role,
                rights=_PIN_RIGHTS if role == "pin_file" else _DIRECTORY_RIGHTS,
            )
            for descriptor, role in zip(dedicated, roles)
        ],
        "enrolled_reader_sid": enrolled_reader.numeric,
        "platform": "windows",
        "schema": "goodq.clean-memory-windows-pin-security-policy.v1",
    }


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
    startup_fallback = ExternalPinReaderError("observation_failed")
    startup_error: ExternalPinReaderError | None = None
    native: _NativeApi | None = None
    backend: WindowsHeldHandleBackend | None = None
    try:
        native = _bind_native()
        backend = _load_windows_backend()
    except Exception as error:
        try:
            startup_error = _sanitize_error(error)
        except BaseException:
            startup_error = startup_fallback
    if startup_error is not None:
        raise startup_error from None
    if native is None or backend is None:
        _raise("observation_failed")

    cleanup_fallback = ExternalPinReaderError("observation_failed")
    processing_fallback = ExternalPinReaderError("observation_failed")
    primary_fallback = ExternalPinReaderError("observation_failed")
    baseline: _OwnedNativeHandle | None = None
    held: list[_HeldObject] | None = None
    backend_entered = False
    primary: BaseException | None = None
    candidate: ExternalPinEvidence | None = None
    try:
        baseline = _OwnedNativeHandle(None)
        held = []
        entered_backend = backend.__enter__()
        backend_entered = True
        if entered_backend is not backend:
            _raise("observation_failed")
        change_notify_luid = _resolve_change_notify_luid(native)
        _open_baseline_token(native, baseline)
        if baseline.value is None:
            _raise("observation_failed")
        baseline_snapshot = _token_snapshot(native, baseline.value)
        _intrinsically_validate_token(baseline_snapshot, change_notify_luid)

        _compare_effective_token(native, baseline_snapshot)
        known_folder = _resolve_known_folder(native)
        _compare_effective_token(native, baseline_snapshot)

        state = _ReadState(
            backend=backend,
            native=native,
            baseline=baseline,
            baseline_snapshot=baseline_snapshot,
            held=held,
        )
        _acquire_root(state, known_folder.root)
        if state.root is None:
            _raise("observation_failed")
        parent = state.root
        for index, component in enumerate(known_folder.components):
            role = (
                "anchor"
                if index == len(known_folder.components) - 1
                else f"program_data_component_{index}"
            )
            parent = _select_child(
                state,
                parent,
                component,
                role,
                directory=True,
            )
        for component, role in zip(
            _FIXED_CHILDREN,
            ("goodq", "authority", "clean_memory"),
        ):
            parent = _select_child(
                state,
                parent,
                component,
                role,
                directory=True,
            )
        held_by_role = {item.role: item for item in held}
        anchor_descriptor, _unused_anchor_reader = _observe_descriptor(
            state,
            held_by_role["anchor"],
            anchor=True,
        )
        dedicated_descriptors: list[_PinnedDescriptor] = []
        enrolled_candidates: list[_Sid] = []
        for role in ("goodq", "authority", "clean_memory"):
            descriptor, enrolled = _observe_descriptor(
                state,
                held_by_role[role],
                anchor=False,
            )
            if enrolled is None:
                _raise("observation_failed")
            dedicated_descriptors.append(descriptor)
            enrolled_candidates.append(enrolled)
        enrolled_reader = enrolled_candidates[0]
        if any(
            candidate.binary != enrolled_reader.binary
            for candidate in enrolled_candidates[1:]
        ):
            _raise("security_policy_mismatch")
        if enrolled_reader.binary != baseline_snapshot.user_sid.binary:
            _raise("untrusted_reader")
        _check_effective_access(state, anchor_descriptor, _DIRECTORY_RIGHTS)
        for descriptor in dedicated_descriptors:
            _check_effective_access(state, descriptor, _DIRECTORY_RIGHTS)

        pin = _select_child(
            state,
            held_by_role["clean_memory"],
            _PIN_NAME,
            "pin",
            directory=False,
        )
        _validate_pin_snapshot(pin.snapshot)
        pin_descriptor, pin_reader = _observe_descriptor(
            state,
            pin,
            anchor=False,
            pin=True,
        )
        if pin_reader is None:
            _raise("observation_failed")
        if pin_reader.binary != enrolled_reader.binary:
            _raise("security_policy_mismatch")
        _check_effective_access(state, pin_descriptor, _PIN_RIGHTS)

        manifest_sha256 = _read_pin_payload(state, pin)
        all_descriptors = (
            anchor_descriptor,
            *dedicated_descriptors,
            pin_descriptor,
        )
        _final_authority_recheck(state, all_descriptors)

        reader_identity_sha256 = hashlib.sha256(
            _canonical_json_bytes(_reader_identity_projection(baseline_snapshot))
        ).hexdigest()
        security_policy_sha256 = hashlib.sha256(
            _canonical_json_bytes(
                _security_policy_projection(
                    anchor_descriptor,
                    tuple((*dedicated_descriptors, pin_descriptor)),
                    enrolled_reader,
                )
            )
        ).hexdigest()
        candidate = ExternalPinEvidence._from_projection(
            {
                "anchor_identity": anchor_descriptor.held.snapshot.identity_projection,
                "dedicated_directory_identities": [
                    descriptor.held.snapshot.identity_projection
                    for descriptor in dedicated_descriptors
                ],
                "enrolled_reader_identity_sha256": reader_identity_sha256,
                "manifest_sha256": manifest_sha256,
                "pin_file_identity": pin.snapshot.identity_projection,
                "platform": "windows",
                "schema": EXTERNAL_PIN_EVIDENCE_SCHEMA,
                "security_policy_sha256": security_policy_sha256,
                "source_id": (
                    "goodq.clean-memory-protected-authority-pin.primary.v1"
                ),
                "source_schema": "goodq.clean-memory-external-pin-source.v1",
            }
        )
    except BaseException as error:
        primary = error

    backend_cleanup_error: BaseException | None = None
    if backend_entered:
        try:
            backend.__exit__(None, None, None)
        except BaseException as error:
            backend_cleanup_error = error
    baseline_cleanup = (
        _close_native_handle(native, baseline) if baseline is not None else None
    )
    cleanup: ExternalPinReaderError | None = None
    if backend_cleanup_error is not None:
        cleanup = _sanitize_cleanup_chain(
            backend_cleanup_error,
            cleanup_fallback=cleanup_fallback,
            processing_fallback=processing_fallback,
        )
    cleanup = _append_cleanup(cleanup, baseline_cleanup)
    _raise_after_cleanup(primary, cleanup, fallback=primary_fallback)
    if candidate is None:
        _raise("observation_failed")
    return candidate
