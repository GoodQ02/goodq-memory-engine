#!/usr/bin/env python3
"""Build and validate the GoodQ host-tools release asset.

This script intentionally does not discover local machine paths. Operators must
point it at an accepted staged host-tools payload and an output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable


ASSET_NAME = "goodq4all-0.1.1-host-tools-windows-x86_64.zip"
EXPECTED_GROUPS = ("ffmpeg", "nssm", "piper", "poppler", "qdrant", "tesseract")
EXPECTED_NSSM_SHA256 = (
    "EEE9C44C29C2BE011F1F1E43BB8C3FCA888CB81053022EC5A0060035DE16D848"
)
FIXED_ZIP_DATE = (2026, 1, 1, 0, 0, 0)
BUILDER_VERSION = 1

LOCAL_DRIVE_PATTERN = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")
WSL_UNC_MARKER = "\\\\" + "wsl"
TOKEN_MARKERS = (
    "s" + "k-",
    "h" + "f_",
    "github" + "_pat_",
    "g" + "hp_",
    "AK" + "IA",
    "x" + "oxb",
    "Author" + "ization:",
    "Bear" + "er",
)


class AssetError(RuntimeError):
    """Raised when the release asset cannot be built or validated."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def safe_relative(path: Path, root: Path) -> PurePosixPath:
    rel = path.relative_to(root)
    return PurePosixPath(*rel.parts)


def iter_files(root: Path) -> Iterable[Path]:
    return sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix().lower())


def guard_archive_name(name: PurePosixPath) -> None:
    parts = name.parts
    if name.is_absolute() or ".." in parts:
        raise AssetError(f"Unsafe archive member path: {name}")
    lowered = [part.lower() for part in parts]
    blocked = {".git", ".svn", "__pycache__", "scratch", "downloads", "reports"}
    if any(part in blocked for part in lowered):
        raise AssetError(f"Blocked archive member path: {name}")
    if "control_recurrence" in lowered:
        raise AssetError(f"Blocked control recurrence path: {name}")


