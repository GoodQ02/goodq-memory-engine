from __future__ import annotations

import ast
import ctypes
import hashlib
import importlib
import inspect
import os
from pathlib import Path
import sys

import pytest


class _NativeCall:
    def __init__(self, implementation):
        self.implementation = implementation
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.implementation(*args)


class _Kernel32:
    def __init__(self) -> None:
        self.closed: list[int] = []
        self.GetDriveTypeW = _NativeCall(lambda _root: 3)
        self.CreateFileW = _NativeCall(lambda *_args: 41)
        self.GetVolumeInformationByHandleW = _NativeCall(lambda *_args: 1)
        self.GetFileInformationByHandleEx = _NativeCall(lambda *_args: 1)
        self.GetFileInformationByHandle = _NativeCall(lambda *_args: 1)
        self.OpenFileById = _NativeCall(lambda *_args: 42)
        self.SetFilePointerEx = _NativeCall(lambda *_args: 1)
        self.ReadFile = _NativeCall(lambda *_args: 1)
        self.LocalFree = _NativeCall(lambda *_args: None)
        self.CloseHandle = _NativeCall(self._close)

    def _close(self, handle) -> int:
        raw = handle if isinstance(handle, int) else handle.value
        self.closed.append(raw)
        return 1


class _IntSubclass(int):
    pass


class _Advapi32:
    def __init__(self) -> None:
        self.GetSecurityInfo = _NativeCall(lambda *_args: 0)
        self.IsValidSecurityDescriptor = _NativeCall(lambda *_args: 1)
        self.GetSecurityDescriptorControl = _NativeCall(lambda *_args: 1)
        self.GetSecurityDescriptorLength = _NativeCall(lambda *_args: 20)


class _SecurityScript:
    def __init__(self, payload: bytes = bytes(range(20))) -> None:
        self.payload = payload
        self.buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
        self.security_result = 0
        self.security_last_error: int | None = None
        self.write_descriptor_on_success = True
        self.write_descriptor_on_error = False
        self.valid = True
        self.valid_last_error: int | None = None
        self.control_success = True
        self.control_error = 5
        self.control = 0x8000
        self.revision = 1
        self.length = len(payload)
        self.local_free_result: int | None = None
        self.local_free_error = 6
        self.poison_on_free = False
        self.security_calls: list[tuple[object, ...]] = []
        self.valid_calls = 0
        self.valid_pointers: list[int] = []
        self.control_calls = 0
        self.control_pointers: list[int] = []
        self.length_calls = 0
        self.length_pointers: list[int] = []
        self.freed: list[int] = []

    @property
    def address(self) -> int:
        return ctypes.addressof(self.buffer)

    def bind(self, kernel32: _Kernel32, advapi32: _Advapi32) -> None:
        advapi32.GetSecurityInfo.implementation = self._get_security_info
        advapi32.IsValidSecurityDescriptor.implementation = self._is_valid
        advapi32.GetSecurityDescriptorControl.implementation = self._get_control
        advapi32.GetSecurityDescriptorLength.implementation = self._get_length
        kernel32.LocalFree.implementation = self._local_free

    def _get_security_info(self, *args) -> int:
        self.security_calls.append(args)
        if self.security_last_error is not None:
            ctypes.set_last_error(self.security_last_error)
        should_write = (
            self.security_result == 0 and self.write_descriptor_on_success
        ) or (
            self.security_result != 0 and self.write_descriptor_on_error
        )
        if should_write:
            ctypes.cast(args[-1], ctypes.POINTER(ctypes.c_void_p))[0] = self.address
        return self.security_result

    def _get_control(self, _descriptor, control, revision) -> int:
        self.control_calls += 1
        self.control_pointers.append(self._pointer_value(_descriptor))
        if not self.control_success:
            ctypes.set_last_error(self.control_error)
            return 0
        ctypes.cast(control, ctypes.POINTER(ctypes.c_uint16))[0] = self.control
        ctypes.cast(revision, ctypes.POINTER(ctypes.c_uint32))[0] = self.revision
        return 1

    def _is_valid(self, _descriptor) -> int:
        self.valid_calls += 1
        self.valid_pointers.append(self._pointer_value(_descriptor))
        if self.valid_last_error is not None:
            ctypes.set_last_error(self.valid_last_error)
        return int(self.valid)

    def _get_length(self, _descriptor) -> int:
        self.length_calls += 1
        self.length_pointers.append(self._pointer_value(_descriptor))
        return self.length

    @staticmethod
    def _pointer_value(pointer) -> int:
        return pointer if isinstance(pointer, int) else pointer.value

    def _local_free(self, descriptor) -> int | None:
        raw = descriptor if isinstance(descriptor, int) else descriptor.value
        self.freed.append(raw)
        if self.poison_on_free:
            ctypes.memset(raw, 0xEE, len(self.payload))
        if self.local_free_result is not None:
            ctypes.set_last_error(self.local_free_error)
        return self.local_free_result


def _backend(
    monkeypatch: pytest.MonkeyPatch,
    kernel32: _Kernel32,
    *,
    access_profile: str = "observation",
    advapi32: _Advapi32 | None = None,
):
    module = _load_module()
    security = advapi32 or _Advapi32()

    def load_library(name: str, **_kwargs):
        assert _kwargs == {"use_last_error": True}
        if name.casefold() == "kernel32":
            return kernel32
        if name.casefold() == "advapi32":
            return security
        raise OSError("unexpected native library")

    monkeypatch.setattr(ctypes, "WinDLL", load_library)
    return module, module.WindowsHeldHandleBackend(access_profile=access_profile)


def _load_module():
    return importlib.import_module("steps.common.windows_held_handle")


def _open_test_member(module, backend):
    root = backend.open_root("X:\\")
    entry = module.WindowsDirectoryEntry(
        "member",
        0,
        "ntfs_file_index_64",
        7,
    )
    return backend.open_by_id(root, entry, directory=False)


def _assert_bounded_read_trace(
    trace: list[tuple[int, int]],
    *,
    maximum_bytes: int,
    returned_bytes: int,
    eof_observed: bool,
) -> None:
    assert trace
    remaining = maximum_bytes
    consumed = 0
    for index, (requested, count) in enumerate(trace):
        assert 1 <= requested <= remaining
        assert 0 <= count <= requested
        if count == 0:
            assert eof_observed is True
            assert index == len(trace) - 1
            continue
        consumed += count
        remaining -= count
    assert consumed == returned_bytes
    if eof_observed:
        assert trace[-1][1] == 0
        assert remaining > 0
    else:
        assert all(count > 0 for _, count in trace)
        assert remaining == 0


def test_public_api_is_exact() -> None:
    module = _load_module()

    assert module.__all__ == (
        "WindowsHeldHandleError",
        "WindowsDirectoryEntry",
        "WindowsObjectSnapshot",
        "WindowsHeldHandleBackend",
    )


def test_backend_public_method_surface_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module, backend = _backend(monkeypatch, _Kernel32())
    expected = {
        "close",
        "enumerate_directory",
        "hash_file",
        "open_by_id",
        "open_root",
        "read_file_bounded",
        "read_security_descriptor",
        "snapshot",
        "volume_filesystem",
    }

    assert {
        name for name in dir(module.WindowsHeldHandleBackend)
        if not name.startswith("_")
    } == expected
    assert {name for name in dir(backend) if not name.startswith("_")} == expected


def test_read_file_bounded_signature_is_exact() -> None:
    module = _load_module()

    assert str(
        inspect.signature(module.WindowsHeldHandleBackend.read_file_bounded)
    ) == "(self, handle: 'object', *, maximum_bytes: 'int') -> 'tuple[bytes, bool]'"


def test_security_capability_signatures_are_exact() -> None:
    module = _load_module()

    assert str(inspect.signature(module.WindowsHeldHandleBackend)) == (
        "(*, access_profile: 'str' = 'observation') -> 'None'"
    )
    assert str(
        inspect.signature(module.WindowsHeldHandleBackend.read_security_descriptor)
    ) == "(self, handle: 'object') -> 'bytes'"


@pytest.mark.parametrize(
    "access_profile",
    (None, "", "security", True, 1, [], object()),
)
def test_access_profile_rejects_every_non_exact_value_before_native_load(
    monkeypatch: pytest.MonkeyPatch,
    access_profile: object,
) -> None:
    module = _load_module()

    def forbidden_load(*_args, **_kwargs):
        raise AssertionError("native load must not occur")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden_load)
    with pytest.raises(
        ValueError,
        match="^Unsupported Windows held-handle access profile$",
    ):
        module.WindowsHeldHandleBackend(access_profile=access_profile)


