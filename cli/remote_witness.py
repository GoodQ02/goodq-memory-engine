"""Durable launcher and status reader for isolated witnesses over SSH.

The launcher is intended to run *on* an approved follower device.  Its receipt
lives beside (not inside) the fresh witness root, so operators retain a status
record even when preflight rejects the root or an SSH client disconnects.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli.golden_witness import prepare_witness_run, seal_prepared_receipt


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def receipt_path(artifact_root: Path) -> Path:
    root = artifact_root.resolve()
    return root.parent / f"{root.name}.remote-receipt.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _update(path: Path, payload: dict[str, Any], phase: str, **fields: Any) -> dict[str, Any]:
    payload = dict(payload)
    payload.update(fields)
    payload["phase"] = phase
    payload["updated_at"] = _now()
    _write_json(path, payload)
    return payload


def execute(artifact_root: Path, input_file: Path, scene_indices: str = "0") -> int:
    root = artifact_root.resolve()
    input_path = input_file.resolve(strict=True)
    receipt = receipt_path(root)
    state: dict[str, Any] = {
        "artifact_root": str(root),
        "input_file": str(input_path),
        "scene_indices": scene_indices,
        "started_at": _now(),
        "schema": "goodq.remote-witness.v1",
    }
    try:
        state = _update(receipt, state, "preflight_started")
        prepared = prepare_witness_run(root, input_path)
        sealed_path = seal_prepared_receipt(prepared)
        config_path = root / "config" / "witness-config.json"
        log_path = root / "scene-zero.log"
        root.mkdir(parents=True, exist_ok=True)
        state = _update(receipt, state, "preflight_sealed", sealed_receipt=str(sealed_path), log_path=str(log_path))
        command = [
            sys.executable, "-m", "cli.run_ingestion", "--input-file", str(input_path),
            "--config", str(config_path), "--output", str(root / "output"),
            "--workspace", str(root / "workspace"), "--scene-indices", scene_indices, "--verbose",
        ]
        with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
            process = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT, text=True)
            state = _update(receipt, state, "runner_started", runner_pid=process.pid, command=command)
            exit_code = process.wait()
        _update(receipt, state, "runner_finished", runner_exit_code=exit_code, finished_at=_now())
        return int(exit_code)
    except Exception as exc:
        _update(receipt, state, "failed", error=f"{type(exc).__name__}: {exc}", finished_at=_now())
        return 1


def _scheduled_task_name(root: Path) -> str:
    """Return a task name that is stable for one fresh witness root."""
    token = "".join(character if character.isalnum() else "-" for character in root.name)
    return f"GoodQ4All-RemoteWitness-{token}".rstrip("-")


def _launch_with_task_scheduler(command: list[str], root: Path) -> tuple[str, Path]:
    """Launch a Windows witness outside the OpenSSH session job.

    Windows OpenSSH can terminate ordinary detached children when the SSH client
    disconnects.  A scheduled task is owned by Task Scheduler instead, which
    gives the witness a durable execution boundary on approved follower hosts.
    """
    task_name = _scheduled_task_name(root)
    worker_path = root.parent / f"{root.name}.remote-runner.cmd"
    worker_path.parent.mkdir(parents=True, exist_ok=True)
    worker_path.write_text(
        "@echo off\r\n" + subprocess.list2cmdline(command) + "\r\nexit /b %ERRORLEVEL%\r\n",
        encoding="utf-8",
    )
    task_command = f'cmd.exe /d /c "{worker_path}"'
    subprocess.run(
        [
            "schtasks.exe", "/Create", "/TN", task_name, "/TR", task_command,
            "/SC", "ONCE", "/ST", "23:59", "/RL", "HIGHEST", "/F",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["schtasks.exe", "/Run", "/TN", task_name],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return task_name, worker_path


def launch(artifact_root: Path, input_file: Path, scene_indices: str = "0") -> Path:
    root = artifact_root.resolve()
    receipt = receipt_path(root)
    state = {
        "artifact_root": str(root), "input_file": str(input_file.resolve(strict=True)),
        "scene_indices": scene_indices, "schema": "goodq.remote-witness.v1", "started_at": _now(),
    }
    state = _update(receipt, state, "launch_requested")
    command = [sys.executable, "-m", "cli.remote_witness", "execute", "--artifact-root", str(root), "--input-file", str(input_file), "--scene-indices", scene_indices]
    try:
        if os.name == "nt":
            task_name, worker_path = _launch_with_task_scheduler(command, root)
            _update(
                receipt,
                state,
                "launcher_started",
                command=command,
                scheduler_task=task_name,
                scheduler_worker=str(worker_path),
            )
        else:
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            process = subprocess.Popen(command, creationflags=flags, close_fds=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _update(receipt, state, "launcher_started", launcher_pid=process.pid, command=command)
    except Exception as exc:
        _update(receipt, state, "failed", error=f"{type(exc).__name__}: {exc}", finished_at=_now())
        raise
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("execute", "launch"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--artifact-root", type=Path, required=True)
        sub.add_argument("--input-file", type=Path, required=True)
        sub.add_argument("--scene-indices", default="0")
    status = subparsers.add_parser("status")
    status.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "status":
        print(receipt_path(args.artifact_root).read_text(encoding="utf-8"), end="")
        return 0
    if args.command == "launch":
        print(launch(args.artifact_root, args.input_file, args.scene_indices))
        return 0
    return execute(args.artifact_root, args.input_file, args.scene_indices)


if __name__ == "__main__":
    raise SystemExit(main())
