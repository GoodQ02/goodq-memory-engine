"""Create and verify immutable, content-addressed personal asset snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class VaultError(RuntimeError):
    """Raised when a source asset cannot satisfy the vault contract."""


@dataclass(frozen=True)
class SnapshotResult:
    """A sealed snapshot path and its immutable source identity."""

    path: Path
    asset_id: str
    revision: str
    manifest_sha256: str


def _canonical_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _write_json(path: Path, value: object) -> None:
    path.write_text(_canonical_json(value), encoding="utf-8")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one regular file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_relative(root: Path, member: Path) -> str:
    try:
        relative = member.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise VaultError(f"source member escapes source directory: {member}") from exc
    return relative.as_posix()


def inventory_source(source_dir: Path) -> list[dict[str, object]]:
    """Inventory regular source files deterministically without mutating them."""

    source_dir = source_dir.resolve()
    if not source_dir.is_dir():
        raise VaultError(f"source directory does not exist: {source_dir}")

    inventory: list[dict[str, object]] = []
    for member in sorted(source_dir.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if member.is_dir():
            continue
        if member.is_symlink() or not member.is_file():
            raise VaultError(f"source contains a non-regular file: {member}")
        inventory.append(
            {
                "path": _validated_relative(source_dir, member),
                "size_bytes": member.stat().st_size,
                "sha256": sha256_file(member),
            }
        )
    if not inventory:
        raise VaultError("source directory is empty")
    return inventory


def find_duplicate_members(inventory: Iterable[dict[str, object]]) -> list[dict[str, str]]:
    """Choose the lexically first path as canonical for equal-content members."""

    by_hash: dict[str, list[str]] = {}
    for member in inventory:
        digest = str(member["sha256"])
        by_hash.setdefault(digest, []).append(str(member["path"]))

    duplicates: list[dict[str, str]] = []
    for paths in by_hash.values():
        paths.sort(key=str.casefold)
        for duplicate in paths[1:]:
            duplicates.append({"canonical": paths[0], "duplicate": duplicate})
    return sorted(duplicates, key=lambda item: item["duplicate"].casefold())


def _safe_identifier(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise VaultError(f"invalid {label}: {value!r}")
    return value


def _copy_and_verify(source: Path, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    actual = sha256_file(destination)
    if actual != expected_sha256:
        raise VaultError(f"copy hash mismatch for {source.name}")


def _terms_inventory(terms_files: Iterable[Path]) -> list[tuple[Path, str, str]]:
    entries: list[tuple[Path, str, str]] = []
    for index, raw_path in enumerate(terms_files):
        path = raw_path.resolve()
        if not path.is_file() or path.is_symlink():
            raise VaultError(f"terms input is not a regular file: {raw_path}")
        entries.append((path, f"{index:02d}_{path.name}", sha256_file(path)))
    if not entries:
        raise VaultError("terms input is required before sealing")
    return entries


def seal_snapshot(
    source_dir: Path,
    vault_root: Path,
    asset_id: str,
    revision: str,
    terms_files: list[Path],
    *,
    source_url: str = "",
    disposition: str = "personal_only",
) -> SnapshotResult:
    """Copy hash-distinct source bytes, verify them, and atomically seal a snapshot."""

    asset_id = _safe_identifier(asset_id, "asset id")
    revision = _safe_identifier(revision, "revision")
    inventory = inventory_source(source_dir)
    duplicates = find_duplicate_members(inventory)
    duplicate_paths = {entry["duplicate"] for entry in duplicates}
    canonical_members = [member for member in inventory if member["path"] not in duplicate_paths]
    terms = _terms_inventory(terms_files)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "asset_id": asset_id,
        "revision": revision,
        "source_url": source_url,
        "members": canonical_members,
    }
    manifest_sha256 = hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()
    final_path = vault_root.resolve() / asset_id / f"{revision}-{manifest_sha256[:12]}"
    if final_path.exists():
        raise VaultError(f"sealed snapshot already exists: {final_path}")

    asset_root = final_path.parent
    asset_root.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(tempfile.mkdtemp(prefix=".seal-", dir=asset_root))
    try:
        source_root = source_dir.resolve()
        for member in canonical_members:
            relative = Path(str(member["path"]))
            _copy_and_verify(source_root / relative, temporary_path / "source" / relative, str(member["sha256"]))
        terms_manifest: list[dict[str, str]] = []
        for source, target_name, digest in terms:
            target = temporary_path / "terms" / target_name
            _copy_and_verify(source, target, digest)
            terms_manifest.append({"path": f"terms/{target_name}", "sha256": digest})

        _write_json(temporary_path / "source-manifest.json", manifest)
        _write_json(temporary_path / "duplicates.json", {"duplicates": duplicates})
        _write_json(
            temporary_path / "disposition.json",
            {"asset_id": asset_id, "disposition": disposition, "source_url": source_url},
        )
        (temporary_path / "README.md").write_text(
            f"# {asset_id} source snapshot\n\nRevision: `{revision}`\n\n"
            "This directory is immutable after `seal.json` is written.\n",
            encoding="utf-8",
        )
        seal = {
            "schema_version": 1,
            "asset_id": asset_id,
            "revision": revision,
            "source_manifest_sha256": manifest_sha256,
            "terms": terms_manifest,
        }
        _write_json(temporary_path / "seal.json", seal)
        verify_snapshot(temporary_path)
        os.replace(temporary_path, final_path)
    except Exception:
        shutil.rmtree(temporary_path, ignore_errors=True)
        raise

    return SnapshotResult(final_path, asset_id, revision, manifest_sha256)


def verify_snapshot(seal_path: Path) -> SnapshotResult:
    """Verify every retained source and terms file against its immutable seal."""

    seal_path = seal_path.resolve()
    try:
        seal = json.loads((seal_path / "seal.json").read_text(encoding="utf-8"))
        manifest = json.loads((seal_path / "source-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VaultError(f"invalid sealed snapshot: {seal_path}") from exc

    manifest_sha256 = hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()
    if manifest_sha256 != seal.get("source_manifest_sha256"):
        raise VaultError("source manifest digest does not match seal")
    for member in manifest.get("members", []):
        relative = Path(str(member["path"]))
        candidate = seal_path / "source" / relative
        if not candidate.is_file() or sha256_file(candidate) != member["sha256"]:
            raise VaultError(f"sealed source verification failed: {relative}")
    for term in seal.get("terms", []):
        candidate = seal_path / str(term["path"])
        if not candidate.is_file() or sha256_file(candidate) != term["sha256"]:
            raise VaultError(f"sealed terms verification failed: {term['path']}")
    return SnapshotResult(
        seal_path,
        str(seal["asset_id"]),
        str(seal["revision"]),
        manifest_sha256,
    )


def cleanup_duplicates(source_dir: Path, seal_path: Path) -> list[str]:
    """Delete only duplicate source members that a verified seal explicitly names."""

    verified = verify_snapshot(seal_path)
    source_dir = source_dir.resolve()
    source_inventory = {entry["path"]: entry for entry in inventory_source(source_dir)}
    manifest = json.loads((verified.path / "source-manifest.json").read_text(encoding="utf-8"))
    expected = {entry["path"]: entry["sha256"] for entry in manifest["members"]}
    for relative, digest in expected.items():
        observed = source_inventory.get(relative)
        if observed is None or observed["sha256"] != digest:
            raise VaultError(f"retained source verification failed: {relative}")

    duplicates = json.loads((verified.path / "duplicates.json").read_text(encoding="utf-8"))["duplicates"]
    removed: list[str] = []
    for entry in duplicates:
        canonical = str(entry["canonical"])
        duplicate = str(entry["duplicate"])
        canonical_digest = expected.get(canonical)
        observed = source_inventory.get(duplicate)
        if canonical_digest is None or observed is None or observed["sha256"] != canonical_digest:
            raise VaultError(f"duplicate source verification failed: {duplicate}")
        duplicate_path = source_dir / Path(duplicate)
        if _validated_relative(source_dir, duplicate_path) != duplicate:
            raise VaultError(f"duplicate path escapes source directory: {duplicate}")
        duplicate_path.unlink()
        removed.append(duplicate)
    return removed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and verify immutable personal asset snapshots")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory = subparsers.add_parser("inventory", help="inventory a source directory without mutation")
    inventory.add_argument("--source-dir", type=Path, required=True)

    seal = subparsers.add_parser("seal", help="copy, verify, and atomically seal a source snapshot")
    seal.add_argument("--source-dir", type=Path, required=True)
    seal.add_argument("--vault-root", type=Path, required=True)
    seal.add_argument("--asset-id", required=True)
    seal.add_argument("--revision", required=True)
    seal.add_argument("--terms-file", type=Path, action="append", required=True)
    seal.add_argument("--source-url", default="")
    seal.add_argument("--disposition", default="personal_only")

    verify = subparsers.add_parser("verify", help="verify an immutable snapshot")
    verify.add_argument("--seal-path", type=Path, required=True)

    cleanup = subparsers.add_parser("cleanup-duplicates", help="remove only verified source duplicates")
    cleanup.add_argument("--source-dir", type=Path, required=True)
    cleanup.add_argument("--seal-path", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one vault command and emit a JSON receipt suitable for operator logs."""

    args = _parser().parse_args(argv)
    try:
        if args.command == "inventory":
            print(_canonical_json({"members": inventory_source(args.source_dir)}), end="")
        elif args.command == "seal":
            result = seal_snapshot(
                args.source_dir,
                args.vault_root,
                args.asset_id,
                args.revision,
                args.terms_file,
                source_url=args.source_url,
                disposition=args.disposition,
            )
            print(_canonical_json({"asset_id": result.asset_id, "manifest_sha256": result.manifest_sha256, "seal_path": str(result.path)}), end="")
        elif args.command == "verify":
            result = verify_snapshot(args.seal_path)
            print(_canonical_json({"asset_id": result.asset_id, "manifest_sha256": result.manifest_sha256, "seal_path": str(result.path), "verified": True}), end="")
        else:
            removed = cleanup_duplicates(args.source_dir, args.seal_path)
            print(_canonical_json({"removed": removed, "seal_path": str(args.seal_path.resolve())}), end="")
    except VaultError as exc:
        print(f"vault error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
