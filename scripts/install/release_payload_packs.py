"""Build and apply member-complete signed offline release payload packs.

NSIS remains a small bootstrap while sealed models, wheels, and vendor payloads
ship as ZIP64 archives beside it.  Schema v2 binds both each pack and every
archive member to the selected-capability and transformed-model inventories.
Extraction is allowed only after the complete archive set is closed, and the
installed copy of every member is re-hashed before a receipt is written.

Historical schema-v1 receipts remain historical evidence.  They are never
accepted or reinterpreted as schema-v2 release evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import time
import zipfile
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, BinaryIO, Callable, Iterable, Iterator

if __package__:
    from .installer_contract import (
        MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
        MODEL_MEMBER_MANIFEST_SCHEMA_VERSION,
        PAYLOAD_INSTALL_RECEIPT_REQUIRED_FIELDS,
        PAYLOAD_INSTALL_RECEIPT_SCHEMA_VERSION,
        PAYLOAD_INSTALL_RECEIPT_STATUS,
        PAYLOAD_MANIFEST_REQUIRED_FIELDS,
        PAYLOAD_MANIFEST_SCHEMA_VERSION,
        PAYLOAD_MEMBER_REQUIRED_FIELDS,
        PAYLOAD_PACK_FORMAT,
        PAYLOAD_PACK_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_SCHEMA_VERSION,
    )
else:
    from installer_contract import (
        MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
        MODEL_MEMBER_MANIFEST_SCHEMA_VERSION,
        PAYLOAD_INSTALL_RECEIPT_REQUIRED_FIELDS,
        PAYLOAD_INSTALL_RECEIPT_SCHEMA_VERSION,
        PAYLOAD_INSTALL_RECEIPT_STATUS,
        PAYLOAD_MANIFEST_REQUIRED_FIELDS,
        PAYLOAD_MANIFEST_SCHEMA_VERSION,
        PAYLOAD_MEMBER_REQUIRED_FIELDS,
        PAYLOAD_PACK_FORMAT,
        PAYLOAD_PACK_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_REQUIRED_FIELDS,
        SELECTED_CAPABILITIES_SCHEMA_VERSION,
    )


# Payload packs live beside the small NSIS bootstrap, so their boundary is a
# delivery constraint rather than an NSIS data-block limit.  It must admit the
# largest sealed public GPU model member (currently Gemma 4 12B at ~22.28 GiB)
# without splitting a signed model file across independently verified packs.
DEFAULT_MAX_PACK_BYTES = 32 * 1024 * 1024 * 1024
COPY_CHUNK_BYTES = 16 * 1024 * 1024
DEFAULT_HEARTBEAT_SECONDS = 30.0


class PayloadPackError(RuntimeError):
    """Raised when an offline payload pack cannot be safely produced or applied."""


def _require_fields(
    value: dict[str, Any], required_fields: frozenset[str], label: str
) -> None:
    missing = sorted(required_fields - set(value))
    if missing:
        raise PayloadPackError(f"{label} is missing required field: {missing[0]}")


def _format_bytes(value: int) -> str:
    return f"{value / 1024**3:.2f} GiB"


def sha256(
    path: Path,
    *,
    progress: Callable[[str], None] | None = None,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
) -> str:
    if heartbeat_seconds < 0:
        raise ValueError("heartbeat interval must not be negative")
    digest = hashlib.sha256()
    total_bytes = path.stat().st_size
    copied_bytes = 0
    last_heartbeat = time.monotonic()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(COPY_CHUNK_BYTES), b""):
            digest.update(chunk)
            copied_bytes += len(chunk)
            if progress and time.monotonic() - last_heartbeat >= heartbeat_seconds:
                progress(
                    f"[PAYLOAD] hash heartbeat: {path.name} "
                    f"{_format_bytes(copied_bytes)} / {_format_bytes(total_bytes)}"
                )
                last_heartbeat = time.monotonic()
    return digest.hexdigest()


def _json_inventory_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _expect_sha256(value: object, label: str) -> str:
    digest = str(value or "").casefold()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise PayloadPackError(f"{label} is not a SHA256 digest")
    return digest


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PayloadPackError(f"{label} is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise PayloadPackError(f"{label} must be a JSON object")
    return value


def _read_json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadPackError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise PayloadPackError(f"{label} must be a JSON object")
    return value


@contextmanager
def _open_pack_for_apply(path: Path) -> Iterator[BinaryIO]:
    """Hold one pack open for the complete verify-and-extract transaction."""

    if os.name != "nt":
        with path.open("rb") as handle:
            yield handle
        return

    import ctypes
    import msvcrt
    from ctypes import wintypes

    generic_read = 0x80000000
    file_share_read = 0x00000001
    open_existing = 3
    file_attribute_normal = 0x00000080
    file_flag_sequential_scan = 0x08000000
    invalid_handle_value = ctypes.c_void_p(-1).value

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    native_handle = create_file(
        str(path),
        generic_read,
        file_share_read,
        None,
        open_existing,
        file_attribute_normal | file_flag_sequential_scan,
        None,
    )
    if native_handle == invalid_handle_value:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, ctypes.FormatError(error_code), str(path))
    try:
        descriptor = msvcrt.open_osfhandle(
            int(native_handle), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
    except Exception:
        close_handle(native_handle)
        raise
    with os.fdopen(descriptor, "rb", buffering=0) as handle:
        yield handle


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def _entries(staging_root: Path) -> list[tuple[Path, str]]:
    mappings = (
        (staging_root / "vendor", "program_files/vendor"),
        (staging_root / "wheels", "program_files/wheels"),
        (staging_root / "wheelhouse-sbom.json", "program_files/wheelhouse-sbom.json"),
        (staging_root / "models", "program_data/models"),
    )
    entries: list[tuple[Path, str]] = []
    for source, destination_root in mappings:
        if source.is_file():
            entries.append((source, destination_root))
        elif source.is_dir():
            for file_path in _iter_files(source):
                entries.append(
                    (file_path, f"{destination_root}/{file_path.relative_to(source).as_posix()}")
                )
        else:
            raise PayloadPackError(f"payload source missing: {source}")
    names = [archive_name for _source, archive_name in entries]
    if len(names) != len(set(names)):
        raise PayloadPackError("payload staging produces duplicate member paths")
    for archive_name in names:
        _target_kind(archive_name)
    return entries


def _split(entries: list[tuple[Path, str]], max_pack_bytes: int) -> list[list[tuple[Path, str]]]:
    if max_pack_bytes <= 0:
        raise PayloadPackError("max pack size must be positive")
    groups: list[list[tuple[Path, str]]] = []
    current: list[tuple[Path, str]] = []
    current_bytes = 0
    for source, archive_name in entries:
        size = source.stat().st_size
        if size > max_pack_bytes:
            raise PayloadPackError(
                f"payload member exceeds pack boundary ({size} > {max_pack_bytes}): {source}"
            )
        if current and current_bytes + size > max_pack_bytes:
            groups.append(current)
            current = []
            current_bytes = 0
        current.append((source, archive_name))
        current_bytes += size
    if current:
        groups.append(current)
    return groups


def _validate_relative(path_text: object) -> PurePosixPath:
    text = str(path_text or "")
    posix_path = PurePosixPath(text)
    windows_path = PureWindowsPath(text)
    if (
        not text
        or "\x00" in text
        or "\\" in text
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or any(part in {"", ".", ".."} for part in posix_path.parts)
        or posix_path.as_posix() != text
    ):
        raise PayloadPackError(f"unsafe payload path: {path_text}")
    return posix_path


def _target_kind(path_text: object) -> str:
    member_path = _validate_relative(path_text)
    if len(member_path.parts) > 1 and member_path.parts[0] == "program_files":
        return "program_files"
    if len(member_path.parts) > 2 and member_path.parts[:2] == ("program_data", "models"):
        return "program_data_models"
    raise PayloadPackError(f"payload archive contains an unsupported target: {path_text}")


def _target_path(
    path_text: object,
    *,
    install_dir: Path,
    data_dir: Path,
) -> Path:
    member_path = _validate_relative(path_text)
    kind = _target_kind(path_text)
    if kind == "program_files":
        root = install_dir
        target = root.joinpath(*member_path.parts[1:])
    else:
        root = data_dir / "models"
        target = root.joinpath(*member_path.parts[2:])
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if target_resolved != root_resolved and root_resolved not in target_resolved.parents:
        raise PayloadPackError(f"payload target escapes its install root: {path_text}")
    return target


def _validate_model_build_evidence(
    *,
    staging_root: Path,
    profile: str,
    entries: list[tuple[Path, str]],
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    selected_path = staging_root / "configs" / "selected_capabilities.json"
    model_manifest_path = staging_root / "configs" / "model_member_manifest.json"
    if not selected_path.is_file() or not model_manifest_path.is_file():
        raise PayloadPackError(
            "selected-capability and model-member evidence must be staged before payload packing"
        )
    selected = _read_json(selected_path, "selected capability receipt")
    model_manifest = _read_json(model_manifest_path, "model member manifest")
    _require_fields(
        selected,
        SELECTED_CAPABILITIES_REQUIRED_FIELDS,
        "selected capability receipt",
    )
    _require_fields(
        model_manifest,
        MODEL_MEMBER_MANIFEST_REQUIRED_FIELDS,
        "model member manifest",
    )
    if selected.get("schema_version") != SELECTED_CAPABILITIES_SCHEMA_VERSION:
        raise PayloadPackError("selected capability receipt must use schema version 2")
    if model_manifest.get("schema_version") != MODEL_MEMBER_MANIFEST_SCHEMA_VERSION:
        raise PayloadPackError("model member manifest must use schema version 2")
    if selected.get("profile") != profile or model_manifest.get("profile") != profile:
        raise PayloadPackError("profile does not match staged capability evidence")

    selector_sha256 = _expect_sha256(selected.get("selector_sha256"), "selector digest")
    asset_inventory_sha256 = _expect_sha256(
        selected.get("asset_inventory_sha256"), "asset inventory digest"
    )
    manifest_sha256 = sha256(model_manifest_path)
    manifest_reference = selected.get("model_member_manifest")
    if not isinstance(manifest_reference, dict):
        raise PayloadPackError("selected capability receipt has no model member manifest binding")
    if _expect_sha256(manifest_reference.get("sha256"), "model manifest reference") != manifest_sha256:
        raise PayloadPackError("model member manifest hash does not match selected capabilities")

    members = model_manifest.get("members")
    if not isinstance(members, list) or not members:
        raise PayloadPackError("model member manifest has no members")
    paths = [str(member.get("path") or "") for member in members if isinstance(member, dict)]
    if len(paths) != len(members) or paths != sorted(paths) or len(paths) != len(set(paths)):
        raise PayloadPackError("model member manifest paths must be unique and sorted")
    if model_manifest.get("member_count") != len(members):
        raise PayloadPackError("model member manifest count mismatch")
    inventory_sha256 = _expect_sha256(
        model_manifest.get("inventory_sha256"), "model member inventory digest"
    )
    if _json_inventory_sha256(members) != inventory_sha256:
        raise PayloadPackError("model member inventory digest mismatch")
    if (
        _expect_sha256(
            manifest_reference.get("inventory_sha256"), "selected model inventory digest"
        )
        != inventory_sha256
        or manifest_reference.get("member_count") != len(members)
    ):
        raise PayloadPackError("selected capability model inventory binding mismatch")

    declared: dict[str, dict[str, Any]] = {}
    for member in members:
        if not isinstance(member, dict):
            raise PayloadPackError("model member manifest contains an invalid member")
        member_path = _validate_relative(member.get("path")).as_posix()
        expected_hash = _expect_sha256(member.get("sha256"), f"model member {member_path}")
        try:
            expected_size = int(member.get("size_bytes"))
        except (TypeError, ValueError) as exc:
            raise PayloadPackError(f"model member size is invalid: {member_path}") from exc
        if expected_size < 0:
            raise PayloadPackError(f"model member size is invalid: {member_path}")
        _expect_sha256(
            member.get("source_manifest_sha256"), f"model member source seal {member_path}"
        )
        if not isinstance(member.get("provenance"), dict) or not member["provenance"].get("type"):
            raise PayloadPackError(f"model member provenance is missing: {member_path}")
        declared[member_path] = {
            "sha256": expected_hash,
            "size_bytes": expected_size,
        }

    actual = {
        PurePosixPath(archive_name).relative_to("program_data/models").as_posix(): source
        for source, archive_name in entries
        if archive_name.startswith("program_data/models/")
    }
    if set(actual) != set(declared):
        missing = sorted(set(declared) - set(actual))
        orphaned = sorted(set(actual) - set(declared))
        detail = missing[0] if missing else orphaned[0]
        raise PayloadPackError(f"model membership mismatch: {detail}")
    for member_path, source in actual.items():
        expected = declared[member_path]
        if source.stat().st_size != expected["size_bytes"]:
            raise PayloadPackError(f"staged model member size mismatch: {member_path}")
        if sha256(source) != expected["sha256"]:
            raise PayloadPackError(f"staged model member SHA256 mismatch: {member_path}")

    bindings = {
        "selected_capabilities_sha256": sha256(selected_path),
        "selected_asset_selector_sha256": selector_sha256,
        "selected_asset_inventory_sha256": asset_inventory_sha256,
        "model_member_manifest_sha256": manifest_sha256,
        "model_member_inventory_sha256": inventory_sha256,
    }
    return bindings, declared


def _write_member(
    archive: zipfile.ZipFile,
    source: Path,
    archive_name: str,
    *,
    progress: Callable[[str], None],
    heartbeat_seconds: float,
) -> None:
    total_bytes = source.stat().st_size
    copied_bytes = 0
    last_heartbeat = time.monotonic()
    progress(f"[PAYLOAD] copying: {archive_name} ({_format_bytes(total_bytes)})")
    info = zipfile.ZipInfo.from_file(source, arcname=archive_name)
    info.compress_type = zipfile.ZIP_STORED
    with source.open("rb") as source_handle, archive.open(
        info, mode="w", force_zip64=True
    ) as destination:
        for chunk in iter(lambda: source_handle.read(COPY_CHUNK_BYTES), b""):
            destination.write(chunk)
            copied_bytes += len(chunk)
            if time.monotonic() - last_heartbeat >= heartbeat_seconds:
                progress(
                    f"[PAYLOAD] copy heartbeat: {archive_name} "
                    f"{_format_bytes(copied_bytes)} / {_format_bytes(total_bytes)}"
                )
                last_heartbeat = time.monotonic()
    progress(f"[PAYLOAD] copied: {archive_name} ({_format_bytes(copied_bytes)})")


def build(
    *,
    staging_root: Path,
    output_root: Path,
    version: str,
    profile: str,
    max_pack_bytes: int,
    progress: Callable[[str], None] | None = None,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
) -> Path:
    if heartbeat_seconds < 0:
        raise ValueError("heartbeat interval must not be negative")
    report = progress or (lambda _message: None)
    entries = _entries(staging_root)
    bindings, declared_models = _validate_model_build_evidence(
        staging_root=staging_root,
        profile=profile,
        entries=entries,
    )
    groups = _split(entries, max_pack_bytes)
    report(f"[PAYLOAD] plan: {len(groups)} pack(s), {len(entries)} file(s)")
    pack_root = output_root / "payloads"
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True)
    manifest_path = output_root / f"GoodQ4All_Setup_{version}.payload_manifest.json"
    records: list[dict[str, object]] = []
    member_records: list[dict[str, object]] = []
    for index, group in enumerate(groups, start=1):
        filename = f"GoodQ4All_{version}_{profile.lower()}_payload_{index:03d}.zip"
        pack_relative = f"payloads/{filename}"
        pack_path = pack_root / filename
        group_bytes = sum(source.stat().st_size for source, _archive_name in group)
        report(
            f"[PAYLOAD] writing pack {index}/{len(groups)}: {filename} "
            f"({len(group)} member(s), {_format_bytes(group_bytes)})"
        )
        for source, archive_name in group:
            model_path = (
                PurePosixPath(archive_name).relative_to("program_data/models").as_posix()
                if archive_name.startswith("program_data/models/")
                else None
            )
            expected_hash = (
                str(declared_models[model_path]["sha256"])
                if model_path is not None
                else sha256(source)
            )
            member_records.append(
                {
                    "path": archive_name,
                    "pack_path": pack_relative,
                    "size_bytes": source.stat().st_size,
                    "sha256": expected_hash,
                    "target": _target_kind(archive_name),
                }
            )
        with zipfile.ZipFile(
            pack_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True
        ) as archive:
            for source, archive_name in group:
                _write_member(
                    archive,
                    source,
                    archive_name,
                    progress=report,
                    heartbeat_seconds=heartbeat_seconds,
                )
        if pack_path.stat().st_size > max_pack_bytes:
            raise PayloadPackError(f"pack exceeds bounded size after archive creation: {pack_path}")
        report(f"[PAYLOAD] hashing pack {index}/{len(groups)}: {filename}")
        pack_sha256 = sha256(
            pack_path,
            progress=report,
            heartbeat_seconds=heartbeat_seconds,
        )
        records.append(
            {
                "path": pack_relative,
                "sha256": pack_sha256,
                "size_bytes": pack_path.stat().st_size,
                "member_count": len(group),
            }
        )
        report(
            f"[PAYLOAD] completed pack {index}/{len(groups)}: {filename} "
            f"({_format_bytes(pack_path.stat().st_size)})"
        )
    member_records.sort(key=lambda item: str(item["path"]))
    manifest = {
        "schema_version": PAYLOAD_MANIFEST_SCHEMA_VERSION,
        "product_version": version,
        "profile": profile,
        "pack_format": PAYLOAD_PACK_FORMAT,
        "max_pack_bytes": max_pack_bytes,
        **bindings,
        "member_inventory_sha256": _json_inventory_sha256(member_records),
        "member_count": len(member_records),
        "members": member_records,
        "packs": records,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest_path


def _validate_apply_contract(
    manifest: dict[str, Any],
    *,
    install_dir: Path,
    data_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    _require_fields(manifest, PAYLOAD_MANIFEST_REQUIRED_FIELDS, "release payload manifest")
    schema = manifest.get("schema_version")
    if schema == 1:
        raise PayloadPackError(
            "historical schema v1 payload evidence cannot be reinterpreted as schema v2"
        )
    if schema != PAYLOAD_MANIFEST_SCHEMA_VERSION:
        raise PayloadPackError("release payload manifest uses an unsupported schema")
    if manifest.get("pack_format") != PAYLOAD_PACK_FORMAT:
        raise PayloadPackError("release payload manifest uses an unsupported pack format")
    for field in (
        "selected_capabilities_sha256",
        "selected_asset_selector_sha256",
        "selected_asset_inventory_sha256",
        "model_member_manifest_sha256",
        "model_member_inventory_sha256",
    ):
        _expect_sha256(manifest.get(field), field)

    packs = manifest.get("packs")
    members = manifest.get("members")
    if not isinstance(packs, list) or not packs:
        raise PayloadPackError("release payload manifest has no packs")
    if not isinstance(members, list) or not members:
        raise PayloadPackError("release payload manifest has no members")
    if manifest.get("member_count") != len(members):
        raise PayloadPackError("release payload member count mismatch")
    paths = [str(member.get("path") or "") for member in members if isinstance(member, dict)]
    if len(paths) != len(members) or paths != sorted(paths) or len(paths) != len(set(paths)):
        raise PayloadPackError("release payload member paths must be unique and sorted")
    inventory_sha256 = _expect_sha256(
        manifest.get("member_inventory_sha256"), "payload member inventory digest"
    )
    if _json_inventory_sha256(members) != inventory_sha256:
        raise PayloadPackError("payload member inventory digest mismatch")

    pack_paths: list[str] = []
    pack_records: list[dict[str, Any]] = []
    for record in packs:
        if not isinstance(record, dict):
            raise PayloadPackError("release payload manifest contains an invalid pack record")
        _require_fields(record, PAYLOAD_PACK_REQUIRED_FIELDS, "payload pack record")
        relative = _validate_relative(record.get("path")).as_posix()
        if not relative.startswith("payloads/") or not relative.casefold().endswith(".zip"):
            raise PayloadPackError(f"payload pack has an unsupported location: {relative}")
        _expect_sha256(record.get("sha256"), f"payload pack {relative}")
        try:
            size_bytes = int(record.get("size_bytes"))
            member_count = int(record.get("member_count"))
        except (TypeError, ValueError) as exc:
            raise PayloadPackError(f"payload pack record is malformed: {relative}") from exc
        if size_bytes < 0 or member_count < 1:
            raise PayloadPackError(f"payload pack record is malformed: {relative}")
        pack_paths.append(relative)
        pack_records.append(record)
    if pack_paths != sorted(pack_paths) or len(pack_paths) != len(set(pack_paths)):
        raise PayloadPackError("payload pack paths must be unique and sorted")

    members_by_pack: dict[str, list[dict[str, Any]]] = {path: [] for path in pack_paths}
    for member in members:
        if not isinstance(member, dict):
            raise PayloadPackError("release payload manifest contains an invalid member record")
        _require_fields(member, PAYLOAD_MEMBER_REQUIRED_FIELDS, "payload member record")
        member_path = _validate_relative(member.get("path")).as_posix()
        target = _target_kind(member_path)
        if member.get("target") != target:
            raise PayloadPackError(f"payload member target binding mismatch: {member_path}")
        _target_path(member_path, install_dir=install_dir, data_dir=data_dir)
        pack_path = _validate_relative(member.get("pack_path")).as_posix()
        if pack_path not in members_by_pack:
            raise PayloadPackError(f"payload member references an undeclared pack: {member_path}")
        _expect_sha256(member.get("sha256"), f"payload member {member_path}")
        try:
            size_bytes = int(member.get("size_bytes"))
        except (TypeError, ValueError) as exc:
            raise PayloadPackError(f"payload member size is invalid: {member_path}") from exc
        if size_bytes < 0:
            raise PayloadPackError(f"payload member size is invalid: {member_path}")
        members_by_pack[pack_path].append(member)
    for record in pack_records:
        relative = str(record["path"])
        if int(record["member_count"]) != len(members_by_pack[relative]):
            raise PayloadPackError(f"payload pack member count mismatch: {relative}")
    return pack_records, members, members_by_pack


def _validate_open_archive(
    *,
    archive: zipfile.ZipFile,
    relative: str,
    expected_members: dict[str, dict[str, Any]],
) -> dict[str, zipfile.ZipInfo]:
    info_by_name: dict[str, zipfile.ZipInfo] = {}
    for info in archive.infolist():
        member_name = _validate_relative(info.filename).as_posix()
        _target_kind(member_name)
        if info.is_dir():
            raise PayloadPackError(
                f"payload archive contains an undeclared directory: {member_name}"
            )
        if info.compress_type != zipfile.ZIP_STORED or info.flag_bits & 0x1:
            raise PayloadPackError(
                f"payload archive member is not plain ZIP_STORED: {member_name}"
            )
        unix_mode = (info.external_attr >> 16) & 0o170000
        if unix_mode == stat.S_IFLNK:
            raise PayloadPackError(f"payload archive contains a symbolic link: {member_name}")
        if member_name in info_by_name:
            raise PayloadPackError(f"payload archive contains duplicate members: {relative}")
        info_by_name[member_name] = info
    if set(info_by_name) != set(expected_members):
        raise PayloadPackError(f"payload archive membership mismatch: {relative}")
    for member_name, info in info_by_name.items():
        if info.file_size != int(expected_members[member_name]["size_bytes"]):
            raise PayloadPackError(f"payload member size mismatch: {member_name}")
    return info_by_name


def _apply_pack_archives(
    *,
    bundle_root: Path,
    install_dir: Path,
    data_dir: Path,
    pack_records: list[dict[str, Any]],
    members_by_pack: dict[str, list[dict[str, Any]]],
) -> list[dict[str, object]]:
    verified_archives: list[
        tuple[str, zipfile.ZipFile, dict[str, zipfile.ZipInfo]]
    ] = []
    with ExitStack() as stack:
        for record in pack_records:
            relative = _validate_relative(record["path"]).as_posix()
            pack_path = bundle_root.joinpath(*PurePosixPath(relative).parts)
            expected_hash = _expect_sha256(
                record.get("sha256"), f"payload pack {relative}"
            )
            try:
                handle = stack.enter_context(_open_pack_for_apply(pack_path))
            except OSError as exc:
                raise PayloadPackError(
                    f"payload pack is missing or cannot be locked: {relative}"
                ) from exc
            file_info = os.fstat(handle.fileno())
            if not stat.S_ISREG(file_info.st_mode):
                raise PayloadPackError(f"payload pack is not a regular file: {relative}")
            if file_info.st_size != int(record["size_bytes"]):
                raise PayloadPackError(f"payload pack byte count mismatch: {relative}")
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(COPY_CHUNK_BYTES), b""):
                digest.update(chunk)
            if digest.hexdigest().casefold() != expected_hash:
                raise PayloadPackError(f"payload pack SHA256 mismatch: {relative}")
            handle.seek(0)
            archive = stack.enter_context(zipfile.ZipFile(handle))
            expected_members = {
                str(member["path"]): member for member in members_by_pack[relative]
            }
            info_by_name = _validate_open_archive(
                archive=archive,
                relative=relative,
                expected_members=expected_members,
            )
            verified_archives.append((relative, archive, info_by_name))

        for relative, archive, info_by_name in verified_archives:
            for member in sorted(
                members_by_pack[relative], key=lambda item: str(item["path"])
            ):
                member_path = str(member["path"])
                target = _target_path(member_path, install_dir=install_dir, data_dir=data_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.parent / f".{target.name}.goodq-part"
                if temporary.exists():
                    temporary.unlink()
                digest = hashlib.sha256()
                copied_bytes = 0
                try:
                    with archive.open(
                        info_by_name[member_path]
                    ) as source, temporary.open("xb") as destination:
                        for chunk in iter(lambda: source.read(COPY_CHUNK_BYTES), b""):
                            destination.write(chunk)
                            digest.update(chunk)
                            copied_bytes += len(chunk)
                    if copied_bytes != int(member["size_bytes"]):
                        raise PayloadPackError(f"payload member size mismatch: {member_path}")
                    if digest.hexdigest() != str(member["sha256"]):
                        raise PayloadPackError(f"payload member SHA256 mismatch: {member_path}")
                    os.replace(temporary, target)
                finally:
                    if temporary.exists():
                        temporary.unlink()

    installed: list[dict[str, object]] = []
    for members in members_by_pack.values():
        for member in members:
            member_path = str(member["path"])
            target = _target_path(member_path, install_dir=install_dir, data_dir=data_dir)
            if not target.is_file() or target.stat().st_size != int(member["size_bytes"]):
                raise PayloadPackError(f"installed payload member size mismatch: {member_path}")
            installed_hash = sha256(target)
            if installed_hash != str(member["sha256"]):
                raise PayloadPackError(f"installed payload member SHA256 mismatch: {member_path}")
            installed.append(
                {
                    "path": member_path,
                    "size_bytes": target.stat().st_size,
                    "sha256": installed_hash,
                    "status": "verified",
                }
            )
    installed.sort(key=lambda item: str(item["path"]))
    return installed


def apply(
    *,
    bundle_root: Path,
    install_dir: Path,
    data_dir: Path,
    manifest_bytes: bytes,
) -> Path:
    if not manifest_bytes:
        raise PayloadPackError("authenticated release payload manifest bytes are required")
    manifest = _read_json_bytes(manifest_bytes, "release payload manifest")
    pack_records, members, members_by_pack = _validate_apply_contract(
        manifest,
        install_dir=install_dir,
        data_dir=data_dir,
    )
    product_version = manifest.get("product_version")
    if (
        not isinstance(product_version, str)
        or not product_version.strip()
        or product_version != Path(product_version).name
    ):
        raise PayloadPackError("release payload product version is invalid")
    installed_members = _apply_pack_archives(
        bundle_root=bundle_root,
        install_dir=install_dir,
        data_dir=data_dir,
        pack_records=pack_records,
        members_by_pack=members_by_pack,
    )
    receipt = {
        "schema_version": PAYLOAD_INSTALL_RECEIPT_SCHEMA_VERSION,
        "status": PAYLOAD_INSTALL_RECEIPT_STATUS,
        "payload_manifest": f"GoodQ4All_Setup_{product_version}.payload_manifest.json",
        "payload_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "profile": manifest.get("profile"),
        "selected_capabilities_sha256": manifest["selected_capabilities_sha256"],
        "selected_asset_selector_sha256": manifest["selected_asset_selector_sha256"],
        "selected_asset_inventory_sha256": manifest["selected_asset_inventory_sha256"],
        "model_member_manifest_sha256": manifest["model_member_manifest_sha256"],
        "model_member_inventory_sha256": manifest["model_member_inventory_sha256"],
        "member_inventory_sha256": manifest["member_inventory_sha256"],
        "member_count": len(members),
        "installed_members": installed_members,
        "packs": pack_records,
    }
    _require_fields(
        receipt,
        PAYLOAD_INSTALL_RECEIPT_REQUIRED_FIELDS,
        "payload install receipt",
    )
    receipt_path = data_dir / "payload_install_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--staging-root", type=Path, required=True)
    build_parser.add_argument("--output-root", type=Path, required=True)
    build_parser.add_argument("--version", required=True)
    build_parser.add_argument("--profile", required=True)
    build_parser.add_argument("--max-pack-bytes", type=int, default=DEFAULT_MAX_PACK_BYTES)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--bundle-root", type=Path, required=True)
    apply_parser.add_argument("--install-dir", type=Path, required=True)
    apply_parser.add_argument("--data-dir", type=Path, required=True)
    apply_parser.add_argument("--manifest-stdin", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            print(
                build(
                    staging_root=args.staging_root,
                    output_root=args.output_root,
                    version=args.version,
                    profile=args.profile,
                    max_pack_bytes=args.max_pack_bytes,
                    progress=lambda message: print(message, flush=True),
                )
            )
        else:
            print(
                apply(
                    bundle_root=args.bundle_root,
                    install_dir=args.install_dir,
                    data_dir=args.data_dir,
                    manifest_bytes=sys.stdin.buffer.read(),
                )
            )
    except (OSError, ValueError, PayloadPackError, zipfile.BadZipFile) as exc:
        print(f"release payload pack failure: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
