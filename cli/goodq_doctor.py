"""
GoodQ Doctor - Read-only ingestion preflight validator.

Invoke:
  python -m cli.goodq_doctor

Exit codes:
  0 = PASS
  1 = WARN
  2 = FAIL
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.wsl_audio_preflight import probe_wsl_audio_runtime


# Best-effort to keep this tool read-only (avoid writing __pycache__ for subsequent imports).
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True


PASS = 0
WARN = 1
FAIL = 2


@dataclass(frozen=True)
class Item:
    severity: int
    message: str


def _label(severity: int) -> str:
    return {PASS: "PASS", WARN: "WARN", FAIL: "FAIL"}.get(severity, "FAIL")


def _max_severity(items: Iterable[Item]) -> int:
    max_seen = PASS
    for it in items:
        if it.severity > max_seen:
            max_seen = it.severity
    return max_seen


def _print_section(title: str, items: List[Item]) -> int:
    section_status = _max_severity(items)
    print(f"\n== {title} [{_label(section_status)}] ==")
    if not items:
        print("PASS: No checks executed.")
        return PASS
    for it in items:
        msg = it.message
        try:
            enc = getattr(sys.stdout, "encoding", None) or "utf-8"
            msg = msg.encode(enc, errors="replace").decode(enc, errors="replace")
        except Exception:
            msg = str(msg)
        print(f"{_label(it.severity)}: {msg}")
    return section_status


def _summarize_paths(paths: List[Path], limit: int = 5) -> str:
    if not paths:
        return ""
    shown = [str(p) for p in paths[:limit]]
    remainder = len(paths) - len(shown)
    if remainder > 0:
        shown.append(f"... (+{remainder} more)")
    return "; ".join(shown)


def _read_text(path: Path) -> Tuple[Optional[str], Optional[str]]:
    try:
        return path.read_text(encoding="utf-8", errors="replace"), None
    except Exception as exc:
        return None, str(exc)


def _bootstrap_repo_imports(repo_root: Path) -> None:
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


def _parse_mode(agent_status_text: str) -> Optional[str]:
    # Supports either "- MODE: ..." or "MODE: ..." formats.
    m = re.search(r"^\s*-\s*MODE:\s*(.+?)\s*$", agent_status_text, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r"^\s*MODE:\s*(.+?)\s*$", agent_status_text, flags=re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def _parse_phase6b_status(agent_status_text: str) -> Optional[str]:
    for line in agent_status_text.splitlines():
        if "Phase 6b Harmonization" not in line:
            continue
        # Expected markdown table row: | Phase 6b Harmonization | <status> | <notes> |
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            return parts[1]
    return None


def _is_audio_enabled(cfg: Dict[str, Any]) -> bool:
    seg = cfg.get("segmentation") if isinstance(cfg, dict) else None
    if not isinstance(seg, dict):
        return False
    phase4 = seg.get("phase4")
    if not isinstance(phase4, dict):
        return False
    flags = [
        "enable_transcription",
        "enable_diarization",
        "enable_embeddings",
        "enable_emotion",
        "enable_music_detection",
    ]
    return any(bool(phase4.get(k)) for k in flags)


def _check_tcp(host: str, port: int, timeout_s: float = 1.5) -> Optional[str]:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return None
    except Exception as exc:
        return str(exc)


def _check_cmd(cmd: List[str], timeout_s: float = 10.0) -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if proc.returncode == 0:
            return True, proc.stdout.strip() or proc.stderr.strip()
        msg = (proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}").strip()
        return False, msg
    except FileNotFoundError:
        return False, "not found on PATH"
    except Exception as exc:
        return False, str(exc)


def _governance_checks(repo_root: Path) -> Tuple[List[Item], Dict[str, Any]]:
    items: List[Item] = []
    info: Dict[str, Any] = {}

    system_snapshot = repo_root / "docs" / "SYSTEM_SNAPSHOT.md"
    agent_caps = repo_root / "docs" / "AGENT_CAPABILITIES.md"
    agent_status = repo_root / "docs" / "goodq4all_agent_status.md"

    for label, path in [
        ("SYSTEM_SNAPSHOT.md", system_snapshot),
        ("AGENT_CAPABILITIES.md", agent_caps),
        ("goodq4all_agent_status.md", agent_status),
    ]:
        if path.is_file():
            text, err = _read_text(path)
            if text is None:
                items.append(Item(FAIL, f"Could not read {label}: {path} ({err})"))
            else:
                items.append(Item(PASS, f"Read {label}: {path}"))
        else:
            items.append(Item(FAIL, f"Missing required governance doc: {path}"))

    status_text, err = _read_text(agent_status)
    if status_text is None:
        items.append(Item(FAIL, f"Could not read {agent_status}: {err}"))
        return items, info

    info["agent_status_text"] = status_text

    mode = _parse_mode(status_text)
    if mode:
        items.append(Item(PASS, f"Declared MODE: {mode}"))
        if re.search(r"\baudit\b|\bstabil", mode, flags=re.IGNORECASE):
            items.append(Item(WARN, "MODE indicates audit/stabilization; run ingestion intentionally and scope it."))
    else:
        items.append(Item(WARN, "Could not parse MODE from docs/goodq4all_agent_status.md"))

    phase6b_status = _parse_phase6b_status(status_text)
    if phase6b_status:
        items.append(Item(PASS, f"Declared Phase 6b status: {phase6b_status}"))
    else:
        items.append(Item(WARN, "Could not parse Phase 6b Harmonization status from docs/goodq4all_agent_status.md"))

    info["mode"] = mode
    info["phase6b_status"] = phase6b_status
    return items, info


def _config_checks(repo_root: Path) -> Tuple[List[Item], Optional[Dict[str, Any]]]:
    items: List[Item] = []
    cfg: Optional[Dict[str, Any]] = None

    canonical_cfg_path = repo_root / "configs" / "config.yaml"
    if canonical_cfg_path.is_file():
        items.append(Item(PASS, f"Found canonical config: {canonical_cfg_path}"))
    else:
        items.append(Item(FAIL, f"Missing canonical config: {canonical_cfg_path}"))

    try:
        _bootstrap_repo_imports(repo_root)
        from steps.common.config_loader import load_configs

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            loaded = load_configs({})
        noise = buf.getvalue().strip()
        if noise:
            items.append(Item(WARN, f"load_configs() emitted output: {noise.splitlines()[0]}"))
        if not isinstance(loaded, dict):
            items.append(Item(FAIL, f"load_configs() returned non-dict: {type(loaded)}"))
        else:
            cfg = loaded
            items.append(Item(PASS, "load_configs() succeeded"))
    except Exception as exc:
        if isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", None) == "yaml":
            items.append(
                Item(
                    FAIL,
                    (
                        "load_configs() failed: No module named 'yaml'. "
                        "Run doctor from the bound GoodQ environment, for example: "
                        "conda run -n goodq_core python -m cli.goodq_doctor"
                    ),
                )
            )
        else:
            items.append(Item(FAIL, f"load_configs() failed: {exc}"))
        return items, None

    paths_cfg = cfg.get("paths") if isinstance(cfg, dict) else None
    processing_root = None
    if isinstance(paths_cfg, dict):
        processing_root = paths_cfg.get("processing")
    if not processing_root:
        items.append(Item(FAIL, "cfg['paths']['processing'] is missing"))
        return items, cfg

    processing_path = Path(str(processing_root))
    if not processing_path.is_absolute():
        items.append(Item(WARN, f"cfg['paths']['processing'] is not absolute: {processing_path}"))
    if not processing_path.exists():
        items.append(Item(FAIL, f"Processing root does not exist: {processing_path}"))
    elif not processing_path.is_dir():
        items.append(Item(FAIL, f"Processing root is not a directory: {processing_path}"))
    else:
        items.append(Item(PASS, f"Processing root exists: {processing_path}"))

        if os.access(str(processing_path), os.W_OK):
            items.append(Item(PASS, f"Processing root appears writable: {processing_path}"))
        else:
            items.append(Item(FAIL, f"Processing root is not writable: {processing_path}"))

    return items, cfg


def _manifest_checks(repo_root: Path, cfg: Optional[Dict[str, Any]]) -> List[Item]:
    items: List[Item] = []
    if not isinstance(cfg, dict):
        items.append(Item(FAIL, "Config unavailable; cannot validate manifest locations"))
        return items

    processing_root = (cfg.get("paths") or {}).get("processing")
    processing_path = Path(str(processing_root)) if processing_root else None
    if not processing_path or not processing_path.exists():
        items.append(Item(FAIL, "Processing root unavailable; cannot validate canonical manifest pattern"))
        return items

    items.append(Item(PASS, f"Canonical manifest pattern: {processing_path}\\<video_id>\\video\\scene_manifest.json"))

    canonical = sorted(processing_path.glob("*/video/scene_manifest.json"))
    if canonical:
        items.append(Item(PASS, f"Found {len(canonical)} canonical scene manifests"))
    else:
        items.append(Item(PASS, "No canonical scene manifests found (ok for fresh installs)"))

    legacy = sorted(processing_path.glob("*/scene_manifest.json"))
    if legacy:
        items.append(Item(WARN, f"Found {len(legacy)} legacy manifests at <video_id>/scene_manifest.json: {_summarize_paths(legacy)}"))
    else:
        items.append(Item(PASS, "No legacy manifests found at <video_id>/scene_manifest.json"))

    unknown_dir = processing_path / "unknown"
    if unknown_dir.exists():
        unknown = sorted(unknown_dir.rglob("scene_manifest.json"))
        if unknown:
            items.append(Item(WARN, f"Found {len(unknown)} manifests under <processing_root>/unknown/: {_summarize_paths(unknown)}"))
        else:
            items.append(Item(PASS, "No manifests found under <processing_root>/unknown/"))
    else:
        items.append(Item(PASS, "No <processing_root>/unknown/ directory present"))

    logs_scene_ingest = repo_root / "logs" / "scene_ingest"
    if logs_scene_ingest.exists():
        stray_logs = sorted(logs_scene_ingest.rglob("scene_manifest.json"))
        if stray_logs:
            items.append(Item(WARN, f"Found {len(stray_logs)} stray manifests under logs/scene_ingest/: {_summarize_paths(stray_logs)}"))
        else:
            items.append(Item(PASS, "No stray manifests found under logs/scene_ingest/"))
    else:
        items.append(Item(PASS, "No logs/scene_ingest directory present"))

    return items


def _phase6_checks(repo_root: Path, cfg: Optional[Dict[str, Any]], gov: Dict[str, Any]) -> List[Item]:
    items: List[Item] = []

    # Source-level availability checks avoid false negatives from optional env/import drift.
    sfe_path = repo_root / "steps" / "video" / "scene_frame_extractor.py"
    sfe_text = None
    if sfe_path.is_file():
        sfe_text, err = _read_text(sfe_path)
        if sfe_text is None:
            items.append(Item(FAIL, f"Could not read scene_frame_extractor source: {sfe_path} ({err})"))
        else:
            items.append(Item(PASS, f"Found scene_frame_extractor source: {sfe_path}"))
    else:
        items.append(Item(FAIL, f"Missing phase6 source file: {sfe_path}"))

    harmonizer_path = repo_root / "steps" / "video" / "cross_modal_harmonizer.py"
    if harmonizer_path.is_file():
        harmonizer_text, err = _read_text(harmonizer_path)
        if harmonizer_text is None:
            items.append(Item(FAIL, f"Could not read cross_modal_harmonizer source: {harmonizer_path} ({err})"))
        else:
            items.append(Item(PASS, f"Found cross_modal_harmonizer source: {harmonizer_path}"))
    else:
        items.append(Item(FAIL, f"Missing phase6 source file: {harmonizer_path}"))

    # Validate non-numeric scene_id safety (static source check; avoids IO/writes).
    if sfe_text is not None:
        try:
            ok = (
                "scene_id_for_filename" in sfe_text
                and "int(scene_id_for_filename)" in sfe_text
                and "except (TypeError, ValueError)" in sfe_text
            )
            if ok:
                items.append(Item(PASS, "scene_frame_extractor normalizes non-numeric scene_id for filenames"))
            else:
                items.append(Item(FAIL, "scene_frame_extractor does not appear to normalize non-numeric scene_id (risk: :04d crash)"))
        except Exception as exc:
            items.append(Item(FAIL, f"Could not validate scene_id normalization: {exc}"))

    phase6_enabled = True
    if isinstance(cfg, dict):
        phase6_cfg = cfg.get("phase6")
        if isinstance(phase6_cfg, dict):
            phase6_enabled = bool(phase6_cfg.get("enabled", True))

    declared_phase6b = gov.get("phase6b_status")
    if phase6_enabled:
        if isinstance(declared_phase6b, str) and declared_phase6b.strip():
            if "✅" in declared_phase6b:
                items.append(Item(PASS, "No known Phase 6 blockers indicated by governance status"))
            else:
                items.append(Item(FAIL, f"Phase 6 is enabled but governance declares Phase 6b is not operational: {declared_phase6b}"))
        else:
            items.append(Item(WARN, "Phase 6 is enabled but Phase 6b status could not be confirmed from governance docs"))
    else:
        items.append(Item(PASS, "Phase 6 disabled in config; skipping Phase 6b governance gating"))

    return items


def _service_checks(cfg: Optional[Dict[str, Any]]) -> List[Item]:
    items: List[Item] = []

    # Qdrant reachability
    qdrant_enabled = True
    qdrant_host = "http://127.0.0.1:6333"
    if isinstance(cfg, dict):
        qdrant_cfg = cfg.get("qdrant")
        if isinstance(qdrant_cfg, dict):
            qdrant_enabled = bool(qdrant_cfg.get("enabled", True))
            qdrant_host = str(qdrant_cfg.get("host") or qdrant_host)

    if qdrant_enabled:
        u = urlparse(qdrant_host)
        host = u.hostname or "127.0.0.1"
        port = u.port or 6333
        err = _check_tcp(host, port)
        if err is None:
            items.append(Item(PASS, f"Qdrant reachable at {host}:{port}"))
        else:
            items.append(Item(FAIL, f"Qdrant NOT reachable at {host}:{port} ({err})"))
    else:
        items.append(Item(WARN, "Qdrant disabled in config; skipping reachability check"))

    # ffmpeg (canonical config first, PATH second)
    ffmpeg = None
    tools_cfg = None
    if isinstance(cfg, dict):
        config_cfg = cfg.get("config")
        if isinstance(config_cfg, dict):
            tools_cfg = config_cfg.get("tools")
    if isinstance(tools_cfg, dict):
        configured_ffmpeg = tools_cfg.get("ffmpeg_exe")
        if isinstance(configured_ffmpeg, str) and configured_ffmpeg.strip():
            if configured_ffmpeg.strip().lower() == "ffmpeg":
                ffmpeg = shutil.which("ffmpeg")
            else:
                ffmpeg = configured_ffmpeg.strip()
    if not ffmpeg:
        ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        ok, msg = _check_cmd([ffmpeg, "-version"], timeout_s=10.0)
        if ok:
            items.append(Item(PASS, f"ffmpeg OK: {ffmpeg}"))
        else:
            items.append(Item(FAIL, f"ffmpeg found but not usable: {ffmpeg} ({msg})"))
    else:
        items.append(Item(FAIL, "ffmpeg not resolved from canonical config or PATH"))

    # GPU (nvidia-smi) if enabled
    gpu_enabled = False
    if isinstance(cfg, dict):
        gpu_cfg = cfg.get("gpu")
        if isinstance(gpu_cfg, dict):
            gpu_enabled = bool(gpu_cfg.get("enabled", False))
    if gpu_enabled:
        nvsmi = shutil.which("nvidia-smi")
        if not nvsmi:
            items.append(Item(WARN, "GPU enabled in config but nvidia-smi not found on PATH"))
        else:
            ok, msg = _check_cmd([nvsmi, "-L"], timeout_s=10.0)
            if ok:
                items.append(Item(PASS, "nvidia-smi OK"))
            else:
                items.append(Item(WARN, f"nvidia-smi present but failed: {msg}"))
    else:
        items.append(Item(PASS, "GPU disabled in config; skipping nvidia-smi check"))

    # WSL reachability if audio enabled
    audio_enabled = bool(cfg) and _is_audio_enabled(cfg)  # type: ignore[arg-type]
    if audio_enabled:
        wsl = shutil.which("wsl") or shutil.which("wsl.exe")
        if not wsl:
            items.append(Item(FAIL, "Audio enabled but wsl.exe not found on PATH"))
        else:
            host_cfg = cfg.get("host") if isinstance(cfg, dict) else None
            wsl_distro = None
            wsl_workspace = None
            if isinstance(host_cfg, dict):
                distro_value = host_cfg.get("wsl_distro")
                workspace_value = host_cfg.get("wsl_workspace")
                if isinstance(distro_value, str) and distro_value.strip():
                    wsl_distro = distro_value.strip()
                if isinstance(workspace_value, str) and workspace_value.strip():
                    wsl_workspace = workspace_value.strip()

            distro_cmd = [wsl, "-l", "-q"]
            ok, msg = _check_cmd(distro_cmd, timeout_s=15.0)
            if ok:
                items.append(Item(PASS, "WSL reachable (wsl -l -q succeeded)"))
            else:
                items.append(Item(FAIL, f"WSL not reachable: {msg}"))

            if ok and wsl_distro and wsl_workspace:
                probe = probe_wsl_audio_runtime(wsl_distro, wsl_workspace)
                detail = str(probe.get("detail") or "workspace probe failed")
                if bool(probe.get("runtime_ready")):
                    diarization_known = "diarization_ready" in probe
                    diarization_ready = bool(probe.get("diarization_ready")) if diarization_known else True
                    diarization_detail = str(probe.get("diarization_detail") or detail)
                    if bool(probe.get("abi_ready")) and diarization_ready:
                        items.append(Item(PASS, f"Configured WSL audio runtime ready: {wsl_distro}:{wsl_workspace}"))
                    elif bool(probe.get("abi_ready")) and not diarization_ready:
                        items.append(
                            Item(
                                WARN,
                                (
                                    f"Configured WSL audio runtime is transcription-ready but diarization-degraded: "
                                    f"{wsl_distro}:{wsl_workspace} ({diarization_detail})"
                                ),
                            )
                        )
                    else:
                        items.append(
                            Item(
                                WARN,
                                (
                                    f"Configured WSL audio runtime is transcription-ready but ABI-degraded: "
                                    f"{wsl_distro}:{wsl_workspace} ({detail})"
                                ),
                            )
                        )
                else:
                    items.append(
                        Item(
                            FAIL,
                            f"Configured WSL audio runtime missing/unreachable: {wsl_distro}:{wsl_workspace} ({detail})",
                        )
                    )
    else:
        items.append(Item(PASS, "Audio not enabled in config; skipping WSL reachability check"))

    return items


def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        prog="python -m cli.goodq_doctor",
        description="GoodQ Doctor: read-only preflight validator for ingestion readiness.",
    )
    _ = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    _bootstrap_repo_imports(repo_root)

    print("GoodQ Doctor (read-only preflight)")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Repo: {repo_root}")

    gov_items, gov_info = _governance_checks(repo_root)
    cfg_items, cfg = _config_checks(repo_root)
    manifest_items = _manifest_checks(repo_root, cfg)
    phase6_items = _phase6_checks(repo_root, cfg, gov_info)
    service_items = _service_checks(cfg)

    statuses = [
        _print_section("Governance", gov_items),
        _print_section("Configuration", cfg_items),
        _print_section("Manifests", manifest_items),
        _print_section("Phase 6 Readiness", phase6_items),
        _print_section("Runtime Services", service_items),
    ]

    overall = max(statuses) if statuses else PASS
    print(f"\n== SUMMARY [{_label(overall)}] ==")
    print(f"Exit code: {overall}")
    return overall


if __name__ == "__main__":
    raise SystemExit(main())
