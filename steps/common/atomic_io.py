from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any


def _atomic_write_json(
    path: Path,
    data: Any,
    *,
    indent: int,
    replace,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=indent)
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    replace(tmp, target)


def atomic_write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Write JSON payload atomically using same-directory temp file + os.replace."""
    _atomic_write_json(path, data, indent=indent, replace=os.replace)


def _replace_file_allowing_open_readers(source: Path, destination: Path) -> None:
    """Replace an existing Windows file that may have share-delete readers."""
    source_path = Path(source)
    destination_path = Path(destination)
    if os.name != "nt" or not destination_path.exists():
        os.replace(source_path, destination_path)
        return

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    replace_file = kernel32.ReplaceFileW
    replace_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    replace_file.restype = wintypes.BOOL
    if not replace_file(
        str(destination_path),
        str(source_path),
        None,
        0,
        None,
        None,
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def _replace_file_with_retry_for_open_readers(
    source: Path,
    destination: Path,
    *,
    attempts: int = 50,
    retry_seconds: float = 0.1,
) -> None:
    """Retry transient Windows sharing violations while preserving atomicity."""
    if attempts < 1:
        raise ValueError("Atomic-replace attempts must be positive")
    for attempt in range(attempts):
        try:
            _replace_file_allowing_open_readers(source, destination)
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in (32, 33) or attempt + 1 == attempts:
                raise
            time.sleep(retry_seconds)


def atomic_write_json_for_concurrent_readers(
    path: Path,
    data: Any,
    *,
    indent: int = 2,
) -> None:
    """Atomically write JSON while preserving Windows share-delete readers."""
    _atomic_write_json(
        path,
        data,
        indent=indent,
        replace=_replace_file_with_retry_for_open_readers,
    )


def _read_text_with_windows_share_delete(path: Path, *, encoding: str) -> str:
    import ctypes
    from ctypes import wintypes
    import msvcrt

    generic_read = 0x80000000
    file_share_read = 0x00000001
    file_share_write = 0x00000002
    file_share_delete = 0x00000004
    open_existing = 3
    file_attribute_normal = 0x00000080

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = create_file(
        str(Path(path)),
        generic_read,
        file_share_read | file_share_write | file_share_delete,
        None,
        open_existing,
        file_attribute_normal,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        file_descriptor = msvcrt.open_osfhandle(
            handle,
            os.O_RDONLY | os.O_BINARY,
        )
    except Exception:
        close_handle(handle)
        raise
    with os.fdopen(file_descriptor, "r", encoding=encoding) as stream:
        return stream.read()


def read_text_during_atomic_replace(
    path: Path,
    *,
    encoding: str = "utf-8",
    attempts: int = 50,
    retry_seconds: float = 0.001,
) -> str:
    """Read complete text across an action-job replacement window."""
    target = Path(path)
    if os.name != "nt":
        return target.read_text(encoding=encoding)
    if attempts < 1:
        raise ValueError("Atomic-replace read attempts must be positive")
    last_error: OSError | None = None
    for attempt in range(attempts):
        try:
            return _read_text_with_windows_share_delete(target, encoding=encoding)
        except (FileNotFoundError, PermissionError) as exc:
            last_error = exc
            if attempt + 1 == attempts:
                raise
            time.sleep(retry_seconds)
    if last_error is not None:
        raise last_error
    raise FileNotFoundError(target)
