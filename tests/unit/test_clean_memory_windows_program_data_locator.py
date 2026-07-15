from __future__ import annotations

import ast
import copy
import ctypes
import importlib
import inspect
import pickle
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_NAME = "steps.common.clean_memory_windows_program_data_locator"
MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "steps"
    / "common"
    / "clean_memory_windows_program_data_locator.py"
)

_PUBLIC = (
    "CleanMemoryWindowsProgramDataLocatorError",
    "CleanMemoryWindowsProgramDataLocation",
    "CleanMemoryWindowsProgramDataLocator",
    "verify_clean_memory_windows_program_data_locator_abi",
    "bind_clean_memory_windows_program_data_locator",
)

_ERRORS = {
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

_GUID_HEX = "825dab62c1fdc34da9dd070d1d495d97"
_FIXED_DIRECTORIES = ("GoodQ", "authority", "clean-memory")
_PIN_NAME = "protected-boundaries.sha256"
_SECRET = "DO_NOT_LEAK_LOCATOR_SECRET"


def _load_module():
    return importlib.import_module(MODULE_NAME)


class _NativeCall:
    def __init__(self, callback=None) -> None:
        self.argtypes = None
        self.restype = None
        self._callback = callback

    def __call__(self, *args):
        if self._callback is None:
            raise AssertionError("unexpected native invocation")
        return self._callback(*args)


class _World:
    def __init__(self) -> None:
        self.path = r"C:\ProgramData"
        self.hresult = 0
        self.has_output = True
        self.call_error: BaseException | None = None
        self.free_error: BaseException | None = None
        self.buffers: dict[int, object] = {}
        self.freed: list[int] = []
        self.events: list[tuple[object, ...]] = []
        self.shell32 = SimpleNamespace(
            SHGetKnownFolderPath=_NativeCall(self._known_folder)
        )
        self.ole32 = SimpleNamespace(CoTaskMemFree=_NativeCall(self._free))

    def _known_folder(self, guid, flags, token, output) -> int:
        guid_bytes = ctypes.string_at(guid, 16).hex()
        token_value = ctypes.cast(token, ctypes.c_void_p).value if token else None
        self.events.append(("known_folder", guid_bytes, int(flags), token_value))
        if self.has_output:
            buffer = ctypes.create_unicode_buffer(self.path)
            address = ctypes.addressof(buffer)
            self.buffers[address] = buffer
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = address
        if self.call_error is not None:
            raise self.call_error
        return self.hresult

    def _free(self, pointer) -> None:
        address = ctypes.cast(pointer, ctypes.c_void_p).value
        self.events.append(("free", address))
        if address is not None:
            self.freed.append(address)
            self.buffers.pop(address, None)
        if self.free_error is not None:
            raise self.free_error


def _bind(module, world: _World):
    return module.bind_clean_memory_windows_program_data_locator(
        shell32=world.shell32,
        ole32=world.ole32,
    )


def _assert_closed_graph(module, error: BaseException) -> None:
    pending = [error]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        if isinstance(current, (KeyboardInterrupt, SystemExit, GeneratorExit)):
            pass
        else:
            assert type(current) is module.CleanMemoryWindowsProgramDataLocatorError
            assert current.code in _ERRORS
            assert _SECRET not in str(current)
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
        assert len(seen) <= 256


def test_module_exists_before_any_production_contract_can_pass() -> None:
    assert MODULE_PATH.is_file()


def test_public_surface_and_signatures_are_exact() -> None:
    module = _load_module()

    assert module.__all__ == _PUBLIC
    assert tuple(
        inspect.signature(
            module.verify_clean_memory_windows_program_data_locator_abi
        ).parameters
    ) == ()
    bind_signature = inspect.signature(
        module.bind_clean_memory_windows_program_data_locator
    )
    assert tuple(bind_signature.parameters) == ("shell32", "ole32")
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in bind_signature.parameters.values()
    )
    assert tuple(
        inspect.signature(
            module.CleanMemoryWindowsProgramDataLocator.resolve
        ).parameters
    ) == ("self",)


