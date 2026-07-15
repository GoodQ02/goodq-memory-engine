"""Projection-neutral Windows token, descriptor, and denial mechanics."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import struct
import unicodedata


WINDOWS_TOKEN_PROFILE_BASE = "base"
WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY = "mandatory_policy"
WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY = "dacl_only"
WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL = "mandatory_label"

__all__ = (
    "WINDOWS_TOKEN_PROFILE_BASE",
    "WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY",
    "WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY",
    "WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL",
    "WindowsSecurityMechanicsError",
    "WindowsSid",
    "WindowsSidRecord",
    "WindowsPrivilege",
    "WindowsTokenStatistics",
    "WindowsTokenSnapshot",
    "WindowsAce",
    "WindowsSecurityDescriptor",
    "WindowsPinnedSecurityDescriptor",
    "WindowsMutationDenial",
    "WindowsAccessCheckScope",
    "WindowsSecuritySession",
    "WindowsSecurityMechanics",
    "verify_windows_security_abi",
    "bind_windows_security",
)


_ERROR_MESSAGES = {
    "unsupported_security": "Required Windows security support is unavailable.",
    "thread_token_present": "A thread token is active.",
    "observation_failed": "Windows security observation failed.",
    "malformed_descriptor": "Windows security descriptor is malformed.",
    "unsupported_descriptor": (
        "Windows security descriptor uses unsupported features."
    ),
}


class WindowsSecurityMechanicsError(RuntimeError):
    """Fixed, path-free failure from shared Windows security mechanics."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        try:
            message = _ERROR_MESSAGES[code]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Unknown Windows security mechanics error code"
            ) from exc
        super().__init__(message)
        object.__setattr__(self, "_code", code)

    @property
    def code(self) -> str:
        return self._code

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"code", "_code"} and hasattr(self, "_code"):
            raise AttributeError(
                "WindowsSecurityMechanicsError code is immutable"
            )
        object.__setattr__(self, name, value)


class _RedactedObservation:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>(<redacted>)"


@dataclass(frozen=True, repr=False)
class WindowsSid(_RedactedObservation):
    binary: bytes
    numeric: str


@dataclass(frozen=True, repr=False)
class WindowsSidRecord(_RedactedObservation):
    sid: WindowsSid
    attributes: int


@dataclass(frozen=True, repr=False)
class WindowsPrivilege(_RedactedObservation):
    luid: int
    attributes: int


@dataclass(frozen=True, repr=False)
class WindowsTokenStatistics(_RedactedObservation):
    token_id: int
    authentication_id: int
    expiration_time: int
    token_type: int
    dynamic_charged: int
    dynamic_available: int
    group_count: int
    privilege_count: int
    modified_id: int


@dataclass(frozen=True, repr=False)
class WindowsTokenSnapshot(_RedactedObservation):
    statistics: WindowsTokenStatistics
    user_sid: WindowsSid
    groups: tuple[WindowsSidRecord, ...]
    privileges: tuple[WindowsPrivilege, ...]
    restricted_sids: tuple[WindowsSidRecord, ...]
    elevation_type: int
    is_elevated: bool
    has_restrictions: bool
    integrity: WindowsSidRecord
    ui_access: bool
    mandatory_policy: int | None
    is_app_container: bool


@dataclass(frozen=True, repr=False)
class WindowsAce(_RedactedObservation):
    ace_type: int
    flags: int
    mask: int
    sid: WindowsSid


@dataclass(frozen=True, repr=False)
class WindowsSecurityDescriptor(_RedactedObservation):
    control: int
    owner: WindowsSid
    group: WindowsSid
    dacl_present: bool
    dacl_null: bool
    dacl_revision: int | None
    dacl_aces: tuple[WindowsAce, ...]
    sacl_present: bool
    sacl_null: bool
    sacl_revision: int | None
    mandatory_label_aces: tuple[WindowsAce, ...]


@dataclass(frozen=True, repr=False)
class WindowsMutationDenial(_RedactedObservation):
    raw_mask: int
    mapped_mask: int
    denied: bool


_OWNER_SENTINEL = object()

_TOKEN_QUERY = 0x0008
_TOKEN_DUPLICATE = 0x0002
_ERROR_INSUFFICIENT_BUFFER = 122
_ERROR_NO_TOKEN = 1008
_MAX_TOKEN_BUFFER = 1_048_576
_MAX_TOKEN_RECORDS = 4096
_MAX_SID_SUBAUTHORITIES = 15
_MAX_SID_BYTES = 68
_PRIVILEGE_SET_ALL_NECESSARY = 0x00000001
_MUTATION_DENIAL_MASKS = frozenset(
    {
        0x00000002,
        0x00000004,
        0x00000010,
        0x00000040,
        0x00000100,
        0x00010000,
        0x00040000,
        0x00080000,
    }
)

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
_TOKEN_MANDATORY_POLICY_CLASS = 27
_TOKEN_IS_APP_CONTAINER_CLASS = 29

_TOKEN_PRIMARY = 1
_TOKEN_IMPERSONATION = 2
_SECURITY_IMPERSONATION = 2

_ACCESS_ALLOWED_ACE_TYPE = 0
_ACCESS_DENIED_ACE_TYPE = 1
_SYSTEM_MANDATORY_LABEL_ACE_TYPE = 0x11
_ORDINARY_ACE_FLAG_MASK = 0x1F
_SE_DACL_PRESENT = 0x0004
_SE_SACL_PRESENT = 0x0010
_SE_SELF_RELATIVE = 0x8000
_MIN_DESCRIPTOR_BYTES = 20
_MAX_DESCRIPTOR_BYTES = 131_072
_FILE_GENERIC_MAPPING_VALUES = (
    0x00120089,
    0x00120116,
    0x001200A0,
    0x001F01FF,
)