def test_observation_profile_does_not_load_security_native_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    kernel32 = _Kernel32()
    delattr(kernel32, "LocalFree")
    loaded: list[str] = []

    def load_library(name: str, **_kwargs):
        assert _kwargs == {"use_last_error": True}
        loaded.append(name.casefold())
        if name.casefold() != "kernel32":
            raise AssertionError("observation profile loaded security DLL")
        return kernel32

    monkeypatch.setattr(ctypes, "WinDLL", load_library)
    module.WindowsHeldHandleBackend()

    assert loaded == ["kernel32"]


def test_security_profile_binds_exact_pointer_width_native_abi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )
    void_pointer = ctypes.c_void_p
    pointer_to_void = ctypes.POINTER(void_pointer)

    assert advapi32.GetSecurityInfo.argtypes == [
        void_pointer,
        ctypes.c_int32,
        ctypes.c_uint32,
        pointer_to_void,
        pointer_to_void,
        pointer_to_void,
        pointer_to_void,
        pointer_to_void,
    ]
    assert advapi32.GetSecurityInfo.restype is ctypes.c_uint32
    assert advapi32.IsValidSecurityDescriptor.argtypes == [void_pointer]
    assert advapi32.IsValidSecurityDescriptor.restype is ctypes.c_int32
    assert advapi32.GetSecurityDescriptorControl.argtypes == [
        void_pointer,
        ctypes.POINTER(ctypes.c_uint16),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    assert advapi32.GetSecurityDescriptorControl.restype is ctypes.c_int32
    assert advapi32.GetSecurityDescriptorLength.argtypes == [void_pointer]
    assert advapi32.GetSecurityDescriptorLength.restype is ctypes.c_uint32
    assert kernel32.LocalFree.argtypes == [void_pointer]
    assert kernel32.LocalFree.restype is void_pointer


@pytest.mark.parametrize(
    "missing_export",
    (
        "GetSecurityInfo",
        "IsValidSecurityDescriptor",
        "GetSecurityDescriptorControl",
        "GetSecurityDescriptorLength",
        "LocalFree",
    ),
)
def test_security_profile_rejects_partial_native_surface_before_any_open(
    monkeypatch: pytest.MonkeyPatch,
    missing_export: str,
) -> None:
    module = _load_module()
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    target = kernel32 if missing_export == "LocalFree" else advapi32
    delattr(target, missing_export)
    open_calls = 0

    def create_file(*_args):
        nonlocal open_calls
        open_calls += 1
        return 41

    kernel32.CreateFileW.implementation = create_file

    def load_library(name: str, **_kwargs):
        assert _kwargs == {"use_last_error": True}
        return kernel32 if name.casefold() == "kernel32" else advapi32

    monkeypatch.setattr(ctypes, "WinDLL", load_library)
    with pytest.raises(module.WindowsHeldHandleError) as exc_info:
        module.WindowsHeldHandleBackend(access_profile="security_read")

    assert exc_info.value.code == "unsupported_platform"
    assert open_calls == 0


@pytest.mark.parametrize("failure_mode", ("load", "missing_export"))
def test_backend_initialization_translates_missing_win32_capability(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    module = _load_module()
    native_error = OSError("native capability unavailable")

    def load_failure(*_args, **_kwargs):
        raise native_error

    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        load_failure if failure_mode == "load" else lambda *_args, **_kwargs: object(),
    )

    with pytest.raises(module.WindowsHeldHandleError) as exc_info:
        module.WindowsHeldHandleBackend()

    assert exc_info.value.code == "unsupported_platform"
    assert str(exc_info.value) == "Windows held-handle access is unsupported"
    assert isinstance(exc_info.value.__cause__, (AttributeError, OSError))
    if failure_mode == "load":
        assert exc_info.value.__cause__ is native_error


def test_directory_entry_is_frozen_and_projection_neutral() -> None:
    module = _load_module()
    entry = module.WindowsDirectoryEntry(
        name="member",
        attributes=0x10,
        file_id_kind="ntfs_file_index_64",
        file_id=7,
    )

    assert entry.name == "member"
    assert entry.is_directory is True
    assert entry.is_reparse is False
    assert entry.is_device is False
    assert not hasattr(entry, "membership")
    with pytest.raises(AttributeError):
        entry.name = "changed"


def test_snapshot_owns_exact_ntfs_and_refs_identity_rendering() -> None:
    module = _load_module()
    common = {
        "object_kind": "regular_file",
        "size_bytes": 4,
        "mtime_ns": 500,
        "allocation_size": 4096,
        "link_count": 1,
        "attributes": 0,
        "reparse_tag": 0,
        "last_write_ticks": 116444736000000005,
        "change_ticks": 116444736000000006,
        "streams": (("::$DATA", 4, 4096),),
    }
    ntfs = module.WindowsObjectSnapshot(
        volume_serial=0x123456789ABCDEF0,
        file_id_kind="ntfs_file_index_64",
        file_id=0xFEDCBA9876543210,
        **common,
    )
    refs = module.WindowsObjectSnapshot(
        volume_serial=0x123456789ABCDEF0,
        file_id_kind="refs_file_id_128",
        file_id=bytes(range(16)),
        **common,
    )

    assert ntfs.identity_projection == {
        "file_id": "fedcba9876543210",
        "file_id_kind": "ntfs_file_index_64",
        "object_kind": "regular_file",
        "schema": "goodq.windows-file-identity.v1",
        "volume_serial": "123456789abcdef0",
    }
    detached = ntfs.identity_projection
    detached["file_id"] = "0" * 16
    assert ntfs.identity_projection["file_id"] == "fedcba9876543210"
    assert ntfs.identity_json == (
        '{"file_id":"fedcba9876543210",'
        '"file_id_kind":"ntfs_file_index_64",'
        '"object_kind":"regular_file",'
        '"schema":"goodq.windows-file-identity.v1",'
        '"volume_serial":"123456789abcdef0"}'
    )
    assert refs.identity_json == (
        '{"file_id":"000102030405060708090a0b0c0d0e0f",'
        '"file_id_kind":"refs_file_id_128",'
        '"object_kind":"regular_file",'
        '"schema":"goodq.windows-file-identity.v1",'
        '"volume_serial":"123456789abcdef0"}'
    )
    with pytest.raises(AttributeError):
        ntfs.size_bytes = 5


@pytest.mark.parametrize(
    ("code", "message"),
    (
        ("unsupported_platform", "Windows held-handle access is unsupported"),
        ("unsupported_filesystem", "Windows held-handle storage is unsupported"),
        ("redirected_boundary", "Windows held-handle boundary is redirected"),
        ("unexpected_entry_type", "Windows held-handle entry type is unsupported"),
        ("duplicate_identity", "Windows held-handle identity is ambiguous"),
        ("sharing_conflict", "Windows held-handle target is not quiescent"),
        ("observation_raced", "Windows held-handle state changed during observation"),
        ("observation_failed", "Windows held-handle observation failed"),
    ),
)
def test_error_contract_is_exact_and_immutable(code: str, message: str) -> None:
    module = _load_module()
    error = module.WindowsHeldHandleError(code)

    assert error.code == code
    assert str(error) == message
    with pytest.raises(AttributeError):
        error.code = "observation_failed"
    with pytest.raises(ValueError, match="Unknown Windows held-handle error code"):
        module.WindowsHeldHandleError("unknown")


def test_open_returns_owned_opaque_token_and_explicit_close_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    other = module.WindowsHeldHandleBackend()

    token = backend.open_root("X:\\")

    assert not isinstance(token, int)
    with pytest.raises(module.WindowsHeldHandleError) as foreign:
        other.close(token)
    assert foreign.value.code == "observation_failed"
    assert kernel32.closed == []

    backend.close(token)
    assert kernel32.closed == [41]
    with pytest.raises(module.WindowsHeldHandleError) as repeated:
        backend.close(token)
    assert repeated.value.code == "observation_failed"
    assert kernel32.closed == [41]


def test_explicit_close_failure_is_terminal_and_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    kernel32.CloseHandle.implementation = lambda handle: (
        kernel32.closed.append(handle if isinstance(handle, int) else handle.value)
        or 0
    )
    module, backend = _backend(monkeypatch, kernel32)
    token = backend.open_root("X:\\")

    with pytest.raises(module.WindowsHeldHandleError) as first:
        backend.close(token)
    assert first.value.code == "observation_failed"
    assert kernel32.closed == [41]

    with pytest.raises(module.WindowsHeldHandleError) as repeated:
        backend.close(token)
    assert repeated.value.code == "observation_failed"
    assert kernel32.closed == [41]


def test_context_exit_closes_live_tokens_in_reverse_and_attempts_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    raw_handles = iter((41, 42, 43))
    kernel32.CreateFileW.implementation = lambda *_args: next(raw_handles)

    def close_with_middle_failure(handle) -> int:
        raw = handle if isinstance(handle, int) else handle.value
        kernel32.closed.append(raw)
        return int(raw != 42)

    kernel32.CloseHandle.implementation = close_with_middle_failure
    module, backend = _backend(monkeypatch, kernel32)

    tokens: list[object] = []
    with pytest.raises(module.WindowsHeldHandleError) as exc_info:
        with backend:
            tokens.append(backend.open_root("X:\\"))
            tokens.append(backend.open_root("X:\\"))
            tokens.append(backend.open_root("X:\\"))

    assert exc_info.value.code == "observation_failed"
    assert kernel32.closed == [43, 42, 41]
    with pytest.raises(module.WindowsHeldHandleError) as post_context:
        backend.open_root("X:\\")
    assert post_context.value.code == "observation_failed"
    with pytest.raises(module.WindowsHeldHandleError) as post_context_close:
        backend.close(tokens[0])
    assert post_context_close.value.code == "observation_failed"
    assert kernel32.closed == [43, 42, 41]


def test_context_exit_preserves_primary_and_attaches_close_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    kernel32.CloseHandle.implementation = lambda _handle: 0
    module, backend = _backend(monkeypatch, kernel32)
    primary = RuntimeError("primary")

    with pytest.raises(RuntimeError) as exc_info:
        with backend:
            backend.open_root("X:\\")
            raise primary

    assert exc_info.value is primary
    assert isinstance(primary.__cause__, module.WindowsHeldHandleError)
    assert primary.__cause__.code == "observation_failed"


def test_context_exit_preserves_existing_cause_and_uses_close_failure_as_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    kernel32.CloseHandle.implementation = lambda _handle: 0
    module, backend = _backend(monkeypatch, kernel32)
    original_cause = OSError("original")
    primary = RuntimeError("primary")
    primary.__cause__ = original_cause
    primary.__suppress_context__ = True

    with pytest.raises(RuntimeError) as exc_info:
        with backend:
            backend.open_root("X:\\")
            raise primary

    assert exc_info.value is primary
    assert primary.__cause__ is original_cause
    assert isinstance(primary.__context__, module.WindowsHeldHandleError)
    assert primary.__context__.code == "observation_failed"


@pytest.mark.parametrize(
    ("filesystem", "flags", "expected"),
    (
        ("FAT32", 0x01000000, "unsupported_filesystem"),
        ("NTFS", 0, "unsupported_filesystem"),
        ("NTFS", 0x01000000, "NTFS"),
    ),
)
def test_volume_filesystem_requires_ntfs_or_refs_with_open_by_id(
    monkeypatch: pytest.MonkeyPatch,
    filesystem: str,
    flags: int,
    expected: str,
) -> None:
    kernel32 = _Kernel32()

    def volume_info(
        _handle,
        _volume_name,
        _volume_name_size,
        _serial,
        _max_component,
        volume_flags,
        filesystem_name,
        _filesystem_name_size,
    ) -> int:
        volume_flags._obj.value = flags
        filesystem_name.value = filesystem
        return 1

    kernel32.GetVolumeInformationByHandleW.implementation = volume_info
    module, backend = _backend(monkeypatch, kernel32)
    token = backend.open_root("X:\\")

    if expected == "NTFS":
        assert backend.volume_filesystem(token) == expected
    else:
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.volume_filesystem(token)
        assert exc_info.value.code == expected


def test_windows_abi_and_open_flags_are_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    root_calls: list[tuple[object, ...]] = []
    id_calls: list[tuple[object, ...]] = []

    def create_file(*args):
        root_calls.append(args)
        return 101

    def open_by_id(*args):
        id_calls.append(args)
        return 202 + len(id_calls)

    kernel32.CreateFileW.implementation = create_file
    kernel32.OpenFileById.implementation = open_by_id
    module, backend = _backend(monkeypatch, kernel32)

    assert backend._FILE_ID_BOTH_DIR_INFO_STRUCT.FileName.offset == 104
    assert ctypes.sizeof(backend._FILE_ID_BOTH_DIR_INFO_STRUCT) == 112
    assert backend._FILE_ID_EXTD_DIR_INFO_STRUCT.FileName.offset == 88
    assert ctypes.sizeof(backend._FILE_ID_EXTD_DIR_INFO_STRUCT) == 96
    assert backend._FILE_STREAM_INFO_STRUCT.StreamName.offset == 24
    assert ctypes.sizeof(backend._FILE_STREAM_INFO_STRUCT) == 32
    assert ctypes.sizeof(backend._FILE_ID_DESCRIPTOR_STRUCT) == 24
    assert ctypes.sizeof(backend._FILE_ID_INFO_STRUCT) == 24
    assert ctypes.sizeof(backend._FILE_BASIC_INFO_STRUCT) == 40
    assert ctypes.sizeof(backend._FILE_STANDARD_INFO_STRUCT) == 24
    assert ctypes.sizeof(backend._FILE_ATTRIBUTE_TAG_INFO_STRUCT) == 8
    assert ctypes.sizeof(backend._BY_HANDLE_FILE_INFORMATION_STRUCT) == 52

    with backend:
        root_handle = backend.open_root("X:\\")
        high_id = (1 << 63) + 7
        backend.open_by_id(
            root_handle,
            module.WindowsDirectoryEntry(
                "member.index", 0, "ntfs_file_index_64", high_id
            ),
            directory=False,
        )
        backend.open_by_id(
            root_handle,
            module.WindowsDirectoryEntry(
                "faiss", backend._FILE_ATTRIBUTE_DIRECTORY, "ntfs_file_index_64", 8
            ),
            directory=True,
        )
        refs_id = bytes(range(16))
        backend.open_by_id(
            root_handle,
            module.WindowsDirectoryEntry(
                "refs.index", 0, "refs_file_id_128", refs_id
            ),
            directory=False,
        )

    assert root_calls == [
        (
            "X:\\",
            0x81,
            backend._FILE_SHARE_READ,
            None,
            backend._OPEN_EXISTING,
            backend._FILE_FLAG_OPEN_REPARSE_POINT
            | backend._FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
    ]
    assert len(id_calls) == 3
    file_call, directory_call, refs_call = id_calls
    file_descriptor = file_call[1]._obj
    assert file_descriptor.Type == backend._FILE_ID_TYPE
    assert file_descriptor.FileId == high_id - (1 << 64)
    assert file_call[0] == 101
    assert file_call[2:] == (
        0x81,
        backend._FILE_SHARE_READ,
        None,
        backend._FILE_FLAG_OPEN_REPARSE_POINT | backend._FILE_FLAG_SEQUENTIAL_SCAN,
    )
    assert directory_call[2:] == (
        0x81,
        backend._FILE_SHARE_READ,
        None,
        backend._FILE_FLAG_OPEN_REPARSE_POINT | backend._FILE_FLAG_BACKUP_SEMANTICS,
    )
    refs_descriptor = refs_call[1]._obj
    assert refs_descriptor.Type == backend._EXTENDED_FILE_ID_TYPE
    assert bytes(refs_descriptor.ExtendedFileId.Identifier) == refs_id


def test_directory_enumeration_restarts_once_consumes_all_buffers_and_sorts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    calls: list[tuple[int, int]] = []
    batches = (
        ((".", backend._FILE_ATTRIBUTE_DIRECTORY, 10), ("z.index", 0, 12)),
        (("A.index", 0, 11),),
    )

    def fill_ntfs(buffer_argument, records) -> None:
        base = ctypes.addressof(buffer_argument._obj)
        structure = backend._FILE_ID_BOTH_DIR_INFO_STRUCT
        offset = 0
        for index, (name, attributes, file_id) in enumerate(records):
            encoded = name.encode("utf-16-le")
            record_size = structure.FileName.offset + len(encoded)
            aligned_size = (record_size + 7) & ~7
            record = structure()
            record.NextEntryOffset = aligned_size if index + 1 < len(records) else 0
            record.FileAttributes = attributes
            record.FileNameLength = len(encoded)
            record.FileId = file_id
            ctypes.memmove(base + offset, ctypes.byref(record), structure.FileName.offset)
            ctypes.memmove(base + offset + structure.FileName.offset, encoded, len(encoded))
            offset += aligned_size

    def enumerate_impl(handle, info_class, buffer_argument, _buffer_size) -> int:
        raw = handle if isinstance(handle, int) else handle.value
        calls.append((raw, info_class))
        index = len(calls) - 1
        if index < len(batches):
            fill_ntfs(buffer_argument, batches[index])
            return 1
        ctypes.set_last_error(backend._ERROR_NO_MORE_FILES)
        return 0

    kernel32.GetFileInformationByHandleEx.implementation = enumerate_impl
    with backend:
        root = backend.open_root("X:\\")
        entries = backend.enumerate_directory(root, "NTFS")

    assert calls == [
        (41, backend._FILE_ID_BOTH_DIRECTORY_RESTART_INFO),
        (41, backend._FILE_ID_BOTH_DIRECTORY_INFO),
        (41, backend._FILE_ID_BOTH_DIRECTORY_INFO),
    ]
    assert entries == (
        module.WindowsDirectoryEntry("A.index", 0, "ntfs_file_index_64", 11),
        module.WindowsDirectoryEntry("z.index", 0, "ntfs_file_index_64", 12),
    )


def test_refs_directory_enumeration_preserves_all_128_file_id_bits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    calls: list[int] = []
    expected_id = bytes(range(16))

    def enumerate_impl(_handle, info_class, buffer_argument, _buffer_size) -> int:
        calls.append(info_class)
        if len(calls) == 1:
            structure = backend._FILE_ID_EXTD_DIR_INFO_STRUCT
            record = structure()
            encoded = "member.index".encode("utf-16-le")
            record.FileNameLength = len(encoded)
            for index, byte in enumerate(expected_id):
                record.FileId.Identifier[index] = byte
            base = ctypes.addressof(buffer_argument._obj)
            ctypes.memmove(base, ctypes.byref(record), structure.FileName.offset)
            ctypes.memmove(base + structure.FileName.offset, encoded, len(encoded))
            return 1
        ctypes.set_last_error(backend._ERROR_NO_MORE_FILES)
        return 0

    kernel32.GetFileInformationByHandleEx.implementation = enumerate_impl
    with backend:
        root = backend.open_root("X:\\")
        entries = backend.enumerate_directory(root, "ReFS")

    assert calls == [
        backend._FILE_ID_EXTD_DIRECTORY_RESTART_INFO,
        backend._FILE_ID_EXTD_DIRECTORY_INFO,
    ]
    assert entries == (
        module.WindowsDirectoryEntry(
            "member.index",
            0,
            "refs_file_id_128",
            expected_id,
        ),
    )


def test_snapshot_rejects_post_open_reparse_before_other_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    queried: list[int] = []
    by_handle_calls = 0

    def query_impl(_handle, info_class, buffer_argument, _buffer_size) -> int:
        queried.append(info_class)
        if info_class != backend._FILE_ATTRIBUTE_TAG_INFO:
            raise AssertionError("post-open redirected boundary reached later query")
        value = buffer_argument._obj
        value.FileAttributes = backend._FILE_ATTRIBUTE_REPARSE_POINT
        value.ReparseTag = 0xA000000C
        return 1

    def by_handle_impl(*_args) -> int:
        nonlocal by_handle_calls
        by_handle_calls += 1
        raise AssertionError("post-open redirected boundary reached identity query")

    kernel32.GetFileInformationByHandleEx.implementation = query_impl
    kernel32.GetFileInformationByHandle.implementation = by_handle_impl
    with backend:
        root = backend.open_root("X:\\")
        member = backend.open_by_id(
            root,
            module.WindowsDirectoryEntry("member", 0, "ntfs_file_index_64", 7),
            directory=False,
        )
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.snapshot(
                member,
                filesystem="NTFS",
                expected=module.WindowsDirectoryEntry(
                    "member",
                    0,
                    "ntfs_file_index_64",
                    7,
                ),
                object_kind="regular_file",
                require_stream_contract=False,
            )

    assert exc_info.value.code == "redirected_boundary"
    assert queried == [backend._FILE_ATTRIBUTE_TAG_INFO]
    assert by_handle_calls == 0


def test_snapshot_captures_stable_ntfs_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    file_id = 0x123456789ABCDEF0
    volume_serial = 0xFEDCBA9876543210
    query_order: list[int] = []

    def query_impl(_handle, info_class, buffer_argument, _buffer_size) -> int:
        query_order.append(info_class)
        value = buffer_argument._obj
        if info_class == backend._FILE_ATTRIBUTE_TAG_INFO:
            value.FileAttributes = 0
            value.ReparseTag = 0
        elif info_class == backend._FILE_ID_INFO:
            value.VolumeSerialNumber = volume_serial
        elif info_class == backend._FILE_BASIC_INFO:
            value.LastWriteTime = backend._FILETIME_UNIX_EPOCH + 5
            value.ChangeTime = backend._FILETIME_UNIX_EPOCH + 6
        elif info_class == backend._FILE_STANDARD_INFO:
            value.AllocationSize = 4096
            value.EndOfFile = 4
            value.NumberOfLinks = 1
            value.DeletePending = 0
            value.Directory = 0
        else:
            raise AssertionError(info_class)
        return 1

    def by_handle_impl(_handle, value_argument) -> int:
        value = value_argument._obj
        value.dwVolumeSerialNumber = volume_serial & 0xFFFFFFFF
        value.nFileSizeHigh = 0
        value.nFileSizeLow = 4
        value.nNumberOfLinks = 1
        value.nFileIndexHigh = file_id >> 32
        value.nFileIndexLow = file_id & 0xFFFFFFFF
        return 1

    kernel32.GetFileInformationByHandleEx.implementation = query_impl
    kernel32.GetFileInformationByHandle.implementation = by_handle_impl
    expected = module.WindowsDirectoryEntry(
        "member",
        0,
        "ntfs_file_index_64",
        file_id,
    )
    with backend:
        root = backend.open_root("X:\\")
        member = backend.open_by_id(root, expected, directory=False)
        snapshot = backend.snapshot(
            member,
            filesystem="NTFS",
            expected=expected,
            object_kind="regular_file",
            require_stream_contract=False,
        )

    assert query_order == [
        backend._FILE_ATTRIBUTE_TAG_INFO,
        backend._FILE_ID_INFO,
        backend._FILE_BASIC_INFO,
        backend._FILE_STANDARD_INFO,
    ]
    assert snapshot == module.WindowsObjectSnapshot(
        volume_serial=volume_serial,
        file_id_kind="ntfs_file_index_64",
        file_id=file_id,
        object_kind="regular_file",
        size_bytes=4,
        mtime_ns=500,
        allocation_size=4096,
        link_count=1,
        attributes=0,
        reparse_tag=0,
        last_write_ticks=backend._FILETIME_UNIX_EPOCH + 5,
        change_ticks=backend._FILETIME_UNIX_EPOCH + 6,
        streams=(),
    )


def test_snapshot_requires_exact_unnamed_data_stream_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    file_id = 7
    volume_serial = 9

    def query_impl(_handle, info_class, buffer_argument, _buffer_size) -> int:
        value = buffer_argument._obj
        if info_class == backend._FILE_ATTRIBUTE_TAG_INFO:
            value.FileAttributes = 0
            value.ReparseTag = 0
        elif info_class == backend._FILE_ID_INFO:
            value.VolumeSerialNumber = volume_serial
        elif info_class == backend._FILE_BASIC_INFO:
            value.LastWriteTime = backend._FILETIME_UNIX_EPOCH + 1
            value.ChangeTime = backend._FILETIME_UNIX_EPOCH + 2
        elif info_class == backend._FILE_STANDARD_INFO:
            value.AllocationSize = 4096
            value.EndOfFile = 4
            value.NumberOfLinks = 1
            value.DeletePending = 0
            value.Directory = 0
        elif info_class == backend._FILE_STREAM_INFO:
            structure = backend._FILE_STREAM_INFO_STRUCT
            record = structure()
            encoded = "::$DATA".encode("utf-16-le")
            record.StreamNameLength = len(encoded)
            record.StreamSize = 4
            record.StreamAllocationSize = 4096
            base = ctypes.addressof(value)
            ctypes.memmove(base, ctypes.byref(record), structure.StreamName.offset)
            ctypes.memmove(base + structure.StreamName.offset, encoded, len(encoded))
        else:
            raise AssertionError(info_class)
        return 1

    def by_handle_impl(_handle, value_argument) -> int:
        value = value_argument._obj
        value.nFileSizeLow = 4
        value.nNumberOfLinks = 1
        value.nFileIndexLow = file_id
        return 1

    kernel32.GetFileInformationByHandleEx.implementation = query_impl
    kernel32.GetFileInformationByHandle.implementation = by_handle_impl
    expected = module.WindowsDirectoryEntry(
        "member",
        0,
        "ntfs_file_index_64",
        file_id,
    )
    with backend:
        root = backend.open_root("X:\\")
        member = backend.open_by_id(root, expected, directory=False)
        snapshot = backend.snapshot(
            member,
            filesystem="NTFS",
            expected=expected,
            object_kind="regular_file",
            require_stream_contract=True,
        )

    assert snapshot.streams == (("::$DATA", 4, 4096),)


def test_hash_file_rewinds_and_reads_the_held_token_to_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    seek_calls: list[tuple[int, int, object, int]] = []
    chunks = iter((b"ab", b"cd", b""))

    def seek_impl(handle, distance, new_position, origin) -> int:
        raw = handle if isinstance(handle, int) else handle.value
        seek_calls.append((raw, int(distance), new_position, origin))
        return 1

    def read_impl(handle, buffer_argument, _buffer_size, read_argument, _overlap) -> int:
        raw = handle if isinstance(handle, int) else handle.value
        assert raw == 42
        chunk = next(chunks)
        if chunk:
            ctypes.memmove(buffer_argument, chunk, len(chunk))
        read_argument._obj.value = len(chunk)
        return 1

    kernel32.SetFilePointerEx.implementation = seek_impl
    kernel32.ReadFile.implementation = read_impl
    expected = module.WindowsDirectoryEntry(
        "member",
        0,
        "ntfs_file_index_64",
        7,
    )
    with backend:
        root = backend.open_root("X:\\")
        member = backend.open_by_id(root, expected, directory=False)
        digest, total = backend.hash_file(member)

    assert seek_calls == [(42, 0, None, backend._FILE_BEGIN)]
    assert digest == hashlib.sha256(b"abcd").hexdigest()
    assert total == 4


def test_read_file_bounded_observes_eof_only_after_zero_byte_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    payload = bytes(range(65))
    cursor = 0
    seek_calls: list[tuple[int, int, object, int]] = []
    read_trace: list[tuple[int, int]] = []

    def seek_impl(handle, distance, new_position, origin) -> int:
        nonlocal cursor
        raw = handle if isinstance(handle, int) else handle.value
        cursor = 0
        seek_calls.append((raw, int(distance), new_position, origin))
        return 1

    def read_impl(handle, buffer_argument, buffer_size, read_argument, _overlap) -> int:
        nonlocal cursor
        raw = handle if isinstance(handle, int) else handle.value
        request = int(buffer_size)
        assert raw == 42
        assert request > 0
        count = min(17, request, len(payload) - cursor)
        read_trace.append((request, count))
        chunk = payload[cursor : cursor + count]
        if chunk:
            ctypes.memmove(buffer_argument, chunk, len(chunk))
        cursor += count
        read_argument._obj.value = count
        return 1

    kernel32.SetFilePointerEx.implementation = seek_impl
    kernel32.ReadFile.implementation = read_impl
    with backend:
        member = _open_test_member(module, backend)
        prefix, eof_observed = backend.read_file_bounded(member, maximum_bytes=66)

    assert prefix == payload
    assert eof_observed is True
    assert seek_calls == [(42, 0, None, backend._FILE_BEGIN)]
    _assert_bounded_read_trace(
        read_trace,
        maximum_bytes=66,
        returned_bytes=len(payload),
        eof_observed=eof_observed,
    )


@pytest.mark.parametrize("payload_length", (66, 67))
def test_read_file_bounded_stops_at_cap_without_extra_probe(
    monkeypatch: pytest.MonkeyPatch,
    payload_length: int,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    payload = bytes(range(payload_length))
    cursor = 0
    read_trace: list[tuple[int, int]] = []

    def seek_impl(*_args) -> int:
        nonlocal cursor
        cursor = 0
        return 1

    def read_impl(_handle, buffer_argument, buffer_size, read_argument, _overlap) -> int:
        nonlocal cursor
        request = int(buffer_size)
        assert request > 0
        count = min(17, request, len(payload) - cursor)
        read_trace.append((request, count))
        chunk = payload[cursor : cursor + count]
        ctypes.memmove(buffer_argument, chunk, len(chunk))
        cursor += count
        read_argument._obj.value = count
        return 1

    kernel32.SetFilePointerEx.implementation = seek_impl
    kernel32.ReadFile.implementation = read_impl
    with backend:
        member = _open_test_member(module, backend)
        prefix, eof_observed = backend.read_file_bounded(member, maximum_bytes=66)

    assert prefix == payload[:66]
    assert eof_observed is False
    _assert_bounded_read_trace(
        read_trace,
        maximum_bytes=66,
        returned_bytes=len(prefix),
        eof_observed=eof_observed,
    )


@pytest.mark.parametrize(
    "maximum_bytes",
    (True, False, 0, -1, 67, 1.0, "1", None, _IntSubclass(1)),
)
def test_read_file_bounded_rejects_invalid_limit_before_native_call(
    monkeypatch: pytest.MonkeyPatch,
    maximum_bytes: object,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    with backend:
        member = _open_test_member(module, backend)

        def forbidden_native_call(*_args) -> int:
            raise AssertionError("invalid limit reached native I/O")

        kernel32.SetFilePointerEx.implementation = forbidden_native_call
        kernel32.ReadFile.implementation = forbidden_native_call
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.read_file_bounded(member, maximum_bytes=maximum_bytes)

    assert exc_info.value.code == "observation_failed"
    assert exc_info.value.__cause__ is None


def test_read_file_bounded_rejects_foreign_token_before_native_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, owner = _backend(monkeypatch, kernel32)
    observer = module.WindowsHeldHandleBackend()
    with owner, observer:
        member = _open_test_member(module, owner)

        def forbidden_native_call(*_args) -> int:
            raise AssertionError("foreign token reached native I/O")

        kernel32.SetFilePointerEx.implementation = forbidden_native_call
        kernel32.ReadFile.implementation = forbidden_native_call
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            observer.read_file_bounded(member, maximum_bytes=1)

    assert exc_info.value.code == "observation_failed"


@pytest.mark.parametrize(
    ("payload", "maximum_bytes"),
    (
        (b"", 1),
        (b"xy", 66),
    ),
)
def test_read_file_bounded_observes_empty_and_short_eof(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    maximum_bytes: int,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    cursor = 0
    read_trace: list[tuple[int, int]] = []

    def seek_impl(*_args) -> int:
        nonlocal cursor
        cursor = 0
        return 1

    def read_impl(_handle, buffer_argument, buffer_size, read_argument, _overlap) -> int:
        nonlocal cursor
        request = int(buffer_size)
        count = min(request, len(payload) - cursor)
        read_trace.append((request, count))
        chunk = payload[cursor : cursor + count]
        if chunk:
            ctypes.memmove(buffer_argument, chunk, len(chunk))
        cursor += count
        read_argument._obj.value = count
        return 1

    kernel32.SetFilePointerEx.implementation = seek_impl
    kernel32.ReadFile.implementation = read_impl
    with backend:
        member = _open_test_member(module, backend)
        result = backend.read_file_bounded(member, maximum_bytes=maximum_bytes)

    prefix, eof_observed = result
    assert result == (payload, True)
    _assert_bounded_read_trace(
        read_trace,
        maximum_bytes=maximum_bytes,
        returned_bytes=len(prefix),
        eof_observed=eof_observed,
    )


def test_read_file_bounded_rejects_closed_and_post_context_tokens_before_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, closed_backend = _backend(monkeypatch, kernel32)
    with closed_backend:
        closed_member = _open_test_member(module, closed_backend)
        closed_backend.close(closed_member)

        def forbidden_native_call(*_args) -> int:
            raise AssertionError("non-live token reached native I/O")

        kernel32.SetFilePointerEx.implementation = forbidden_native_call
        kernel32.ReadFile.implementation = forbidden_native_call
        with pytest.raises(module.WindowsHeldHandleError) as closed_exc:
            closed_backend.read_file_bounded(closed_member, maximum_bytes=1)

    post_context_backend = module.WindowsHeldHandleBackend()
    kernel32.SetFilePointerEx.implementation = lambda *_args: 1
    kernel32.ReadFile.implementation = lambda *_args: 1
    with post_context_backend:
        post_context_member = _open_test_member(module, post_context_backend)
    kernel32.SetFilePointerEx.implementation = forbidden_native_call
    kernel32.ReadFile.implementation = forbidden_native_call
    with pytest.raises(module.WindowsHeldHandleError) as post_context_exc:
        post_context_backend.read_file_bounded(post_context_member, maximum_bytes=1)

    assert closed_exc.value.code == "observation_failed"
    assert post_context_exc.value.code == "observation_failed"


def test_read_file_bounded_rejects_impossible_native_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)

    def read_impl(_handle, _buffer, buffer_size, read_argument, _overlap) -> int:
        read_argument._obj.value = int(buffer_size) + 1
        return 1

    kernel32.ReadFile.implementation = read_impl
    with backend:
        member = _open_test_member(module, backend)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.read_file_bounded(member, maximum_bytes=1)

    assert exc_info.value.code == "observation_failed"
    assert exc_info.value.__cause__ is None


def test_bounded_read_and_hash_each_rewind_the_same_held_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    payload = b"abcd"
    cursor = 0
    seek_count = 0

    def seek_impl(*_args) -> int:
        nonlocal cursor, seek_count
        cursor = 0
        seek_count += 1
        return 1

    def read_impl(_handle, buffer_argument, buffer_size, read_argument, _overlap) -> int:
        nonlocal cursor
        request = int(buffer_size)
        count = min(request, len(payload) - cursor)
        chunk = payload[cursor : cursor + count]
        if chunk:
            ctypes.memmove(buffer_argument, chunk, len(chunk))
        cursor += count
        read_argument._obj.value = count
        return 1

    kernel32.SetFilePointerEx.implementation = seek_impl
    kernel32.ReadFile.implementation = read_impl
    with backend:
        member = _open_test_member(module, backend)
        assert backend.read_file_bounded(member, maximum_bytes=5) == (payload, True)
        assert backend.hash_file(member) == (hashlib.sha256(payload).hexdigest(), 4)
        assert backend.hash_file(member) == (hashlib.sha256(payload).hexdigest(), 4)
        assert backend.read_file_bounded(member, maximum_bytes=5) == (payload, True)

    assert seek_count == 4


def test_security_profile_adds_read_control_only_to_descendant_opens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    root_calls: list[tuple[object, ...]] = []
    descendant_calls: list[tuple[object, ...]] = []
    next_handle = iter((42, 43))

    def create_file(*args):
        root_calls.append(args)
        return 41

    def open_by_id(*args):
        descendant_calls.append(args)
        return next(next_handle)

    kernel32.CreateFileW.implementation = create_file
    kernel32.OpenFileById.implementation = open_by_id
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )
    directory = module.WindowsDirectoryEntry(
        "directory",
        backend._FILE_ATTRIBUTE_DIRECTORY,
        "ntfs_file_index_64",
        7,
    )
    regular = module.WindowsDirectoryEntry(
        "pin",
        0,
        "ntfs_file_index_64",
        8,
    )

    with backend:
        root = backend.open_root("X:\\")
        backend.open_by_id(root, directory, directory=True)
        backend.open_by_id(root, regular, directory=False)

    assert root_calls == [
        (
            "X:\\",
            0x00000081,
            backend._FILE_SHARE_READ,
            None,
            backend._OPEN_EXISTING,
            backend._FILE_FLAG_OPEN_REPARSE_POINT
            | backend._FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
    ]
    assert len(descendant_calls) == 2
    directory_call, regular_call = descendant_calls
    assert directory_call[0] == 41
    assert directory_call[1]._obj.Type == backend._FILE_ID_TYPE
    assert directory_call[1]._obj.FileId == 7
    assert directory_call[2:] == (
        0x00020081,
        backend._FILE_SHARE_READ,
        None,
        backend._FILE_FLAG_OPEN_REPARSE_POINT
        | backend._FILE_FLAG_BACKUP_SEMANTICS,
    )
    assert regular_call[0] == 41
    assert regular_call[1]._obj.Type == backend._FILE_ID_TYPE
    assert regular_call[1]._obj.FileId == 8
    assert regular_call[2:] == (
        0x00020081,
        backend._FILE_SHARE_READ,
        None,
        backend._FILE_FLAG_OPEN_REPARSE_POINT
        | backend._FILE_FLAG_SEQUENTIAL_SCAN,
    )


def test_descriptor_read_rejects_default_and_volume_root_before_security_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_kernel = _Kernel32()
    module, default_backend = _backend(monkeypatch, default_kernel)
    with default_backend:
        default_member = _open_test_member(module, default_backend)
        with pytest.raises(module.WindowsHeldHandleError) as default_error:
            default_backend.read_security_descriptor(default_member)
    assert default_error.value.code == "observation_failed"

    security_kernel = _Kernel32()
    security_advapi = _Advapi32()
    script = _SecurityScript()
    script.bind(security_kernel, security_advapi)
    module, security_backend = _backend(
        monkeypatch,
        security_kernel,
        access_profile="security_read",
        advapi32=security_advapi,
    )
    with security_backend:
        root = security_backend.open_root("X:\\")
        with pytest.raises(module.WindowsHeldHandleError) as root_error:
            security_backend.read_security_descriptor(root)

    assert root_error.value.code == "observation_failed"
    assert script.security_calls == []


def test_security_descriptor_is_exact_detached_same_handle_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"\x01\x00security\x00descriptor\xfe\xff"
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    script = _SecurityScript(payload)
    script.poison_on_free = True
    script.bind(kernel32, advapi32)
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )

    with backend:
        member = _open_test_member(module, backend)
        result = backend.read_security_descriptor(member)

    assert type(result) is bytes
    assert result == payload
    assert bytes(script.buffer) == b"\xee" * len(payload)
    assert script.freed == [script.address]
    assert len(script.security_calls) == 1
    call = script.security_calls[0]
    assert call[:3] == (42, 1, 0x00000007)
    assert call[3:7] == (None, None, None, None)
    assert call[7] is not None
    assert script.valid_pointers == [script.address]
    assert script.control_pointers == [script.address]
    assert script.length_pointers == [script.address]


def test_security_descriptor_accepts_inclusive_maximum_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"\xa5" * 131072
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    script = _SecurityScript(payload)
    script.bind(kernel32, advapi32)
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )

    with backend:
        member = _open_test_member(module, backend)
        result = backend.read_security_descriptor(member)

    assert result == payload
    assert script.freed == [script.address]


@pytest.mark.parametrize(
    ("failure_mode", "expected_stages", "expected_frees"),
    (
        ("native_error_with_output", (0, 0, 0), 0),
        ("success_null", (0, 0, 0), 0),
        ("invalid_descriptor", (1, 0, 0), 1),
        ("bad_revision", (1, 1, 0), 1),
        ("not_self_relative", (1, 1, 0), 1),
        ("short_length", (1, 1, 1), 1),
        ("long_length", (1, 1, 1), 1),
    ),
)
def test_security_descriptor_fails_closed_in_selected_validation_order(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
    expected_stages: tuple[int, int, int],
    expected_frees: int,
) -> None:
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    script = _SecurityScript()
    if failure_mode == "native_error_with_output":
        script.security_result = 5
        script.security_last_error = 87
        script.write_descriptor_on_error = True
    elif failure_mode == "success_null":
        script.write_descriptor_on_success = False
    elif failure_mode == "invalid_descriptor":
        script.valid = False
        script.valid_last_error = 87
    elif failure_mode == "bad_revision":
        script.revision = 2
    elif failure_mode == "not_self_relative":
        script.control = 0
    elif failure_mode == "short_length":
        script.length = 19
    elif failure_mode == "long_length":
        script.length = 131073
    script.bind(kernel32, advapi32)
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )

    with backend:
        member = _open_test_member(module, backend)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.read_security_descriptor(member)

    assert exc_info.value.code == "observation_failed"
    assert (script.valid_calls, script.control_calls, script.length_calls) == (
        expected_stages
    )
    assert len(script.freed) == expected_frees
    if failure_mode == "native_error_with_output":
        assert isinstance(exc_info.value.__cause__, OSError)
        assert exc_info.value.__cause__.winerror == 5
    elif failure_mode == "invalid_descriptor":
        assert exc_info.value.__cause__ is None


def test_security_descriptor_captures_control_error_before_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    script = _SecurityScript()
    script.control_success = False
    script.control_error = 5
    script.bind(kernel32, advapi32)
    original_free = script._local_free

    def free_and_overwrite_error(descriptor):
        result = original_free(descriptor)
        ctypes.set_last_error(87)
        return result

    kernel32.LocalFree.implementation = free_and_overwrite_error
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )

    with backend:
        member = _open_test_member(module, backend)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.read_security_descriptor(member)

    assert exc_info.value.code == "observation_failed"
    assert isinstance(exc_info.value.__cause__, OSError)
    assert exc_info.value.__cause__.winerror == 5
    assert script.freed == [script.address]


