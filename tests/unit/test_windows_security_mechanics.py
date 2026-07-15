from __future__ import annotations

import copy
import ctypes
from dataclasses import dataclass, fields, replace
import importlib
import pickle
import struct
import sys
from types import SimpleNamespace

import pytest


MODULE_NAME = "steps.common.windows_security_mechanics"

EXPECTED_EXPORTS = (
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


def _load_module():
    return importlib.import_module(MODULE_NAME)


def test_public_surface_and_profiles_are_exact() -> None:
    module = _load_module()

    assert module.__all__ == EXPECTED_EXPORTS
    assert module.WINDOWS_TOKEN_PROFILE_BASE == "base"
    assert module.WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY == "mandatory_policy"
    assert module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY == "dacl_only"
    assert (
        module.WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL
        == "mandatory_label"
    )


def test_import_is_native_load_free(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []

    def reject_windll(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("module import attempted native loading")

    monkeypatch.setattr(ctypes, "WinDLL", reject_windll)
    monkeypatch.delitem(sys.modules, MODULE_NAME, raising=False)

    _load_module()

    assert calls == []


def test_observation_value_shapes_and_repr_are_exact() -> None:
    module = _load_module()

    expected_fields = {
        module.WindowsSid: ("binary", "numeric"),
        module.WindowsSidRecord: ("sid", "attributes"),
        module.WindowsPrivilege: ("luid", "attributes"),
        module.WindowsTokenStatistics: (
            "token_id",
            "authentication_id",
            "expiration_time",
            "token_type",
            "dynamic_charged",
            "dynamic_available",
            "group_count",
            "privilege_count",
            "modified_id",
        ),
        module.WindowsTokenSnapshot: (
            "statistics",
            "user_sid",
            "groups",
            "privileges",
            "restricted_sids",
            "elevation_type",
            "is_elevated",
            "has_restrictions",
            "integrity",
            "ui_access",
            "mandatory_policy",
            "is_app_container",
        ),
        module.WindowsAce: ("ace_type", "flags", "mask", "sid"),
        module.WindowsSecurityDescriptor: (
            "control",
            "owner",
            "group",
            "dacl_present",
            "dacl_null",
            "dacl_revision",
            "dacl_aces",
            "sacl_present",
            "sacl_null",
            "sacl_revision",
            "mandatory_label_aces",
        ),
        module.WindowsMutationDenial: ("raw_mask", "mapped_mask", "denied"),
    }

    for value_type, field_names in expected_fields.items():
        assert tuple(field.name for field in fields(value_type)) == field_names
        values = {
            field.name: (
                b"secret"
                if field.name == "binary"
                else "S-1-5-18"
                if field.name == "numeric"
                else ()
                if field.name.endswith("s") or field.name.endswith("aces")
                else None
            )
            for field in fields(value_type)
        }
        value = value_type(**values)
        assert repr(value) == f"<{value_type.__name__}>(<redacted>)"


def test_capability_owners_reject_direct_construction() -> None:
    module = _load_module()

    for owner_type in (
        module.WindowsSecurityMechanics,
        module.WindowsSecuritySession,
        module.WindowsAccessCheckScope,
        module.WindowsPinnedSecurityDescriptor,
    ):
        with pytest.raises(
            TypeError,
            match=rf"^{owner_type.__name__} cannot be constructed directly$",
        ):
            owner_type()


def _assert_owner_aliasing_is_rejected(owner: object) -> None:
    owner_name = type(owner).__name__
    message = rf"^{owner_name} cannot be copied or serialized$"
    operations = (
        lambda: copy.copy(owner),
        lambda: copy.deepcopy(owner),
        lambda: owner.__reduce__(),
        lambda: owner.__reduce_ex__(pickle.HIGHEST_PROTOCOL),
        lambda: pickle.dumps(owner),
    )
    for operation in operations:
        with pytest.raises(TypeError, match=message):
            operation()


class _NativeCall:
    def __init__(self) -> None:
        self.argtypes = None
        self.restype = None

    def __call__(self, *_args):
        raise AssertionError("binding invoked a native function")


def _native_security_dlls() -> tuple[SimpleNamespace, SimpleNamespace]:
    kernel32 = SimpleNamespace(
        GetCurrentThread=_NativeCall(),
        GetCurrentProcess=_NativeCall(),
        CloseHandle=_NativeCall(),
        LocalFree=_NativeCall(),
    )
    advapi32 = SimpleNamespace(
        OpenThreadToken=_NativeCall(),
        OpenProcessToken=_NativeCall(),
        GetTokenInformation=_NativeCall(),
        LookupPrivilegeValueW=_NativeCall(),
        DuplicateTokenEx=_NativeCall(),
        MapGenericMask=_NativeCall(),
        AccessCheck=_NativeCall(),
        GetSecurityInfo=_NativeCall(),
        IsValidSecurityDescriptor=_NativeCall(),
        GetSecurityDescriptorControl=_NativeCall(),
        GetSecurityDescriptorLength=_NativeCall(),
    )
    return kernel32, advapi32


def _sid(authority: int, *subauthorities: int) -> bytes:
    return (
        bytes((1, len(subauthorities)))
        + authority.to_bytes(6, "big")
        + b"".join(value.to_bytes(4, "little") for value in subauthorities)
    )


_TEST_SYSTEM_SID = _sid(5, 18)
_TEST_ADMIN_SID = _sid(5, 32, 544)
_TEST_READER_SID = _sid(5, 21, 165, 4242)
_TEST_MEDIUM_INTEGRITY_SID = _sid(16, 8192)


def _ace(
    ace_type: int,
    mask: int,
    sid: bytes,
    *,
    flags: int = 0,
) -> bytes:
    return struct.pack("<BBHI", ace_type, flags, 8 + len(sid), mask) + sid


def _acl(aces: tuple[bytes, ...], *, revision: int = 2) -> bytes:
    size = 8 + sum(len(ace) for ace in aces)
    return struct.pack("<BBHHH", revision, 0, size, len(aces), 0) + b"".join(aces)


def _dacl_only_descriptor() -> bytes:
    dacl = _acl(
        (
            _ace(0, 0x001F01FF, _TEST_SYSTEM_SID),
            _ace(1, 0x00040000, _TEST_ADMIN_SID),
            _ace(0, 0x00120089, _TEST_READER_SID),
        )
    )
    owner_offset = 20
    group_offset = owner_offset
    dacl_offset = owner_offset + len(_TEST_ADMIN_SID)
    return (
        struct.pack(
            "<BBHIIII",
            1,
            0,
            0x8004,
            owner_offset,
            group_offset,
            0,
            dacl_offset,
        )
        + _TEST_ADMIN_SID
        + dacl
    )


def _mandatory_label_descriptor() -> bytes:
    dacl = _acl(
        (_ace(0, 0x00120089, _TEST_READER_SID),),
        revision=4,
    )
    sacl = _acl(
        (_ace(0x11, 0x00000001, _TEST_MEDIUM_INTEGRITY_SID),),
        revision=2,
    )
    owner_offset = 20
    group_offset = owner_offset
    dacl_offset = owner_offset + len(_TEST_ADMIN_SID)
    sacl_offset = dacl_offset + len(dacl)
    return (
        struct.pack(
            "<BBHIIII",
            1,
            0,
            0x8014,
            owner_offset,
            group_offset,
            sacl_offset,
            dacl_offset,
        )
        + _TEST_ADMIN_SID
        + dacl
        + sacl
    )


def _descriptor_with_acl_states(*, dacl_state: str, sacl_state: str) -> bytes:
    data = bytearray(b"\0" * 20)
    owner_offset = len(data)
    data.extend(_TEST_ADMIN_SID)
    group_offset = owner_offset
    control = 0x8000
    dacl_offset = 0
    sacl_offset = 0
    if dacl_state != "absent":
        control |= 0x0004
        if dacl_state == "empty":
            dacl_offset = len(data)
            data.extend(_acl((), revision=4))
        else:
            assert dacl_state == "null"
    if sacl_state != "absent":
        control |= 0x0010
        if sacl_state == "empty":
            sacl_offset = len(data)
            data.extend(_acl((), revision=2))
        else:
            assert sacl_state == "null"
    struct.pack_into(
        "<BBHIIII",
        data,
        0,
        1,
        0,
        control,
        owner_offset,
        group_offset,
        sacl_offset,
        dacl_offset,
    )
    return bytes(data)


def _descriptor_variant(value: bytes, case: str) -> bytes:
    data = bytearray(value)
    owner_offset = struct.unpack_from("<I", data, 4)[0]
    group_offset = struct.unpack_from("<I", data, 8)[0]
    dacl_offset = struct.unpack_from("<I", data, 16)[0]
    if case == "trailing_zero":
        return bytes(data + b"\0\0\0\0")
    if case == "trailing_nonzero":
        return bytes(data + b"\0\0\0\x01")
    if case == "descriptor_revision":
        data[0] = 2
    elif case == "descriptor_sbz1":
        data[1] = 1
    elif case == "missing_self_relative":
        control = struct.unpack_from("<H", data, 2)[0]
        struct.pack_into("<H", data, 2, control & ~0x8000)
    elif case == "owner_absent":
        struct.pack_into("<I", data, 4, 0)
    elif case == "group_absent":
        struct.pack_into("<I", data, 8, 0)
    elif case == "dacl_absent":
        struct.pack_into("<I", data, 16, 0)
    elif case == "dacl_not_present":
        control = struct.unpack_from("<H", data, 2)[0]
        struct.pack_into("<H", data, 2, control & ~0x0004)
    elif case == "owner_out_of_bounds":
        struct.pack_into("<I", data, 4, len(data) + 4)
    elif case == "group_out_of_bounds":
        struct.pack_into("<I", data, 8, len(data) + 4)
    elif case == "dacl_out_of_bounds":
        struct.pack_into("<I", data, 16, len(data) + 4)
    elif case == "owner_inside_header":
        struct.pack_into("<I", data, 4, 16)
    elif case == "group_inside_header":
        struct.pack_into("<I", data, 8, 16)
    elif case == "dacl_inside_header":
        struct.pack_into("<I", data, 16, 16)
    elif case == "unaligned_owner":
        struct.pack_into("<I", data, 4, owner_offset + 2)
    elif case == "unaligned_group":
        struct.pack_into("<I", data, 8, group_offset + 2)
    elif case == "unaligned_dacl":
        struct.pack_into("<I", data, 16, dacl_offset + 2)
    elif case == "partial_owner_group_overlap":
        struct.pack_into("<I", data, 8, owner_offset + 4)
    elif case == "dacl_aliases_owner":
        struct.pack_into("<I", data, 16, owner_offset)
    elif case == "dacl_aliases_group":
        struct.pack_into("<I", data, 16, group_offset)
    elif case == "sacl_present":
        struct.pack_into("<I", data, 12, owner_offset)
    elif case == "sid_revision":
        data[owner_offset] = 2
    elif case == "truncated_declared_ace_sid":
        first_ace_sid = dacl_offset + 16
        data[first_ace_sid + 1] += 1
    elif case == "acl_revision":
        data[dacl_offset] = 3
    elif case == "acl_sbz1":
        data[dacl_offset + 1] = 1
    elif case == "acl_sbz2":
        struct.pack_into("<H", data, dacl_offset + 6, 1)
    elif case == "acl_size_short":
        struct.pack_into("<H", data, dacl_offset + 2, 7)
    elif case == "acl_size_long":
        struct.pack_into("<H", data, dacl_offset + 2, len(data) - dacl_offset + 4)
    elif case == "ace_count_over_cap":
        struct.pack_into("<H", data, dacl_offset + 4, 4097)
    elif case == "ace_count_mismatch":
        struct.pack_into("<H", data, dacl_offset + 4, 4)
    elif case == "ace_size_short":
        struct.pack_into("<H", data, dacl_offset + 10, 7)
    elif case == "ace_size_long":
        old_size = struct.unpack_from("<H", data, dacl_offset + 10)[0]
        struct.pack_into("<H", data, dacl_offset + 10, old_size + 4)
    elif case == "unsupported_ace":
        data[dacl_offset + 8] = 5
    elif case == "unknown_ace_flag":
        data[dacl_offset + 9] = 0x20
    elif case in {"acl_zero_padding", "acl_nonzero_padding"}:
        old_size = struct.unpack_from("<H", data, dacl_offset + 2)[0]
        struct.pack_into("<H", data, dacl_offset + 2, old_size + 4)
        data.extend(
            b"\0\0\0\0"
            if case == "acl_zero_padding"
            else b"\0\0\0\x01"
        )
    else:
        raise AssertionError(f"unknown descriptor case: {case}")
    return bytes(data)


def _mandatory_descriptor_variant(value: bytes, case: str) -> bytes:
    data = bytearray(value)
    owner_offset = struct.unpack_from("<I", data, 4)[0]
    sacl_offset = struct.unpack_from("<I", data, 12)[0]
    dacl_offset = struct.unpack_from("<I", data, 16)[0]
    if case == "sacl_not_present":
        control = struct.unpack_from("<H", data, 2)[0]
        struct.pack_into("<H", data, 2, control & ~0x0010)
    elif case == "dacl_not_present":
        control = struct.unpack_from("<H", data, 2)[0]
        struct.pack_into("<H", data, 2, control & ~0x0004)
    elif case == "unaligned_sacl":
        struct.pack_into("<I", data, 12, sacl_offset + 2)
    elif case == "sacl_aliases_owner":
        struct.pack_into("<I", data, 12, owner_offset)
    elif case == "sacl_aliases_dacl":
        struct.pack_into("<I", data, 12, dacl_offset)
    elif case == "sacl_inside_dacl":
        struct.pack_into("<I", data, 12, dacl_offset + 8)
    elif case == "sacl_revision":
        data[sacl_offset] = 3
    elif case == "unsupported_sacl_ace":
        data[sacl_offset + 8] = 0
    elif case == "sacl_nonzero_padding":
        old_size = struct.unpack_from("<H", data, sacl_offset + 2)[0]
        struct.pack_into("<H", data, sacl_offset + 2, old_size + 4)
        data.extend(b"\0\0\0\x01")
    elif case == "raw_label_values":
        data[sacl_offset + 9] = 0xFF
        struct.pack_into("<I", data, sacl_offset + 12, 0xFFFFFFFF)
    else:
        raise AssertionError(f"unknown mandatory descriptor case: {case}")
    return bytes(data)


@dataclass(frozen=True)
class _TokenSpec:
    user_sid: bytes = _sid(5, 21, 100, 200, 300, 1001)
    groups: tuple[tuple[bytes, int], ...] = ((_sid(5, 32, 545), 0x7),)
    privileges: tuple[tuple[tuple[int, int], int], ...] = (((0x17, 0), 0x2),)
    restricted_sids: tuple[tuple[bytes, int], ...] = ()
    integrity_sid: bytes = _sid(16, 0x2000)
    integrity_attributes: int = 0x20
    elevation_type: int = 1
    is_elevated: int = 0
    has_restrictions: int = 0
    ui_access: int = 0
    mandatory_policy: int = 1
    is_app_container: int = 0
    token_type: int = 1


def _raw_handle(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return ctypes.cast(value, ctypes.c_void_p).value


def _write_uint32(pointer: object, value: int) -> None:
    ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[0] = value


def _write_int32(pointer: object, value: int) -> None:
    ctypes.cast(pointer, ctypes.POINTER(ctypes.c_int32))[0] = value


def _write_handle(pointer: object, value: int | None) -> None:
    ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = value


class _ScriptedCall:
    def __init__(self, implementation) -> None:
        self.implementation = implementation
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.implementation(*args)


class _TokenWorld:
    """Complete fake boundary for projection-neutral token mechanics."""

    def __init__(
        self,
        *,
        token: _TokenSpec | None = None,
        thread_exception: BaseException | None = None,
        mandatory_query_case: str = "success",
        thread_case: str = "no_token_sentinel",
        process_case: str = "success",
        duplicate_case: str = "success",
        access_case: str = "deny",
        duplicate_exception: BaseException | None = None,
        duplicate_exception_after_write: bool = False,
        access_exception: BaseException | None = None,
        close_fail_handles: tuple[int, ...] = (),
        token_info_exception: BaseException | None = None,
        token_info_exception_at: int | None = None,
    ) -> None:
        self.token = token or _TokenSpec()
        self.token_buffer_case: str | None = None
        self.token_query_target: int | None = None
        self.statistics_drift_field: str | None = None
        self.statistics_group_count: int | None = None
        self.statistics_privilege_count: int | None = None
        self.vary_undefined_impersonation = False
        self.thread_exception = thread_exception
        self.mandatory_query_case = mandatory_query_case
        self.thread_case = thread_case
        self.process_case = process_case
        self.duplicate_case = duplicate_case
        self.access_case = access_case
        self.duplicate_exception = duplicate_exception
        self.duplicate_exception_after_write = duplicate_exception_after_write
        self.access_exception = access_exception
        self.close_fail_handles = frozenset(close_fail_handles)
        self.token_info_exception = token_info_exception
        self.token_info_exception_at = token_info_exception_at
        self.events: list[tuple[object, ...]] = []
        self.baseline_handle = 0x1001
        self.transient_handle = 0x1002
        self.thread_handle = 0x1003
        self.duplicate_handle = 0x1004
        self.issued_duplicate_handles: list[int] = []
        self.closed_handles: list[int] = []
        self._process_calls = 0
        self._stats_calls_by_handle: dict[int, int] = {}
        self._token_info_calls = 0
        self.kernel32 = SimpleNamespace(
            GetCurrentThread=_ScriptedCall(self._get_current_thread),
            GetCurrentProcess=_ScriptedCall(self._get_current_process),
            CloseHandle=_ScriptedCall(self._close_handle),
            LocalFree=_ScriptedCall(self._unexpected_call),
        )
        self.advapi32 = SimpleNamespace(
            OpenThreadToken=_ScriptedCall(self._open_thread_token),
            OpenProcessToken=_ScriptedCall(self._open_process_token),
            GetTokenInformation=_ScriptedCall(self._get_token_information),
            LookupPrivilegeValueW=_ScriptedCall(self._lookup_privilege_value),
            DuplicateTokenEx=_ScriptedCall(self._duplicate_token),
            MapGenericMask=_ScriptedCall(self._map_generic_mask),
            AccessCheck=_ScriptedCall(self._access_check),
            GetSecurityInfo=_ScriptedCall(self._unexpected_call),
            IsValidSecurityDescriptor=_ScriptedCall(self._unexpected_call),
            GetSecurityDescriptorControl=_ScriptedCall(self._unexpected_call),
            GetSecurityDescriptorLength=_ScriptedCall(self._unexpected_call),
        )

    def _unexpected_call(self, *_args):
        raise AssertionError("unexpected native call")

    def _get_current_thread(self) -> int:
        self.events.append(("current_thread",))
        return 0xFFFF0001

    def _get_current_process(self) -> int:
        self.events.append(("current_process",))
        return 0xFFFF0002

    def _open_thread_token(self, thread, access, open_as_self, output) -> int:
        self.events.append(
            (
                "open_thread",
                _raw_handle(thread),
                int(access),
                int(open_as_self),
            )
        )
        if self.thread_exception is not None:
            raise self.thread_exception
        if self.thread_case == "success_nonnull":
            _write_handle(output, self.thread_handle)
            return 1
        if self.thread_case == "success_null":
            _write_handle(output, None)
            return 1
        _write_handle(output, 0xDEAD0001)
        ctypes.set_last_error(
            1008 if self.thread_case == "no_token_sentinel" else 5
        )
        return 0

    def _open_process_token(self, process, access, output) -> int:
        self._process_calls += 1
        self.events.append(("open_process", _raw_handle(process), int(access)))
        if self.process_case == "success_null":
            _write_handle(output, None)
            return 1
        if self.process_case == "failure_sentinel":
            _write_handle(output, 0xDEAD0002)
            ctypes.set_last_error(5)
            return 0
        handle = self.baseline_handle if self._process_calls == 1 else self.transient_handle
        _write_handle(output, handle)
        return 1

    def _lookup_privilege_value(self, system_name, name, output) -> int:
        self.events.append(("lookup_privilege", system_name, name))
        words = ctypes.cast(output, ctypes.POINTER(ctypes.c_uint32))
        words[0] = 0x17
        words[1] = 0xFFFFFFFF
        return 1

    def _duplicate_token(
        self,
        source,
        access,
        attributes,
        level,
        token_type,
        output,
    ) -> int:
        self.events.append(
            (
                "duplicate_token",
                _raw_handle(source),
                int(access),
                _raw_handle(attributes),
                int(level),
                int(token_type),
            )
        )
        if self.duplicate_case == "success_null":
            _write_handle(output, None)
            return 1
        if self.duplicate_case == "failure_sentinel":
            _write_handle(output, 0xDEAD0003)
            ctypes.set_last_error(5)
            return 0
        handle = self.duplicate_handle + len(self.issued_duplicate_handles)
        if self.duplicate_exception is not None:
            if self.duplicate_exception_after_write:
                _write_handle(output, handle)
                self.issued_duplicate_handles.append(handle)
            raise self.duplicate_exception
        _write_handle(output, handle)
        self.issued_duplicate_handles.append(handle)
        return 1

    def _map_generic_mask(self, mask_pointer, mapping_pointer) -> None:
        mask = ctypes.cast(mask_pointer, ctypes.POINTER(ctypes.c_uint32))
        mapping = ctypes.cast(mapping_pointer, ctypes.POINTER(ctypes.c_uint32))
        values = tuple(int(mapping[index]) for index in range(4))
        original = int(mask[0])
        self.events.append(("map_generic", original, values))
        mapped = original
        for generic, replacement in zip(
            (0x80000000, 0x40000000, 0x20000000, 0x10000000),
            values,
        ):
            if mapped & generic:
                mapped = (mapped & ~generic) | replacement
        mask[0] = mapped

    def _access_check(
        self,
        descriptor,
        duplicate,
        desired,
        mapping_pointer,
        privilege_set,
        privilege_length,
        granted,
        status,
    ) -> int:
        mapping = ctypes.cast(
            mapping_pointer,
            ctypes.POINTER(ctypes.c_uint32),
        )
        capacity = int(
            ctypes.cast(
                privilege_length,
                ctypes.POINTER(ctypes.c_uint32),
            )[0]
        )
        privilege_address = _raw_handle(privilege_set)
        self.events.append(
            (
                "access_check",
                _raw_handle(descriptor),
                _raw_handle(duplicate),
                int(desired),
                tuple(int(mapping[index]) for index in range(4)),
                capacity,
                privilege_address is not None
                and ctypes.string_at(privilege_address, capacity)
                == bytes(capacity),
                int(
                    ctypes.cast(granted, ctypes.POINTER(ctypes.c_uint32))[0]
                ),
                int(ctypes.cast(status, ctypes.POINTER(ctypes.c_int32))[0]),
            )
        )
        if self.access_exception is not None:
            raise self.access_exception
        if privilege_address is not None:
            ctypes.memset(privilege_address, 0, capacity)
        _write_uint32(privilege_length, 8)
        if self.access_case == "native_failure_dirty":
            _write_uint32(privilege_length, 0xFFFFFFFF)
            _write_uint32(granted, 0xFFFFFFFF)
            _write_int32(status, 1)
            ctypes.set_last_error(122)
            return 0
        if self.access_case == "privilege_short":
            _write_uint32(privilege_length, 7)
        elif self.access_case == "privilege_long":
            _write_uint32(privilege_length, 49_161)
        elif self.access_case == "privilege_count_over_cap":
            ctypes.c_uint32.from_address(privilege_address).value = 4097
        elif self.access_case == "privilege_bad_control":
            ctypes.c_uint32.from_address(privilege_address + 4).value = 2
        elif self.access_case == "privilege_nonzero_trailing":
            _write_uint32(privilege_length, 9)
            ctypes.c_ubyte.from_address(privilege_address + 8).value = 1
        elif self.access_case == "denial_nonzero_privilege_output":
            _write_uint32(privilege_length, 20)
            ctypes.c_uint32.from_address(privilege_address).value = 1
            ctypes.c_uint32.from_address(privilege_address + 4).value = 1
            ctypes.c_uint32.from_address(privilege_address + 8).value = 0x17
            ctypes.c_int32.from_address(privilege_address + 12).value = 0
            ctypes.c_uint32.from_address(privilege_address + 16).value = 0x2

        if self.access_case == "omitted_status":
            pass
        elif self.access_case == "status_two":
            _write_int32(status, 2)
        elif self.access_case in {
            "grant",
            "true_extra_bits",
            "true_missing_bits",
        }:
            _write_int32(status, 1)
        else:
            _write_int32(status, 0)

        if self.access_case in {"grant", "true_extra_bits"}:
            _write_uint32(granted, int(desired))
            if self.access_case == "true_extra_bits":
                _write_uint32(granted, int(desired) | 0x1)
        elif self.access_case == "true_missing_bits":
            _write_uint32(granted, 0)
        elif self.access_case == "false_nonzero_grant":
            _write_uint32(granted, 1)
        else:
            _write_uint32(granted, 0)
        return 1

    @staticmethod
    def _sid_records_payload(
        records: tuple[tuple[bytes, int], ...],
        *,
        base: int,
    ) -> bytes:
        records_end = 8 + 16 * len(records)
        data = bytearray(b"\xA5" * (records_end + sum(len(sid) for sid, _ in records)))
        struct.pack_into("<I", data, 0, len(records))
        cursor = records_end
        for index, (sid, attributes) in enumerate(records):
            struct.pack_into("<Q", data, 8 + 16 * index, base + cursor)
            struct.pack_into("<I", data, 16 + 16 * index, attributes)
            data[cursor : cursor + len(sid)] = sid
            cursor += len(sid)
        return bytes(data)

    def _variable_payload(self, info_class: int, base: int) -> bytes:
        if info_class == 1:
            data = bytearray(b"\xA5" * (16 + len(self.token.user_sid)))
            pointer = base + 16
            if self.token_buffer_case in {"pointer_escape", "user_pointer_escape"}:
                pointer = base + len(data) + 4
            elif self.token_buffer_case == "user_pointer_below":
                pointer = base - 4
            elif self.token_buffer_case == "user_pointer_partial":
                pointer = base + len(data) - 4
            struct.pack_into("<Q", data, 0, pointer)
            struct.pack_into("<I", data, 8, 0)
            data[16:] = self.token.user_sid
            return bytes(data)
        if info_class == 2:
            data = bytearray(self._sid_records_payload(self.token.groups, base=base))
            if self.token_buffer_case == "group_count_over_cap":
                struct.pack_into("<I", data, 0, 4097)
            elif self.token.groups and self.token_buffer_case in {
                "group_pointer_escape",
                "group_pointer_below",
                "group_pointer_partial",
            }:
                if self.token_buffer_case == "group_pointer_escape":
                    pointer = base + len(data) + 4
                elif self.token_buffer_case == "group_pointer_below":
                    pointer = base - 4
                else:
                    pointer = base + len(data) - 4
                struct.pack_into("<Q", data, 8, pointer)
            elif (
                len(self.token.groups) >= 2
                and self.token_buffer_case == "group_cross_record_partial_overlap"
            ):
                records_end = 8 + 16 * len(self.token.groups)
                struct.pack_into("<Q", data, 24, base + records_end + 8)
            return bytes(data)
        if info_class == 3:
            data = bytearray(b"\xA5" * (4 + 12 * len(self.token.privileges)))
            privilege_count = len(self.token.privileges)
            if self.token_buffer_case == "privilege_count_over_cap":
                privilege_count = 4097
            struct.pack_into("<I", data, 0, privilege_count)
            for index, ((low, high), attributes) in enumerate(self.token.privileges):
                struct.pack_into("<IiI", data, 4 + index * 12, low, high, attributes)
            return bytes(data)
        if info_class == 11:
            data = bytearray(
                self._sid_records_payload(self.token.restricted_sids, base=base)
            )
            if self.token_buffer_case == "restricted_count_over_cap":
                struct.pack_into("<I", data, 0, 4097)
            elif self.token.restricted_sids and self.token_buffer_case in {
                "restricted_pointer_escape",
                "restricted_pointer_below",
                "restricted_pointer_partial",
            }:
                if self.token_buffer_case == "restricted_pointer_escape":
                    pointer = base + len(data) + 4
                elif self.token_buffer_case == "restricted_pointer_below":
                    pointer = base - 4
                else:
                    pointer = base + len(data) - 4
                struct.pack_into("<Q", data, 8, pointer)
            return bytes(data)
        if info_class == 25:
            data = bytearray(b"\xA5" * (16 + len(self.token.integrity_sid)))
            pointer = base + 16
            if self.token_buffer_case == "integrity_pointer_escape":
                pointer = base + len(data) + 4
            elif self.token_buffer_case == "integrity_pointer_below":
                pointer = base - 4
            elif self.token_buffer_case == "integrity_pointer_partial":
                pointer = base + len(data) - 4
            struct.pack_into("<Q", data, 0, pointer)
            struct.pack_into("<I", data, 8, self.token.integrity_attributes)
            data[16:] = self.token.integrity_sid
            return bytes(data)
        raise AssertionError(f"unexpected variable token class {info_class}")

    def _required_size(self, info_class: int) -> int:
        if info_class == 1:
            return 16 + len(self.token.user_sid)
        if info_class == 2:
            return 8 + 16 * len(self.token.groups) + sum(
                len(sid) for sid, _ in self.token.groups
            )
        if info_class == 3:
            return 4 + 12 * len(self.token.privileges)
        if info_class == 11:
            return 8 + 16 * len(self.token.restricted_sids) + sum(
                len(sid) for sid, _ in self.token.restricted_sids
            )
        if info_class == 25:
            return 16 + len(self.token.integrity_sid)
        raise AssertionError(f"unexpected variable token class {info_class}")

    def _statistics_payload(self, phase: int) -> bytes:
        token_id = 1
        authentication_id = 2
        expiration_time = 0
        token_type = self.token.token_type
        dynamic_charged = 4096
        dynamic_available = 2048
        group_count = (
            len(self.token.groups)
            if self.statistics_group_count is None
            else self.statistics_group_count
        )
        privilege_count = (
            len(self.token.privileges)
            if self.statistics_privilege_count is None
            else self.statistics_privilege_count
        )
        modified_id = 4
        if phase == 1:
            if self.statistics_drift_field == "token_id":
                token_id = 9
            elif self.statistics_drift_field == "authentication_id":
                authentication_id = 9
            elif self.statistics_drift_field == "expiration_time":
                expiration_time = 1
            elif self.statistics_drift_field == "token_type":
                token_type = 2
            elif self.statistics_drift_field == "dynamic_charged":
                dynamic_charged += 1
            elif self.statistics_drift_field == "dynamic_available":
                dynamic_available += 1
            elif self.statistics_drift_field == "group_count":
                group_count += 1
            elif self.statistics_drift_field == "privilege_count":
                privilege_count += 1
            elif self.statistics_drift_field == "modified_id":
                modified_id = 5
        impersonation = 0
        if self.vary_undefined_impersonation and phase % 2:
            impersonation = 0x5A5A5A5A
        data = bytearray(b"\xA5" * 56)
        struct.pack_into("<Ii", data, 0, token_id, 0)
        struct.pack_into("<Ii", data, 8, authentication_id, 0)
        struct.pack_into("<q", data, 16, expiration_time)
        struct.pack_into("<i", data, 24, token_type)
        struct.pack_into("<i", data, 28, impersonation)
        struct.pack_into("<I", data, 32, dynamic_charged)
        struct.pack_into("<I", data, 36, dynamic_available)
        struct.pack_into("<I", data, 40, group_count)
        struct.pack_into("<I", data, 44, privilege_count)
        struct.pack_into("<Ii", data, 48, modified_id, 0)
        if self.token_buffer_case == "statistics_token_type_sentinel":
            struct.pack_into("<i", data, 24, -1)
        elif self.token_buffer_case == "statistics_group_count_sentinel":
            struct.pack_into("<I", data, 40, 0xFFFFFFFF)
        elif self.token_buffer_case == "statistics_privilege_count_sentinel":
            struct.pack_into("<I", data, 44, 0xFFFFFFFF)
        return bytes(data)

    def _get_token_information(
        self,
        token_handle,
        info_class,
        buffer,
        buffer_length,
        return_length,
    ) -> int:
        self._token_info_calls += 1
        handle = _raw_handle(token_handle)
        assert handle is not None
        info = int(info_class)
        size = int(buffer_length)
        address = _raw_handle(buffer)
        initial_return_length = int(
            ctypes.cast(return_length, ctypes.POINTER(ctypes.c_uint32))[0]
        )
        if address is None:
            initial_buffer_state: tuple[object, ...] = ("none",)
        elif info == 10 and size >= 48:
            initial_buffer_state = (
                "statistics",
                struct.unpack("<i", ctypes.string_at(address + 24, 4))[0],
                struct.unpack("<I", ctypes.string_at(address + 40, 4))[0],
                struct.unpack("<I", ctypes.string_at(address + 44, 4))[0],
            )
        elif info in {18, 20, 21, 26, 27, 29} and size >= 4:
            initial_buffer_state = (
                "fixed",
                struct.unpack("<i", ctypes.string_at(address, 4))[0],
            )
        elif 0 <= size <= 1_048_576:
            initial_buffer_state = (
                "variable",
                ctypes.string_at(address, size) == b"\xA5" * size,
            )
        else:
            initial_buffer_state = ("invalid_size", size)
        self.events.append(
            (
                "token_input",
                handle,
                info,
                size,
                initial_return_length,
                initial_buffer_state,
            )
        )
        self.events.append(("token_info", handle, info, size, address is not None))
        if (
            self.token_info_exception is not None
            and self._token_info_calls == self.token_info_exception_at
        ):
            raise self.token_info_exception
        targeted = self.token_query_target in {None, info}
        if info == 10:
            if targeted and self.token_buffer_case == "statistics_failure_dirty":
                ctypes.memset(address, 0x5A, min(size, 56))
                _write_uint32(return_length, 7)
                ctypes.set_last_error(5)
                return 0
            phase = self._stats_calls_by_handle.get(handle, 0)
            self._stats_calls_by_handle[handle] = phase + 1
            if not (
                targeted and self.token_buffer_case == "statistics_omit_output"
            ):
                ctypes.memmove(address, self._statistics_payload(phase), 56)
            statistics_length = 56
            if targeted and self.token_buffer_case in {
                "fixed_bad_length",
                "statistics_short_length",
            }:
                statistics_length = 55
            elif targeted and self.token_buffer_case == "statistics_long_length":
                statistics_length = 57
            _write_uint32(return_length, statistics_length)
            return 1
        fixed = {
            18: self.token.elevation_type,
            20: self.token.is_elevated,
            21: self.token.has_restrictions,
            26: self.token.ui_access,
            27: self.token.mandatory_policy,
            29: self.token.is_app_container,
        }
        if info in fixed:
            if targeted and self.token_buffer_case == f"fixed_failure_dirty_{info}":
                ctypes.c_int32.from_address(address).value = 0x5A5A5A5A
                _write_uint32(return_length, 7)
                ctypes.set_last_error(5)
                return 0
            if info == 27 and self.mandatory_query_case == "failure_dirty":
                ctypes.c_uint32.from_address(address).value = fixed[info] & 0xFFFFFFFF
                _write_uint32(return_length, 4)
                ctypes.set_last_error(5)
                return 0
            omitted = (
                info == 27 and self.mandatory_query_case == "omit"
            ) or (
                targeted and self.token_buffer_case == f"omit_fixed_{info}"
            )
            if not omitted:
                ctypes.c_uint32.from_address(address).value = fixed[info] & 0xFFFFFFFF
            returned = 4
            if info == 27 and self.mandatory_query_case == "short":
                returned = 3
            elif info == 27 and self.mandatory_query_case == "long":
                returned = 5
            elif targeted and self.token_buffer_case == f"short_fixed_{info}":
                returned = 3
            elif targeted and self.token_buffer_case == f"long_fixed_{info}":
                returned = 5
            _write_uint32(return_length, returned)
            return 1
        required = self._required_size(info)
        exact_cap = (
            targeted
            and self.token_buffer_case == "exact_cap_a5_slack"
            and handle == self.baseline_handle
        )
        if exact_cap:
            required = 1_048_576
        if address is None and size == 0:
            if targeted and self.token_buffer_case == "zero_required":
                required = 0
            elif targeted and self.token_buffer_case == "over_cap_required":
                required = 1_048_577
            _write_uint32(return_length, required)
            if targeted and self.token_buffer_case == "sizing_success":
                return 1
            if targeted and self.token_buffer_case == "sizing_wrong_error":
                ctypes.set_last_error(5)
                return 0
            ctypes.set_last_error(122)
            return 0
        payload = self._variable_payload(info, address or 0)
        if exact_cap:
            structured_length = len(payload)
            exact_payload = bytearray(b"\xA5" * required)
            exact_payload[:structured_length] = payload
            payload = bytes(exact_payload)
            self.events.append(
                (
                    "token_exact_cap",
                    info,
                    structured_length,
                    len(payload),
                    payload[structured_length:]
                    == b"\xA5" * (required - structured_length),
                )
            )
        ctypes.memmove(address, payload, len(payload))
        if targeted and self.token_buffer_case == "fill_failure_dirty":
            _write_uint32(return_length, 7)
            ctypes.set_last_error(5)
            return 0
        reported = required
        if targeted and self.token_buffer_case == "size_changed":
            reported += 4
        _write_uint32(return_length, reported)
        return 1

    def _close_handle(self, handle) -> int:
        raw = _raw_handle(handle)
        assert raw is not None
        if raw in self.closed_handles:
            raise AssertionError("native handle closed more than once")
        self.closed_handles.append(raw)
        self.events.append(("close", raw))
        if raw in self.close_fail_handles:
            ctypes.set_last_error(5)
            return 0
        return 1


def test_win64_security_layouts_and_preflight_are_exact() -> None:
    module = _load_module()

    assert ctypes.sizeof(module._LUID) == 8
    assert ctypes.sizeof(module._LUID_AND_ATTRIBUTES) == 12
    assert ctypes.sizeof(module._SID_AND_ATTRIBUTES) == 16
    assert module._SID_AND_ATTRIBUTES.Attributes.offset == 8
    assert ctypes.sizeof(module._TOKEN_USER) == 16
    assert module._TOKEN_GROUPS.Groups.offset == 8
    assert module._TOKEN_PRIVILEGES.Privileges.offset == 4
    assert ctypes.sizeof(module._TOKEN_MANDATORY_LABEL) == 16
    assert ctypes.sizeof(module._TOKEN_ELEVATION) == 4
    assert ctypes.sizeof(module._TOKEN_STATISTICS) == 56
    assert module._TOKEN_STATISTICS.GroupCount.offset == 40
    assert module._TOKEN_STATISTICS.PrivilegeCount.offset == 44
    assert module._TOKEN_STATISTICS.ModifiedId.offset == 48
    assert ctypes.sizeof(module._GENERIC_MAPPING) == 16
    assert module._PRIVILEGE_SET.Privilege.offset == 8
    assert ctypes.sizeof(module._PRIVILEGE_SET) == 20

    module.verify_windows_security_abi()


def test_bind_assigns_exact_security_abi_without_native_observation() -> None:
    module = _load_module()
    kernel32, advapi32 = _native_security_dlls()

    mechanics = module.bind_windows_security(
        kernel32=kernel32,
        advapi32=advapi32,
    )

    assert type(mechanics) is module.WindowsSecurityMechanics
    assert advapi32.GetTokenInformation.argtypes == [
        module._HANDLE,
        module._ENUM,
        module._PVOID,
        module._DWORD,
        ctypes.POINTER(module._DWORD),
    ]
    assert advapi32.GetTokenInformation.restype is module._BOOL
    assert advapi32.AccessCheck.restype is module._BOOL
    assert advapi32.GetSecurityDescriptorLength.restype is module._DWORD
    _assert_owner_aliasing_is_rejected(mechanics)


def test_bind_rejects_missing_or_null_security_exports() -> None:
    module = _load_module()
    kernel32, advapi32 = _native_security_dlls()
    del advapi32.AccessCheck

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        module.bind_windows_security(kernel32=kernel32, advapi32=advapi32)
    assert exc_info.value.code == "unsupported_security"

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        module.bind_windows_security(kernel32=None, advapi32=object())
    assert exc_info.value.code == "unsupported_security"


def test_base_token_profile_uses_exact_17_call_sequence_and_owned_close() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE
    )

    assert [event[2] for event in world.events if event[0] == "token_info"] == [
        10,
        1,
        1,
        2,
        2,
        3,
        3,
        11,
        11,
        18,
        20,
        21,
        25,
        25,
        26,
        29,
        10,
    ]
    assert ("open_thread", 0xFFFF0001, 0x8, 1) in world.events
    assert ("open_process", 0xFFFF0002, 0xA) in world.events
    assert world.closed_handles == []
    assert session.baseline_snapshot.mandatory_policy is None
    _assert_owner_aliasing_is_rejected(session)

    session.close()
    session.close()

    assert world.closed_handles == [world.baseline_handle]


def test_mandatory_profile_inserts_class_27_and_changes_snapshot_equality() -> None:
    module = _load_module()
    snapshots = []

    for policy in (1, 3):
        world = _TokenWorld(token=_TokenSpec(mandatory_policy=policy))
        mechanics = module.bind_windows_security(
            kernel32=world.kernel32,
            advapi32=world.advapi32,
        )

        session = mechanics.open_token_session(
            profile=module.WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY
        )
        snapshots.append(session.baseline_snapshot)

        assert [event[2] for event in world.events if event[0] == "token_info"] == [
            10,
            1,
            1,
            2,
            2,
            3,
            3,
            11,
            11,
            18,
            20,
            21,
            25,
            25,
            26,
            27,
            29,
            10,
        ]
        assert session.baseline_snapshot.mandatory_policy == policy

        session.close()
        assert world.closed_handles == [world.baseline_handle]

    assert snapshots[0] != snapshots[1]


@pytest.mark.parametrize("policy", [0, 1, 2, 3])
def test_mandatory_profile_preserves_every_documented_policy(policy: int) -> None:
    module = _load_module()
    world = _TokenWorld(token=_TokenSpec(mandatory_policy=policy))
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY
    )

    assert session.baseline_snapshot.mandatory_policy == policy
    session.close()
    assert world.closed_handles == [world.baseline_handle]


@pytest.mark.parametrize(
    ("query_case", "policy"),
    [
        pytest.param("failure_dirty", 1, id="failure-dirty"),
        pytest.param("omit", 1, id="success-omitted"),
        pytest.param("short", 1, id="short-length"),
        pytest.param("long", 1, id="long-length"),
        pytest.param("success", 4, id="reserved-low-bit"),
        pytest.param("success", 0x80000000, id="reserved-high-bit"),
    ],
)
def test_malformed_mandatory_policy_stops_before_later_queries(
    query_case: str,
    policy: int,
) -> None:
    module = _load_module()
    world = _TokenWorld(
        token=_TokenSpec(mandatory_policy=policy),
        mandatory_query_case=query_case,
    )
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        mechanics.open_token_session(
            profile=module.WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY
        )

    assert exc_info.value.code == "observation_failed"
    queried = [event[2] for event in world.events if event[0] == "token_info"]
    assert queried.count(27) == 1
    assert 29 not in queried
    assert queried.count(10) == 1
    assert world.closed_handles == [world.baseline_handle]


def test_observe_effective_reprobes_query_only_and_closes_transient() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE
    )
    world.events.clear()

    current = session.observe_effective()

    assert current == session.baseline_snapshot
    assert world.events[:3] == [
        ("current_thread",),
        ("open_thread", 0xFFFF0001, 0x8, 1),
        ("current_process",),
    ]
    assert ("open_process", 0xFFFF0002, 0x8) in world.events
    assert [event[2] for event in world.events if event[0] == "token_info"] == [
        10,
        1,
        1,
        2,
        2,
        3,
        3,
        11,
        11,
        18,
        20,
        21,
        25,
        25,
        26,
        29,
        10,
    ]
    assert world.closed_handles == [world.transient_handle]

    session.close()
    assert world.closed_handles == [world.transient_handle, world.baseline_handle]


def test_native_exception_is_sanitized_without_secret_text() -> None:
    module = _load_module()
    secret = "native-secret-path"
    world = _TokenWorld(thread_exception=RuntimeError(secret))
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        mechanics.open_token_session(profile=module.WINDOWS_TOKEN_PROFILE_BASE)

    assert exc_info.value.code == "observation_failed"
    assert secret not in repr(exc_info.value)
    assert secret not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert world.closed_handles == []


def test_resolve_privilege_luid_uses_null_system_and_returns_unsigned_value() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    luid = mechanics.resolve_privilege_luid("SeChangeNotifyPrivilege")

    assert luid == 0xFFFFFFFF00000017
    assert world.events == [
        ("lookup_privilege", None, "SeChangeNotifyPrivilege")
    ]


class _PrivilegeNameSubclass(str):
    pass


class _DescriptorBytesSubclass(bytes):
    pass


class _MaskIntSubclass(int):
    pass


@pytest.mark.parametrize(
    ("value", "exception_type", "message"),
    [
        pytest.param(
            None,
            TypeError,
            "privilege_name must be exact str",
            id="none",
        ),
        pytest.param(
            b"SeChangeNotifyPrivilege",
            TypeError,
            "privilege_name must be exact str",
            id="bytes",
        ),
        pytest.param(
            _PrivilegeNameSubclass("SeChangeNotifyPrivilege"),
            TypeError,
            "privilege_name must be exact str",
            id="str-subclass",
        ),
        pytest.param("", ValueError, "privilege_name is invalid", id="empty"),
        pytest.param(
            "A" * 257,
            ValueError,
            "privilege_name is invalid",
            id="257-code-units",
        ),
        pytest.param(
            "\U0001F600" * 129,
            ValueError,
            "privilege_name is invalid",
            id="258-surrogate-code-units",
        ),
        pytest.param(
            "SeChange\x00NotifyPrivilege",
            ValueError,
            "privilege_name is invalid",
            id="nul",
        ),
        pytest.param(
            "SeChange\nNotifyPrivilege",
            ValueError,
            "privilege_name is invalid",
            id="control",
        ),
    ],
)
def test_invalid_privilege_names_fail_before_native_call(
    value: object,
    exception_type: type[Exception],
    message: str,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    with pytest.raises(exception_type) as exc_info:
        mechanics.resolve_privilege_luid(value)

    assert str(exc_info.value) == message
    assert world.events == []


@pytest.mark.parametrize(
    ("thread_case", "process_case", "expected_code", "closed_handles"),
    [
        pytest.param(
            "success_nonnull",
            "success",
            "thread_token_present",
            (0x1003,),
            id="thread-success-nonnull",
        ),
        pytest.param(
            "success_null",
            "success",
            "observation_failed",
            (),
            id="thread-success-null",
        ),
        pytest.param(
            "failure_other",
            "success",
            "observation_failed",
            (),
            id="thread-failure-dirty",
        ),
        pytest.param(
            "no_token_sentinel",
            "success_null",
            "observation_failed",
            (),
            id="process-success-null",
        ),
        pytest.param(
            "no_token_sentinel",
            "failure_sentinel",
            "observation_failed",
            (),
            id="process-failure-dirty",
        ),
    ],
)
def test_token_open_output_quadrants_only_close_owned_handles(
    thread_case: str,
    process_case: str,
    expected_code: str,
    closed_handles: tuple[int, ...],
) -> None:
    module = _load_module()
    world = _TokenWorld(
        thread_case=thread_case,
        process_case=process_case,
    )
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        mechanics.open_token_session(profile=module.WINDOWS_TOKEN_PROFILE_BASE)

    assert exc_info.value.code == expected_code
    assert tuple(world.closed_handles) == closed_handles
    assert not ({0xDEAD0001, 0xDEAD0002} & set(world.closed_handles))
    process_calls = [event for event in world.events if event[0] == "open_process"]
    assert bool(process_calls) is (thread_case == "no_token_sentinel")


@pytest.mark.parametrize(
    ("phase", "last_error_call"),
    [
        pytest.param("initial_thread", 1, id="initial-thread"),
        pytest.param("initial_process", 2, id="initial-process"),
        pytest.param("recheck_thread", 1, id="recheck-thread"),
        pytest.param("recheck_process", 2, id="recheck-process"),
    ],
)
def test_failed_token_open_clears_unowned_output_before_last_error_control_flow(
    monkeypatch,
    phase: str,
    last_error_call: int,
) -> None:
    module = _load_module()
    world = _TokenWorld(
        thread_case="failure_other" if phase == "initial_thread" else "no_token_sentinel",
        process_case="failure_sentinel" if phase == "initial_process" else "success",
    )
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = None
    if phase.startswith("recheck"):
        session = mechanics.open_token_session(
            profile=module.WINDOWS_TOKEN_PROFILE_BASE
        )
        if phase == "recheck_thread":
            world.thread_case = "failure_other"
        else:
            world.process_case = "failure_sentinel"

    primary = KeyboardInterrupt()
    original_tail = _traceback_tail(_prime_traceback(primary))
    primary.__suppress_context__ = False
    call_count = 0

    def interrupting_last_error() -> int:
        nonlocal call_count
        call_count += 1
        if call_count == last_error_call:
            raise primary
        return 1008

    monkeypatch.setattr(module, "_last_error", interrupting_last_error)

    with pytest.raises(KeyboardInterrupt) as exc_info:
        if session is None:
            mechanics.open_token_session(profile=module.WINDOWS_TOKEN_PROFILE_BASE)
        else:
            session.observe_effective()

    assert exc_info.value is primary
    assert _traceback_tail(primary.__traceback__) is original_tail
    assert primary.__suppress_context__ is False
    assert world.closed_handles == []
    assert not ({0xDEAD0001, 0xDEAD0002} & set(world.closed_handles))

    if session is not None:
        session.close()
        assert world.closed_handles == [world.baseline_handle]


def test_failed_session_close_is_final_and_closed_reads_are_native_silent() -> None:
    module = _load_module()
    world = _TokenWorld(close_fail_handles=(0x1001,))
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE
    )

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        session.close()

    assert exc_info.value.code == "observation_failed"
    assert world.closed_handles == [world.baseline_handle]
    frozen_events = tuple(world.events)

    session.close()
    for action in (
        lambda: session.baseline_snapshot,
        session.observe_effective,
    ):
        with pytest.raises(module.WindowsSecurityMechanicsError) as closed_exc:
            action()
        assert closed_exc.value.code == "observation_failed"

    assert tuple(world.events) == frozen_events
    assert world.closed_handles == [world.baseline_handle]
    assert not hasattr(session, "__enter__")
    assert not hasattr(session, "__del__")


def _prime_traceback(error: BaseException):
    try:
        raise error
    except BaseException as caught:
        traceback = caught.__traceback__
    assert traceback is not None
    return traceback


def _traceback_tail(traceback):
    while traceback.tb_next is not None:
        traceback = traceback.tb_next
    return traceback


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_control_flow_cleanup_preserves_occupied_graph_and_traceback(
    exception_type: type[BaseException],
) -> None:
    module = _load_module()
    primary = exception_type()
    original_tail = _traceback_tail(_prime_traceback(primary))
    original_cause = RuntimeError("preserved-cause")
    original_context = LookupError("preserved-context")
    primary.__cause__ = original_cause
    primary.__context__ = original_context
    primary.__suppress_context__ = False
    world = _TokenWorld(
        close_fail_handles=(0x1002,),
        token_info_exception=primary,
        token_info_exception_at=18,
    )
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE
    )

    with pytest.raises(exception_type) as exc_info:
        session.observe_effective()

    assert exc_info.value is primary
    assert primary.__cause__ is original_cause
    cleanup = primary.__context__
    assert type(cleanup) is module.WindowsSecurityMechanicsError
    assert cleanup.code == "observation_failed"
    assert cleanup.__context__ is original_context
    assert primary.__suppress_context__ is False
    assert _traceback_tail(primary.__traceback__) is original_tail
    assert world.closed_handles == [world.transient_handle]

    session.close()
    assert world.closed_handles == [world.transient_handle, world.baseline_handle]


