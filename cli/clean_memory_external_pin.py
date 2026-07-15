"""Read-only Windows external-pin evidence for clean-memory authority."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
import hashlib
import json
import os
import unicodedata
from typing import Any

from steps.common.windows_held_handle import (
    WindowsDirectoryEntry,
    WindowsHeldHandleBackend,
    WindowsHeldHandleError,
    WindowsObjectSnapshot,
)
from steps.common.windows_security_mechanics import (
    WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    WINDOWS_TOKEN_PROFILE_BASE,
    WindowsAce,
    WindowsPinnedSecurityDescriptor,
    WindowsSecurityDescriptor,
    WindowsSecurityMechanics,
    WindowsSecurityMechanicsError,
    WindowsSecuritySession,
    WindowsSid,
    WindowsTokenSnapshot,
    bind_windows_security,
    verify_windows_security_abi,
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
_WORD = ctypes.c_uint16
_BYTE = ctypes.c_ubyte
_HANDLE = ctypes.c_void_p
_PVOID = ctypes.c_void_p

_TOKEN_PRIMARY = 1

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
_INHERIT_ONLY_ACE = 0x08
_SE_DACL_PRESENT = 0x0004
_SE_DACL_PROTECTED = 0x1000
_SE_SELF_RELATIVE = 0x8000
_DANGEROUS_DIRECTORY_MASK = 0x00000040 | 0x00040000 | 0x00080000


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", _DWORD),
        ("Data2", _WORD),
        ("Data3", _WORD),
        ("Data4", _BYTE * 8),
    ]


@dataclass(frozen=True)
class _NativeApi:
    shell32: object
    ole32: object
    security: WindowsSecurityMechanics


@dataclass(frozen=True)
class _PinnedDescriptor:
    held: _HeldObject
    raw: bytes
    security: WindowsPinnedSecurityDescriptor


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
    session: WindowsSecuritySession
    baseline_snapshot: WindowsTokenSnapshot
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


def _security_error_code(
    error: WindowsSecurityMechanicsError,
    *,
    phase: str,
) -> str:
    if error.code == "thread_token_present":
        if phase == "baseline":
            return "untrusted_reader"
        if phase == "recheck":
            return "observation_raced"
        return "observation_failed"
    if error.code in {"unsupported_security", "unsupported_descriptor"}:
        return "unsupported_security"
    return "observation_failed"


def _translate_security_error_graph(
    error: WindowsSecurityMechanicsError,
    *,
    phase: str,
) -> ExternalPinReaderError:
    memo: list[tuple[int, ExternalPinReaderError]] = []
    visiting: list[int] = []

    def clone(node: BaseException, remaining: int) -> ExternalPinReaderError:
        identity = id(node)
        if remaining <= 0 or identity in visiting:
            return ExternalPinReaderError("observation_failed")
        for known_identity, known_error in memo:
            if identity == known_identity:
                return known_error
        if isinstance(node, WindowsSecurityMechanicsError):
            code = _security_error_code(node, phase=phase)
        else:
            code = "observation_failed"
        public = ExternalPinReaderError(code)
        memo.append((identity, public))
        visiting.append(identity)
        cause = node.__cause__
        context = node.__context__
        if cause is not None:
            public.__cause__ = clone(cause, remaining - 1)
        if context is not None:
            public.__context__ = clone(context, remaining - 1)
        public.__suppress_context__ = bool(node.__suppress_context__)
        del visiting[-1]
        return public

    return clone(error, 256)


def _sanitize_control_links(
    error: BaseException,
    *,
    phase: str,
    fallback: ExternalPinReaderError,
) -> None:
    raw_cause = error.__cause__
    raw_context = error.__context__
    suppress_context = bool(error.__suppress_context__)
    public_cause = raw_cause
    public_context = raw_context

    cause_is_security = isinstance(raw_cause, WindowsSecurityMechanicsError)
    context_is_security = isinstance(raw_context, WindowsSecurityMechanicsError)
    if cause_is_security or context_is_security:
        try:
            wrapper = WindowsSecurityMechanicsError("observation_failed")
            if cause_is_security:
                wrapper.__cause__ = raw_cause
            if context_is_security:
                wrapper.__context__ = raw_context
            wrapper.__suppress_context__ = False
            translated = _translate_security_error_graph(wrapper, phase=phase)
            if cause_is_security:
                candidate = translated.__cause__
                public_cause = (
                    candidate
                    if type(candidate) is ExternalPinReaderError
                    else fallback
                )
            if context_is_security:
                candidate = translated.__context__
                public_context = (
                    candidate
                    if type(candidate) is ExternalPinReaderError
                    else fallback
                )
        except BaseException:
            if cause_is_security:
                public_cause = fallback
            if context_is_security:
                public_context = public_cause if raw_context is raw_cause else fallback

    if isinstance(raw_cause, WindowsHeldHandleError):
        try:
            public_cause = _sanitize_error(raw_cause)
        except BaseException:
            public_cause = fallback
    if isinstance(raw_context, WindowsHeldHandleError):
        if raw_context is raw_cause:
            public_context = public_cause
        else:
            try:
                public_context = _sanitize_error(raw_context)
            except BaseException:
                public_context = fallback

    error.__cause__ = public_cause
    error.__context__ = public_context
    error.__suppress_context__ = suppress_context


def _raise_security_failure(error: BaseException, *, phase: str) -> None:
    if isinstance(error, WindowsSecurityMechanicsError):
        public = _translate_security_error_graph(error, phase=phase)
        _reraise_preserving_graph(public)
    if isinstance(error, Exception):
        _raise("observation_failed")
    fallback = ExternalPinReaderError("observation_failed")
    _sanitize_control_links(error, phase=phase, fallback=fallback)
    _reraise_preserving_graph(error)


def _reraise_preserving_graph(error: BaseException) -> None:
    traceback = error.__traceback__
    cause = error.__cause__
    context = error.__context__
    suppress_context = bool(error.__suppress_context__)
    try:
        raise error.with_traceback(traceback)
    except BaseException:
        error.__cause__ = cause
        error.__context__ = context
        error.__suppress_context__ = suppress_context
        raise


def _sanitize_error(error: BaseException) -> ExternalPinReaderError:
    if type(error) is ExternalPinReaderError:
        if _is_sanitized_public_error_graph(error):
            return error
        return _clone_public_error(error)
    if isinstance(error, WindowsHeldHandleError):
        return _sanitize_windows_error_graph(error)
    if isinstance(error, WindowsSecurityMechanicsError):
        return _translate_security_error_graph(error, phase="observation")
    return ExternalPinReaderError("observation_failed")


def _raise_collected(
    primary: ExternalPinReaderError | None,
    cleanup: ExternalPinReaderError | None,
) -> None:
    if primary is None:
        if cleanup is not None:
            _reraise_preserving_graph(cleanup)
        return
    _attach_cleanup(primary, cleanup)
    _reraise_preserving_graph(primary)


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
    control_fallback = fallback or ExternalPinReaderError("observation_failed")
    _sanitize_control_links(
        primary,
        phase="cleanup",
        fallback=control_fallback,
    )
    _attach_cleanup(primary, cleanup)
    _reraise_preserving_graph(primary)


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


def _verify_win64_layouts() -> None:
    if ctypes.sizeof(_GUID) != 16:
        _raise("unsupported_security")
    try:
        verify_windows_security_abi()
    except WindowsSecurityMechanicsError:
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
        security = bind_windows_security(
            kernel32=kernel32,
            advapi32=advapi32,
        )
    except WindowsSecurityMechanicsError:
        _raise("unsupported_security")

    return _NativeApi(
        shell32=shell32,
        ole32=ole32,
        security=security,
    )


def _validate_anchor_policy(
    security: WindowsSecurityMechanics,
    descriptor: WindowsSecurityDescriptor,
) -> None:
    if (
        descriptor.control != (_SE_SELF_RELATIVE | _SE_DACL_PRESENT)
        or descriptor.owner.binary not in {_SYSTEM_SID, _ADMIN_SID}
        or descriptor.group.binary not in {_SYSTEM_SID, _ADMIN_SID}
    ):
        _raise("security_policy_mismatch")
    for ace in descriptor.dacl_aces:
        if (
            ace.ace_type == _ACCESS_ALLOWED_ACE_TYPE
            and not (ace.flags & _INHERIT_ONLY_ACE)
            and ace.sid.binary not in {_SYSTEM_SID, _ADMIN_SID}
            and security.map_file_mask(ace.mask) & _DANGEROUS_DIRECTORY_MASK
        ):
            _raise("security_policy_mismatch")


def _validate_dedicated_policy(
    descriptor: WindowsSecurityDescriptor,
    *,
    pin: bool,
) -> WindowsSid:
    reader_mask = 0x00120089 if pin else 0x001200A1
    if (
        descriptor.control
        != (_SE_SELF_RELATIVE | _SE_DACL_PROTECTED | _SE_DACL_PRESENT)
        or descriptor.owner.binary != _ADMIN_SID
        or descriptor.group.binary != _ADMIN_SID
        or descriptor.dacl_revision != 2
        or len(descriptor.dacl_aces) != 3
    ):
        _raise("security_policy_mismatch")
    expected = (
        (_SYSTEM_SID, 0x001F01FF),
        (_ADMIN_SID, 0x001F01FF),
        (descriptor.dacl_aces[2].sid.binary, reader_mask),
    )
    for ace, (sid, mask) in zip(descriptor.dacl_aces, expected):
        if (
            ace.ace_type != _ACCESS_ALLOWED_ACE_TYPE
            or ace.flags != 0
            or ace.mask != mask
            or ace.sid.binary != sid
        ):
            _raise("security_policy_mismatch")
    if len({ace.sid.binary for ace in descriptor.dacl_aces}) != 3:
        _raise("security_policy_mismatch")
    return descriptor.dacl_aces[2].sid


def _intrinsically_validate_token(
    snapshot: WindowsTokenSnapshot,
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


def _compare_effective_token(
    session: WindowsSecuritySession,
    baseline: WindowsTokenSnapshot,
) -> None:
    try:
        current = session.observe_effective()
    except BaseException as error:
        _raise_security_failure(error, phase="recheck")
    if current != baseline:
        _raise("observation_raced")


def _reader_identity_projection(snapshot: WindowsTokenSnapshot) -> dict[str, Any]:
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
    _compare_effective_token(state.session, state.baseline_snapshot)
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
    _compare_effective_token(state.session, state.baseline_snapshot)


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
    _compare_effective_token(state.session, state.baseline_snapshot)
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
        _compare_effective_token(state.session, state.baseline_snapshot)
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
    _compare_effective_token(state.session, state.baseline_snapshot)
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
    try:
        security = state.native.security.pin_security_descriptor(
            raw,
            profile=WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
        )
    except BaseException as error:
        _raise_security_failure(error, phase="descriptor")
    if security.observation.sacl_present:
        _raise("unsupported_security")
    return _PinnedDescriptor(
        held=held,
        raw=raw,
        security=security,
    )


def _observe_descriptor(
    state: _ReadState,
    held: _HeldObject,
    *,
    anchor: bool,
    pin: bool = False,
) -> tuple[_PinnedDescriptor, WindowsSid | None]:
    _compare_effective_token(state.session, state.baseline_snapshot)
    pinned = _read_and_pin_descriptor(state, held)
    descriptor = pinned.security.observation
    reader: WindowsSid | None = None
    if anchor:
        _validate_anchor_policy(state.native.security, descriptor)
    else:
        reader = _validate_dedicated_policy(descriptor, pin=pin)
    _compare_effective_token(state.session, state.baseline_snapshot)
    return pinned, reader


def _ace_projection(ace: WindowsAce) -> dict[str, str]:
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
    descriptor = pinned.security.observation
    return {
        "dacl": [_ace_projection(ace) for ace in descriptor.dacl_aces],
        "dacl_revision": descriptor.dacl_revision,
        "denied_access_checks": _denied_access_projection(rights),
        "descriptor_control": f"{descriptor.control:04x}",
        "owner_sid": descriptor.owner.numeric,
        "physical_identity": pinned.held.snapshot.identity_projection,
        "primary_group_sid": descriptor.group.numeric,
        "role": role,
    }


def _check_effective_access(
    state: _ReadState,
    pinned: _PinnedDescriptor,
    rights: tuple[tuple[str, int], ...],
) -> None:
    _compare_effective_token(state.session, state.baseline_snapshot)
    scope = None
    primary: BaseException | None = None
    try:
        scope = state.session.open_access_check(pinned.security)
        for _name, mask in rights:
            result = scope.check_denial(raw_mask=mask)
            if not result.denied:
                _raise("security_policy_mismatch")
    except BaseException as error:
        primary = error
    cleanup: ExternalPinReaderError | None = None
    cleanup_control: BaseException | None = None
    if scope is not None:
        try:
            scope.close()
        except BaseException as error:
            if isinstance(error, WindowsSecurityMechanicsError):
                cleanup = _translate_security_error_graph(
                    error,
                    phase="cleanup",
                )
            elif isinstance(error, Exception):
                cleanup = ExternalPinReaderError("observation_failed")
            else:
                _sanitize_control_links(
                    error,
                    phase="cleanup",
                    fallback=ExternalPinReaderError("observation_failed"),
                )
                cleanup_control = error
    if cleanup_control is not None:
        if primary is not None and cleanup_control.__context__ is None:
            cleanup_control.__context__ = primary
        _raise_after_cleanup(cleanup_control, cleanup)
    _raise_after_cleanup(primary, cleanup)
    _compare_effective_token(state.session, state.baseline_snapshot)


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
    _compare_effective_token(state.session, state.baseline_snapshot)
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
    _compare_effective_token(state.session, state.baseline_snapshot)
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
    _compare_effective_token(state.session, state.baseline_snapshot)
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
    _compare_effective_token(state.session, state.baseline_snapshot)
    if raced:
        _raise("observation_raced")


def _security_policy_projection(
    anchor: _PinnedDescriptor,
    dedicated: tuple[_PinnedDescriptor, ...],
    enrolled_reader: WindowsSid,
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
    session: WindowsSecuritySession | None = None
    held: list[_HeldObject] | None = None
    backend_entered = False
    primary: BaseException | None = None
    candidate: ExternalPinEvidence | None = None
    try:
        held = []
        entered_backend = backend.__enter__()
        backend_entered = True
        if entered_backend is not backend:
            _raise("observation_failed")
        try:
            change_notify_luid = native.security.resolve_privilege_luid(
                "SeChangeNotifyPrivilege"
            )
            session = native.security.open_token_session(
                profile=WINDOWS_TOKEN_PROFILE_BASE
            )
            baseline_snapshot = session.baseline_snapshot
        except BaseException as error:
            _raise_security_failure(error, phase="baseline")
        _intrinsically_validate_token(baseline_snapshot, change_notify_luid)

        _compare_effective_token(session, baseline_snapshot)
        known_folder = _resolve_known_folder(native)
        _compare_effective_token(session, baseline_snapshot)

        state = _ReadState(
            backend=backend,
            native=native,
            session=session,
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
        enrolled_candidates: list[WindowsSid] = []
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
    session_cleanup: ExternalPinReaderError | None = None
    session_control_error: BaseException | None = None
    if session is not None:
        try:
            session.close()
        except BaseException as error:
            if isinstance(error, WindowsSecurityMechanicsError):
                session_cleanup = _translate_security_error_graph(
                    error,
                    phase="cleanup",
                )
            elif isinstance(error, Exception):
                session_cleanup = ExternalPinReaderError("observation_failed")
            else:
                _sanitize_control_links(
                    error,
                    phase="cleanup",
                    fallback=primary_fallback,
                )
                session_control_error = error
    cleanup: ExternalPinReaderError | None = None
    if backend_cleanup_error is not None:
        cleanup = _sanitize_cleanup_chain(
            backend_cleanup_error,
            cleanup_fallback=cleanup_fallback,
            processing_fallback=processing_fallback,
        )
    cleanup = _append_cleanup(cleanup, session_cleanup)
    if session_control_error is not None:
        if primary is not None and session_control_error.__context__ is None:
            session_control_error.__context__ = primary
        _raise_after_cleanup(
            session_control_error,
            cleanup,
            fallback=primary_fallback,
        )
    _raise_after_cleanup(primary, cleanup, fallback=primary_fallback)
    if candidate is None:
        _raise("observation_failed")
    return candidate
