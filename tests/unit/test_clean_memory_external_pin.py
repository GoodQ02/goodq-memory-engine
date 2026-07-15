from __future__ import annotations

import ast
import builtins
import ctypes
import dataclasses
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from steps.common.windows_held_handle import (
    WindowsDirectoryEntry,
    WindowsHeldHandleError,
    WindowsObjectSnapshot,
)
from steps.common.windows_security_mechanics import (
    WINDOWS_TOKEN_PROFILE_BASE,
    WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
    WindowsSecurityMechanics,
)


MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "cli" / "clean_memory_external_pin.py"
)

_ERRORS = {
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


def _load_module():
    return importlib.import_module("cli.clean_memory_external_pin")


def _identity(file_id: str, *, object_kind: str) -> dict[str, str]:
    return {
        "file_id": file_id,
        "file_id_kind": "ntfs_file_index_64",
        "object_kind": object_kind,
        "schema": "goodq.windows-file-identity.v1",
        "volume_serial": "0123456789abcdef",
    }


def _evidence_projection() -> dict[str, object]:
    return {
        "anchor_identity": _identity("0000000000000001", object_kind="directory"),
        "dedicated_directory_identities": [
            _identity("0000000000000002", object_kind="directory"),
            _identity("0000000000000003", object_kind="directory"),
            _identity("0000000000000004", object_kind="directory"),
        ],
        "enrolled_reader_identity_sha256": "1" * 64,
        "manifest_sha256": "2" * 64,
        "pin_file_identity": _identity(
            "0000000000000005", object_kind="regular_file"
        ),
        "platform": "windows",
        "schema": "goodq.clean-memory-external-pin-evidence.v1",
        "security_policy_sha256": "3" * 64,
        "source_id": "goodq.clean-memory-protected-authority-pin.primary.v1",
        "source_schema": "goodq.clean-memory-external-pin-source.v1",
    }


class _NativeCall:
    def __init__(self) -> None:
        self.argtypes = None
        self.restype = None

    def __call__(self, *_args):
        raise AssertionError("native function was bound but must not be called")


def _native_dlls() -> dict[str, SimpleNamespace]:
    return {
        "kernel32": SimpleNamespace(
            GetCurrentThread=_NativeCall(),
            GetCurrentProcess=_NativeCall(),
            CloseHandle=_NativeCall(),
            LocalFree=_NativeCall(),
        ),
        "shell32": SimpleNamespace(SHGetKnownFolderPath=_NativeCall()),
        "ole32": SimpleNamespace(CoTaskMemFree=_NativeCall()),
        "advapi32": SimpleNamespace(
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
        ),
    }


def _install_fake_windll(monkeypatch, dlls: dict[str, SimpleNamespace]):
    calls: list[tuple[str, bool]] = []

    def fake_windll(name: str, *, use_last_error: bool):
        calls.append((name, use_last_error))
        return dlls[name.casefold()]

    monkeypatch.setattr(ctypes, "WinDLL", fake_windll)
    return calls


_PIN_NAME = "protected-boundaries.sha256"
_TOKEN_NATIVE_CALL_ORDER = (
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
_FILE_GENERIC_MAPPING = (
    0x00120089,
    0x00120116,
    0x001200A0,
    0x001F01FF,
)
_ROLE_ORDER = (
    "anchor",
    "goodq",
    "authority",
    "clean_memory",
    "pin",
)
_SECRET_MARKER = r"SECRET C:\private\reader.sid S-1-5-21-999"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sid(authority: int, *subauthorities: int) -> bytes:
    assert 0 <= authority < (1 << 48)
    assert len(subauthorities) <= 15
    return (
        bytes((1, len(subauthorities)))
        + authority.to_bytes(6, "big")
        + b"".join(value.to_bytes(4, "little") for value in subauthorities)
    )


def _sid_text(value: bytes) -> str:
    count = value[1]
    authority = int.from_bytes(value[2:8], "big")
    subauthorities = [
        int.from_bytes(value[8 + index * 4 : 12 + index * 4], "little")
        for index in range(count)
    ]
    return "-".join(("S", "1", str(authority), *(str(item) for item in subauthorities)))


_SYSTEM_SID = _sid(5, 18)
_ADMIN_SID = _sid(5, 32, 544)
_USERS_SID = _sid(5, 32, 545)
_MEDIUM_INTEGRITY_SID = _sid(16, 8192)
_DEFAULT_READER_SID = _sid(5, 21, 165, 4242)


def _ace(
    ace_type: int,
    mask: int,
    sid: bytes,
    *,
    flags: int = 0,
) -> bytes:
    return struct.pack("<BBHI", ace_type, flags, 8 + len(sid), mask) + sid


def _acl(aces: tuple[bytes, ...], *, revision: int = 2, padding: bytes = b"") -> bytes:
    size = 8 + sum(len(ace) for ace in aces) + len(padding)
    return struct.pack("<BBHHH", revision, 0, size, len(aces), 0) + b"".join(aces) + padding


def _descriptor(
    *,
    reader_sid: bytes,
    reader_mask: int,
    control: int,
    anchor: bool = False,
) -> bytes:
    owner = _ADMIN_SID
    dacl = _acl(
        (
            _ace(0, 0x001F01FF, _SYSTEM_SID),
            _ace(0, 0x001F01FF, _ADMIN_SID),
            _ace(0, reader_mask, reader_sid),
        )
    )
    owner_offset = 20
    group_offset = owner_offset  # Exact identical owner/group SID alias is accepted.
    dacl_offset = owner_offset + len(owner)
    return (
        struct.pack(
            "<BBHIIII",
            1,
            0,
            control,
            owner_offset,
            group_offset,
            0,
            dacl_offset,
        )
        + owner
        + dacl
    )


def _descriptor_from_components(
    *,
    owner: bytes,
    group: bytes,
    aces: tuple[bytes, ...],
    control: int,
    acl_revision: int = 2,
    owner_group_alias: bool = False,
    header_gap: bytes = b"",
    component_gap: bytes = b"",
) -> bytes:
    """Build detached self-relative bytes without relying on production helpers."""

    data = bytearray(b"\0" * 20)
    data.extend(header_gap)
    while len(data) % 4:
        data.append(0)
    owner_offset = len(data)
    data.extend(owner)
    if owner_group_alias:
        assert owner == group
        group_offset = owner_offset
    else:
        data.extend(component_gap)
        while len(data) % 4:
            data.append(0)
        group_offset = len(data)
        data.extend(group)
    data.extend(component_gap)
    while len(data) % 4:
        data.append(0)
    dacl_offset = len(data)
    data.extend(_acl(aces, revision=acl_revision))
    struct.pack_into(
        "<BBHIIII",
        data,
        0,
        1,
        0,
        control,
        owner_offset,
        group_offset,
        0,
        dacl_offset,
    )
    return bytes(data)


def _ordinary_policy_aces(
    reader_sid: bytes,
    reader_mask: int,
    *,
    reader_flags: int = 0,
) -> tuple[bytes, ...]:
    return (
        _ace(0, 0x001F01FF, _SYSTEM_SID),
        _ace(0, 0x001F01FF, _ADMIN_SID),
        _ace(0, reader_mask, reader_sid, flags=reader_flags),
    )


def _descriptor_variant(value: bytes, case: str) -> bytes:
    data = bytearray(value)
    owner_offset = struct.unpack_from("<I", data, 4)[0]
    group_offset = struct.unpack_from("<I", data, 8)[0]
    dacl_offset = struct.unpack_from("<I", data, 16)[0]
    if case == "truncated_header":
        return bytes(data[:19])
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
    elif case == "owner_inside_header":
        struct.pack_into("<I", data, 4, 16)
    elif case == "group_inside_header":
        struct.pack_into("<I", data, 8, 16)
    elif case == "dacl_inside_header":
        struct.pack_into("<I", data, 16, 16)
    elif case == "group_out_of_bounds":
        struct.pack_into("<I", data, 8, len(data) + 4)
    elif case == "dacl_out_of_bounds":
        struct.pack_into("<I", data, 16, len(data) + 4)
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
    elif case == "null_sacl_present":
        control = struct.unpack_from("<H", data, 2)[0]
        struct.pack_into("<H", data, 2, control | 0x0010)
    elif case == "sid_revision":
        data[owner_offset] = 2
    elif case == "truncated_declared_ace_sid":
        first_ace_sid = dacl_offset + 8 + 8
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
    elif case == "dedicated_inheritance_flag":
        data[dacl_offset + 9] = 0x01
    elif case == "dedicated_auto_inherited":
        control = struct.unpack_from("<H", data, 2)[0]
        struct.pack_into("<H", data, 2, control | 0x0400)
    elif case == "reader_mask":
        offset = dacl_offset + 8
        for _ in range(2):
            offset += struct.unpack_from("<H", data, offset + 2)[0]
        struct.pack_into("<I", data, offset + 4, 0x001F01FF)
    elif case in {"acl_zero_padding", "acl_nonzero_padding"}:
        old_size = struct.unpack_from("<H", data, dacl_offset + 2)[0]
        struct.pack_into("<H", data, dacl_offset + 2, old_size + 4)
        data.extend(b"\0\0\0\0" if case == "acl_zero_padding" else b"\0\0\0\x01")
    else:
        raise AssertionError(f"unknown descriptor case: {case}")
    return bytes(data)


def _descriptor_with_group_dacl_partial_overlap(reader_sid: bytes) -> bytes:
    owner = _ADMIN_SID
    dacl = _acl((_ace(1, 0, reader_sid),))
    owner_offset = 20
    group_offset = owner_offset + len(owner)
    dacl_offset = group_offset + 8
    group_prefix = bytes((1, 2)) + (5).to_bytes(6, "big")
    assert len(group_prefix) == 8
    assert dacl[:2] in {b"\x02\x00", b"\x04\x00"}
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
        + owner
        + group_prefix
        + dacl
    )


def _directory_snapshot(file_id: int) -> WindowsObjectSnapshot:
    return WindowsObjectSnapshot(
        volume_serial=0x0123456789ABCDEF,
        file_id_kind="ntfs_file_index_64",
        file_id=file_id,
        object_kind="directory",
        size_bytes=0,
        mtime_ns=None,
        allocation_size=0,
        link_count=1,
        attributes=0x10,
        reparse_tag=0,
        last_write_ticks=132_000_000_000_000_000 + file_id,
        change_ticks=132_000_000_000_100_000 + file_id,
        streams=(),
    )


def _file_snapshot(file_id: int) -> WindowsObjectSnapshot:
    return WindowsObjectSnapshot(
        volume_serial=0x0123456789ABCDEF,
        file_id_kind="ntfs_file_index_64",
        file_id=file_id,
        object_kind="regular_file",
        size_bytes=65,
        mtime_ns=1_700_000_000_000_000_000,
        allocation_size=4096,
        link_count=1,
        attributes=0,
        reparse_tag=0,
        last_write_ticks=133_444_736_000_000_000,
        change_ticks=133_444_736_000_000_001,
        streams=(("::$DATA", 65, 4096),),
    )


@dataclasses.dataclass(frozen=True)
class _TokenSpec:
    user_sid: bytes = _DEFAULT_READER_SID
    groups: tuple[tuple[bytes, int], ...] = ((_USERS_SID, 0x00000007),)
    privileges: tuple[tuple[tuple[int, int], int], ...] = (((0x17, 0), 0x2),)
    restricted_sids: tuple[tuple[bytes, int], ...] = ()
    integrity_sid: bytes = _MEDIUM_INTEGRITY_SID
    integrity_attributes: int = 0x20
    elevation_type: int = 1
    is_elevated: int = 0
    has_restrictions: int = 0
    ui_access: int = 0
    is_app_container: int = 0
    token_type: int = 1


@dataclasses.dataclass(frozen=True)
class _Held:
    role: str


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


class _ScriptedNativeCall:
    def __init__(self, name: str, implementation) -> None:
        self.name = name
        self.implementation = implementation
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.implementation(*args)


class _RecordingSecurityMechanics:
    def __init__(self, world: "_ReaderWorld", delegate: WindowsSecurityMechanics) -> None:
        self._world = world
        self._delegate = delegate

    def open_token_session(self, *, profile: str):
        self._world.security_session_profiles.append(profile)
        if self._world.security_open_exception is not None:
            raise self._world.security_open_exception
        session = self._delegate.open_token_session(profile=profile)
        self._world.security_baseline_snapshots.append(session.baseline_snapshot)
        return session

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)