def test_cleanup_only_rethrow_preserves_graph_inside_active_handler() -> None:
    module = _load_module()
    cleanup = module.WindowsSecurityMechanicsError("observation_failed")
    context = module.WindowsSecurityMechanicsError("observation_failed")
    cleanup.__context__ = context
    cleanup.__suppress_context__ = False

    def invoke_inside_active_handler() -> None:
        try:
            raise RuntimeError("active-handler")
        except RuntimeError:
            module._raise_after_cleanup(None, cleanup)

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        invoke_inside_active_handler()

    assert exc_info.value is cleanup
    assert cleanup.__cause__ is None
    assert cleanup.__context__ is context
    assert cleanup.__suppress_context__ is False


def _open_base_session(module, world: _TokenWorld):
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    return mechanics, session


def _expect_base_token_error(module, world: _TokenWorld) -> None:
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        mechanics.open_token_session(profile=module.WINDOWS_TOKEN_PROFILE_BASE)
    assert exc_info.value.code == "observation_failed"


def test_token_queries_use_exact_order_sizes_and_fresh_input_sentinels() -> None:
    module = _load_module()
    world = _TokenWorld()
    _mechanics, session = _open_base_session(module, world)

    inputs = [
        event
        for event in world.events
        if event[:2] == ("token_input", world.baseline_handle)
    ]
    assert [(event[2], event[3]) for event in inputs] == [
        (10, 56),
        (1, 0),
        (1, world._required_size(1)),
        (2, 0),
        (2, world._required_size(2)),
        (3, 0),
        (3, world._required_size(3)),
        (11, 0),
        (11, world._required_size(11)),
        (18, 4),
        (20, 4),
        (21, 4),
        (25, 0),
        (25, world._required_size(25)),
        (26, 4),
        (29, 4),
        (10, 56),
    ]
    for event in inputs:
        info, size, initial_length, state = event[2], event[3], event[4], event[5]
        if size == 0:
            assert state == ("none",)
        elif info == 10:
            assert initial_length == 0xFFFFFFFF
            assert state == ("statistics", -1, 0xFFFFFFFF, 0xFFFFFFFF)
        elif info in {18, 20, 21, 26, 29}:
            assert initial_length == 0xFFFFFFFF
            assert state == ("fixed", -1)
        else:
            assert initial_length == 0xFFFFFFFF
            assert state == ("variable", True)
    session.close()


