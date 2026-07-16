from __future__ import annotations

import ast
import base64
import builtins
import copy
from dataclasses import FrozenInstanceError
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from tests.unit.test_clean_memory_cli import EPOCH_ID, _config


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "cli" / "clean_memory_protected_membership.py"
MANIFEST_ROLES = (
    "backup_root",
    "download_cache",
    "public_checkout",
    "qdrant_service_logs",
    "recovery_root",
    "reports_root",
    "repository",
    "source_media",
)
CONFIGURED_MEMBER_POLICY = {
    "archive_root": ("directory", "allow_absent"),
    "control_root": ("directory", "required"),
    "data_root": ("directory", "required"),
    "failed_media": ("directory", "allow_absent"),
    "import_media": ("directory", "allow_absent"),
    "model_cache": ("directory", "allow_absent"),
    "processed_media": ("directory", "allow_absent"),
    "processing_media": ("directory", "allow_absent"),
    "qdrant_storage": ("directory", "allow_absent"),
    "watchdog_state": ("regular_file", "allow_absent"),
}
FULL_ROLE_ORDER = (
    "archive_root",
    "backup_root",
    "control_root",
    "data_root",
    "download_cache",
    "failed_media",
    "import_media",
    "model_cache",
    "processed_media",
    "processing_media",
    "public_checkout",
    "qdrant_service_logs",
    "qdrant_storage",
    "recovery_root",
    "reports_root",
    "repository",
    "source_media",
    "watchdog_state",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _manifest(*, root: str = "/protected") -> dict[str, object]:
    return {
        "schema": "goodq.clean-memory-protected-authority.v1",
        "roles": [
            {
                "role": role,
                "members": [
                    {
                        "member_id": "primary",
                        "absolute_path": f"{root}/{role}",
                        "object_kind": "directory",
                        "presence": "required",
                    }
                ],
            }
            for role in MANIFEST_ROLES
        ],
    }


def _resolved_configuration(*, data_root: str = "/authority/GoodQ_Data"):
    module = importlib.import_module("cli.clean_memory")
    return module.resolve_plan_configuration(
        _config(data_root=data_root), requested_epoch_id=EPOCH_ID
    )


def _project(
    *,
    manifest: dict[str, object] | None = None,
    manifest_bytes: bytes | None = None,
    data_root: str = "/authority/GoodQ_Data",
):
    module = importlib.import_module("cli.clean_memory_protected_membership")
    if manifest_bytes is None:
        manifest_bytes = _canonical_bytes(
            manifest if manifest is not None else _manifest()
        )
    return module.project_protected_membership(
        _resolved_configuration(data_root=data_root),
        manifest_bytes=manifest_bytes,
    )


def test_module_exists_with_exact_public_api() -> None:
    assert MODULE_PATH.is_file(), "protected-membership projection is not implemented"
    module = importlib.import_module("cli.clean_memory_protected_membership")
    assert module.__all__ == (
        "PROTECTED_MEMBERSHIP_SCHEMA",
        "ProtectedMembershipProjection",
        "project_protected_membership",
    )
    assert all(hasattr(module, name) for name in module.__all__)
    assert module.PROTECTED_MEMBERSHIP_SCHEMA == (
        "goodq.clean-memory-protected-membership.v1"
    )
    assert tuple(inspect.signature(module.project_protected_membership).parameters) == (
        "configuration",
        "manifest_bytes",
    )
    assert inspect.signature(module.project_protected_membership).parameters[
        "manifest_bytes"
    ].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize(
    ("data_root", "manifest_root", "expected_flavor"),
    [
        ("/authority/GoodQ_Data", "/protected", "posix"),
        ("R:/GOODCUBE/GoodQ_Data", "S:/Protected", "windows"),
    ],
)
def test_membership_delegates_once_with_original_bytes_and_resolved_flavor(
    monkeypatch: pytest.MonkeyPatch,
    data_root: str,
    manifest_root: str,
    expected_flavor: str,
) -> None:
    module = importlib.import_module("cli.clean_memory_protected_membership")
    manifest = _manifest(root=manifest_root)
    manifest_bytes = b"opaque original manifest bytes"
    sentinel_digest = "a" * 64
    calls: list[tuple[bytes, str]] = []
    manifest_accesses = 0

    class FakeValidatedManifest:
        manifest_sha256 = sentinel_digest

        @property
        def manifest(self) -> dict[str, object]:
            nonlocal manifest_accesses
            manifest_accesses += 1
            return copy.deepcopy(manifest)

    def audited_validator(candidate: bytes, *, path_flavor: str):
        calls.append((candidate, path_flavor))
        return FakeValidatedManifest()

    monkeypatch.setattr(
        module,
        "_validate_protected_manifest",
        audited_validator,
        raising=False,
    )

    result = module.project_protected_membership(
        _resolved_configuration(data_root=data_root),
        manifest_bytes=manifest_bytes,
    )

    assert len(calls) == 1
    assert calls[0][0] is manifest_bytes
    assert calls[0][1] == expected_flavor
    assert manifest_accesses == 1
    assert result.projection["manifest"]["sha256"] == sentinel_digest
    projected_roles = {
        record["role"]: record["members"]
        for record in result.projection["protected_roles"]
    }
    assert projected_roles["backup_root"] == manifest["roles"][0]["members"]


def test_membership_preserves_bytes_and_configuration_failure_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration_module = importlib.import_module("cli.clean_memory")
    module = importlib.import_module("cli.clean_memory_protected_membership")
    validator_calls = 0

    def forbidden_validator(*_args: object, **_kwargs: object) -> None:
        nonlocal validator_calls
        validator_calls += 1
        raise AssertionError("manifest validator ran out of order")

    monkeypatch.setattr(
        module,
        "_validate_protected_manifest",
        forbidden_validator,
        raising=False,
    )
    with monkeypatch.context() as role_patch:
        role_patch.setattr(module, "_PROTECTED_BOUNDARY_ROLES", ())
        with pytest.raises(TypeError) as bytes_error:
            module.project_protected_membership(
                object(),
                manifest_bytes=bytearray(b"x"),
            )
        assert str(bytes_error.value) == "manifest_bytes must be exact bytes"
        with pytest.raises(ValueError) as size_error:
            module.project_protected_membership(object(), manifest_bytes=b"")
        assert str(size_error.value) == (
            "Manifest bytes exceed the protocol size boundary"
        )
        with pytest.raises(ValueError) as oversized_error:
            module.project_protected_membership(
                object(),
                manifest_bytes=b"x" * (4_194_304 + 1),
            )
        assert str(oversized_error.value) == (
            "Manifest bytes exceed the protocol size boundary"
        )
        with pytest.raises(ValueError) as role_error:
            module.project_protected_membership(
                object(),
                manifest_bytes=_canonical_bytes(_manifest()),
            )
    assert str(role_error.value) == (
        "Protected role authority does not match the selected contract"
    )

    projection = _resolved_configuration().projection
    projection["schema"] = "goodq.clean-memory-configuration.v2"
    forged = configuration_module.ResolvedPlanConfiguration._from_projection(
        projection
    )
    wrong_manifest = _manifest()
    wrong_manifest["schema"] = "goodq.clean-memory-protected-authority.v2"
    with pytest.raises(ValueError) as configuration_error:
        module.project_protected_membership(
            forged,
            manifest_bytes=_canonical_bytes(wrong_manifest),
        )
    assert str(configuration_error.value) == "Configuration projection has the wrong schema"
    assert validator_calls == 0


def test_membership_source_has_exact_shared_manifest_ownership_boundary() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    shared_imports = [
        tuple((alias.name, alias.asname) for alias in node.names)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "steps.common.clean_memory_protected_manifest"
    ]
    assert shared_imports == [
        (
            (
                "PROTECTED_MANIFEST_CHILD_NAME",
                "_PROTECTED_MANIFEST_CHILD_NAME",
            ),
            (
                "PROTECTED_MANIFEST_MAX_BYTES",
                "_PROTECTED_MANIFEST_MAX_BYTES",
            ),
            (
                "PROTECTED_MANIFEST_ROLE_ORDER",
                "_PROTECTED_MANIFEST_ROLE_ORDER",
            ),
            ("validate_protected_manifest", "_validate_protected_manifest"),
        )
    ]

    forbidden_assignments = {
        "_MANIFEST_SCHEMA",
        "_MANIFEST_CHILD_NAME",
        "_MAX_MANIFEST_BYTES",
        "_MANIFEST_ROLE_ORDER",
        "_MAX_PATH_BYTES",
        "_MAX_MEMBERS_PER_ROLE",
        "_MAX_MEMBERS_TOTAL",
        "_MEMBER_ID_RE",
    }
    assigned_names = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else (node.target,)
        )
        if isinstance(target, ast.Name)
    }
    assert assigned_names.isdisjoint(forbidden_assignments)
    assert "_manifest_members" not in {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    assert "goodq.clean-memory-protected-authority.v1" not in {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and type(node.value) is str
    }
    assert "protected-boundaries.json" not in {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and type(node.value) is str
    }
    assert r"^[a-z][a-z0-9_]{0,63}$" not in {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and type(node.value) is str
    }
    assert not {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and type(node.value) is int
    }.intersection({4_194_304, 4_096, 64, 512})
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Tuple)
        and tuple(
            item.value
            for item in node.elts
            if isinstance(item, ast.Constant) and type(item.value) is str
        )
        == MANIFEST_ROLES
    ]
    assert tuple(
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    ) == (
        "_canonical_json_text",
        "_pairs_without_duplicates",
        "_reject_nonfinite",
        "_strict_json_text",
        "_validate_json_strings",
        "_contains_control",
        "_canonical_absolute_path",
        "_comparison_key",
        "_paths_overlap",
        "_configuration_snapshot",
        "_configured_members",
        "_validate_combined_scope",
        "project_protected_membership",
    )

    project_function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "project_protected_membership"
    )
    direct_calls = [
        node.func.id
        for node in ast.walk(project_function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert tuple(sorted(direct_calls)) == tuple(
        sorted(
            (
                "type",
                "len",
                "tuple",
                "_configuration_snapshot",
                "_configured_members",
                "_validate_protected_manifest",
                "set",
                "set",
                "_validate_combined_scope",
                "TypeError",
                "ValueError",
                "ValueError",
                "ValueError",
                "ValueError",
            )
        )
    )
    attribute_calls = [
        (node.func.value.id, node.func.attr)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node in set(ast.walk(project_function))
    ]
    assert attribute_calls == [
        ("ProtectedMembershipProjection", "_from_projection")
    ]


def test_valid_manifest_projects_exact_detached_membership() -> None:
    configuration_module = importlib.import_module("cli.clean_memory")
    module = importlib.import_module("cli.clean_memory_protected_membership")
    configuration = configuration_module.resolve_plan_configuration(
        _config(), requested_epoch_id=EPOCH_ID
    )
    manifest_bytes = _canonical_bytes(_manifest())

    result = module.project_protected_membership(
        configuration, manifest_bytes=manifest_bytes
    )
    projection = result.projection

    assert set(projection) == {
        "configuration_scope_sha256",
        "manifest",
        "path_flavor",
        "protected_roles",
        "schema",
    }
    assert projection["schema"] == module.PROTECTED_MEMBERSHIP_SCHEMA
    assert projection["configuration_scope_sha256"] == (
        configuration.configuration_scope_sha256
    )
    assert projection["manifest"] == {
        "child_name": "protected-boundaries.json",
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }
    assert projection["path_flavor"] == "posix"

    configured = {
        record["role"]: record["paths"]
        for record in configuration.projection["configured_protected_paths"]
    }
    manifest = {
        record["role"]: record["members"] for record in _manifest()["roles"]
    }
    expected_roles = []
    for role in FULL_ROLE_ORDER:
        if role in configured:
            kind, presence = CONFIGURED_MEMBER_POLICY[role]
            members = [
                {
                    "absolute_path": path,
                    "member_id": f"configured_{index:02d}",
                    "object_kind": kind,
                    "presence": presence,
                }
                for index, path in enumerate(configured[role])
            ]
        else:
            members = manifest[role]
        expected_roles.append({"members": members, "role": role})
    assert projection["protected_roles"] == expected_roles

    canonical_projection = _canonical_bytes(projection)
    assert result.protected_membership_scope_sha256 == hashlib.sha256(
        canonical_projection
    ).hexdigest()
    projection["protected_roles"][0]["members"][0]["member_id"] = "tampered"
    assert result.projection["protected_roles"] == expected_roles
    assert "/protected/" not in repr(result)


@pytest.mark.parametrize("mutation", ["detached_control_root", "watchdog_reorder"])
def test_forged_consumed_configuration_semantics_are_rejected(mutation: str) -> None:
    configuration_module = importlib.import_module("cli.clean_memory")
    module = importlib.import_module("cli.clean_memory_protected_membership")
    valid = configuration_module.resolve_plan_configuration(
        _config(), requested_epoch_id=EPOCH_ID
    )
    projection = valid.projection
    configured = {
        record["role"]: record
        for record in projection["configured_protected_paths"]
    }
    if mutation == "detached_control_root":
        configured["control_root"]["paths"] = ["/detached/control"]
        projection["logical_paths"]["candidate_evidence_root"] = (
            "/detached/control/clean_memory"
        )
    else:
        configured["watchdog_state"]["paths"].reverse()
    forged = configuration_module.ResolvedPlanConfiguration._from_projection(
        projection
    )

    with pytest.raises(ValueError):
        module.project_protected_membership(
            forged, manifest_bytes=_canonical_bytes(_manifest())
        )


def test_exact_input_types_and_result_immutability() -> None:
    configuration_module = importlib.import_module("cli.clean_memory")
    module = importlib.import_module("cli.clean_memory_protected_membership")
    configuration = _resolved_configuration()
    manifest_bytes = _canonical_bytes(_manifest())

    class ConfigurationSubclass(configuration_module.ResolvedPlanConfiguration):
        pass

    class BytesSubclass(bytes):
        pass

    for invalid_configuration in ({}, ConfigurationSubclass()):
        with pytest.raises(TypeError):
            module.project_protected_membership(
                invalid_configuration, manifest_bytes=manifest_bytes
            )
    for invalid_bytes in (
        manifest_bytes.decode("utf-8"),
        bytearray(manifest_bytes),
        memoryview(manifest_bytes),
        BytesSubclass(manifest_bytes),
    ):
        with pytest.raises(TypeError):
            module.project_protected_membership(
                configuration, manifest_bytes=invalid_bytes
            )

    result = module.project_protected_membership(
        configuration, manifest_bytes=manifest_bytes
    )
    with pytest.raises(FrozenInstanceError):
        result.protected_membership_scope_sha256 = "0" * 64
    first = result.projection
    first["manifest"]["sha256"] = "0" * 64
    assert result.projection["manifest"]["sha256"] != "0" * 64
    assert "/protected/" not in repr(result)


@pytest.mark.parametrize(
    "invalid_bytes",
    [
        b"",
        b"\xff",
        b"\xef\xbb\xbf{}",
        b"{}\n",
        b"{}{}",
        b"[]",
        b'{"roles":[],"roles":[],"schema":"goodq.clean-memory-protected-authority.v1"}',
        b'{"roles":[],"schema":NaN}',
        b'{"schema":"goodq.clean-memory-protected-authority.v1","roles":[]}',
    ],
)
def test_noncanonical_manifest_bytes_are_rejected(invalid_bytes: bytes) -> None:
    with pytest.raises(ValueError):
        _project(manifest_bytes=invalid_bytes)


def test_semantically_valid_noncanonical_manifest_encodings_are_rejected() -> None:
    manifest = _manifest()
    canonical = _canonical_bytes(manifest)
    duplicate_member_key = canonical.replace(
        b'"presence":"required"',
        b'"presence":"required","presence":"required"',
        1,
    )
    escaped_slash = canonical.replace(b"/protected/", b"\\/protected/", 1)
    variants = (
        canonical + b"\n",
        b"\xef\xbb\xbf" + canonical,
        json.dumps(manifest, ensure_ascii=False, sort_keys=False).encode("utf-8"),
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode(
            "utf-8"
        ),
        duplicate_member_key,
        escaped_slash,
    )
    assert duplicate_member_key != canonical
    assert escaped_slash != canonical
    for invalid_bytes in variants:
        with pytest.raises(ValueError):
            _project(manifest_bytes=invalid_bytes)


def test_oversized_manifest_is_rejected_before_json_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("cli.clean_memory_protected_membership")
    configuration = _resolved_configuration()

    def forbidden_loads(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("JSON parsing ran before the size gate")

    monkeypatch.setattr(module.json, "loads", forbidden_loads)
    with pytest.raises(ValueError, match="size boundary"):
        module.project_protected_membership(
            configuration, manifest_bytes=b"x" * (4_194_304 + 1)
        )


def test_deeply_nested_manifest_is_a_redacted_validation_failure() -> None:
    invalid_bytes = (
        b'{"roles":'
        + (b"[" * 2_000)
        + b"0"
        + (b"]" * 2_000)
        + b',"schema":"goodq.clean-memory-protected-authority.v1"}'
    )
    with pytest.raises(ValueError, match="canonical JSON"):
        _project(manifest_bytes=invalid_bytes)


def test_noncanonical_strings_and_errors_do_not_expose_paths() -> None:
    invalid = copy.deepcopy(_manifest())
    canary = "/SECRET_PATH_CANARY/e\u0301"
    invalid["roles"][0]["members"][0]["absolute_path"] = canary
    with pytest.raises(ValueError) as exc_info:
        _project(manifest=invalid)
    assert canary not in str(exc_info.value)


@pytest.mark.parametrize(
    "mutation",
    [
        "top_missing",
        "top_extra",
        "wrong_schema",
        "role_missing",
        "role_extra",
        "role_reordered",
        "role_record_extra",
        "members_empty",
        "members_too_many",
        "member_missing",
        "member_extra",
        "member_id_invalid",
        "member_ids_duplicate",
        "member_ids_reordered",
        "wrong_kind",
        "wrong_presence",
        "path_too_long",
    ],
)
def test_manifest_schema_census_and_member_contract_are_exact(mutation: str) -> None:
    manifest = copy.deepcopy(_manifest())
    first_role = manifest["roles"][0]
    first_member = first_role["members"][0]
    if mutation == "top_missing":
        del manifest["schema"]
    elif mutation == "top_extra":
        manifest["extra"] = False
    elif mutation == "wrong_schema":
        manifest["schema"] = "goodq.clean-memory-protected-authority.v2"
    elif mutation == "role_missing":
        manifest["roles"].pop()
    elif mutation == "role_extra":
        manifest["roles"].append(copy.deepcopy(first_role))
    elif mutation == "role_reordered":
        manifest["roles"][0], manifest["roles"][1] = (
            manifest["roles"][1],
            manifest["roles"][0],
        )
    elif mutation == "role_record_extra":
        first_role["extra"] = False
    elif mutation == "members_empty":
        first_role["members"] = []
    elif mutation == "members_too_many":
        first_role["members"] = [
            {
                **first_member,
                "member_id": f"member_{index:02d}",
                "absolute_path": f"/protected/backup_root/member_{index:02d}",
            }
            for index in range(65)
        ]
    elif mutation == "member_missing":
        del first_member["presence"]
    elif mutation == "member_extra":
        first_member["extra"] = False
    elif mutation == "member_id_invalid":
        first_member["member_id"] = "9invalid"
    elif mutation == "member_ids_duplicate":
        first_role["members"].append(copy.deepcopy(first_member))
    elif mutation == "member_ids_reordered":
        second = {
            **first_member,
            "member_id": "alpha",
            "absolute_path": "/protected/backup_root/alpha",
        }
        first_role["members"].append(second)
    elif mutation == "wrong_kind":
        first_member["object_kind"] = "regular_file"
    elif mutation == "wrong_presence":
        first_member["presence"] = "optional"
    else:
        first_member["absolute_path"] = "/" + ("a" * 4_096)

    with pytest.raises(ValueError):
        _project(manifest=manifest)


def test_manifest_protocol_count_and_path_boundaries_are_accepted() -> None:
    manifest = copy.deepcopy(_manifest())
    for role_record in manifest["roles"]:
        role = role_record["role"]
        role_record["members"] = [
            {
                "absolute_path": f"/protected/{role}/member_{index:02d}",
                "member_id": f"member_{index:02d}",
                "object_kind": "directory",
                "presence": "allow_absent" if index % 2 else "required",
            }
            for index in range(64)
        ]
    manifest["roles"][0]["members"][0]["absolute_path"] = "/" + ("a" * 4_095)

    projection = _project(manifest=manifest).projection

    assert sum(
        len(role["members"]) for role in projection["protected_roles"]
    ) == 11 + 512
    assert (
        len(projection["protected_roles"][1]["members"][0]["absolute_path"].encode())
        == 4_096
    )


@pytest.mark.parametrize(
    "invalid_path",
    [
        "relative/path",
        "/",
        "/protected/.",
        "/protected/..",
        "/protected//child",
        "/protected/child/",
        "/protected\\child",
        "/protected/${ROOT}",
        "/protected/${ROOT-default}",
        "/protected/${ROOT:=default}",
        "/protected/${ROOT:+default}",
        "/protected/${ROOT:?default}",
        "/protected/${ROOT",
        "/protected/$ROOT",
        "/protected/%ROOT%",
        "/protected/control\u0085character",
        "R:/protected",
    ],
)
def test_posix_manifest_paths_are_reject_on_change(invalid_path: str) -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["roles"][0]["members"][0]["absolute_path"] = invalid_path
    with pytest.raises(ValueError):
        _project(manifest=manifest)


@pytest.mark.parametrize(
    "invalid_path",
    [
        "s:/protected/backup",
        "S:/",
        "//server/share",
        "\\\\?\\S:\\protected\\backup",
        "S:\\protected\\backup",
        "S:/protected//backup",
        "S:/protected/backup/",
        "S:/protected/./backup",
        "S:/protected/../backup",
        "S:/protected/CON",
        "S:/protected/com1.txt",
        "S:/protected/COM¹",
        "S:/protected/LPT².txt",
        "S:/protected/trailing.",
        "S:/protected/trailing ",
        "S:/protected/inva?id",
        "S:/protected/%ROOT%",
        "/protected/backup",
    ],
)
def test_windows_manifest_paths_are_reject_on_change(invalid_path: str) -> None:
    manifest = copy.deepcopy(_manifest(root="S:/protected"))
    manifest["roles"][0]["members"][0]["absolute_path"] = invalid_path
    with pytest.raises(ValueError):
        _project(manifest=manifest, data_root="R:/GOODCUBE/GoodQ_Data")


def test_windows_paths_are_preserved_exactly() -> None:
    manifest = _manifest(root="S:/Protected")
    result = _project(
        manifest=manifest, data_root="R:/GOODCUBE/GoodQ_Data"
    )
    projection = result.projection
    assert projection["path_flavor"] == "windows"
    assert projection["protected_roles"][1]["members"][0]["absolute_path"] == (
        "S:/Protected/backup_root"
    )


@pytest.mark.parametrize("alias_kind", ["exact", "configured", "windows_case"])
def test_duplicate_and_windows_alias_membership_is_rejected(alias_kind: str) -> None:
    if alias_kind == "windows_case":
        manifest = copy.deepcopy(_manifest(root="S:/Protected"))
        manifest["roles"][1]["members"][0]["absolute_path"] = (
            "S:/protected/BACKUP_ROOT"
        )
        data_root = "R:/GOODCUBE/GoodQ_Data"
    else:
        manifest = copy.deepcopy(_manifest())
        if alias_kind == "exact":
            manifest["roles"][1]["members"][0]["absolute_path"] = (
                manifest["roles"][0]["members"][0]["absolute_path"]
            )
        else:
            manifest["roles"][0]["members"][0]["absolute_path"] = (
                "/authority/models"
            )
        data_root = "/authority/GoodQ_Data"
    with pytest.raises(ValueError):
        _project(manifest=manifest, data_root=data_root)


@pytest.mark.parametrize(
    "overlap_path",
    [
        f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/memory.db",
        f"/authority/GoodQ_Data/epochs/{EPOCH_ID}",
        f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/memory.db/child",
        f"/authority/GoodQ_Data/epochs/{EPOCH_ID}/faiss/child",
        "/authority/GoodQ_Data/control/clean_memory",
        "/authority/GoodQ_Data/control/clean_memory/child",
    ],
)
def test_manifest_members_cannot_overlap_cleanup_or_evidence_scope(
    overlap_path: str,
) -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["roles"][0]["members"][0]["absolute_path"] = overlap_path
    with pytest.raises(ValueError):
        _project(manifest=manifest)


def test_intentional_protected_containment_is_preserved() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["roles"][0]["members"][0]["absolute_path"] = "/protected/shared"
    manifest["roles"][1]["members"][0]["absolute_path"] = (
        "/protected/shared/downloads"
    )
    manifest["roles"][2]["members"][0]["absolute_path"] = (
        "/authority/GoodQ_Data/control/operator_exports"
    )

    projection = _project(manifest=manifest).projection

    assert projection["protected_roles"][1]["members"][0]["absolute_path"] == (
        "/protected/shared"
    )
    assert projection["protected_roles"][4]["members"][0]["absolute_path"] == (
        "/protected/shared/downloads"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_schema",
        "extra_top_key",
        "unresolved_reorder",
        "configured_reorder",
        "configured_cardinality",
        "data_root_mismatch",
        "memory_sidecar_mismatch",
        "wrong_path_flavor",
    ],
)
def test_forged_configuration_consumed_shape_is_rejected(mutation: str) -> None:
    configuration_module = importlib.import_module("cli.clean_memory")
    module = importlib.import_module("cli.clean_memory_protected_membership")
    projection = _resolved_configuration().projection
    if mutation == "wrong_schema":
        projection["schema"] = "goodq.clean-memory-configuration.v2"
    elif mutation == "extra_top_key":
        projection["extra"] = False
    elif mutation == "unresolved_reorder":
        projection["unresolved_protected_roles"].reverse()
    elif mutation == "configured_reorder":
        projection["configured_protected_paths"][0:2] = reversed(
            projection["configured_protected_paths"][0:2]
        )
    elif mutation == "configured_cardinality":
        projection["configured_protected_paths"][0]["paths"].append(
            "/authority/archive_two"
        )
    elif mutation == "data_root_mismatch":
        projection["logical_paths"]["data_root"] = "/detached/GoodQ_Data"
    elif mutation == "memory_sidecar_mismatch":
        projection["logical_paths"]["memory_database_wal"] = (
            "/detached/memory.db-wal"
        )
    else:
        projection["logical_paths"]["faiss_root"] = "R:/foreign/faiss"
    forged = configuration_module.ResolvedPlanConfiguration._from_projection(
        projection
    )

    with pytest.raises(ValueError):
        module.project_protected_membership(
            forged, manifest_bytes=_canonical_bytes(_manifest())
        )


def test_configuration_canonical_bytes_and_digest_are_rechecked() -> None:
    module = importlib.import_module("cli.clean_memory_protected_membership")
    manifest_bytes = _canonical_bytes(_manifest())

    noncanonical = _resolved_configuration()
    object.__setattr__(
        noncanonical, "_projection_json", f"{noncanonical._projection_json}\n"
    )
    object.__setattr__(
        noncanonical,
        "configuration_scope_sha256",
        hashlib.sha256(noncanonical._projection_json.encode()).hexdigest(),
    )
    with pytest.raises(ValueError):
        module.project_protected_membership(
            noncanonical, manifest_bytes=manifest_bytes
        )

    digest_mismatch = _resolved_configuration()
    object.__setattr__(digest_mismatch, "configuration_scope_sha256", "0" * 64)
    with pytest.raises(ValueError):
        module.project_protected_membership(
            digest_mismatch, manifest_bytes=manifest_bytes
        )


def test_configuration_mutation_during_projection_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("cli.clean_memory_protected_membership")
    configuration = _resolved_configuration()
    original = module.ProtectedMembershipProjection._from_projection.__func__

    def mutate_after_result(cls, projection):
        result = original(cls, projection)
        object.__setattr__(configuration, "configuration_scope_sha256", "0" * 64)
        return result

    monkeypatch.setattr(
        module.ProtectedMembershipProjection,
        "_from_projection",
        classmethod(mutate_after_result),
    )
    with pytest.raises(ValueError, match="changed during"):
        module.project_protected_membership(
            configuration, manifest_bytes=_canonical_bytes(_manifest())
        )


def test_projection_digest_is_stable_sensitive_and_nonrecursive() -> None:
    base_manifest = _manifest()
    first = _project(manifest=base_manifest)
    second = _project(manifest=copy.deepcopy(base_manifest))
    changed_manifest = copy.deepcopy(base_manifest)
    changed_manifest["roles"][0]["members"][0]["presence"] = "allow_absent"
    changed = _project(manifest=changed_manifest)
    changed_configuration = _project(
        manifest=base_manifest, data_root="/alternate/GoodQ_Data"
    )

    assert first.protected_membership_scope_sha256 == (
        second.protected_membership_scope_sha256
    )
    assert len(
        {
            first.protected_membership_scope_sha256,
            changed.protected_membership_scope_sha256,
            changed_configuration.protected_membership_scope_sha256,
        }
    ) == 3
    assert "protected_membership_scope_sha256" not in first.projection


def test_caller_cannot_supply_trust_or_location_authority() -> None:
    module = importlib.import_module("cli.clean_memory_protected_membership")
    configuration = _resolved_configuration()
    manifest_bytes = _canonical_bytes(_manifest())
    for forbidden_name in (
        "manifest_path",
        "pin_evidence",
        "provenance",
        "no_overrides",
        "membership_projection",
    ):
        with pytest.raises(TypeError):
            module.project_protected_membership(
                configuration,
                manifest_bytes=manifest_bytes,
                **{forbidden_name: object()},
            )


def test_source_has_exact_project_import_boundary() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    plain_imports = tuple(
        sorted(
            (alias.name, alias.asname)
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
    )
    from_imports = tuple(
        sorted(
            (
                node.module,
                node.level,
                tuple((alias.name, alias.asname) for alias in node.names),
            )
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
    )
    assert plain_imports == (
        ("hashlib", None),
        ("json", None),
        ("re", None),
        ("unicodedata", None),
    )
    assert from_imports == (
        ("__future__", 0, (("annotations", None),)),
        (
            "cli.clean_memory",
            0,
            (("CONFIGURATION_SCHEMA", None), ("ResolvedPlanConfiguration", None)),
        ),
        ("dataclasses", 0, (("dataclass", None), ("field", None))),
        (
            "steps.common.clean_memory",
            0,
            (("PROTECTED_BOUNDARY_ROLES", "_PROTECTED_BOUNDARY_ROLES"),),
        ),
        (
            "steps.common.clean_memory_protected_manifest",
            0,
            (
                (
                    "PROTECTED_MANIFEST_CHILD_NAME",
                    "_PROTECTED_MANIFEST_CHILD_NAME",
                ),
                (
                    "PROTECTED_MANIFEST_MAX_BYTES",
                    "_PROTECTED_MANIFEST_MAX_BYTES",
                ),
                (
                    "PROTECTED_MANIFEST_ROLE_ORDER",
                    "_PROTECTED_MANIFEST_ROLE_ORDER",
                ),
                ("validate_protected_manifest", "_validate_protected_manifest"),
            ),
        ),
        ("typing", 0, (("Any", None),)),
    )
    dynamic_import_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    } & {"__import__", "eval", "exec"}
    dynamic_import_calls |= {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    } & {"exec_module", "import_module"}
    assert dynamic_import_calls == set()


def test_module_import_and_invocation_are_capability_free(tmp_path: Path) -> None:
    configuration = _resolved_configuration()
    manifest_bytes = _canonical_bytes(_manifest())
    script = r"""
import base64
import builtins
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

repo_root = sys.argv[1]
configuration_json = sys.argv[2]
configuration_digest = sys.argv[3]
manifest_bytes = base64.b64decode(sys.argv[4], validate=True)
sys.path.insert(0, repo_root)
before_path = tuple(sys.path)
before_env = dict(os.environ)
before_modules = set(sys.modules)

def forbidden(*_args, **_kwargs):
    raise AssertionError("forbidden capability used")

class GuardedEnvironment(dict):
    __getitem__ = forbidden
    __setitem__ = forbidden
    __delitem__ = forbidden
    __iter__ = forbidden
    __len__ = forbidden
    __contains__ = forbidden
    get = forbidden
    items = forbidden
    keys = forbidden
    values = forbidden

os.environ = GuardedEnvironment(before_env)
os.getenv = forbidden
builtins.open = forbidden
for name in (
    "getcwd", "chdir", "mkdir", "makedirs", "remove", "unlink", "rename",
    "replace", "chmod", "stat", "lstat", "readlink", "listdir", "scandir",
    "walk", "putenv", "unsetenv",
):
    if hasattr(os, name):
        setattr(os, name, forbidden)
for name in (
    "absolute", "cwd", "exists", "home", "is_dir", "is_file", "iterdir",
    "lstat", "mkdir", "open", "read_bytes", "read_text", "rename", "replace",
    "resolve", "rmdir", "stat", "touch", "unlink", "write_bytes", "write_text",
):
    if hasattr(Path, name):
        setattr(Path, name, forbidden)
socket.socket = forbidden
subprocess.run = forbidden
subprocess.Popen = forbidden

module = importlib.import_module("cli.clean_memory_protected_membership")
assert module.__all__ == (
    "PROTECTED_MEMBERSHIP_SCHEMA",
    "ProtectedMembershipProjection",
    "project_protected_membership",
)
assert tuple(sys.path) == before_path
forbidden_roots = {
    "ctypes", "httpx", "qdrant_client", "requests", "win32api", "win32security",
    "steps.common.config_loader", "cli.clean_memory_filesystem",
}
new_modules = set(sys.modules) - before_modules
assert not {
    name for name in new_modules
    if name in forbidden_roots or name.split(".", 1)[0] in forbidden_roots
}

configuration = object.__new__(module.ResolvedPlanConfiguration)
object.__setattr__(configuration, "_projection_json", configuration_json)
object.__setattr__(
    configuration, "configuration_scope_sha256", configuration_digest
)
denied_audit_prefixes = (
    "ctypes.", "os.chdir", "os.listdir", "os.mkdir", "os.remove", "os.rename",
    "os.rmdir", "os.scandir", "os.system", "socket.", "subprocess.",
)

def audit(event, _args):
    if event == "open" or event == "import" or event.startswith(denied_audit_prefixes):
        raise AssertionError("forbidden audited capability used")

sys.addaudithook(audit)
builtins.__import__ = forbidden
result = module.project_protected_membership(
    configuration, manifest_bytes=manifest_bytes
)
print(json.dumps({
    "schema": result.projection["schema"],
    "digest": result.protected_membership_scope_sha256,
    "path_unchanged": tuple(sys.path) == before_path,
}))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            script,
            str(REPO_ROOT),
            configuration._projection_json,
            configuration.configuration_scope_sha256,
            base64.b64encode(manifest_bytes).decode("ascii"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "schema": "goodq.clean-memory-protected-membership.v1",
        "digest": _project().protected_membership_scope_sha256,
        "path_unchanged": True,
    }
    assert list(tmp_path.iterdir()) == []


def test_source_has_no_other_project_import_edges() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    project_imports = [
        (node.module, tuple((alias.name, alias.asname) for alias in node.names))
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (node.module == "cli.clean_memory" or node.module.startswith("steps."))
    ]
    assert project_imports == [
        (
            "cli.clean_memory",
            (("CONFIGURATION_SCHEMA", None), ("ResolvedPlanConfiguration", None)),
        ),
        (
            "steps.common.clean_memory",
            (("PROTECTED_BOUNDARY_ROLES", "_PROTECTED_BOUNDARY_ROLES"),),
        ),
        (
            "steps.common.clean_memory_protected_manifest",
            (
                (
                    "PROTECTED_MANIFEST_CHILD_NAME",
                    "_PROTECTED_MANIFEST_CHILD_NAME",
                ),
                (
                    "PROTECTED_MANIFEST_MAX_BYTES",
                    "_PROTECTED_MANIFEST_MAX_BYTES",
                ),
                (
                    "PROTECTED_MANIFEST_ROLE_ORDER",
                    "_PROTECTED_MANIFEST_ROLE_ORDER",
                ),
                ("validate_protected_manifest", "_validate_protected_manifest"),
            ),
        ),
    ]


def test_valid_invocation_has_no_io_process_network_or_environment_capability(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = importlib.import_module("cli.clean_memory_protected_membership")
    configuration = _resolved_configuration()
    manifest_bytes = _canonical_bytes(_manifest())

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("forbidden capability used")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "write_text", forbidden)
    monkeypatch.setattr(Path, "write_bytes", forbidden)
    monkeypatch.setattr(Path, "exists", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)
    monkeypatch.setattr(os, "listdir", forbidden)
    monkeypatch.setattr(os, "scandir", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    with pytest.raises(AssertionError, match="forbidden capability"):
        Path("unused").exists()
    result = module.project_protected_membership(
        configuration, manifest_bytes=manifest_bytes
    )

    assert result.projection["schema"] == module.PROTECTED_MEMBERSHIP_SCHEMA
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
