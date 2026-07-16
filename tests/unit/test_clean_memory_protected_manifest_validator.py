from __future__ import annotations

import ast
import base64
import copy
from dataclasses import FrozenInstanceError, fields, is_dataclass
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "steps" / "common" / "clean_memory_protected_manifest.py"
ROLE_ORDER = (
    "backup_root",
    "download_cache",
    "public_checkout",
    "qdrant_service_logs",
    "recovery_root",
    "reports_root",
    "repository",
    "source_media",
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
            for role in ROLE_ORDER
        ],
    }


def _maximal_manifest() -> dict[str, object]:
    manifest = _manifest()
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
    return manifest


def _module():
    return importlib.import_module("steps.common.clean_memory_protected_manifest")


def _validate(
    manifest: dict[str, object] | None = None,
    *,
    manifest_bytes: bytes | None = None,
    path_flavor: str = "posix",
):
    if manifest_bytes is None:
        manifest_bytes = _canonical_bytes(
            manifest if manifest is not None else _manifest()
        )
    return _module().validate_protected_manifest(
        manifest_bytes,
        path_flavor=path_flavor,
    )


def _assert_failure(
    manifest: dict[str, object],
    *,
    message: str,
    path_flavor: str = "posix",
) -> None:
    with pytest.raises(ValueError) as exc_info:
        _validate(manifest, path_flavor=path_flavor)
    assert str(exc_info.value) == message


def test_module_exists_with_exact_public_api() -> None:
    assert MODULE_PATH.is_file(), "canonical protected-manifest validator is absent"
    module = _module()
    assert module.__all__ == (
        "PROTECTED_MANIFEST_SCHEMA",
        "PROTECTED_MANIFEST_CHILD_NAME",
        "PROTECTED_MANIFEST_MAX_BYTES",
        "PROTECTED_MANIFEST_ROLE_ORDER",
        "CanonicalProtectedManifest",
        "validate_protected_manifest",
    )
    assert all(hasattr(module, name) for name in module.__all__)
    assert module.PROTECTED_MANIFEST_SCHEMA == (
        "goodq.clean-memory-protected-authority.v1"
    )
    assert module.PROTECTED_MANIFEST_CHILD_NAME == "protected-boundaries.json"
    assert module.PROTECTED_MANIFEST_MAX_BYTES == 4_194_304
    assert module.PROTECTED_MANIFEST_ROLE_ORDER == ROLE_ORDER
    assert type(module.PROTECTED_MANIFEST_ROLE_ORDER) is tuple

    signature = inspect.signature(module.validate_protected_manifest)
    assert tuple(signature.parameters) == ("manifest_bytes", "path_flavor")
    manifest_bytes_parameter = signature.parameters["manifest_bytes"]
    assert manifest_bytes_parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert manifest_bytes_parameter.default is inspect.Parameter.empty
    assert manifest_bytes_parameter.annotation == "bytes"
    path_flavor_parameter = signature.parameters["path_flavor"]
    assert path_flavor_parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert path_flavor_parameter.default is inspect.Parameter.empty
    assert path_flavor_parameter.annotation == "str"
    assert signature.return_annotation == "CanonicalProtectedManifest"

    result_type = module.CanonicalProtectedManifest
    assert is_dataclass(result_type)
    assert result_type.__dataclass_params__.frozen is True
    assert result_type.__dataclass_params__.init is False
    assert tuple(item.name for item in fields(result_type)) == (
        "_manifest_bytes",
        "manifest_sha256",
    )
    assert fields(result_type)[0].repr is False
    assert tuple(inspect.signature(result_type.__new__).parameters) == ("cls",)


def test_result_cannot_be_constructed_directly() -> None:
    with pytest.raises(TypeError) as exc_info:
        _module().CanonicalProtectedManifest()
    assert str(exc_info.value) == (
        "CanonicalProtectedManifest cannot be constructed directly"
    )


