#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = REPO_ROOT / "logs" / "bootstrap_smoke"
RUN_TS = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = LOG_ROOT / RUN_TS

PROFILES: List[Tuple[str, Optional[str]]] = [
    ("UNSET", None),
    ("BASELINE", "BASELINE"),
    ("GPU_ENHANCED", "GPU_ENHANCED"),
]

SMOKE_OVERRIDE_ROOT = "X:/BOOTSTRAP_SMOKE"


PROBE_CODE = r"""
import json
import os
import traceback

out = {
    "status": "ok",
    "errors": [],
}

try:
    from steps.common.profile_config import (
        get_host_profile,
        is_baseline,
        is_gpu_enhanced,
        require_gpu,
        require_wsl_audio,
        gpu_auto_config_enabled,
        wsl_audio_auto_enabled,
        resolve_wsl_gpu_config,
    )
    out["profile"] = get_host_profile() or "UNSET"
    out["is_baseline"] = is_baseline()
    out["is_gpu_enhanced"] = is_gpu_enhanced()
    out["require_gpu"] = require_gpu()
    out["require_wsl_audio"] = require_wsl_audio()
    out["gpu_auto_config_enabled"] = gpu_auto_config_enabled()
    out["wsl_audio_auto_enabled"] = wsl_audio_auto_enabled()
    out["wsl_gpu_cfg"] = resolve_wsl_gpu_config(
        {"device": "cuda", "compute_type": "float16", "mixed_precision": True}
    )
except Exception as e:
    out["status"] = "error"
    out["errors"].append({"stage": "profile_probe", "error": str(e), "trace": traceback.format_exc()})

try:
    from steps.common.config_loader import load_configs
    cfg = load_configs()
    paths = cfg.get("paths", {}) if isinstance(cfg, dict) else {}
    out["paths"] = {
        "data_root": paths.get("data_root"),
        "import_inbox": paths.get("import_inbox"),
        "db_path": paths.get("db_path"),
        "knowledge_graph_db": paths.get("knowledge_graph_db"),
    }
except Exception as e:
    out["status"] = "error"
    out["errors"].append({"stage": "config_loader", "error": str(e), "trace": traceback.format_exc()})

try:
    import steps.common.gpu_config as gc
    gpu_cfg = getattr(gc, "_gpu_config", {}) or {}
    out["gpu_module"] = {
        "available": gpu_cfg.get("available"),
        "device": gpu_cfg.get("device"),
        "reason": gpu_cfg.get("reason"),
    }
    out["env_after_gpu_import"] = {
        "GOODQ_NO_AUTO_GPU": os.getenv("GOODQ_NO_AUTO_GPU"),
    }
except Exception as e:
    out["status"] = "error"
    out["errors"].append({"stage": "gpu_import", "error": str(e), "trace": traceback.format_exc()})

print("SMOKE_JSON:" + json.dumps(out, sort_keys=True))
"""


STRICT_GPU_CODE = r"""
import json
import traceback

result = {"status": "ok", "error": None}
try:
    import steps.common.gpu_config  # noqa: F401
except Exception as e:
    result["status"] = "error"
    result["error"] = str(e)
    result["trace"] = traceback.format_exc()

print("SMOKE_JSON:" + json.dumps(result, sort_keys=True))
"""


STRICT_WSL_CODE = r"""
import json
import traceback
from pathlib import Path

result = {"status": "ok", "error": None}
try:
    from steps.audio_transcribe.step import audio_transcribe
    probe_file = str(Path("steps/audio_transcribe/step.py").resolve())
    audio_transcribe({"source_path": probe_file}, {})
except Exception as e:
    result["status"] = "error"
    result["error"] = str(e)
    result["trace"] = traceback.format_exc()

print("SMOKE_JSON:" + json.dumps(result, sort_keys=True))
"""


def _path_root_match(path_value: Any, root_value: str) -> bool:
    if not isinstance(path_value, str):
        return False
    path_norm = path_value.replace("\\", "/")
    root_norm = root_value.replace("\\", "/").rstrip("/")
    if path_norm.startswith(root_norm):
        return True
    if len(root_norm) >= 2 and root_norm[1] == ":":
        drive = root_norm[0].lower()
        rest = root_norm[2:].lstrip("/")
        wsl_norm = f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}"
        return path_norm.startswith(wsl_norm)
    return False