def test_security_descriptor_primary_without_cause_attaches_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    script = _SecurityScript()
    script.valid = False
    script.local_free_result = script.address
    script.local_free_error = 6
    script.bind(kernel32, advapi32)
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )

    with backend:
        member = _open_test_member(module, backend)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.read_security_descriptor(member)

    assert exc_info.value.code == "observation_failed"
    assert isinstance(exc_info.value.__cause__, module.WindowsHeldHandleError)
    assert isinstance(exc_info.value.__cause__.__cause__, OSError)
    assert exc_info.value.__cause__.__cause__.winerror == 6
    assert script.freed == [script.address]


def test_security_descriptor_rejects_malformed_copy_and_still_frees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    script = _SecurityScript()
    script.bind(kernel32, advapi32)
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )
    monkeypatch.setattr(ctypes, "string_at", lambda *_args: b"short")

    with backend:
        member = _open_test_member(module, backend)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.read_security_descriptor(member)

    assert exc_info.value.code == "observation_failed"
    assert script.freed == [script.address]


def test_security_descriptor_cleanup_failure_prevents_successful_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    script = _SecurityScript()
    script.local_free_result = script.address
    script.local_free_error = 6
    script.bind(kernel32, advapi32)
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )

    with backend:
        member = _open_test_member(module, backend)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.read_security_descriptor(member)

    assert exc_info.value.code == "observation_failed"
    assert isinstance(exc_info.value.__cause__, OSError)
    assert exc_info.value.__cause__.winerror == 6
    assert script.freed == [script.address]


