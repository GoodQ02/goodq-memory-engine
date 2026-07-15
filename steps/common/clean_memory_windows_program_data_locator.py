"""Capability-bound Windows ProgramData location for clean-memory authority."""

from __future__ import annotations

import ctypes
import unicodedata


__all__ = (
    "CleanMemoryWindowsProgramDataLocatorError",
    "CleanMemoryWindowsProgramDataLocation",
    "CleanMemoryWindowsProgramDataLocator",
    "verify_clean_memory_windows_program_data_locator_abi",
    "bind_clean_memory_windows_program_data_locator",
)

_ERROR_MESSAGES = {
    "unsupported_platform": (
        "Clean-memory Windows ProgramData locator is unsupported"
    ),
    "redirected_boundary": (
        "Clean-memory Windows ProgramData locator boundary is redirected"
    ),
    "observation_failed": (
        "Clean-memory Windows ProgramData locator observation failed"
    ),
}

_DWORD = ctypes.c_uint32
_WORD = ctypes.c_uint16
_BYTE = ctypes.c_ubyte
_PVOID = ctypes.c_void_p

_PROGRAM_DATA_GUID_FIELDS = (
    0x62AB5D82,
    0xFDC1,
    0x4DC3,
    (0xA9, 0xDD, 0x07, 0x0D, 0x1D, 0x49, 0x5D, 0x97),
)
_FIXED_DIRECTORY_COMPONENTS = ("GoodQ", "authority", "clean-memory")
_PIN_NAME = "protected-boundaries.sha256"
_OWNER = object()
_GRAPH_LIMIT = 256


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", _DWORD),
        ("Data2", _WORD),
        ("Data3", _WORD),
        ("Data4", _BYTE * 8),
    ]