class _ReaderWorld:
    """Complete hermetic external boundary; assertions remain in reader tests."""

    def __init__(self, *, token: _TokenSpec | None = None) -> None:
        self.events: list[tuple[Any, ...]] = []
        self.security_session_profiles: list[str] = []
        self.security_baseline_snapshots: list[object] = []
        self.security_open_exception: BaseException | None = None
        self.known_folder_path = r"C:\ProgramData"
        self.known_folder_hresult = 0
        self.known_folder_output = True
        self.known_folder_call_exception: BaseException | None = None
        self.known_folder_free_exception: BaseException | None = None
        self.known_folder_buffers: dict[int, object] = {}
        self.freed_known_folder: list[int] = []
        self.filesystem = "NTFS"
        self.payload = b"a" * 64 + b"\n"
        self.explicit_eof = True
        self.token = token or _TokenSpec()
        self.token_buffer_case: str | None = None
        self.token_query_target: int | None = None
        self.statistics_drift_field: str | None = None
        self.statistics_group_count: int | None = None
        self.statistics_privilege_count: int | None = None
        self.vary_undefined_impersonation = False
        self.outer_token_drift_at: int | None = None
        self.absence_post_token_drift_role: str | None = None
        self.thread_case = "no_token_sentinel"
        self.comparison_thread_at: int | None = None
        self.process_case = "success"
        self.duplicate_case = "success"
        self.access_case = "deny"
        self.missing_role: str | None = None
        self.duplicate_role: str | None = None
        self.membership_mutation_role: str | None = None
        self.second_proof_membership_mutation_role: str | None = None
        self.proof_target_appearance_role: str | None = None
        self.absence_sibling_mutation_role: str | None = None
        self.absence_sibling_mutation_field: str | None = None
        self.recheck_membership_role: str | None = None
        self.recheck_membership_replace_role: str | None = None
        self.recheck_snapshot_role: str | None = None
        self.recheck_descriptor_role: str | None = None
        self.recheck_stream_role: str | None = None
        self.read_snapshot_role: str | None = None
        self.backend_failure: tuple[str, str] | None = None
        self.backend_failure_code = "observation_failed"
        self.backend_exception: tuple[str, str, BaseException] | None = None
        self.backend_construction_error: str | None = None
        self.backend_close_failure = False
        self.native_close_failure_kind: str | None = None
        self.native_close_failure_at: int | None = None
        self.token_snapshot_exception_kind: str | None = None
        self.token_snapshot_exception: BaseException | None = None
        self.access_exception: BaseException | None = None

        self.reader_sid = self.token.user_sid
        self.descriptors = {
            "anchor": _descriptor(
                reader_sid=self.reader_sid,
                reader_mask=0x001200A1,
                control=0x8004,
                anchor=True,
            ),
            "goodq": _descriptor(
                reader_sid=self.reader_sid,
                reader_mask=0x001200A1,
                control=0x9004,
            ),
            "authority": _descriptor(
                reader_sid=self.reader_sid,
                reader_mask=0x001200A1,
                control=0x9004,
            ),
            "clean_memory": _descriptor(
                reader_sid=self.reader_sid,
                reader_mask=0x001200A1,
                control=0x9004,
            ),
            "pin": _descriptor(
                reader_sid=self.reader_sid,
                reader_mask=0x00120089,
                control=0x9004,
            ),
        }
        self.snapshots = {
            "root": _directory_snapshot(6),
            "anchor": _directory_snapshot(1),
            "goodq": _directory_snapshot(2),
            "authority": _directory_snapshot(3),
            "clean_memory": _directory_snapshot(4),
            "pin": _file_snapshot(5),
        }
        self.child_specs = {
            "root": ("anchor", "ProgramData", 1, 0x10),
            "anchor": ("goodq", "GoodQ", 2, 0x10),
            "goodq": ("authority", "authority", 3, 0x10),
            "authority": ("clean_memory", "clean-memory", 4, 0x10),
            "clean_memory": ("pin", _PIN_NAME, 5, 0),
        }
        self.role_by_file_id = {
            file_id: role for role, _name, file_id, _attributes in self.child_specs.values()
        }
        self.backend: _FakeHeldHandleBackend | None = None

        self._next_process_handle = 0x1000
        self._next_duplicate_handle = 0x2000
        self._handle_kinds: dict[int, str] = {}
        self._closed_handles: set[int] = set()
        self._close_counts: dict[str, int] = {}
        self._thread_calls = 0
        self._process_calls = 0
        self._duplicate_index = 0
        self._current_access_role: str | None = None
        self._access_index = 0
        self._snapshot_ordinal = 0
        self._snapshot_by_handle: dict[int, int] = {}
        self._stats_calls_by_handle: dict[int, int] = {}
        self.max_live_duplicates = 0
        self._live_duplicates: set[int] = set()

        self.native = SimpleNamespace(
            kernel32=SimpleNamespace(
                GetCurrentThread=_ScriptedNativeCall(
                    "GetCurrentThread", self._get_current_thread
                ),
                GetCurrentProcess=_ScriptedNativeCall(
                    "GetCurrentProcess", self._get_current_process
                ),
                CloseHandle=_ScriptedNativeCall("CloseHandle", self._close_handle),
                LocalFree=_ScriptedNativeCall(
                    "LocalFree", self._unexpected_backend_native_call
                ),
            ),
            shell32=SimpleNamespace(
                SHGetKnownFolderPath=_ScriptedNativeCall(
                    "SHGetKnownFolderPath", self._known_folder
                )
            ),
            ole32=SimpleNamespace(
                CoTaskMemFree=_ScriptedNativeCall(
                    "CoTaskMemFree", self._free_known_folder
                )
            ),
            advapi32=SimpleNamespace(
                OpenThreadToken=_ScriptedNativeCall(
                    "OpenThreadToken", self._open_thread_token
                ),
                OpenProcessToken=_ScriptedNativeCall(
                    "OpenProcessToken", self._open_process_token
                ),
                GetTokenInformation=_ScriptedNativeCall(
                    "GetTokenInformation", self._get_token_information
                ),
                LookupPrivilegeValueW=_ScriptedNativeCall(
                    "LookupPrivilegeValueW", self._lookup_privilege
                ),
                DuplicateTokenEx=_ScriptedNativeCall(
                    "DuplicateTokenEx", self._duplicate_token
                ),
                MapGenericMask=_ScriptedNativeCall(
                    "MapGenericMask", self._map_generic_mask
                ),
                AccessCheck=_ScriptedNativeCall("AccessCheck", self._access_check),
                GetSecurityInfo=_ScriptedNativeCall(
                    "GetSecurityInfo", self._unexpected_backend_native_call
                ),
                IsValidSecurityDescriptor=_ScriptedNativeCall(
                    "IsValidSecurityDescriptor", self._unexpected_backend_native_call
                ),
                GetSecurityDescriptorControl=_ScriptedNativeCall(
                    "GetSecurityDescriptorControl", self._unexpected_backend_native_call
                ),
                GetSecurityDescriptorLength=_ScriptedNativeCall(
                    "GetSecurityDescriptorLength", self._unexpected_backend_native_call
                ),
            ),
        )

    def bind_native(self):
        self.events.append(("native.bind",))
        return self.native

    def load_backend(self):
        self.events.append(("backend.construct", "security_read"))
        if self.backend_construction_error is not None:
            raise WindowsHeldHandleError(self.backend_construction_error)
        if self.backend is not None:
            raise AssertionError("backend factory called more than once")
        self.backend = _FakeHeldHandleBackend(self)
        return self.backend

    def _set_last_error(self, value: int) -> None:
        ctypes.set_last_error(value)

    def _unexpected_backend_native_call(self, *_args):
        raise AssertionError("reader bypassed the public held-handle backend")

    def _get_current_thread(self) -> int:
        self.events.append(("native.current_thread",))
        return 0xFFFF0001

    def _get_current_process(self) -> int:
        self.events.append(("native.current_process",))
        return 0xFFFF0002

    def _known_folder(self, guid, flags, token, output) -> int:
        guid_bytes = ctypes.string_at(guid, 16)
        self.events.append(
            ("known_folder", guid_bytes, int(flags), _raw_handle(token))
        )
        if self.known_folder_output:
            buffer = ctypes.create_unicode_buffer(self.known_folder_path)
            address = ctypes.addressof(buffer)
            self.known_folder_buffers[address] = buffer
            _write_handle(output, address)
        else:
            _write_handle(output, None)
        if self.known_folder_call_exception is not None:
            raise self.known_folder_call_exception
        return self.known_folder_hresult

    def _free_known_folder(self, pointer) -> None:
        raw = _raw_handle(pointer)
        self.events.append(("known_folder.free", raw))
        if raw is not None:
            self.freed_known_folder.append(raw)
        if self.known_folder_free_exception is not None:
            raise self.known_folder_free_exception

    def _open_thread_token(self, thread, access, open_as_self, output) -> int:
        self._thread_calls += 1
        self.events.append(
            (
                "token.open_thread",
                self._thread_calls,
                _raw_handle(thread),
                int(access),
                int(open_as_self),
            )
        )
        comparison_hit = (
            self.comparison_thread_at is not None
            and self._thread_calls == self.comparison_thread_at
        )
        case = "success_nonnull" if comparison_hit else self.thread_case
        if case == "success_nonnull":
            handle = 0x3000 + self._thread_calls
            _write_handle(output, handle)
            self._handle_kinds[handle] = "thread"
            return 1
        if case == "success_null":
            _write_handle(output, None)
            return 1
        _write_handle(output, 0xDEAD0001)
        self._set_last_error(1008 if case == "no_token_sentinel" else 5)
        return 0

    def _open_process_token(self, process, access, output) -> int:
        self._process_calls += 1
        self.events.append(
            (
                "token.open_process",
                self._process_calls,
                _raw_handle(process),
                int(access),
            )
        )
        if self.process_case == "success_null":
            _write_handle(output, None)
            return 1
        if self.process_case == "failure_sentinel":
            _write_handle(output, 0xDEAD0002)
            self._set_last_error(5)
            return 0
        self._next_process_handle += 1
        handle = self._next_process_handle
        _write_handle(output, handle)
        self._handle_kinds[handle] = "baseline" if self._process_calls == 1 else "transient"
        return 1

    def _lookup_privilege(self, system_name, name, output) -> int:
        self.events.append(("privilege.lookup", system_name, name))
        luid = ctypes.cast(output, ctypes.POINTER(ctypes.c_uint32))
        luid[0] = 0x17
        luid[1] = 0
        return 1

    def _snapshot_index(self, handle: int) -> int:
        if handle not in self._snapshot_by_handle:
            self._snapshot_by_handle[handle] = self._snapshot_ordinal
            self._snapshot_ordinal += 1
        return self._snapshot_by_handle[handle]

    def _statistics_bytes(self, handle: int, phase: int) -> bytes:
        ordinal = self._snapshot_index(handle)
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
        modified_low = 4
        if self.outer_token_drift_at is not None and ordinal >= self.outer_token_drift_at:
            modified_low = 5
        if (
            self.absence_post_token_drift_role is not None
            and self.backend is not None
        ):
            parent = next(
                (
                    parent_role
                    for parent_role, (child, _name, _file_id, _attributes)
                    in self.child_specs.items()
                    if child == self.absence_post_token_drift_role
                ),
                None,
            )
            if parent is not None and self.backend.enumeration_counts.get(parent, 0) >= 3:
                modified_low = 5
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
                modified_low = 5
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
        struct.pack_into("<Ii", data, 48, modified_low, 0)
        if self.token_buffer_case == "statistics_token_type_sentinel":
            struct.pack_into("<i", data, 24, -1)
        elif self.token_buffer_case == "statistics_group_count_sentinel":
            struct.pack_into("<I", data, 40, 0xFFFFFFFF)
        elif self.token_buffer_case == "statistics_privilege_count_sentinel":
            struct.pack_into("<I", data, 44, 0xFFFFFFFF)
        return bytes(data)

    @staticmethod
    def _sid_records_payload(
        records: tuple[tuple[bytes, int], ...],
        *,
        base: int,
    ) -> bytes:
        header = 8
        records_end = header + 16 * len(records)
        data = bytearray(b"\xA5" * (records_end + sum(len(sid) for sid, _ in records)))
        struct.pack_into("<I", data, 0, len(records))
        cursor = records_end
        for index, (sid, attributes) in enumerate(records):
            offset = header + 16 * index
            struct.pack_into("<Q", data, offset, base + cursor)
            struct.pack_into("<I", data, offset + 8, attributes)
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
            data = bytearray(
                self._sid_records_payload(self.token.groups, base=base)
            )
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

    def _required_token_size(self, info_class: int) -> int:
        if info_class == 1:
            return 16 + len(self.token.user_sid)
        if info_class == 2:
            return 8 + 16 * len(self.token.groups) + sum(
                len(sid) for sid, _attributes in self.token.groups
            )
        if info_class == 3:
            return 4 + 12 * len(self.token.privileges)
        if info_class == 11:
            return 8 + 16 * len(self.token.restricted_sids) + sum(
                len(sid) for sid, _attributes in self.token.restricted_sids
            )
        if info_class == 25:
            return 16 + len(self.token.integrity_sid)
        raise AssertionError(f"unexpected variable token class {info_class}")

    def _get_token_information(
        self,
        token_handle,
        info_class,
        buffer,
        buffer_length,
        return_length,
    ) -> int:
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
        elif info in {18, 20, 21, 26, 29} and size >= 4:
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
                "token.input",
                handle,
                info,
                size,
                initial_return_length,
                initial_buffer_state,
            )
        )
        self.events.append(("token.info", handle, info, size, address is not None))
        targeted = self.token_query_target in {None, info}
        if info == 10:
            if targeted and self.token_buffer_case == "statistics_failure_dirty":
                if address is not None:
                    ctypes.memset(address, 0x5A, min(size, 56))
                _write_uint32(return_length, 7)
                self._set_last_error(5)
                return 0
            phase = self._stats_calls_by_handle.get(handle, 0)
            self._stats_calls_by_handle[handle] = phase + 1
            if address is not None and not (
                targeted and self.token_buffer_case == "statistics_omit_output"
            ):
                ctypes.memmove(address, self._statistics_bytes(handle, phase), 56)
            statistics_length = 56
            if targeted and self.token_buffer_case in {
                "fixed_bad_length",
                "statistics_short_length",
            }:
                statistics_length = 55
            elif targeted and self.token_buffer_case == "statistics_long_length":
                statistics_length = 57
            _write_uint32(return_length, statistics_length)
            if phase == 1:
                self.events.append(
                    (
                        "token.snapshot",
                        self._handle_kinds.get(handle),
                        self._snapshot_index(handle),
                        handle,
                    )
                )
                if (
                    self.token_snapshot_exception is not None
                    and self.token_snapshot_exception_kind
                    == self._handle_kinds.get(handle)
                ):
                    raise self.token_snapshot_exception
            return 1
        fixed = {
            18: self.token.elevation_type,
            20: self.token.is_elevated,
            21: self.token.has_restrictions,
            26: self.token.ui_access,
            29: self.token.is_app_container,
        }
        if info in fixed:
            if targeted and self.token_buffer_case == f"fixed_failure_dirty_{info}":
                if address is not None:
                    ctypes.c_int32.from_address(address).value = 0x5A5A5A5A
                _write_uint32(return_length, 7)
                self._set_last_error(5)
                return 0
            if not (
                targeted and self.token_buffer_case == f"omit_fixed_{info}"
            ) and address is not None:
                ctypes.c_int32.from_address(address).value = fixed[info]
            fixed_length = 4
            if targeted and self.token_buffer_case == f"short_fixed_{info}":
                fixed_length = 3
            elif targeted and self.token_buffer_case == f"long_fixed_{info}":
                fixed_length = 5
            _write_uint32(return_length, fixed_length)
            return 1

        required = self._required_token_size(info)
        exact_cap = (
            targeted
            and self.token_buffer_case == "exact_cap_a5_slack"
            and self._handle_kinds.get(handle) == "baseline"
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
                self._set_last_error(5)
                return 0
            self._set_last_error(122)
            return 0
        payload = self._variable_payload(info, address or 0)
        if exact_cap:
            structured_length = len(payload)
            exact_payload = bytearray(b"\xA5" * required)
            exact_payload[:structured_length] = payload
            payload = bytes(exact_payload)
            self.events.append(
                (
                    "token.exact_cap",
                    info,
                    structured_length,
                    len(payload),
                    payload[structured_length:] == b"\xA5" * (required - structured_length),
                )
            )
        ctypes.memmove(address, payload, min(len(payload), size))
        if targeted and self.token_buffer_case == "fill_failure_dirty":
            _write_uint32(return_length, 7)
            self._set_last_error(5)
            return 0
        reported = required
        if targeted and self.token_buffer_case == "size_changed":
            reported += 4
        _write_uint32(return_length, reported)
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
        role = _ROLE_ORDER[self._duplicate_index] if self._duplicate_index < len(_ROLE_ORDER) else "extra"
        self._duplicate_index += 1
        self.events.append(
            (
                "token.duplicate",
                role,
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
            self._set_last_error(5)
            return 0
        self._next_duplicate_handle += 1
        handle = self._next_duplicate_handle
        _write_handle(output, handle)
        self._handle_kinds[handle] = "duplicate"
        self._live_duplicates.add(handle)
        self.max_live_duplicates = max(self.max_live_duplicates, len(self._live_duplicates))
        self._current_access_role = role
        self._access_index = 0
        return 1

    def _map_generic_mask(self, access_mask, mapping) -> None:
        pointer = ctypes.cast(access_mask, ctypes.POINTER(ctypes.c_uint32))
        raw = int(pointer[0])
        values = ctypes.cast(mapping, ctypes.POINTER(ctypes.c_uint32))
        mapping_values = tuple(int(values[index]) for index in range(4))
        mapped = raw & 0x0FFFFFFF
        for bit, replacement in zip(
            (0x80000000, 0x40000000, 0x20000000, 0x10000000),
            mapping_values,
        ):
            if raw & bit:
                mapped |= replacement
        pointer[0] = mapped
        self.events.append(
            (
                "access.map",
                self._current_access_role,
                raw,
                mapped,
                mapping_values,
            )
        )

    def _access_check(
        self,
        descriptor,
        duplicate,
        desired,
        mapping,
        privilege_set,
        privilege_length,
        granted,
        status,
    ) -> int:
        role = self._current_access_role
        rights = _PIN_RIGHTS if role == "pin" else _DIRECTORY_RIGHTS
        right_name, expected = rights[self._access_index]
        self._access_index += 1
        desired_value = int(desired)
        mapping_values = tuple(
            int(ctypes.cast(mapping, ctypes.POINTER(ctypes.c_uint32))[index])
            for index in range(4)
        )
        privilege_capacity = int(
            ctypes.cast(privilege_length, ctypes.POINTER(ctypes.c_uint32))[0]
        )
        privilege_address = _raw_handle(privilege_set)
        privilege_initially_zero = (
            privilege_address is not None
            and 0 <= privilege_capacity <= 49_160
            and ctypes.string_at(privilege_address, privilege_capacity)
            == bytes(privilege_capacity)
        )
        self.events.append(
            (
                "access.check",
                role,
                right_name,
                expected,
                desired_value,
                _raw_handle(duplicate),
                _raw_handle(descriptor),
                mapping_values,
                privilege_capacity,
                privilege_initially_zero,
                int(ctypes.cast(granted, ctypes.POINTER(ctypes.c_uint32))[0]),
                int(ctypes.cast(status, ctypes.POINTER(ctypes.c_int32))[0]),
            )
        )
        if self.access_exception is not None:
            raise self.access_exception
        address = privilege_address
        if address is not None:
            ctypes.memset(address, 0, max(8, int(ctypes.cast(privilege_length, ctypes.POINTER(ctypes.c_uint32))[0])))
        _write_uint32(privilege_length, 8)
        if self.access_case == "native_failure_dirty":
            _write_uint32(privilege_length, 0xFFFFFFFF)
            _write_uint32(granted, 0xFFFFFFFF)
            _write_int32(status, 1)
            self._set_last_error(122)
            return 0
        if self.access_case == "privilege_short":
            _write_uint32(privilege_length, 7)
        elif self.access_case == "privilege_long":
            _write_uint32(privilege_length, 49_161)
        elif self.access_case == "privilege_count_over_cap" and address is not None:
            ctypes.c_uint32.from_address(address).value = 4097
        elif self.access_case == "privilege_bad_control" and address is not None:
            ctypes.c_uint32.from_address(address + 4).value = 2
        elif self.access_case == "privilege_nonzero_trailing" and address is not None:
            _write_uint32(privilege_length, 9)
            ctypes.c_ubyte.from_address(address + 8).value = 1
        elif self.access_case == "denial_nonzero_privilege_output" and address is not None:
            _write_uint32(privilege_length, 20)
            ctypes.c_uint32.from_address(address).value = 1
            ctypes.c_uint32.from_address(address + 4).value = 1
            ctypes.c_uint32.from_address(address + 8).value = 0x17
            ctypes.c_int32.from_address(address + 12).value = 0
            ctypes.c_uint32.from_address(address + 16).value = 0x2

        if self.access_case != "omitted_status":
            if self.access_case == "status_two":
                _write_int32(status, 2)
            else:
                _write_int32(
                    status,
                    1
                    if self.access_case
                    in {"grant", "true_extra_bits", "true_missing_bits"}
                    else 0,
                )
        if self.access_case in {"grant", "true_extra_bits"}:
            _write_uint32(granted, desired_value)
            if self.access_case == "true_extra_bits":
                _write_uint32(granted, desired_value | 0x1)
        elif self.access_case == "true_missing_bits":
            _write_uint32(granted, 0)
        elif self.access_case == "false_nonzero_grant":
            _write_uint32(granted, 1)
        else:
            _write_uint32(granted, 0)
        return 1

    def _close_handle(self, handle) -> int:
        raw = _raw_handle(handle)
        assert raw is not None
        kind = self._handle_kinds.get(raw, "unknown")
        close_count = self._close_counts.get(kind, 0) + 1
        self._close_counts[kind] = close_count
        self.events.append(("native.close", kind, raw))
        if raw in self._closed_handles:
            raise AssertionError("native handle closed more than once")
        self._closed_handles.add(raw)
        self._live_duplicates.discard(raw)
        if kind == "duplicate":
            self._current_access_role = None
        if self.native_close_failure_kind == kind and (
            self.native_close_failure_at is None
            or self.native_close_failure_at == close_count
        ):
            self._set_last_error(5)
            return 0
        return 1


class _FakeBackendLifecycle:
    def __init__(self, world: _ReaderWorld) -> None:
        self.world = world
        self.handles: list[_Held] = []
        self.enumeration_counts: dict[str, int] = {}
        self.enumeration_results: dict[
            str, list[tuple[WindowsDirectoryEntry, ...]]
        ] = {}
        self.snapshot_counts: dict[str, int] = {}
        self.descriptor_counts: dict[str, int] = {}
        self.read_count = 0
        self.closed: list[str] = []

    def __enter__(self):
        self.world.events.append(("backend.enter",))
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.world.events.append(("backend.exit", exc_type is not None))
        cleanup_error = None
        for handle in tuple(reversed(self.handles)):
            try:
                self.close(handle)
            except WindowsHeldHandleError as error:
                if cleanup_error is None:
                    cleanup_error = error
        if self.world.backend_close_failure and cleanup_error is None:
            cleanup_error = WindowsHeldHandleError("observation_failed")
            cleanup_error.__cause__ = OSError(_SECRET_MARKER)
        if cleanup_error is not None:
            if exc is None:
                raise cleanup_error
            if exc.__cause__ is None:
                exc.__cause__ = cleanup_error
                exc.__suppress_context__ = True
            else:
                exc.__context__ = cleanup_error
            raise exc.with_traceback(traceback)
        return False

    def _fail_if_scripted(self, method: str, role: str) -> None:
        if (
            self.world.backend_exception is not None
            and self.world.backend_exception[:2] == (method, role)
        ):
            raise self.world.backend_exception[2]
        if self.world.backend_failure == (method, role):
            error = WindowsHeldHandleError(self.world.backend_failure_code)
            error.__cause__ = OSError(_SECRET_MARKER)
            error.__suppress_context__ = True
            raise error


def _install_reader_world(
    monkeypatch: pytest.MonkeyPatch,
    world: _ReaderWorld,
):
    module = _load_module()
    monkeypatch.setattr(module.os, "name", "nt")

    def bind_native():
        native = world.bind_native()
        security = module.bind_windows_security(
            kernel32=native.kernel32,
            advapi32=native.advapi32,
        )
        return module._NativeApi(
            shell32=native.shell32,
            ole32=native.ole32,
            security=_RecordingSecurityMechanics(world, security),
        )

    monkeypatch.setattr(module, "_bind_native", bind_native)
    monkeypatch.setattr(
        module,
        "_load_windows_backend",
        world.load_backend,
        raising=False,
    )
    return module


def _read_world(monkeypatch: pytest.MonkeyPatch, world: _ReaderWorld):
    module = _install_reader_world(monkeypatch, world)
    return module, module.read_external_pin()


def _expect_reader_error(
    monkeypatch: pytest.MonkeyPatch,
    world: _ReaderWorld,
    code: str,
):
    module = _install_reader_world(monkeypatch, world)
    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()
    assert exc_info.value.code == code
    assert str(exc_info.value) == _ERRORS[code]
    return module, exc_info.value


def _configure_multicomponent_program_data(world: _ReaderWorld) -> None:
    world.known_folder_path = r"C:\Corp\Shared\ProgramData"
    world.snapshots["pd_corp"] = _directory_snapshot(101)
    world.snapshots["pd_shared"] = _directory_snapshot(102)
    world.child_specs = {
        "root": ("pd_corp", "Corp", 101, 0x10),
        "pd_corp": ("pd_shared", "Shared", 102, 0x10),
        "pd_shared": ("anchor", "ProgramData", 1, 0x10),
        "anchor": ("goodq", "GoodQ", 2, 0x10),
        "goodq": ("authority", "authority", 3, 0x10),
        "authority": ("clean_memory", "clean-memory", 4, 0x10),
        "clean_memory": ("pin", _PIN_NAME, 5, 0),
    }
    world.role_by_file_id = {
        file_id: role
        for role, _name, file_id, _attributes in world.child_specs.values()
    }


def _reader_identity_projection(token: _TokenSpec) -> dict[str, object]:
    groups = [
        {"attributes": f"{attributes:08x}", "sid": _sid_text(sid)}
        for sid, attributes in sorted(token.groups, key=lambda item: item[0])
    ]
    privileges = []
    for (low, high), attributes in sorted(
        token.privileges,
        key=lambda item: (((item[0][1] & 0xFFFFFFFF) << 32) | item[0][0]),
    ):
        unsigned_luid = ((high & 0xFFFFFFFF) << 32) | low
        privileges.append(
            {"attributes": f"{attributes:08x}", "luid": f"{unsigned_luid:016x}"}
        )
    restricted = [
        {"attributes": f"{attributes:08x}", "sid": _sid_text(sid)}
        for sid, attributes in sorted(token.restricted_sids, key=lambda item: item[0])
    ]
    elevation_type = {1: "default", 2: "full", 3: "limited"}.get(
        token.elevation_type, "invalid"
    )
    integrity_rid = int.from_bytes(token.integrity_sid[-4:], "little")
    return {
        "elevation": {
            "is_elevated": bool(token.is_elevated),
            "type": elevation_type,
        },
        "groups": groups,
        "has_restrictions": bool(token.has_restrictions),
        "impersonation_level": None,
        "integrity_rid": f"{integrity_rid:08x}",
        "integrity_sid": _sid_text(token.integrity_sid),
        "is_app_container": bool(token.is_app_container),
        "privileges": privileges,
        "restricted_sids": restricted,
        "schema": "goodq.clean-memory-windows-reader-identity.v1",
        "token_source": "process",
        "token_statistics": {
            "authentication_id": "0000000000000002",
            "expiration_time": "0",
            "group_count": str(len(token.groups)),
            "modified_id": "0000000000000004",
            "privilege_count": str(len(token.privileges)),
            "token_id": "0000000000000001",
        },
        "token_type": "primary" if token.token_type == 1 else "impersonation",
        "ui_access": bool(token.ui_access),
        "user_sid": _sid_text(token.user_sid),
    }


def _dacl_projection(
    reader_sid: bytes,
    reader_mask: int,
) -> list[dict[str, str]]:
    return [
        {
            "flags": "00",
            "mask": "001f01ff",
            "sid": "S-1-5-18",
            "type": "access_allowed",
        },
        {
            "flags": "00",
            "mask": "001f01ff",
            "sid": "S-1-5-32-544",
            "type": "access_allowed",
        },
        {
            "flags": "00",
            "mask": f"{reader_mask:08x}",
            "sid": _sid_text(reader_sid),
            "type": "access_allowed",
        },
    ]


def _denied_projection(
    rights: tuple[tuple[str, int], ...],
) -> list[dict[str, object]]:
    return [
        {"denied": True, "mask": f"{mask:08x}", "name": name}
        for name, mask in rights
    ]


def _security_policy_projection(world: _ReaderWorld) -> dict[str, object]:
    backend = world.snapshots
    anchor = {
        "dacl": _dacl_projection(world.reader_sid, 0x001200A1),
        "dacl_revision": 2,
        "denied_access_checks": _denied_projection(_DIRECTORY_RIGHTS),
        "descriptor_control": "8004",
        "owner_sid": "S-1-5-32-544",
        "physical_identity": backend["anchor"].identity_projection,
        "primary_group_sid": "S-1-5-32-544",
        "role": "program_data_anchor",
    }
    dedicated = []
    for role, public_role in (
        ("goodq", "goodq_directory"),
        ("authority", "authority_directory"),
        ("clean_memory", "clean_memory_directory"),
        ("pin", "pin_file"),
    ):
        is_pin = role == "pin"
        dedicated.append(
            {
                "dacl": _dacl_projection(
                    world.reader_sid,
                    0x00120089 if is_pin else 0x001200A1,
                ),
                "dacl_revision": 2,
                "denied_access_checks": _denied_projection(
                    _PIN_RIGHTS if is_pin else _DIRECTORY_RIGHTS
                ),
                "descriptor_control": "9004",
                "owner_sid": "S-1-5-32-544",
                "physical_identity": backend[role].identity_projection,
                "primary_group_sid": "S-1-5-32-544",
                "role": public_role,
            }
        )
    return {
        "anchor": anchor,
        "dedicated_objects": dedicated,
        "enrolled_reader_sid": _sid_text(world.reader_sid),
        "platform": "windows",
        "schema": "goodq.clean-memory-windows-pin-security-policy.v1",
    }


def _expected_world_evidence(world: _ReaderWorld) -> dict[str, object]:
    reader_digest = hashlib.sha256(
        _canonical_bytes(_reader_identity_projection(world.token))
    ).hexdigest()
    security_digest = hashlib.sha256(
        _canonical_bytes(_security_policy_projection(world))
    ).hexdigest()
    return {
        "anchor_identity": world.snapshots["anchor"].identity_projection,
        "dedicated_directory_identities": [
            world.snapshots[role].identity_projection
            for role in ("goodq", "authority", "clean_memory")
        ],
        "enrolled_reader_identity_sha256": reader_digest,
        "manifest_sha256": world.payload[:64].decode("ascii"),
        "pin_file_identity": world.snapshots["pin"].identity_projection,
        "platform": "windows",
        "schema": "goodq.clean-memory-external-pin-evidence.v1",
        "security_policy_sha256": security_digest,
        "source_id": "goodq.clean-memory-protected-authority-pin.primary.v1",
        "source_schema": "goodq.clean-memory-external-pin-source.v1",
    }


def _normalized_authority_trace(
    events: list[tuple[Any, ...]],
) -> list[tuple[str, str | None]]:
    """Collapse the native/backend call stream to the 19 governed operations."""

    normalized: list[tuple[str, str | None]] = []
    for event in events:
        name = event[0]
        if name == "native.bind":
            normalized.append(("setup", "bind"))
        elif name == "backend.construct":
            normalized.append(("setup", "backend"))
        elif name == "privilege.lookup":
            normalized.append(("setup", "privilege"))
        elif name == "token.snapshot":
            normalized.append(("token", event[1]))
        elif name == "known_folder":
            normalized.append(("operation", "known_folder"))
        elif name == "backend.open_root":
            normalized.append(("operation", "root"))
        elif name == "backend.open_by_id":
            normalized.append(("operation", f"select:{event[2]}"))
        elif name == "backend.descriptor" and event[2] == 1:
            normalized.append(("operation", f"descriptor:{event[1]}"))
        elif name == "token.duplicate":
            normalized.append(("operation", f"access:{event[1]}"))
        elif name == "backend.read_bounded":
            normalized.append(("operation", "read"))
        elif name == "backend.descriptor" and event[1:] == ("anchor", 2):
            normalized.append(("operation", "final"))
    return normalized


def _governed_bracket_semantics(
    events: list[tuple[Any, ...]], operation_index: int
) -> list[tuple[Any, ...]]:
    before = max(
        index
        for index in range(operation_index)
        if events[index][:2] == ("token.snapshot", "transient")
    )
    after = next(
        index
        for index in range(operation_index + 1, len(events))
        if events[index][:2] == ("token.snapshot", "transient")
    )
    after_handle = events[after][3]
    end = next(
        index
        for index in range(after + 1, len(events))
        if events[index] == ("native.close", "transient", after_handle)
    )
    semantics: list[tuple[Any, ...]] = []
    for event in events[before : end + 1]:
        if event[:2] == ("token.snapshot", "transient"):
            semantics.append(("token.snapshot",))
        elif event[:2] == ("native.close", "transient"):
            semantics.append(("token.close",))
        elif event[0].startswith("backend."):
            semantics.append(event)
    return semantics


def _walk_exception_chain(error: BaseException) -> tuple[BaseException, ...]:
    pending = [error]
    seen: set[int] = set()
    values = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        values.append(current)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
    return tuple(values)


def _assert_sanitized_chain(module, error: BaseException) -> None:
    chain = _walk_exception_chain(error)
    assert chain
    for node in chain:
        assert type(node) is module.ExternalPinReaderError
        assert node.code in _ERRORS
        rendered = " ".join((str(node), repr(node), repr(node.args), repr(vars(node))))
        assert _SECRET_MARKER not in rendered
        assert "S-1-5-21-999" not in rendered
        assert r"C:\private" not in rendered


def _assert_linear_cause_chain(
    error: BaseException,
    *,
    expected_length: int,
) -> tuple[BaseException, ...]:
    chain = _walk_exception_chain(error)
    assert len(chain) == expected_length
    for index, node in enumerate(chain):
        assert node.__context__ is None
        expected_cause = chain[index + 1] if index + 1 < len(chain) else None
        assert node.__cause__ is expected_cause
    return chain


def _assert_control_primary_has_only_sanitized_cleanup(
    module,
    error: BaseException,
    *,
    expected_cleanup_count: int = 1,
) -> None:
    cleanup = error.__cause__
    assert type(cleanup) is module.ExternalPinReaderError
    assert error.__context__ is None
    assert cleanup.code == "observation_failed"
    _assert_sanitized_chain(module, cleanup)
    cleanup_chain = _walk_exception_chain(cleanup)
    assert len(cleanup_chain) == expected_cleanup_count
    for index, node in enumerate(cleanup_chain):
        assert node.__context__ is None
        expected_cause = (
            cleanup_chain[index + 1]
            if index + 1 < len(cleanup_chain)
            else None
        )
        assert node.__cause__ is expected_cause


def _prime_control_primary(error: BaseException):
    try:
        raise error
    except BaseException as caught:
        assert caught is error
        traceback = caught.__traceback__
    assert traceback is not None
    return traceback


def _assert_original_traceback_tail_is_preserved(
    error: BaseException,
    expected_tail,
) -> None:
    traceback = error.__traceback__
    while traceback is not None:
        if traceback is expected_tail:
            return
        traceback = traceback.tb_next
    raise AssertionError("control-flow traceback tail was not preserved")


def _capture_top_cleanup_nodes(monkeypatch, module, world):
    del world
    backend_cleanup_nodes: list[BaseException] = []
    baseline_cleanup_nodes: list[BaseException] = []
    original_sanitize = module._sanitize_error
    original_translate = module._translate_security_error_graph

    def capture_backend_cleanup(error: BaseException):
        sanitized = original_sanitize(error)
        if isinstance(error, WindowsHeldHandleError):
            backend_cleanup_nodes.append(sanitized)
        return sanitized

    def capture_baseline_cleanup(error, *, phase: str):
        cleanup = original_translate(error, phase=phase)
        if phase == "cleanup":
            baseline_cleanup_nodes.append(cleanup)
        return cleanup

    monkeypatch.setattr(module, "_sanitize_error", capture_backend_cleanup)
    monkeypatch.setattr(
        module,
        "_translate_security_error_graph",
        capture_baseline_cleanup,
    )
    return backend_cleanup_nodes, baseline_cleanup_nodes


class _FakeHeldHandleBackend(_FakeBackendLifecycle):
    def open_root(self, root: str) -> object:
        self.world.events.append(("backend.open_root", root))
        self._fail_if_scripted("open_root", "root")
        handle = _Held("root")
        self.handles.append(handle)
        return handle

    def volume_filesystem(self, handle: object) -> str:
        assert isinstance(handle, _Held)
        self.world.events.append(("backend.filesystem", handle.role))
        self._fail_if_scripted("volume_filesystem", handle.role)
        return self.world.filesystem

    def enumerate_directory(
        self, handle: object, filesystem: str
    ) -> tuple[WindowsDirectoryEntry, ...]:
        assert isinstance(handle, _Held)
        role = handle.role
        count = self.enumeration_counts.get(role, 0) + 1
        self.enumeration_counts[role] = count
        self.world.events.append(("backend.enumerate", role, filesystem, count))
        self._fail_if_scripted("enumerate_directory", role)
        if role not in self.world.child_specs:
            return ()
        child_role, name, file_id, attributes = self.world.child_specs[role]
        entries: list[WindowsDirectoryEntry] = []
        if self.world.missing_role != child_role:
            entries.append(
                WindowsDirectoryEntry(
                    name=name,
                    attributes=attributes,
                    file_id_kind="ntfs_file_index_64",
                    file_id=file_id,
                )
            )
        if self.world.duplicate_role == child_role:
            entries.append(
                WindowsDirectoryEntry(
                    name=name.swapcase(),
                    attributes=attributes,
                    file_id_kind="ntfs_file_index_64",
                    file_id=file_id + 100,
                )
            )
        if (
            count >= 2
            and self.world.membership_mutation_role == child_role
            and self.world.missing_role == child_role
        ):
            entries.append(
                WindowsDirectoryEntry(
                    name="late-entry",
                    attributes=0,
                    file_id_kind="ntfs_file_index_64",
                    file_id=900,
                )
            )
        if (
            count >= 3
            and self.world.second_proof_membership_mutation_role == child_role
            and self.world.missing_role == child_role
        ):
            entries.append(
                WindowsDirectoryEntry(
                    name="proof-late-entry",
                    attributes=0,
                    file_id_kind="ntfs_file_index_64",
                    file_id=901,
                )
            )
        if (
            count >= 2
            and self.world.proof_target_appearance_role == child_role
            and self.world.missing_role == child_role
        ):
            entries.append(
                WindowsDirectoryEntry(
                    name=name,
                    attributes=attributes,
                    file_id_kind="ntfs_file_index_64",
                    file_id=file_id,
                )
            )
        if (
            self.world.absence_sibling_mutation_role == child_role
            and self.world.missing_role == child_role
        ):
            drift = count >= 2
            field = self.world.absence_sibling_mutation_field
            entries.append(
                WindowsDirectoryEntry(
                    name="unrelated-sibling",
                    attributes=0x20 if drift and field == "attributes" else 0,
                    file_id_kind=(
                        "refs_file_id_128"
                        if drift and field == "file_id_kind"
                        else "ntfs_file_index_64"
                    ),
                    file_id=(
                        b"\x01" * 16
                        if drift and field == "file_id_kind"
                        else 801
                        if drift and field == "file_id"
                        else 800
                    ),
                )
            )
        if count >= 2 and self.world.recheck_membership_role == child_role:
            entries.append(
                WindowsDirectoryEntry(
                    name="late-entry",
                    attributes=0,
                    file_id_kind="ntfs_file_index_64",
                    file_id=901,
                )
            )
        if (
            count >= 2
            and self.world.recheck_membership_replace_role == child_role
            and entries
        ):
            current = entries[0]
            entries[0] = WindowsDirectoryEntry(
                name=current.name,
                attributes=current.attributes ^ 0x400,
                file_id_kind=current.file_id_kind,
                file_id=current.file_id,
            )
        result = tuple(entries)
        self.enumeration_results.setdefault(role, []).append(result)
        return result

    def open_by_id(
        self,
        volume_handle: object,
        entry: WindowsDirectoryEntry,
        *,
        directory: bool,
    ) -> object:
        assert isinstance(volume_handle, _Held)
        role = self.world.role_by_file_id.get(int(entry.file_id), "unknown")
        self.world.events.append(
            ("backend.open_by_id", volume_handle.role, role, directory)
        )
        self._fail_if_scripted("open_by_id", role)
        handle = _Held(role)
        self.handles.append(handle)
        return handle

    def snapshot(
        self,
        handle: object,
        *,
        filesystem: str,
        expected: WindowsDirectoryEntry | None,
        object_kind: str,
        require_stream_contract: bool,
    ) -> WindowsObjectSnapshot:
        assert isinstance(handle, _Held)
        role = handle.role
        count = self.snapshot_counts.get(role, 0) + 1
        self.snapshot_counts[role] = count
        self.world.events.append(
            (
                "backend.snapshot",
                role,
                filesystem,
                None if expected is None else expected.file_id,
                object_kind,
                require_stream_contract,
                count,
            )
        )
        self._fail_if_scripted("snapshot", role)
        snapshot = self.world.snapshots[role]
        final_threshold = 3 if role == "pin" else 2
        if count >= final_threshold and self.world.recheck_snapshot_role == role:
            snapshot = dataclasses.replace(snapshot, change_ticks=snapshot.change_ticks + 1)
        if count == 2 and self.world.read_snapshot_role == role:
            snapshot = dataclasses.replace(snapshot, size_bytes=snapshot.size_bytes + 1)
        if count >= final_threshold and self.world.recheck_stream_role == role:
            snapshot = dataclasses.replace(
                snapshot,
                streams=tuple(
                    (name, size + 1, allocation)
                    for name, size, allocation in snapshot.streams
                ),
            )
        return snapshot

    def read_security_descriptor(self, handle: object) -> bytes:
        assert isinstance(handle, _Held)
        role = handle.role
        count = self.descriptor_counts.get(role, 0) + 1
        self.descriptor_counts[role] = count
        self.world.events.append(("backend.descriptor", role, count))
        self._fail_if_scripted("read_security_descriptor", role)
        value = self.world.descriptors[role]
        if count >= 2 and self.world.recheck_descriptor_role == role:
            value = value + b"\0\0\0\x01"
        return bytes(value)

    def read_file_bounded(self, handle: object, *, maximum_bytes: int):
        assert isinstance(handle, _Held)
        self.read_count += 1
        self.world.events.append(
            ("backend.read_bounded", handle.role, maximum_bytes, self.read_count)
        )
        self._fail_if_scripted("read_file_bounded", handle.role)
        return bytes(self.world.payload), self.world.explicit_eof

    def close(self, handle: object) -> None:
        if not isinstance(handle, _Held) or handle not in self.handles:
            raise WindowsHeldHandleError("observation_failed")
        self.handles.remove(handle)
        self.closed.append(handle.role)
        self.world.events.append(("backend.close", handle.role))
        if self.world.backend_close_failure and len(self.closed) == 1:
            error = WindowsHeldHandleError("observation_failed")
            error.__cause__ = OSError(_SECRET_MARKER)
            error.__suppress_context__ = True
            raise error


def test_external_pin_reader_module_exists() -> None:
    assert MODULE_PATH.is_file()


def test_public_contract_is_exact_and_no_argument() -> None:
    module = _load_module()

    assert module.__all__ == (
        "EXTERNAL_PIN_EVIDENCE_SCHEMA",
        "ExternalPinReaderError",
        "ExternalPinEvidence",
        "read_external_pin",
    )
    assert (
        module.EXTERNAL_PIN_EVIDENCE_SCHEMA
        == "goodq.clean-memory-external-pin-evidence.v1"
    )
    assert tuple(inspect.signature(module.read_external_pin).parameters) == ()
    assert inspect.signature(module.read_external_pin).return_annotation in {
        "ExternalPinEvidence",
        module.ExternalPinEvidence,
    }


@pytest.mark.parametrize(("code", "message"), tuple(_ERRORS.items()))
def test_error_contract_is_closed_path_free_and_immutable(
    code: str, message: str
) -> None:
    module = _load_module()

    error = module.ExternalPinReaderError(code)
    assert isinstance(error, RuntimeError)
    assert error.code == code
    assert str(error) == message
    assert error.args == (message,)
    with pytest.raises(AttributeError):
        error.code = "observation_failed"
    with pytest.raises(AttributeError):
        error._code = "observation_failed"


@pytest.mark.parametrize("value", [None, "", "unknown", 1, True])
def test_error_rejects_every_unknown_code(value: object) -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="Unknown external pin reader error code"):
        module.ExternalPinReaderError(value)


def test_evidence_is_private_frozen_detached_and_digest_bound() -> None:
    module = _load_module()
    projection = _evidence_projection()
    canonical = json.dumps(
        projection,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    with pytest.raises(TypeError):
        module.ExternalPinEvidence()
    evidence = module.ExternalPinEvidence._from_projection(projection)

    assert dataclasses.is_dataclass(evidence)
    assert evidence.__dataclass_params__.frozen is True
    assert evidence.__dataclass_params__.init is False
    assert evidence.external_pin_evidence_sha256 == hashlib.sha256(canonical).hexdigest()
    assert evidence.projection == projection
    assert evidence.projection is not evidence.projection
    detached = evidence.projection
    detached["manifest_sha256"] = "f" * 64
    detached["dedicated_directory_identities"][0]["file_id"] = "f" * 16
    assert evidence.projection == projection
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.external_pin_evidence_sha256 = "0" * 64
    assert "0123456789abcdef" not in repr(evidence)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.pop("platform"),
        lambda value: value.__setitem__("extra", None),
        lambda value: value.__setitem__("schema", "wrong"),
        lambda value: value.__setitem__("dedicated_directory_identities", []),
    ],
)
def test_evidence_rejects_invalid_internal_projection(mutator) -> None:
    module = _load_module()
    projection = _evidence_projection()
    mutator(projection)

    with pytest.raises(ValueError, match="External pin evidence projection is invalid"):
        module.ExternalPinEvidence._from_projection(projection)


def test_module_import_loads_no_native_capability(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: calls.append(args))
    sys.modules.pop("cli.clean_memory_external_pin", None)

    module = importlib.import_module("cli.clean_memory_external_pin")

    assert module.__all__[0] == "EXTERNAL_PIN_EVIDENCE_SCHEMA"
    assert calls == []


def test_non_windows_rejects_before_native_binding(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module.os, "name", "posix")
    monkeypatch.setattr(
        module,
        "_bind_native",
        lambda: pytest.fail("non-Windows reader attempted native binding"),
    )

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    assert exc_info.value.code == "unsupported_platform"


def test_consumer_known_folder_guid_layout_is_exact() -> None:
    module = _load_module()

    assert ctypes.sizeof(module._GUID) == 16


def test_native_binding_uses_exact_dlls_exports_and_pointer_width(monkeypatch) -> None:
    module = _load_module()
    dlls = _native_dlls()
    calls = _install_fake_windll(monkeypatch, dlls)

    native = module._bind_native()

    assert calls == [
        ("kernel32", True),
        ("shell32", True),
        ("ole32", True),
        ("advapi32", True),
    ]
    assert native.shell32 is dlls["shell32"]
    assert native.ole32 is dlls["ole32"]
    assert type(native.security) is WindowsSecurityMechanics
    assert dlls["shell32"].SHGetKnownFolderPath.argtypes == [
        ctypes.POINTER(module._GUID),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    assert dlls["shell32"].SHGetKnownFolderPath.restype is ctypes.c_int32
    assert dlls["ole32"].CoTaskMemFree.argtypes == [ctypes.c_void_p]
    assert dlls["ole32"].CoTaskMemFree.restype is None


def test_native_binding_runs_shared_abi_preflight_before_loading_and_delegates(
    monkeypatch,
) -> None:
    module = _load_module()
    dlls = _native_dlls()
    events: list[tuple[object, ...]] = []
    security = object()

    monkeypatch.setattr(
        module,
        "verify_windows_security_abi",
        lambda: events.append(("security.abi",)),
    )

    def fake_windll(name: str, *, use_last_error: bool):
        normalized = name.casefold()
        events.append(("dll", normalized, use_last_error))
        return dlls[normalized]

    def fake_bind_windows_security(*, kernel32: object, advapi32: object):
        events.append(("security.bind", kernel32, advapi32))
        return security

    monkeypatch.setattr(ctypes, "WinDLL", fake_windll)
    monkeypatch.setattr(
        module,
        "bind_windows_security",
        fake_bind_windows_security,
    )

    native = module._bind_native()

    assert events == [
        ("security.abi",),
        ("dll", "kernel32", True),
        ("dll", "shell32", True),
        ("dll", "ole32", True),
        ("dll", "advapi32", True),
        ("security.bind", dlls["kernel32"], dlls["advapi32"]),
    ]
    assert native.security is security


def test_native_binding_translates_shared_abi_failure_before_loading_dlls(
    monkeypatch,
) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "verify_windows_security_abi",
        lambda: (_ for _ in ()).throw(
            module.WindowsSecurityMechanicsError("unsupported_security")
        ),
    )
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda *_args, **_kwargs: pytest.fail("DLL loaded before shared ABI guard"),
    )

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module._bind_native()

    assert exc_info.value.code == "unsupported_security"