def test_security_descriptor_primary_failure_survives_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    script = _SecurityScript()
    script.control_success = False
    script.control_error = 5
    script.local_free_result = script.address
    script.local_free_error = 6
    script.bind(kernel32, advapi32)
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )

    with backend:
        member = _open_test_member(module, backend)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.read_security_descriptor(member)

    assert exc_info.value.code == "observation_failed"
    assert isinstance(exc_info.value.__cause__, OSError)
    assert exc_info.value.__cause__.winerror == 5
    assert isinstance(exc_info.value.__context__, module.WindowsHeldHandleError)
    assert isinstance(exc_info.value.__context__.__cause__, OSError)
    assert exc_info.value.__context__.__cause__.winerror == 6
    assert script.freed == [script.address]


def test_security_descriptor_rejects_foreign_closed_and_post_context_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    advapi32 = _Advapi32()
    script = _SecurityScript()
    script.bind(kernel32, advapi32)
    module, backend = _backend(
        monkeypatch,
        kernel32,
        access_profile="security_read",
        advapi32=advapi32,
    )
    other_kernel = _Kernel32()
    other_advapi = _Advapi32()
    other_script = _SecurityScript()
    other_script.bind(other_kernel, other_advapi)
    _, other = _backend(
        monkeypatch,
        other_kernel,
        access_profile="security_read",
        advapi32=other_advapi,
    )

    with backend:
        member = _open_test_member(module, backend)
        with pytest.raises(module.WindowsHeldHandleError):
            other.read_security_descriptor(member)
        backend.close(member)
        with pytest.raises(module.WindowsHeldHandleError):
            backend.read_security_descriptor(member)
    with pytest.raises(module.WindowsHeldHandleError):
        backend.read_security_descriptor(member)

    assert script.security_calls == []
    assert other_script.security_calls == []