class _CapabilityOwner:
    __slots__ = ()

    def __new__(cls, token: object = None):
        if token is not _OWNER_SENTINEL:
            raise TypeError(f"{cls.__name__} cannot be constructed directly")
        return super().__new__(cls)

    def _alias_error(self) -> TypeError:
        return TypeError(f"{type(self).__name__} cannot be copied or serialized")

    def __copy__(self):
        raise self._alias_error()

    def __deepcopy__(self, memo):
        del memo
        raise self._alias_error()

    def __reduce__(self):
        raise self._alias_error()

    def __reduce_ex__(self, protocol):
        del protocol
        raise self._alias_error()


class WindowsPinnedSecurityDescriptor(_CapabilityOwner):
    __slots__ = ("_address", "_mechanics", "_observation", "_storage")

    @property
    def observation(self) -> WindowsSecurityDescriptor:
        return self._observation


class WindowsAccessCheckScope(_CapabilityOwner):
    __slots__ = (
        "_closed",
        "_descriptor",
        "_mechanics",
        "_owned",
        "_session",
    )

    def check_denial(self, *, raw_mask: int) -> WindowsMutationDenial:
        return self._mechanics._check_denial(self, raw_mask=raw_mask)

    def close(self) -> None:
        self._mechanics._close_access_scope(self)


class WindowsSecuritySession(_CapabilityOwner):
    __slots__ = (
        "_baseline_snapshot",
        "_closed",
        "_mechanics",
        "_owned",
        "_profile",
        "_scope",
    )

    @property
    def baseline_snapshot(self) -> WindowsTokenSnapshot:
        return self._mechanics._session_baseline(self)

    def observe_effective(self) -> WindowsTokenSnapshot:
        return self._mechanics._observe_effective(self)

    def open_access_check(
        self,
        descriptor: WindowsPinnedSecurityDescriptor,
    ) -> WindowsAccessCheckScope:
        return self._mechanics._open_access_scope(self, descriptor)

    def close(self) -> None:
        self._mechanics._close_session(self)


class WindowsSecurityMechanics(_CapabilityOwner):
    __slots__ = ("_advapi32", "_kernel32", "_provenance")

    def resolve_privilege_luid(self, privilege_name: str) -> int:
        return self._resolve_privilege_luid(privilege_name)

    def open_token_session(self, *, profile: str) -> WindowsSecuritySession:
        return self._open_token_session(profile=profile)

    def pin_security_descriptor(
        self,
        descriptor_bytes: bytes,
        *,
        profile: str,
    ) -> WindowsPinnedSecurityDescriptor:
        return self._pin_security_descriptor(descriptor_bytes, profile=profile)

    def map_file_mask(self, raw_mask: int) -> int:
        return self._map_file_mask(raw_mask)

    def _resolve_privilege_luid(self, privilege_name: str) -> int:
        return _resolve_privilege_luid(self, privilege_name)

    def _open_token_session(self, *, profile: str) -> WindowsSecuritySession:
        return _open_token_session(self, profile=profile)

    def _session_baseline(
        self,
        session: WindowsSecuritySession,
    ) -> WindowsTokenSnapshot:
        _require_open_session(self, session)
        return session._baseline_snapshot

    def _observe_effective(
        self,
        session: WindowsSecuritySession,
    ) -> WindowsTokenSnapshot:
        return _observe_effective(self, session)

    def _pin_security_descriptor(
        self,
        descriptor_bytes: bytes,
        *,
        profile: str,
    ) -> WindowsPinnedSecurityDescriptor:
        return _pin_security_descriptor(
            self,
            descriptor_bytes,
            profile=profile,
        )

    def _map_file_mask(self, raw_mask: int) -> int:
        return _map_file_mask(self, raw_mask)

    def _open_access_scope(
        self,
        session: WindowsSecuritySession,
        descriptor: WindowsPinnedSecurityDescriptor,
    ) -> WindowsAccessCheckScope:
        return _open_access_scope(self, session, descriptor)

    def _check_denial(
        self,
        scope: WindowsAccessCheckScope,
        *,
        raw_mask: int,
    ) -> WindowsMutationDenial:
        return _check_denial(self, scope, raw_mask=raw_mask)

    def _close_access_scope(self, scope: WindowsAccessCheckScope) -> None:
        _close_access_scope(self, scope)

    def _close_session(self, session: WindowsSecuritySession) -> None:
        _close_session(self, session)


_DWORD = ctypes.c_uint32
_BOOL = ctypes.c_int32
_ENUM = ctypes.c_int32
_WORD = ctypes.c_uint16
_BYTE = ctypes.c_ubyte
_HANDLE = ctypes.c_void_p
_PVOID = ctypes.c_void_p
_LARGE_INTEGER = ctypes.c_int64


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


class _OwnedNativeHandle:
    __slots__ = ("_cleanup_error", "_storage")

    def __init__(self, value: int | None) -> None:
        self._storage = _HANDLE(value)
        self._cleanup_error = WindowsSecurityMechanicsError("observation_failed")

    @property
    def value(self) -> int | None:
        value = self._storage.value
        return None if value is None else int(value)

    @value.setter
    def value(self, value: int | None) -> None:
        self._storage.value = value

    def output_pointer(self):
        return ctypes.byref(self._storage)


def _raise(code: str) -> None:
    raise WindowsSecurityMechanicsError(code) from None


def _last_error() -> int:
    try:
        return int(ctypes.get_last_error())
    except Exception:
        _raise("observation_failed")


def _close_owned_handle(
    mechanics: WindowsSecurityMechanics,
    owned: _OwnedNativeHandle,
) -> WindowsSecurityMechanicsError | None:
    value = owned.value
    if value is None:
        return None
    owned.value = None
    try:
        if not mechanics._kernel32.CloseHandle(_HANDLE(value)):
            _last_error()
            return owned._cleanup_error
    except BaseException:
        return owned._cleanup_error
    return None


