"""Projection-neutral Windows held-handle access for GoodQ authority readers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from typing import Any


__all__ = (
    "WindowsHeldHandleError",
    "WindowsDirectoryEntry",
    "WindowsObjectSnapshot",
    "WindowsHeldHandleBackend",
)

_ERROR_MESSAGES = {
    "unsupported_platform": "Windows held-handle access is unsupported",
    "unsupported_filesystem": "Windows held-handle storage is unsupported",
    "redirected_boundary": "Windows held-handle boundary is redirected",
    "unexpected_entry_type": "Windows held-handle entry type is unsupported",
    "duplicate_identity": "Windows held-handle identity is ambiguous",
    "sharing_conflict": "Windows held-handle target is not quiescent",
    "observation_raced": "Windows held-handle state changed during observation",
    "observation_failed": "Windows held-handle observation failed",
}


class WindowsHeldHandleError(RuntimeError):
    """Path-free held-handle failure."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        try:
            message = _ERROR_MESSAGES[code]
        except (KeyError, TypeError) as exc:
            raise ValueError("Unknown Windows held-handle error code") from exc
        super().__init__(message)
        object.__setattr__(self, "_code", code)

    @property
    def code(self) -> str:
        return self._code

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"code", "_code"} and hasattr(self, "_code"):
            raise AttributeError("Windows held-handle error code is immutable")
        object.__setattr__(self, name, value)


def _raise(code: str, cause: BaseException | None = None) -> None:
    error = WindowsHeldHandleError(code)
    if cause is None:
        raise error
    raise error from cause


def _windows_filetime_to_ns(value: int) -> int:
    epoch = WindowsHeldHandleBackend._FILETIME_UNIX_EPOCH
    if isinstance(value, bool) or not isinstance(value, int) or value < epoch:
        _raise("observation_failed")
    nanoseconds = (value - epoch) * 100
    if nanoseconds > (1 << 63) - 1:
        _raise("observation_failed")
    return nanoseconds


def _validate_windows_streams(
    streams: tuple[tuple[str, int, int], ...],
    *,
    object_kind: str,
    size_bytes: int,
) -> None:
    if any(
        stream_size < 0 or allocation_size < 0
        for _, stream_size, allocation_size in streams
    ):
        _raise("observation_failed")
    if object_kind == "directory":
        if streams:
            _raise("unexpected_entry_type")
        return
    if (
        len(streams) != 1
        or streams[0][0] != "::$DATA"
        or streams[0][1] != size_bytes
    ):
        _raise("unexpected_entry_type")


@dataclass(frozen=True)
class WindowsDirectoryEntry:
    """One directory entry selected by physical file identity."""

    name: str
    attributes: int
    file_id_kind: str
    file_id: int | bytes

    @property
    def is_directory(self) -> bool:
        return bool(self.attributes & 0x10)

    @property
    def is_reparse(self) -> bool:
        return bool(self.attributes & 0x400)

    @property
    def is_device(self) -> bool:
        return bool(self.attributes & 0x40)


@dataclass(frozen=True)
class WindowsObjectSnapshot:
    """Stable physical object state observed from one held handle."""

    volume_serial: int
    file_id_kind: str
    file_id: int | bytes
    object_kind: str
    size_bytes: int
    mtime_ns: int | None
    allocation_size: int
    link_count: int
    attributes: int
    reparse_tag: int
    last_write_ticks: int
    change_ticks: int
    streams: tuple[tuple[str, int, int], ...]

    @property
    def identity_projection(self) -> dict[str, str]:
        rendered_file_id = (
            f"{self.file_id:016x}"
            if isinstance(self.file_id, int)
            else self.file_id.hex()
        )
        return {
            "file_id": rendered_file_id,
            "file_id_kind": self.file_id_kind,
            "object_kind": self.object_kind,
            "schema": "goodq.windows-file-identity.v1",
            "volume_serial": f"{self.volume_serial:016x}",
        }

    @property
    def identity_json(self) -> str:
        return json.dumps(
            self.identity_projection,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )


class _WindowsHandleToken:
    __slots__ = (
        "_cleanup_error",
        "_owner",
        "_raw",
        "_live",
        "_security_readable",
    )

    def __init__(
        self,
        owner: WindowsHeldHandleBackend,
        raw: object | None,
        *,
        security_readable: bool,
    ) -> None:
        self._cleanup_error = WindowsHeldHandleError("observation_failed")
        self._owner = owner
        self._raw = raw
        self._live = True
        self._security_readable = security_readable