def test_valid_posix_manifest_returns_detached_immutable_result() -> None:
    manifest = _manifest()
    manifest["roles"][0]["members"][0]["presence"] = "allow_absent"
    manifest_bytes = _canonical_bytes(manifest)

    result = _validate(manifest_bytes=manifest_bytes)

    assert result.manifest_sha256 == hashlib.sha256(manifest_bytes).hexdigest()
    assert result.manifest == manifest
    first = result.manifest
    second = result.manifest
    assert first is not second
    assert first["roles"] is not second["roles"]
    first["roles"][0]["members"][0]["absolute_path"] = "/tampered"
    assert result.manifest == manifest
    with pytest.raises(FrozenInstanceError):
        result.manifest_sha256 = "0" * 64
    with pytest.raises(FrozenInstanceError):
        result._manifest_bytes = b"{}"
    assert not hasattr(result, "manifest_bytes")
    assert "/protected" not in repr(result)
    assert "_manifest_bytes" not in repr(result)
    assert repr(manifest_bytes) not in repr(result)


def test_valid_windows_manifest_preserves_case_and_unicode() -> None:
    manifest = _manifest(root="S:/Protected")
    manifest["roles"][0]["members"][0]["absolute_path"] = (
        "S:/Protected/Caf\u00e9"
    )

    result = _validate(manifest, path_flavor="windows")

    assert result.manifest == manifest
    assert result.manifest["roles"][0]["members"][0]["absolute_path"] == (
        "S:/Protected/Caf\u00e9"
    )


def test_exact_and_windows_casefold_path_aliases_are_valid_direct_inputs() -> None:
    posix = _manifest()
    posix["roles"][1]["members"][0]["absolute_path"] = (
        posix["roles"][0]["members"][0]["absolute_path"]
    )
    assert _validate(posix).manifest == posix

    windows = _manifest(root="S:/Protected")
    windows["roles"][0]["members"][0]["absolute_path"] = "S:/Protected/Shared"
    windows["roles"][1]["members"][0]["absolute_path"] = "S:/protected/shared"
    assert _validate(windows, path_flavor="windows").manifest == windows


def test_protocol_member_id_count_and_path_boundaries_are_accepted() -> None:
    manifest = _maximal_manifest()
    manifest["roles"][0]["members"][0]["absolute_path"] = "/" + ("a" * 4_095)
    manifest["roles"][0]["members"][0]["member_id"] = "a" + ("0" * 63)
    manifest["roles"][1]["members"][0]["member_id"] = "a"

    result = _validate(manifest)

    assert sum(len(role["members"]) for role in result.manifest["roles"]) == 512
    first_member = result.manifest["roles"][0]["members"][0]
    assert len(first_member["absolute_path"].encode("utf-8")) == 4_096
    assert len(first_member["member_id"]) == 64


def test_total_member_count_rejection_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    monkeypatch.setattr(module, "_MAX_MEMBERS_TOTAL", 511)

    with pytest.raises(ValueError) as exc_info:
        module.validate_protected_manifest(
            _canonical_bytes(_maximal_manifest()),
            path_flavor="posix",
        )
    assert str(exc_info.value) == "Manifest has too many members"


def test_path_boundary_is_measured_in_utf8_bytes() -> None:
    accepted = _manifest()
    accepted["roles"][0]["members"][0]["absolute_path"] = (
        "/" + ("\u00e9" * 2_047) + "a"
    )
    accepted_path = accepted["roles"][0]["members"][0]["absolute_path"]
    assert len(accepted_path.encode("utf-8")) == 4_096
    assert _validate(accepted).manifest == accepted

    rejected = _manifest()
    rejected["roles"][0]["members"][0]["absolute_path"] = "/" + ("\u00e9" * 2_048)
    with pytest.raises(ValueError) as exc_info:
        _validate(rejected)
    assert str(exc_info.value) == "Manifest member path exceeds the protocol boundary"


