from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple


PROBE_CODE = (
    "import importlib.util as u, json\n"
    "probe = {\n"
    "  'torch_import': u.find_spec('torch') is not None,\n"
    "  'torchaudio_import': u.find_spec('torchaudio') is not None,\n"
    "  'faster_whisper_import': u.find_spec('faster_whisper') is not None,\n"
    "}\n"
    "if probe['torch_import']:\n"
    "  import torch\n"
    "  probe['torch_version'] = torch.__version__\n"
    "  probe['torch_cuda'] = torch.version.cuda\n"
    "  probe['cuda_available'] = bool(getattr(torch, 'cuda', None) and torch.cuda.is_available())\n"
    "else:\n"
    "  probe['torch_version'] = None\n"
    "  probe['torch_cuda'] = None\n"
    "  probe['cuda_available'] = False\n"
    "print(json.dumps(probe))\n"
)


def _resolve_conda_exe() -> str:
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe and Path(conda_exe).exists():
        return conda_exe
    found = shutil.which("conda")
    if found:
        return found
    fallback = Path.home() / "miniconda3" / "Scripts" / "conda.exe"
    if fallback.exists():
        return str(fallback)
    raise RuntimeError("Unable to locate conda executable. Set CONDA_EXE or add conda to PATH.")


def _extract_json_line(stdout: str) -> Dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            return json.loads(line)
    raise ValueError("No JSON probe payload found in subprocess stdout")


def _probe_env(conda_exe: str, env_name: str) -> Tuple[Dict[str, Any], str]:
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix="_goodq_probe.py",
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(PROBE_CODE)
            script_path = handle.name
        cmd = [
            conda_exe,
            "run",
            "--no-capture-output",
            "-n",
            env_name,
            "python",
            script_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    finally:
        if script_path:
            try:
                Path(script_path).unlink(missing_ok=True)
            except Exception:
                pass
    if result.returncode != 0:
        return {"error": f"probe_failed_returncode_{result.returncode}"}, result.stderr.strip()
    try:
        payload = _extract_json_line(result.stdout)
        return payload, ""
    except Exception as exc:  # noqa: BLE001
        return {"error": f"probe_parse_error:{type(exc).__name__}"}, result.stdout.strip()


def _normalize_profile(raw: str) -> str:
    value = (raw or "").strip().upper()
    return value if value in {"BASELINE", "GPU_ENHANCED"} else "UNSET"


def _format_cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    return text if len(text) <= 26 else text[:23] + "..."


def _print_table(rows: List[Dict[str, Any]]) -> None:
    headers = ["env", "torch_version", "cuda_available", "torchaudio", "faster_whisper", "status"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(_format_cell(row.get(h))))
    line = " | ".join(h.ljust(widths[h]) for h in headers)
    sep = "-+-".join("-" * widths[h] for h in headers)
    print(line)
    print(sep)
    for row in rows:
        print(" | ".join(_format_cell(row.get(h)).ljust(widths[h]) for h in headers))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify audio provisioning seams across canonical conda envs.")
    parser.add_argument(
        "--profile",
        default=os.environ.get("GOODQ_HOST_PROFILE", "UNSET"),
        help="Profile contract for pass/fail rules (BASELINE|GPU_ENHANCED|UNSET).",
    )
    args = parser.parse_args()
    profile = _normalize_profile(args.profile)

    conda_exe = _resolve_conda_exe()
    targets = ["goodq_core", "goodq_audio_transcribe", "goodq_audio_embed"]

    rows: List[Dict[str, Any]] = []
    probes: Dict[str, Dict[str, Any]] = {}
    failures: List[str] = []
    for env_name in targets:
        payload, detail = _probe_env(conda_exe, env_name)
        probes[env_name] = payload
        status = payload.get("error", "ok")
        rows.append(
            {
                "env": env_name,
                "torch_version": payload.get("torch_version"),
                "cuda_available": payload.get("cuda_available"),
                "torchaudio": payload.get("torchaudio_import"),
                "faster_whisper": payload.get("faster_whisper_import"),
                "status": status,
            }
        )
        if payload.get("error"):
            suffix = f" detail={detail}" if detail else ""
            failures.append(f"{env_name}: {payload['error']}{suffix}")

    _print_table(rows)

    if profile in {"GPU_ENHANCED", "UNSET"}:
        embed = probes.get("goodq_audio_embed", {})
        if not bool(embed.get("torchaudio_import")):
            failures.append(
                "GPU_ENHANCED contract check failed: goodq_audio_embed missing torchaudio import"
            )

    if profile in {"BASELINE", "UNSET"}:
        core = probes.get("goodq_core", {})
        if not bool(core.get("faster_whisper_import")):
            failures.append(
                "BASELINE contract check failed: goodq_core missing faster_whisper import"
            )

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"\nProvisioning verification passed for profile={profile}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