class CleanMemoryWindowsProgramDataLocatorError(RuntimeError):
    """Fixed, path-free ProgramData locator failure."""

    __slots__ = ("_code",)

    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in _ERROR_MESSAGES:
            raise ValueError(
                "Unknown clean-memory Windows ProgramData locator error code"
            ) from None
        message = _ERROR_MESSAGES[code]
        super().__init__(message)
        object.__setattr__(self, "_code", code)

    @property
    def code(self) -> str:
        return object.__getattribute__(self, "_code")

    def __getattribute__(self, name: str):
        if name == "__dict__":
            return {}
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("ProgramData locator errors are immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("ProgramData locator errors are immutable")

    def add_note(self, note: str) -> None:
        del note
        raise TypeError("ProgramData locator errors cannot carry notes")


class CleanMemoryWindowsProgramDataLocation:
    """Redacted immutable components returned by a bound locator."""

    __slots__ = (
        "_drive_root",
        "_program_data_components",
        "_fixed_directory_components",
        "_pin_name",
    )

    def __new__(cls, owner: object = None, *args: object, **kwargs: object):
        if owner is not _OWNER:
            raise TypeError("ProgramData locations are capability-created")
        return super().__new__(cls)

    def __init__(
        self,
        owner: object,
        drive_root: str,
        program_data_components: tuple[str, ...],
    ) -> None:
        object.__setattr__(self, "_drive_root", drive_root)
        object.__setattr__(
            self,
            "_program_data_components",
            program_data_components,
        )
        object.__setattr__(
            self,
            "_fixed_directory_components",
            _FIXED_DIRECTORY_COMPONENTS,
        )
        object.__setattr__(self, "_pin_name", _PIN_NAME)

    @property
    def drive_root(self) -> str:
        return self._drive_root

    @property
    def program_data_components(self) -> tuple[str, ...]:
        return self._program_data_components

    @property
    def fixed_directory_components(self) -> tuple[str, ...]:
        return self._fixed_directory_components

    @property
    def pin_name(self) -> str:
        return self._pin_name

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ProgramData locations are immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("ProgramData locations are immutable")

    def __repr__(self) -> str:
        return "CleanMemoryWindowsProgramDataLocation(<redacted>)"

    def __eq__(self, other: object) -> bool:
        if type(other) is not CleanMemoryWindowsProgramDataLocation:
            return False
        return (
            self._drive_root,
            self._program_data_components,
            self._fixed_directory_components,
            self._pin_name,
        ) == (
            other._drive_root,
            other._program_data_components,
            other._fixed_directory_components,
            other._pin_name,
        )

    def __hash__(self) -> int:
        return hash(
            (
                self._drive_root,
                self._program_data_components,
                self._fixed_directory_components,
                self._pin_name,
            )
        )

    def __copy__(self):
        raise TypeError("ProgramData locations cannot be copied")

    def __deepcopy__(self, memo: object):
        raise TypeError("ProgramData locations cannot be copied")

    def __reduce__(self):
        raise TypeError("ProgramData locations cannot be serialized")

    def __reduce_ex__(self, protocol: int):
        raise TypeError("ProgramData locations cannot be serialized")


class CleanMemoryWindowsProgramDataLocator:
    """Bound native capability that resolves ProgramData components."""

    __slots__ = ("_known_folder", "_free")

    def __new__(cls, owner: object = None, *args: object, **kwargs: object):
        if owner is not _OWNER:
            raise TypeError("ProgramData locators must be bound")
        return super().__new__(cls)

    def __init__(self, owner: object, known_folder: object, free: object) -> None:
        object.__setattr__(self, "_known_folder", known_folder)
        object.__setattr__(self, "_free", free)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ProgramData locators are immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("ProgramData locators are immutable")

    def __repr__(self) -> str:
        return "CleanMemoryWindowsProgramDataLocator(<redacted>)"

    def __copy__(self):
        raise TypeError("ProgramData locators cannot be copied")

    def __deepcopy__(self, memo: object):
        raise TypeError("ProgramData locators cannot be copied")

    def __reduce__(self):
        raise TypeError("ProgramData locators cannot be serialized")

    def __reduce_ex__(self, protocol: int):
        raise TypeError("ProgramData locators cannot be serialized")

    def resolve(self) -> CleanMemoryWindowsProgramDataLocation:
        return _resolve_program_data(self._known_folder, self._free)


def _raise(code: str) -> None:
    raise CleanMemoryWindowsProgramDataLocatorError(code) from None


def _clone_failure_graph(error: BaseException):
    remaining = [_GRAPH_LIMIT]
    visiting: set[int] = set()
    memo: dict[int, CleanMemoryWindowsProgramDataLocatorError] = {}

    def clone(node: BaseException):
        identity = id(node)
        if remaining[0] <= 0 or identity in visiting:
            return CleanMemoryWindowsProgramDataLocatorError(
                "observation_failed"
            )
        known = memo.get(identity)
        if known is not None:
            return known
        remaining[0] -= 1
        code = "observation_failed"
        if type(node) is CleanMemoryWindowsProgramDataLocatorError:
            try:
                candidate = object.__getattribute__(node, "_code")
            except BaseException:
                candidate = None
            if type(candidate) is str and candidate in _ERROR_MESSAGES:
                code = candidate
        public = CleanMemoryWindowsProgramDataLocatorError(code)
        memo[identity] = public
        visiting.add(identity)
        try:
            cause = object.__getattribute__(node, "__cause__")
        except BaseException:
            cause = None
        try:
            context = object.__getattribute__(node, "__context__")
        except BaseException:
            context = None
        if cause is not None:
            object.__setattr__(public, "__cause__", clone(cause))
        if context is not None:
            object.__setattr__(public, "__context__", clone(context))
        try:
            suppress_context = bool(
                object.__getattribute__(node, "__suppress_context__")
            )
        except BaseException:
            suppress_context = False
        object.__setattr__(
            public,
            "__suppress_context__",
            suppress_context,
        )
        visiting.discard(identity)
        return public

    return clone(error)


def _sanitize_control_links(error: BaseException) -> None:
    cause = error.__cause__
    context = error.__context__
    suppress_context = bool(error.__suppress_context__)
    fallback = CleanMemoryWindowsProgramDataLocatorError(
        "observation_failed"
    )
    try:
        public_cause = (
            _clone_failure_graph(cause) if cause is not None else None
        )
    except BaseException:
        public_cause = fallback if cause is not None else None
    try:
        public_context = (
            public_cause
            if context is cause and context is not None
            else _clone_failure_graph(context)
            if context is not None
            else None
        )
    except BaseException:
        public_context = fallback if context is not None else None
    object.__setattr__(error, "__cause__", public_cause)
    object.__setattr__(error, "__context__", public_context)
    object.__setattr__(error, "__suppress_context__", suppress_context)


def _append_cleanup(
    head: CleanMemoryWindowsProgramDataLocatorError | None,
    later: CleanMemoryWindowsProgramDataLocatorError | None,
):
    if later is None:
        return head
    if head is None or head is later:
        return later if head is None else head
    tail = head
    remaining = _GRAPH_LIMIT
    while remaining:
        remaining -= 1
        if tail is later:
            return head
        cause = tail.__cause__
        if type(cause) is CleanMemoryWindowsProgramDataLocatorError:
            tail = cause
            continue
        context = tail.__context__
        if type(context) is CleanMemoryWindowsProgramDataLocatorError:
            tail = context
            continue
        if cause is None:
            object.__setattr__(tail, "__cause__", later)
            object.__setattr__(tail, "__suppress_context__", True)
        elif context is None:
            object.__setattr__(tail, "__context__", later)
        return head
    return head


def _attach_cleanup(
    primary: BaseException,
    cleanup: CleanMemoryWindowsProgramDataLocatorError | None,
) -> None:
    if cleanup is None:
        return
    if primary.__cause__ is None:
        object.__setattr__(primary, "__cause__", cleanup)
        object.__setattr__(primary, "__suppress_context__", True)
        return
    if primary.__context__ is None:
        object.__setattr__(primary, "__context__", cleanup)
        return
    if type(primary.__context__) is CleanMemoryWindowsProgramDataLocatorError:
        _append_cleanup(primary.__context__, cleanup)
        return
    if type(primary.__cause__) is CleanMemoryWindowsProgramDataLocatorError:
        _append_cleanup(primary.__cause__, cleanup)


def _reraise_preserving_graph(error: BaseException) -> None:
    traceback = error.__traceback__
    cause = error.__cause__
    context = error.__context__
    suppress_context = bool(error.__suppress_context__)
    try:
        raise error.with_traceback(traceback)
    except BaseException:
        object.__setattr__(error, "__cause__", cause)
        object.__setattr__(error, "__context__", context)
        object.__setattr__(error, "__suppress_context__", suppress_context)
        raise


def _raise_after_cleanup(
    primary: BaseException | None,
    cleanup: CleanMemoryWindowsProgramDataLocatorError | None,
) -> None:
    if primary is None:
        if cleanup is not None:
            _reraise_preserving_graph(cleanup)
        return
    if isinstance(primary, Exception):
        public = _clone_failure_graph(primary)
        _attach_cleanup(public, cleanup)
        _reraise_preserving_graph(public)
    _sanitize_control_links(primary)
    _attach_cleanup(primary, cleanup)
    _reraise_preserving_graph(primary)


def _validate_program_data_text(
    value: str,
) -> CleanMemoryWindowsProgramDataLocation:
    if type(value) is not str:
        _raise("observation_failed")
    try:
        utf16_units = len(value.encode("utf-16-le")) // 2
    except UnicodeError:
        _raise("observation_failed")
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
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in component
            )
        ):
            _raise("redirected_boundary")
    return CleanMemoryWindowsProgramDataLocation(
        _OWNER,
        value[:3],
        components,
    )