@pytest.mark.parametrize("info_class", [1, 2, 3, 11, 25])
def test_exact_inclusive_variable_token_buffer_cap_is_accepted(
    info_class: int,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    world.token_buffer_case = "exact_cap_a5_slack"
    world.token_query_target = info_class

    _mechanics, session = _open_base_session(module, world)

    assert [event for event in world.events if event[0] == "token_exact_cap"] == [
        (
            "token_exact_cap",
            info_class,
            world._required_size(info_class),
            1_048_576,
            True,
        )
    ]
    session.close()


@pytest.mark.parametrize(
    ("case", "expected_calls"),
    [
        pytest.param("sizing_success", 1),
        pytest.param("sizing_wrong_error", 1),
        pytest.param("zero_required", 1),
        pytest.param("over_cap_required", 1),
        pytest.param("fill_failure_dirty", 2),
        pytest.param("size_changed", 2),
    ],
)
@pytest.mark.parametrize("info_class", [1, 2, 3, 11, 25])
def test_variable_token_query_quadrants_fail_without_retry(
    case: str,
    expected_calls: int,
    info_class: int,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    world.token_buffer_case = case
    world.token_query_target = info_class

    _expect_base_token_error(module, world)

    calls = [
        event
        for event in world.events
        if event[0] == "token_info" and event[2] == info_class
    ]
    assert len(calls) == expected_calls
    assert world.closed_handles == [world.baseline_handle]


@pytest.mark.parametrize(
    "case",
    [
        "user_pointer_below",
        "user_pointer_partial",
        "user_pointer_escape",
        "group_pointer_below",
        "group_pointer_partial",
        "group_pointer_escape",
        "integrity_pointer_below",
        "integrity_pointer_partial",
        "integrity_pointer_escape",
        "restricted_pointer_below",
        "restricted_pointer_partial",
        "restricted_pointer_escape",
    ],
)
def test_every_token_sid_pointer_must_be_wholly_contained(case: str) -> None:
    module = _load_module()
    token = _TokenSpec()
    if case.startswith("restricted_"):
        token = replace(token, restricted_sids=((_sid(5, 12), 0),))
    world = _TokenWorld(token=token)
    world.token_buffer_case = case

    _expect_base_token_error(module, world)

    assert world.closed_handles == [world.baseline_handle]


def test_partially_overlapping_token_sid_intervals_are_rejected() -> None:
    module = _load_module()
    first_sid = (
        bytes((1, 2))
        + (5).to_bytes(6, "big")
        + bytes((1, 1))
        + (7).to_bytes(6, "big")
    )
    token = replace(
        _TokenSpec(),
        groups=((first_sid, 0), (_sid(5, 99), 0)),
    )
    world = _TokenWorld(token=token)
    world.token_buffer_case = "group_cross_record_partial_overlap"

    _expect_base_token_error(module, world)

    assert world.closed_handles == [world.baseline_handle]


@pytest.mark.parametrize(
    "case",
    [
        "group_count_over_cap",
        "restricted_count_over_cap",
        "privilege_count_over_cap",
    ],
)
def test_each_variable_token_count_cap_is_checked(case: str) -> None:
    module = _load_module()
    world = _TokenWorld()
    world.token_buffer_case = case

    _expect_base_token_error(module, world)


@pytest.mark.parametrize(
    "case",
    [
        "statistics_token_type_sentinel",
        "statistics_group_count_sentinel",
        "statistics_privilege_count_sentinel",
        "statistics_failure_dirty",
        "statistics_omit_output",
        "statistics_short_length",
        "statistics_long_length",
    ],
)
def test_statistics_failure_and_sentinel_outputs_fail_without_retry(
    case: str,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    world.token_buffer_case = case

    _expect_base_token_error(module, world)

    calls = [
        event
        for event in world.events
        if event[0] == "token_info" and event[2] == 10
    ]
    assert len(calls) == 1


@pytest.mark.parametrize("info_class", [18, 20, 21, 26, 29])
@pytest.mark.parametrize(
    "case_prefix",
    ["fixed_failure_dirty", "omit_fixed", "short_fixed", "long_fixed"],
)
def test_each_fixed_token_class_rejects_output_quadrants(
    info_class: int,
    case_prefix: str,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    world.token_query_target = info_class
    world.token_buffer_case = f"{case_prefix}_{info_class}"

    _expect_base_token_error(module, world)

    calls = [
        event
        for event in world.events
        if event[0] == "token_info" and event[2] == info_class
    ]
    assert len(calls) == 1


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(replace(_TokenSpec(), token_type=0), id="token-type-zero"),
        pytest.param(replace(_TokenSpec(), token_type=3), id="token-type-three"),
        pytest.param(replace(_TokenSpec(), elevation_type=0), id="elevation-zero"),
        pytest.param(replace(_TokenSpec(), elevation_type=4), id="elevation-four"),
        pytest.param(replace(_TokenSpec(), is_elevated=2), id="elevation-bool"),
        pytest.param(
            replace(_TokenSpec(), has_restrictions=2),
            id="restriction-bool",
        ),
        pytest.param(replace(_TokenSpec(), ui_access=2), id="uiaccess-bool"),
        pytest.param(
            replace(_TokenSpec(), is_app_container=2),
            id="appcontainer-bool",
        ),
    ],
)
def test_out_of_domain_fixed_token_values_are_observation_failures(
    token: _TokenSpec,
) -> None:
    module = _load_module()
    world = _TokenWorld(token=token)

    _expect_base_token_error(module, world)


@pytest.mark.parametrize(
    "field",
    [
        "token_id",
        "authentication_id",
        "expiration_time",
        "token_type",
        "dynamic_charged",
        "dynamic_available",
        "group_count",
        "privilege_count",
        "modified_id",
    ],
)
def test_each_defined_token_statistics_field_is_fenced(field: str) -> None:
    module = _load_module()
    world = _TokenWorld()
    world.statistics_drift_field = field

    _expect_base_token_error(module, world)


@pytest.mark.parametrize("field", ["groups", "privileges"])
def test_statistics_counts_must_equal_parsed_array_counts(field: str) -> None:
    module = _load_module()
    world = _TokenWorld()
    if field == "groups":
        world.statistics_group_count = len(world.token.groups) + 1
    else:
        world.statistics_privilege_count = len(world.token.privileges) + 1

    _expect_base_token_error(module, world)


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(
            replace(
                _TokenSpec(),
                groups=((_sid(5, 32, 545), 7), (_sid(5, 32, 545), 0)),
            ),
            id="duplicate-group-sid",
        ),
        pytest.param(
            replace(
                _TokenSpec(),
                privileges=(((0x17, 0), 2), ((0x17, 0), 0)),
            ),
            id="duplicate-privilege-luid",
        ),
        pytest.param(
            replace(
                _TokenSpec(),
                restricted_sids=((_sid(5, 12), 0), (_sid(5, 12), 1)),
            ),
            id="duplicate-restricted-sid",
        ),
    ],
)
def test_duplicate_token_sid_and_luid_records_are_rejected(
    token: _TokenSpec,
) -> None:
    module = _load_module()
    world = _TokenWorld(token=token)

    _expect_base_token_error(module, world)