@pytest.mark.parametrize(("code", "message"), tuple(_ERRORS.items()))
def test_error_contract_is_closed_path_free_and_immutable(
    code: str, message: str
) -> None:
    module = _load_module()

    error = module.CleanMemoryWindowsProgramDataLocatorError(code)
    assert isinstance(error, RuntimeError)
    assert error.code == code
    assert str(error) == message
    assert error.args == (message,)
    with pytest.raises(AttributeError):
        error.code = "observation_failed"
    with pytest.raises(AttributeError):
        error._code = "observation_failed"
    with pytest.raises(AttributeError):
        error.args = (_SECRET,)
    with pytest.raises(AttributeError):
        error.unexpected = _SECRET
    with pytest.raises(AttributeError):
        del error._code
    with pytest.raises(AttributeError):
        del error.args
    with pytest.raises(TypeError):
        error.add_note(_SECRET)
    detached = error.__dict__
    detached["unexpected"] = _SECRET
    assert error.__dict__ == {}
    assert error.args == (message,)
    assert _SECRET not in repr(error.__dict__)


@pytest.mark.parametrize(
    "value",
    [None, "", "unknown", _SECRET, 1, True, []],
)
def test_error_rejects_unknown_codes(value: object) -> None:
    module = _load_module()

    with pytest.raises(
        ValueError,
        match="Unknown clean-memory Windows ProgramData locator error code",
    ) as exc_info:
        module.CleanMemoryWindowsProgramDataLocatorError(value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert _SECRET not in repr(exc_info.value)


def test_import_is_capability_pure(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda *args, **kwargs: calls.append((args, kwargs)),
        raising=False,
    )
    importlib.invalidate_caches()
    importlib.import_module(MODULE_NAME)

    assert calls == []


def test_abi_and_binding_are_exact_and_operation_free() -> None:
    module = _load_module()
    world = _World()

    assert ctypes.sizeof(ctypes.c_void_p) == 8
    assert ctypes.sizeof(module._GUID) == 16
    module.verify_clean_memory_windows_program_data_locator_abi()
    locator = _bind(module, world)

    assert type(locator) is module.CleanMemoryWindowsProgramDataLocator
    assert world.events == []
    assert world.shell32.SHGetKnownFolderPath.argtypes == [
        ctypes.POINTER(module._GUID),
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    assert world.shell32.SHGetKnownFolderPath.restype is ctypes.c_int32
    assert world.ole32.CoTaskMemFree.argtypes == [ctypes.c_void_p]
    assert world.ole32.CoTaskMemFree.restype is None


@pytest.mark.parametrize("missing", ["shell32", "ole32"])
def test_binding_rejects_missing_library_without_operation(missing: str) -> None:
    module = _load_module()
    world = _World()
    libraries = {"shell32": world.shell32, "ole32": world.ole32}
    libraries[missing] = None

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        module.bind_clean_memory_windows_program_data_locator(**libraries)

    assert exc_info.value.code == "unsupported_platform"
    assert world.events == []
    _assert_closed_graph(module, exc_info.value)


@pytest.mark.parametrize(
    ("library", "export"),
    [("shell32", "SHGetKnownFolderPath"), ("ole32", "CoTaskMemFree")],
)
def test_binding_rejects_missing_exports(
    library: str, export: str
) -> None:
    module = _load_module()
    world = _World()
    delattr(getattr(world, library), export)

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        _bind(module, world)

    assert exc_info.value.code == "unsupported_platform"
    assert world.events == []
    _assert_closed_graph(module, exc_info.value)


@pytest.mark.parametrize(
    ("library", "export"),
    [("shell32", "SHGetKnownFolderPath"), ("ole32", "CoTaskMemFree")],
)
def test_binding_rejects_non_callable_exports_without_operation(
    library: str, export: str
) -> None:
    module = _load_module()
    world = _World()
    setattr(getattr(world, library), export, SimpleNamespace())

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        _bind(module, world)

    assert exc_info.value.code == "unsupported_platform"
    assert world.events == []
    _assert_closed_graph(module, exc_info.value)


def test_binding_sanitizes_unexpected_ordinary_export_failure() -> None:
    module = _load_module()
    world = _World()

    class FailingBinding:
        @property
        def argtypes(self):
            return None

        @argtypes.setter
        def argtypes(self, value) -> None:
            del value
            raise RuntimeError(_SECRET)

    world.shell32.SHGetKnownFolderPath = FailingBinding()

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        _bind(module, world)

    assert exc_info.value.code == "unsupported_platform"
    assert world.events == []
    _assert_closed_graph(module, exc_info.value)


def test_success_returns_exact_redacted_non_aliasable_location() -> None:
    module = _load_module()
    world = _World()
    locator = _bind(module, world)
    del world.shell32.SHGetKnownFolderPath
    del world.ole32.CoTaskMemFree

    location = locator.resolve()

    assert type(location) is module.CleanMemoryWindowsProgramDataLocation
    assert location.drive_root == "C:\\"
    assert location.program_data_components == ("ProgramData",)
    assert location.fixed_directory_components == _FIXED_DIRECTORIES
    assert location.pin_name == _PIN_NAME
    assert world.events[0] == ("known_folder", _GUID_HEX, 0, None)
    assert world.events[1][0] == "free"
    assert len(world.freed) == 1
    assert repr(location) == (
        "CleanMemoryWindowsProgramDataLocation(<redacted>)"
    )
    assert repr(locator) == (
        "CleanMemoryWindowsProgramDataLocator(<redacted>)"
    )
    with pytest.raises(TypeError):
        module.CleanMemoryWindowsProgramDataLocation()
    with pytest.raises(TypeError):
        module.CleanMemoryWindowsProgramDataLocator()
    retained_slots = (
        (
            location,
            (
                "_drive_root",
                "_program_data_components",
                "_fixed_directory_components",
                "_pin_name",
            ),
        ),
        (locator, ("_known_folder", "_free")),
    )
    for value, names in retained_slots:
        for name in names:
            with pytest.raises(AttributeError):
                delattr(value, name)
    for value in (location, locator):
        with pytest.raises(TypeError):
            copy.copy(value)
        with pytest.raises(TypeError):
            copy.deepcopy(value)
        with pytest.raises(TypeError):
            pickle.dumps(value)


def test_location_equality_is_exact_and_has_no_full_path_surface() -> None:
    module = _load_module()
    world = _World()
    locator = _bind(module, world)
    first = locator.resolve()
    second = locator.resolve()
    world.path = r"D:\ProgramData"
    different = locator.resolve()

    assert first == second
    assert first != different
    assert first != object()
    assert not hasattr(first, "path")
    assert not hasattr(first, "full_path")
    assert not hasattr(first, "projection")
    assert not hasattr(first, "to_dict")
    with pytest.raises(AttributeError):
        first.drive_root = "D:\\"


@pytest.mark.parametrize(
    ("hresult", "has_output"),
    [(0, False), (-1, False), (-1, True)],
)
def test_output_quadrants_fail_closed_and_free_owned_output(
    hresult: int, has_output: bool
) -> None:
    module = _load_module()
    world = _World()
    world.hresult = hresult
    world.has_output = has_output

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        _bind(module, world).resolve()

    assert exc_info.value.code == "observation_failed"
    assert len(world.freed) == int(has_output)


def test_failing_hresult_output_is_never_dereferenced(monkeypatch) -> None:
    module = _load_module()
    world = _World()
    world.hresult = -1
    monkeypatch.setattr(
        module.ctypes,
        "wstring_at",
        lambda *args: pytest.fail("failing HRESULT output was dereferenced"),
    )

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError):
        _bind(module, world).resolve()

    assert len(world.freed) == 1


@pytest.mark.parametrize(
    "decoded",
    [b"not-text", "C:\\Bad\ud800"],
    ids=("non-string", "unpaired-surrogate"),
)
def test_malformed_decoded_output_is_observation_failed(
    monkeypatch,
    decoded: object,
) -> None:
    module = _load_module()
    world = _World()
    monkeypatch.setattr(module.ctypes, "wstring_at", lambda _pointer: decoded)

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        _bind(module, world).resolve()

    assert exc_info.value.code == "observation_failed"
    assert len(world.freed) == 1
    _assert_closed_graph(module, exc_info.value)


def test_malformed_injected_shared_error_fails_closed() -> None:
    module = _load_module()
    world = _World()
    malformed = RuntimeError.__new__(
        module.CleanMemoryWindowsProgramDataLocatorError
    )
    world.call_error = malformed

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        _bind(module, world).resolve()

    assert exc_info.value.code == "observation_failed"
    assert len(world.freed) == 1
    _assert_closed_graph(module, exc_info.value)


@pytest.mark.parametrize(
    "path",
    [
        r"c:\ProgramData",
        "C:\\ProgramData\\",
        "C:\\",
        r"\\server\share",
        r"\\?\C:\ProgramData",
        r"ProgramData",
        r"%PROGRAMDATA%",
        r"C:\base\..\ProgramData",
        "C:\\ProgramData ",
        "C:\\ProgramData.",
        "C:\\Progra\u006d\u0301Data",
        "C:\\A:B",
        "C:\\A\x01B",
        "C:\\" + "\\".join("x" for _ in range(65)),
        "C:\\" + "x" * 32768,
        "C:\\" + "\U0001f600" * 16383,
    ],
    ids=(
        "lowercase-drive",
        "trailing-separator",
        "drive-root-only",
        "unc-path",
        "extended-path",
        "relative-path",
        "environment-token",
        "parent-component",
        "trailing-space",
        "trailing-dot",
        "non-nfc",
        "component-colon",
        "component-control",
        "too-many-components",
        "too-many-utf16-units-bmp",
        "too-many-utf16-units-non-bmp",
    ),
)
def test_lexical_boundary_is_closed(path: str) -> None:
    module = _load_module()
    world = _World()
    world.path = path

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        _bind(module, world).resolve()

    assert exc_info.value.code == "redirected_boundary"
    assert len(world.freed) == 1
    assert str(exc_info.value) == _ERRORS["redirected_boundary"]


def test_multicomponent_program_data_is_retained_exactly() -> None:
    module = _load_module()
    world = _World()
    world.path = r"C:\Corp\Shared\ProgramData"

    location = _bind(module, world).resolve()

    assert location.drive_root == "C:\\"
    assert location.program_data_components == (
        "Corp",
        "Shared",
        "ProgramData",
    )
    assert location.fixed_directory_components == _FIXED_DIRECTORIES
    assert location.pin_name == _PIN_NAME


def test_cleanup_only_failure_prevents_location_and_is_sanitized() -> None:
    module = _load_module()
    world = _World()
    world.free_error = OSError(_SECRET)

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        _bind(module, world).resolve()

    assert exc_info.value.code == "observation_failed"
    assert len(world.freed) == 1
    _assert_closed_graph(module, exc_info.value)


def test_primary_precedes_cleanup_failure_with_closed_graph() -> None:
    module = _load_module()
    world = _World()
    world.path = r"c:\ProgramData"
    world.free_error = OSError(_SECRET)

    with pytest.raises(module.CleanMemoryWindowsProgramDataLocatorError) as exc_info:
        _bind(module, world).resolve()

    assert exc_info.value.code == "redirected_boundary"
    assert len(world.freed) == 1
    assert exc_info.value.__cause__ is not None or exc_info.value.__context__ is not None
    _assert_closed_graph(module, exc_info.value)


@pytest.mark.parametrize("control", [KeyboardInterrupt(), SystemExit(), GeneratorExit()])
def test_control_flow_primary_is_preserved_and_buffer_is_freed(control) -> None:
    module = _load_module()
    world = _World()
    control.__cause__ = OSError(_SECRET)
    control.__context__ = LookupError(_SECRET)
    control.__suppress_context__ = False
    world.call_error = control
    world.free_error = OSError(_SECRET)

    with pytest.raises(type(control)) as exc_info:
        _bind(module, world).resolve()

    assert exc_info.value is control
    assert len(world.freed) == 1
    assert control.__suppress_context__ is False
    assert type(control.__cause__) is (
        module.CleanMemoryWindowsProgramDataLocatorError
    )
    assert control.__cause__.code == "observation_failed"
    assert type(control.__context__) is (
        module.CleanMemoryWindowsProgramDataLocatorError
    )
    assert control.__context__.code == "observation_failed"
    assert type(control.__context__.__cause__) is (
        module.CleanMemoryWindowsProgramDataLocatorError
    )
    assert control.__context__.__cause__.code == "observation_failed"
    _assert_closed_graph(module, exc_info.value)


def test_source_imports_and_calls_are_strictly_contained() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    direct_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    from_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
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

    assert direct_imports <= {"ctypes", "unicodedata"}
    assert from_imports <= {"__future__"}
    assert not any(
        name == "cli" or name.startswith("cli.") for name in from_imports
    )
    assert called_names.isdisjoint({"open", "exec", "eval", "compile", "print"})
    assert called_attributes.isdisjoint(
        {
            "WinDLL",
            "CDLL",
            "OleDLL",
            "PyDLL",
            "getenv",
            "resolve",
            "absolute",
            "read_text",
            "write_text",
            "read_bytes",
            "write_bytes",
            "listdir",
            "scandir",
            "walk",
            "system",
            "popen",
        }
    )
    assert "PROGRAMDATA" not in source
    assert "C:/ProgramData" not in source
    assert "C:\\ProgramData" not in source