def test_protocol_byte_boundary_is_checked_before_decoding_or_json() -> None:
    module = _module()
    with pytest.raises(ValueError) as at_boundary:
        module.validate_protected_manifest(
            b"x" * module.PROTECTED_MANIFEST_MAX_BYTES,
            path_flavor="posix",
        )
    assert str(at_boundary.value) == "Manifest is not canonical JSON"

    with pytest.raises(ValueError) as above_boundary:
        module.validate_protected_manifest(
            b"x" * (module.PROTECTED_MANIFEST_MAX_BYTES + 1),
            path_flavor="posix",
        )
    assert str(above_boundary.value) == (
        "Manifest bytes exceed the protocol size boundary"
    )


def test_exact_input_types_and_failure_order() -> None:
    module = _module()
    valid_bytes = _canonical_bytes(_manifest())

    class BytesSubclass(bytes):
        pass

    class StringSubclass(str):
        pass

    for invalid_bytes in (
        valid_bytes.decode("utf-8"),
        bytearray(valid_bytes),
        memoryview(valid_bytes),
        BytesSubclass(valid_bytes),
    ):
        with pytest.raises(TypeError) as exc_info:
            module.validate_protected_manifest(
                invalid_bytes,
                path_flavor=object(),
            )
        assert str(exc_info.value) == "manifest_bytes must be exact bytes"

    for invalid_size in (b"", b"x" * (4_194_304 + 1)):
        with pytest.raises(ValueError) as exc_info:
            module.validate_protected_manifest(
                invalid_size,
                path_flavor=object(),
            )
        assert str(exc_info.value) == (
            "Manifest bytes exceed the protocol size boundary"
        )

    for invalid_flavor in (None, 1, StringSubclass("posix")):
        with pytest.raises(TypeError) as exc_info:
            module.validate_protected_manifest(
                valid_bytes,
                path_flavor=invalid_flavor,
            )
        assert str(exc_info.value) == "path_flavor must be exact str"

    for invalid_flavor in ("", "POSIX", "linux", "win32"):
        with pytest.raises(ValueError) as exc_info:
            module.validate_protected_manifest(
                b"\xff",
                path_flavor=invalid_flavor,
            )
        assert str(exc_info.value) == "path_flavor must be 'windows' or 'posix'"

    with pytest.raises(ValueError) as exc_info:
        module.validate_protected_manifest(b"\xff", path_flavor="posix")
    assert str(exc_info.value) == "Manifest bytes are not canonical UTF-8"


@pytest.mark.parametrize(
    ("invalid_bytes", "message"),
    [
        (b"\xff", "Manifest bytes are not canonical UTF-8"),
        (b"{", "Manifest is not canonical JSON"),
        (b'{"roles":[],"roles":[],"schema":"x"}', "Manifest is not canonical JSON"),
        (b'{"roles":[],"schema":NaN}', "Manifest is not canonical JSON"),
        (b'{"roles":[],"schema":Infinity}', "Manifest is not canonical JSON"),
        (b'{"roles":[],"schema":-Infinity}', "Manifest is not canonical JSON"),
        (
            b'{"roles":[],"schema":1e400}',
            "Protected-membership value is not canonical JSON",
        ),
        (b"[]", "Manifest is not a JSON object"),
        (b"null", "Manifest is not a JSON object"),
        (b"\xef\xbb\xbf{}", "Manifest is not canonical JSON"),
    ],
)
def test_utf8_json_and_object_failures_are_exact(
    invalid_bytes: bytes,
    message: str,
) -> None:
    with pytest.raises(ValueError) as exc_info:
        _validate(manifest_bytes=invalid_bytes)
    assert str(exc_info.value) == message


