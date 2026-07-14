"""Projection-neutral Windows token, descriptor, and denial mechanics."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass


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
        del name, value
        raise AttributeError("WindowsSecurityMechanicsError is immutable")


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
    __slots__ = ("_closed", "_descriptor", "_mechanics", "_owned")

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


_DWORD = ctypes.c_uint32
_BOOL = ctypes.c_int32
_ENUM = ctypes.c_int32
_WORD = ctypes.c_uint16
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


def _raise(code: str) -> None:
    raise WindowsSecurityMechanicsError(code)


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
