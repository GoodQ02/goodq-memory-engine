"""Build and apply bounded, signed offline release payload packs.

NSIS is deliberately kept as a small bootstrap.  Complete offline profiles can
contain many gigabytes of sealed models and wheels, which are distributed as
independent ZIP payload packs beside the bootstrap executable.  The signed
payload manifest binds each pack name, byte count, and SHA256 before the
bootstrap extracts anything into the target layout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Iterable


# Payload packs live beside the small NSIS bootstrap, so their boundary is a
# delivery constraint rather than an NSIS data-block limit.  It must admit the
# largest sealed public GPU model shard (currently DeepSeek 14B at ~8.12 GiB).
DEFAULT_MAX_PACK_BYTES = 10 * 1024 * 1024 * 1024
SCHEMA_VERSION = 1


class PayloadPackError(RuntimeError):
    """Raised when an offline payload pack cannot be safely produced or applied."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
                entries.append((file_path, f"{destination_root}/{file_path.relative_to(source).as_posix()}"))
        else:
            raise PayloadPackError(f"payload source missing: {source}")
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


def build(*, staging_root: Path, output_root: Path, version: str, profile: str, max_pack_bytes: int) -> Path:
    entries = _entries(staging_root)
    groups = _split(entries, max_pack_bytes)
    pack_root = output_root / "payloads"
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True)
    records: list[dict[str, object]] = []
    for index, group in enumerate(groups, start=1):
        filename = f"GoodQ4All_{version}_{profile.lower()}_payload_{index:03d}.zip"
        pack_path = pack_root / filename
        with zipfile.ZipFile(pack_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for source, archive_name in group:
                archive.write(source, archive_name)
        if pack_path.stat().st_size > max_pack_bytes:
            raise PayloadPackError(f"pack exceeds bounded size after archive creation: {pack_path}")
        records.append(
            {
                "path": f"payloads/{filename}",
                "sha256": sha256(pack_path),
                "size_bytes": pack_path.stat().st_size,
                "member_count": len(group),
            }
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "product_version": version,
        "profile": profile,
        "pack_format": "zip_stored_zip64",
        "max_pack_bytes": max_pack_bytes,
        "packs": records,
    }
    manifest_path = output_root / f"GoodQ4All_Setup_{version}.payload_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def _validate_relative(path_text: object) -> Path:
    path = Path(str(path_text))
    if path.is_absolute() or ".." in path.parts:
        raise PayloadPackError(f"unsafe payload path: {path_text}")
    return path


def apply(*, bundle_root: Path, install_dir: Path, data_dir: Path, manifest_path: Path | None = None) -> Path:
    manifest_path = manifest_path or next(bundle_root.glob("GoodQ4All_Setup_*.payload_manifest.json"), None)
    if manifest_path is None or not manifest_path.is_file():
        raise PayloadPackError("signed release payload manifest is missing beside the installer")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        packs = manifest["packs"]
    except (OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise PayloadPackError("release payload manifest is unreadable") from exc
    if manifest.get("schema_version") != SCHEMA_VERSION or not isinstance(packs, list) or not packs:
        raise PayloadPackError("release payload manifest has an unsupported schema or no packs")
    for record in packs:
        if not isinstance(record, dict):
            raise PayloadPackError("release payload manifest contains an invalid pack record")
        relative = _validate_relative(record.get("path"))
        pack_path = bundle_root / relative
        expected_hash = str(record.get("sha256") or "").lower()
        if not pack_path.is_file() or len(expected_hash) != 64:
            raise PayloadPackError(f"payload pack is missing or unsigned: {relative}")
        if pack_path.stat().st_size != int(record.get("size_bytes") or -1):
            raise PayloadPackError(f"payload pack byte count mismatch: {relative}")
        if sha256(pack_path).lower() != expected_hash:
            raise PayloadPackError(f"payload pack SHA256 mismatch: {relative}")
    for record in packs:
        pack_path = bundle_root / _validate_relative(record["path"])
        with zipfile.ZipFile(pack_path) as archive:
            for member in archive.infolist():
                member_path = _validate_relative(member.filename)
                if member.is_dir():
                    continue
                if member_path.parts[0] == "program_files":
                    target = install_dir.joinpath(*member_path.parts[1:])
                elif member_path.parts[:2] == ("program_data", "models"):
                    target = data_dir / "models" / Path(*member_path.parts[2:])
                else:
                    raise PayloadPackError(f"payload archive contains an unsupported target: {member.filename}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "applied",
        "payload_manifest": manifest_path.name,
        "payload_manifest_sha256": sha256(manifest_path),
        "profile": manifest.get("profile"),
        "packs": packs,
    }
    receipt_path = data_dir / "payload_install_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    apply_parser.add_argument("--manifest-path", type=Path)
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
                )
            )
        else:
            print(
                apply(
                    bundle_root=args.bundle_root,
                    install_dir=args.install_dir,
                    data_dir=args.data_dir,
                    manifest_path=args.manifest_path,
                )
            )
    except (OSError, ValueError, PayloadPackError, zipfile.BadZipFile) as exc:
        print(f"release payload pack failure: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
