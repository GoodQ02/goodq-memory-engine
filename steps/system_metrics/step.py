from __future__ import annotations
import os
import json
import subprocess
from typing import Any, Dict, Optional


def _read_csv_latest(path: str) -> Optional[Dict[str, Any]]:
    try:
        import chardet  # type: ignore
        import pandas as pd  # type: ignore
    except Exception:
        return None
    try:
        with open(path, "rb") as f:
            encoding = chardet.detect(f.read()).get("encoding", "utf-8")
        df = pd.read_csv(path, encoding=encoding)
        if df is None or df.empty:
            return None
        return df.iloc[-1].to_dict()
    except Exception:
        return None


def _collect_psutil() -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    try:
        import psutil  # type: ignore
        data["cpu_load_pct"] = psutil.cpu_percent(interval=0.2)
        vm = psutil.virtual_memory()
        data["ram_used_gb"] = vm.used / (1024 ** 3)
        data["ram_load_pct"] = vm.percent
        # primary drives (C and L if present)
        for drive in ("C:", "L:"):
            try:
                du = psutil.disk_usage(drive)
                data[f"disk_{drive[0]}_used_gb"] = du.used / (1024 ** 3)
                data[f"disk_{drive[0]}_total_gb"] = du.total / (1024 ** 3)
            except Exception:
                continue
    except Exception:
        pass
    return data


def _collect_nvidia() -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0 and r.stdout.strip():
            fields = [x.strip() for x in r.stdout.strip().split(",")]
            if len(fields) >= 4:
                data["gpu_temp_c"] = float(fields[0])
                data["gpu_load_pct"] = float(fields[1])
                data["gpu_vram_used_mb"] = float(fields[2])
                data["gpu_vram_total_mb"] = float(fields[3])
    except Exception:
        pass
    return data


def _summarize_row(row: Dict[str, Any]) -> str:
    parts = []
    if "Core Temperatures (avg) [°F]" in row and "Total CPU Usage [%]" in row:
        try:
            f = float(row["Core Temperatures (avg) [°F]"])
            c = (f - 32.0) * 5.0 / 9.0
            parts.append(f"CPU {f:.1f}°F/{c:.1f}°C @ {float(row['Total CPU Usage [%]']):.0f}%")
        except Exception:
            pass
    if "GPU Temperature [°F]" in row and "GPU Core Load [%]" in row:
        try:
            f = float(row["GPU Temperature [°F]"])
            c = (f - 32.0) * 5.0 / 9.0
            parts.append(f"GPU {c:.1f}°C @ {float(row['GPU Core Load [%]']):.0f}%")
        except Exception:
            pass
    if "Physical Memory Used [MB]" in row and "Physical Memory Load [%]" in row:
        try:
            parts.append(f"RAM {float(row['Physical Memory Used [MB]'])/1024:.1f}GB ({float(row['Physical Memory Load [%]']):.0f}%)")
        except Exception:
            pass
    return "; ".join(parts)


def _summarize_live(row: Dict[str, Any]) -> str:
    parts = []
    if "cpu_load_pct" in row:
        parts.append(f"CPU {row['cpu_load_pct']:.0f}%")
    if "ram_used_gb" in row and "ram_load_pct" in row:
        parts.append(f"RAM {row['ram_used_gb']:.1f}GB ({row['ram_load_pct']:.0f}%)")
    if "gpu_temp_c" in row and "gpu_load_pct" in row:
        parts.append(f"GPU {row['gpu_temp_c']:.0f}°C @ {row['gpu_load_pct']:.0f}%")
    return "; ".join(parts)


def system_metrics(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Prefer live, low-overhead metrics; fall back to CSV if present and desired
    csv_path = cfg.get("paths", {}).get("system_csv", "")
    use_csv_first = False  # set True to prefer historical CSV

    latest_csv = _read_csv_latest(csv_path) if (csv_path and os.path.isfile(csv_path) and use_csv_first) else None
    if latest_csv:
        return {"status": "ok", "latest": latest_csv, "summary": _summarize_row(latest_csv)}

    live: Dict[str, Any] = {}
    live.update(_collect_psutil())
    live.update(_collect_nvidia())
    return {"status": "ok", "latest": live, "summary": _summarize_live(live)}
