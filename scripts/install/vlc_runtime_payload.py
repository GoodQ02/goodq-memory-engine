"""Stage and verify the pinned, unmodified personal VLC runtime without network I/O."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "configs" / "offline_dependencies_manifest.json"
RECEIPT = "goodq-vlc-receipt.json"
PROFILE = "PERSONAL_AIR_GAP"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _record(manifest: Path, profile: str) -> dict:
    record = json.loads(manifest.read_text(encoding="utf-8"))["dependencies"]["vlc"]
    if profile != PROFILE or record.get("profiles") != [PROFILE]:
        raise ValueError("VLC payload is admitted only to PERSONAL_AIR_GAP")
    if record.get("redistribution_status") != "personal_only":
        raise ValueError("VLC public redistribution has not been cleared")
    return record


def _relative(value: str) -> Path:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(p in {".", ".."} or ":" in p or "\\" in p for p in path.parts):
        raise ValueError(f"invalid VLC archive member: {value}")
    return Path(*path.parts)


def _inventory(archive: zipfile.ZipFile, prefix: str) -> list[dict]:
    members = []
    seen = set()
    for info in archive.infolist():
        if info.is_dir():
            continue
        if not info.filename.startswith(prefix):
            raise ValueError("VLC archive has an unexpected root")
        relative = _relative(info.filename[len(prefix):]).as_posix()
        if relative.casefold() in seen or stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError("VLC archive has duplicate or linked members")
        seen.add(relative.casefold())
        with archive.open(info) as handle:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        members.append({"path": relative, "size_bytes": info.file_size, "sha256": digest.hexdigest()})
    required = {"vlc.exe", "libvlc.dll", "libvlccore.dll", "COPYING.txt", "plugins/codec/libavcodec_plugin.dll"}
    if not required <= {m["path"] for m in members}:
        raise ValueError("VLC archive lacks required executable, plugins or license")
    return sorted(members, key=lambda m: m["path"])


def stage(archive: Path, destination: Path, manifest: Path, profile: str) -> dict:
    record = _record(manifest, profile)
    if destination.exists():
        raise ValueError("VLC staging destination must be new")
    if archive.stat().st_size != record["size_bytes"] or _sha256(archive) != record["sha256"]:
        raise ValueError("VLC source archive does not match pinned size/SHA256")
    prefix = f"vlc-{record['source_version']}/"
    with zipfile.ZipFile(archive) as bundle:
        members = _inventory(bundle, prefix)
        receipt = {"schema_version": 1, "version": record["source_version"], "archive_sha256": record["sha256"], "members": members}
        if hashlib.sha256(_canonical(receipt)).hexdigest() != record["runtime_manifest_sha256"]:
            raise ValueError("VLC runtime member inventory does not match pinned receipt")
        destination.mkdir(parents=True)
        for member in members:
            target = destination / _relative(member["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(prefix + member["path"]) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
        (destination / RECEIPT).write_bytes(_canonical(receipt))
    return verify(destination, manifest, profile)


def verify(root: Path, manifest: Path, profile: str) -> dict:
    record = _record(manifest, profile)
    receipt_path = root / RECEIPT
    if _sha256(receipt_path) != record["runtime_manifest_sha256"]:
        raise ValueError("VLC runtime receipt does not match pinned inventory")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    for member in receipt["members"]:
        path = root / _relative(member["path"])
        if not path.is_file() or path.is_symlink() or path.stat().st_size != member["size_bytes"] or _sha256(path) != member["sha256"]:
            raise ValueError(f"VLC runtime member mismatch: {member['path']}")
    return {"status": "verified", "version": receipt["version"], "archive_sha256": receipt["archive_sha256"], "member_count": len(receipt["members"])}


def probe(root: Path, expected_version: str) -> dict:
    if os.name != "nt":
        raise ValueError("VLC runtime execution probe requires Windows")
    with os.add_dll_directory(str(root.resolve())):
        library = ctypes.CDLL(str(root.resolve() / "libvlc.dll"))
        library.libvlc_get_version.restype = ctypes.c_char_p
        version = library.libvlc_get_version().decode("utf-8")
    if version.split()[0] != expected_version:
        raise ValueError(f"VLC runtime version mismatch: {version}")
    with tempfile.TemporaryDirectory(prefix="goodq-vlc-probe-") as home:
        env = dict(os.environ, APPDATA=home, LOCALAPPDATA=home)
        result = subprocess.run(
            [str(root.resolve() / "vlc.exe"), "--intf=dummy", "--ignore-config", "--no-one-instance", "--no-media-library", "--no-plugins-cache", "--no-metadata-network-access", "--no-qt-privacy-ask", "--no-qt-updates-notif", "--no-stats", "--play-and-exit", "vlc://quit"],
            env=env, capture_output=True, timeout=20, check=False,
        )
    if result.returncode:
        raise ValueError(f"VLC dummy-interface execution failed: {result.returncode}")
    return {"version": version, "dummy_interface_exit_code": result.returncode}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["stage", "verify"])
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    try:
        if args.mode == "stage":
            if args.archive is None:
                raise ValueError("stage requires --archive")
            result = stage(args.archive, args.root, args.manifest, args.profile)
        else:
            result = verify(args.root, args.manifest, args.profile)
        if args.probe:
            result["execution"] = probe(args.root, result["version"])
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        parser.exit(1, f"VLC payload failed: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