def test_windows_filetime_conversion_is_exact_and_bounded() -> None:
    module = _load_module()
    epoch = module.WindowsHeldHandleBackend._FILETIME_UNIX_EPOCH

    assert module._windows_filetime_to_ns(epoch) == 0
    assert module._windows_filetime_to_ns(epoch + 1) == 100
    for value in (
        True,
        epoch - 1,
        epoch + ((1 << 63) - 1) // 100 + 1,
    ):
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            module._windows_filetime_to_ns(value)
        assert exc_info.value.code == "observation_failed"


def test_failed_open_is_not_registered_and_maps_unsupported_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)

    def fail_open(*_args) -> int:
        ctypes.set_last_error(backend._ERROR_NOT_SUPPORTED)
        return backend._invalid_handle

    kernel32.OpenFileById.implementation = fail_open
    with backend:
        root = backend.open_root("X:\\")
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.open_by_id(
                root,
                module.WindowsDirectoryEntry(
                    "member",
                    0,
                    "ntfs_file_index_64",
                    7,
                ),
                directory=False,
            )

    assert exc_info.value.code == "unsupported_filesystem"
    assert isinstance(exc_info.value.__cause__, OSError)
    assert kernel32.closed == [41]


def test_snapshot_rejects_post_open_device_before_other_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    queried: list[int] = []

    def query_impl(_handle, info_class, buffer_argument, _buffer_size) -> int:
        queried.append(info_class)
        if info_class != backend._FILE_ATTRIBUTE_TAG_INFO:
            raise AssertionError("post-open device boundary reached later query")
        value = buffer_argument._obj
        value.FileAttributes = backend._FILE_ATTRIBUTE_DEVICE
        value.ReparseTag = 0
        return 1

    kernel32.GetFileInformationByHandleEx.implementation = query_impl
    expected = module.WindowsDirectoryEntry(
        "member",
        0,
        "ntfs_file_index_64",
        7,
    )
    with backend:
        root = backend.open_root("X:\\")
        member = backend.open_by_id(root, expected, directory=False)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.snapshot(
                member,
                filesystem="NTFS",
                expected=expected,
                object_kind="regular_file",
                require_stream_contract=False,
            )

    assert exc_info.value.code == "unexpected_entry_type"
    assert queried == [backend._FILE_ATTRIBUTE_TAG_INFO]