def test_deeply_nested_json_is_a_sanitized_failure() -> None:
    invalid_bytes = (
        b'{"roles":'
        + (b"[" * 2_000)
        + b"0"
        + (b"]" * 2_000)
        + b',"schema":"goodq.clean-memory-protected-authority.v1"}'
    )
    with pytest.raises(ValueError) as exc_info:
        _validate(manifest_bytes=invalid_bytes)
    assert str(exc_info.value) == "Manifest is not canonical JSON"


@pytest.mark.parametrize("variant", ["newline", "unsorted", "pretty", "duplicate", "escaped_slash", "ascii_escape"])
def test_semantically_valid_noncanonical_encodings_have_exact_failure(
    variant: str,
) -> None:
    manifest = _manifest()
    manifest["roles"][0]["members"][0]["absolute_path"] = "/protected/Caf\u00e9"
    canonical = _canonical_bytes(manifest)
    if variant == "newline":
        invalid_bytes = canonical + b"\n"
    elif variant == "unsorted":
        invalid_bytes = json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
        ).encode("utf-8")
    elif variant == "pretty":
        invalid_bytes = json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
    elif variant == "duplicate":
        invalid_bytes = canonical.replace(
            b'"presence":"required"',
            b'"presence":"required","presence":"required"',
            1,
        )
    elif variant == "escaped_slash":
        invalid_bytes = canonical.replace(b"/protected/", b"\\/protected/", 1)
    else:
        invalid_bytes = json.dumps(
            manifest,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    assert invalid_bytes != canonical

    with pytest.raises(ValueError) as exc_info:
        _validate(manifest_bytes=invalid_bytes)
    expected = (
        "Manifest is not canonical JSON"
        if variant == "duplicate"
        else "Manifest bytes are not canonical"
    )
    assert str(exc_info.value) == expected


@pytest.mark.parametrize(
    "mutation",
    ["nfd_key", "nfd_value", "control_value", "c1_control_value"],
)
def test_recursive_noncanonical_strings_are_rejected_exactly(mutation: str) -> None:
    manifest = _manifest()
    if mutation == "nfd_key":
        manifest["roles"][0]["members"][0]["e\u0301xtra"] = False
    elif mutation == "nfd_value":
        manifest["roles"][0]["members"][0]["absolute_path"] = (
            "/SECRET_PATH_CANARY/e\u0301"
        )
    elif mutation == "control_value":
        manifest["roles"][0]["members"][0]["absolute_path"] = (
            "/SECRET_PATH_CANARY/control\u0000value"
        )
    else:
        manifest["roles"][0]["members"][0]["absolute_path"] = (
            "/SECRET_PATH_CANARY/control\u0085value"
        )

    with pytest.raises(ValueError) as exc_info:
        _validate(manifest)
    assert str(exc_info.value) == "Manifest contains a noncanonical string"
    assert "SECRET_PATH_CANARY" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("top_missing", "Manifest has an invalid schema envelope"),
        ("top_extra", "Manifest has an invalid schema envelope"),
        ("wrong_schema", "Manifest has an invalid schema envelope"),
        ("roles_not_list", "Manifest has an invalid role census"),
        ("role_missing", "Manifest has an invalid role census"),
        ("role_extra", "Manifest has an invalid role census"),
        ("role_reordered", "Manifest has an invalid role order"),
        ("role_wrong_name", "Manifest has an invalid role order"),
        ("role_not_object", "Manifest has an invalid role order"),
        ("role_record_extra", "Manifest has an invalid role record"),
        ("members_not_list", "Manifest has an invalid member count"),
        ("members_empty", "Manifest has an invalid member count"),
        ("members_too_many", "Manifest has an invalid member count"),
        ("member_not_object", "Manifest has an invalid member record"),
        ("member_missing", "Manifest has an invalid member record"),
        ("member_extra", "Manifest has an invalid member record"),
        ("member_id_not_string", "Manifest has an invalid member identifier"),
        ("member_id_invalid", "Manifest has an invalid member identifier"),
        ("member_id_too_long", "Manifest has an invalid member identifier"),
        ("member_ids_duplicate", "Manifest member identifiers are not strictly ordered"),
        ("member_ids_reordered", "Manifest member identifiers are not strictly ordered"),
        ("wrong_kind", "Manifest has an invalid member policy"),
        ("wrong_presence", "Manifest has an invalid member policy"),
        ("path_too_long", "Manifest member path exceeds the protocol boundary"),
    ],
)
def test_schema_role_member_and_policy_failures_are_exact(
    mutation: str,
    message: str,
) -> None:
    manifest = copy.deepcopy(_manifest())
    first_role = manifest["roles"][0]
    first_member = first_role["members"][0]
    if mutation == "top_missing":
        del manifest["schema"]
    elif mutation == "top_extra":
        manifest["extra"] = False
    elif mutation == "wrong_schema":
        manifest["schema"] = "goodq.clean-memory-protected-authority.v2"
    elif mutation == "roles_not_list":
        manifest["roles"] = {}
    elif mutation == "role_missing":
        manifest["roles"].pop()
    elif mutation == "role_extra":
        manifest["roles"].append(copy.deepcopy(first_role))
    elif mutation == "role_reordered":
        manifest["roles"][0], manifest["roles"][1] = (
            manifest["roles"][1],
            manifest["roles"][0],
        )
    elif mutation == "role_wrong_name":
        first_role["role"] = "wrong"
    elif mutation == "role_not_object":
        manifest["roles"][0] = None
    elif mutation == "role_record_extra":
        first_role["extra"] = False
    elif mutation == "members_not_list":
        first_role["members"] = {}
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
    elif mutation == "member_not_object":
        first_role["members"][0] = None
    elif mutation == "member_missing":
        del first_member["presence"]
    elif mutation == "member_extra":
        first_member["extra"] = False
    elif mutation == "member_id_not_string":
        first_member["member_id"] = 1
    elif mutation == "member_id_invalid":
        first_member["member_id"] = "9invalid"
    elif mutation == "member_id_too_long":
        first_member["member_id"] = "a" + ("0" * 64)
    elif mutation == "member_ids_duplicate":
        first_role["members"].append(copy.deepcopy(first_member))
    elif mutation == "member_ids_reordered":
        first_role["members"].append(
            {
                **first_member,
                "member_id": "alpha",
                "absolute_path": "/protected/backup_root/alpha",
            }
        )
    elif mutation == "wrong_kind":
        first_member["object_kind"] = "regular_file"
    elif mutation == "wrong_presence":
        first_member["presence"] = "optional"
    else:
        first_member["absolute_path"] = "/" + ("a" * 4_096)

    _assert_failure(manifest, message=message)