class WindowsHeldHandleBackend:
    """Own Windows file handles for one bounded observation."""

    _DRIVE_FIXED = 3
    _FILE_LIST_DIRECTORY = 0x0001
    _FILE_READ_DATA = 0x0001
    _FILE_READ_ATTRIBUTES = 0x0080
    _READ_CONTROL = 0x00020000
    _FILE_SHARE_READ = 0x00000001
    _OPEN_EXISTING = 3
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
    _FILE_SUPPORTS_OPEN_BY_FILE_ID = 0x01000000
    _FILE_ATTRIBUTE_DEVICE = 0x40
    _FILE_ATTRIBUTE_DIRECTORY = 0x10
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x400
    _ERROR_INVALID_FUNCTION = 1
    _ERROR_FILE_NOT_FOUND = 2
    _ERROR_PATH_NOT_FOUND = 3
    _ERROR_SHARING_VIOLATION = 32
    _ERROR_NOT_SUPPORTED = 50
    _ERROR_INVALID_PARAMETER = 87
    _ERROR_NO_MORE_FILES = 18
    _ERROR_HANDLE_EOF = 38
    _ERROR_INSUFFICIENT_BUFFER = 122
    _ERROR_MORE_DATA = 234
    _FILE_BEGIN = 0
    _FILETIME_UNIX_EPOCH = 116444736000000000
    _SE_FILE_OBJECT = 1
    _OWNER_SECURITY_INFORMATION = 0x00000001
    _GROUP_SECURITY_INFORMATION = 0x00000002
    _DACL_SECURITY_INFORMATION = 0x00000004
    _SECURITY_DESCRIPTOR_REVISION = 1
    _SE_SELF_RELATIVE = 0x8000
    _SECURITY_DESCRIPTOR_MIN_LENGTH = 20
    _SECURITY_DESCRIPTOR_MAX_LENGTH = 131072

    _FILE_BASIC_INFO = 0
    _FILE_STANDARD_INFO = 1
    _FILE_STREAM_INFO = 7
    _FILE_ATTRIBUTE_TAG_INFO = 9
    _FILE_ID_BOTH_DIRECTORY_INFO = 10
    _FILE_ID_BOTH_DIRECTORY_RESTART_INFO = 11
    _FILE_ID_INFO = 18
    _FILE_ID_EXTD_DIRECTORY_INFO = 19
    _FILE_ID_EXTD_DIRECTORY_RESTART_INFO = 20

    _FILE_ID_TYPE = 0
    _EXTENDED_FILE_ID_TYPE = 2

    def __init__(self, *, access_profile: str = "observation") -> None:
        if type(access_profile) is not str or access_profile not in {
            "observation",
            "security_read",
        }:
            raise ValueError("Unsupported Windows held-handle access profile")
        if os.name != "nt":
            _raise("unsupported_platform")
        import ctypes

        self._ctypes = ctypes
        self._access_profile = access_profile
        DWORD = ctypes.c_uint32
        WORD = ctypes.c_uint16
        BOOL = ctypes.c_int32
        BYTE = ctypes.c_ubyte
        BOOLEAN = ctypes.c_ubyte
        LARGE_INTEGER = ctypes.c_int64
        ULONGLONG = ctypes.c_uint64
        HANDLE = ctypes.c_void_p

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", DWORD), ("dwHighDateTime", DWORD)]

        class FILE_ID_128(ctypes.Structure):
            _fields_ = [("Identifier", BYTE * 16)]

        class FILE_ID_INFO_STRUCT(ctypes.Structure):
            _fields_ = [("VolumeSerialNumber", ULONGLONG), ("FileId", FILE_ID_128)]

        class FILE_BASIC_INFO_STRUCT(ctypes.Structure):
            _fields_ = [
                ("CreationTime", LARGE_INTEGER),
                ("LastAccessTime", LARGE_INTEGER),
                ("LastWriteTime", LARGE_INTEGER),
                ("ChangeTime", LARGE_INTEGER),
                ("FileAttributes", DWORD),
            ]

        class FILE_STANDARD_INFO_STRUCT(ctypes.Structure):
            _fields_ = [
                ("AllocationSize", LARGE_INTEGER),
                ("EndOfFile", LARGE_INTEGER),
                ("NumberOfLinks", DWORD),
                ("DeletePending", BOOLEAN),
                ("Directory", BOOLEAN),
            ]

        class FILE_ATTRIBUTE_TAG_INFO_STRUCT(ctypes.Structure):
            _fields_ = [("FileAttributes", DWORD), ("ReparseTag", DWORD)]

        class BY_HANDLE_FILE_INFORMATION_STRUCT(ctypes.Structure):
            _fields_ = [
                ("dwFileAttributes", DWORD),
                ("ftCreationTime", FILETIME),
                ("ftLastAccessTime", FILETIME),
                ("ftLastWriteTime", FILETIME),
                ("dwVolumeSerialNumber", DWORD),
                ("nFileSizeHigh", DWORD),
                ("nFileSizeLow", DWORD),
                ("nNumberOfLinks", DWORD),
                ("nFileIndexHigh", DWORD),
                ("nFileIndexLow", DWORD),
            ]

        class FILE_ID_UNION(ctypes.Union):
            _fields_ = [
                ("FileId", LARGE_INTEGER),
                ("ObjectId", BYTE * 16),
                ("ExtendedFileId", FILE_ID_128),
            ]

        class FILE_ID_DESCRIPTOR_STRUCT(ctypes.Structure):
            _anonymous_ = ("Identifier",)
            _fields_ = [
                ("dwSize", DWORD),
                ("Type", ctypes.c_int32),
                ("Identifier", FILE_ID_UNION),
            ]

        class FILE_ID_BOTH_DIR_INFO_STRUCT(ctypes.Structure):
            _fields_ = [
                ("NextEntryOffset", DWORD),
                ("FileIndex", DWORD),
                ("CreationTime", LARGE_INTEGER),
                ("LastAccessTime", LARGE_INTEGER),
                ("LastWriteTime", LARGE_INTEGER),
                ("ChangeTime", LARGE_INTEGER),
                ("EndOfFile", LARGE_INTEGER),
                ("AllocationSize", LARGE_INTEGER),
                ("FileAttributes", DWORD),
                ("FileNameLength", DWORD),
                ("EaSize", DWORD),
                ("ShortNameLength", ctypes.c_byte),
                ("ShortName", ctypes.c_wchar * 12),
                ("FileId", LARGE_INTEGER),
                ("FileName", ctypes.c_wchar * 1),
            ]

        class FILE_ID_EXTD_DIR_INFO_STRUCT(ctypes.Structure):
            _fields_ = [
                ("NextEntryOffset", DWORD),
                ("FileIndex", DWORD),
                ("CreationTime", LARGE_INTEGER),
                ("LastAccessTime", LARGE_INTEGER),
                ("LastWriteTime", LARGE_INTEGER),
                ("ChangeTime", LARGE_INTEGER),
                ("EndOfFile", LARGE_INTEGER),
                ("AllocationSize", LARGE_INTEGER),
                ("FileAttributes", DWORD),
                ("FileNameLength", DWORD),
                ("EaSize", DWORD),
                ("ReparsePointTag", DWORD),
                ("FileId", FILE_ID_128),
                ("FileName", ctypes.c_wchar * 1),
            ]

        class FILE_STREAM_INFO_STRUCT(ctypes.Structure):
            _fields_ = [
                ("NextEntryOffset", DWORD),
                ("StreamNameLength", DWORD),
                ("StreamSize", LARGE_INTEGER),
                ("StreamAllocationSize", LARGE_INTEGER),
                ("StreamName", ctypes.c_wchar * 1),
            ]

        self._DWORD = DWORD
        self._WORD = WORD
        self._HANDLE = HANDLE
        self._FILE_ID_128 = FILE_ID_128
        self._FILE_ID_INFO_STRUCT = FILE_ID_INFO_STRUCT
        self._FILE_BASIC_INFO_STRUCT = FILE_BASIC_INFO_STRUCT
        self._FILE_STANDARD_INFO_STRUCT = FILE_STANDARD_INFO_STRUCT
        self._FILE_ATTRIBUTE_TAG_INFO_STRUCT = FILE_ATTRIBUTE_TAG_INFO_STRUCT
        self._BY_HANDLE_FILE_INFORMATION_STRUCT = BY_HANDLE_FILE_INFORMATION_STRUCT
        self._FILE_ID_DESCRIPTOR_STRUCT = FILE_ID_DESCRIPTOR_STRUCT
        self._FILE_ID_BOTH_DIR_INFO_STRUCT = FILE_ID_BOTH_DIR_INFO_STRUCT
        self._FILE_ID_EXTD_DIR_INFO_STRUCT = FILE_ID_EXTD_DIR_INFO_STRUCT
        self._FILE_STREAM_INFO_STRUCT = FILE_STREAM_INFO_STRUCT

        expected_abi = {
            "both_name": (FILE_ID_BOTH_DIR_INFO_STRUCT.FileName.offset, 104),
            "both_size": (ctypes.sizeof(FILE_ID_BOTH_DIR_INFO_STRUCT), 112),
            "extd_name": (FILE_ID_EXTD_DIR_INFO_STRUCT.FileName.offset, 88),
            "extd_size": (ctypes.sizeof(FILE_ID_EXTD_DIR_INFO_STRUCT), 96),
            "stream_name": (FILE_STREAM_INFO_STRUCT.StreamName.offset, 24),
            "stream_size": (ctypes.sizeof(FILE_STREAM_INFO_STRUCT), 32),
            "descriptor_size": (ctypes.sizeof(FILE_ID_DESCRIPTOR_STRUCT), 24),
            "id_info_size": (ctypes.sizeof(FILE_ID_INFO_STRUCT), 24),
            "basic_size": (ctypes.sizeof(FILE_BASIC_INFO_STRUCT), 40),
            "standard_size": (ctypes.sizeof(FILE_STANDARD_INFO_STRUCT), 24),
            "tag_size": (ctypes.sizeof(FILE_ATTRIBUTE_TAG_INFO_STRUCT), 8),
            "by_handle_size": (ctypes.sizeof(BY_HANDLE_FILE_INFORMATION_STRUCT), 52),
        }
        if any(actual != expected for actual, expected in expected_abi.values()):
            _raise("unsupported_platform")

        self._advapi32 = None
        try:
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel32.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
            self._kernel32.GetDriveTypeW.restype = ctypes.c_uint32
            self._kernel32.CreateFileW.argtypes = [
                ctypes.c_wchar_p,
                self._DWORD,
                self._DWORD,
                ctypes.c_void_p,
                self._DWORD,
                self._DWORD,
                self._HANDLE,
            ]
            self._kernel32.CreateFileW.restype = self._HANDLE
            self._kernel32.GetVolumeInformationByHandleW.argtypes = [
                self._HANDLE,
                ctypes.c_wchar_p,
                self._DWORD,
                ctypes.POINTER(self._DWORD),
                ctypes.POINTER(self._DWORD),
                ctypes.POINTER(self._DWORD),
                ctypes.c_wchar_p,
                self._DWORD,
            ]
            self._kernel32.GetVolumeInformationByHandleW.restype = ctypes.c_int32
            self._kernel32.GetFileInformationByHandleEx.argtypes = [
                HANDLE,
                ctypes.c_int32,
                ctypes.c_void_p,
                DWORD,
            ]
            self._kernel32.GetFileInformationByHandleEx.restype = ctypes.c_int32
            self._kernel32.GetFileInformationByHandle.argtypes = [
                HANDLE,
                ctypes.POINTER(BY_HANDLE_FILE_INFORMATION_STRUCT),
            ]
            self._kernel32.GetFileInformationByHandle.restype = ctypes.c_int32
            self._kernel32.OpenFileById.argtypes = [
                HANDLE,
                ctypes.POINTER(FILE_ID_DESCRIPTOR_STRUCT),
                DWORD,
                DWORD,
                ctypes.c_void_p,
                DWORD,
            ]
            self._kernel32.OpenFileById.restype = HANDLE
            self._kernel32.SetFilePointerEx.argtypes = [
                HANDLE,
                LARGE_INTEGER,
                ctypes.c_void_p,
                DWORD,
            ]
            self._kernel32.SetFilePointerEx.restype = ctypes.c_int32
            self._kernel32.ReadFile.argtypes = [
                HANDLE,
                ctypes.c_void_p,
                DWORD,
                ctypes.POINTER(DWORD),
                ctypes.c_void_p,
            ]
            self._kernel32.ReadFile.restype = ctypes.c_int32
            self._kernel32.CloseHandle.argtypes = [self._HANDLE]
            self._kernel32.CloseHandle.restype = ctypes.c_int32
            if access_profile == "security_read":
                self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
                void_pointer = ctypes.c_void_p
                pointer_to_void = ctypes.POINTER(void_pointer)
                self._advapi32.GetSecurityInfo.argtypes = [
                    void_pointer,
                    ctypes.c_int32,
                    DWORD,
                    pointer_to_void,
                    pointer_to_void,
                    pointer_to_void,
                    pointer_to_void,
                    pointer_to_void,
                ]
                self._advapi32.GetSecurityInfo.restype = DWORD
                self._advapi32.IsValidSecurityDescriptor.argtypes = [void_pointer]
                self._advapi32.IsValidSecurityDescriptor.restype = BOOL
                self._advapi32.GetSecurityDescriptorControl.argtypes = [
                    void_pointer,
                    ctypes.POINTER(WORD),
                    ctypes.POINTER(DWORD),
                ]
                self._advapi32.GetSecurityDescriptorControl.restype = BOOL
                self._advapi32.GetSecurityDescriptorLength.argtypes = [void_pointer]
                self._advapi32.GetSecurityDescriptorLength.restype = DWORD
                self._kernel32.LocalFree.argtypes = [void_pointer]
                self._kernel32.LocalFree.restype = void_pointer
        except (AttributeError, OSError) as exc:
            _raise("unsupported_platform", exc)
        self._invalid_handle = ctypes.c_void_p(-1).value
        self._handles: list[_WindowsHandleToken] = []
        self._reservation_error = WindowsHeldHandleError("observation_failed")
        self._exited = False

    def _last_error(self) -> int:
        return int(self._ctypes.get_last_error())

    def _cause(self, error: int) -> OSError:
        try:
            return self._ctypes.WinError(error)
        except Exception:
            return OSError(error, "Win32 call failed")

    def _raise_call_error(
        self,
        error: int,
        *,
        disappeared: bool = False,
        unsupported_capability: bool = False,
    ) -> None:
        cause = self._cause(error)
        if error == self._ERROR_SHARING_VIOLATION:
            _raise("sharing_conflict", cause)
        if disappeared and error in {
            self._ERROR_FILE_NOT_FOUND,
            self._ERROR_PATH_NOT_FOUND,
        }:
            _raise("observation_raced", cause)
        if unsupported_capability and error in {
            self._ERROR_INVALID_FUNCTION,
            self._ERROR_NOT_SUPPORTED,
            self._ERROR_INVALID_PARAMETER,
        }:
            _raise("unsupported_filesystem", cause)
        _raise("observation_failed", cause)

    def _value(self, handle: object) -> int | None:
        if handle is None:
            return None
        if isinstance(handle, int):
            return handle
        return getattr(handle, "value", None)

    def _failed_handle(self, handle: object) -> bool:
        value = self._value(handle)
        return value is None or value == self._invalid_handle

    def _reserve(
        self,
        *,
        security_readable: bool = False,
    ) -> _WindowsHandleToken:
        if self._exited:
            _raise("observation_failed")
        token: _WindowsHandleToken | None = None
        failed = False
        try:
            token = _WindowsHandleToken(
                self,
                None,
                security_readable=security_readable,
            )
            self._handles.append(token)
        except Exception:
            failed = True
        if failed:
            self._reservation_error.__cause__ = None
            self._reservation_error.__context__ = None
            self._reservation_error.__traceback__ = None
            self._reservation_error.__suppress_context__ = True
            raise self._reservation_error from None
        assert token is not None
        return token

    def _discard_reservation(self, token: _WindowsHandleToken) -> None:
        token._live = False
        self._handles.remove(token)

    def _raw(self, token: object) -> int:
        if (
            self._exited
            or not isinstance(token, _WindowsHandleToken)
            or token._owner is not self
            or not token._live
            or token not in self._handles
        ):
            _raise("observation_failed")
        value = self._value(token._raw)
        if value is None or value == self._invalid_handle:
            _raise("observation_failed")
        return int(value)

    def open_root(self, root: str) -> object:
        if self._exited:
            _raise("observation_failed")
        if self._kernel32.GetDriveTypeW(root) != self._DRIVE_FIXED:
            _raise("unsupported_filesystem")
        token = self._reserve()
        try:
            handle = self._kernel32.CreateFileW(
                root,
                self._FILE_LIST_DIRECTORY | self._FILE_READ_ATTRIBUTES,
                self._FILE_SHARE_READ,
                None,
                self._OPEN_EXISTING,
                self._FILE_FLAG_OPEN_REPARSE_POINT | self._FILE_FLAG_BACKUP_SEMANTICS,
                None,
            )
        except BaseException:
            self._discard_reservation(token)
            raise
        token._raw = handle
        if self._failed_handle(handle):
            last_error = self._last_error()
            self._discard_reservation(token)
            self._raise_call_error(last_error)
        return token

    def volume_filesystem(self, handle: object) -> str:
        raw = self._raw(handle)
        volume_name = self._ctypes.create_unicode_buffer(261)
        filesystem_name = self._ctypes.create_unicode_buffer(64)
        serial = self._DWORD()
        max_component = self._DWORD()
        flags = self._DWORD()
        if not self._kernel32.GetVolumeInformationByHandleW(
            raw,
            volume_name,
            len(volume_name),
            self._ctypes.byref(serial),
            self._ctypes.byref(max_component),
            self._ctypes.byref(flags),
            filesystem_name,
            len(filesystem_name),
        ):
            self._raise_call_error(
                self._last_error(),
                unsupported_capability=True,
            )
        filesystem = filesystem_name.value
        if filesystem not in {"NTFS", "ReFS"}:
            _raise("unsupported_filesystem")
        if not (flags.value & self._FILE_SUPPORTS_OPEN_BY_FILE_ID):
            _raise("unsupported_filesystem")
        return filesystem

    def _aligned_buffer(self, size: int) -> tuple[Any, int]:
        count = (size + 7) // 8
        value = (self._ctypes.c_uint64 * count)()
        return value, self._ctypes.sizeof(value)

    def _query(self, handle: object, info_class: int, structure: type[Any]) -> Any:
        raw = self._raw(handle)
        value = structure()
        if not self._kernel32.GetFileInformationByHandleEx(
            raw,
            info_class,
            self._ctypes.byref(value),
            self._ctypes.sizeof(value),
        ):
            self._raise_call_error(
                self._last_error(),
                unsupported_capability=True,
            )
        return value

    def _by_handle(self, handle: object) -> Any:
        raw = self._raw(handle)
        value = self._BY_HANDLE_FILE_INFORMATION_STRUCT()
        if not self._kernel32.GetFileInformationByHandle(
            raw,
            self._ctypes.byref(value),
        ):
            self._raise_call_error(self._last_error())
        return value

    def enumerate_directory(
        self,
        handle: object,
        filesystem: str,
    ) -> tuple[WindowsDirectoryEntry, ...]:
        raw = self._raw(handle)
        if filesystem == "NTFS":
            structure = self._FILE_ID_BOTH_DIR_INFO_STRUCT
            file_id_kind = "ntfs_file_index_64"
            restart_class = self._FILE_ID_BOTH_DIRECTORY_RESTART_INFO
            continuation_class = self._FILE_ID_BOTH_DIRECTORY_INFO
        elif filesystem == "ReFS":
            structure = self._FILE_ID_EXTD_DIR_INFO_STRUCT
            file_id_kind = "refs_file_id_128"
            restart_class = self._FILE_ID_EXTD_DIRECTORY_RESTART_INFO
            continuation_class = self._FILE_ID_EXTD_DIRECTORY_INFO
        else:
            _raise("unsupported_filesystem")

        entries: list[WindowsDirectoryEntry] = []
        first = True
        while True:
            buffer, buffer_size = self._aligned_buffer(64 * 1024)
            info_class = restart_class if first else continuation_class
            first = False
            if not self._kernel32.GetFileInformationByHandleEx(
                raw,
                info_class,
                self._ctypes.byref(buffer),
                buffer_size,
            ):
                error = self._last_error()
                if error == self._ERROR_NO_MORE_FILES:
                    break
                self._raise_call_error(error, unsupported_capability=True)

            offset = 0
            while True:
                if offset % 8 or offset + self._ctypes.sizeof(structure) > buffer_size:
                    _raise("observation_failed")
                try:
                    record = structure.from_buffer(buffer, offset)
                except (TypeError, ValueError) as exc:
                    _raise("observation_failed", exc)
                name_length = int(record.FileNameLength)
                if name_length % 2 or name_length <= 0:
                    _raise("observation_failed")
                record_limit = (
                    offset + int(record.NextEntryOffset)
                    if record.NextEntryOffset
                    else buffer_size
                )
                name_end = offset + structure.FileName.offset + name_length
                if name_end > record_limit or name_end > buffer_size:
                    _raise("observation_failed")
                try:
                    name = self._ctypes.string_at(
                        self._ctypes.addressof(buffer)
                        + offset
                        + structure.FileName.offset,
                        name_length,
                    ).decode("utf-16-le", "strict")
                except UnicodeDecodeError as exc:
                    _raise("observation_failed", exc)
                if name not in {".", ".."}:
                    file_id: int | bytes
                    if filesystem == "NTFS":
                        file_id = int(record.FileId) & ((1 << 64) - 1)
                    else:
                        file_id = bytes(record.FileId.Identifier)
                    if file_id == 0 or file_id == b"\x00" * 16:
                        _raise("duplicate_identity")
                    entries.append(
                        WindowsDirectoryEntry(
                            name=name,
                            attributes=int(record.FileAttributes),
                            file_id_kind=file_id_kind,
                            file_id=file_id,
                        )
                    )
                next_offset = int(record.NextEntryOffset)
                if next_offset == 0:
                    break
                if next_offset % 8 or next_offset < structure.FileName.offset + name_length:
                    _raise("observation_failed")
                offset += next_offset
                if offset >= buffer_size:
                    _raise("observation_failed")

        entries.sort(key=lambda item: (item.name.casefold(), item.name))
        return tuple(entries)

    def _stream_inventory(
        self,
        handle: object,
    ) -> tuple[tuple[str, int, int], ...]:
        raw = self._raw(handle)
        size = 64 * 1024
        while size <= 16 * 1024 * 1024:
            buffer, buffer_size = self._aligned_buffer(size)
            if self._kernel32.GetFileInformationByHandleEx(
                raw,
                self._FILE_STREAM_INFO,
                self._ctypes.byref(buffer),
                buffer_size,
            ):
                break
            error = self._last_error()
            if error == self._ERROR_HANDLE_EOF:
                return ()
            if error in {self._ERROR_MORE_DATA, self._ERROR_INSUFFICIENT_BUFFER}:
                size *= 2
                continue
            self._raise_call_error(error, unsupported_capability=True)
        else:
            _raise("observation_failed")

        structure = self._FILE_STREAM_INFO_STRUCT
        streams: list[tuple[str, int, int]] = []
        offset = 0
        while True:
            if offset % 8 or offset + self._ctypes.sizeof(structure) > buffer_size:
                _raise("observation_failed")
            try:
                record = structure.from_buffer(buffer, offset)
            except (TypeError, ValueError) as exc:
                _raise("observation_failed", exc)
            name_length = int(record.StreamNameLength)
            if name_length % 2 or name_length <= 0:
                _raise("observation_failed")
            record_limit = (
                offset + int(record.NextEntryOffset)
                if record.NextEntryOffset
                else buffer_size
            )
            name_end = offset + structure.StreamName.offset + name_length
            if name_end > record_limit or name_end > buffer_size:
                _raise("observation_failed")
            try:
                name = self._ctypes.string_at(
                    self._ctypes.addressof(buffer)
                    + offset
                    + structure.StreamName.offset,
                    name_length,
                ).decode("utf-16-le", "strict")
            except UnicodeDecodeError as exc:
                _raise("observation_failed", exc)
            streams.append(
                (
                    name,
                    int(record.StreamSize),
                    int(record.StreamAllocationSize),
                )
            )
            next_offset = int(record.NextEntryOffset)
            if next_offset == 0:
                break
            if next_offset % 8 or next_offset < structure.StreamName.offset + name_length:
                _raise("observation_failed")
            offset += next_offset
            if offset >= buffer_size:
                _raise("observation_failed")
        return tuple(streams)

    def snapshot(
        self,
        handle: object,
        *,
        filesystem: str,
        expected: WindowsDirectoryEntry | None,
        object_kind: str,
        require_stream_contract: bool,
    ) -> WindowsObjectSnapshot:
        attribute = self._query(
            handle,
            self._FILE_ATTRIBUTE_TAG_INFO,
            self._FILE_ATTRIBUTE_TAG_INFO_STRUCT,
        )
        attributes = int(attribute.FileAttributes)
        if attributes & self._FILE_ATTRIBUTE_DEVICE:
            _raise("unexpected_entry_type")
        if (
            attributes & self._FILE_ATTRIBUTE_REPARSE_POINT
            or int(attribute.ReparseTag) != 0
        ):
            _raise("redirected_boundary")
        identity = self._query(
            handle,
            self._FILE_ID_INFO,
            self._FILE_ID_INFO_STRUCT,
        )
        basic = self._query(
            handle,
            self._FILE_BASIC_INFO,
            self._FILE_BASIC_INFO_STRUCT,
        )
        standard = self._query(
            handle,
            self._FILE_STANDARD_INFO,
            self._FILE_STANDARD_INFO_STRUCT,
        )
        by_handle = self._by_handle(handle)

        is_directory = bool(standard.Directory)
        if is_directory != (object_kind == "directory"):
            _raise("observation_raced" if expected is not None else "unexpected_entry_type")
        if bool(attributes & self._FILE_ATTRIBUTE_DIRECTORY) != is_directory:
            _raise("observation_raced")
        if bool(standard.DeletePending):
            _raise("observation_raced")

        volume_serial = int(identity.VolumeSerialNumber)
        if volume_serial == 0:
            _raise("duplicate_identity")
        if filesystem == "NTFS":
            file_id_kind = "ntfs_file_index_64"
            file_id: int | bytes = (
                int(by_handle.nFileIndexHigh) << 32
            ) | int(by_handle.nFileIndexLow)
        elif filesystem == "ReFS":
            file_id_kind = "refs_file_id_128"
            file_id = bytes(identity.FileId.Identifier)
        else:
            _raise("unsupported_filesystem")
        if file_id == 0 or file_id == b"\x00" * 16:
            _raise("duplicate_identity")
        if expected is not None and (
            expected.file_id_kind != file_id_kind or expected.file_id != file_id
        ):
            _raise("observation_raced")

        size_bytes = int(standard.EndOfFile)
        by_size = (
            int(by_handle.nFileSizeHigh) << 32
        ) | int(by_handle.nFileSizeLow)
        allocation_size = int(standard.AllocationSize)
        link_count = int(standard.NumberOfLinks)
        if size_bytes < 0 or allocation_size < 0 or by_size != size_bytes:
            _raise("observation_failed")
        if link_count != int(by_handle.nNumberOfLinks):
            _raise("observation_raced")
        if object_kind == "regular_file" and link_count != 1:
            _raise("duplicate_identity")

        last_write_ticks = int(basic.LastWriteTime)
        change_ticks = int(basic.ChangeTime)
        mtime_ns: int | None = None
        if object_kind == "regular_file":
            if last_write_ticks < self._FILETIME_UNIX_EPOCH:
                _raise("observation_failed")
            mtime_ns = _windows_filetime_to_ns(last_write_ticks)
        streams: tuple[tuple[str, int, int], ...] = ()
        if require_stream_contract:
            streams = self._stream_inventory(handle)
            _validate_windows_streams(
                streams,
                object_kind=object_kind,
                size_bytes=size_bytes,
            )

        return WindowsObjectSnapshot(
            volume_serial=volume_serial,
            file_id_kind=file_id_kind,
            file_id=file_id,
            object_kind=object_kind,
            size_bytes=size_bytes,
            mtime_ns=mtime_ns,
            allocation_size=allocation_size,
            link_count=link_count,
            attributes=attributes,
            reparse_tag=int(attribute.ReparseTag),
            last_write_ticks=last_write_ticks,
            change_ticks=change_ticks,
            streams=streams,
        )

    def read_file_bounded(
        self,
        handle: object,
        *,
        maximum_bytes: int,
    ) -> tuple[bytes, bool]:
        if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= 66:
            _raise("observation_failed")
        raw = self._raw(handle)
        if not self._kernel32.SetFilePointerEx(raw, 0, None, self._FILE_BEGIN):
            self._raise_call_error(self._last_error())
        prefix = bytearray()
        buffer = (self._ctypes.c_ubyte * maximum_bytes)()
        while len(prefix) < maximum_bytes:
            remaining = maximum_bytes - len(prefix)
            read = self._DWORD()
            if not self._kernel32.ReadFile(
                raw,
                self._ctypes.byref(buffer),
                remaining,
                self._ctypes.byref(read),
                None,
            ):
                self._raise_call_error(self._last_error())
            count = int(read.value)
            if count > remaining:
                _raise("observation_failed")
            if count == 0:
                return bytes(prefix), True
            prefix.extend(bytes(buffer[:count]))
        return bytes(prefix), False

    def read_security_descriptor(self, handle: object) -> bytes:
        raw = self._raw(handle)
        assert isinstance(handle, _WindowsHandleToken)
        if (
            self._access_profile != "security_read"
            or not handle._security_readable
            or self._advapi32 is None
        ):
            _raise("observation_failed")

        descriptor = self._ctypes.c_void_p()
        result = int(
            self._advapi32.GetSecurityInfo(
                raw,
                self._SE_FILE_OBJECT,
                self._OWNER_SECURITY_INFORMATION
                | self._GROUP_SECURITY_INFORMATION
                | self._DACL_SECURITY_INFORMATION,
                None,
                None,
                None,
                None,
                self._ctypes.byref(descriptor),
            )
        )
        if result != 0:
            _raise("observation_failed", self._cause(result))
        pointer = descriptor.value
        if pointer is None:
            _raise("observation_failed")

        primary_error: BaseException | None = None
        primary_traceback = None
        detached: bytes | None = None
        try:
            if not self._advapi32.IsValidSecurityDescriptor(pointer):
                _raise("observation_failed")
            control = self._WORD()
            revision = self._DWORD()
            if not self._advapi32.GetSecurityDescriptorControl(
                pointer,
                self._ctypes.byref(control),
                self._ctypes.byref(revision),
            ):
                error = self._last_error()
                _raise("observation_failed", self._cause(error))
            if (
                int(revision.value) != self._SECURITY_DESCRIPTOR_REVISION
                or not int(control.value) & self._SE_SELF_RELATIVE
            ):
                _raise("observation_failed")
            length = int(self._advapi32.GetSecurityDescriptorLength(pointer))
            if not (
                self._SECURITY_DESCRIPTOR_MIN_LENGTH
                <= length
                <= self._SECURITY_DESCRIPTOR_MAX_LENGTH
            ):
                _raise("observation_failed")
            try:
                copied = self._ctypes.string_at(pointer, length)
            except Exception as exc:
                _raise("observation_failed", exc)
            if type(copied) is not bytes or len(copied) != length:
                _raise("observation_failed")
            detached = copied
        except BaseException as exc:
            primary_error = exc
            primary_traceback = exc.__traceback__

        cleanup_error: WindowsHeldHandleError | None = None
        try:
            free_result = self._kernel32.LocalFree(self._ctypes.c_void_p(pointer))
            if self._value(free_result) not in {None, 0}:
                cleanup_error = WindowsHeldHandleError("observation_failed")
                cleanup_error.__cause__ = self._cause(self._last_error())
                cleanup_error.__suppress_context__ = True
        except BaseException as exc:
            cleanup_error = WindowsHeldHandleError("observation_failed")
            cleanup_error.__cause__ = exc
            cleanup_error.__suppress_context__ = True

        if primary_error is not None:
            if cleanup_error is not None:
                cleanup_error.__context__ = primary_error.__context__
                if primary_error.__cause__ is None:
                    primary_error.__cause__ = cleanup_error
                    primary_error.__suppress_context__ = True
                else:
                    primary_error.__context__ = cleanup_error
            raise primary_error.with_traceback(primary_traceback)
        if cleanup_error is not None:
            raise cleanup_error
        assert detached is not None
        return detached

    def hash_file(self, handle: object) -> tuple[str, int]:
        raw = self._raw(handle)
        if not self._kernel32.SetFilePointerEx(raw, 0, None, self._FILE_BEGIN):
            self._raise_call_error(self._last_error())
        digest = hashlib.sha256()
        total = 0
        buffer = (self._ctypes.c_ubyte * (1024 * 1024))()
        while True:
            read = self._DWORD()
            if not self._kernel32.ReadFile(
                raw,
                self._ctypes.byref(buffer),
                self._ctypes.sizeof(buffer),
                self._ctypes.byref(read),
                None,
            ):
                self._raise_call_error(self._last_error())
            count = int(read.value)
            if count == 0:
                break
            digest.update(bytes(buffer[:count]))
            total += count
        return digest.hexdigest(), total

    def open_by_id(
        self,
        volume_handle: object,
        entry: WindowsDirectoryEntry,
        *,
        directory: bool,
    ) -> object:
        raw_volume = self._raw(volume_handle)
        descriptor = self._FILE_ID_DESCRIPTOR_STRUCT()
        descriptor.dwSize = self._ctypes.sizeof(descriptor)
        if entry.file_id_kind == "ntfs_file_index_64" and isinstance(entry.file_id, int):
            descriptor.Type = self._FILE_ID_TYPE
            descriptor.FileId = (
                entry.file_id
                if entry.file_id < (1 << 63)
                else entry.file_id - (1 << 64)
            )
        elif (
            entry.file_id_kind == "refs_file_id_128"
            and isinstance(entry.file_id, bytes)
            and len(entry.file_id) == 16
        ):
            descriptor.Type = self._EXTENDED_FILE_ID_TYPE
            for index, byte in enumerate(entry.file_id):
                descriptor.ExtendedFileId.Identifier[index] = byte
        else:
            _raise("observation_failed")
        flags = self._FILE_FLAG_OPEN_REPARSE_POINT
        if directory:
            access = self._FILE_LIST_DIRECTORY | self._FILE_READ_ATTRIBUTES
            flags |= self._FILE_FLAG_BACKUP_SEMANTICS
        else:
            access = self._FILE_READ_DATA | self._FILE_READ_ATTRIBUTES
            flags |= self._FILE_FLAG_SEQUENTIAL_SCAN
        security_readable = self._access_profile == "security_read"
        if security_readable:
            access |= self._READ_CONTROL
        token = self._reserve(security_readable=security_readable)
        try:
            handle = self._kernel32.OpenFileById(
                raw_volume,
                self._ctypes.byref(descriptor),
                access,
                self._FILE_SHARE_READ,
                None,
                flags,
            )
        except BaseException:
            self._discard_reservation(token)
            raise
        token._raw = handle
        if self._failed_handle(handle):
            last_error = self._last_error()
            self._discard_reservation(token)
            self._raise_call_error(
                last_error,
                disappeared=True,
                unsupported_capability=True,
            )
        return token

    def _close_registered(self, handle: _WindowsHandleToken) -> None:
        raw = handle._raw
        handle._live = False
        self._handles.remove(handle)
        if raw is None:
            return
        if not self._kernel32.CloseHandle(raw):
            _raise("observation_failed", self._cause(self._last_error()))

    def close(self, handle: object) -> None:
        self._raw(handle)
        assert isinstance(handle, _WindowsHandleToken)
        self._close_registered(handle)

    def __enter__(self) -> WindowsHeldHandleBackend:
        if self._exited:
            _raise("observation_failed")
        return self

    @classmethod
    def _append_close_error(
        cls,
        head: WindowsHeldHandleError | None,
        later: WindowsHeldHandleError,
    ) -> WindowsHeldHandleError:
        if head is None:
            return later
        if head is later:
            return head
        tail = head
        while True:
            if tail is later:
                return head
            linked = tail.__cause__
            if isinstance(linked, WindowsHeldHandleError):
                tail = linked
                continue
            context = tail.__context__
            if isinstance(context, WindowsHeldHandleError):
                tail = context
                continue
            if linked is None:
                tail.__cause__ = later
                tail.__suppress_context__ = True
            elif context is None:
                tail.__context__ = later
            else:
                preserved = context
                tail.__context__ = later
                cls._preserve_context(later, preserved)
            return head

    @staticmethod
    def _preserve_context(
        cleanup: WindowsHeldHandleError,
        preserved: BaseException,
    ) -> None:
        tail: BaseException = cleanup
        remaining = 256
        while remaining:
            remaining -= 1
            if tail is preserved:
                return
            cause = tail.__cause__
            if isinstance(cause, WindowsHeldHandleError):
                tail = cause
                continue
            context = tail.__context__
            if isinstance(context, WindowsHeldHandleError):
                tail = context
                continue
            if context is None:
                tail.__context__ = preserved
                return
            tail = context
        return

    @classmethod
    def _attach_close_error(
        cls,
        primary: BaseException,
        cleanup: WindowsHeldHandleError,
    ) -> None:
        if primary.__cause__ is None:
            primary.__cause__ = cleanup
            primary.__suppress_context__ = True
            return
        if primary.__context__ is None:
            primary.__context__ = cleanup
            return
        if isinstance(primary.__context__, WindowsHeldHandleError):
            cls._append_close_error(primary.__context__, cleanup)
            return
        if isinstance(primary.__cause__, WindowsHeldHandleError):
            cls._append_close_error(primary.__cause__, cleanup)
            return
        preserved = primary.__context__
        primary.__context__ = cleanup
        cls._preserve_context(cleanup, preserved)

    def __exit__(self, exc_type, exc, traceback) -> bool:
        first_close_error: WindowsHeldHandleError | None = None
        while self._handles:
            handle = self._handles[-1]
            try:
                self._close_registered(handle)
            except BaseException as close_error:
                handle._live = False
                if self._handles and self._handles[-1] is handle:
                    self._handles.pop()
                else:
                    try:
                        self._handles.remove(handle)
                    except ValueError:
                        pass
                normalized = (
                    close_error
                    if isinstance(close_error, WindowsHeldHandleError)
                    else handle._cleanup_error
                )
                if normalized.__cause__ is exc:
                    normalized.__cause__ = None
                    normalized.__suppress_context__ = False
                if normalized.__context__ is exc:
                    normalized.__context__ = None
                first_close_error = self._append_close_error(
                    first_close_error,
                    normalized,
                )
        self._exited = True
        if exc is None and first_close_error is not None:
            raise first_close_error
        if exc is not None and first_close_error is not None:
            self._attach_close_error(exc, first_close_error)
            raise exc.with_traceback(traceback)
        return False