def test_token_arrays_use_binary_sid_and_unsigned_luid_sort_authority() -> None:
    module = _load_module()
    token = replace(
        _TokenSpec(),
        groups=(
            (_sid(5, 21, 300), 1),
            (_sid(5, 32, 545), 7),
            (_sid(5, 21, 2), 0),
        ),
        privileges=(((1, -1), 0), ((0x17, 0), 2), ((2, 0), 0)),
    )
    world = _TokenWorld(token=token)

    _mechanics, session = _open_base_session(module, world)

    snapshot = session.baseline_snapshot
    assert tuple(record.sid.binary for record in snapshot.groups) == tuple(
        sorted(sid for sid, _attributes in token.groups)
    )
    assert tuple(record.luid for record in snapshot.privileges) == (
        2,
        0x17,
        0xFFFFFFFF00000001,
    )
    session.close()


@pytest.mark.parametrize("kind", ["groups", "privileges", "restricted"])
def test_token_array_exact_4096_record_boundary_is_accepted(kind: str) -> None:
    module = _load_module()
    token = _TokenSpec()
    if kind == "groups":
        token = replace(
            token,
            groups=tuple((_sid(5, 21, index), 0) for index in range(4096)),
        )
    elif kind == "privileges":
        token = replace(
            token,
            privileges=tuple(((index, 1), 0) for index in range(4096)),
        )
    else:
        token = replace(
            token,
            restricted_sids=tuple(
                (_sid(5, 12, index), 0) for index in range(4096)
            ),
        )
    world = _TokenWorld(token=token)

    _mechanics, session = _open_base_session(module, world)

    snapshot = session.baseline_snapshot
    expected = 4096
    if kind == "groups":
        assert len(snapshot.groups) == expected
    elif kind == "privileges":
        assert len(snapshot.privileges) == expected
    else:
        assert len(snapshot.restricted_sids) == expected
    session.close()