@pytest.mark.parametrize(
    "invalid_member_id",
    ["", "Primary", "UPPER", "_primary", "a-b", "a.b", "a/b", "a b"],
)
def test_member_identifier_pattern_rejections_are_exact(
    invalid_member_id: str,
) -> None:
    manifest = _manifest()
    manifest["roles"][0]["members"][0]["member_id"] = invalid_member_id

    with pytest.raises(ValueError) as exc_info:
        _validate(manifest)
    assert str(exc_info.value) == "Manifest has an invalid member identifier"


@pytest.mark.parametrize(
    ("invalid_path", "path_flavor", "message"),
    [
        (None, "posix", "Protected-membership path is not canonical"),
        (" relative/path", "posix", "Protected-membership path is not canonical"),
        ("/protected/child/", "posix", "Protected-membership path is not canonical"),
        ("/protected//child", "posix", "Protected-membership path is not canonical"),
        ("/protected\\child", "posix", "Protected-membership path is not canonical"),
        ("/protected/${ROOT}", "posix", "Protected-membership path is not canonical"),
        ("/protected/${ROOT-default}", "posix", "Protected-membership path is not canonical"),
        ("/protected/${ROOT:=default}", "posix", "Protected-membership path is not canonical"),
        ("/protected/${ROOT:+default}", "posix", "Protected-membership path is not canonical"),
        ("/protected/${ROOT:?default}", "posix", "Protected-membership path is not canonical"),
        ("/protected/${ROOT", "posix", "Protected-membership path is not canonical"),
        ("/protected/$ROOT", "posix", "Protected-membership path is not canonical"),
        ("/protected/%ROOT%", "posix", "Protected-membership path is not canonical"),
        ("/protected/.", "posix", "Protected-membership path is not canonical"),
        ("/protected/..", "posix", "Protected-membership path is not canonical"),
        ("relative/path", "posix", "Protected-membership path is not a canonical local absolute path"),
        ("/", "posix", "Protected-membership path is not canonical"),
        ("R:/protected", "posix", "Protected-membership path uses the wrong flavor"),
        ("/protected/backup", "windows", "Protected-membership path uses the wrong flavor"),
        ("s:/protected/backup", "windows", "Protected-membership path is not a canonical local absolute path"),
        ("S:/", "windows", "Protected-membership path is not canonical"),
        ("//server/share", "windows", "Protected-membership path is not canonical"),
        ("\\\\?\\S:\\protected\\backup", "windows", "Protected-membership path is not canonical"),
        ("S:\\protected\\backup", "windows", "Protected-membership path is not canonical"),
        ("S:/protected//backup", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/backup/", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/./backup", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/CON", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/com1.txt", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/COM\u00b9", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/LPT\u00b2.txt", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/trailing.", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/trailing ", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/inva?id", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/%ROOT%", "windows", "Protected-membership path is not canonical"),
        ("S:/protected/../backup", "windows", "Protected-membership path is not canonical"),
    ],
)
def test_path_failures_preserve_exact_class_message_and_sanitization(
    invalid_path: object,
    path_flavor: str,
    message: str,
) -> None:
    manifest = _manifest(root="S:/protected" if path_flavor == "windows" else "/protected")
    manifest["roles"][0]["members"][0]["absolute_path"] = invalid_path

    with pytest.raises(ValueError) as exc_info:
        _validate(manifest, path_flavor=path_flavor)
    assert str(exc_info.value) == message
    if type(invalid_path) is str:
        assert invalid_path not in str(exc_info.value)