def test_snapshot_captures_stable_refs_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)
    file_id = bytes(range(16))
    volume_serial = 0x123456789ABCDEF0

    def query_impl(_handle, info_class, buffer_argument, _buffer_size) -> int:
        value = buffer_argument._obj
        if info_class == backend._FILE_ATTRIBUTE_TAG_INFO:
            value.FileAttributes = 0
            value.ReparseTag = 0
        elif info_class == backend._FILE_ID_INFO:
            value.VolumeSerialNumber = volume_serial
            for index, byte in enumerate(file_id):
                value.FileId.Identifier[index] = byte
        elif info_class == backend._FILE_BASIC_INFO:
            value.LastWriteTime = backend._FILETIME_UNIX_EPOCH
            value.ChangeTime = backend._FILETIME_UNIX_EPOCH
        elif info_class == backend._FILE_STANDARD_INFO:
            value.EndOfFile = 0
            value.AllocationSize = 0
            value.NumberOfLinks = 1
            value.DeletePending = 0
            value.Directory = 0
        else:
            raise AssertionError(info_class)
        return 1

    def by_handle_impl(_handle, value_argument) -> int:
        value = value_argument._obj
        value.nNumberOfLinks = 1
        return 1

    kernel32.GetFileInformationByHandleEx.implementation = query_impl
    kernel32.GetFileInformationByHandle.implementation = by_handle_impl
    expected = module.WindowsDirectoryEntry(
        "member",
        0,
        "refs_file_id_128",
        file_id,
    )
    with backend:
        root = backend.open_root("X:\\")
        member = backend.open_by_id(root, expected, directory=False)
        snapshot = backend.snapshot(
            member,
            filesystem="ReFS",
            expected=expected,
            object_kind="regular_file",
            require_stream_contract=False,
        )

    assert snapshot.file_id_kind == "refs_file_id_128"
    assert snapshot.file_id == file_id
    assert snapshot.identity_json == (
        '{"file_id":"000102030405060708090a0b0c0d0e0f",'
        '"file_id_kind":"refs_file_id_128",'
        '"object_kind":"regular_file",'
        '"schema":"goodq.windows-file-identity.v1",'
        '"volume_serial":"123456789abcdef0"}'
    )


