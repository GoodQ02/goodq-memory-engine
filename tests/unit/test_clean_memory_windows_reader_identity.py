from __future__ import annotations

import ast
import builtins
import ctypes
import dataclasses
import hashlib
import importlib
import inspect
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from steps.common.windows_security_mechanics import (
    WINDOWS_TOKEN_PROFILE_BASE,
    WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
    WindowsPrivilege,
    WindowsSid,
    WindowsSidRecord,
    WindowsTokenSnapshot,
    WindowsTokenStatistics,
)


def _load_module():
    return importlib.import_module(
        "steps.common.clean_memory_windows_reader_identity"
    )


def _sid(authority: int, *subauthorities: int) -> WindowsSid:
    binary = (
        bytes((1, len(subauthorities)))
        + authority.to_bytes(6, "big")
        + b"".join(value.to_bytes(4, "little") for value in subauthorities)
    )
    numeric = "-".join(
        ("S", "1", str(authority), *(str(value) for value in subauthorities))
    )
    return WindowsSid(binary=binary, numeric=numeric)


_ADMIN_SID = _sid(5, 32, 544)
_USERS_SID = _sid(5, 32, 545)
_MEDIUM_INTEGRITY_SID = _sid(16, 8192)
_READER_SID = _sid(5, 21, 165, 4242)
_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "steps"
    / "common"
    / "clean_memory_windows_reader_identity.py"
)

_DEFAULT_CANONICAL_BYTES = (
    b'{"elevation":{"is_elevated":false,"type":"default"},'
    b'"groups":[{"attributes":"00000007","sid":"S-1-5-32-545"}],'
    b'"has_restrictions":false,"impersonation_level":null,'
    b'"integrity_rid":"00002000","integrity_sid":"S-1-16-8192",'
    b'"is_app_container":false,'
    b'"privileges":[{"attributes":"00000002",'
    b'"luid":"0000000000000017"}],"restricted_sids":[],'
    b'"schema":"goodq.clean-memory-windows-reader-identity.v1",'
    b'"token_source":"process","token_statistics":{'
    b'"authentication_id":"0000000000000002","expiration_time":"0",'
    b'"group_count":"1","modified_id":"0000000000000004",'
    b'"privilege_count":"1","token_id":"0000000000000001"},'
    b'"token_type":"primary","ui_access":false,'
    b'"user_sid":"S-1-5-21-165-4242"}'
)
_DEFAULT_DIGEST = "585d9f4a8a6e9686b4e35ae6517e97ded3c2b456c1035b70920e023536b69cc9"
_LIMITED_DIGEST = "159cd0c074f014691cd50a26ec2b1bb51c7a79099ef4a469c610be01133362fc"
_COMPLEX_CANONICAL_BYTES = (
    b'{"elevation":{"is_elevated":false,"type":"default"},'
    b'"groups":[{"attributes":"abcdef01","sid":"S-1-5-21-2"},'
    b'{"attributes":"00000010","sid":"S-1-5-32-545"}],'
    b'"has_restrictions":false,"impersonation_level":null,'
    b'"integrity_rid":"00002000","integrity_sid":"S-1-16-8192",'
    b'"is_app_container":false,'
    b'"privileges":[{"attributes":"abcdef01",'
    b'"luid":"0000000100000002"},{"attributes":"00000010",'
    b'"luid":"fedcba9876543210"}],"restricted_sids":[],'
    b'"schema":"goodq.clean-memory-windows-reader-identity.v1",'
    b'"token_source":"process","token_statistics":{'
    b'"authentication_id":"fedcba9876543210",'
    b'"expiration_time":"-123456789","group_count":"12",'
    b'"modified_id":"0123456789abcdef","privilege_count":"34",'
    b'"token_id":"abcdef0123456789"},"token_type":"primary",'
    b'"ui_access":false,"user_sid":"S-1-5-21-165-4242"}'
)


def _snapshot(**changes: object) -> WindowsTokenSnapshot:
    baseline = WindowsTokenSnapshot(
        statistics=WindowsTokenStatistics(
            token_id=1,
            authentication_id=2,
            expiration_time=0,
            token_type=1,
            dynamic_charged=0,
            dynamic_available=0,
            group_count=1,
            privilege_count=1,
            modified_id=4,
        ),
        user_sid=_READER_SID,
        groups=(WindowsSidRecord(sid=_USERS_SID, attributes=7),),
        privileges=(WindowsPrivilege(luid=0x17, attributes=2),),
        restricted_sids=(),
        elevation_type=1,
        is_elevated=False,
        has_restrictions=False,
        integrity=WindowsSidRecord(
            sid=_MEDIUM_INTEGRITY_SID,
            attributes=0x20,
        ),
        ui_access=False,
        mandatory_policy=None,
        is_app_container=False,
    )
    return dataclasses.replace(baseline, **changes)