def test_private_protocol_limits_and_identifier_pattern_are_exact() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    assignments = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert ast.literal_eval(assignments["_MAX_PATH_BYTES"]) == 4_096
    assert ast.literal_eval(assignments["_MAX_MEMBERS_PER_ROLE"]) == 64
    assert ast.literal_eval(assignments["_MAX_MEMBERS_TOTAL"]) == 512
    member_id_call = assignments["_MEMBER_ID_RE"]
    assert isinstance(member_id_call, ast.Call)
    assert isinstance(member_id_call.func, ast.Attribute)
    assert isinstance(member_id_call.func.value, ast.Name)
    assert member_id_call.func.value.id == "re"
    assert member_id_call.func.attr == "compile"
    assert len(member_id_call.args) == 1
    assert member_id_call.keywords == []
    assert ast.literal_eval(member_id_call.args[0]) == r"^[a-z][a-z0-9_]{0,63}$"


def test_only_validator_owned_code_can_allocate_a_result() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    result_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "CanonicalProtectedManifest"
    )
    assert {
        node.name for node in result_class.body if isinstance(node, ast.FunctionDef)
    } == {"__new__", "manifest"}
    assert not [
        decorator
        for node in result_class.body
        if isinstance(node, ast.FunctionDef)
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Name)
        and decorator.id in {"classmethod", "staticmethod"}
    ]

    allocation_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "object"
        and node.func.attr == "__new__"
    ]
    assert len(allocation_calls) == 1
    validator = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "validate_protected_manifest"
    )
    assert allocation_calls[0] in set(ast.walk(validator))
    assert allocation_calls[0].lineno > max(
        node.lineno for node in ast.walk(validator) if isinstance(node, ast.Raise)
    )