@pytest.mark.parametrize(
    ("dll_name", "export_name", "expected_code"),
    [
        ("kernel32", "GetCurrentThread", "unsupported_security"),
        ("kernel32", "GetCurrentProcess", "unsupported_security"),
        ("kernel32", "CloseHandle", "unsupported_security"),
        ("kernel32", "LocalFree", "unsupported_security"),
        ("shell32", "SHGetKnownFolderPath", "unsupported_platform"),
        ("ole32", "CoTaskMemFree", "unsupported_platform"),
        ("advapi32", "OpenThreadToken", "unsupported_security"),
        ("advapi32", "OpenProcessToken", "unsupported_security"),
        ("advapi32", "GetTokenInformation", "unsupported_security"),
        ("advapi32", "LookupPrivilegeValueW", "unsupported_security"),
        ("advapi32", "DuplicateTokenEx", "unsupported_security"),
        ("advapi32", "MapGenericMask", "unsupported_security"),
        ("advapi32", "AccessCheck", "unsupported_security"),
        ("advapi32", "GetSecurityInfo", "unsupported_security"),
        ("advapi32", "IsValidSecurityDescriptor", "unsupported_security"),
        ("advapi32", "GetSecurityDescriptorControl", "unsupported_security"),
        ("advapi32", "GetSecurityDescriptorLength", "unsupported_security"),
    ],
)
def test_native_binding_classifies_missing_exports(
    monkeypatch, dll_name: str, export_name: str, expected_code: str
) -> None:
    module = _load_module()
    dlls = _native_dlls()
    delattr(dlls[dll_name], export_name)
    _install_fake_windll(monkeypatch, dlls)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module._bind_native()

    assert exc_info.value.code == expected_code


@pytest.mark.parametrize(
    ("failed_dll", "expected_code", "expected_calls"),
    [
        ("kernel32", "unsupported_platform", ("kernel32",)),
        ("shell32", "unsupported_platform", ("kernel32", "shell32")),
        ("ole32", "unsupported_platform", ("kernel32", "shell32", "ole32")),
        (
            "advapi32",
            "unsupported_security",
            ("kernel32", "shell32", "ole32", "advapi32"),
        ),
    ],
)
def test_native_binding_classifies_each_dll_load_failure(
    monkeypatch, failed_dll: str, expected_code: str, expected_calls: tuple[str, ...]
) -> None:
    module = _load_module()
    dlls = _native_dlls()
    calls: list[str] = []

    def fake_windll(name: str, *, use_last_error: bool):
        assert use_last_error is True
        normalized = name.casefold()
        calls.append(normalized)
        if normalized == failed_dll:
            raise OSError("sanitized fake load failure")
        return dlls[normalized]

    monkeypatch.setattr(ctypes, "WinDLL", fake_windll)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module._bind_native()

    assert exc_info.value.code == expected_code
    assert tuple(calls) == expected_calls


def test_public_reader_completes_native_preflight_before_backend_construction(
    monkeypatch,
) -> None:
    module = _load_module()
    monkeypatch.setattr(module.os, "name", "nt")

    def fail_preflight():
        raise module.ExternalPinReaderError("unsupported_security")

    monkeypatch.setattr(module, "_bind_native", fail_preflight)
    monkeypatch.setattr(
        module,
        "_load_windows_backend",
        lambda: pytest.fail("backend constructed before native preflight completed"),
        raising=False,
    )

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    assert exc_info.value.code == "unsupported_security"


def test_startup_sanitization_allocation_failure_is_contained(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module.os, "name", "nt")
    raw_error = module.ExternalPinReaderError("unsupported_security")

    def fail_preflight():
        raise raw_error

    def fail_sanitization(error: BaseException):
        assert error is raw_error
        raise MemoryError(_SECRET_MARKER)

    monkeypatch.setattr(module, "_bind_native", fail_preflight)
    monkeypatch.setattr(module, "_sanitize_error", fail_sanitization)
    monkeypatch.setattr(
        module,
        "_load_windows_backend",
        lambda: pytest.fail("backend constructed after failed native preflight"),
        raising=False,
    )

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error.code == "observation_failed"
    assert error.__cause__ is None
    assert error.__context__ is None
    assert _SECRET_MARKER not in repr(error)


def test_reader_opens_exact_shared_base_token_profile(monkeypatch) -> None:
    world = _ReaderWorld()

    module, _evidence = _read_world(monkeypatch, world)

    assert world.security_session_profiles == [WINDOWS_TOKEN_PROFILE_BASE]
    baseline = world.security_baseline_snapshots[0]
    assert baseline.mandatory_policy is None
    policy_one = dataclasses.replace(baseline, mandatory_policy=1)
    policy_three = dataclasses.replace(baseline, mandatory_policy=3)
    assert policy_one != policy_three
    assert module.clean_memory_windows_reader_identity_sha256(
        policy_one,
        profile=WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
        change_notify_luid=0x17,
    ) == module.clean_memory_windows_reader_identity_sha256(
        policy_three,
        profile=WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
        change_notify_luid=0x17,
    )


def test_shared_reader_identity_errors_map_to_closed_external_errors(
    monkeypatch,
) -> None:
    module = _load_module()
    cases = (
        ("validate", module.CleanMemoryWindowsReaderIdentityError(), "untrusted_reader"),
        ("digest", module.CleanMemoryWindowsReaderIdentityError(), "untrusted_reader"),
        ("validate", TypeError(_SECRET_MARKER), "observation_failed"),
        ("digest", ValueError(_SECRET_MARKER), "observation_failed"),
        ("validate", RuntimeError(_SECRET_MARKER), "observation_failed"),
        ("digest", KeyboardInterrupt(_SECRET_MARKER), "observation_failed"),
    )

    for phase, failure, expected_code in cases:
        world = _ReaderWorld()

        def validate(_snapshot, *, profile: str, change_notify_luid: int) -> None:
            assert profile == WINDOWS_TOKEN_PROFILE_BASE
            assert change_notify_luid == 0x17

        def digest(_snapshot, *, profile: str, change_notify_luid: int) -> str:
            assert profile == WINDOWS_TOKEN_PROFILE_BASE
            assert change_notify_luid == 0x17
            return hashlib.sha256(
                _canonical_bytes(_reader_identity_projection(world.token))
            ).hexdigest()

        def fail(*_args, **_kwargs):
            raise failure

        monkeypatch.setattr(
            module,
            "validate_clean_memory_windows_reader_identity",
            fail if phase == "validate" else validate,
        )
        monkeypatch.setattr(
            module,
            "clean_memory_windows_reader_identity_sha256",
            fail if phase == "digest" else digest,
        )

        _module, error = _expect_reader_error(
            monkeypatch,
            world,
            expected_code,
        )

        assert _SECRET_MARKER not in repr(error)