def test_undefined_impersonation_statistics_bytes_do_not_create_drift() -> None:
    module = _load_module()
    world = _TokenWorld()
    world.vary_undefined_impersonation = True

    _mechanics, session = _open_base_session(module, world)

    assert session.baseline_snapshot.statistics.token_type == 1
    session.close()


def test_dacl_only_descriptor_is_parsed_once_into_pinned_observation() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )

    observation = pinned.observation
    assert observation.control == 0x8004
    assert observation.owner.binary == _TEST_ADMIN_SID
    assert observation.group.binary == _TEST_ADMIN_SID
    assert observation.dacl_present is True
    assert observation.dacl_null is False
    assert observation.dacl_revision == 2
    assert [ace.ace_type for ace in observation.dacl_aces] == [0, 1, 0]
    assert [ace.mask for ace in observation.dacl_aces] == [
        0x001F01FF,
        0x00040000,
        0x00120089,
    ]
    assert observation.sacl_present is False
    assert observation.sacl_null is False
    assert observation.sacl_revision is None
    assert observation.mandatory_label_aces == ()
    assert "<redacted>" in repr(observation)
    _assert_owner_aliasing_is_rejected(pinned)
    assert world.events == []


def test_descriptor_parser_receives_the_exact_retained_allocation(
    monkeypatch,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    original = module._parse_dacl_only_descriptor
    observed: list[memoryview] = []

    def audit_parser(raw):
        assert type(raw) is memoryview
        observed.append(raw)
        return original(raw)

    monkeypatch.setattr(module, "_parse_dacl_only_descriptor", audit_parser)

    descriptor = _dacl_only_descriptor()
    pinned = mechanics.pin_security_descriptor(
        descriptor,
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )

    assert len(observed) == 1
    assert observed[0].obj is pinned._storage
    assert pinned._address == ctypes.addressof(pinned._storage)
    assert bytes(observed[0]) == descriptor


def test_mandatory_label_profile_preserves_dacl_and_label_sacl() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    pinned = mechanics.pin_security_descriptor(
        _mandatory_label_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL,
    )

    observation = pinned.observation
    assert observation.control == 0x8014
    assert observation.owner.binary == _TEST_ADMIN_SID
    assert observation.group.binary == _TEST_ADMIN_SID
    assert observation.dacl_present is True
    assert observation.dacl_null is False
    assert observation.dacl_revision == 4
    assert [(ace.ace_type, ace.mask) for ace in observation.dacl_aces] == [
        (0, 0x00120089)
    ]
    assert observation.sacl_present is True
    assert observation.sacl_null is False
    assert observation.sacl_revision == 2
    assert [
        (ace.ace_type, ace.flags, ace.mask, ace.sid.binary)
        for ace in observation.mandatory_label_aces
    ] == [(0x11, 0, 0x00000001, _TEST_MEDIUM_INTEGRITY_SID)]
    assert world.events == []


@pytest.mark.parametrize(
    ("state", "present", "null", "dacl_revision", "sacl_revision"),
    [
        pytest.param("absent", False, False, None, None, id="absent"),
        pytest.param("null", True, True, None, None, id="null"),
        pytest.param("empty", True, False, 4, 2, id="empty"),
    ],
)
def test_mandatory_label_profile_distinguishes_each_acl_state(
    state: str,
    present: bool,
    null: bool,
    dacl_revision: int | None,
    sacl_revision: int | None,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    descriptor = _descriptor_with_acl_states(
        dacl_state=state,
        sacl_state=state,
    )

    observation = mechanics.pin_security_descriptor(
        descriptor,
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL,
    ).observation

    assert (observation.dacl_present, observation.dacl_null) == (present, null)
    assert observation.dacl_revision == dacl_revision
    assert observation.dacl_aces == ()
    assert (observation.sacl_present, observation.sacl_null) == (present, null)
    assert observation.sacl_revision == sacl_revision
    assert observation.mandatory_label_aces == ()


@pytest.mark.parametrize("dacl_state", ["absent", "null"])
def test_dacl_only_rejects_absent_or_null_dacl(dacl_state: str) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    descriptor = _descriptor_with_acl_states(
        dacl_state=dacl_state,
        sacl_state="absent",
    )

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        mechanics.pin_security_descriptor(
            descriptor,
            profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
        )

    assert exc_info.value.code == "unsupported_descriptor"


def test_dacl_only_preserves_null_sacl_but_rejects_populated_sacl() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    null_sacl = _descriptor_with_acl_states(
        dacl_state="empty",
        sacl_state="null",
    )

    observation = mechanics.pin_security_descriptor(
        null_sacl,
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    ).observation

    assert observation.sacl_present is True
    assert observation.sacl_null is True
    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        mechanics.pin_security_descriptor(
            _mandatory_label_descriptor(),
            profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
        )
    assert exc_info.value.code == "unsupported_descriptor"


@pytest.mark.parametrize(
    ("descriptor", "profile", "exception_type", "message"),
    [
        pytest.param(
            bytearray(_dacl_only_descriptor()),
            "dacl_only",
            TypeError,
            "descriptor_bytes must be exact bytes",
            id="bytearray",
        ),
        pytest.param(
            memoryview(_dacl_only_descriptor()),
            "dacl_only",
            TypeError,
            "descriptor_bytes must be exact bytes",
            id="memoryview",
        ),
        pytest.param(
            _DescriptorBytesSubclass(_dacl_only_descriptor()),
            "dacl_only",
            TypeError,
            "descriptor_bytes must be exact bytes",
            id="bytes-subclass",
        ),
        pytest.param(
            _dacl_only_descriptor(),
            1,
            TypeError,
            "profile must be exact str",
            id="profile-type",
        ),
        pytest.param(
            _dacl_only_descriptor(),
            "other",
            ValueError,
            "Unsupported Windows descriptor profile",
            id="profile-value",
        ),
        pytest.param(
            b"\0" * 19,
            "dacl_only",
            ValueError,
            "descriptor_bytes length is outside the supported boundary",
            id="below-minimum",
        ),
        pytest.param(
            b"\0" * 131073,
            "dacl_only",
            ValueError,
            "descriptor_bytes length is outside the supported boundary",
            id="above-maximum",
        ),
    ],
)
def test_invalid_descriptor_callers_stop_before_parser(
    monkeypatch,
    descriptor: object,
    profile: object,
    exception_type: type[Exception],
    message: str,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    def unexpected_parser(_raw):
        raise AssertionError("invalid caller reached descriptor parser")

    monkeypatch.setattr(module, "_parse_dacl_only_descriptor", unexpected_parser)
    monkeypatch.setattr(
        module,
        "_parse_mandatory_label_descriptor",
        unexpected_parser,
    )

    with pytest.raises(exception_type) as exc_info:
        mechanics.pin_security_descriptor(descriptor, profile=profile)

    assert str(exc_info.value) == message
    assert world.events == []


def test_descriptor_size_boundaries_are_inclusive_before_structure() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        mechanics.pin_security_descriptor(
            b"\0" * 20,
            profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
        )
    assert exc_info.value.code == "malformed_descriptor"

    maximum = _dacl_only_descriptor().ljust(131072, b"\0")
    pinned = mechanics.pin_security_descriptor(
        maximum,
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )
    assert ctypes.sizeof(pinned._storage) == 131072
    assert pinned.observation.dacl_present is True


@pytest.mark.parametrize("case", ["trailing_zero", "acl_zero_padding"])
def test_dacl_only_accepts_zero_padding(case: str) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    pinned = mechanics.pin_security_descriptor(
        _descriptor_variant(_dacl_only_descriptor(), case),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )

    assert pinned.observation.dacl_present is True


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        pytest.param("descriptor_revision", "malformed_descriptor"),
        pytest.param("descriptor_sbz1", "malformed_descriptor"),
        pytest.param("missing_self_relative", "malformed_descriptor"),
        pytest.param("owner_absent", "unsupported_descriptor"),
        pytest.param("group_absent", "unsupported_descriptor"),
        pytest.param("dacl_absent", "unsupported_descriptor"),
        pytest.param("dacl_not_present", "unsupported_descriptor"),
        pytest.param("owner_out_of_bounds", "malformed_descriptor"),
        pytest.param("group_out_of_bounds", "malformed_descriptor"),
        pytest.param("dacl_out_of_bounds", "malformed_descriptor"),
        pytest.param("owner_inside_header", "malformed_descriptor"),
        pytest.param("group_inside_header", "malformed_descriptor"),
        pytest.param("dacl_inside_header", "malformed_descriptor"),
        pytest.param("trailing_nonzero", "malformed_descriptor"),
        pytest.param("unaligned_owner", "malformed_descriptor"),
        pytest.param("unaligned_group", "malformed_descriptor"),
        pytest.param("unaligned_dacl", "malformed_descriptor"),
        pytest.param("partial_owner_group_overlap", "malformed_descriptor"),
        pytest.param("dacl_aliases_owner", "malformed_descriptor"),
        pytest.param("dacl_aliases_group", "malformed_descriptor"),
        pytest.param("sid_revision", "malformed_descriptor"),
        pytest.param("truncated_declared_ace_sid", "malformed_descriptor"),
        pytest.param("sacl_present", "unsupported_descriptor"),
        pytest.param("acl_revision", "unsupported_descriptor"),
        pytest.param("acl_sbz1", "malformed_descriptor"),
        pytest.param("acl_sbz2", "malformed_descriptor"),
        pytest.param("acl_size_short", "malformed_descriptor"),
        pytest.param("acl_size_long", "malformed_descriptor"),
        pytest.param("ace_count_over_cap", "malformed_descriptor"),
        pytest.param("ace_count_mismatch", "malformed_descriptor"),
        pytest.param("ace_size_short", "malformed_descriptor"),
        pytest.param("ace_size_long", "malformed_descriptor"),
        pytest.param("unsupported_ace", "unsupported_descriptor"),
        pytest.param("unknown_ace_flag", "unsupported_descriptor"),
        pytest.param("acl_nonzero_padding", "malformed_descriptor"),
    ],
)
def test_dacl_only_descriptor_failures_have_shared_classification(
    case: str,
    expected_code: str,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        mechanics.pin_security_descriptor(
            _descriptor_variant(_dacl_only_descriptor(), case),
            profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
        )

    assert exc_info.value.code == expected_code
    assert world.events == []


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        pytest.param("sacl_not_present", "malformed_descriptor"),
        pytest.param("dacl_not_present", "malformed_descriptor"),
        pytest.param("unaligned_sacl", "malformed_descriptor"),
        pytest.param("sacl_aliases_owner", "malformed_descriptor"),
        pytest.param("sacl_aliases_dacl", "malformed_descriptor"),
        pytest.param("sacl_inside_dacl", "malformed_descriptor"),
        pytest.param("sacl_revision", "unsupported_descriptor"),
        pytest.param("unsupported_sacl_ace", "unsupported_descriptor"),
        pytest.param("sacl_nonzero_padding", "malformed_descriptor"),
    ],
)
def test_mandatory_label_descriptor_failures_have_shared_classification(
    case: str,
    expected_code: str,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        mechanics.pin_security_descriptor(
            _mandatory_descriptor_variant(_mandatory_label_descriptor(), case),
            profile=module.WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL,
        )

    assert exc_info.value.code == expected_code


def test_mandatory_label_profile_preserves_raw_label_flags_and_mask() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    descriptor = _mandatory_descriptor_variant(
        _mandatory_label_descriptor(),
        "raw_label_values",
    )

    observation = mechanics.pin_security_descriptor(
        descriptor,
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_MANDATORY_LABEL,
    ).observation

    label = observation.mandatory_label_aces[0]
    assert label.flags == 0xFF
    assert label.mask == 0xFFFFFFFF


def test_map_file_mask_uses_exact_mapping_on_fresh_dword() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    raw_mask = 0x40000002

    mapped = mechanics.map_file_mask(raw_mask)

    assert raw_mask == 0x40000002
    assert mapped == 0x00120116
    assert world.events == [
        (
            "map_generic",
            0x40000002,
            (0x00120089, 0x00120116, 0x001200A0, 0x001F01FF),
        )
    ]


@pytest.mark.parametrize(
    ("raw_mask", "exception_type", "message"),
    [
        pytest.param(
            True,
            TypeError,
            "raw_mask must be exact int",
            id="bool",
        ),
        pytest.param(
            _MaskIntSubclass(1),
            TypeError,
            "raw_mask must be exact int",
            id="int-subclass",
        ),
        pytest.param(
            1.0,
            TypeError,
            "raw_mask must be exact int",
            id="float",
        ),
        pytest.param(
            -1,
            ValueError,
            "raw_mask is outside the DWORD boundary",
            id="negative",
        ),
        pytest.param(
            0x100000000,
            ValueError,
            "raw_mask is outside the DWORD boundary",
            id="overflow",
        ),
    ],
)
def test_invalid_map_masks_fail_before_native_call(
    raw_mask: object,
    exception_type: type[Exception],
    message: str,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )

    with pytest.raises(exception_type) as exc_info:
        mechanics.map_file_mask(raw_mask)

    assert str(exc_info.value) == message
    assert world.events == []


def test_access_scope_owns_one_exact_duplicate_and_pinned_descriptor() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )

    scope = session.open_access_check(pinned)

    assert scope._descriptor is pinned
    for owner in (mechanics, session, pinned, scope):
        _assert_owner_aliasing_is_rejected(owner)
    assert not hasattr(scope, "__enter__")
    assert not hasattr(scope, "__del__")
    assert [event for event in world.events if event[0] == "duplicate_token"] == [
        (
            "duplicate_token",
            world.baseline_handle,
            0x0008,
            None,
            2,
            2,
        )
    ]
    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        session.open_access_check(pinned)
    assert exc_info.value.code == "observation_failed"
    assert len(
        [event for event in world.events if event[0] == "duplicate_token"]
    ) == 1

    scope.close()
    scope.close()
    session.close()

    assert world.closed_handles == [
        world.duplicate_handle,
        world.baseline_handle,
    ]