class _IntSubclass(int):
    pass


class _StrSubclass(str):
    pass


class _SnapshotSubclass(WindowsTokenSnapshot):
    pass


def _invoke(
    module,
    operation: str,
    snapshot: object,
    *,
    profile: object = WINDOWS_TOKEN_PROFILE_BASE,
    change_notify_luid: object = 0x17,
):
    return getattr(module, operation)(
        snapshot,
        profile=profile,
        change_notify_luid=change_notify_luid,
    )


def test_reader_identity_module_exports_only_the_digest_authority() -> None:
    module = _load_module()

    assert module.__all__ == (
        "CleanMemoryWindowsReaderIdentityError",
        "validate_clean_memory_windows_reader_identity",
        "clean_memory_windows_reader_identity_sha256",
    )


def test_policy_error_and_function_signatures_are_exact() -> None:
    module = _load_module()

    error = module.CleanMemoryWindowsReaderIdentityError()
    assert isinstance(error, ValueError)
    assert str(error) == (
        "Clean-memory Windows reader identity is not authorized"
    )
    assert error.args == (str(error),)
    with pytest.raises(TypeError):
        module.CleanMemoryWindowsReaderIdentityError("caller detail")

    for name in (
        "validate_clean_memory_windows_reader_identity",
        "clean_memory_windows_reader_identity_sha256",
    ):
        signature = inspect.signature(getattr(module, name))
        assert tuple(signature.parameters) == (
            "snapshot",
            "profile",
            "change_notify_luid",
        )
        assert signature.parameters["snapshot"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        assert signature.parameters["profile"].kind is inspect.Parameter.KEYWORD_ONLY
        assert signature.parameters["change_notify_luid"].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize(
    "operation",
    [
        "validate_clean_memory_windows_reader_identity",
        "clean_memory_windows_reader_identity_sha256",
    ],
)
@pytest.mark.parametrize(
    "snapshot",
    [object(), object.__new__(_SnapshotSubclass)],
    ids=["object", "snapshot-subclass"],
)
def test_snapshot_must_be_the_exact_mechanics_type(
    operation: str,
    snapshot: object,
) -> None:
    module = _load_module()

    with pytest.raises(TypeError):
        _invoke(module, operation, snapshot)


@pytest.mark.parametrize(
    "operation",
    [
        "validate_clean_memory_windows_reader_identity",
        "clean_memory_windows_reader_identity_sha256",
    ],
)
@pytest.mark.parametrize(
    ("profile", "exception_type"),
    [
        pytest.param(None, TypeError, id="none"),
        pytest.param(True, TypeError, id="bool"),
        pytest.param(_StrSubclass(WINDOWS_TOKEN_PROFILE_BASE), TypeError, id="subclass"),
        pytest.param("unknown", ValueError, id="unknown"),
    ],
)
def test_profile_fence_is_exact_and_closed(
    operation: str,
    profile: object,
    exception_type: type[Exception],
) -> None:
    module = _load_module()

    with pytest.raises(exception_type) as exc_info:
        _invoke(
            module,
            operation,
            _snapshot(),
            profile=profile,
        )

    assert "\\" not in str(exc_info.value)
    assert "/" not in str(exc_info.value)


@pytest.mark.parametrize(
    "operation",
    [
        "validate_clean_memory_windows_reader_identity",
        "clean_memory_windows_reader_identity_sha256",
    ],
)
@pytest.mark.parametrize(
    ("change_notify_luid", "exception_type"),
    [
        pytest.param(True, TypeError, id="bool"),
        pytest.param(_IntSubclass(0x17), TypeError, id="subclass"),
        pytest.param(23.0, TypeError, id="float"),
        pytest.param(-1, ValueError, id="negative"),
        pytest.param(2**64, ValueError, id="overflow"),
    ],
)
def test_change_notify_luid_is_exact_unsigned_64_bit(
    operation: str,
    change_notify_luid: object,
    exception_type: type[Exception],
) -> None:
    module = _load_module()

    with pytest.raises(exception_type) as exc_info:
        _invoke(
            module,
            operation,
            _snapshot(),
            change_notify_luid=change_notify_luid,
        )

    assert "\\" not in str(exc_info.value)
    assert "/" not in str(exc_info.value)


_ACCEPTED_SNAPSHOTS = (
    pytest.param(_snapshot(), id="default"),
    pytest.param(
        _snapshot(elevation_type=3, has_restrictions=True),
        id="limited",
    ),
    pytest.param(
        _snapshot(
            groups=(
                WindowsSidRecord(sid=_USERS_SID, attributes=7),
                WindowsSidRecord(sid=_ADMIN_SID, attributes=0x10),
            )
        ),
        id="admin-deny-only",
    ),
    pytest.param(
        _snapshot(
            privileges=(
                WindowsPrivilege(luid=0x17, attributes=2),
                WindowsPrivilege(luid=0x99, attributes=0),
            )
        ),
        id="foreign-privilege-disabled",
    ),
    pytest.param(_snapshot(groups=(), privileges=()), id="empty-records"),
    pytest.param(
        dataclasses.replace(
            _snapshot(
                user_sid=_sid(5, 21, 999, 7),
                groups=(
                    WindowsSidRecord(
                        sid=_sid(5, 21, 3),
                        attributes=0xFFFFFFFF,
                    ),
                ),
                privileges=(
                    WindowsPrivilege(luid=0xAABBCCDD, attributes=0xFFFFFFFD),
                ),
                integrity=WindowsSidRecord(
                    sid=_MEDIUM_INTEGRITY_SID,
                    attributes=0xFFFFFFFF,
                ),
            ),
            statistics=dataclasses.replace(
                _snapshot().statistics,
                token_id=0xFFFFFFFFFFFFFFFF,
                authentication_id=0,
                expiration_time=-9,
                dynamic_charged=123,
                dynamic_available=456,
                group_count=99,
                privilege_count=77,
                modified_id=0x0102030405060708,
            ),
        ),
        id="non-authoritative-fields",
    ),
)


@pytest.mark.parametrize("snapshot", _ACCEPTED_SNAPSHOTS)
def test_exact_current_ordinary_reader_acceptance_is_preserved(
    snapshot: WindowsTokenSnapshot,
) -> None:
    module = _load_module()

    assert (
        module.validate_clean_memory_windows_reader_identity(
            snapshot,
            profile=WINDOWS_TOKEN_PROFILE_BASE,
            change_notify_luid=0x17,
        )
        is None
    )
    digest = module.clean_memory_windows_reader_identity_sha256(
        snapshot,
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0x17,
    )
    assert type(digest) is str
    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")


@pytest.mark.parametrize("change_notify_luid", [0, 2**64 - 1])
def test_unsigned_luid_boundaries_are_accepted_when_privilege_is_absent(
    change_notify_luid: int,
) -> None:
    module = _load_module()
    snapshot = _snapshot(privileges=())

    assert module.validate_clean_memory_windows_reader_identity(
        snapshot,
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=change_notify_luid,
    ) is None


_REJECTED_SNAPSHOTS = (
    pytest.param(
        dataclasses.replace(
            _snapshot(),
            statistics=dataclasses.replace(_snapshot().statistics, token_type=2),
        ),
        id="impersonation-token",
    ),
    pytest.param(_snapshot(elevation_type=2), id="full-elevation"),
    pytest.param(_snapshot(is_elevated=True), id="elevated"),
    pytest.param(
        _snapshot(
            restricted_sids=(
                WindowsSidRecord(sid=_sid(5, 12), attributes=0),
            )
        ),
        id="restricted-sid",
    ),
    pytest.param(
        _snapshot(
            integrity=WindowsSidRecord(sid=_sid(5, 8192), attributes=0x20)
        ),
        id="wrong-integrity",
    ),
    pytest.param(_snapshot(ui_access=True), id="ui-access"),
    pytest.param(_snapshot(is_app_container=True), id="app-container"),
    pytest.param(_snapshot(has_restrictions=True), id="default-restricted-pair"),
    pytest.param(
        _snapshot(elevation_type=3, has_restrictions=False),
        id="limited-unrestricted-pair",
    ),
    pytest.param(
        _snapshot(groups=(WindowsSidRecord(sid=_ADMIN_SID, attributes=0),)),
        id="admin-not-deny-only",
    ),
    pytest.param(
        _snapshot(groups=(WindowsSidRecord(sid=_ADMIN_SID, attributes=0x14),)),
        id="admin-enabled",
    ),
    pytest.param(
        _snapshot(
            privileges=(
                WindowsPrivilege(luid=0x17, attributes=2),
                WindowsPrivilege(luid=0x99, attributes=2),
            )
        ),
        id="foreign-enabled-privilege",
    ),
)


@pytest.mark.parametrize(
    "operation",
    [
        "validate_clean_memory_windows_reader_identity",
        "clean_memory_windows_reader_identity_sha256",
    ],
)
@pytest.mark.parametrize("snapshot", _REJECTED_SNAPSHOTS)
def test_every_intrinsically_untrusted_snapshot_uses_only_the_policy_error(
    operation: str,
    snapshot: WindowsTokenSnapshot,
) -> None:
    module = _load_module()

    with pytest.raises(module.CleanMemoryWindowsReaderIdentityError) as exc_info:
        _invoke(module, operation, snapshot)

    assert type(exc_info.value) is module.CleanMemoryWindowsReaderIdentityError
    assert str(exc_info.value) == (
        "Clean-memory Windows reader identity is not authorized"
    )


def test_change_notify_need_not_be_present_enabled_or_disabled() -> None:
    module = _load_module()
    snapshots = (
        _snapshot(privileges=()),
        _snapshot(privileges=(WindowsPrivilege(luid=0x17, attributes=0),)),
        _snapshot(privileges=(WindowsPrivilege(luid=0x17, attributes=2),)),
    )

    for snapshot in snapshots:
        assert module.validate_clean_memory_windows_reader_identity(
            snapshot,
            profile=WINDOWS_TOKEN_PROFILE_BASE,
            change_notify_luid=0x17,
        ) is None


def test_base_and_mandatory_profiles_have_the_exact_policy_fence() -> None:
    module = _load_module()
    base = _snapshot(mandatory_policy=None)
    mandatory_one = _snapshot(mandatory_policy=1)
    mandatory_three = _snapshot(mandatory_policy=3)

    assert module.validate_clean_memory_windows_reader_identity(
        base,
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0x17,
    ) is None
    for snapshot in (mandatory_one, mandatory_three):
        assert module.validate_clean_memory_windows_reader_identity(
            snapshot,
            profile=WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
            change_notify_luid=0x17,
        ) is None

    rejected = (
        (mandatory_one, WINDOWS_TOKEN_PROFILE_BASE),
        (mandatory_three, WINDOWS_TOKEN_PROFILE_BASE),
        (base, WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY),
        (_snapshot(mandatory_policy=0), WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY),
        (_snapshot(mandatory_policy=2), WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY),
        (_snapshot(mandatory_policy=True), WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY),
        (
            _snapshot(mandatory_policy=_IntSubclass(1)),
            WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
        ),
    )
    for operation in (
        "validate_clean_memory_windows_reader_identity",
        "clean_memory_windows_reader_identity_sha256",
    ):
        for snapshot, profile in rejected:
            with pytest.raises(module.CleanMemoryWindowsReaderIdentityError):
                _invoke(
                    module,
                    operation,
                    snapshot,
                    profile=profile,
                    change_notify_luid=0x17,
                )


def test_default_and_limited_v1_digests_match_independent_golden_vectors() -> None:
    module = _load_module()
    default = module.clean_memory_windows_reader_identity_sha256(
        _snapshot(),
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0x17,
    )
    limited = module.clean_memory_windows_reader_identity_sha256(
        _snapshot(elevation_type=3, has_restrictions=True),
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0x17,
    )

    assert hashlib.sha256(_DEFAULT_CANONICAL_BYTES).hexdigest() == _DEFAULT_DIGEST
    assert default == _DEFAULT_DIGEST
    assert limited == _LIMITED_DIGEST
    assert default != limited


def test_complex_v1_vector_locks_record_order_and_numeric_grammar() -> None:
    module = _load_module()
    baseline = _snapshot()
    snapshot = dataclasses.replace(
        baseline,
        statistics=dataclasses.replace(
            baseline.statistics,
            token_id=0xABCDEF0123456789,
            authentication_id=0xFEDCBA9876543210,
            expiration_time=-123456789,
            group_count=12,
            privilege_count=34,
            modified_id=0x0123456789ABCDEF,
        ),
        groups=(
            WindowsSidRecord(sid=_sid(5, 21, 2), attributes=0xABCDEF01),
            WindowsSidRecord(sid=_USERS_SID, attributes=0x10),
        ),
        privileges=(
            WindowsPrivilege(luid=0x0000000100000002, attributes=0xABCDEF01),
            WindowsPrivilege(luid=0xFEDCBA9876543210, attributes=0x10),
        ),
    )

    digest = module.clean_memory_windows_reader_identity_sha256(
        snapshot,
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0,
    )

    assert digest == hashlib.sha256(_COMPLEX_CANONICAL_BYTES).hexdigest()


def test_mandatory_policy_profile_and_luid_argument_stay_outside_v1() -> None:
    module = _load_module()
    base = _snapshot(mandatory_policy=None, privileges=())
    policy_one = _snapshot(mandatory_policy=1, privileges=())
    policy_three = _snapshot(mandatory_policy=3, privileges=())

    assert base != policy_one
    assert policy_one != policy_three
    digests = {
        module.clean_memory_windows_reader_identity_sha256(
            base,
            profile=WINDOWS_TOKEN_PROFILE_BASE,
            change_notify_luid=0,
        ),
        module.clean_memory_windows_reader_identity_sha256(
            base,
            profile=WINDOWS_TOKEN_PROFILE_BASE,
            change_notify_luid=2**64 - 1,
        ),
        module.clean_memory_windows_reader_identity_sha256(
            policy_one,
            profile=WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
            change_notify_luid=0,
        ),
        module.clean_memory_windows_reader_identity_sha256(
            policy_three,
            profile=WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY,
            change_notify_luid=0,
        ),
    }
    assert len(digests) == 1


def test_only_frozen_v1_fields_can_change_the_digest() -> None:
    module = _load_module()
    baseline = _snapshot()
    omitted_only = dataclasses.replace(
        baseline,
        statistics=dataclasses.replace(
            baseline.statistics,
            dynamic_charged=999,
            dynamic_available=123,
        ),
        integrity=dataclasses.replace(baseline.integrity, attributes=0xFFFFFFFF),
    )
    alternate_privilege = _snapshot(
        privileges=(WindowsPrivilege(luid=0x99, attributes=2),)
    )

    baseline_digest = module.clean_memory_windows_reader_identity_sha256(
        baseline,
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0x17,
    )
    assert module.clean_memory_windows_reader_identity_sha256(
        omitted_only,
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0x17,
    ) == baseline_digest
    assert module.clean_memory_windows_reader_identity_sha256(
        alternate_privilege,
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0x99,
    ) != baseline_digest


def test_digest_only_surface_exposes_no_projection_preimage_or_result() -> None:
    module = _load_module()

    for name in (
        "READER_IDENTITY_SCHEMA",
        "WINDOWS_READER_IDENTITY_SCHEMA",
        "reader_identity_projection",
        "canonical_reader_identity_bytes",
        "WindowsReaderIdentityResult",
        "ReaderIdentityResult",
        "_intrinsically_validate_token",
    ):
        assert not hasattr(module, name)
    assert not any(
        token in exported.lower()
        for exported in module.__all__
        for token in ("schema", "projection", "preimage", "bytes", "result")
    )


def test_import_and_invocation_are_pure_and_silent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    def forbidden(*_args, **_kwargs):
        pytest.fail("reader identity policy attempted an external capability")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    before_path = tuple(sys.path)
    sys.modules.pop("steps.common.clean_memory_windows_reader_identity", None)

    module = importlib.import_module(
        "steps.common.clean_memory_windows_reader_identity"
    )
    module.validate_clean_memory_windows_reader_identity(
        _snapshot(),
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0x17,
    )
    module.clean_memory_windows_reader_identity_sha256(
        _snapshot(),
        profile=WINDOWS_TOKEN_PROFILE_BASE,
        change_notify_luid=0x17,
    )

    assert tuple(sys.path) == before_path
    assert capsys.readouterr() == ("", "")
    assert caplog.records == []


def test_source_dependency_and_native_capability_boundary_is_closed() -> None:
    source = _MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    direct_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    from_imports = {
        node.module: {alias.name for alias in node.names}
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert direct_imports == {"hashlib", "json"}
    assert from_imports == {
        "__future__": {"annotations"},
        "steps.common.windows_security_mechanics": {
            "WINDOWS_TOKEN_PROFILE_BASE",
            "WINDOWS_TOKEN_PROFILE_MANDATORY_POLICY",
            "WindowsTokenSnapshot",
        },
    }
    assert "cli" not in source
    assert "windows_held_handle" not in source
    assert "WinDLL" not in source
    assert "subprocess" not in source
    assert "socket" not in source
    assert source.count("goodq.clean-memory-windows-reader-identity.v1") == 1
