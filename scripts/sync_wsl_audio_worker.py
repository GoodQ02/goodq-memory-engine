"""Synchronize the versioned WSL audio worker before a strict audio run.

This tool owns only the three source-controlled worker files.  It writes a
missing or stale file atomically inside the configured WSL workspace, then
requires the deployed hashes to match the repository before returning success.
"""

from __future__ import annotations

import argparse
import hashlib
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wsl_audio_preflight import _default_wsl_distro, _default_wsl_workspace


WORKER_FILES = ("setup_cuda_env.sh", "process_audio.py", "model_cache.py")
SOURCE_ROOT = REPO_ROOT / "wsl2_audio"


def expected_worker_hashes(source_root: Path = SOURCE_ROOT) -> dict[str, str]:
    return {
        name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
        for name in WORKER_FILES
    }


def _wsl(distro: str, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["wsl", "-d", distro, "--", "bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )


def deployed_worker_hashes(distro: str, workspace: str) -> dict[str, str]:
    paths = " ".join(shlex.quote(f"{workspace}/{name}") for name in WORKER_FILES)
    result = _wsl(distro, f"sha256sum {paths} 2>/dev/null || true")
    hashes: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        hashes[Path(parts[1].strip().lstrip("*")).name] = parts[0].lower()
    return hashes


def _as_wsl_path(path: Path) -> str:
    if not path.drive:
        raise ValueError(f"worker source must be on a mounted Windows drive: {path}")
    return f"/mnt/{path.drive.rstrip(':').lower()}{path.as_posix()[2:]}"


def _write_worker_file(distro: str, workspace: str, name: str, source: Path) -> None:
    destination = f"{workspace}/{name}"
    temporary = f"{destination}.goodq-new"
    command = (
        f"mkdir -p {shlex.quote(workspace)} && "
        f"install -m 700 {shlex.quote(_as_wsl_path(source))} {shlex.quote(temporary)} && "
        f"mv -f {shlex.quote(temporary)} {shlex.quote(destination)}"
    )
    result = _wsl(distro, command)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or f"WSL write failed for {name}").strip())


def synchronize_worker(
    distro: str,
    workspace: str,
    *,
    source_root: Path = SOURCE_ROOT,
) -> tuple[str, ...]:
    expected = expected_worker_hashes(source_root)
    deployed = deployed_worker_hashes(distro, workspace)
    stale = tuple(name for name in WORKER_FILES if deployed.get(name) != expected[name])
    for name in stale:
        _write_worker_file(distro, workspace, name, source_root / name)

    verified = deployed_worker_hashes(distro, workspace)
    remaining = [name for name in WORKER_FILES if verified.get(name) != expected[name]]
    if remaining:
        raise RuntimeError("WSL worker hash verification failed: " + ", ".join(remaining))
    return stale


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synchronize only versioned GoodQ WSL audio worker files.")
    parser.add_argument("--distro", default=_default_wsl_distro())
    parser.add_argument("--workspace", default=_default_wsl_workspace())
    args = parser.parse_args(argv)
    changed = synchronize_worker(args.distro, args.workspace)
    detail = ", ".join(changed) if changed else "already current"
    print(f"[WSL AUDIO] Worker hashes verified ({detail}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