def _resolve_program_data(
    known_folder: object,
    free: object,
) -> CleanMemoryWindowsProgramDataLocation:
    data4 = (_BYTE * 8)(*_PROGRAM_DATA_GUID_FIELDS[3])
    guid = _GUID(
        _PROGRAM_DATA_GUID_FIELDS[0],
        _PROGRAM_DATA_GUID_FIELDS[1],
        _PROGRAM_DATA_GUID_FIELDS[2],
        data4,
    )
    output = _PVOID()
    primary: BaseException | None = None
    result: CleanMemoryWindowsProgramDataLocation | None = None
    try:
        hresult = int(
            known_folder(
                ctypes.byref(guid),
                0,
                None,
                ctypes.byref(output),
            )
        )
        if hresult < 0 or output.value is None:
            _raise("observation_failed")
        result = _validate_program_data_text(ctypes.wstring_at(output.value))
    except BaseException as error:
        primary = error

    cleanup = None
    if output.value is not None:
        try:
            free(_PVOID(output.value))
        except BaseException as error:
            try:
                cleanup = _clone_failure_graph(error)
            except BaseException:
                cleanup = CleanMemoryWindowsProgramDataLocatorError(
                    "observation_failed"
                )

    _raise_after_cleanup(primary, cleanup)
    if result is None:
        _raise("observation_failed")
    return result


def verify_clean_memory_windows_program_data_locator_abi() -> None:
    if ctypes.sizeof(ctypes.c_void_p) != 8 or ctypes.sizeof(_GUID) != 16:
        _raise("unsupported_platform")
    if (
        _GUID.Data1.offset != 0
        or _GUID.Data2.offset != 4
        or _GUID.Data3.offset != 6
        or _GUID.Data4.offset != 8
    ):
        _raise("unsupported_platform")


def bind_clean_memory_windows_program_data_locator(
    *,
    shell32: object,
    ole32: object,
) -> CleanMemoryWindowsProgramDataLocator:
    verify_clean_memory_windows_program_data_locator_abi()
    if shell32 is None or ole32 is None:
        _raise("unsupported_platform")
    binding_failed = False
    try:
        known_folder = shell32.SHGetKnownFolderPath
        free = ole32.CoTaskMemFree
        if not callable(known_folder) or not callable(free):
            raise TypeError("ProgramData locator exports must be callable")
        known_folder.argtypes = [
            ctypes.POINTER(_GUID),
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        known_folder.restype = ctypes.c_int32
        free.argtypes = [ctypes.c_void_p]
        free.restype = None
    except Exception:
        binding_failed = True
    if binding_failed:
        _raise("unsupported_platform")
    return CleanMemoryWindowsProgramDataLocator(
        _OWNER,
        known_folder,
        free,
    )