def _build_env(
    profile: Optional[str],
    *,
    data_root: Optional[str] = None,
    require_gpu: bool = False,
    require_wsl_audio: bool = False,
) -> Dict[str, str]:
    env = dict(os.environ)
    for key in (
        "GOODQ_HOST_PROFILE",
        "GOODQ_REQUIRE_GPU",
        "GOODQ_REQUIRE_WSL_AUDIO",
        "GOODQ_NO_AUTO_GPU",
        "GOODQ_DATA_ROOT",
        "GOODQ_WSL_AUDIO_DEVICE",
        "GOODQ_WSL_AUDIO_COMPUTE_TYPE",
        "GOODQ_WSL_AUDIO_MIXED_PRECISION",
    ):
        env.pop(key, None)

    if profile:
        env["GOODQ_HOST_PROFILE"] = profile
    if data_root:
        env["GOODQ_DATA_ROOT"] = data_root
    if require_gpu:
        env["GOODQ_REQUIRE_GPU"] = "1"
    if require_wsl_audio:
        env["GOODQ_REQUIRE_WSL_AUDIO"] = "1"

    env["PYTHONUTF8"] = "1"
    repo_py = str(REPO_ROOT)
    if env.get("PYTHONPATH"):
        env["PYTHONPATH"] = repo_py + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = repo_py
    return env


def _run_python_inline(code: str, env: Dict[str, str]) -> Dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    parsed: Dict[str, Any] = {}
    marker = "SMOKE_JSON:"
    for line in reversed((proc.stdout or "").splitlines()):
        if line.startswith(marker):
            try:
                parsed = json.loads(line[len(marker) :])
            except json.JSONDecodeError:
                parsed = {"status": "error", "error": "failed_to_parse_marker_json"}
            break
    if not parsed:
        parsed = {
            "status": "error",
            "error": "missing_smoke_json_marker",
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-2000:],
        }

    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "parsed": parsed,
    }