def test_happy_path_returns_exact_evidence_and_frozen_trace(monkeypatch) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    shared_calls: list[tuple[object, ...]] = []
    original_final_recheck = module._final_authority_recheck

    def validate(snapshot, *, profile: str, change_notify_luid: int) -> None:
        assert not any(
            event[0] in {"known_folder", "backend.open_root"}
            for event in world.events
        )
        assert snapshot is world.security_baseline_snapshots[0]
        shared_calls.append(
            ("validate", snapshot, profile, change_notify_luid)
        )

    def final_recheck(*args, **kwargs) -> None:
        original_final_recheck(*args, **kwargs)
        shared_calls.append(("final",))

    def digest(snapshot, *, profile: str, change_notify_luid: int) -> str:
        assert shared_calls[-1] == ("final",)
        assert snapshot is world.security_baseline_snapshots[0]
        shared_calls.append(("digest", snapshot, profile, change_notify_luid))
        return hashlib.sha256(
            _canonical_bytes(_reader_identity_projection(world.token))
        ).hexdigest()

    monkeypatch.setattr(
        module,
        "validate_clean_memory_windows_reader_identity",
        validate,
    )
    monkeypatch.setattr(module, "_final_authority_recheck", final_recheck)
    monkeypatch.setattr(
        module,
        "clean_memory_windows_reader_identity_sha256",
        digest,
    )

    evidence = module.read_external_pin()
    baseline = world.security_baseline_snapshots[0]

    assert shared_calls == [
        ("validate", baseline, WINDOWS_TOKEN_PROFILE_BASE, 0x17),
        ("final",),
        ("digest", baseline, WINDOWS_TOKEN_PROFILE_BASE, 0x17),
    ]

    assert evidence.projection == _expected_world_evidence(world)
    assert evidence.external_pin_evidence_sha256 == hashlib.sha256(
        _canonical_bytes(_expected_world_evidence(world))
    ).hexdigest()
    assert world.events[:2] == [
        ("native.bind",),
        ("backend.construct", "security_read"),
    ]
    known_folder = [event for event in world.events if event[0] == "known_folder"]
    assert known_folder == [
        (
            "known_folder",
            bytes.fromhex("825dab62c1fdc34da9dd070d1d495d97"),
            0,
            None,
        )
    ]
    assert len(world.freed_known_folder) == 1
    assert world.backend is not None
    assert world.backend.handles == []
    assert world.backend.read_count == 1
    assert world.backend.closed == [
        "pin",
        "clean_memory",
        "authority",
        "goodq",
        "anchor",
        "root",
    ]
    assert world.backend.enumeration_counts == {
        "root": 2,
        "anchor": 2,
        "goodq": 2,
        "authority": 2,
        "clean_memory": 2,
    }
    assert world.backend.descriptor_counts == {
        "anchor": 2,
        "goodq": 2,
        "authority": 2,
        "clean_memory": 2,
        "pin": 2,
    }
    assert world.backend.snapshot_counts == {
        "root": 2,
        "anchor": 2,
        "goodq": 2,
        "authority": 2,
        "clean_memory": 2,
        "pin": 3,
    }
    token_sequences: dict[int, list[int]] = {}
    for event in world.events:
        if event[0] == "token.info":
            token_sequences.setdefault(event[1], []).append(event[2])
    assert len(token_sequences) == 39
    assert all(
        tuple(sequence) == _TOKEN_NATIVE_CALL_ORDER
        for sequence in token_sequences.values()
    )
    assert all(27 not in sequence for sequence in token_sequences.values())
    assert len([event for event in world.events if event[0] == "token.duplicate"]) == 5
    assert len([event for event in world.events if event[0] == "access.check"]) == 19
    assert world.max_live_duplicates == 1
    assert not world._live_duplicates
    assert not any(
        event[:2] == ("native.close", "unknown") for event in world.events
    )
    assert not any(
        event[0] == "native.close" and event[2] in {0xDEAD0001, 0xFFFF0001, 0xFFFF0002}
        for event in world.events
    )
    read_index = next(
        index for index, event in enumerate(world.events) if event[0] == "backend.read_bounded"
    )
    assert all(
        next(
            index
            for index, event in enumerate(world.events)
            if event[:2] == ("backend.descriptor", role)
        )
        < read_index
        for role in _ROLE_ORDER
    )


def test_multicomponent_program_data_is_traversed_and_rechecked_only_by_id(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    _configure_multicomponent_program_data(world)

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection["manifest_sha256"] == "a" * 64
    assert world.backend is not None
    assert world.backend.read_count == 1
    assert [event for event in world.events if event[0] == "backend.read_bounded"] == [
        ("backend.read_bounded", "pin", 66, 1)
    ]
    assert [event for event in world.events if event[0] == "backend.open_root"] == [
        ("backend.open_root", "C:\\")
    ]
    assert [event for event in world.events if event[0] == "backend.open_by_id"] == [
        ("backend.open_by_id", "root", role, role != "pin")
        for role in (
            "pd_corp",
            "pd_shared",
            "anchor",
            "goodq",
            "authority",
            "clean_memory",
            "pin",
        )
    ]
    assert world.backend is not None
    assert world.backend.enumeration_counts == {
        role: 2
        for role in (
            "root",
            "pd_corp",
            "pd_shared",
            "anchor",
            "goodq",
            "authority",
            "clean_memory",
        )
    }
    assert world.backend.snapshot_counts == {
        "root": 2,
        "pd_corp": 2,
        "pd_shared": 2,
        "anchor": 2,
        "goodq": 2,
        "authority": 2,
        "clean_memory": 2,
        "pin": 3,
    }
    assert world.backend.closed == [
        "pin",
        "clean_memory",
        "authority",
        "goodq",
        "anchor",
        "pd_shared",
        "pd_corp",
        "root",
    ]

    for parent, (role, _name, file_id, _attributes) in world.child_specs.items():
        select_index = next(
            index
            for index, event in enumerate(world.events)
            if event[:3] == ("backend.open_by_id", "root", role)
        )
        assert _governed_bracket_semantics(world.events, select_index) == [
            ("token.snapshot",),
            ("token.close",),
            ("backend.enumerate", parent, "NTFS", 1),
            ("backend.open_by_id", "root", role, role != "pin"),
            (
                "backend.snapshot",
                role,
                "NTFS",
                file_id,
                "regular_file" if role == "pin" else "directory",
                True,
                1,
            ),
            ("token.snapshot",),
            ("token.close",),
        ]

    final_index = next(
        index
        for index, event in enumerate(world.events)
        if event == ("backend.descriptor", "anchor", 2)
    )
    assert _governed_bracket_semantics(world.events, final_index) == [
        ("token.snapshot",),
        ("token.close",),
        *(("backend.descriptor", role, 2) for role in _ROLE_ORDER),
        ("backend.snapshot", "root", "NTFS", None, "directory", True, 2),
        *(
            (
                "backend.snapshot",
                role,
                "NTFS",
                world.child_specs[
                    next(
                        parent
                        for parent, spec in world.child_specs.items()
                        if spec[0] == role
                    )
                ][2],
                "regular_file" if role == "pin" else "directory",
                True,
                3 if role == "pin" else 2,
            )
            for role in ("pd_corp", "pd_shared", *_ROLE_ORDER)
        ),
        *(
            ("backend.enumerate", parent, "NTFS", 2)
            for parent in world.child_specs
        ),
        ("token.snapshot",),
        ("token.close",),
    ]


def test_happy_path_has_exact_governed_operation_and_token_bracket_trace(
    monkeypatch,
) -> None:
    world = _ReaderWorld()

    _read_world(monkeypatch, world)

    operations = (
        "known_folder",
        "root",
        "select:anchor",
        "select:goodq",
        "select:authority",
        "select:clean_memory",
        "descriptor:anchor",
        "descriptor:goodq",
        "descriptor:authority",
        "descriptor:clean_memory",
        "access:anchor",
        "access:goodq",
        "access:authority",
        "access:clean_memory",
        "select:pin",
        "descriptor:pin",
        "access:pin",
        "read",
        "final",
    )
    expected = [
        ("setup", "bind"),
        ("setup", "backend"),
        ("setup", "privilege"),
        ("token", "baseline"),
    ]
    for operation in operations:
        expected.extend(
            (
                ("token", "transient"),
                ("operation", operation),
                ("token", "transient"),
            )
        )
    assert _normalized_authority_trace(world.events) == expected


def test_root_selection_and_read_have_exact_internal_token_brackets(
    monkeypatch,
) -> None:
    world = _ReaderWorld()

    _read_world(monkeypatch, world)

    root_index = next(
        index
        for index, event in enumerate(world.events)
        if event == ("backend.open_root", "C:\\")
    )
    assert _governed_bracket_semantics(world.events, root_index) == [
        ("token.snapshot",),
        ("token.close",),
        ("backend.open_root", "C:\\"),
        ("backend.filesystem", "root"),
        ("backend.snapshot", "root", "NTFS", None, "directory", True, 1),
        ("token.snapshot",),
        ("token.close",),
    ]

    for parent, (role, _name, file_id, _attributes) in world.child_specs.items():
        select_index = next(
            index
            for index, event in enumerate(world.events)
            if event[:3] == ("backend.open_by_id", "root", role)
        )
        assert _governed_bracket_semantics(world.events, select_index) == [
            ("token.snapshot",),
            ("token.close",),
            ("backend.enumerate", parent, "NTFS", 1),
            ("backend.open_by_id", "root", role, role != "pin"),
            (
                "backend.snapshot",
                role,
                "NTFS",
                file_id,
                "regular_file" if role == "pin" else "directory",
                True,
                1,
            ),
            ("token.snapshot",),
            ("token.close",),
        ]

    read_index = next(
        index
        for index, event in enumerate(world.events)
        if event[0] == "backend.read_bounded"
    )
    assert _governed_bracket_semantics(world.events, read_index) == [
        ("token.snapshot",),
        ("token.close",),
        ("backend.read_bounded", "pin", 66, 1),
        ("backend.snapshot", "pin", "NTFS", 5, "regular_file", True, 2),
        ("token.snapshot",),
        ("token.close",),
    ]


def test_final_authority_recheck_has_exact_internal_operation_order(
    monkeypatch,
) -> None:
    world = _ReaderWorld()

    _read_world(monkeypatch, world)

    token_positions = [
        index for index, event in enumerate(world.events) if event[0] == "token.snapshot"
    ]
    assert len(token_positions) == 39
    final_events = world.events[token_positions[-2] + 1 : token_positions[-1]]
    authority_events = [
        event
        for event in final_events
        if event[0] in {"backend.descriptor", "backend.snapshot", "backend.enumerate"}
    ]
    assert authority_events == [
        *(("backend.descriptor", role, 2) for role in _ROLE_ORDER),
        (
            "backend.snapshot",
            "root",
            "NTFS",
            None,
            "directory",
            True,
            2,
        ),
        *(
            (
                "backend.snapshot",
                role,
                "NTFS",
                world.child_specs[
                    next(parent for parent, spec in world.child_specs.items() if spec[0] == role)
                ][2],
                "regular_file" if role == "pin" else "directory",
                True,
                3 if role == "pin" else 2,
            )
            for role in _ROLE_ORDER
        ),
        *(
            ("backend.enumerate", role, "NTFS", 2)
            for role in ("root", "anchor", "goodq", "authority", "clean_memory")
        ),
    ]


def test_effective_access_uses_exact_duplicate_mapping_rights_and_fresh_outputs(
    monkeypatch,
) -> None:
    world = _ReaderWorld()

    _read_world(monkeypatch, world)

    baseline_handle = next(
        handle for handle, kind in world._handle_kinds.items() if kind == "baseline"
    )
    process_opens = [event for event in world.events if event[0] == "token.open_process"]
    assert process_opens[0][3] == 0x000A
    assert all(event[3] == 0x0008 for event in process_opens[1:])

    duplicates = [event for event in world.events if event[0] == "token.duplicate"]
    assert duplicates == [
        ("token.duplicate", role, baseline_handle, 0x0008, None, 2, 2)
        for role in _ROLE_ORDER
    ]

    privilege_capacity = 8 + 12 * max(1, len(world.token.privileges))
    for role in _ROLE_ORDER:
        rights = _PIN_RIGHTS if role == "pin" else _DIRECTORY_RIGHTS
        duplicate_index = next(
            index
            for index, event in enumerate(world.events)
            if event[:2] == ("token.duplicate", role)
        )
        close_index = next(
            index
            for index in range(duplicate_index + 1, len(world.events))
            if world.events[index][:2] == ("native.close", "duplicate")
        )
        post_access_token_index = next(
            index
            for index in range(duplicate_index + 1, len(world.events))
            if world.events[index][:2] == ("token.snapshot", "transient")
        )
        pre_access_token_index = max(
            index
            for index in range(duplicate_index)
            if world.events[index][:2] == ("token.snapshot", "transient")
        )
        pre_access_close_index = next(
            index
            for index in range(pre_access_token_index + 1, duplicate_index)
            if world.events[index]
            == (
                "native.close",
                "transient",
                world.events[pre_access_token_index][3],
            )
        )
        post_access_close_index = next(
            index
            for index in range(post_access_token_index + 1, len(world.events))
            if world.events[index]
            == (
                "native.close",
                "transient",
                world.events[post_access_token_index][3],
            )
        )
        assert (
            pre_access_token_index
            < pre_access_close_index
            < duplicate_index
            < close_index
            < post_access_token_index
            < post_access_close_index
        )
        assert not any(
            event[:2] == ("token.snapshot", "transient")
            for event in world.events[duplicate_index + 1 : close_index]
        )
        duplicate_handle = world.events[duplicate_index + 1 : close_index]
        access_events = [
            event
            for event in duplicate_handle
            if event[0] in {"access.map", "access.check"}
        ]
        expected_names = [
            name for _right in rights for name in ("access.map", "access.check")
        ]
        assert [event[0] for event in access_events] == expected_names

        checks = [event for event in access_events if event[0] == "access.check"]
        assert [(event[2], event[3], event[4]) for event in checks] == [
            (name, mask, mask) for name, mask in rights
        ]
        assert len({event[5] for event in checks}) == 1
        assert len({event[6] for event in checks}) == 1
        assert checks[0][5] == world.events[close_index][2]
        assert checks[0][5] is not None
        assert checks[0][6] is not None
        assert all(event[7] == _FILE_GENERIC_MAPPING for event in checks)
        assert all(event[8] == privilege_capacity for event in checks)
        assert all(event[9] is True for event in checks)
        assert all(event[10] == 0xFFFFFFFF for event in checks)
        assert all(event[11] == -1 for event in checks)

        maps = [event for event in access_events if event[0] == "access.map"]
        assert [(event[2], event[3]) for event in maps] == [
            (mask, mask) for _name, mask in rights
        ]
        assert all(event[4] == _FILE_GENERIC_MAPPING for event in maps)


@pytest.mark.parametrize(
    ("hresult", "has_output"),
    [
        pytest.param(0, False, id="success-null"),
        pytest.param(-1, False, id="failure-null"),
        pytest.param(-1, True, id="failure-owned-buffer"),
    ],
)
def test_known_folder_output_quadrants_are_observation_failures(
    monkeypatch, hresult: int, has_output: bool
) -> None:
    world = _ReaderWorld()
    world.known_folder_hresult = hresult
    world.known_folder_output = has_output

    _expect_reader_error(monkeypatch, world, "observation_failed")

    assert len(world.freed_known_folder) == int(has_output)
    assert world.backend is not None
    assert world.backend.read_count == 0


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(r"c:\ProgramData", id="lowercase-drive"),
        pytest.param("C:\\ProgramData\\", id="trailing-separator"),
        pytest.param("C:\\", id="drive-root-only"),
        pytest.param(r"\\server\share", id="unc"),
        pytest.param(r"\\?\C:\ProgramData", id="extended-prefix"),
        pytest.param(r"ProgramData", id="relative"),
        pytest.param(r"%PROGRAMDATA%", id="environment-shaped"),
        pytest.param(r"C:\base\..\ProgramData", id="dot-dot"),
        pytest.param("C:\\ProgramData ", id="trailing-space"),
        pytest.param("C:\\Progra\u006d\u0301Data", id="non-nfc"),
        pytest.param("C:\\" + "\\".join("x" for _ in range(65)), id="component-cap"),
        pytest.param("C:\\" + "x" * 32768, id="utf16-cap"),
        pytest.param(
            "C:\\" + "\U0001f600" * 16383,
            id="utf16-non-bmp-code-unit-cap",
        ),
    ],
)
def test_known_folder_lexical_boundary_is_closed(monkeypatch, path: str) -> None:
    world = _ReaderWorld()
    world.known_folder_path = path

    _expect_reader_error(monkeypatch, world, "redirected_boundary")

    assert len(world.freed_known_folder) == 1
    assert world.backend is not None
    assert not any(event[0] == "backend.open_root" for event in world.events)


@pytest.mark.parametrize("role", _ROLE_ORDER)
def test_stable_absence_uses_one_probe_and_two_fresh_proof_enumerations(
    monkeypatch, role: str
) -> None:
    world = _ReaderWorld()
    world.missing_role = role
    parent = next(
        parent
        for parent, (child, _name, _file_id, _attributes) in world.child_specs.items()
        if child == role
    )

    _expect_reader_error(monkeypatch, world, "pin_missing")

    assert world.backend is not None
    assert world.backend.enumeration_counts[parent] == 3
    assert world.backend.read_count == 0
    probe_index = next(
        index
        for index, event in enumerate(world.events)
        if event == ("backend.enumerate", parent, "NTFS", 1)
    )
    parent_file_id = (
        None
        if parent == "root"
        else next(
            file_id
            for child, _name, file_id, _attributes in world.child_specs.values()
            if child == parent
        )
    )
    assert _governed_bracket_semantics(world.events, probe_index) == [
        ("token.snapshot",),
        ("token.close",),
        ("backend.enumerate", parent, "NTFS", 1),
        ("backend.snapshot", parent, "NTFS", parent_file_id, "directory", True, 2),
        ("backend.enumerate", parent, "NTFS", 2),
        ("backend.enumerate", parent, "NTFS", 3),
        ("backend.snapshot", parent, "NTFS", parent_file_id, "directory", True, 3),
        ("token.snapshot",),
        ("token.close",),
    ]