def _open_access_world(module, world: _TokenWorld):
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )
    scope = session.open_access_check(pinned)
    return mechanics, session, pinned, scope


@pytest.mark.parametrize(
    ("access_case", "expected_denied"),
    [
        pytest.param("deny", True),
        pytest.param("grant", False),
    ],
)
def test_access_scope_returns_exact_policy_neutral_denial(
    access_case: str,
    expected_denied: bool,
) -> None:
    module = _load_module()
    world = _TokenWorld(access_case=access_case)
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )
    scope = session.open_access_check(pinned)

    denial = scope.check_denial(raw_mask=0x00000002)

    assert denial.raw_mask == 0x00000002
    assert denial.mapped_mask == 0x00000002
    assert denial.denied is expected_denied
    assert [event for event in world.events if event[0] == "access_check"] == [
        (
            "access_check",
            pinned._address,
            world.duplicate_handle,
            0x00000002,
            (0x00120089, 0x00120116, 0x001200A0, 0x001F01FF),
            20,
            True,
            0xFFFFFFFF,
            -1,
        )
    ]

    scope.close()
    session.close()


def test_access_scope_accepts_every_closed_mutation_mask_sequentially() -> None:
    module = _load_module()
    world = _TokenWorld()
    _mechanics, session, _pinned, scope = _open_access_world(module, world)
    masks = (
        0x00000002,
        0x00000004,
        0x00000010,
        0x00000040,
        0x00000100,
        0x00010000,
        0x00040000,
        0x00080000,
    )

    denials = tuple(scope.check_denial(raw_mask=mask) for mask in masks)

    assert tuple(denial.raw_mask for denial in denials) == masks
    assert tuple(denial.mapped_mask for denial in denials) == masks
    assert all(denial.denied for denial in denials)
    assert len(
        [event for event in world.events if event[0] == "access_check"]
    ) == len(masks)
    scope.close()
    session.close()