def _append_cleanup(
    head: WindowsSecurityMechanicsError | None,
    later: WindowsSecurityMechanicsError | None,
) -> WindowsSecurityMechanicsError | None:
    if later is None:
        return head
    if head is None or head is later:
        return later if head is None else head
    tail = head
    remaining = 256
    while remaining:
        remaining -= 1
        if tail is later:
            return head
        cause = tail.__cause__
        if type(cause) is WindowsSecurityMechanicsError:
            tail = cause
            continue
        context = tail.__context__
        if type(context) is WindowsSecurityMechanicsError:
            tail = context
            continue
        if cause is None:
            tail.__cause__ = later
            tail.__suppress_context__ = True
        elif context is None:
            tail.__context__ = later
        return head
    return head


def _preserve_context(
    cleanup: WindowsSecurityMechanicsError,
    preserved: BaseException,
) -> None:
    tail: BaseException = cleanup
    remaining = 256
    while remaining:
        remaining -= 1
        if tail is preserved:
            return
        cause = tail.__cause__
        if type(cause) is WindowsSecurityMechanicsError:
            tail = cause
            continue
        context = tail.__context__
        if type(context) is WindowsSecurityMechanicsError:
            tail = context
            continue
        if context is None:
            tail.__context__ = preserved
            return
        tail = context


def _attach_cleanup(
    primary: BaseException,
    cleanup: WindowsSecurityMechanicsError | None,
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
    if type(primary.__context__) is WindowsSecurityMechanicsError:
        _append_cleanup(primary.__context__, cleanup)
        return
    if type(primary.__cause__) is WindowsSecurityMechanicsError:
        _append_cleanup(primary.__cause__, cleanup)
        return
    preserved = primary.__context__
    primary.__context__ = cleanup
    _preserve_context(cleanup, preserved)


def _raise_after_cleanup(
    primary: BaseException | None,
    cleanup: WindowsSecurityMechanicsError | None,
) -> None:
    if primary is None:
        if cleanup is not None:
            _reraise_preserving_graph(cleanup)
        return
    if isinstance(primary, Exception):
        if type(primary) is WindowsSecurityMechanicsError:
            public = primary
            if (
                public.__cause__ is not None
                and type(public.__cause__) is not WindowsSecurityMechanicsError
            ):
                public.__cause__ = None
            if (
                public.__context__ is not None
                and type(public.__context__) is not WindowsSecurityMechanicsError
            ):
                public.__context__ = None
        else:
            public = WindowsSecurityMechanicsError("observation_failed")
        _attach_cleanup(public, cleanup)
        _reraise_preserving_graph(public)
    _attach_cleanup(primary, cleanup)
    _reraise_preserving_graph(primary)


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


def _luid_value(value: _LUID) -> int:
    return ((int(value.HighPart) & 0xFFFFFFFF) << 32) | int(value.LowPart)


def _resolve_privilege_luid(
    mechanics: WindowsSecurityMechanics,
    privilege_name: str,
) -> int:
    if type(privilege_name) is not str:
        raise TypeError("privilege_name must be exact str")
    try:
        code_units = len(privilege_name.encode("utf-16-le")) // 2
    except UnicodeEncodeError as error:
        raise ValueError("privilege_name is invalid") from error
    if (
        not privilege_name
        or code_units > 256
        or any(unicodedata.category(character) == "Cc" for character in privilege_name)
    ):
        raise ValueError("privilege_name is invalid")
    value = _LUID()
    try:
        succeeded = mechanics._advapi32.LookupPrivilegeValueW(
            None,
            privilege_name,
            ctypes.byref(value),
        )
        if not succeeded:
            _last_error()
            _raise("observation_failed")
    except BaseException as error:
        _raise_after_cleanup(error, None)
    return _luid_value(value)


def _parse_sid(
    raw: bytes | memoryview,
    offset: int,
    *,
    error_code: str = "observation_failed",
) -> tuple[WindowsSid, tuple[int, int]]:
    if offset < 0 or offset + 8 > len(raw):
        _raise(error_code)
    revision = raw[offset]
    count = raw[offset + 1]
    size = 8 + 4 * count
    if (
        revision != 1
        or count > _MAX_SID_SUBAUTHORITIES
        or size > _MAX_SID_BYTES
        or offset + size > len(raw)
    ):
        _raise(error_code)
    binary = bytes(raw[offset : offset + size])
    authority = int.from_bytes(binary[2:8], "big")
    subauthorities = tuple(
        int.from_bytes(binary[8 + index * 4 : 12 + index * 4], "little")
        for index in range(count)
    )
    numeric = "-".join(
        ("S", "1", str(authority), *(str(value) for value in subauthorities))
    )
    return WindowsSid(binary=binary, numeric=numeric), (offset, offset + size)


def _sid_from_pointer(
    raw: bytes,
    base: int,
    pointer: int,
) -> tuple[WindowsSid, tuple[int, int]]:
    if pointer < base or pointer - base >= len(raw):
        _raise("observation_failed")
    return _parse_sid(raw, pointer - base)


def _reject_overlapping_intervals(
    intervals: tuple[tuple[int, int], ...],
) -> None:
    ordered = sorted(intervals)
    for index in range(1, len(ordered)):
        if ordered[index][0] < ordered[index - 1][1]:
            _raise("observation_failed")


def _query_variable_token(
    mechanics: WindowsSecurityMechanics,
    handle: int,
    info_class: int,
) -> tuple[bytes, int]:
    required = _DWORD(0xFFFFFFFF)
    try:
        succeeded = mechanics._advapi32.GetTokenInformation(
            _HANDLE(handle),
            info_class,
            None,
            0,
            ctypes.byref(required),
        )
        if succeeded:
            _raise("observation_failed")
        error = _last_error()
    except WindowsSecurityMechanicsError:
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
        succeeded = mechanics._advapi32.GetTokenInformation(
            _HANDLE(handle),
            info_class,
            ctypes.cast(storage, _PVOID),
            size,
            ctypes.byref(returned),
        )
        if not succeeded:
            _last_error()
            _raise("observation_failed")
    except WindowsSecurityMechanicsError:
        raise
    except Exception:
        _raise("observation_failed")
    if int(returned.value) != size:
        _raise("observation_failed")
    return bytes(storage), ctypes.addressof(storage)


def _query_statistics(
    mechanics: WindowsSecurityMechanics,
    handle: int,
) -> WindowsTokenStatistics:
    value = _TOKEN_STATISTICS()
    ctypes.memset(ctypes.addressof(value), 0, ctypes.sizeof(value))
    value.TokenType = -1
    value.GroupCount = 0xFFFFFFFF
    value.PrivilegeCount = 0xFFFFFFFF
    returned = _DWORD(0xFFFFFFFF)
    try:
        succeeded = mechanics._advapi32.GetTokenInformation(
            _HANDLE(handle),
            _TOKEN_STATISTICS_CLASS,
            ctypes.byref(value),
            ctypes.sizeof(value),
            ctypes.byref(returned),
        )
        if not succeeded:
            _last_error()
            _raise("observation_failed")
    except WindowsSecurityMechanicsError:
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
    return WindowsTokenStatistics(
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
    mechanics: WindowsSecurityMechanics,
    handle: int,
    info_class: int,
    accepted: tuple[int, ...],
) -> int:
    value = _ENUM(-1)
    returned = _DWORD(0xFFFFFFFF)
    try:
        succeeded = mechanics._advapi32.GetTokenInformation(
            _HANDLE(handle),
            info_class,
            ctypes.byref(value),
            4,
            ctypes.byref(returned),
        )
        if not succeeded:
            _last_error()
            _raise("observation_failed")
    except WindowsSecurityMechanicsError:
        raise
    except Exception:
        _raise("observation_failed")
    result = int(value.value)
    if int(returned.value) != 4 or result not in accepted:
        _raise("observation_failed")
    return result


def _query_mandatory_policy(
    mechanics: WindowsSecurityMechanics,
    handle: int,
) -> int:
    return _query_fixed_value(
        mechanics,
        handle,
        _TOKEN_MANDATORY_POLICY_CLASS,
        (0, 1, 2, 3),
    )


def _parse_token_user(raw: bytes, base: int) -> WindowsSid:
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
) -> tuple[WindowsSidRecord, ...]:
    if len(raw) < 8:
        _raise("observation_failed")
    count = struct.unpack_from("<I", raw, 0)[0]
    if count > _MAX_TOKEN_RECORDS or 8 + 16 * count > len(raw):
        _raise("observation_failed")
    records: list[WindowsSidRecord] = []
    intervals: list[tuple[int, int]] = []
    for index in range(count):
        offset = 8 + 16 * index
        pointer = struct.unpack_from("<Q", raw, offset)[0]
        attributes = struct.unpack_from("<I", raw, offset + 8)[0]
        sid, interval = _sid_from_pointer(raw, base, pointer)
        records.append(WindowsSidRecord(sid=sid, attributes=attributes))
        intervals.append(interval)
    _reject_overlapping_intervals(tuple(intervals))
    identities = [record.sid.binary for record in records]
    if len(set(identities)) != len(identities):
        _raise("observation_failed")
    return tuple(sorted(records, key=lambda record: record.sid.binary))