def test_intermediate_program_data_absence_has_exact_stable_token_bracket(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    _configure_multicomponent_program_data(world)
    world.missing_role = "pd_shared"

    _expect_reader_error(monkeypatch, world, "pin_missing")

    probe_index = next(
        index
        for index, event in enumerate(world.events)
        if event == ("backend.enumerate", "pd_corp", "NTFS", 1)
    )
    parent_file_id = world.child_specs["root"][2]
    assert _governed_bracket_semantics(world.events, probe_index) == [
        ("token.snapshot",),
        ("token.close",),
        ("backend.enumerate", "pd_corp", "NTFS", 1),
        (
            "backend.snapshot",
            "pd_corp",
            "NTFS",
            parent_file_id,
            "directory",
            True,
            2,
        ),
        ("backend.enumerate", "pd_corp", "NTFS", 2),
        ("backend.enumerate", "pd_corp", "NTFS", 3),
        (
            "backend.snapshot",
            "pd_corp",
            "NTFS",
            parent_file_id,
            "directory",
            True,
            3,
        ),
        ("token.snapshot",),
        ("token.close",),
    ]
    assert world.backend is not None
    assert world.backend.enumeration_counts["pd_corp"] == 3
    assert world.backend.read_count == 0
    assert not any(
        event[:3] == ("backend.open_by_id", "root", "pd_shared")
        for event in world.events
    )


def test_absence_probe_to_proof_membership_change_is_a_race(monkeypatch) -> None:
    world = _ReaderWorld()
    world.missing_role = "pin"
    world.membership_mutation_role = "pin"

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.enumeration_counts["clean_memory"] == 3
    assert world.backend.read_count == 0


def test_absence_first_to_second_proof_membership_change_is_a_race(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.missing_role = "pin"
    world.second_proof_membership_mutation_role = "pin"

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.enumeration_counts["clean_memory"] == 3
    assert world.backend.read_count == 0


def test_absence_proof_target_appearance_is_a_race_and_is_never_promoted(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.missing_role = "pin"
    world.proof_target_appearance_role = "pin"

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.enumeration_counts["clean_memory"] == 3
    assert world.backend.read_count == 0
    assert not any(
        event[:3] == ("backend.open_by_id", "root", "pin")
        for event in world.events
    )


def test_absence_parent_snapshot_change_is_a_race(monkeypatch) -> None:
    world = _ReaderWorld()
    world.missing_role = "pin"
    world.read_snapshot_role = "clean_memory"

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.enumeration_counts["clean_memory"] == 3
    assert world.backend.snapshot_counts["clean_memory"] == 3
    assert world.backend.read_count == 0


def test_absence_specific_post_token_projection_change_is_a_race(monkeypatch) -> None:
    world = _ReaderWorld()
    world.missing_role = "pin"
    world.absence_post_token_drift_role = "pin"

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.enumeration_counts["clean_memory"] == 3
    assert world.backend.read_count == 0
    probe_index = next(
        index
        for index, event in enumerate(world.events)
        if event == ("backend.enumerate", "clean_memory", "NTFS", 1)
    )
    bracket = _governed_bracket_semantics(world.events, probe_index)
    assert bracket[:2] == [("token.snapshot",), ("token.close",)]
    assert bracket[-2:] == [("token.snapshot",), ("token.close",)]
    assert not any(
        event[:3] == ("backend.open_by_id", "root", "pin")
        for event in world.events
    )


@pytest.mark.parametrize("field", ("file_id", "attributes", "file_id_kind"))
def test_absence_complete_tuple_change_is_a_race_even_when_names_are_stable(
    monkeypatch,
    field: str,
) -> None:
    world = _ReaderWorld()
    world.missing_role = "pin"
    world.absence_sibling_mutation_role = "pin"
    world.absence_sibling_mutation_field = field

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.enumeration_counts["clean_memory"] == 3
    assert world.backend.read_count == 0
    results = world.backend.enumeration_results["clean_memory"]
    assert tuple(tuple(entry.name for entry in result) for result in results) == (
        ("unrelated-sibling",),
        ("unrelated-sibling",),
        ("unrelated-sibling",),
    )
    assert results[0] != results[1]
    assert results[1] == results[2]


def test_casefold_collision_is_ambiguous_before_open(monkeypatch) -> None:
    world = _ReaderWorld()
    world.duplicate_role = "goodq"

    _expect_reader_error(monkeypatch, world, "duplicate_identity")

    assert not any(
        event[:3] == ("backend.open_by_id", "root", "goodq")
        for event in world.events
    )


def test_unsupported_filesystem_stops_before_descendant_selection(monkeypatch) -> None:
    world = _ReaderWorld()
    world.filesystem = "FAT32"

    _expect_reader_error(monkeypatch, world, "unsupported_filesystem")

    assert not any(event[0] == "backend.open_by_id" for event in world.events)


@pytest.mark.parametrize("case", ["trailing_zero", "acl_zero_padding"])
def test_descriptor_zero_padding_and_exact_owner_group_alias_are_accepted(
    monkeypatch, case: str
) -> None:
    world = _ReaderWorld()
    world.descriptors["anchor"] = _descriptor_variant(world.descriptors["anchor"], case)

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection["manifest_sha256"] == "a" * 64


@pytest.mark.parametrize(
    ("role", "case", "expected_code"),
    [
        pytest.param("anchor", "truncated_header", "observation_failed", id="header-short"),
        pytest.param("anchor", "descriptor_revision", "observation_failed", id="descriptor-revision"),
        pytest.param("anchor", "descriptor_sbz1", "observation_failed", id="descriptor-reserved"),
        pytest.param("anchor", "missing_self_relative", "observation_failed", id="not-self-relative"),
        pytest.param("anchor", "owner_absent", "unsupported_security", id="owner-absent"),
        pytest.param("anchor", "group_absent", "unsupported_security", id="group-absent"),
        pytest.param("anchor", "dacl_absent", "unsupported_security", id="dacl-absent"),
        pytest.param("anchor", "dacl_not_present", "unsupported_security", id="dacl-not-present"),
        pytest.param("anchor", "owner_out_of_bounds", "observation_failed", id="owner-oob"),
        pytest.param("anchor", "group_out_of_bounds", "observation_failed", id="group-oob"),
        pytest.param("anchor", "dacl_out_of_bounds", "observation_failed", id="dacl-oob"),
        pytest.param("anchor", "owner_inside_header", "observation_failed", id="owner-in-header"),
        pytest.param("anchor", "group_inside_header", "observation_failed", id="group-in-header"),
        pytest.param("anchor", "dacl_inside_header", "observation_failed", id="dacl-in-header"),
        pytest.param("anchor", "trailing_nonzero", "observation_failed", id="trailing-byte"),
        pytest.param("anchor", "unaligned_owner", "observation_failed", id="unaligned-owner"),
        pytest.param("anchor", "unaligned_group", "observation_failed", id="unaligned-group"),
        pytest.param("anchor", "unaligned_dacl", "observation_failed", id="unaligned-dacl"),
        pytest.param("anchor", "partial_owner_group_overlap", "observation_failed", id="partial-alias"),
        pytest.param("anchor", "dacl_aliases_owner", "observation_failed", id="dacl-alias"),
        pytest.param("anchor", "dacl_aliases_group", "observation_failed", id="group-dacl-alias"),
        pytest.param("anchor", "sid_revision", "observation_failed", id="sid-revision"),
        pytest.param(
            "anchor",
            "truncated_declared_ace_sid",
            "observation_failed",
            id="truncated-declared-ace-sid",
        ),
        pytest.param("anchor", "sacl_present", "unsupported_security", id="sacl"),
        pytest.param(
            "anchor",
            "null_sacl_present",
            "unsupported_security",
            id="null-sacl",
        ),
        pytest.param("anchor", "acl_revision", "unsupported_security", id="acl-revision"),
        pytest.param("anchor", "acl_sbz1", "observation_failed", id="acl-reserved-byte"),
        pytest.param("anchor", "acl_sbz2", "observation_failed", id="acl-reserved-word"),
        pytest.param("anchor", "acl_size_short", "observation_failed", id="acl-size-short"),
        pytest.param("anchor", "acl_size_long", "observation_failed", id="acl-size-long"),
        pytest.param("anchor", "ace_count_over_cap", "observation_failed", id="ace-count-cap"),
        pytest.param("anchor", "ace_count_mismatch", "observation_failed", id="ace-count-mismatch"),
        pytest.param("anchor", "ace_size_short", "observation_failed", id="ace-size-short"),
        pytest.param("anchor", "ace_size_long", "observation_failed", id="ace-size-long"),
        pytest.param("anchor", "unsupported_ace", "unsupported_security", id="ace-type"),
        pytest.param("anchor", "unknown_ace_flag", "unsupported_security", id="ace-flag"),
        pytest.param("goodq", "dedicated_inheritance_flag", "security_policy_mismatch", id="dedicated-flags"),
        pytest.param("goodq", "dedicated_auto_inherited", "security_policy_mismatch", id="auto-inherited"),
        pytest.param("goodq", "reader_mask", "security_policy_mismatch", id="reader-mask"),
        pytest.param("anchor", "acl_nonzero_padding", "observation_failed", id="acl-padding"),
    ],
)
def test_descriptor_boundaries_have_exact_classification_before_content(
    monkeypatch, role: str, case: str, expected_code: str
) -> None:
    world = _ReaderWorld()
    world.descriptors[role] = _descriptor_variant(world.descriptors[role], case)

    _expect_reader_error(monkeypatch, world, expected_code)


def test_partially_overlapping_valid_group_and_dacl_intervals_are_malformed(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    descriptor = _descriptor_with_group_dacl_partial_overlap(
        world.reader_sid
    )
    group_offset = struct.unpack_from("<I", descriptor, 8)[0]
    dacl_offset = struct.unpack_from("<I", descriptor, 16)[0]
    group_end = group_offset + 8 + 4 * descriptor[group_offset + 1]
    dacl_end = dacl_offset + struct.unpack_from("<H", descriptor, dacl_offset + 2)[0]
    assert descriptor[group_offset] == 1
    assert descriptor[dacl_offset] in {2, 4}
    assert group_offset < dacl_offset < group_end < dacl_end
    world.descriptors["anchor"] = descriptor

    _expect_reader_error(monkeypatch, world, "observation_failed")

    assert world.backend is not None
    assert world.backend.read_count == 0


def test_empty_anchor_dacl_revision_four_is_a_supported_denial_policy(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_SYSTEM_SID,
        aces=(),
        control=0x8004,
        acl_revision=4,
    )

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection["manifest_sha256"] == "a" * 64


def test_maximum_wire_representable_4095_minimum_size_anchor_aces_are_accepted(
    monkeypatch,
) -> None:
    minimum_ordinary_ace = _ace(1, 0, _sid(0))
    assert len(minimum_ordinary_ace) == 16
    assert 8 + 4095 * len(minimum_ordinary_ace) == 65_528
    world = _ReaderWorld()
    world.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_ADMIN_SID,
        aces=(minimum_ordinary_ace,) * 4095,
        control=0x8004,
        owner_group_alias=True,
    )

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection["manifest_sha256"] == "a" * 64

    assert world.backend is not None
    assert world.backend.read_count == 1
    assert [event for event in world.events if event[0] == "backend.read_bounded"] == [
        ("backend.read_bounded", "pin", 66, 1)
    ]


@pytest.mark.parametrize(
    ("owner", "group", "revision", "alias"),
    [
        pytest.param(_SYSTEM_SID, _SYSTEM_SID, 2, True, id="system-system-alias"),
        pytest.param(_SYSTEM_SID, _ADMIN_SID, 2, False, id="system-admin"),
        pytest.param(_ADMIN_SID, _SYSTEM_SID, 2, False, id="admin-system"),
        pytest.param(_ADMIN_SID, _ADMIN_SID, 2, False, id="admin-admin-separated"),
        pytest.param(_ADMIN_SID, _ADMIN_SID, 4, True, id="anchor-acl-revision-four"),
    ],
)
def test_anchor_accepts_exact_owner_group_domain_aliasing_and_acl_revisions(
    monkeypatch, owner: bytes, group: bytes, revision: int, alias: bool
) -> None:
    world = _ReaderWorld()
    world.descriptors["anchor"] = _descriptor_from_components(
        owner=owner,
        group=group,
        aces=_ordinary_policy_aces(world.reader_sid, 0x00120089),
        control=0x8004,
        acl_revision=revision,
        owner_group_alias=alias,
    )

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection["manifest_sha256"] == "a" * 64


@pytest.mark.parametrize("flags", range(0x20))
def test_anchor_accepts_every_defined_ordinary_ace_flag(
    monkeypatch, flags: int
) -> None:
    world = _ReaderWorld()
    world.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_ADMIN_SID,
        aces=_ordinary_policy_aces(
            world.reader_sid,
            0x001F01FF if flags & 0x08 else 0x00120089,
            reader_flags=flags,
        ),
        control=0x8004,
        owner_group_alias=True,
    )

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection["manifest_sha256"] == "a" * 64


def test_anchor_accepts_ordinary_deny_aces_and_inherit_only_dangerous_allows(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_ADMIN_SID,
        aces=(
            _ace(1, 0x001F01FF, _USERS_SID),
            _ace(0, 0x10000000, world.reader_sid, flags=0x08),
        ),
        control=0x8004,
        owner_group_alias=True,
    )

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection["manifest_sha256"] == "a" * 64


def test_nondefault_anchor_policy_digest_preserves_observed_order_masks_and_flags(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    alternate_sid = _sid(5, 21, 77)
    world.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_SYSTEM_SID,
        aces=(
            _ace(1, 0x10000000, _USERS_SID, flags=0x1F),
            _ace(0, 0x80000000, alternate_sid, flags=0x03),
            _ace(0, 0x40000000, _SYSTEM_SID, flags=0x10),
        ),
        control=0x8004,
        acl_revision=4,
    )
    expected_policy = _security_policy_projection(world)
    expected_policy["anchor"] = {
        "dacl": [
            {
                "flags": "1f",
                "mask": "10000000",
                "sid": "S-1-5-32-545",
                "type": "access_denied",
            },
            {
                "flags": "03",
                "mask": "80000000",
                "sid": _sid_text(alternate_sid),
                "type": "access_allowed",
            },
            {
                "flags": "10",
                "mask": "40000000",
                "sid": "S-1-5-18",
                "type": "access_allowed",
            },
        ],
        "dacl_revision": 4,
        "denied_access_checks": _denied_projection(_DIRECTORY_RIGHTS),
        "descriptor_control": "8004",
        "owner_sid": "S-1-5-32-544",
        "physical_identity": world.snapshots["anchor"].identity_projection,
        "primary_group_sid": "S-1-5-18",
        "role": "program_data_anchor",
    }
    expected_digest = hashlib.sha256(_canonical_bytes(expected_policy)).hexdigest()
    baseline_digest = hashlib.sha256(
        _canonical_bytes(_security_policy_projection(world))
    ).hexdigest()

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection["security_policy_sha256"] == expected_digest
    assert expected_digest != baseline_digest


@pytest.mark.parametrize("raw_mask", [0x00000040, 0x00040000, 0x00080000, 0x10000000])
def test_anchor_rejects_each_self_applicable_dangerous_allow_after_mapping(
    monkeypatch, raw_mask: int
) -> None:
    world = _ReaderWorld()
    world.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_ADMIN_SID,
        aces=(_ace(0, raw_mask, world.reader_sid),),
        control=0x8004,
        owner_group_alias=True,
    )

    _expect_reader_error(monkeypatch, world, "security_policy_mismatch")

    assert world.backend is not None
    assert world.backend.read_count == 0


def test_anchor_generic_checking_copy_preserves_distinct_raw_masks_in_digest(
    monkeypatch,
) -> None:
    digests = []
    for raw_mask in (0x80000000, 0x40000000, 0x20000000):
        world = _ReaderWorld()
        world.descriptors["anchor"] = _descriptor_from_components(
            owner=_ADMIN_SID,
            group=_ADMIN_SID,
            aces=(_ace(0, raw_mask, world.reader_sid),),
            control=0x8004,
            owner_group_alias=True,
        )
        _module, evidence = _read_world(monkeypatch, world)
        digests.append(evidence.projection["security_policy_sha256"])

    assert len(set(digests)) == 3


@pytest.mark.parametrize(
    ("owner", "group", "control"),
    [
        pytest.param(_USERS_SID, _ADMIN_SID, 0x8004, id="anchor-owner-domain"),
        pytest.param(_ADMIN_SID, _USERS_SID, 0x8004, id="anchor-group-domain"),
        pytest.param(_ADMIN_SID, _ADMIN_SID, 0x8005, id="anchor-owner-defaulted"),
        pytest.param(_ADMIN_SID, _ADMIN_SID, 0x8006, id="anchor-group-defaulted"),
        pytest.param(_ADMIN_SID, _ADMIN_SID, 0x800C, id="anchor-dacl-defaulted"),
    ],
)
def test_anchor_supported_but_wrong_static_policy_is_policy_mismatch(
    monkeypatch, owner: bytes, group: bytes, control: int
) -> None:
    world = _ReaderWorld()
    world.descriptors["anchor"] = _descriptor_from_components(
        owner=owner,
        group=group,
        aces=_ordinary_policy_aces(world.reader_sid, 0x00120089),
        control=control,
        owner_group_alias=owner == group,
    )

    _expect_reader_error(monkeypatch, world, "security_policy_mismatch")


@pytest.mark.parametrize(
    "case",
    [
        "owner",
        "group",
        "unprotected",
        "owner_defaulted",
        "group_defaulted",
        "dacl_defaulted",
        "auto_inherit_req",
        "auto_inherited",
        "revision_four",
        "system_mask",
        "admin_mask",
        "reader_mask",
        "wrong_order",
        "deny",
        "extra",
        "duplicate",
        "ace_flags",
    ],
)
def test_dedicated_object_policy_matrix_is_exact(monkeypatch, case: str) -> None:
    world = _ReaderWorld()
    owner = _ADMIN_SID
    group = _ADMIN_SID
    control = 0x9004
    revision = 2
    aces = list(_ordinary_policy_aces(world.reader_sid, 0x001200A1))
    if case == "owner":
        owner = _SYSTEM_SID
    elif case == "group":
        group = _SYSTEM_SID
    elif case == "unprotected":
        control &= ~0x1000
    elif case == "owner_defaulted":
        control |= 0x0001
    elif case == "group_defaulted":
        control |= 0x0002
    elif case == "dacl_defaulted":
        control |= 0x0008
    elif case == "auto_inherit_req":
        control |= 0x0100
    elif case == "auto_inherited":
        control |= 0x0400
    elif case == "revision_four":
        revision = 4
    elif case == "system_mask":
        aces[0] = _ace(0, 0x00120089, _SYSTEM_SID)
    elif case == "admin_mask":
        aces[1] = _ace(0, 0x00120089, _ADMIN_SID)
    elif case == "reader_mask":
        aces[2] = _ace(0, 0x001F01FF, world.reader_sid)
    elif case == "wrong_order":
        aces[0], aces[1] = aces[1], aces[0]
    elif case == "deny":
        aces[2] = _ace(1, 0x001200A1, world.reader_sid)
    elif case == "extra":
        aces.append(_ace(0, 0x00120089, _USERS_SID))
    elif case == "duplicate":
        aces.append(aces[2])
    elif case == "ace_flags":
        aces[2] = _ace(0, 0x001200A1, world.reader_sid, flags=1)
    else:
        raise AssertionError(case)
    world.descriptors["goodq"] = _descriptor_from_components(
        owner=owner,
        group=group,
        aces=tuple(aces),
        control=control,
        acl_revision=revision,
        owner_group_alias=owner == group,
    )

    _expect_reader_error(monkeypatch, world, "security_policy_mismatch")

    assert world.backend is not None
    assert world.backend.read_count == 0


def test_zero_unbound_descriptor_gaps_are_accepted_but_nonzero_gaps_are_malformed(
    monkeypatch,
) -> None:
    accepted = _ReaderWorld()
    accepted.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_ADMIN_SID,
        aces=_ordinary_policy_aces(accepted.reader_sid, 0x00120089),
        control=0x8004,
        owner_group_alias=False,
        header_gap=b"\0" * 4,
        component_gap=b"\0" * 4,
    )
    _read_world(monkeypatch, accepted)

    malformed = _ReaderWorld()
    malformed.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_ADMIN_SID,
        aces=_ordinary_policy_aces(malformed.reader_sid, 0x00120089),
        control=0x8004,
        owner_group_alias=False,
        header_gap=b"\0\0\0\x01",
    )
    _expect_reader_error(monkeypatch, malformed, "observation_failed")


def test_sid_and_ace_exact_length_boundaries_are_enforced(monkeypatch) -> None:
    maximum_sid = _sid(5, *range(15))
    accepted = _ReaderWorld()
    accepted.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_ADMIN_SID,
        aces=(_ace(0, 0x00120089, maximum_sid),),
        control=0x8004,
        owner_group_alias=True,
    )
    _read_world(monkeypatch, accepted)

    too_many = _ReaderWorld()
    sid_count_sixteen = bytes((1, 16)) + (5).to_bytes(6, "big") + b"\0" * 64
    too_many.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_ADMIN_SID,
        aces=(_ace(0, 0x00120089, sid_count_sixteen),),
        control=0x8004,
        owner_group_alias=True,
    )
    _expect_reader_error(monkeypatch, too_many, "observation_failed")

    trailing = _ReaderWorld()
    ordinary = _ace(0, 0x00120089, _USERS_SID)
    ace_with_internal_padding = (
        ordinary[:2]
        + struct.pack("<H", len(ordinary) + 4)
        + ordinary[4:]
        + b"\0" * 4
    )
    trailing.descriptors["anchor"] = _descriptor_from_components(
        owner=_ADMIN_SID,
        group=_ADMIN_SID,
        aces=(ace_with_internal_padding,),
        control=0x8004,
        owner_group_alias=True,
    )
    _expect_reader_error(monkeypatch, trailing, "observation_failed")


def test_valid_a5_payload_and_undefined_primary_impersonation_are_accepted(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    assert b"\xA5" in world.reader_sid
    world.vary_undefined_impersonation = True

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection == _expected_world_evidence(world)
    assert all(
        tuple(
            event[2]
            for event in world.events
            if event[0] == "token.info" and event[1] == handle
        )
        == _TOKEN_NATIVE_CALL_ORDER
        for handle in {event[1] for event in world.events if event[0] == "token.info"}
    )


@pytest.mark.parametrize(
    "case",
    [
        "pointer_escape",
        "group_count_over_cap",
    ],
)
def test_token_buffer_bounds_and_whole_field_sentinels_fail_closed(
    monkeypatch, case: str
) -> None:
    world = _ReaderWorld()
    world.token_buffer_case = case

    _expect_reader_error(monkeypatch, world, "observation_failed")

    assert world.backend is None or world.backend.read_count == 0


def test_token_queries_use_exact_order_sizes_and_fresh_input_sentinels(
    monkeypatch,
) -> None:
    world = _ReaderWorld()

    _read_world(monkeypatch, world)

    baseline = next(
        handle for handle, kind in world._handle_kinds.items() if kind == "baseline"
    )
    inputs = [
        event for event in world.events if event[:2] == ("token.input", baseline)
    ]
    expected_info_and_sizes = [
        (10, 56),
        (1, 0),
        (1, world._required_token_size(1)),
        (2, 0),
        (2, world._required_token_size(2)),
        (3, 0),
        (3, world._required_token_size(3)),
        (11, 0),
        (11, world._required_token_size(11)),
        (18, 4),
        (20, 4),
        (21, 4),
        (25, 0),
        (25, world._required_token_size(25)),
        (26, 4),
        (29, 4),
        (10, 56),
    ]
    assert [(event[2], event[3]) for event in inputs] == expected_info_and_sizes
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


@pytest.mark.parametrize("info_class", [1, 2, 3, 11, 25])
def test_exact_inclusive_variable_token_buffer_cap_accepts_valid_a5_slack(
    monkeypatch, info_class: int
) -> None:
    world = _ReaderWorld()
    world.token_buffer_case = "exact_cap_a5_slack"
    world.token_query_target = info_class

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection == _expected_world_evidence(world)
    assert [event for event in world.events if event[0] == "token.exact_cap"] == [
        (
            "token.exact_cap",
            info_class,
            world._required_token_size(info_class),
            1_048_576,
            True,
        )
    ]
    cap_inputs = [
        event
        for event in world.events
        if event[0] == "token.input"
        and event[2] == info_class
        and event[3] == 1_048_576
    ]
    assert len(cap_inputs) == 1
    assert cap_inputs[0][5] == ("variable", True)
    assert world.backend is not None
    assert world.backend.read_count == 1


@pytest.mark.parametrize(
    ("case", "expected_user_calls"),
    [
        pytest.param("sizing_success", 1, id="sizing-success-is-invalid"),
        pytest.param("sizing_wrong_error", 1, id="sizing-wrong-last-error"),
        pytest.param("zero_required", 1, id="zero-required-size"),
        pytest.param("over_cap_required", 1, id="over-cap-required-size"),
        pytest.param("fill_failure_dirty", 2, id="fill-failure-dirty-output"),
        pytest.param("size_changed", 2, id="fill-size-changed"),
    ],
)
@pytest.mark.parametrize("info_class", [1, 2, 3, 11, 25])
def test_variable_token_query_sizing_and_fill_quadrants_do_not_retry(
    monkeypatch, case: str, expected_user_calls: int, info_class: int
) -> None:
    world = _ReaderWorld()
    world.token_buffer_case = case
    world.token_query_target = info_class

    _expect_reader_error(monkeypatch, world, "observation_failed")

    target_calls = [
        event
        for event in world.events
        if event[0] == "token.info" and event[2] == info_class
    ]
    assert len(target_calls) == expected_user_calls
    assert world.backend is None or world.backend.read_count == 0


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
def test_every_token_sid_pointer_must_be_wholly_contained(monkeypatch, case: str) -> None:
    token = _TokenSpec()
    if case.startswith("restricted_"):
        token = dataclasses.replace(
            token,
            restricted_sids=((_sid(5, 12), 0),),
        )
    world = _ReaderWorld(token=token)
    world.token_buffer_case = case

    _expect_reader_error(monkeypatch, world, "observation_failed")

    assert world.backend is None or world.backend.read_count == 0


def test_partially_overlapping_individually_valid_token_sid_intervals_are_malformed(
    monkeypatch,
) -> None:
    first_sid = (
        bytes((1, 2))
        + (5).to_bytes(6, "big")
        + bytes((1, 1))
        + (7).to_bytes(6, "big")
    )
    assert len(first_sid) == 16
    assert first_sid[8:10] == b"\x01\x01"
    token = dataclasses.replace(
        _TokenSpec(),
        groups=((first_sid, 0), (_sid(5, 99), 0)),
    )
    world = _ReaderWorld(token=token)
    world.token_buffer_case = "group_cross_record_partial_overlap"
    base = 0x1000
    payload = world._variable_payload(2, base)
    first_pointer = struct.unpack_from("<Q", payload, 8)[0]
    second_pointer = struct.unpack_from("<Q", payload, 24)[0]
    first_offset = first_pointer - base
    second_offset = second_pointer - base
    first_end = first_pointer + 8 + 4 * payload[first_offset + 1]
    second_end = second_pointer + 8 + 4 * payload[second_offset + 1]
    assert payload[first_offset] == payload[second_offset] == 1
    assert first_pointer < second_pointer < first_end < second_end

    _expect_reader_error(monkeypatch, world, "observation_failed")

    assert world.backend is not None
    assert world.backend.handles == []
    assert world.backend.closed == []
    assert world.backend.read_count == 0
    assert [event for event in world.events if event[0] == "backend.construct"] == [
        ("backend.construct", "security_read")
    ]
    assert not any(event[0] == "backend.open_root" for event in world.events)


@pytest.mark.parametrize(
    "case",
    ["group_count_over_cap", "restricted_count_over_cap", "privilege_count_over_cap"],
)
def test_each_variable_token_count_cap_is_checked_before_records(
    monkeypatch, case: str
) -> None:
    world = _ReaderWorld()
    world.token_buffer_case = case

    _expect_reader_error(monkeypatch, world, "observation_failed")


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
def test_fixed_token_query_failure_and_sentinel_outputs_fail_without_retry(
    monkeypatch, case: str
) -> None:
    world = _ReaderWorld()
    world.token_buffer_case = case

    _expect_reader_error(monkeypatch, world, "observation_failed")

    calls = [event for event in world.events if event[0] == "token.info" and event[2] == 10]
    assert len(calls) == 1


@pytest.mark.parametrize("info_class", [18, 20, 21, 26, 29])
@pytest.mark.parametrize(
    "case_prefix",
    ["fixed_failure_dirty", "omit_fixed", "short_fixed", "long_fixed"],
)
def test_each_fixed_token_class_closes_failure_write_and_length_quadrants(
    monkeypatch, info_class: int, case_prefix: str
) -> None:
    world = _ReaderWorld()
    world.token_query_target = info_class
    world.token_buffer_case = f"{case_prefix}_{info_class}"

    _expect_reader_error(monkeypatch, world, "observation_failed")

    calls = [
        event
        for event in world.events
        if event[0] == "token.info" and event[2] == info_class
    ]
    assert len(calls) == 1


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(dataclasses.replace(_TokenSpec(), token_type=0), id="token-type-zero"),
        pytest.param(dataclasses.replace(_TokenSpec(), token_type=3), id="token-type-three"),
        pytest.param(dataclasses.replace(_TokenSpec(), elevation_type=0), id="elevation-type-zero"),
        pytest.param(dataclasses.replace(_TokenSpec(), elevation_type=4), id="elevation-type-four"),
        pytest.param(dataclasses.replace(_TokenSpec(), is_elevated=2), id="elevation-bool"),
        pytest.param(dataclasses.replace(_TokenSpec(), has_restrictions=2), id="restriction-bool"),
        pytest.param(dataclasses.replace(_TokenSpec(), ui_access=2), id="uiaccess-bool"),
        pytest.param(dataclasses.replace(_TokenSpec(), is_app_container=2), id="appcontainer-bool"),
    ],
)
def test_out_of_domain_fixed_token_semantics_are_observation_failures(
    monkeypatch, token: _TokenSpec
) -> None:
    world = _ReaderWorld(token=token)

    _expect_reader_error(monkeypatch, world, "observation_failed")


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
def test_each_defined_internal_statistics_field_is_fenced(
    monkeypatch, field: str
) -> None:
    world = _ReaderWorld()
    world.statistics_drift_field = field

    _expect_reader_error(monkeypatch, world, "observation_failed")

    assert world.backend is None or world.backend.read_count == 0