@pytest.mark.parametrize(
    "raw_mask",
    [
        0,
        0x00000006,
        0x01000000,
        0x02000000,
        0x10000000,
        0xFFFFFFFF,
    ],
)
def test_access_scope_rejects_masks_outside_closed_mutation_set(
    raw_mask: object,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )
    scope = session.open_access_check(pinned)
    before = list(world.events)

    with pytest.raises(
        ValueError,
        match="^raw_mask is outside the mutation-denial boundary$",
    ):
        scope.check_denial(raw_mask=raw_mask)

    assert world.events == before
    scope.close()
    session.close()


@pytest.mark.parametrize(
    "raw_mask",
    [
        True,
        _MaskIntSubclass(0x00000002),
        2.0,
    ],
)
def test_access_scope_rejects_non_exact_integer_masks(
    raw_mask: object,
) -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )
    scope = session.open_access_check(pinned)
    before = list(world.events)

    with pytest.raises(TypeError, match="^raw_mask must be exact int$"):
        scope.check_denial(raw_mask=raw_mask)

    assert world.events == before
    scope.close()
    session.close()


def test_access_scope_rejects_foreign_owners_before_native_execution() -> None:
    module = _load_module()
    first_world = _TokenWorld()
    second_world = _TokenWorld()
    first = module.bind_windows_security(
        kernel32=first_world.kernel32,
        advapi32=first_world.advapi32,
    )
    second = module.bind_windows_security(
        kernel32=second_world.kernel32,
        advapi32=second_world.advapi32,
    )
    session = first.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    first_pinned = first.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )
    second_pinned = second.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )

    for operation in (
        lambda: session.open_access_check(second_pinned),
        lambda: session.open_access_check(object()),
        lambda: second._open_access_scope(session, second_pinned),
    ):
        first_before = tuple(first_world.events)
        second_before = tuple(second_world.events)
        with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
            operation()
        assert exc_info.value.code == "observation_failed"
        assert tuple(first_world.events) == first_before
        assert tuple(second_world.events) == second_before

    scope = session.open_access_check(first_pinned)
    second_before = tuple(second_world.events)
    for operation in (
        lambda: second._check_denial(scope, raw_mask=0x00000002),
        lambda: second._close_access_scope(scope),
    ):
        with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
            operation()
        assert exc_info.value.code == "observation_failed"
        assert tuple(second_world.events) == second_before

    scope.close()
    session.close()


