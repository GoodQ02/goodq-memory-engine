from __future__ import annotations

import copy
import ctypes
from dataclasses import fields
import importlib
import pickle
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
