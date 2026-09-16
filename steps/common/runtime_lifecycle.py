"""Opt-in Windows lifecycle for the existing API and Watchdog entrypoints.

The launcher owns the stop event. Each role owns its own non-inherited job
handle until process exit, so a failed launcher can preserve a working peer
without leaving that peer's eventual children uncontained.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
        ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t), ("active_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
        ("scheduling", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ("reads", "writes", "other", "read_bytes", "write_bytes", "other_bytes")]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicLimits), ("io", _IoCounters),
        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t),
    ]


class RuntimeLifecycle:
    @classmethod
    def from_environment(cls, role: str) -> RuntimeLifecycle | None:
        event_name = os.environ.get("GOODQ_RUNTIME_STOP_EVENT")
        if event_name is None:
            return None
        if os.name != "nt" or role not in {"api", "watchdog"} or not re.fullmatch(r"Local\\GoodQRuntime-[0-9a-f]{32}", event_name):
            raise RuntimeError("Invalid supervised Windows lifecycle binding")
        return cls(event_name, role)

    def __init__(self, event_name: str, role: str):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.OpenEventW.restype = wintypes.HANDLE
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        event = kernel.OpenEventW(0x00100000, False, event_name)  # SYNCHRONIZE only
        if not event:
            raise ctypes.WinError(ctypes.get_last_error())
        job = None
        try:
            job = kernel.CreateJobObjectW(None, f"{event_name}.{role}.{os.getpid()}")
            error = ctypes.get_last_error()
            if not job:
                raise ctypes.WinError(error)
            if error == 183:  # ERROR_ALREADY_EXISTS: never adopt another owner.
                raise RuntimeError("Runtime job already exists; refusing adoption")
            limits = _ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess()):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            if job:
                kernel.CloseHandle(job)
            kernel.CloseHandle(event)
            raise
        self._kernel, self._event, self._job = kernel, event, job
        # Do not close the job on function return or in a Python finalizer: the
        # current process is a member. Windows closes it on normal/forced exit.
        # Neither this handle nor breakaway rights are inherited by descendants.

    def stop_requested(self) -> bool:
        result = self._kernel.WaitForSingleObject(self._event, 0)
        if result not in (0, 258):  # WAIT_OBJECT_0 / WAIT_TIMEOUT
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0