def test_source_is_standard_library_only_with_exact_exports() -> None:
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
        ("dataclasses", 0, (("dataclass", None), ("field", None))),
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


def test_module_import_and_invocation_are_poisoned_audited_and_capability_free(
    tmp_path: Path,
) -> None:
    manifest_bytes = _canonical_bytes(_manifest())
    script = r'''
import base64
import builtins
import ctypes
import dataclasses
import hashlib
import importlib
import json
import logging
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import types
import typing
import unicodedata

repo_root = sys.argv[1]
manifest_bytes = base64.b64decode(sys.argv[2], validate=True)
sys.path.insert(0, repo_root)
importlib.import_module("steps.common")
module_name = "steps.common.clean_memory_protected_manifest"
module_path = Path(repo_root) / "steps" / "common" / "clean_memory_protected_manifest.py"
module_code = compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
before_path = tuple(sys.path)
before_env = dict(os.environ)
before_modules = set(sys.modules)
real_import = builtins.__import__

def forbidden(*_args, **_kwargs):
    raise AssertionError("forbidden capability used")

allowed_runtime_imports = {
    "__future__", "dataclasses", "hashlib", "json", "re", "typing",
    "unicodedata",
}
observed_runtime_imports = []

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name not in allowed_runtime_imports or level != 0:
        raise AssertionError(f"forbidden runtime import: {name}")
    observed_runtime_imports.append(name)
    return real_import(name, globals, locals, fromlist, level)

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

guarded_environment = GuardedEnvironment(before_env)
os.environ = guarded_environment
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
ctypes.CDLL = forbidden
ctypes.PyDLL = forbidden
logging.getLogger = forbidden
logging.basicConfig = forbidden

denied_audit_prefixes = (
    "ctypes.", "os.chdir", "os.listdir", "os.mkdir", "os.remove", "os.rename",
    "os.rmdir", "os.scandir", "os.system", "socket.", "subprocess.",
)
allowed_audited_imports = allowed_runtime_imports

def audit(event, args):
    if event == "import" and args[0] not in allowed_audited_imports:
        raise AssertionError(f"forbidden audited import: {args[0]}")
    if event == "open":
        raise AssertionError("forbidden audited open")
    if event.startswith(denied_audit_prefixes):
        raise AssertionError("forbidden audited capability used")

sys.addaudithook(audit)
builtins.__import__ = guarded_import
module = types.ModuleType(module_name)
module.__file__ = str(module_path)
module.__package__ = "steps.common"
sys.modules[module_name] = module
exec(module_code, module.__dict__)
assert observed_runtime_imports == [
    "__future__", "dataclasses", "hashlib", "json", "re", "typing",
    "unicodedata",
]
builtins.__import__ = forbidden
assert tuple(sys.path) == before_path
assert os.environ is guarded_environment
forbidden_roots = {
    "httpx", "qdrant_client", "requests", "win32api", "win32security",
    "steps.common.config_loader", "cli",
}
new_modules = set(sys.modules) - before_modules
assert not {
    name for name in new_modules
    if name in forbidden_roots or name.split(".", 1)[0] in forbidden_roots
}

result = module.validate_protected_manifest(manifest_bytes, path_flavor="posix")
view = result.manifest
assert tuple(sys.path) == before_path
assert os.environ is guarded_environment
sys.stdout.write(json.dumps({
    "digest": result.manifest_sha256,
    "schema": view["schema"],
    "path_unchanged": tuple(sys.path) == before_path,
}))
'''
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            script,
            str(REPO_ROOT),
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
        "digest": hashlib.sha256(manifest_bytes).hexdigest(),
        "schema": "goodq.clean-memory-protected-authority.v1",
        "path_unchanged": True,
    }
    assert list(tmp_path.iterdir()) == []