def test_closed_session_rejects_access_scope_without_native_execution() -> None:
    module = _load_module()
    world = _TokenWorld()
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )
    session.close()
    before = tuple(world.events)

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        session.open_access_check(pinned)

    assert exc_info.value.code == "observation_failed"
    assert tuple(world.events) == before


@pytest.mark.parametrize(
    "duplicate_case",
    ["success_null", "failure_sentinel"],
)
def test_access_scope_duplicate_output_quadrants_never_close_unowned_values(
    duplicate_case: str,
) -> None:
    module = _load_module()
    world = _TokenWorld(duplicate_case=duplicate_case)
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        session.open_access_check(pinned)

    assert exc_info.value.code == "observation_failed"
    assert world.closed_handles == []
    session.close()
    assert world.closed_handles == [world.baseline_handle]


def test_access_scope_duplicate_control_flow_after_write_closes_owned_output() -> None:
    module = _load_module()
    primary = KeyboardInterrupt()
    original_tail = _traceback_tail(_prime_traceback(primary))
    world = _TokenWorld(
        duplicate_exception=primary,
        duplicate_exception_after_write=True,
    )
    mechanics = module.bind_windows_security(
        kernel32=world.kernel32,
        advapi32=world.advapi32,
    )
    session = mechanics.open_token_session(
        profile=module.WINDOWS_TOKEN_PROFILE_BASE,
    )
    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )

    with pytest.raises(KeyboardInterrupt) as exc_info:
        session.open_access_check(pinned)

    assert exc_info.value is primary
    assert _traceback_tail(primary.__traceback__) is original_tail
    assert world.closed_handles == [world.duplicate_handle]
    assert session._scope is None
    session.close()
    assert world.closed_handles == [
        world.duplicate_handle,
        world.baseline_handle,
    ]


def test_access_scope_cleanup_only_rethrow_ignores_active_handler_context() -> None:
    module = _load_module()
    world = _TokenWorld(close_fail_handles=(0x1004,))
    mechanics, session = _open_base_session(module, world)
    pinned = mechanics.pin_security_descriptor(
        _dacl_only_descriptor(),
        profile=module.WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY,
    )
    scope = session.open_access_check(pinned)

    def close_inside_active_handler() -> None:
        try:
            raise RuntimeError("active-handler")
        except RuntimeError:
            scope.close()

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        close_inside_active_handler()

    assert exc_info.value.code == "observation_failed"
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert exc_info.value.__suppress_context__ is False
    assert world.closed_handles == [world.duplicate_handle]
    session.close()
    assert world.closed_handles == [world.duplicate_handle, world.baseline_handle]


@pytest.mark.parametrize(
    "access_case",
    [
        "true_extra_bits",
        "true_missing_bits",
        "status_two",
        "false_nonzero_grant",
        "omitted_status",
        "native_failure_dirty",
        "privilege_short",
        "privilege_long",
        "privilege_count_over_cap",
        "privilege_bad_control",
        "privilege_nonzero_trailing",
        "denial_nonzero_privilege_output",
    ],
)
def test_access_scope_rejects_malformed_access_and_privilege_outputs(
    access_case: str,
) -> None:
    module = _load_module()
    world = _TokenWorld(access_case=access_case)
    _mechanics, session, _pinned, scope = _open_access_world(module, world)

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        scope.check_denial(raw_mask=0x00000002)

    assert exc_info.value.code == "observation_failed"
    assert len(
        [event for event in world.events if event[0] == "access_check"]
    ) == 1
    scope.close()
    session.close()
    assert world.closed_handles == [
        world.duplicate_handle,
        world.baseline_handle,
    ]


def test_access_scope_native_exception_is_sanitized_without_raw_text() -> None:
    module = _load_module()
    world = _TokenWorld(access_exception=RuntimeError(r"C:\private\token"))
    _mechanics, session, _pinned, scope = _open_access_world(module, world)

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        scope.check_denial(raw_mask=0x00000002)

    assert exc_info.value.code == "observation_failed"
    assert "private" not in repr(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    scope.close()
    session.close()


def test_access_scope_close_failure_is_final_and_allows_reopen() -> None:
    module = _load_module()
    world = _TokenWorld(close_fail_handles=(0x1004,))
    _mechanics, session, pinned, scope = _open_access_world(module, world)

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        scope.close()

    assert exc_info.value.code == "observation_failed"
    frozen_events = tuple(world.events)
    scope.close()
    assert tuple(world.events) == frozen_events
    replacement = session.open_access_check(pinned)
    replacement.close()
    session.close()
    assert world.closed_handles == [0x1004, 0x1005, world.baseline_handle]


def test_session_close_orders_scope_before_baseline_and_links_both_failures() -> None:
    module = _load_module()
    world = _TokenWorld(close_fail_handles=(0x1004, 0x1001))
    _mechanics, session, _pinned, scope = _open_access_world(module, world)

    with pytest.raises(module.WindowsSecurityMechanicsError) as exc_info:
        session.close()

    assert exc_info.value.code == "observation_failed"
    assert type(exc_info.value.__cause__) is module.WindowsSecurityMechanicsError
    assert exc_info.value.__cause__.code == "observation_failed"
    assert world.closed_handles == [world.duplicate_handle, world.baseline_handle]
    frozen_events = tuple(world.events)
    session.close()
    scope.close()
    with pytest.raises(module.WindowsSecurityMechanicsError) as closed_exc:
        scope.check_denial(raw_mask=0x00000002)
    assert closed_exc.value.code == "observation_failed"
    assert tuple(world.events) == frozen_events