def _expect_profile_case(label: str, snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    parsed = snap.get("parsed", {})
    status_ok = snap.get("returncode") == 0 and parsed.get("status") == "ok"
    rows.append(
        {
            "test_case": "dry_boot_probe",
            "profile": label,
            "expected_result": "Probe process exits 0 and reports status=ok",
            "actual_result": f"rc={snap.get('returncode')} status={parsed.get('status')}",
            "pass": status_ok,
        }
    )

    expected_profile = label
    actual_profile = parsed.get("profile")
    rows.append(
        {
            "test_case": "profile_resolution",
            "profile": label,
            "expected_result": f"profile={expected_profile}",
            "actual_result": f"profile={actual_profile}",
            "pass": actual_profile == expected_profile,
        }
    )

    expected_baseline = label == "BASELINE"
    expected_gpu_enhanced = label == "GPU_ENHANCED"
    rows.append(
        {
            "test_case": "profile_flags",
            "profile": label,
            "expected_result": f"is_baseline={expected_baseline}, is_gpu_enhanced={expected_gpu_enhanced}",
            "actual_result": f"is_baseline={parsed.get('is_baseline')}, is_gpu_enhanced={parsed.get('is_gpu_enhanced')}",
            "pass": parsed.get("is_baseline") == expected_baseline
            and parsed.get("is_gpu_enhanced") == expected_gpu_enhanced,
        }
    )

    expected_gpu_auto = not expected_baseline
    rows.append(
        {
            "test_case": "gpu_auto_toggle",
            "profile": label,
            "expected_result": f"gpu_auto_config_enabled={expected_gpu_auto}",
            "actual_result": f"gpu_auto_config_enabled={parsed.get('gpu_auto_config_enabled')}",
            "pass": parsed.get("gpu_auto_config_enabled") == expected_gpu_auto,
        }
    )

    expected_wsl_auto = not expected_baseline
    rows.append(
        {
            "test_case": "wsl_auto_toggle",
            "profile": label,
            "expected_result": f"wsl_audio_auto_enabled={expected_wsl_auto}",
            "actual_result": f"wsl_audio_auto_enabled={parsed.get('wsl_audio_auto_enabled')}",
            "pass": parsed.get("wsl_audio_auto_enabled") == expected_wsl_auto,
        }
    )

    wsl_cfg = parsed.get("wsl_gpu_cfg") or {}
    if expected_baseline:
        wsl_ok = (
            str(wsl_cfg.get("device")).lower() == "cpu"
            and str(wsl_cfg.get("compute_type")).lower() == "int8"
            and wsl_cfg.get("mixed_precision") is False
        )
        expected_wsl_cfg = "device=cpu, compute_type=int8, mixed_precision=False"
    else:
        wsl_ok = (
            str(wsl_cfg.get("device")).lower() == "cuda"
            and str(wsl_cfg.get("compute_type")).lower() == "float16"
            and wsl_cfg.get("mixed_precision") is True
        )
        expected_wsl_cfg = "device=cuda, compute_type=float16, mixed_precision=True"
    rows.append(
        {
            "test_case": "wsl_gpu_profile_resolution",
            "profile": label,
            "expected_result": expected_wsl_cfg,
            "actual_result": (
                f"device={wsl_cfg.get('device')}, "
                f"compute_type={wsl_cfg.get('compute_type')}, "
                f"mixed_precision={wsl_cfg.get('mixed_precision')}"
            ),
            "pass": wsl_ok,
        }
    )

    env_after = parsed.get("env_after_gpu_import") or {}
    no_auto = env_after.get("GOODQ_NO_AUTO_GPU")
    if expected_baseline:
        no_auto_ok = no_auto == "1"
        expected_no_auto = "GOODQ_NO_AUTO_GPU=1"
    else:
        no_auto_ok = no_auto != "1"
        expected_no_auto = "GOODQ_NO_AUTO_GPU not forced to 1"
    rows.append(
        {
            "test_case": "goodq_no_auto_gpu_state",
            "profile": label,
            "expected_result": expected_no_auto,
            "actual_result": f"GOODQ_NO_AUTO_GPU={no_auto}",
            "pass": no_auto_ok,
        }
    )

    gpu_module = parsed.get("gpu_module") or {}
    if expected_baseline:
        fallback_ok = str(gpu_module.get("device")).lower() == "cpu"
        expected_fallback = "CPU fallback selected by profile defaults"
    else:
        fallback_ok = str(gpu_module.get("device")).lower() in {"cpu", "cuda:0", "cuda"}
        expected_fallback = "Device resolves without profile-forced CPU override"
    rows.append(
        {
            "test_case": "cpu_fallback_device_selection",
            "profile": label,
            "expected_result": expected_fallback,
            "actual_result": f"gpu_module.device={gpu_module.get('device')} reason={gpu_module.get('reason')}",
            "pass": fallback_ok,
        }
    )

    paths = parsed.get("paths") or {}
    data_root = paths.get("data_root")
    path_default_ok = _path_root_match(data_root, "L:/_DATA")
    rows.append(
        {
            "test_case": "path_resolution_default_root",
            "profile": label,
            "expected_result": "paths.data_root resolves from default L:/_DATA when GOODQ_DATA_ROOT unset",
            "actual_result": f"paths.data_root={data_root}",
            "pass": path_default_ok,
        }
    )
    return rows


def _expect_override_case(label: str, snap: Dict[str, Any]) -> Dict[str, Any]:
    parsed = snap.get("parsed", {})
    paths = parsed.get("paths") or {}
    data_root = paths.get("data_root")
    ok = _path_root_match(data_root, SMOKE_OVERRIDE_ROOT)
    return {
        "test_case": "path_resolution_env_override",
        "profile": label,
        "expected_result": f"paths.data_root starts with {SMOKE_OVERRIDE_ROOT}",
        "actual_result": f"paths.data_root={data_root}",
        "pass": ok,
    }


def _expect_strict_gpu_case(label: str, strict_gpu: Dict[str, Any], base_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    parsed = strict_gpu.get("parsed", {})
    status = parsed.get("status")
    err = str(parsed.get("error") or "")
    gpu_available = bool(((base_snapshot.get("parsed") or {}).get("gpu_module") or {}).get("available"))

    if label == "BASELINE":
        ok = status == "error" and "GOODQ_REQUIRE_GPU=1 but GPU auto-config is disabled" in err
        expected = "Fail-fast with explicit baseline/GOODQ_NO_AUTO_GPU conflict"
    else:
        if gpu_available:
            ok = status == "ok"
            expected = "Pass when GPU requirement can be satisfied"
        else:
            ok = status == "error" and (
                "CUDA required but unavailable" in err
                or "PyTorch required for GPU step" in err
                or "GOODQ_REQUIRE_GPU=1" in err
            )
            expected = "Fail-fast when GPU requirement cannot be satisfied"

    return {
        "test_case": "strict_flag_goodq_require_gpu",
        "profile": label,
        "expected_result": expected,
        "actual_result": f"status={status}; error={err or 'None'}",
        "pass": ok,
    }


def _expect_strict_wsl_case(label: str, strict_wsl: Dict[str, Any]) -> Dict[str, Any]:
    parsed = strict_wsl.get("parsed", {})
    status = parsed.get("status")
    err = str(parsed.get("error") or "")
    if label == "BASELINE":
        ok = status == "error" and "GOODQ_REQUIRE_WSL_AUDIO=1 but WSL audio is disabled by profile/config" in err
        expected = "Fail-fast immediately because BASELINE disables WSL auto path"
    else:
        ok = (status == "ok") or (status == "error" and "GOODQ_REQUIRE_WSL_AUDIO=1" in err)
        expected = "Either succeeds with WSL path or fails-fast with explicit GOODQ_REQUIRE_WSL_AUDIO=1 error"

    return {
        "test_case": "strict_flag_goodq_require_wsl_audio",
        "profile": label,
        "expected_result": expected,
        "actual_result": f"status={status}; error={err or 'None'}",
        "pass": ok,
    }


def _table_markdown(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "| Test Case | Profile | Expected Result | Actual Result | Pass/Fail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        verdict = "PASS" if row.get("pass") else "FAIL"
        lines.append(
            "| {test_case} | {profile} | {expected} | {actual} | {verdict} |".format(
                test_case=str(row.get("test_case", "")).replace("|", "/"),
                profile=str(row.get("profile", "")).replace("|", "/"),
                expected=str(row.get("expected_result", "")).replace("|", "/"),
                actual=str(row.get("actual_result", "")).replace("|", "/"),
                verdict=verdict,
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    snapshots: Dict[str, Dict[str, Any]] = {}
    override_snapshots: Dict[str, Dict[str, Any]] = {}
    strict_gpu_results: Dict[str, Dict[str, Any]] = {}
    strict_wsl_results: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []

    for label, profile in PROFILES:
        probe_env = _build_env(profile)
        snapshots[label] = _run_python_inline(PROBE_CODE, probe_env)
        rows.extend(_expect_profile_case(label, snapshots[label]))

        override_env = _build_env(profile, data_root=SMOKE_OVERRIDE_ROOT)
        override_snapshots[label] = _run_python_inline(PROBE_CODE, override_env)
        rows.append(_expect_override_case(label, override_snapshots[label]))

        strict_gpu_env = _build_env(profile, require_gpu=True)
        strict_gpu_results[label] = _run_python_inline(STRICT_GPU_CODE, strict_gpu_env)
        rows.append(_expect_strict_gpu_case(label, strict_gpu_results[label], snapshots[label]))

        strict_wsl_env = _build_env(profile, require_wsl_audio=True)
        strict_wsl_results[label] = _run_python_inline(STRICT_WSL_CODE, strict_wsl_env)
        rows.append(_expect_strict_wsl_case(label, strict_wsl_results[label]))

    passed = sum(1 for r in rows if r.get("pass"))
    failed = len(rows) - passed

    summary = {
        "run_timestamp": RUN_TS,
        "repo_root": str(REPO_ROOT),
        "logs_dir": str(RUN_DIR),
        "totals": {
            "test_count": len(rows),
            "passed": passed,
            "failed": failed,
        },
        "rows": rows,
        "snapshots": snapshots,
        "override_snapshots": override_snapshots,
        "strict_gpu_results": strict_gpu_results,
        "strict_wsl_results": strict_wsl_results,
    }

    json_path = RUN_DIR / "smoke_matrix_results.json"
    table_path = RUN_DIR / "smoke_matrix_results.md"
    stdout_path = RUN_DIR / "smoke_matrix_console.txt"

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    table_path.write_text(_table_markdown(rows), encoding="utf-8")

    console_lines = [
        f"Bootstrap Phase A Smoke Matrix run: {RUN_TS}",
        f"Repository: {REPO_ROOT}",
        f"Logs: {RUN_DIR}",
        f"Results: {passed}/{len(rows)} passed; {failed} failed",
        "",
        _table_markdown(rows),
    ]
    console_text = "\n".join(console_lines)
    stdout_path.write_text(console_text, encoding="utf-8")
    print(console_text)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