def _parse_privileges(raw: bytes) -> tuple[WindowsPrivilege, ...]:
    if len(raw) < 4:
        _raise("observation_failed")
    count = struct.unpack_from("<I", raw, 0)[0]
    if count > _MAX_TOKEN_RECORDS or 4 + 12 * count > len(raw):
        _raise("observation_failed")
    records = []
    for index in range(count):
        low, high, attributes = struct.unpack_from("<IiI", raw, 4 + 12 * index)
        luid = ((high & 0xFFFFFFFF) << 32) | low
        records.append(WindowsPrivilege(luid=luid, attributes=attributes))
    identities = [record.luid for record in records]
    if len(set(identities)) != len(identities):
        _raise("observation_failed")
    return tuple(sorted(records, key=lambda record: record.luid))


def _parse_integrity(raw: bytes, base: int) -> WindowsSidRecord:
    if len(raw) < 16:
        _raise("observation_failed")
    pointer = struct.unpack_from("<Q", raw, 0)[0]
    attributes = struct.unpack_from("<I", raw, 8)[0]
    sid, _interval = _sid_from_pointer(raw, base, pointer)
    return WindowsSidRecord(sid=sid, attributes=attributes)


def _parse_descriptor_header(
    raw: memoryview,
) -> tuple[int, int, int, int, int]:
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
        _raise("malformed_descriptor")
    return control, owner_offset, group_offset, sacl_offset, dacl_offset


def _validate_descriptor_offset(raw: memoryview, offset: int) -> None:
    if offset < _MIN_DESCRIPTOR_BYTES or offset % 4 or offset >= len(raw):
        _raise("malformed_descriptor")


def _parse_descriptor_owner_group(
    raw: memoryview,
    owner_offset: int,
    group_offset: int,
) -> tuple[
    WindowsSid,
    tuple[int, int],
    WindowsSid,
    tuple[int, int],
]:
    if owner_offset == 0 or group_offset == 0:
        _raise("unsupported_descriptor")
    _validate_descriptor_offset(raw, owner_offset)
    _validate_descriptor_offset(raw, group_offset)
    owner, owner_interval = _parse_sid(
        raw,
        owner_offset,
        error_code="malformed_descriptor",
    )
    group, group_interval = _parse_sid(
        raw,
        group_offset,
        error_code="malformed_descriptor",
    )
    return owner, owner_interval, group, group_interval