def test_truncated_directory_buffer_maps_to_finite_observation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)

    def query_impl(_handle, _info_class, buffer_argument, buffer_size) -> int:
        structure = backend._FILE_ID_BOTH_DIR_INFO_STRUCT
        record = structure()
        encoded = "x".encode("utf-16-le")
        record.NextEntryOffset = buffer_size - structure.FileName.offset
        record.FileNameLength = len(encoded)
        record.FileId = 9
        base = ctypes.addressof(buffer_argument._obj)
        ctypes.memmove(base, ctypes.byref(record), structure.FileName.offset)
        ctypes.memmove(base + structure.FileName.offset, encoded, len(encoded))
        return 1

    kernel32.GetFileInformationByHandleEx.implementation = query_impl
    with backend:
        root = backend.open_root("X:\\")
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.enumerate_directory(root, "NTFS")

    assert exc_info.value.code == "observation_failed"


def test_truncated_stream_buffer_maps_to_finite_observation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)

    def query_impl(_handle, info_class, buffer_argument, buffer_size) -> int:
        assert info_class == backend._FILE_STREAM_INFO
        structure = backend._FILE_STREAM_INFO_STRUCT
        record = structure()
        encoded = "::$DATA".encode("utf-16-le")
        record.NextEntryOffset = buffer_size - structure.StreamName.offset
        record.StreamNameLength = len(encoded)
        base = ctypes.addressof(buffer_argument._obj)
        ctypes.memmove(base, ctypes.byref(record), structure.StreamName.offset)
        ctypes.memmove(base + structure.StreamName.offset, encoded, len(encoded))
        return 1

    kernel32.GetFileInformationByHandleEx.implementation = query_impl
    with backend:
        root = backend.open_root("X:\\")
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend._stream_inventory(root)

    assert exc_info.value.code == "observation_failed"