@pytest.mark.parametrize("field", ["groups", "privileges"])
def test_statistics_counts_must_equal_parsed_array_counts(
    monkeypatch, field: str
) -> None:
    world = _ReaderWorld()
    if field == "groups":
        world.statistics_group_count = len(world.token.groups) + 1
    else:
        world.statistics_privilege_count = len(world.token.privileges) + 1

    _expect_reader_error(monkeypatch, world, "observation_failed")


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(
            dataclasses.replace(
                _TokenSpec(), groups=((_USERS_SID, 7), (_USERS_SID, 0))
            ),
            id="duplicate-group-sid",
        ),
        pytest.param(
            dataclasses.replace(
                _TokenSpec(), privileges=(((0x17, 0), 2), ((0x17, 0), 0))
            ),
            id="duplicate-privilege-luid",
        ),
        pytest.param(
            dataclasses.replace(
                _TokenSpec(),
                restricted_sids=((_sid(5, 12), 0), (_sid(5, 12), 1)),
            ),
            id="duplicate-restricted-sid",
        ),
    ],
)
def test_duplicate_token_sid_and_luid_records_are_malformed_observations(
    monkeypatch, token: _TokenSpec
) -> None:
    world = _ReaderWorld(token=token)

    _expect_reader_error(monkeypatch, world, "observation_failed")


def test_token_arrays_use_binary_sid_and_unsigned_luid_sort_authority(
    monkeypatch,
) -> None:
    token = dataclasses.replace(
        _TokenSpec(),
        groups=((_sid(5, 21, 300), 1), (_USERS_SID, 7), (_sid(5, 21, 2), 0)),
        privileges=(((1, -1), 0), ((0x17, 0), 2), ((2, 0), 0)),
    )
    world = _ReaderWorld(token=token)

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection == _expected_world_evidence(world)


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(
            dataclasses.replace(
                _TokenSpec(), groups=((_USERS_SID, 7), (_ADMIN_SID, 0x10))
            ),
            id="admin-deny-only-not-enabled",
        ),
        pytest.param(
            dataclasses.replace(
                _TokenSpec(), privileges=(((0x17, 0), 2), ((0x99, 0), 0))
            ),
            id="extra-privilege-disabled",
        ),
        pytest.param(
            dataclasses.replace(_TokenSpec(), groups=(), privileges=()),
            id="zero-groups-and-privileges",
        ),
    ],
)
def test_exact_accepted_group_and_privilege_policy_variants(
    monkeypatch, token: _TokenSpec
) -> None:
    world = _ReaderWorld(token=token)

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection == _expected_world_evidence(world)


@pytest.mark.parametrize("kind", ["groups", "privileges"])
def test_token_array_exact_4096_record_boundary_is_accepted(
    monkeypatch, kind: str
) -> None:
    if kind == "groups":
        token = dataclasses.replace(
            _TokenSpec(),
            groups=tuple((_sid(5, 21, index), 0) for index in range(4096)),
        )
    else:
        token = dataclasses.replace(
            _TokenSpec(),
            privileges=tuple(((index, 1), 0) for index in range(4096)),
        )
    world = _ReaderWorld(token=token)

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection == _expected_world_evidence(world)


def test_exact_4096_restricted_sid_records_are_parsed_before_policy_rejection(
    monkeypatch,
) -> None:
    token = dataclasses.replace(
        _TokenSpec(),
        restricted_sids=tuple((_sid(5, 12, index), 0) for index in range(4096)),
    )
    world = _ReaderWorld(token=token)

    _expect_reader_error(monkeypatch, world, "untrusted_reader")

    restricted_queries = [
        event
        for event in world.events
        if event[0] == "token.info" and event[2] == 11
    ]
    assert len(restricted_queries) == 2
    assert world.backend is not None
    assert world.backend.handles == []
    assert world.backend.closed == []
    assert world.backend.read_count == 0
    assert [event for event in world.events if event[0] == "backend.construct"] == [
        ("backend.construct", "security_read")
    ]
    assert not any(event[0] == "backend.open_root" for event in world.events)


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(
            dataclasses.replace(
                _TokenSpec(), groups=((_ADMIN_SID, 0x00000007),)
            ),
            id="admin-enabled",
        ),
        pytest.param(
            dataclasses.replace(
                _TokenSpec(),
                privileges=(((0x17, 0), 0x2), ((0x99, 0), 0x2)),
            ),
            id="extra-enabled-privilege",
        ),
        pytest.param(
            dataclasses.replace(
                _TokenSpec(), restricted_sids=((_sid(5, 12), 0),)
            ),
            id="restricted-sid",
        ),
        pytest.param(
            dataclasses.replace(_TokenSpec(), integrity_sid=_sid(5, 8192)),
            id="noncanonical-medium-integrity",
        ),
        pytest.param(
            dataclasses.replace(_TokenSpec(), elevation_type=2, is_elevated=1),
            id="full-elevation",
        ),
        pytest.param(
            dataclasses.replace(_TokenSpec(), elevation_type=3, has_restrictions=0),
            id="limited-pairing",
        ),
        pytest.param(
            dataclasses.replace(_TokenSpec(), is_app_container=1),
            id="app-container",
        ),
        pytest.param(
            dataclasses.replace(_TokenSpec(), ui_access=1),
            id="ui-access",
        ),
        pytest.param(
            dataclasses.replace(_TokenSpec(), token_type=2),
            id="impersonation-token-type",
        ),
    ],
)
def test_intrinsically_untrusted_tokens_never_reach_storage(
    monkeypatch, token: _TokenSpec
) -> None:
    world = _ReaderWorld(token=token)

    _expect_reader_error(monkeypatch, world, "untrusted_reader")

    assert world.backend is None or not any(
        event[0] == "backend.open_root" for event in world.events
    )


def test_valid_limited_token_remains_distinct_in_reader_digest(monkeypatch) -> None:
    token = dataclasses.replace(
        _TokenSpec(), elevation_type=3, has_restrictions=1
    )
    world = _ReaderWorld(token=token)

    _module, evidence = _read_world(monkeypatch, world)

    assert evidence.projection == _expected_world_evidence(world)
    assert _reader_identity_projection(token)["elevation"] == {
        "is_elevated": False,
        "type": "limited",
    }


@pytest.mark.parametrize(
    ("attribute", "value", "expected_code"),
    [
        ("thread_case", "success_nonnull", "untrusted_reader"),
        ("thread_case", "success_null", "observation_failed"),
        ("thread_case", "failure_other", "observation_failed"),
        ("process_case", "success_null", "observation_failed"),
        ("process_case", "failure_sentinel", "observation_failed"),
        ("duplicate_case", "success_null", "observation_failed"),
        ("duplicate_case", "failure_sentinel", "observation_failed"),
    ],
)
def test_token_handle_output_quadrants_own_only_successful_nonnull_handles(
    monkeypatch, attribute: str, value: str, expected_code: str
) -> None:
    world = _ReaderWorld()
    setattr(world, attribute, value)

    _expect_reader_error(monkeypatch, world, expected_code)

    assert not any(
        event[0] == "native.close" and event[2] in {0xDEAD0001, 0xDEAD0002, 0xDEAD0003}
        for event in world.events
    )


def test_new_thread_token_at_outer_fence_is_a_race_and_is_closed(monkeypatch) -> None:
    world = _ReaderWorld()
    world.comparison_thread_at = 2

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert any(event[:2] == ("native.close", "thread") for event in world.events)


def test_defined_token_change_at_outer_fence_is_a_race(monkeypatch) -> None:
    world = _ReaderWorld()
    world.outer_token_drift_at = 2

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is None or world.backend.read_count == 0


def test_final_fence_post_snapshot_token_change_is_a_race_after_read(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.outer_token_drift_at = 38

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.read_count == 1
    assert any(
        event[:3] == ("token.snapshot", "transient", 38)
        for event in world.events
    )


def test_enrollment_policy_disagreement_precedes_token_mismatch(monkeypatch) -> None:
    world = _ReaderWorld()
    other_sid = _sid(5, 21, 777)
    world.token = dataclasses.replace(world.token, user_sid=other_sid)
    world.descriptors["authority"] = _descriptor(
        reader_sid=_sid(5, 21, 888),
        reader_mask=0x001200A1,
        control=0x9004,
    )

    _expect_reader_error(monkeypatch, world, "security_policy_mismatch")

    assert world.backend is not None
    assert world.backend.read_count == 0


def test_common_enrollment_sid_must_match_token_user(monkeypatch) -> None:
    world = _ReaderWorld()
    world.token = dataclasses.replace(world.token, user_sid=_sid(5, 21, 777))

    _expect_reader_error(monkeypatch, world, "untrusted_reader")

    assert world.backend is not None
    assert world.backend.read_count == 0


def test_pin_reader_sid_must_match_already_bound_enrollment(monkeypatch) -> None:
    world = _ReaderWorld()
    world.descriptors["pin"] = _descriptor(
        reader_sid=_sid(5, 21, 999),
        reader_mask=0x00120089,
        control=0x9004,
    )

    _expect_reader_error(monkeypatch, world, "security_policy_mismatch")

    assert world.backend is not None
    assert world.backend.read_count == 0


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("grant", "security_policy_mismatch"),
        ("true_extra_bits", "observation_failed"),
        ("true_missing_bits", "observation_failed"),
        ("status_two", "observation_failed"),
        ("false_nonzero_grant", "observation_failed"),
        ("omitted_status", "observation_failed"),
        ("native_failure_dirty", "observation_failed"),
        ("privilege_short", "observation_failed"),
        ("privilege_long", "observation_failed"),
        ("privilege_count_over_cap", "observation_failed"),
        ("privilege_bad_control", "observation_failed"),
        ("privilege_nonzero_trailing", "observation_failed"),
    ],
)
def test_access_check_quadrants_and_privilege_outputs_fail_closed(
    monkeypatch, case: str, expected_code: str
) -> None:
    world = _ReaderWorld()
    world.access_case = case

    _expect_reader_error(monkeypatch, world, expected_code)

    assert len([event for event in world.events if event[0] == "access.check"]) == 1
    duplicate_events = [
        event for event in world.events if event[:2] == ("native.close", "duplicate")
    ]
    assert len(duplicate_events) == 1
    assert world.max_live_duplicates == 1
    assert world.backend is not None
    assert world.backend.read_count == 0