def _inspect_descriptor_acl(
    raw: memoryview,
    offset: int,
) -> tuple[int, int, tuple[int, int]]:
    _validate_descriptor_offset(raw, offset)
    if offset + 8 > len(raw):
        _raise("malformed_descriptor")
    acl_revision, acl_reserved, acl_size, ace_count, acl_reserved_word = (
        struct.unpack_from("<BBHHH", raw, offset)
    )
    if acl_reserved != 0 or acl_reserved_word != 0:
        _raise("malformed_descriptor")
    if (
        acl_size < 8
        or offset + acl_size > len(raw)
        or ace_count > _MAX_TOKEN_RECORDS
    ):
        _raise("malformed_descriptor")
    acl_end = offset + acl_size
    return acl_revision, ace_count, (offset, acl_end)


def _parse_descriptor_acl(
    raw: memoryview,
    offset: int,
    *,
    mandatory_labels: bool,
) -> tuple[int, tuple[WindowsAce, ...], tuple[int, int]]:
    acl_revision, ace_count, interval = _inspect_descriptor_acl(raw, offset)
    if acl_revision not in {2, 4}:
        _raise("unsupported_descriptor")
    acl_end = interval[1]
    cursor = offset + 8
    aces: list[WindowsAce] = []
    for _index in range(ace_count):
        if cursor + 8 > acl_end:
            _raise("malformed_descriptor")
        ace_type, flags, ace_size, mask = struct.unpack_from("<BBHI", raw, cursor)
        if mandatory_labels:
            if ace_type != _SYSTEM_MANDATORY_LABEL_ACE_TYPE:
                _raise("unsupported_descriptor")
        else:
            if ace_type not in {_ACCESS_ALLOWED_ACE_TYPE, _ACCESS_DENIED_ACE_TYPE}:
                _raise("unsupported_descriptor")
            if flags & ~_ORDINARY_ACE_FLAG_MASK:
                _raise("unsupported_descriptor")
        if ace_size < 8 or cursor + ace_size > acl_end:
            _raise("malformed_descriptor")
        sid, sid_interval = _parse_sid(
            raw,
            cursor + 8,
            error_code="malformed_descriptor",
        )
        if sid_interval[1] != cursor + ace_size:
            _raise("malformed_descriptor")
        aces.append(
            WindowsAce(
                ace_type=ace_type,
                flags=flags,
                mask=mask,
                sid=sid,
            )
        )
        cursor += ace_size
    if any(raw[cursor:acl_end]):
        _raise("malformed_descriptor")
    return acl_revision, tuple(aces), interval


def _reject_acl_offsets_inside_sids(
    owner_interval: tuple[int, int],
    group_interval: tuple[int, int],
    *acl_offsets: int,
) -> None:
    for offset in acl_offsets:
        if offset == 0:
            continue
        if (
            owner_interval[0] <= offset < owner_interval[1]
            or group_interval[0] <= offset < group_interval[1]
        ):
            _raise("malformed_descriptor")