def zip_info(name: PurePosixPath, *, executable: bool, compression: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(str(name), FIXED_ZIP_DATE)
    info.compress_type = compression
    mode = 0o755 if executable else 0o644
    info.external_attr = mode << 16
    return info


def is_executable_like(path: Path) -> bool:
    return path.suffix.lower() in {".exe", ".bat", ".cmd", ".ps1", ".sh"}


def write_file(zf: zipfile.ZipFile, source: Path, archive_name: PurePosixPath, compression: int) -> None:
    guard_archive_name(archive_name)
    info = zip_info(archive_name, executable=is_executable_like(source), compression=compression)
    with source.open("rb") as handle:
        zf.writestr(info, handle.read())


def write_text(zf: zipfile.ZipFile, archive_name: PurePosixPath, data: str, compression: int) -> None:
    guard_archive_name(archive_name)
    info = zip_info(archive_name, executable=False, compression=compression)
    zf.writestr(info, data.encode("utf-8"))


def ensure_expected_groups(staging_root: Path) -> list[str]:
    missing = [name for name in EXPECTED_GROUPS if not (staging_root / name).is_dir()]
    if missing:
        raise AssetError(f"Missing host-tool payload groups: {', '.join(missing)}")
    return list(EXPECTED_GROUPS)


def read_staged_manifest(manifest_path: Path | None) -> dict | None:
    if manifest_path is None:
        return None
    if not manifest_path.is_file():
        raise AssetError(f"Manifest not found: {manifest_path}")
    return load_json(manifest_path)


def host_file_manifest_names(staged_manifest: dict | None) -> list[str]:
    if staged_manifest:
        names = []
        for artifact in staged_manifest.get("artifacts", []):
            manifest_ref = artifact.get("files_manifest")
            if manifest_ref:
                names.append(PurePosixPath(str(manifest_ref).replace("\\", "/")).name)
        return sorted(set(names), key=str.lower)

    return [
        "ffmpeg_tool_pack_files.json",
        "nssm_service_helper_files.json",
        "piper_tool_and_voice_pack_files.json",
        "poppler_tool_pack_files.json",
        "qdrant_tool_pack_files.json",
        "tesseract_tool_pack_files.json",
    ]


def default_notice_file() -> Path | None:
    candidate = repo_root() / "THIRD_PARTY_NOTICES.md"
    return candidate if candidate.is_file() else None


def build(args: argparse.Namespace) -> int:
    staging_root = args.staging_root.resolve()
    output_dir = args.output_dir.resolve()
    manifest_path = args.manifest.resolve() if args.manifest else None
    file_manifest_dir = args.file_manifest_dir.resolve() if args.file_manifest_dir else None
    notice_file = None if args.no_notice else (args.notice_file.resolve() if args.notice_file else default_notice_file())

    if not staging_root.is_dir():
        raise AssetError(f"Staged host-tools payload not found: {staging_root}")
    output_dir.mkdir(parents=True, exist_ok=True)

    groups = ensure_expected_groups(staging_root)
    nssm_path = staging_root / "nssm" / "nssm.exe"
    if not nssm_path.is_file():
        raise AssetError("Missing staged NSSM binary at nssm/nssm.exe")
    nssm_sha = sha256_file(nssm_path)
    if nssm_sha != EXPECTED_NSSM_SHA256:
        raise AssetError(f"Unexpected staged NSSM SHA256: {nssm_sha}")

    staged_manifest = read_staged_manifest(manifest_path)
    if file_manifest_dir is None and manifest_path is not None:
        file_manifest_dir = manifest_path.parent

    asset_path = output_dir / args.asset_name
    if asset_path.exists() and not args.force:
        raise AssetError(f"Output already exists; pass --force to overwrite: {asset_path}")
    if asset_path.exists():
        asset_path.unlink()

    compression = zipfile.ZIP_STORED if args.compression == "stored" else zipfile.ZIP_DEFLATED
    release_manifest = {
        "asset_name": args.asset_name,
        "asset_class": "host_tools_payload",
        "builder": "scripts/releases/host_tools_asset.py",
        "builder_version": BUILDER_VERSION,
        "zip_timestamp_policy": "fixed",
        "zip_file_order_policy": "sorted_posix_relative_paths",
        "zip_compression": args.compression,
        "source_pack_id": staged_manifest.get("pack_id") if staged_manifest else None,
        "source_pack_status": staged_manifest.get("status") if staged_manifest else None,
        "source_tree_sha256": staged_manifest.get("sha256") if staged_manifest else None,
        "source_size_bytes": staged_manifest.get("size_bytes") if staged_manifest else None,
        "source_file_count": staged_manifest.get("file_count") if staged_manifest else None,
        "included_payload_groups": groups,
        "expected_nssm_sha256": EXPECTED_NSSM_SHA256,
        "restored_nssm_relative_path": "tools/nssm/nssm.exe",
        "exclusions": [
            "optional corpus/eval/witness/private material",
            "runtime databases and logs",
            "local config and authentication material",
            "scratch artifacts outside the staged host-tools payload",
        ],
        "reproducibility_note": (
            "Archive member paths, order, permissions, and timestamps are fixed. "
            "Use stored compression for the most stable byte-for-byte rebuilds."
        ),
    }

    with zipfile.ZipFile(asset_path, "w", compression=compression, allowZip64=True) as zf:
        for source in iter_files(staging_root):
            rel = PurePosixPath("tools") / safe_relative(source, staging_root)
            write_file(zf, source, rel, compression)

        if manifest_path is not None:
            write_file(zf, manifest_path, PurePosixPath("manifests") / manifest_path.name, compression)
        if file_manifest_dir is not None and file_manifest_dir.is_dir():
            for manifest_name in host_file_manifest_names(staged_manifest):
                source = file_manifest_dir / manifest_name
                if not source.is_file():
                    raise AssetError(f"Expected host-tool file manifest not found: {source}")
                write_file(zf, source, PurePosixPath("manifests") / source.name, compression)
        if notice_file is not None:
            if not notice_file.is_file():
                raise AssetError(f"Notice file not found: {notice_file}")
            write_file(zf, notice_file, PurePosixPath("THIRD_PARTY_NOTICES.md"), compression)

        manifest_text = json.dumps(release_manifest, indent=2, sort_keys=True) + "\n"
        write_text(
            zf,
            PurePosixPath("manifests/host_tools_release_asset_manifest.json"),
            manifest_text,
            compression,
        )

    asset_size = asset_path.stat().st_size
    asset_sha = sha256_file(asset_path)
    result = {
        "asset_path": str(asset_path),
        "asset_name": args.asset_name,
        "asset_sha256": asset_sha,
        "asset_size_bytes": asset_size,
        "source_staging_root": str(staging_root),
        "source_manifest": str(manifest_path) if manifest_path else None,
        "source_tree_sha256": release_manifest["source_tree_sha256"],
        "included_payload_groups": groups,
        "restored_nssm_sha256_expected": EXPECTED_NSSM_SHA256,
        "reproducibility_note": release_manifest["reproducibility_note"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def safe_extract(zf: zipfile.ZipFile, restore_root: Path) -> None:
    root = restore_root.resolve()
    for member in zf.infolist():
        target = (root / member.filename).resolve()
        if root != target and root not in target.parents:
            raise AssetError(f"Unsafe archive extraction path: {member.filename}")
    zf.extractall(root)


def contains_forbidden_text(text: str) -> list[str]:
    hits: list[str] = []
    if LOCAL_DRIVE_PATTERN.search(text):
        hits.append("local-drive-root")
    if WSL_UNC_MARKER.lower() in text.lower():
        hits.append("wsl-unc-root")
    for marker in TOKEN_MARKERS:
        if marker in text:
            hits.append(f"token-marker:{marker[:3]}...")
    return hits


def scan_release_docs(restore_root: Path) -> list[dict]:
    scan_targets: list[Path] = []
    notice = restore_root / "THIRD_PARTY_NOTICES.md"
    if notice.is_file():
        scan_targets.append(notice)
    manifest_dir = restore_root / "manifests"
    if manifest_dir.is_dir():
        scan_targets.extend(sorted(p for p in manifest_dir.rglob("*") if p.is_file()))

    findings: list[dict] = []
    for path in scan_targets:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        hits = contains_forbidden_text(text)
        if hits:
            findings.append({"path": str(path.relative_to(restore_root)), "findings": hits})
    return findings


def validate(args: argparse.Namespace) -> int:
    asset_path = args.asset.resolve()
    if not asset_path.is_file():
        raise AssetError(f"Asset not found: {asset_path}")

    if args.restore_root:
        restore_root = args.restore_root.resolve()
        if restore_root.exists():
            if not args.force:
                raise AssetError(f"Restore root already exists; pass --force to replace: {restore_root}")
            shutil.rmtree(restore_root)
        restore_root.mkdir(parents=True)
        temp_created = False
    else:
        restore_root = Path(tempfile.mkdtemp(prefix="goodq_host_tools_restore_"))
        temp_created = True

    with zipfile.ZipFile(asset_path, "r", allowZip64=True) as zf:
        members = sorted(zf.namelist())
        safe_extract(zf, restore_root)

    required_paths = [
        "THIRD_PARTY_NOTICES.md",
        "manifests/host_tools_release_asset_manifest.json",
        "manifests/host_tools_pack_manifest.json",
        "tools/ffmpeg/bin/ffmpeg.exe",
        "tools/nssm/nssm.exe",
        "tools/qdrant/LICENSE",
        "tools/qdrant/qdrant.exe",
        "tools/tesseract/tesseract.exe",
        "tools/tesseract/doc/LICENSE",
        "tools/poppler/pdftotext.exe",
        "tools/piper/piper/piper.exe",
    ]
    missing = [path for path in required_paths if not (restore_root / Path(path)).is_file()]
    if missing:
        raise AssetError(f"Missing restored required files: {', '.join(missing)}")

    restored_nssm = restore_root / "tools" / "nssm" / "nssm.exe"
    restored_nssm_sha = sha256_file(restored_nssm)
    if restored_nssm_sha != EXPECTED_NSSM_SHA256:
        raise AssetError(f"Unexpected restored NSSM SHA256: {restored_nssm_sha}")

    doc_findings = scan_release_docs(restore_root)
    if doc_findings:
        raise AssetError(f"Forbidden local path or token-shaped text in restored docs/manifests: {doc_findings}")

    result = {
        "asset_path": str(asset_path),
        "asset_sha256": sha256_file(asset_path),
        "asset_size_bytes": asset_path.stat().st_size,
        "member_count": len(members),
        "restore_root": str(restore_root),
        "restore_root_created_by_validator": temp_created,
        "required_files_present": True,
        "restored_nssm_sha256": restored_nssm_sha,
        "restored_docs_manifest_scan": "clean",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build the host-tools release ZIP")
    build_parser.add_argument("--staging-root", type=Path, required=True, help="Directory containing staged host-tool groups")
    build_parser.add_argument("--manifest", type=Path, help="Staged host_tools_pack_manifest.json")
    build_parser.add_argument("--file-manifest-dir", type=Path, help="Directory containing staged *_files.json manifests")
    build_parser.add_argument("--output-dir", type=Path, required=True, help="Directory that receives the release asset")
    build_parser.add_argument("--asset-name", default=ASSET_NAME, help="Release asset file name")
    build_parser.add_argument("--notice-file", type=Path, help="Third-party notice file to include")
    build_parser.add_argument("--no-notice", action="store_true", help="Do not include THIRD_PARTY_NOTICES.md")
    build_parser.add_argument("--compression", choices=("stored", "deflated"), default="stored")
    build_parser.add_argument("--force", action="store_true", help="Overwrite an existing output asset")
    build_parser.set_defaults(func=build)

    validate_parser = subparsers.add_parser("validate", help="Restore and validate a host-tools release ZIP")
    validate_parser.add_argument("--asset", type=Path, required=True, help="Release asset ZIP to validate")
    validate_parser.add_argument("--restore-root", type=Path, help="Temporary restore directory to create")
    validate_parser.add_argument("--force", action="store_true", help="Replace restore root if it already exists")
    validate_parser.set_defaults(func=validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except AssetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