@pytest.mark.parametrize(
    ("streams", "object_kind", "size_bytes", "expected_code"),
    (
        ((("::$DATA", 4, 4096),), "regular_file", 4, None),
        ((("secret:$DATA", 4, 4096),), "regular_file", 4, "unexpected_entry_type"),
        ((("::$DATA", 5, 4096),), "regular_file", 4, "unexpected_entry_type"),
        ((("::$DATA", -1, 0),), "regular_file", 4, "observation_failed"),
        (((), "directory", 0, None)),
        ((("::$DATA", 0, 0),), "directory", 0, "unexpected_entry_type"),
    ),
)
def test_stream_contract_is_exact(
    streams: tuple[tuple[str, int, int], ...],
    object_kind: str,
    size_bytes: int,
    expected_code: str | None,
) -> None:
    module = _load_module()

    if expected_code is None:
        module._validate_windows_streams(
            streams,
            object_kind=object_kind,
            size_bytes=size_bytes,
        )
        return
    with pytest.raises(module.WindowsHeldHandleError) as exc_info:
        module._validate_windows_streams(
            streams,
            object_kind=object_kind,
            size_bytes=size_bytes,
        )
    assert exc_info.value.code == expected_code


def test_open_root_rejects_non_fixed_volume_before_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    create_calls = 0
    kernel32.GetDriveTypeW.implementation = lambda _root: 4

    def forbidden_create(*_args) -> int:
        nonlocal create_calls
        create_calls += 1
        raise AssertionError("non-fixed volume reached CreateFileW")

    kernel32.CreateFileW.implementation = forbidden_create
    module, backend = _backend(monkeypatch, kernel32)

    with pytest.raises(module.WindowsHeldHandleError) as exc_info:
        backend.open_root("X:\\")

    assert exc_info.value.code == "unsupported_filesystem"
    assert create_calls == 0


def test_hash_file_maps_native_sharing_failure_with_internal_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)

    def fail_seek(*_args) -> int:
        ctypes.set_last_error(backend._ERROR_SHARING_VIOLATION)
        return 0

    kernel32.SetFilePointerEx.implementation = fail_seek
    expected = module.WindowsDirectoryEntry(
        "member",
        0,
        "ntfs_file_index_64",
        7,
    )
    with backend:
        root = backend.open_root("X:\\")
        member = backend.open_by_id(root, expected, directory=False)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.hash_file(member)

    assert exc_info.value.code == "sharing_conflict"
    assert isinstance(exc_info.value.__cause__, OSError)


@pytest.mark.parametrize(
    ("failure_stage", "native_error", "expected_code"),
    (
        ("seek", 32, "sharing_conflict"),
        ("read", 5, "observation_failed"),
    ),
)
def test_read_file_bounded_preserves_native_error_translation(
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
    native_error: int,
    expected_code: str,
) -> None:
    kernel32 = _Kernel32()
    module, backend = _backend(monkeypatch, kernel32)

    def fail_native(*_args) -> int:
        ctypes.set_last_error(native_error)
        return 0

    if failure_stage == "seek":
        kernel32.SetFilePointerEx.implementation = fail_native
    else:
        kernel32.ReadFile.implementation = fail_native
    with backend:
        member = _open_test_member(module, backend)
        with pytest.raises(module.WindowsHeldHandleError) as exc_info:
            backend.read_file_bounded(member, maximum_bytes=1)

    assert exc_info.value.code == expected_code
    assert str(exc_info.value) == module._ERROR_MESSAGES[expected_code]
    assert isinstance(exc_info.value.__cause__, OSError)


@pytest.mark.skipif(os.name != "nt", reason="native share modes are Windows-only")
def test_native_open_by_id_maps_incompatible_writer_as_sharing_conflict(
    tmp_path: Path,
) -> None:
    module = _load_module()
    target = tmp_path / "leased.bin"
    target.write_bytes(b"leased")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int32
    exclusive = kernel32.CreateFileW(str(target), 0x80000000, 0, None, 3, 0, None)
    invalid = ctypes.c_void_p(-1).value
    if exclusive is None or exclusive == invalid:
        pytest.skip(f"exclusive fixture unavailable: {ctypes.get_last_error()}")

    try:
        with module.WindowsHeldHandleBackend() as backend:
            volume = backend.open_root(f"{tmp_path.drive}\\")
            filesystem = backend.volume_filesystem(volume)
            parent = volume
            for component in tmp_path.parts[1:]:
                entries = backend.enumerate_directory(parent, filesystem)
                entry = next(item for item in entries if item.name == component)
                parent = backend.open_by_id(volume, entry, directory=True)
            entries = backend.enumerate_directory(parent, filesystem)
            target_entry = next(item for item in entries if item.name == target.name)

            with pytest.raises(module.WindowsHeldHandleError) as exc_info:
                backend.open_by_id(volume, target_entry, directory=False)

        assert exc_info.value.code == "sharing_conflict"
        assert isinstance(exc_info.value.__cause__, OSError)
    finally:
        assert kernel32.CloseHandle(exclusive)


@pytest.mark.skipif(os.name != "nt", reason="native held-handle reads are Windows-only")
def test_native_read_file_bounded_proves_eof_and_enforces_cap(
    tmp_path: Path,
) -> None:
    module = _load_module()
    payload_65 = bytes(range(65))
    payload_67 = bytes(range(67))
    (tmp_path / "bounded-65.bin").write_bytes(payload_65)
    (tmp_path / "bounded-67.bin").write_bytes(payload_67)

    with module.WindowsHeldHandleBackend() as backend:
        volume = backend.open_root(f"{tmp_path.drive}\\")
        filesystem = backend.volume_filesystem(volume)
        parent = volume
        for component in tmp_path.parts[1:]:
            entries = backend.enumerate_directory(parent, filesystem)
            entry = next(item for item in entries if item.name == component)
            parent = backend.open_by_id(volume, entry, directory=True)
        entries = backend.enumerate_directory(parent, filesystem)
        entry_by_name = {entry.name: entry for entry in entries}
        member_65 = backend.open_by_id(
            volume,
            entry_by_name["bounded-65.bin"],
            directory=False,
        )
        member_67 = backend.open_by_id(
            volume,
            entry_by_name["bounded-67.bin"],
            directory=False,
        )

        assert backend.read_file_bounded(member_65, maximum_bytes=66) == (
            payload_65,
            True,
        )
        assert backend.read_file_bounded(member_67, maximum_bytes=66) == (
            payload_67[:66],
            False,
        )


@pytest.mark.skipif(
    os.name != "nt",
    reason="native security descriptors are Windows-only",
)
def test_native_read_security_descriptor_is_detached_and_self_relative(
    tmp_path: Path,
) -> None:
    module = _load_module()
    target = tmp_path / "security-descriptor-witness.bin"
    target.write_bytes(b"witness")

    with module.WindowsHeldHandleBackend(access_profile="security_read") as backend:
        volume = backend.open_root(f"{tmp_path.drive}\\")
        filesystem = backend.volume_filesystem(volume)
        parent = volume
        for component in tmp_path.parts[1:]:
            entries = backend.enumerate_directory(parent, filesystem)
            entry = next(item for item in entries if item.name == component)
            parent = backend.open_by_id(volume, entry, directory=True)
        entries = backend.enumerate_directory(parent, filesystem)
        target_entry = next(item for item in entries if item.name == target.name)
        member = backend.open_by_id(volume, target_entry, directory=False)

        descriptor = backend.read_security_descriptor(member)

    assert type(descriptor) is bytes
    assert len(descriptor) >= 20
    assert descriptor[0] == 1
    control = int.from_bytes(descriptor[2:4], "little")
    assert control & 0x8000
    descriptor_buffer = ctypes.create_string_buffer(descriptor)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.IsValidSecurityDescriptor.argtypes = [ctypes.c_void_p]
    advapi32.IsValidSecurityDescriptor.restype = ctypes.c_int32
    assert advapi32.IsValidSecurityDescriptor(
        ctypes.cast(descriptor_buffer, ctypes.c_void_p)
    )


def test_shared_module_imports_only_standard_library_without_dynamic_escape() -> None:
    module = _load_module()
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    allowed_roots = {
        "__future__",
        "dataclasses",
        "hashlib",
        "json",
        "os",
        "typing",
        "ctypes",
    }
    imported_roots: set[str] = set()
    dynamic_calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                dynamic_calls.append("__import__")
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            ):
                dynamic_calls.append("import_module")

    assert imported_roots <= allowed_roots
    assert imported_roots.isdisjoint({"api", "cli", "steps"})
    assert dynamic_calls == []


def test_shared_module_import_does_not_load_win32_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_name = "steps.common.windows_held_handle"
    previous = sys.modules.pop(module_name, None)

    def forbidden_windll(*_args, **_kwargs):
        raise AssertionError("shared module loaded Win32 capability during import")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden_windll)
    try:
        module = importlib.import_module(module_name)
        assert module.__all__ == (
            "WindowsHeldHandleError",
            "WindowsDirectoryEntry",
            "WindowsObjectSnapshot",
            "WindowsHeldHandleBackend",
        )
    finally:
        sys.modules.pop(module_name, None)
        if previous is not None:
            sys.modules[module_name] = previous