def _validate_descriptor_intervals(
    raw: memoryview,
    owner: WindowsSid,
    owner_interval: tuple[int, int],
    group: WindowsSid,
    group_interval: tuple[int, int],
    acl_intervals: tuple[tuple[str, tuple[int, int]], ...],
) -> None:
    components = (
        ("owner", owner_interval),
        ("group", group_interval),
        *acl_intervals,
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
                _raise("malformed_descriptor")

    intervals = sorted({interval for _name, interval in components})
    cursor = _MIN_DESCRIPTOR_BYTES
    for start, end in intervals:
        if start < cursor or any(raw[cursor:start]):
            _raise("malformed_descriptor")
        cursor = end
    if any(raw[cursor:]):
        _raise("malformed_descriptor")


def _parse_dacl_only_descriptor(raw: memoryview) -> WindowsSecurityDescriptor:
    control, owner_offset, group_offset, sacl_offset, dacl_offset = (
        _parse_descriptor_header(raw)
    )
    if sacl_offset != 0:
        _raise("unsupported_descriptor")
    if dacl_offset == 0 or not (control & _SE_DACL_PRESENT):
        _raise("unsupported_descriptor")
    owner, owner_interval, group, group_interval = (
        _parse_descriptor_owner_group(raw, owner_offset, group_offset)
    )
    _reject_acl_offsets_inside_sids(
        owner_interval,
        group_interval,
        dacl_offset,
    )
    _revision, _ace_count, dacl_interval = _inspect_descriptor_acl(
        raw,
        dacl_offset,
    )
    _validate_descriptor_intervals(
        raw,
        owner,
        owner_interval,
        group,
        group_interval,
        (("dacl", dacl_interval),),
    )
    dacl_revision, dacl_aces, dacl_interval = _parse_descriptor_acl(
        raw,
        dacl_offset,
        mandatory_labels=False,
    )
    sacl_present = bool(control & _SE_SACL_PRESENT)
    return WindowsSecurityDescriptor(
        control=control,
        owner=owner,
        group=group,
        dacl_present=True,
        dacl_null=False,
        dacl_revision=dacl_revision,
        dacl_aces=dacl_aces,
        sacl_present=sacl_present,
        sacl_null=sacl_present,
        sacl_revision=None,
        mandatory_label_aces=(),
    )


def _parse_optional_descriptor_acl(
    raw: memoryview,
    *,
    control: int,
    present_bit: int,
    offset: int,
    mandatory_labels: bool,
) -> tuple[
    bool,
    bool,
    int | None,
    tuple[WindowsAce, ...],
    tuple[int, int] | None,
]:
    present = bool(control & present_bit)
    if not present:
        if offset != 0:
            _raise("malformed_descriptor")
        return False, False, None, (), None
    if offset == 0:
        return True, True, None, (), None
    revision, aces, interval = _parse_descriptor_acl(
        raw,
        offset,
        mandatory_labels=mandatory_labels,
    )
    return True, False, revision, aces, interval


def _optional_descriptor_acl_interval(
    raw: memoryview,
    *,
    control: int,
    present_bit: int,
    offset: int,
) -> tuple[int, int] | None:
    present = bool(control & present_bit)
    if not present:
        if offset != 0:
            _raise("malformed_descriptor")
        return None
    if offset == 0:
        return None
    _revision, _ace_count, interval = _inspect_descriptor_acl(raw, offset)
    return interval


def _parse_mandatory_label_descriptor(
    raw: memoryview,
) -> WindowsSecurityDescriptor:
    control, owner_offset, group_offset, sacl_offset, dacl_offset = (
        _parse_descriptor_header(raw)
    )
    owner, owner_interval, group, group_interval = (
        _parse_descriptor_owner_group(raw, owner_offset, group_offset)
    )
    _reject_acl_offsets_inside_sids(
        owner_interval,
        group_interval,
        dacl_offset,
        sacl_offset,
    )
    if dacl_offset != 0 and dacl_offset == sacl_offset:
        _raise("malformed_descriptor")
    dacl_interval = _optional_descriptor_acl_interval(
        raw,
        control=control,
        present_bit=_SE_DACL_PRESENT,
        offset=dacl_offset,
    )
    sacl_interval = _optional_descriptor_acl_interval(
        raw,
        control=control,
        present_bit=_SE_SACL_PRESENT,
        offset=sacl_offset,
    )
    intervals = []
    if dacl_interval is not None:
        intervals.append(("dacl", dacl_interval))
    if sacl_interval is not None:
        intervals.append(("sacl", sacl_interval))
    _validate_descriptor_intervals(
        raw,
        owner,
        owner_interval,
        group,
        group_interval,
        tuple(intervals),
    )
    (
        dacl_present,
        dacl_null,
        dacl_revision,
        dacl_aces,
        dacl_interval,
    ) = _parse_optional_descriptor_acl(
        raw,
        control=control,
        present_bit=_SE_DACL_PRESENT,
        offset=dacl_offset,
        mandatory_labels=False,
    )
    (
        sacl_present,
        sacl_null,
        sacl_revision,
        mandatory_label_aces,
        sacl_interval,
    ) = _parse_optional_descriptor_acl(
        raw,
        control=control,
        present_bit=_SE_SACL_PRESENT,
        offset=sacl_offset,
        mandatory_labels=True,
    )
    return WindowsSecurityDescriptor(
        control=control,
        owner=owner,
        group=group,
        dacl_present=dacl_present,
        dacl_null=dacl_null,
        dacl_revision=dacl_revision,
        dacl_aces=dacl_aces,
        sacl_present=sacl_present,
        sacl_null=sacl_null,
        sacl_revision=sacl_revision,
        mandatory_label_aces=mandatory_label_aces,
    )


def _validate_descriptor_profile(profile: object) -> str:
    if type(profile) is not str:
        raise TypeError("profile must be exact str")
    if profile not in {
        WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
        WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL,
    }:
        raise ValueError("Unsupported Windows descriptor profile")
    return profile


def _pin_security_descriptor(
    mechanics: WindowsSecurityMechanics,
    descriptor_bytes: bytes,
    *,
    profile: str,
) -> WindowsPinnedSecurityDescriptor:
    selected_profile = _validate_descriptor_profile(profile)
    if type(descriptor_bytes) is not bytes:
        raise TypeError("descriptor_bytes must be exact bytes")
    if not _MIN_DESCRIPTOR_BYTES <= len(descriptor_bytes) <= _MAX_DESCRIPTOR_BYTES:
        raise ValueError(
            "descriptor_bytes length is outside the supported boundary"
        )
    storage = (_BYTE * len(descriptor_bytes)).from_buffer_copy(descriptor_bytes)
    address = ctypes.addressof(storage)
    raw = memoryview(storage).cast("B")
    if selected_profile == WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY:
        observation = _parse_dacl_only_descriptor(raw)
    else:
        observation = _parse_mandatory_label_descriptor(raw)
    pinned = WindowsPinnedSecurityDescriptor(_OWNER_SENTINEL)
    pinned._address = address
    pinned._mechanics = mechanics
    pinned._observation = observation
    pinned._storage = storage
    return pinned


def _map_file_mask(
    mechanics: WindowsSecurityMechanics,
    raw_mask: int,
) -> int:
    if type(raw_mask) is not int:
        raise TypeError("raw_mask must be exact int")
    if not 0 <= raw_mask <= 0xFFFFFFFF:
        raise ValueError("raw_mask is outside the DWORD boundary")
    value = _DWORD(raw_mask)
    mapping = _GENERIC_MAPPING(*_FILE_GENERIC_MAPPING_VALUES)
    try:
        mechanics._advapi32.MapGenericMask(
            ctypes.byref(value),
            ctypes.byref(mapping),
        )
    except BaseException as error:
        _raise_after_cleanup(error, None)
    return int(value.value)


def _token_snapshot(
    mechanics: WindowsSecurityMechanics,
    handle: int,
    *,
    profile: str,
) -> WindowsTokenSnapshot:
    before = _query_statistics(mechanics, handle)
    user_raw, user_base = _query_variable_token(
        mechanics, handle, _TOKEN_USER_CLASS
    )
    user_sid = _parse_token_user(user_raw, user_base)
    groups_raw, groups_base = _query_variable_token(
        mechanics, handle, _TOKEN_GROUPS_CLASS
    )
    groups = _parse_sid_records(groups_raw, groups_base)
    privileges_raw, _privileges_base = _query_variable_token(
        mechanics, handle, _TOKEN_PRIVILEGES_CLASS
    )
    privileges = _parse_privileges(privileges_raw)
    restricted_raw, restricted_base = _query_variable_token(
        mechanics, handle, _TOKEN_RESTRICTED_SIDS_CLASS
    )
    restricted = _parse_sid_records(restricted_raw, restricted_base)
    elevation_type = _query_fixed_value(
        mechanics, handle, _TOKEN_ELEVATION_TYPE_CLASS, (1, 2, 3)
    )
    is_elevated = _query_fixed_value(
        mechanics, handle, _TOKEN_ELEVATION_CLASS, (0, 1)
    )
    has_restrictions = _query_fixed_value(
        mechanics, handle, _TOKEN_HAS_RESTRICTIONS_CLASS, (0, 1)
    )
    integrity_raw, integrity_base = _query_variable_token(
        mechanics, handle, _TOKEN_INTEGRITY_LEVEL_CLASS
    )
    integrity = _parse_integrity(integrity_raw, integrity_base)
    ui_access = _query_fixed_value(
        mechanics, handle, _TOKEN_UI_ACCESS_CLASS, (0, 1)
    )
    mandatory_policy = (
        _query_mandatory_policy(mechanics, handle)
        if profile == WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY
        else None
    )
    is_app_container = _query_fixed_value(
        mechanics, handle, _TOKEN_IS_APP_CONTAINER_CLASS, (0, 1)
    )
    after = _query_statistics(mechanics, handle)
    if (
        before != after
        or before.group_count != len(groups)
        or before.privilege_count != len(privileges)
    ):
        _raise("observation_failed")
    return WindowsTokenSnapshot(
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
        mandatory_policy=mandatory_policy,
        is_app_container=bool(is_app_container),
    )


def _validate_token_profile(profile: object) -> str:
    if type(profile) is not str:
        raise TypeError("profile must be exact str")
    if profile not in {
        WINDOWS_TOKEN_PROFILE_BASE,
        WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
    }:
        raise ValueError("Unsupported Windows token profile")
    return profile


def _open_token_session(
    mechanics: WindowsSecurityMechanics,
    *,
    profile: str,
) -> WindowsSecuritySession:
    selected_profile = _validate_token_profile(profile)
    thread_owner = _OwnedNativeHandle(None)
    try:
        thread_result = mechanics._advapi32.OpenThreadToken(
            mechanics._kernel32.GetCurrentThread(),
            _TOKEN_QUERY,
            1,
            thread_owner.output_pointer(),
        )
        if not thread_result:
            thread_owner.value = None
            thread_error = _last_error()
        else:
            thread_error = 0
    except BaseException as error:
        cleanup = _close_owned_handle(mechanics, thread_owner)
        _raise_after_cleanup(error, cleanup)
    if thread_result:
        if thread_owner.value is None:
            _raise("observation_failed")
        cleanup = _close_owned_handle(mechanics, thread_owner)
        _raise_after_cleanup(
            WindowsSecurityMechanicsError("thread_token_present"),
            cleanup,
        )
    if thread_error != _ERROR_NO_TOKEN:
        _raise("observation_failed")

    baseline = _OwnedNativeHandle(None)
    try:
        process_result = mechanics._advapi32.OpenProcessToken(
            mechanics._kernel32.GetCurrentProcess(),
            _TOKEN_QUERY | _TOKEN_DUPLICATE,
            baseline.output_pointer(),
        )
        if not process_result:
            baseline.value = None
            _last_error()
            _raise("observation_failed")
    except BaseException as error:
        cleanup = _close_owned_handle(mechanics, baseline)
        _raise_after_cleanup(error, cleanup)
    if baseline.value is None:
        _raise("observation_failed")

    try:
        snapshot = _token_snapshot(
            mechanics,
            baseline.value,
            profile=selected_profile,
        )
    except BaseException as error:
        cleanup = _close_owned_handle(mechanics, baseline)
        _raise_after_cleanup(error, cleanup)

    session = WindowsSecuritySession(_OWNER_SENTINEL)
    session._baseline_snapshot = snapshot
    session._closed = False
    session._mechanics = mechanics
    session._owned = baseline
    session._profile = selected_profile
    session._scope = None
    return session


def _observe_effective(
    mechanics: WindowsSecurityMechanics,
    session: WindowsSecuritySession,
) -> WindowsTokenSnapshot:
    _require_open_session(mechanics, session)
    thread_owner = _OwnedNativeHandle(None)
    try:
        thread_result = mechanics._advapi32.OpenThreadToken(
            mechanics._kernel32.GetCurrentThread(),
            _TOKEN_QUERY,
            1,
            thread_owner.output_pointer(),
        )
        if not thread_result:
            thread_owner.value = None
            thread_error = _last_error()
        else:
            thread_error = 0
    except BaseException as error:
        cleanup = _close_owned_handle(mechanics, thread_owner)
        _raise_after_cleanup(error, cleanup)
    if thread_result:
        if thread_owner.value is None:
            _raise("observation_failed")
        cleanup = _close_owned_handle(mechanics, thread_owner)
        _raise_after_cleanup(
            WindowsSecurityMechanicsError("thread_token_present"),
            cleanup,
        )
    if thread_error != _ERROR_NO_TOKEN:
        _raise("observation_failed")

    transient = _OwnedNativeHandle(None)
    try:
        process_result = mechanics._advapi32.OpenProcessToken(
            mechanics._kernel32.GetCurrentProcess(),
            _TOKEN_QUERY,
            transient.output_pointer(),
        )
        if not process_result:
            transient.value = None
            _last_error()
            _raise("observation_failed")
    except BaseException as error:
        cleanup = _close_owned_handle(mechanics, transient)
        _raise_after_cleanup(error, cleanup)
    if transient.value is None:
        _raise("observation_failed")

    snapshot: WindowsTokenSnapshot | None = None
    primary: BaseException | None = None
    try:
        snapshot = _token_snapshot(
            mechanics,
            transient.value,
            profile=session._profile,
        )
    except BaseException as error:
        primary = error
    cleanup = _close_owned_handle(mechanics, transient)
    _raise_after_cleanup(primary, cleanup)
    if snapshot is None:
        _raise("observation_failed")
    return snapshot


def _require_session(
    mechanics: WindowsSecurityMechanics,
    session: WindowsSecuritySession,
) -> None:
    if (
        type(session) is not WindowsSecuritySession
        or session._mechanics is not mechanics
    ):
        _raise("observation_failed")


def _require_open_session(
    mechanics: WindowsSecurityMechanics,
    session: WindowsSecuritySession,
) -> None:
    _require_session(mechanics, session)
    if session._closed:
        _raise("observation_failed")


def _require_pinned_descriptor(
    mechanics: WindowsSecurityMechanics,
    descriptor: WindowsPinnedSecurityDescriptor,
) -> None:
    if (
        type(descriptor) is not WindowsPinnedSecurityDescriptor
        or descriptor._mechanics is not mechanics
    ):
        _raise("observation_failed")


def _open_access_scope(
    mechanics: WindowsSecurityMechanics,
    session: WindowsSecuritySession,
    descriptor: WindowsPinnedSecurityDescriptor,
) -> WindowsAccessCheckScope:
    _require_open_session(mechanics, session)
    _require_pinned_descriptor(mechanics, descriptor)
    if session._scope is not None:
        _raise("observation_failed")

    duplicate = _OwnedNativeHandle(None)
    scope = WindowsAccessCheckScope(_OWNER_SENTINEL)
    scope._closed = False
    scope._descriptor = descriptor
    scope._mechanics = mechanics
    scope._owned = duplicate
    scope._session = session
    try:
        succeeded = mechanics._advapi32.DuplicateTokenEx(
            _HANDLE(session._owned.value),
            _TOKEN_QUERY,
            None,
            _SECURITY_IMPERSONATION,
            _TOKEN_IMPERSONATION,
            duplicate.output_pointer(),
        )
    except BaseException as error:
        cleanup = _close_owned_handle(mechanics, duplicate)
        _raise_after_cleanup(error, cleanup)
    if not succeeded:
        duplicate.value = None
        _last_error()
        _raise("observation_failed")
    if duplicate.value is None:
        _raise("observation_failed")
    session._scope = scope
    return scope


def _require_access_scope(
    mechanics: WindowsSecurityMechanics,
    scope: WindowsAccessCheckScope,
) -> None:
    if (
        type(scope) is not WindowsAccessCheckScope
        or scope._mechanics is not mechanics
    ):
        _raise("observation_failed")


def _require_open_access_scope(
    mechanics: WindowsSecurityMechanics,
    scope: WindowsAccessCheckScope,
) -> None:
    _require_access_scope(mechanics, scope)
    if (
        scope._closed
        or scope._session._scope is not scope
        or scope._session._closed
    ):
        _raise("observation_failed")


def _validate_privilege_output(
    storage: object,
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


def _check_denial(
    mechanics: WindowsSecurityMechanics,
    scope: WindowsAccessCheckScope,
    *,
    raw_mask: int,
) -> WindowsMutationDenial:
    _require_open_access_scope(mechanics, scope)
    if type(raw_mask) is not int:
        raise TypeError("raw_mask must be exact int")
    if raw_mask not in _MUTATION_DENIAL_MASKS:
        raise ValueError("raw_mask is outside the mutation-denial boundary")

    mapped = _map_file_mask(mechanics, raw_mask)
    accepted_count = scope._session._baseline_snapshot.statistics.privilege_count
    capacity = 8 + 12 * max(1, accepted_count)
    if capacity > 49_160:
        _raise("observation_failed")
    privilege_storage = (_BYTE * capacity)()
    ctypes.memset(ctypes.addressof(privilege_storage), 0, capacity)
    privilege_length = _DWORD(capacity)
    granted = _DWORD(0xFFFFFFFF)
    access_status = _BOOL(-1)
    mapping = _GENERIC_MAPPING(*_FILE_GENERIC_MAPPING_VALUES)
    try:
        succeeded = mechanics._advapi32.AccessCheck(
            _PVOID(scope._descriptor._address),
            _HANDLE(scope._owned.value),
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
    except BaseException as error:
        _raise_after_cleanup(error, None)

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
        denied = True
    elif status == 1 and granted_mask == mapped:
        denied = False
    else:
        _raise("observation_failed")
    return WindowsMutationDenial(
        raw_mask=raw_mask,
        mapped_mask=mapped,
        denied=denied,
    )


def _close_access_scope(
    mechanics: WindowsSecurityMechanics,
    scope: WindowsAccessCheckScope,
) -> None:
    _require_access_scope(mechanics, scope)
    if scope._closed:
        return
    scope._closed = True
    if scope._session._scope is scope:
        scope._session._scope = None
    cleanup = _close_owned_handle(mechanics, scope._owned)
    if cleanup is not None:
        _reraise_preserving_graph(cleanup)


def _close_session(
    mechanics: WindowsSecurityMechanics,
    session: WindowsSecuritySession,
) -> None:
    _require_session(mechanics, session)
    if session._closed:
        return
    session._closed = True
    primary: BaseException | None = None
    if session._scope is not None:
        try:
            _close_access_scope(mechanics, session._scope)
        except BaseException as error:
            primary = error
    cleanup = _close_owned_handle(mechanics, session._owned)
    _raise_after_cleanup(primary, cleanup)


def verify_windows_security_abi() -> None:
    expected = (
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
    if ctypes.sizeof(ctypes.c_void_p) != 8 or any(
        actual != required for actual, required in expected
    ):
        _raise("unsupported_security")


def bind_windows_security(
    *,
    kernel32: object,
    advapi32: object,
) -> WindowsSecurityMechanics:
    verify_windows_security_abi()
    if kernel32 is None or advapi32 is None:
        _raise("unsupported_security")

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
    except (AttributeError, OSError, TypeError):
        _raise("unsupported_security")

    mechanics = WindowsSecurityMechanics(_OWNER_SENTINEL)
    mechanics._kernel32 = kernel32
    mechanics._advapi32 = advapi32
    mechanics._provenance = object()
    return mechanics
