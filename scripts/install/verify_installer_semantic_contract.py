"""Fail fast when installer components no longer share one semantic contract."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

if __package__:
    from .installer_contract import (
        INSTALLER_PROFILES,
        MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
        MODEL_MEMBER_MANIFEST_SCHEMA_VERSION,
        PAYLOAD_BINDING_FIELDS,
        PAYLOAD_INSTALL_RECEIPT_REQUIRED_FIELDS,
        PAYLOAD_INSTALL_RECEIPT_SCHEMA_VERSION,
        PAYLOAD_INSTALL_RECEIPT_STATUS,
        PAYLOAD_MANIFEST_REQUIRED_FIELDS,
        PAYLOAD_MANIFEST_SCHEMA_VERSION,
        PAYLOAD_MEMBER_REQUIRED_FIELDS,
        PAYLOAD_PACK_FORMAT,
        PAYLOAD_PACK_REQUIRED_FIELDS,
        RELEASE_BUILD_PROFILES,
        SELECTED_CAPABILITIES_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_SCHEMA_VERSION,
    )
else:
    from installer_contract import (
        INSTALLER_PROFILES,
        MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
        MODEL_MEMBER_MANIFEST_SCHEMA_VERSION,
        PAYLOAD_BINDING_FIELDS,
        PAYLOAD_INSTALL_RECEIPT_REQUIRED_FIELDS,
        PAYLOAD_INSTALL_RECEIPT_SCHEMA_VERSION,
        PAYLOAD_INSTALL_RECEIPT_STATUS,
        PAYLOAD_MANIFEST_REQUIRED_FIELDS,
        PAYLOAD_MANIFEST_SCHEMA_VERSION,
        PAYLOAD_MEMBER_REQUIRED_FIELDS,
        PAYLOAD_PACK_FORMAT,
        PAYLOAD_PACK_REQUIRED_FIELDS,
        RELEASE_BUILD_PROFILES,
        SELECTED_CAPABILITIES_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_SCHEMA_VERSION,
    )


REPORT_SCHEMA = "goodq.installer-semantic-contract-check.v1"
REQUIRED_SOURCES = {
    "version": Path("goodq_version.py"),
    "profiles": Path("configs/installer_profile_contract.yaml"),
    "contract": Path("scripts/install/installer_contract.py"),
    "payload": Path("scripts/install/release_payload_packs.py"),
    "stage": Path("scripts/install/stage_profile_model_packs.py"),
    "profile_verify": Path("scripts/install/verify_profile_model_payload.py"),
    "prebuild": Path("scripts/install/prebuild_readiness.py"),
    "go": Path("scripts/install/LAUNCH_GOODQ.go"),
    "nsi": Path("scripts/install/goodq4all_installer.nsi"),
    "manifest_ps": Path("scripts/install/generate_manifest.ps1"),
    "release_verify_ps": Path("scripts/install/verify_release_asset.ps1"),
    "release_batch": Path("scripts/install/run_offline_release_build.bat"),
    "builder_batch": Path("scripts/install/build_installer.bat"),
    "version_info": Path("scripts/install/versioninfo.json"),
    "ci": Path(".github/workflows/ci.yml"),
}


class SemanticContractConfigurationError(RuntimeError):
    """Raised when the checker cannot load or interpret its required inputs."""


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


def _result(name: str, compatible: bool, detail: str) -> CheckResult:
    return CheckResult(
        name=name,
        status="compatible" if compatible else "mismatch",
        detail=detail,
    )


def _load_sources(repo_root: Path) -> dict[str, str]:
    sources: dict[str, str] = {}
    for name, relative in REQUIRED_SOURCES.items():
        path = repo_root / relative
        try:
            sources[name] = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SemanticContractConfigurationError(
                f"required installer contract source is unavailable: {relative.as_posix()}"
            ) from exc
    return sources


def _literal_assignment(source: str, name: str, label: str) -> Any:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SemanticContractConfigurationError(f"{label} is not valid Python") from exc
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                value = node.value
                try:
                    return ast.literal_eval(value)
                except (TypeError, ValueError) as exc:
                    raise SemanticContractConfigurationError(
                        f"{label} {name} must be a literal"
                    ) from exc
    raise SemanticContractConfigurationError(f"{label} does not define {name}")


def _function_node(source: str, function_name: str, label: str) -> ast.FunctionDef:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SemanticContractConfigurationError(f"{label} is not valid Python") from exc
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return node
    raise SemanticContractConfigurationError(f"{label} does not define {function_name}")


def _assigned_dict(function: ast.FunctionDef, variable: str) -> ast.Dict | None:
    for node in ast.walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == variable for target in targets):
            return node.value if isinstance(node.value, ast.Dict) else None
    return None


def _returned_dict(function: ast.FunctionDef) -> ast.Dict | None:
    for node in ast.walk(function):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            return node.value
    return None


def _dict_keys(node: ast.Dict | None) -> set[str]:
    if node is None:
        return set()
    return {
        str(key.value)
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def _dict_value(node: ast.Dict | None, key_name: str) -> ast.AST | None:
    if node is None:
        return None
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and key.value == key_name:
            return value
    return None


def _has_markers(source: str, markers: Iterable[str]) -> bool:
    return all(marker in source for marker in markers)


def _ordered(source: str, markers: Iterable[str]) -> bool:
    positions: list[int] = []
    for marker in markers:
        if source.count(marker) != 1:
            return False
        positions.append(source.index(marker))
    return positions == sorted(positions)


def _version_projection_check(sources: dict[str, str]) -> CheckResult:
    version = _literal_assignment(sources["version"], "GOODQ_VERSION", "goodq_version.py")
    if not isinstance(version, str) or re.fullmatch(r"\d+\.\d+\.\d+", version) is None:
        raise SemanticContractConfigurationError("GOODQ_VERSION must be a numeric semantic version")
    major, minor, patch = (int(part) for part in version.split("."))
    try:
        info = json.loads(sources["version_info"])
    except json.JSONDecodeError as exc:
        raise SemanticContractConfigurationError("versioninfo.json is invalid") from exc
    expected_fixed = {"Major": major, "Minor": minor, "Patch": patch, "Build": 0}
    nsi_ok = _has_markers(
        sources["nsi"],
        (
            f'OutFile "${{GOODQ_INSTALLER_OUTPUT_ROOT}}\\GoodQ4All_Setup_{version}.exe"',
            f'!define MUI_WELCOMEPAGE_TITLE "Welcome to the GoodQ4All v{version} Offline Installer"',
            f'"DisplayVersion" "{version}"',
        ),
    )
    info_ok = (
        info.get("FixedFileInfo", {}).get("FileVersion") == expected_fixed
        and info.get("FixedFileInfo", {}).get("ProductVersion") == expected_fixed
        and info.get("StringFileInfo", {}).get("FileVersion") == f"{version}.0"
        and info.get("StringFileInfo", {}).get("ProductVersion") == f"{version}.0"
    )
    prebuild_ok = (
        "RELEASE_VERSION" not in sources["prebuild"]
        and "expected_version" in sources["prebuild"]
        and "_canonical_version(repo_root)" in sources["prebuild"]
    )
    return _result(
        "product_version",
        nsi_ok and info_ok and prebuild_ok,
        f"GOODQ_VERSION {version} must project into NSIS, versioninfo, and readiness validation",
    )


def _profile_check(sources: dict[str, str]) -> CheckResult:
    try:
        profile_document = yaml.safe_load(sources["profiles"]) or {}
    except yaml.YAMLError as exc:
        raise SemanticContractConfigurationError("installer profile contract YAML is invalid") from exc
    profile_map = profile_document.get("profiles")
    if not isinstance(profile_map, dict):
        raise SemanticContractConfigurationError("installer profile contract has no profile map")
    all_profiles = tuple(profile_map)
    release_condition = " ".join(
        f'if /I not "%GOODQ_INSTALLER_PROFILE%"=="{profile}"'
        for profile in RELEASE_BUILD_PROFILES
    ) + " ("
    compatible = (
        all_profiles == INSTALLER_PROFILES
        and set(RELEASE_BUILD_PROFILES) < set(INSTALLER_PROFILES)
        and sources["release_batch"].count(release_condition) == 1
        and sources["builder_batch"].count(release_condition) == 1
        and "PUBLIC_PROFILE, PERSONAL_PROFILE = RELEASE_BUILD_PROFILES"
        in sources["prebuild"]
        and all(profile in sources["nsi"] for profile in INSTALLER_PROFILES)
    )
    return _result(
        "profiles",
        compatible,
        "profile YAML must remain complete while release build lanes stay GPU and Personal only",
    )


def _schema_checks(sources: dict[str, str]) -> list[CheckResult]:
    payload_ok = _has_markers(
        sources["payload"],
        (
            '"schema_version": PAYLOAD_MANIFEST_SCHEMA_VERSION',
            "schema != PAYLOAD_MANIFEST_SCHEMA_VERSION",
        ),
    ) and _has_markers(
        sources["go"],
        (f"const releasePayloadSchemaVersion = {PAYLOAD_MANIFEST_SCHEMA_VERSION}",),
    ) and _has_markers(
        sources["manifest_ps"],
        (f"$payloadManifest.schema_version -ne {PAYLOAD_MANIFEST_SCHEMA_VERSION}",),
    ) and _has_markers(
        sources["release_verify_ps"],
        (f"$payloadContract.schema_version -ne {PAYLOAD_MANIFEST_SCHEMA_VERSION}",),
    )
    selected_ok = all(
        marker in source
        for source, marker in (
            (
                sources["stage"],
                '"schema_version": SELECTED_CAPABILITIES_SCHEMA_VERSION',
            ),
            (
                sources["payload"],
                'selected.get("schema_version") != SELECTED_CAPABILITIES_SCHEMA_VERSION',
            ),
            (
                sources["profile_verify"],
                'selected.get("schema_version") != SELECTED_CAPABILITIES_SCHEMA_VERSION',
            ),
        )
    )
    member_ok = all(
        marker in source
        for source, marker in (
            (
                sources["stage"],
                '"schema_version": MODEL_MEMBER_MANIFEST_SCHEMA_VERSION',
            ),
            (
                sources["stage"],
                'manifest.get("schema_version") != MODEL_MEMBER_MANIFEST_SCHEMA_VERSION',
            ),
            (
                sources["payload"],
                'model_manifest.get("schema_version") != MODEL_MEMBER_MANIFEST_SCHEMA_VERSION',
            ),
            (
                sources["profile_verify"],
                'manifest.get("schema_version") != MODEL_MEMBER_MANIFEST_SCHEMA_VERSION',
            ),
        )
    )
    return [
        _result("payload_schema", payload_ok, "payload schema projections must agree"),
        _result(
            "selected_capabilities_schema",
            selected_ok,
            "selected-capability producer and validators must use the canonical schema",
        ),
        _result(
            "model_member_schema",
            member_ok,
            "model-member producer and validators must use the canonical schema",
        ),
    ]


def _required_field_check(sources: dict[str, str]) -> CheckResult:
    build_function = _function_node(sources["payload"], "build", "release_payload_packs.py")
    manifest_node = _assigned_dict(build_function, "manifest")
    stage_function = _function_node(
        sources["stage"], "stage_profile", "stage_profile_model_packs.py"
    )
    selected_node = _assigned_dict(stage_function, "result")
    member_function = _function_node(
        sources["stage"],
        "_build_model_member_manifest",
        "stage_profile_model_packs.py",
    )
    model_member_node = _returned_dict(member_function)
    direct_manifest_fields = PAYLOAD_MANIFEST_REQUIRED_FIELDS - PAYLOAD_BINDING_FIELDS
    manifest_keys = _dict_keys(manifest_node)
    has_binding_expansion = bool(
        manifest_node
        and any(
            key is None and isinstance(value, ast.Name) and value.id == "bindings"
            for key, value in zip(manifest_node.keys, manifest_node.values)
        )
    )
    validation_markers = (
        "PAYLOAD_MANIFEST_REQUIRED_FIELDS",
        "PAYLOAD_PACK_REQUIRED_FIELDS",
        "PAYLOAD_MEMBER_REQUIRED_FIELDS",
        "SELECTED_CAPABILITIES_REQUIRED_FIELDS",
        "MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS",
    )
    compatible = (
        manifest_keys == direct_manifest_fields
        and has_binding_expansion
        and _dict_keys(selected_node) == SELECTED_CAPABILITIES_REQUIRED_FIELDS
        and _dict_keys(model_member_node) == MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS
        and _has_markers(sources["payload"], validation_markers)
        and _has_markers(sources["stage"], ("MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS",))
        and _has_markers(
            sources["profile_verify"],
            ("SELECTED_CAPABILITIES_REQUIRED_FIELDS", "MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS"),
        )
    )
    return _result(
        "required_fields",
        compatible,
        "manifest, pack, member, selected-capability, and model-member fields must stay complete",
    )


def _install_receipt_check(sources: dict[str, str]) -> CheckResult:
    apply_function = _function_node(sources["payload"], "apply", "release_payload_packs.py")
    receipt = _assigned_dict(apply_function, "receipt")
    status_value = _dict_value(receipt, "status")
    schema_value = _dict_value(receipt, "schema_version")
    compatible = (
        _dict_keys(receipt) == PAYLOAD_INSTALL_RECEIPT_REQUIRED_FIELDS
        and isinstance(status_value, ast.Name)
        and status_value.id == "PAYLOAD_INSTALL_RECEIPT_STATUS"
        and isinstance(schema_value, ast.Name)
        and schema_value.id == "PAYLOAD_INSTALL_RECEIPT_SCHEMA_VERSION"
        and f'PAYLOAD_INSTALL_RECEIPT_STATUS = "{PAYLOAD_INSTALL_RECEIPT_STATUS}"'
        in sources["contract"]
        and f"PAYLOAD_INSTALL_RECEIPT_SCHEMA_VERSION = {PAYLOAD_INSTALL_RECEIPT_SCHEMA_VERSION}"
        in sources["contract"]
    )
    return _result(
        "install_receipt",
        compatible,
        "install receipt schema, required fields, and terminal status must remain canonical",
    )


def _payload_binding_check(sources: dict[str, str]) -> CheckResult:
    binding_markers = tuple(f'"{field}"' for field in sorted(PAYLOAD_BINDING_FIELDS))
    pack_markers = tuple(f'json:"{field}"' for field in sorted(PAYLOAD_PACK_REQUIRED_FIELDS))
    go_manifest_markers = tuple(
        f'json:"{field}"' for field in sorted(PAYLOAD_MANIFEST_REQUIRED_FIELDS)
    )
    compatible = (
        _has_markers(sources["payload"], (*binding_markers, "member_inventory_sha256", "member_count"))
        and _has_markers(sources["manifest_ps"], binding_markers)
        and _has_markers(sources["release_verify_ps"], binding_markers)
        and _has_markers(sources["go"], (*go_manifest_markers, *pack_markers))
        and f'const releasePayloadPackFormat = "{PAYLOAD_PACK_FORMAT}"'
        in sources["go"]
        and f'PAYLOAD_PACK_FORMAT = "{PAYLOAD_PACK_FORMAT}"' in sources["contract"]
        and f'manifest.get("pack_format") != PAYLOAD_PACK_FORMAT' in sources["payload"]
        and f'$payloadManifest.pack_format -ne "{PAYLOAD_PACK_FORMAT}"'
        in sources["manifest_ps"]
        and f'$payloadContract.pack_format -ne "{PAYLOAD_PACK_FORMAT}"'
        in sources["release_verify_ps"]
        and all(field in PAYLOAD_MEMBER_REQUIRED_FIELDS for field in ("path", "pack_path", "sha256", "size_bytes", "target"))
    )
    return _result(
        "payload_bindings",
        compatible,
        "pack format, binding hashes, inventory digests, and counts must project consistently",
    )


def _cli_check(sources: dict[str, str]) -> CheckResult:
    go_markers = (
        'flag.String("verify-release-payload",',
        'flag.String("apply-release-payload",',
        'flag.String("payload-data-dir",',
        '"--manifest-stdin"',
        '"--bundle-root", root',
        '"--install-dir", programFilesDir',
        '"--data-dir", dataDir',
    )
    python_markers = (
        'apply_parser.add_argument("--bundle-root"',
        'apply_parser.add_argument("--install-dir"',
        'apply_parser.add_argument("--data-dir"',
        'apply_parser.add_argument("--manifest-stdin"',
    )
    nsi_apply = "--apply-release-payload"
    compatible = (
        _has_markers(sources["go"], go_markers)
        and _has_markers(sources["payload"], python_markers)
        and "--manifest-path" not in sources["payload"]
        and sources["nsi"].count(nsi_apply) == 1
        and "--payload-data-dir" in sources["nsi"]
        and 'release_payload_packs.py" apply' not in sources["nsi"]
        and _has_markers(
            sources["builder_batch"],
            (
                "release_payload_packs.py build --staging-root",
                '--output-root "%OUTPUT_ROOT%"',
                '--version "%GOODQ_PRODUCT_VERSION%"',
                '--profile "%GOODQ_INSTALLER_PROFILE%"',
            ),
        )
    )
    return _result(
        "cli_contract",
        compatible,
        "caller and callee flags must agree and Python apply must accept stdin only",
    )


def _authenticated_handoff_check(sources: dict[str, str]) -> CheckResult:
    go_markers = (
        "manifestBytes, err := os.ReadFile(manifestPath)",
        "ed25519.Verify(publicKey, manifestBytes, sigBytes)",
        "json.Unmarshal(manifestBytes, &manifest)",
        "command.Stdin = bytes.NewReader(manifestBytes)",
    )
    compatible = (
        _has_markers(sources["go"], go_markers)
        and sources["go"].count("command.Stdin = bytes.NewReader(manifestBytes)") == 1
        and "manifest_bytes=sys.stdin.buffer.read()" in sources["payload"]
        and sources["nsi"].count("--apply-release-payload") == 1
        and "--verify-release-payload" not in sources["nsi"]
    )
    return _result(
        "authenticated_handoff",
        compatible,
        "Go must parse and stream the exact signed manifest bytes to the sole elevated apply path",
    )


def _single_handle_check(sources: dict[str, str]) -> CheckResult:
    payload = sources["payload"]
    markers = (
        "with ExitStack() as stack:",
        "handle = stack.enter_context(_open_pack_for_apply(pack_path))",
        "file_info = os.fstat(handle.fileno())",
        "handle.seek(0)",
        "archive = stack.enter_context(zipfile.ZipFile(handle))",
        "verified_archives.append((relative, archive, info_by_name))",
    )
    compatible = (
        _has_markers(payload, markers)
        and "zipfile.ZipFile(pack_path)" not in payload
        and _ordered(
            payload,
            (
                "handle = stack.enter_context(_open_pack_for_apply(pack_path))",
                "handle.seek(0)",
                "archive = stack.enter_context(zipfile.ZipFile(handle))",
                "verified_archives.append((relative, archive, info_by_name))",
                "for relative, archive, info_by_name in verified_archives:",
            ),
        )
        and "file_share_read" in payload
        and "file_share_write" not in payload
        and "file_share_delete" not in payload
    )
    return _result(
        "single_handle_processing",
        compatible,
        "each pack must stay on one write/delete-denying handle from hash through extraction",
    )


def _wsl_check(sources: dict[str, str]) -> CheckResult:
    function = _function_node(
        sources["profile_verify"],
        "_probe_pyannote_via_wsl",
        "verify_profile_model_payload.py",
    )
    shell_assignment: ast.AST | None = None
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "shell_command"
            for target in node.targets
        ):
            shell_assignment = node.value
            break
    unsafe_names = {"workspace", "translated", "kind", "device", "encoded"}
    referenced_names = {
        node.id for node in ast.walk(shell_assignment) if isinstance(node, ast.Name)
    } if shell_assignment is not None else unsafe_names
    markers = (
        '["wsl", "-d", distro, "--", "env"]',
        'command.append(f"GOODQ_PROBE_WORKSPACE={workspace}")',
        '"HF_HUB_OFFLINE=1"',
        '"bash"',
        '"-lc"',
        'translated.stdout.strip(),',
        "': \"${GOODQ_PROBE_WORKSPACE:=$HOME/goodq_audio}\"; '",
    )
    compatible = (
        shell_assignment is not None
        and not (referenced_names & unsafe_names)
        and not any(isinstance(node, ast.FormattedValue) for node in ast.walk(shell_assignment))
        and _has_markers(sources["profile_verify"], markers)
        and "json.dumps(translated.stdout.strip())" not in sources["profile_verify"]
    )
    return _result(
        "wsl_argument_transport",
        compatible,
        "WSL values must remain argv or environment entries outside the fixed shell program",
    )


def _ordering_checks(sources: dict[str, str]) -> list[CheckResult]:
    gate = (
        '"%GOODQ_DEV_PYTHON%" "%REPO_ROOT%\\scripts\\install\\'
        'verify_installer_semantic_contract.py" --check --repo-root "%REPO_ROOT%"'
    )
    release_ok = _ordered(
        sources["release_batch"],
        (
            "--phase prebuild",
            gate,
            "powershell -NoProfile -ExecutionPolicy Bypass -File .\\preflight_check.ps1",
            'mkdir "%GOODQ_RELEASE_OUTPUT_ROOT%"',
        ),
    )
    release_gate_start = sources["release_batch"].find(gate)
    release_preflight_start = sources["release_batch"].find(
        "powershell -NoProfile -ExecutionPolicy Bypass -File .\\preflight_check.ps1"
    )
    release_gate_block = sources["release_batch"][
        release_gate_start:release_preflight_start
    ]
    release_ok = release_ok and _has_markers(
        release_gate_block,
        (
            "if errorlevel 1 (",
            "Installer components are semantically incompatible. No output was created.",
            "popd",
            "goto :failed",
        ),
    )
    builder = sources["builder_batch"]
    builder_markers = (
        gate,
        'if exist "staged" (',
        'mkdir "%STAGING_ROOT%"',
        'mklink /J "staged" "%STAGING_ROOT%"',
    )
    builder_ok = (
        builder.count(gate) == 1
        and all(builder.count(marker) == 1 for marker in builder_markers[1:])
        and builder.find("--phase source") < builder.find(gate)
        and [builder.find(marker) for marker in builder_markers]
        == sorted(builder.find(marker) for marker in builder_markers)
    )
    builder_gate_block = builder[
        builder.find(gate):builder.find('if exist "staged" (')
    ]
    builder_ok = builder_ok and _has_markers(
        builder_gate_block,
        (
            "if %ERRORLEVEL% neq 0 (",
            "Installer components are semantically incompatible. No staging was created.",
            "exit /b 117",
        ),
    )
    ci_gate = (
        "conda run -n goodq_core python scripts/install/"
        "verify_installer_semantic_contract.py --check --repo-root ."
    )
    ci_ok = (
        "- name: Installer semantic compatibility" in sources["ci"]
        and _ordered(
            sources["ci"],
            (ci_gate, "conda run -n goodq_core python -m pytest -q"),
        )
    )
    return [
        _result(
            "release_entrypoint_order",
            release_ok,
            "release gate must follow receipt verification and precede network preflight/output creation",
        ),
        _result(
            "builder_entrypoint_order",
            builder_ok,
            "builder gate must follow source verification and precede staging checks/creation",
        ),
        _result("ci_order", ci_ok, "CI semantic gate must run before the test suite"),
    ]


def check_repository(repo_root: Path) -> dict[str, object]:
    root = repo_root.resolve()
    if not root.is_dir():
        raise SemanticContractConfigurationError(f"repository root is unavailable: {root}")
    sources = _load_sources(root)
    checks = [
        *_schema_checks(sources),
        _version_projection_check(sources),
        _profile_check(sources),
        _required_field_check(sources),
        _install_receipt_check(sources),
        _payload_binding_check(sources),
        _cli_check(sources),
        _authenticated_handoff_check(sources),
        _single_handle_check(sources),
        _wsl_check(sources),
        *_ordering_checks(sources),
    ]
    compatible = all(check.status == "compatible" for check in checks)
    return {
        "schema": REPORT_SCHEMA,
        "status": "compatible" if compatible else "mismatch",
        "compatible": compatible,
        "repo_root": str(root),
        "checks": [asdict(check) for check in checks],
    }


def _print_human(report: dict[str, object]) -> None:
    status = str(report["status"]).upper()
    print(f"[{status}] Installer semantic compatibility")
    for check in report.get("checks", []):
        prefix = "OK" if check["status"] == "compatible" else "MISMATCH"
        print(f"[{prefix}] {check['name']}: {check['detail']}")
    if report.get("error"):
        print(f"[ERROR] {report['error']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = check_repository(args.repo_root)
        exit_code = 0 if report["compatible"] else 2
    except (OSError, ValueError, SemanticContractConfigurationError) as exc:
        report = {
            "schema": REPORT_SCHEMA,
            "status": "error",
            "compatible": False,
            "repo_root": str(args.repo_root.resolve()),
            "checks": [],
            "error": str(exc),
        }
        exit_code = 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