def test_access_check_rejects_nonzero_privilege_output_for_denial(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.access_case = "denial_nonzero_privilege_output"

    _expect_reader_error(monkeypatch, world, "observation_failed")

    checks = [event for event in world.events if event[0] == "access.check"]
    assert len(checks) == 1
    duplicate_closes = [
        event for event in world.events if event[:2] == ("native.close", "duplicate")
    ]
    assert len(duplicate_closes) == 1
    assert world.backend is not None
    assert world.backend.read_count == 0
    assert not any(event[0] == "backend.read_bounded" for event in world.events)


@pytest.mark.parametrize(
    ("payload", "explicit_eof"),
    [
        pytest.param(b"a" * 64, True, id="missing-newline"),
        pytest.param(b"a" * 64 + b"\r", True, id="wrong-terminator"),
        pytest.param(b"A" * 64 + b"\n", True, id="uppercase"),
        pytest.param(b"g" * 64 + b"\n", True, id="nonhex"),
        pytest.param(b"a" * 65 + b"\n", False, id="over-bound"),
        pytest.param(b"a" * 64 + b"\n", False, id="no-eof"),
    ],
)
def test_pin_payload_requires_exact_single_bounded_read(
    monkeypatch, payload: bytes, explicit_eof: bool
) -> None:
    world = _ReaderWorld()
    world.payload = payload
    world.explicit_eof = explicit_eof

    _expect_reader_error(monkeypatch, world, "malformed_pin")

    assert world.backend is not None
    assert world.backend.read_count == 1
    reads = [event for event in world.events if event[0] == "backend.read_bounded"]
    assert reads == [("backend.read_bounded", "pin", 66, 1)]


@pytest.mark.parametrize(
    ("attribute", "role"),
    [
        *(("recheck_descriptor_role", role) for role in _ROLE_ORDER),
        *(
            ("recheck_snapshot_role", role)
            for role in ("root", "anchor", "goodq", "authority", "clean_memory", "pin")
        ),
        *(("recheck_membership_role", role) for role in _ROLE_ORDER),
        ("recheck_stream_role", "pin"),
    ],
)
def test_final_authority_mutations_are_observation_races(
    monkeypatch, attribute: str, role: str
) -> None:
    world = _ReaderWorld()
    setattr(world, attribute, role)

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.read_count == 1


@pytest.mark.parametrize("role", _ROLE_ORDER)
def test_final_parent_tuple_replacement_with_same_cardinality_is_a_race(
    monkeypatch, role: str
) -> None:
    world = _ReaderWorld()
    world.recheck_membership_replace_role = role
    parent = next(
        parent_role
        for parent_role, (child, _name, _file_id, _attributes)
        in world.child_specs.items()
        if child == role
    )

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.read_count == 1
    assert world.backend.enumeration_counts[parent] == 2


def test_post_read_same_handle_snapshot_mutation_is_an_observation_race(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.read_snapshot_role = "pin"

    _expect_reader_error(monkeypatch, world, "observation_raced")

    assert world.backend is not None
    assert world.backend.read_count == 1
    assert world.backend.snapshot_counts["pin"] == 2


def test_backend_error_and_entire_public_chain_are_sanitized(monkeypatch) -> None:
    world = _ReaderWorld()
    world.backend_failure = ("snapshot", "anchor")

    module, error = _expect_reader_error(monkeypatch, world, "observation_failed")

    _assert_sanitized_chain(module, error)


def test_success_cleanup_ownership_and_release_order_are_exact(monkeypatch) -> None:
    world = _ReaderWorld()

    _read_world(monkeypatch, world)

    assert [event for event in world.events if event[0] == "backend.enter"] == [
        ("backend.enter",)
    ]
    assert [event for event in world.events if event[0] == "backend.exit"] == [
        ("backend.exit", False)
    ]
    enter_index = world.events.index(("backend.enter",))
    baseline_open_index = next(
        index
        for index, event in enumerate(world.events)
        if event[:2] == ("token.open_process", 1)
    )
    exit_index = world.events.index(("backend.exit", False))
    assert enter_index < baseline_open_index < exit_index
    backend_close_indices = [
        index
        for index, event in enumerate(world.events)
        if event[0] == "backend.close"
    ]
    assert backend_close_indices
    assert exit_index < min(backend_close_indices)

    known_index = next(
        index for index, event in enumerate(world.events) if event[0] == "known_folder"
    )
    assert world.events[known_index + 1][0] == "known_folder.free"
    assert world.events[known_index + 1][1] in world.freed_known_folder

    transient_snapshots = [
        (index, event)
        for index, event in enumerate(world.events)
        if event[:2] == ("token.snapshot", "transient")
    ]
    assert len(transient_snapshots) == 38
    for index, snapshot_event in transient_snapshots:
        assert world.events[index + 1] == (
            "native.close",
            "transient",
            snapshot_event[3],
        )

    transient_handles = {
        handle for handle, kind in world._handle_kinds.items() if kind == "transient"
    }
    assert transient_handles == {
        event[2]
        for event in world.events
        if event[:2] == ("native.close", "transient")
    }
    assert world._close_counts == {
        "transient": 38,
        "duplicate": 5,
        "baseline": 1,
    }
    baseline_close = next(
        index
        for index, event in enumerate(world.events)
        if event[:2] == ("native.close", "baseline")
    )
    assert baseline_close > max(
        index for index, event in enumerate(world.events) if event[0] == "backend.close"
    )
    assert world.events[baseline_close + 1 :] == []


@pytest.mark.parametrize(
    "exception_type",
    [KeyboardInterrupt, SystemExit, GeneratorExit],
)
def test_backend_control_flow_primary_is_re_raised_after_context_cleanup(
    monkeypatch,
    exception_type: type[BaseException],
) -> None:
    world = _ReaderWorld()
    primary = exception_type()
    original_traceback = _prime_control_primary(primary)
    world.backend_exception = ("snapshot", "anchor", primary)
    module = _install_reader_world(monkeypatch, world)

    with pytest.raises(exception_type) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    assert primary.__cause__ is None
    assert primary.__context__ is None
    assert world.backend is not None
    assert world.backend.closed == ["anchor", "root"]
    assert world.backend.handles == []
    assert [event for event in world.events if event[0] == "backend.exit"] == [
        ("backend.exit", False)
    ]
    assert world._close_counts == {"transient": 5, "baseline": 1}


def test_transient_token_control_flow_primary_closes_transient_before_propagation(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    primary = KeyboardInterrupt()
    original_traceback = _prime_control_primary(primary)
    world.token_snapshot_exception_kind = "transient"
    world.token_snapshot_exception = primary
    module = _install_reader_world(monkeypatch, world)

    with pytest.raises(KeyboardInterrupt) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    assert world._close_counts == {"transient": 1, "baseline": 1}
    assert [event for event in world.events if event[0] == "backend.exit"] == [
        ("backend.exit", False)
    ]


def test_duplicate_token_control_flow_primary_closes_duplicate_before_propagation(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    primary = SystemExit()
    original_traceback = _prime_control_primary(primary)
    world.access_exception = primary
    module = _install_reader_world(monkeypatch, world)

    with pytest.raises(SystemExit) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    assert world._close_counts["duplicate"] == 1
    assert world._close_counts["baseline"] == 1
    assert world._live_duplicates == set()
    assert world._current_access_role is None
    assert world.backend is not None
    assert world.backend.closed == [
        "clean_memory",
        "authority",
        "goodq",
        "anchor",
        "root",
    ]


def test_known_folder_control_flow_primary_frees_buffer_before_propagation(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    primary = GeneratorExit()
    original_traceback = _prime_control_primary(primary)
    world.known_folder_call_exception = primary
    module = _install_reader_world(monkeypatch, world)

    with pytest.raises(GeneratorExit) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    assert len(world.freed_known_folder) == 1
    assert world._close_counts == {"transient": 1, "baseline": 1}
    assert [event for event in world.events if event[0] == "backend.exit"] == [
        ("backend.exit", False)
    ]


def test_control_flow_primary_keeps_identity_and_sanitizes_cleanup_failures(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    primary = KeyboardInterrupt()
    original_traceback = _prime_control_primary(primary)
    world.backend_exception = ("snapshot", "anchor", primary)
    world.backend_close_failure = True
    world.native_close_failure_kind = "baseline"
    world.native_close_failure_at = 1
    module = _install_reader_world(monkeypatch, world)
    backend_cleanup_nodes, baseline_cleanup_nodes = _capture_top_cleanup_nodes(
        monkeypatch,
        module,
        world,
    )

    with pytest.raises(KeyboardInterrupt) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    _assert_control_primary_has_only_sanitized_cleanup(
        module,
        primary,
        expected_cleanup_count=2,
    )
    assert len(backend_cleanup_nodes) == 1
    assert len(baseline_cleanup_nodes) == 1
    assert primary.__cause__ is backend_cleanup_nodes[0]
    assert backend_cleanup_nodes[0].__cause__ is baseline_cleanup_nodes[0]
    assert world.backend is not None
    assert world.backend.closed == ["anchor", "root"]
    assert world.backend.handles == []
    assert world._close_counts["baseline"] == 1
    assert _SECRET_MARKER not in repr(primary.__cause__)


def test_cleanup_only_keeps_backend_then_baseline_failure_chain(monkeypatch) -> None:
    world = _ReaderWorld()
    world.backend_close_failure = True
    world.native_close_failure_kind = "baseline"
    world.native_close_failure_at = 1
    module = _install_reader_world(monkeypatch, world)
    backend_cleanup_nodes, baseline_cleanup_nodes = _capture_top_cleanup_nodes(
        monkeypatch,
        module,
        world,
    )

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert len(backend_cleanup_nodes) == 1
    assert len(baseline_cleanup_nodes) == 1
    assert error is backend_cleanup_nodes[0]
    assert error.__cause__ is baseline_cleanup_nodes[0]
    assert error.__context__ is None
    assert baseline_cleanup_nodes[0].__cause__ is None
    assert baseline_cleanup_nodes[0].__context__ is None
    _assert_sanitized_chain(module, error)
    assert len(_walk_exception_chain(error)) == 2


def test_cleanup_aggregation_does_not_depend_on_dynamic_set_allocation(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.backend_close_failure = True
    world.native_close_failure_kind = "baseline"
    world.native_close_failure_at = 1
    module = _install_reader_world(monkeypatch, world)
    backend_cleanup_nodes, baseline_cleanup_nodes = _capture_top_cleanup_nodes(
        monkeypatch,
        module,
        world,
    )
    backend_type = _FakeHeldHandleBackend
    original_exit = backend_type.__exit__
    cleanup_started = False
    original_set = set

    def arm_cleanup_allocation_fault(self, exc_type, exc, traceback):
        nonlocal cleanup_started
        cleanup_started = True
        return original_exit(self, exc_type, exc, traceback)

    def reject_cleanup_allocation(*_args, **_kwargs):
        if cleanup_started:
            raise MemoryError(_SECRET_MARKER)
        return original_set(*_args, **_kwargs)

    monkeypatch.setattr(backend_type, "__exit__", arm_cleanup_allocation_fault)
    monkeypatch.setattr(module, "set", reject_cleanup_allocation, raising=False)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error.code == "observation_failed"
    _assert_sanitized_chain(module, error)
    assert len(backend_cleanup_nodes) == 1
    assert len(baseline_cleanup_nodes) == 1
    assert error is backend_cleanup_nodes[0]
    assert error.__cause__ is baseline_cleanup_nodes[0]
    assert len(_walk_exception_chain(error)) == 2
    assert _SECRET_MARKER not in repr(_walk_exception_chain(error))
    assert world._close_counts["baseline"] == 1
    assert world.backend is not None
    assert world.backend.closed == [
        "pin",
        "clean_memory",
        "authority",
        "goodq",
        "anchor",
        "root",
    ]
    assert world.backend.handles == []


def test_operation_primary_sanitization_allocation_failure_is_contained(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    primary = module.ExternalPinReaderError("redirected_boundary")
    world.backend_exception = ("read_file_bounded", "pin", primary)
    backend_type = _FakeHeldHandleBackend
    original_exit = backend_type.__exit__
    cleanup_started = False
    original_set = set

    def arm_primary_sanitization_fault(self, exc_type, exc, traceback):
        nonlocal cleanup_started
        cleanup_started = True
        return original_exit(self, exc_type, exc, traceback)

    def reject_post_cleanup_allocation(*args, **kwargs):
        if cleanup_started:
            raise MemoryError(_SECRET_MARKER)
        return original_set(*args, **kwargs)

    monkeypatch.setattr(backend_type, "__exit__", arm_primary_sanitization_fault)
    monkeypatch.setattr(module, "set", reject_post_cleanup_allocation, raising=False)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error.code == "observation_failed"
    _assert_sanitized_chain(module, error)
    assert len(_walk_exception_chain(error)) == 1
    assert _SECRET_MARKER not in repr(error)
    assert world.backend is not None
    assert world.backend.handles == []
    assert world._close_counts["baseline"] == 1


def test_backend_cleanup_sanitization_failure_cannot_skip_baseline_close(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    backend_type = _FakeHeldHandleBackend
    original_exit = backend_type.__exit__
    first = WindowsHeldHandleError("observation_failed")
    second = WindowsHeldHandleError("observation_failed")
    first.__context__ = second

    def chained_exit(self, exc_type, exc, traceback):
        result = original_exit(self, exc_type, exc, traceback)
        assert result is False
        raise first

    monkeypatch.setattr(backend_type, "__exit__", chained_exit)
    original_sanitize = module._sanitize_error
    sanitize_calls: list[BaseException] = []
    later_sanitized_nodes: list[BaseException] = []

    def fail_backend_sanitization(error: BaseException):
        if isinstance(error, WindowsHeldHandleError):
            sanitize_calls.append(error)
            if len(sanitize_calls) == 1:
                raise MemoryError(_SECRET_MARKER)
            sanitized = original_sanitize(error)
            later_sanitized_nodes.append(sanitized)
            return sanitized
        return original_sanitize(error)

    monkeypatch.setattr(module, "_sanitize_error", fail_backend_sanitization)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error.code == "observation_failed"
    _assert_sanitized_chain(module, error)
    assert sanitize_calls == [first, second]
    assert len(later_sanitized_nodes) == 1
    assert error.__context__ is None
    assert error.__cause__ is later_sanitized_nodes[0]
    processing_failure = later_sanitized_nodes[0].__cause__
    assert type(processing_failure) is module.ExternalPinReaderError
    assert processing_failure.code == "observation_failed"
    assert processing_failure.__cause__ is None
    assert processing_failure.__context__ is None
    assert len(_walk_exception_chain(error)) == 3
    assert world._close_counts["baseline"] == 1
    assert world.backend is not None
    assert world.backend.handles == []


def test_cyclic_backend_cleanup_graph_is_bounded_and_signaled(monkeypatch) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    backend_type = _FakeHeldHandleBackend
    original_exit = backend_type.__exit__
    first = WindowsHeldHandleError("observation_failed")
    second = WindowsHeldHandleError("observation_failed")
    first.__cause__ = second
    first.__suppress_context__ = True
    second.__cause__ = first
    second.__suppress_context__ = True

    def cyclic_exit(self, exc_type, exc, traceback):
        result = original_exit(self, exc_type, exc, traceback)
        assert result is False
        raise first

    monkeypatch.setattr(backend_type, "__exit__", cyclic_exit)
    original_sanitize = module._sanitize_error

    def sanitize_one(error: BaseException):
        if isinstance(error, WindowsHeldHandleError):
            return module.ExternalPinReaderError("observation_failed")
        return original_sanitize(error)

    monkeypatch.setattr(module, "_sanitize_error", sanitize_one)
    original_append = module._append_cleanup
    append_calls = 0

    def bounded_append(head, later):
        nonlocal append_calls
        append_calls += 1
        if append_calls > 8:
            raise AssertionError("cyclic cleanup traversal exceeded fixed bound")
        return original_append(head, later)

    monkeypatch.setattr(module, "_append_cleanup", bounded_append)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error.code == "observation_failed"
    _assert_sanitized_chain(module, error)
    _assert_linear_cause_chain(error, expected_length=3)
    assert append_calls <= 4
    assert world._close_counts["baseline"] == 1
    assert world.backend is not None
    assert world.backend.handles == []


def test_over_depth_backend_cleanup_graph_is_bounded_and_signaled(monkeypatch) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    backend_type = _FakeHeldHandleBackend
    original_exit = backend_type.__exit__
    raw_nodes = [WindowsHeldHandleError("observation_failed") for _ in range(300)]
    for current, later in zip(raw_nodes, raw_nodes[1:]):
        current.__cause__ = later
        current.__suppress_context__ = True

    def over_depth_exit(self, exc_type, exc, traceback):
        result = original_exit(self, exc_type, exc, traceback)
        assert result is False
        raise raw_nodes[0]

    monkeypatch.setattr(backend_type, "__exit__", over_depth_exit)
    original_sanitize = module._sanitize_error

    def sanitize_one(error: BaseException):
        if isinstance(error, WindowsHeldHandleError):
            return module.ExternalPinReaderError("observation_failed")
        return original_sanitize(error)

    monkeypatch.setattr(module, "_sanitize_error", sanitize_one)
    original_append = module._append_cleanup
    append_calls = 0

    def bounded_append(head, later):
        nonlocal append_calls
        append_calls += 1
        if append_calls > 258:
            raise AssertionError("cleanup traversal exceeded the fixed hop budget")
        return original_append(head, later)

    monkeypatch.setattr(module, "_append_cleanup", bounded_append)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error.code == "observation_failed"
    _assert_sanitized_chain(module, error)
    chain = _assert_linear_cause_chain(error, expected_length=257)
    assert all(node.code == "observation_failed" for node in chain)
    assert append_calls == 258
    assert world._close_counts["baseline"] == 1
    assert world.backend is not None
    assert world.backend.handles == []


def test_exact_cleanup_hop_budget_does_not_add_processing_failure(monkeypatch) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    backend_type = _FakeHeldHandleBackend
    original_exit = backend_type.__exit__
    raw_nodes = [WindowsHeldHandleError("observation_failed") for _ in range(256)]
    for current, later in zip(raw_nodes, raw_nodes[1:]):
        current.__cause__ = later
        current.__suppress_context__ = True

    def exact_budget_exit(self, exc_type, exc, traceback):
        result = original_exit(self, exc_type, exc, traceback)
        assert result is False
        raise raw_nodes[0]

    monkeypatch.setattr(backend_type, "__exit__", exact_budget_exit)
    original_sanitize = module._sanitize_error

    def sanitize_one(error: BaseException):
        if isinstance(error, WindowsHeldHandleError):
            return module.ExternalPinReaderError("observation_failed")
        return original_sanitize(error)

    monkeypatch.setattr(module, "_sanitize_error", sanitize_one)
    original_append = module._append_cleanup
    append_calls = 0

    def bounded_append(head, later):
        nonlocal append_calls
        append_calls += 1
        if append_calls > 257:
            raise AssertionError("exact cleanup budget added a processing fallback")
        return original_append(head, later)

    monkeypatch.setattr(module, "_append_cleanup", bounded_append)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error.code == "observation_failed"
    _assert_sanitized_chain(module, error)
    chain = _assert_linear_cause_chain(error, expected_length=256)
    assert all(node.code == "observation_failed" for node in chain)
    assert append_calls == 257
    assert world._close_counts["baseline"] == 1
    assert world.backend is not None
    assert world.backend.handles == []


def test_reader_preserves_every_backend_cleanup_failure_as_sanitized_nodes(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    backend_type = _FakeHeldHandleBackend
    original_exit = backend_type.__exit__
    first = WindowsHeldHandleError("observation_failed")
    second = WindowsHeldHandleError("observation_failed")
    first.__context__ = second

    def chained_exit(self, exc_type, exc, traceback):
        result = original_exit(self, exc_type, exc, traceback)
        assert result is False
        raise first

    monkeypatch.setattr(backend_type, "__exit__", chained_exit)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error.code == "observation_failed"
    _assert_sanitized_chain(module, error)
    assert error.__context__ is None
    assert type(error.__cause__) is module.ExternalPinReaderError
    assert error.__cause__.code == "observation_failed"
    assert error.__cause__.__cause__ is None
    assert error.__cause__.__context__ is None
    assert len(_walk_exception_chain(error)) == 2
    assert world._close_counts["baseline"] == 1
    assert world.backend is not None
    assert world.backend.handles == []


def test_reader_preserves_nested_backend_cleanup_on_operation_error(monkeypatch) -> None:
    world = _ReaderWorld()
    primary = WindowsHeldHandleError("redirected_boundary")
    cleanup = WindowsHeldHandleError("observation_failed")
    primary.__context__ = cleanup
    world.backend_exception = ("read_security_descriptor", "anchor", primary)
    module = _install_reader_world(monkeypatch, world)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error.code == "redirected_boundary"
    assert error.__context__ is None
    assert type(error.__cause__) is module.ExternalPinReaderError
    assert error.__cause__.code == "observation_failed"
    assert error.__cause__.__cause__ is None
    assert error.__cause__.__context__ is None
    _assert_sanitized_chain(module, error)
    assert len(_walk_exception_chain(error)) == 2
    assert world.backend is not None
    assert world.backend.handles == []
    assert world._close_counts["baseline"] == 1


def test_immediate_cleanup_is_not_overwritten_by_later_backend_cleanup(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    primary = module.ExternalPinReaderError("redirected_boundary")
    original_operation = module.ExternalPinReaderError("unsupported_platform")
    primary.__cause__ = original_operation
    primary.__suppress_context__ = True
    immediate_failure = OSError(_SECRET_MARKER)
    world.known_folder_call_exception = primary
    world.known_folder_free_exception = immediate_failure
    world.backend_close_failure = True
    immediate_cleanup_nodes: list[BaseException] = []
    backend_cleanup_nodes: list[BaseException] = []
    original_sanitize = module._sanitize_error

    def capture_cleanup(error: BaseException):
        sanitized = original_sanitize(error)
        if error is immediate_failure:
            immediate_cleanup_nodes.append(sanitized)
        if isinstance(error, WindowsHeldHandleError):
            backend_cleanup_nodes.append(sanitized)
        return sanitized

    monkeypatch.setattr(module, "_sanitize_error", capture_cleanup)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    assert len(immediate_cleanup_nodes) == 1
    assert len(backend_cleanup_nodes) == 1
    assert primary.__cause__ is original_operation
    assert primary.__context__ is immediate_cleanup_nodes[0]
    assert immediate_cleanup_nodes[0].__cause__ is backend_cleanup_nodes[0]
    assert backend_cleanup_nodes[0].__cause__ is None
    assert backend_cleanup_nodes[0].__context__ is None
    _assert_sanitized_chain(module, primary)


def test_control_primary_preserves_occupied_graph_and_inserts_sanitized_cleanup(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    primary = KeyboardInterrupt()
    original_traceback = _prime_control_primary(primary)
    original_cause = OSError("original cause")
    original_context = LookupError("original context")
    primary.__cause__ = original_cause
    primary.__context__ = original_context
    primary.__suppress_context__ = True
    world.known_folder_call_exception = primary
    world.known_folder_free_exception = OSError(_SECRET_MARKER)

    with pytest.raises(KeyboardInterrupt) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    assert primary.__cause__ is original_cause
    cleanup = primary.__context__
    assert type(cleanup) is module.ExternalPinReaderError
    assert cleanup.code == "observation_failed"
    assert cleanup.__cause__ is None
    assert cleanup.__context__ is original_context
    assert _SECRET_MARKER not in repr(cleanup)
    assert len(world.freed_known_folder) == 1
    assert world._close_counts["baseline"] == 1


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
@pytest.mark.parametrize("route", ["security_failure", "cleanup"])
def test_control_flow_rethrow_preserves_false_suppression_and_translated_context(
    route: str,
    exception_type: type[BaseException],
) -> None:
    module = _load_module()
    primary = exception_type()
    original_traceback = _prime_control_primary(primary)
    original_cause = LookupError("preserved-cause")
    shared_context = module.WindowsSecurityMechanicsError("observation_failed")
    primary.__cause__ = original_cause
    primary.__context__ = shared_context
    primary.__suppress_context__ = False

    def invoke_inside_active_handler() -> None:
        try:
            raise RuntimeError("active-handler")
        except RuntimeError:
            if route == "security_failure":
                module._raise_security_failure(primary, phase="recheck")
            else:
                module._raise_after_cleanup(primary, None)

    with pytest.raises(exception_type) as exc_info:
        invoke_inside_active_handler()

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    assert primary.__cause__ is original_cause
    assert type(primary.__context__) is module.ExternalPinReaderError
    assert primary.__context__.code == "observation_failed"
    assert primary.__context__.__cause__ is None
    assert primary.__context__.__context__ is None
    assert primary.__suppress_context__ is False


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
@pytest.mark.parametrize("route", ["security_failure", "cleanup"])
def test_control_flow_shared_cause_translation_preserves_false_suppression(
    route: str,
    exception_type: type[BaseException],
) -> None:
    module = _load_module()
    primary = exception_type()
    original_traceback = _prime_control_primary(primary)
    shared_cause = module.WindowsSecurityMechanicsError("observation_failed")
    original_context = LookupError("preserved-context")
    primary.__cause__ = shared_cause
    primary.__context__ = original_context
    primary.__suppress_context__ = False

    with pytest.raises(exception_type) as exc_info:
        if route == "security_failure":
            module._raise_security_failure(primary, phase="recheck")
        else:
            module._raise_after_cleanup(primary, None)

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    assert type(primary.__cause__) is module.ExternalPinReaderError
    assert primary.__cause__.code == "observation_failed"
    assert primary.__cause__.__cause__ is None
    assert primary.__cause__.__context__ is None
    assert primary.__context__ is original_context
    assert primary.__suppress_context__ is False


@pytest.mark.parametrize("route", ["security_failure", "cleanup"])
def test_control_flow_shared_cause_context_alias_survives_translation(route: str) -> None:
    module = _load_module()
    primary = KeyboardInterrupt()
    shared_link = module.WindowsSecurityMechanicsError("observation_failed")
    primary.__cause__ = shared_link
    primary.__context__ = shared_link
    primary.__suppress_context__ = False

    with pytest.raises(KeyboardInterrupt) as exc_info:
        if route == "security_failure":
            module._raise_security_failure(primary, phase="recheck")
        else:
            module._raise_after_cleanup(primary, None)

    assert exc_info.value is primary
    assert type(primary.__cause__) is module.ExternalPinReaderError
    assert primary.__cause__ is primary.__context__
    assert primary.__suppress_context__ is False


@pytest.mark.parametrize("route", ["security_failure", "cleanup"])
def test_control_flow_translation_failure_keeps_primary_and_uses_fallback(
    monkeypatch,
    route: str,
) -> None:
    module = _load_module()
    primary = KeyboardInterrupt()
    original_traceback = _prime_control_primary(primary)
    primary.__cause__ = module.WindowsSecurityMechanicsError("observation_failed")
    original_context = LookupError("preserved-context")
    primary.__context__ = original_context
    primary.__suppress_context__ = False
    fallback = module.ExternalPinReaderError("observation_failed")

    def fail_translation(*_args, **_kwargs):
        raise MemoryError(_SECRET_MARKER)

    monkeypatch.setattr(module, "_translate_security_error_graph", fail_translation)

    with pytest.raises(KeyboardInterrupt) as exc_info:
        if route == "security_failure":
            module._raise_security_failure(primary, phase="recheck")
        else:
            module._raise_after_cleanup(primary, None, fallback=fallback)

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    assert type(primary.__cause__) is module.ExternalPinReaderError
    assert primary.__cause__.code == "observation_failed"
    if route == "cleanup":
        assert primary.__cause__ is fallback
    assert primary.__context__ is original_context
    assert primary.__suppress_context__ is False
    assert _SECRET_MARKER not in repr(primary.__cause__)


def test_exception_cleanup_rethrow_preserves_context_only_false_suppression() -> None:
    module = _load_module()
    primary = module.ExternalPinReaderError("observation_failed")
    context = module.ExternalPinReaderError("unsupported_security")
    primary.__context__ = context
    primary.__suppress_context__ = False

    def invoke_inside_active_handler() -> None:
        try:
            raise RuntimeError("active-handler")
        except RuntimeError:
            module._raise_after_cleanup(primary, None)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        invoke_inside_active_handler()

    assert exc_info.value is primary
    assert primary.__cause__ is None
    assert primary.__context__ is context
    assert primary.__suppress_context__ is False


def test_cleanup_only_rethrow_preserves_context_inside_active_handler() -> None:
    module = _load_module()
    cleanup = module.ExternalPinReaderError("observation_failed")
    context = module.ExternalPinReaderError("unsupported_security")
    cleanup.__context__ = context
    cleanup.__suppress_context__ = False

    def invoke_inside_active_handler() -> None:
        try:
            raise RuntimeError("active-handler")
        except RuntimeError:
            module._raise_after_cleanup(None, cleanup)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        invoke_inside_active_handler()

    assert exc_info.value is cleanup
    assert cleanup.__cause__ is None
    assert cleanup.__context__ is context
    assert cleanup.__suppress_context__ is False


def test_control_primary_sanitizes_preexisting_backend_cleanup_link(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    primary = KeyboardInterrupt()
    original_traceback = _prime_control_primary(primary)
    backend_cleanup = WindowsHeldHandleError("observation_failed")
    backend_cleanup.__cause__ = OSError(_SECRET_MARKER)
    backend_cleanup.__suppress_context__ = True
    primary.__cause__ = backend_cleanup
    primary.__suppress_context__ = True
    world.backend_exception = ("read_security_descriptor", "anchor", primary)
    module = _install_reader_world(monkeypatch, world)

    with pytest.raises(KeyboardInterrupt) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    cleanup = primary.__cause__
    assert type(cleanup) is module.ExternalPinReaderError
    assert cleanup.code == "observation_failed"
    assert cleanup.__cause__ is None
    assert cleanup.__context__ is None
    _assert_sanitized_chain(module, cleanup)
    assert world.backend is not None
    assert world.backend.handles == []
    assert world._close_counts["baseline"] == 1


def test_shared_session_internal_failure_is_sanitized_without_route_acquisition(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.security_open_exception = MemoryError(_SECRET_MARKER)
    module = _install_reader_world(monkeypatch, world)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    assert exc_info.value.code == "observation_failed"
    _assert_sanitized_chain(module, exc_info.value)
    backend_enters = [event for event in world.events if event[0] == "backend.enter"]
    backend_exits = [event for event in world.events if event[0] == "backend.exit"]
    assert len(backend_enters) == len(backend_exits)
    assert len(backend_enters) <= 1
    if backend_enters:
        assert backend_exits == [("backend.exit", False)]
    assert not any(event[0].startswith("backend.open") for event in world.events)
    assert not any(event[0] == "native.close" for event in world.events)
    assert world.backend is not None
    assert world.backend.handles == []
    assert _SECRET_MARKER not in repr(exc_info.value)


@pytest.mark.parametrize(
    ("mode", "close_kind", "trigger_at"),
    [
        ("initial_thread", "thread", 1),
        ("comparison_thread", "thread", 2),
        ("baseline_process", "baseline", 1),
        ("transient_process", "transient", 2),
        ("duplicate", "duplicate", 1),
    ],
)
def test_native_output_written_before_control_interrupt_is_closed_once(
    monkeypatch,
    mode: str,
    close_kind: str,
    trigger_at: int,
) -> None:
    world = _ReaderWorld()
    if mode == "initial_thread":
        world.thread_case = "success_nonnull"
    elif mode == "comparison_thread":
        world.comparison_thread_at = 2
    module = _install_reader_world(monkeypatch, world)
    if mode in {"initial_thread", "comparison_thread"}:
        call = world.native.advapi32.OpenThreadToken
    elif mode in {"baseline_process", "transient_process"}:
        call = world.native.advapi32.OpenProcessToken
    else:
        call = world.native.advapi32.DuplicateTokenEx
    original = call.implementation
    primary = KeyboardInterrupt()
    original_traceback = _prime_control_primary(primary)
    call_count = 0

    def interrupt_after_write(*args):
        nonlocal call_count
        call_count += 1
        result = original(*args)
        if call_count == trigger_at:
            raise primary
        return result

    call.implementation = interrupt_after_write

    with pytest.raises(KeyboardInterrupt) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    _assert_original_traceback_tail_is_preserved(primary, original_traceback)
    assert world._close_counts.get(close_kind, 0) == 1
    assert [event for event in world.events if event[0] == "backend.exit"] == [
        ("backend.exit", False)
    ]


def test_backend_ledger_closes_handle_when_reader_tracking_allocation_fails(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    original = module._HeldObject

    def fail_reader_tracking(*args, **kwargs):
        role = kwargs.get("role", args[0] if args else None)
        if role == "goodq":
            raise MemoryError(_SECRET_MARKER)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "_HeldObject", fail_reader_tracking)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    assert exc_info.value.code == "observation_failed"
    _assert_sanitized_chain(module, exc_info.value)
    assert world.backend is not None
    assert world.backend.closed == ["goodq", "anchor", "root"]
    assert world.backend.handles == []
    assert world.backend.read_count == 0
    assert [event for event in world.events if event[0] == "backend.exit"] == [
        ("backend.exit", False)
    ]
    assert world._close_counts == {"transient": 7, "baseline": 1}


@pytest.mark.parametrize(
    ("mode", "expected_code"),
    [
        ("initial_thread", "untrusted_reader"),
        ("comparison_thread", "observation_raced"),
    ],
)
def test_shared_thread_token_failure_uses_exact_consumer_phase_classification(
    monkeypatch,
    mode: str,
    expected_code: str,
) -> None:
    world = _ReaderWorld()
    if mode == "initial_thread":
        world.thread_case = "success_nonnull"
    else:
        world.comparison_thread_at = 2
    module = _install_reader_world(monkeypatch, world)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    assert exc_info.value.code == expected_code
    _assert_sanitized_chain(module, exc_info.value)


@pytest.mark.parametrize(
    "code",
    [
        "unsupported_platform",
        "unsupported_filesystem",
        "redirected_boundary",
        "unexpected_entry_type",
        "duplicate_identity",
        "sharing_conflict",
        "observation_raced",
        "observation_failed",
    ],
)
def test_backend_error_codes_map_exactly_to_sanitized_reader_codes(
    monkeypatch, code: str
) -> None:
    world = _ReaderWorld()
    world.backend_failure = ("snapshot", "anchor")
    world.backend_failure_code = code

    module, error = _expect_reader_error(monkeypatch, world, code)

    _assert_sanitized_chain(module, error)
    assert world.backend is not None
    assert world.backend.read_count == 0


@pytest.mark.parametrize(
    ("method", "role"),
    [
        ("open_root", "root"),
        ("volume_filesystem", "root"),
        ("enumerate_directory", "root"),
        ("open_by_id", "anchor"),
        ("snapshot", "anchor"),
        ("read_security_descriptor", "anchor"),
        ("read_file_bounded", "pin"),
    ],
)
def test_each_public_backend_operation_failure_maps_and_sanitizes(
    monkeypatch, method: str, role: str
) -> None:
    world = _ReaderWorld()
    world.backend_failure = (method, role)

    module, error = _expect_reader_error(monkeypatch, world, "observation_failed")

    _assert_sanitized_chain(module, error)


@pytest.mark.parametrize(
    "code",
    [
        "unsupported_platform",
        "unsupported_filesystem",
        "redirected_boundary",
        "unexpected_entry_type",
        "duplicate_identity",
        "sharing_conflict",
        "observation_raced",
        "observation_failed",
    ],
)
def test_backend_construction_error_mapping_precedes_token_and_storage_access(
    monkeypatch, code: str
) -> None:
    world = _ReaderWorld()
    world.backend_construction_error = code

    module, error = _expect_reader_error(monkeypatch, world, code)

    _assert_sanitized_chain(module, error)
    assert world.events[:2] == [
        ("native.bind",),
        ("backend.construct", "security_read"),
    ]
    assert not any(event[0] == "privilege.lookup" for event in world.events)
    assert not any(event[0].startswith("token.") for event in world.events)
    assert not any(event[0] == "backend.open_root" for event in world.events)


@pytest.mark.parametrize(
    ("primary_setup", "close_kind", "expected_code"),
    [
        pytest.param("malformed_pin", "baseline", "malformed_pin", id="payload-over-baseline-close"),
        pytest.param(
            "access_grant",
            "duplicate",
            "security_policy_mismatch",
            id="policy-over-duplicate-close",
        ),
        pytest.param(
            "thread_race",
            "thread",
            "observation_raced",
            id="race-over-thread-close",
        ),
    ],
)
def test_primary_result_precedes_native_cleanup_failures(
    monkeypatch, primary_setup: str, close_kind: str, expected_code: str
) -> None:
    world = _ReaderWorld()
    if primary_setup == "malformed_pin":
        world.payload = b"not-a-pin"
    elif primary_setup == "access_grant":
        world.access_case = "grant"
    elif primary_setup == "thread_race":
        world.comparison_thread_at = 2
    else:
        raise AssertionError(primary_setup)
    world.native_close_failure_kind = close_kind
    world.native_close_failure_at = 1

    module, error = _expect_reader_error(monkeypatch, world, expected_code)

    _assert_sanitized_chain(module, error)
    assert len(_walk_exception_chain(error)) >= 2
    assert world._close_counts[close_kind] == 1


@pytest.mark.parametrize("kind", ["transient", "duplicate", "baseline"])
def test_cleanup_only_native_handle_failure_prevents_evidence(
    monkeypatch, kind: str
) -> None:
    world = _ReaderWorld()
    world.native_close_failure_kind = kind
    world.native_close_failure_at = 1

    module, error = _expect_reader_error(monkeypatch, world, "observation_failed")

    _assert_sanitized_chain(module, error)
    assert world._close_counts[kind] == 1


def test_primary_error_survives_cleanup_failure_and_all_cleanup_is_attempted(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.payload = b"not-a-pin"
    world.backend_close_failure = True

    module, error = _expect_reader_error(monkeypatch, world, "malformed_pin")

    _assert_sanitized_chain(module, error)
    assert len(_walk_exception_chain(error)) >= 2
    assert world.backend is not None
    assert world.backend.closed == [
        "pin",
        "clean_memory",
        "authority",
        "goodq",
        "anchor",
        "root",
    ]


def test_cleanup_only_failure_prevents_partial_evidence(monkeypatch) -> None:
    world = _ReaderWorld()
    world.native_close_failure_kind = "baseline"

    module, error = _expect_reader_error(monkeypatch, world, "observation_failed")

    _assert_sanitized_chain(module, error)
    assert len(
        [event for event in world.events if event[:2] == ("native.close", "baseline")]
    ) == 1


def test_known_folder_free_exception_is_a_sanitized_cleanup_only_failure(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    world.known_folder_free_exception = OSError(_SECRET_MARKER)

    module, error = _expect_reader_error(monkeypatch, world, "observation_failed")

    _assert_sanitized_chain(module, error)
    assert len(world.freed_known_folder) == 1
    assert world.backend is not None
    assert world.backend.read_count == 0


def test_primary_with_existing_sanitized_cause_precedes_known_folder_free_failure(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    primary = module.ExternalPinReaderError("redirected_boundary")
    original_operation = module.ExternalPinReaderError("unsupported_platform")
    primary.__cause__ = original_operation
    primary.__suppress_context__ = True
    world.known_folder_call_exception = primary
    world.known_folder_free_exception = OSError(_SECRET_MARKER)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    error = exc_info.value
    assert error is primary
    assert error.code == "redirected_boundary"
    assert str(error) == _ERRORS["redirected_boundary"]
    assert error.args == (_ERRORS["redirected_boundary"],)
    assert error.__cause__ is original_operation
    assert original_operation.code == "unsupported_platform"
    assert str(original_operation) == _ERRORS["unsupported_platform"]
    assert original_operation.args == (_ERRORS["unsupported_platform"],)
    assert original_operation.__cause__ is None
    assert original_operation.__context__ is None
    cleanup = error.__context__
    assert type(cleanup) is module.ExternalPinReaderError
    assert cleanup.code == "observation_failed"
    assert str(cleanup) == _ERRORS["observation_failed"]
    assert cleanup.args == (_ERRORS["observation_failed"],)
    assert cleanup.__cause__ is None
    assert cleanup.__context__ is None
    assert error.__cause__ is not cleanup
    assert error.__context__ is not original_operation
    _assert_sanitized_chain(module, error)
    chain = _walk_exception_chain(error)
    assert len(chain) == 3
    assert {id(node) for node in chain} == {
        id(error),
        id(original_operation),
        id(cleanup),
    }


def test_known_folder_cleanup_sanitization_failure_preserves_primary(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)
    primary = module.ExternalPinReaderError("redirected_boundary")
    original_operation = module.ExternalPinReaderError("unsupported_platform")
    primary.__cause__ = original_operation
    primary.__suppress_context__ = True
    cleanup_error = OSError(_SECRET_MARKER)
    world.known_folder_call_exception = primary
    world.known_folder_free_exception = cleanup_error
    original_sanitize = module._sanitize_error

    def fail_cleanup_sanitization(error: BaseException):
        if error is cleanup_error:
            raise MemoryError(_SECRET_MARKER)
        return original_sanitize(error)

    monkeypatch.setattr(module, "_sanitize_error", fail_cleanup_sanitization)

    with pytest.raises(module.ExternalPinReaderError) as exc_info:
        module.read_external_pin()

    assert exc_info.value is primary
    assert primary.__cause__ is original_operation
    cleanup = primary.__context__
    assert type(cleanup) is module.ExternalPinReaderError
    assert cleanup.code == "observation_failed"
    assert cleanup.__context__ is None
    processing_failure = cleanup.__cause__
    assert type(processing_failure) is module.ExternalPinReaderError
    assert processing_failure.code == "observation_failed"
    assert processing_failure.__cause__ is None
    assert processing_failure.__context__ is None
    _assert_sanitized_chain(module, primary)
    assert len(_walk_exception_chain(primary)) == 4
    assert len(world.freed_known_folder) == 1
    assert world._close_counts["baseline"] == 1
    assert len(world.freed_known_folder) == 1
    assert world.backend is not None
    assert world.backend.read_count == 0


_APPROVED_DIRECT_IMPORTS = {
    "ctypes",
    "hashlib",
    "json",
    "os",
    "struct",
    "unicodedata",
}
_APPROVED_FROM_IMPORTS = {
    "__future__": {"annotations"},
    "dataclasses": {"dataclass", "field"},
    "typing": {"Any"},
    "steps.common.clean_memory_windows_reader_identity": {
        "CleanMemoryWindowsReaderIdentityError",
        "clean_memory_windows_reader_identity_sha256",
        "validate_clean_memory_windows_reader_identity",
    },
    "steps.common.windows_held_handle": {
        "WindowsDirectoryEntry",
        "WindowsHeldHandleBackend",
        "WindowsHeldHandleError",
        "WindowsObjectSnapshot",
    },
    "steps.common.windows_security_mechanics": {
        "WINDOWS_DESCRIPTOR_PROFILE_DACL_ONLY",
        "WINDOWS_TOKEN_PROFILE_BASE",
        "WindowsAce",
        "WindowsPinnedSecurityDescriptor",
        "WindowsSecurityDescriptor",
        "WindowsSecurityMechanics",
        "WindowsSecurityMechanicsError",
        "WindowsSecuritySession",
        "WindowsSid",
        "WindowsTokenSnapshot",
        "bind_windows_security",
        "verify_windows_security_abi",
    },
}


def _assert_approved_source_imports(source: str) -> None:
    tree = ast.parse(source)
    held_imports: list[ast.ImportFrom] = []
    identity_imports: list[ast.ImportFrom] = []
    security_imports: list[ast.ImportFrom] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name in _APPROVED_DIRECT_IMPORTS
                assert alias.asname is None
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module in _APPROVED_FROM_IMPORTS
            approved_names = _APPROVED_FROM_IMPORTS[node.module]
            assert node.names
            assert all(
                alias.name in approved_names
                and alias.name != "*"
                and alias.asname is None
                for alias in node.names
            )
            if node.module == "steps.common.windows_held_handle":
                held_imports.append(node)
            if node.module == "steps.common.clean_memory_windows_reader_identity":
                identity_imports.append(node)
            if node.module == "steps.common.windows_security_mechanics":
                security_imports.append(node)

    assert len(held_imports) == 1
    assert len(identity_imports) == 1
    assert len(security_imports) == 1
    imported_backend_names = {alias.name for alias in held_imports[0].names}
    assert {
        "WindowsHeldHandleBackend",
        "WindowsHeldHandleError",
    } <= imported_backend_names
    imported_security_names = {
        alias.name for alias in security_imports[0].names
    }
    assert imported_security_names == _APPROVED_FROM_IMPORTS[
        "steps.common.windows_security_mechanics"
    ]
    imported_identity_names = {
        alias.name for alias in identity_imports[0].names
    }
    assert imported_identity_names == _APPROVED_FROM_IMPORTS[
        "steps.common.clean_memory_windows_reader_identity"
    ]


_FORBIDDEN_PRIVATE_SECURITY_DEFINITIONS = {
    "_LUID",
    "_LUID_AND_ATTRIBUTES",
    "_SID_AND_ATTRIBUTES",
    "_TOKEN_USER",
    "_TOKEN_GROUPS",
    "_TOKEN_PRIVILEGES",
    "_TOKEN_MANDATORY_LABEL",
    "_TOKEN_ELEVATION",
    "_TOKEN_STATISTICS",
    "_GENERIC_MAPPING",
    "_PRIVILEGE_SET",
    "_Sid",
    "_SidRecord",
    "_Privilege",
    "_PrimaryStatistics",
    "_TokenSnapshot",
    "_Ace",
    "_SecurityDescriptor",
    "_OwnedNativeHandle",
    "_parse_sid",
    "_sid_from_pointer",
    "_reject_overlapping_intervals",
    "_query_variable_token",
    "_query_statistics",
    "_query_fixed_value",
    "_parse_token_user",
    "_parse_sid_records",
    "_parse_privileges",
    "_parse_integrity",
    "_parse_security_descriptor",
    "_file_generic_mapping",
    "_mapped_mask",
    "_token_snapshot",
    "_resolve_change_notify_luid",
    "_open_baseline_token",
    "_duplicate_access_token",
    "_validate_privilege_output",
    "_check_denied_right",
    "_close_native_handle",
}

_FORBIDDEN_PRIVATE_READER_IDENTITY_AUTHORITIES = {
    "_intrinsically_validate_token",
    "_reader_identity_projection",
}


def _defined_or_assigned_authority_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in ast.walk(tree):
        targets: tuple[ast.AST, ...] = ()
        if isinstance(node, ast.Assign):
            targets = tuple(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
        elif isinstance(node, ast.NamedExpr):
            targets = (node.target,)
        for target in targets:
            names.update(
                child.id
                for child in ast.walk(target)
                if isinstance(child, ast.Name)
            )
    return names


def test_source_has_no_private_windows_security_or_reader_identity_authority() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    defined = _defined_or_assigned_authority_names(source)
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert defined.isdisjoint(_FORBIDDEN_PRIVATE_SECURITY_DEFINITIONS)
    assert defined.isdisjoint(_FORBIDDEN_PRIVATE_READER_IDENTITY_AUTHORITIES)
    assert "goodq.clean-memory-windows-reader-identity.v1" not in source
    assert called_attributes.isdisjoint(
        {
            "OpenThreadToken",
            "OpenProcessToken",
            "GetTokenInformation",
            "LookupPrivilegeValueW",
            "DuplicateTokenEx",
            "MapGenericMask",
            "AccessCheck",
            "GetSecurityInfo",
            "IsValidSecurityDescriptor",
            "GetSecurityDescriptorControl",
            "GetSecurityDescriptorLength",
        }
    )
    for mutant in (
        "_intrinsically_validate_token = validate_clean_memory_windows_reader_identity",
        "_reader_identity_projection: object = clean_memory_windows_reader_identity_sha256",
    ):
        assert not _defined_or_assigned_authority_names(mutant).isdisjoint(
            _FORBIDDEN_PRIVATE_READER_IDENTITY_AUTHORITIES
        )


def test_source_has_only_the_strict_approved_import_allowlist() -> None:
    _assert_approved_source_imports(MODULE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "forbidden_import",
    [
        "import steps.common.windows_held_handle",
        "import steps.common.windows_held_handle as held",
        "import ctypes.util",
        "import subprocess",
        "from cli import clean_memory_external_pin",
        "from steps.common.windows_held_handle import _open_by_path",
    ],
)
def test_strict_import_allowlist_rejects_direct_project_and_capability_escapes(
    forbidden_import: str,
) -> None:
    approved_boundary = (
        "from steps.common.windows_held_handle "
        "import WindowsHeldHandleBackend, WindowsHeldHandleError\n"
    )
    with pytest.raises(AssertionError):
        _assert_approved_source_imports(approved_boundary + forbidden_import + "\n")


def test_source_has_no_descendant_path_or_forbidden_authority_calls() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called_names.isdisjoint({"open", "exec", "eval", "compile"})
    assert called_attributes.isdisjoint(
        {
            "CreateFileW",
            "OpenFileById",
            "hash_file",
            "getenv",
            "unlink",
            "remove",
            "rmdir",
            "write_text",
            "write_bytes",
        }
    )


def test_source_has_no_dynamic_import_os_open_or_environment_mapping_escape() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    os_aliases = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "os"
    }
    importlib_aliases = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "importlib"
    }
    builtins_aliases = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "builtins"
    }
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported_roots.isdisjoint({"pkgutil", "runpy"})
    assert os_aliases, "os.name platform gating must remain explicit and inspectable"
    forbidden_os_attributes = {
        "environ",
        "environb",
        "getenv",
        "get_exec_path",
        "listdir",
        "open",
        "putenv",
        "read",
        "scandir",
        "stat",
        "unsetenv",
        "walk",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is not None and node.module.startswith("importlib"):
                pytest.fail("dynamic import machinery is outside the reader boundary")
            if node.module in {"pkgutil", "runpy"}:
                pytest.fail("dynamic module loading is outside the reader boundary")
            if node.module == "os":
                assert all(alias.name not in forbidden_os_attributes for alias in node.names)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in os_aliases:
                assert node.attr not in forbidden_os_attributes | {
                    "__dict__",
                    "__getattribute__",
                }
            if node.value.id in importlib_aliases:
                assert node.attr not in {
                    "import_module",
                    "module_from_spec",
                    "reload",
                }
            if node.value.id in builtins_aliases:
                assert node.attr != "__import__"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {
                "__import__",
                "exec",
                "eval",
                "compile",
                "globals",
                "locals",
            }
            if node.func.id in {"getattr", "vars"} and node.args:
                owner = node.args[0]
                assert not (
                    isinstance(owner, ast.Name)
                    and owner.id in os_aliases | importlib_aliases
                )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "__import__",
                "import_module",
                "module_from_spec",
                "run_module",
                "run_path",
                "spec_from_file_location",
            }


_CLEANUP_HELPERS = {
    "_append_cleanup",
    "_attach_cleanup",
    "_next_windows_cleanup",
    "_preserve_context",
    "_raise_after_cleanup",
    "_sanitize_cleanup_chain",
    "_sanitize_windows_error_graph",
}


def _assert_cleanup_helpers_have_no_collection_snapshot_allocation(source: str) -> None:
    tree = ast.parse(source)
    helpers = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in _CLEANUP_HELPERS
    }
    assert set(helpers) == _CLEANUP_HELPERS
    forbidden_calls = {"dict", "iter", "list", "reversed", "set", "sorted", "tuple"}
    forbidden_nodes = (
        ast.Dict,
        ast.DictComp,
        ast.GeneratorExp,
        ast.List,
        ast.ListComp,
        ast.Set,
        ast.SetComp,
        ast.Tuple,
    )
    violations: list[ast.AST] = []
    for helper in helpers.values():
        for node in ast.walk(helper):
            if isinstance(node, forbidden_nodes):
                violations.append(node)
            elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
                violations.append(node)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                    violations.append(node)
                elif isinstance(node.func, ast.Attribute) and node.func.attr in {
                    "copy",
                    "deepcopy",
                }:
                    violations.append(node)
    assert violations == []


def test_cleanup_helpers_have_no_collection_snapshot_allocation_path() -> None:
    _assert_cleanup_helpers_have_no_collection_snapshot_allocation(
        MODULE_PATH.read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "snapshot",
    [
        "list(error)",
        "tuple(error)",
        "reversed(error)",
        "error.copy()",
        "error[::-1]",
        "[error]",
        "{'error': error}",
        "{error}",
        "(error,)",
        "[item for item in error]",
        "{item for item in error}",
        "(item for item in error)",
    ],
)
def test_cleanup_allocation_oracle_rejects_snapshot_mutants(snapshot: str) -> None:
    supporting_helpers = "\n".join(
        f"def {name}(*args, **kwargs):\n    return None\n"
        for name in sorted(_CLEANUP_HELPERS - {"_sanitize_cleanup_chain"})
    )
    mutant = (
        supporting_helpers
        + "\ndef _sanitize_cleanup_chain(error, **kwargs):\n"
        + f"    return {snapshot}\n"
    )
    with pytest.raises(AssertionError):
        _assert_cleanup_helpers_have_no_collection_snapshot_allocation(mutant)


_FORBIDDEN_DIRECT_CTYPES_CAPABILITIES = {
    "CDLL",
    "LibraryLoader",
    "OleDLL",
    "PyDLL",
    "cdll",
    "oledll",
    "pydll",
    "pythonapi",
    "windll",
}


def _direct_ctypes_capability_violations(source: str) -> list[ast.AST]:
    tree = ast.parse(source)
    violations: list[ast.AST] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "ctypes"
            and node.attr in _FORBIDDEN_DIRECT_CTYPES_CAPABILITIES
        ):
            violations.append(node)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "ctypes"
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in _FORBIDDEN_DIRECT_CTYPES_CAPABILITIES
        ):
            violations.append(node)
    return violations


def test_source_has_no_alternate_direct_ctypes_loader_capability() -> None:
    assert not _direct_ctypes_capability_violations(
        MODULE_PATH.read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "escape",
    [
        "ctypes.CDLL('x')",
        "ctypes.OleDLL('x')",
        "ctypes.PyDLL('x')",
        "ctypes.cdll.LoadLibrary('x')",
        "ctypes.windll.kernel32",
        "ctypes.pythonapi",
        "getattr(ctypes, 'CDLL')('x')",
    ],
)
def test_ctypes_capability_checker_rejects_each_alternate_loader_escape(
    escape: str,
) -> None:
    assert _direct_ctypes_capability_violations("import ctypes\n" + escape + "\n")


def _opaque_backend_token_attribute_violations(source: str) -> list[ast.Attribute]:
    tree = ast.parse(source)
    token_names: set[str] = set()
    for node in ast.walk(tree):
        value: ast.AST | None = None
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr in {"open_root", "open_by_id"}
        ):
            token_names.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in token_names
    ]


def test_source_treats_backend_handle_tokens_as_opaque() -> None:
    assert not _opaque_backend_token_attribute_violations(
        MODULE_PATH.read_text(encoding="utf-8")
    )


def test_opaque_backend_token_checker_rejects_attribute_introspection() -> None:
    mutant = """
root = backend.open_root("C:\\\\")
anchor = backend.open_by_id(root, entry, directory=True)
leak = root.handle
kind = anchor.role
"""

    violations = _opaque_backend_token_attribute_violations(mutant)

    assert {node.attr for node in violations} == {"handle", "role"}


def test_runtime_uses_only_injected_native_and_public_backend_capabilities(
    monkeypatch,
) -> None:
    world = _ReaderWorld()
    module = _install_reader_world(monkeypatch, world)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden capability used")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    for name in (
        "open",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "unlink",
    ):
        monkeypatch.setattr(Path, name, forbidden)

    evidence = module.read_external_pin()

    assert evidence.projection == _expected_world_evidence(world)
    root_opens = [event for event in world.events if event[0] == "backend.open_root"]
    assert root_opens == [("backend.open_root", "C:\\")]
    assert len([event for event in world.events if event[0] == "backend.open_by_id"]) == 5
