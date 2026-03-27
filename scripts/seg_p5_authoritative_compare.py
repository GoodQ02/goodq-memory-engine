from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from steps.common.config_loader import load_configs


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = REPO_ROOT / "samples" / "ingestion" / "Sein_Experiment"
DEFAULT_REPORT_PATH = REPO_ROOT / "reports" / "seg_p5_authoritative_vs_legacy.json"
DEFAULT_CAMPAIGN_ROOT = REPO_ROOT / "reports" / "seg_p5_authoritative_runs"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _campaign_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _slugify(value: str) -> str:
    safe = []
    for ch in value.lower():
        if ch.isalnum():
            safe.append(ch)
        elif ch in {" ", "-", "_", "."}:
            safe.append("_")
    slug = "".join(safe).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "episode"


def _link_or_copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _mean_or_none(values: Iterable[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    return float(mean(nums))


def _base_models_cache(cfg: Dict[str, Any]) -> Optional[str]:
    paths_cfg = cfg.get("paths") if isinstance(cfg, dict) else {}
    if not isinstance(paths_cfg, dict):
        return None
    value = paths_cfg.get("models_cache")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _base_qdrant_host(cfg: Dict[str, Any]) -> Optional[str]:
    qdrant_cfg = cfg.get("qdrant") if isinstance(cfg, dict) else {}
    if not isinstance(qdrant_cfg, dict):
        return None
    value = qdrant_cfg.get("host")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _build_run_overrides(
    *,
    campaign_root: Path,
    episode_slug: str,
    mode_slug: str,
    collection_prefix: str,
    base_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_root = campaign_root / episode_slug / mode_slug / "runtime"
    data_root = runtime_root / "GoodQ_Data"
    epoch_root = data_root / "epochs" / "seg_p5_compare"
    log_dir = epoch_root / "logs"
    faiss_dir = epoch_root / "faiss"
    output_dir = epoch_root / "output"
    processing_dir = epoch_root / "processing"
    models_cache = _base_models_cache(base_cfg)
    qdrant_host = _base_qdrant_host(base_cfg)

    overrides: Dict[str, Any] = {
        "segmentation": {
            "enabled": True,
            "activation": "off",
            "metrics_output": False,
            "shadow_audio_overlay": False,
        },
        "paths": {
            "data_root": str(data_root),
            "import_inbox": str(data_root / "import_inbox"),
            "processed": str(data_root / "processed"),
            "failed": str(data_root / "failed"),
            "db_dir": str(epoch_root),
            "db_path": str(epoch_root / "memory.db"),
            "knowledge_graph_db": str(epoch_root / "knowledge_graph.db"),
            "processing": str(processing_dir),
            "output_directory": str(output_dir),
            "log_dir": str(log_dir),
            "watchdog_state_file": str(log_dir / "watchdog_state.json"),
            "watchdog_lock_file": str(log_dir / "watchdog.lock"),
            "csv_path": str(log_dir / "system_metrics.csv"),
            "faiss_dir": str(faiss_dir),
            "faiss_audio_path": str(faiss_dir / f"{collection_prefix}_audio.index"),
        },
        "qdrant": {
            "enabled": True,
            "collections": {
                "clip": f"{collection_prefix}_clip",
                "dino": f"{collection_prefix}_dino",
                "text": f"{collection_prefix}_text",
                "audio": f"{collection_prefix}_audio",
            },
        },
    }
    if models_cache:
        overrides["paths"]["models_cache"] = models_cache
    if qdrant_host:
        overrides["qdrant"]["host"] = qdrant_host
    return overrides


def _episode_runtime_layout(campaign_root: Path, episode_slug: str, mode_slug: str) -> Dict[str, Path]:
    episode_root = campaign_root / episode_slug / mode_slug
    return {
        "episode_root": episode_root,
        "workspace": episode_root / "workspace",
        "output": episode_root / "ingestion_results.json",
        "input_dir": episode_root / "input",
    }


def _patch_load_configs(overrides: Dict[str, Any]):
    import cli.run_ingestion as run_ingestion_module

    original = run_ingestion_module.load_configs

    def patched(_unused: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return load_configs(copy.deepcopy(overrides))

    run_ingestion_module.load_configs = patched
    return run_ingestion_module, original


@contextmanager
def _temporary_env(updates: Dict[str, Optional[str]]):
    saved = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _normalize_scenes(result: Dict[str, Any]) -> List[Dict[str, float]]:
    scenes = []
    for scene in result.get("scenes", []) if isinstance(result.get("scenes"), list) else []:
        if not isinstance(scene, dict):
            continue
        start = scene.get("start")
        end = scene.get("end")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
            scenes.append({"start": float(start), "end": float(end)})
    return scenes


def _scene_overlap(left: Dict[str, float], right: Dict[str, float]) -> float:
    return max(0.0, min(left["end"], right["end"]) - max(left["start"], right["start"]))


def _compare_scene_lists(live_scenes: List[Dict[str, float]], candidate_scenes: List[Dict[str, float]]) -> Dict[str, Any]:
    claimed_candidates = set()
    matched_count = 0
    matched_duration = 0.0
    boundary_deltas: List[float] = []

    for live_idx, live in enumerate(live_scenes):
        best_idx = None
        best_overlap = 0.0
        for candidate_idx, candidate in enumerate(candidate_scenes):
            if candidate_idx in claimed_candidates:
                continue
            overlap = _scene_overlap(live, candidate)
            if overlap > best_overlap:
                best_idx = candidate_idx
                best_overlap = overlap
        if best_idx is None or best_overlap <= 0.0:
            continue
        claimed_candidates.add(best_idx)
        matched_count += 1
        matched_duration += best_overlap
        candidate = candidate_scenes[best_idx]
        boundary_deltas.append(abs(live["start"] - candidate["start"]))
        boundary_deltas.append(abs(live["end"] - candidate["end"]))

    live_duration = sum(scene["end"] - scene["start"] for scene in live_scenes)
    return {
        "live_scene_count": len(live_scenes),
        "candidate_scene_count": len(candidate_scenes),
        "matched_scene_count": matched_count,
        "matched_scene_ratio_live": matched_count / len(live_scenes) if live_scenes else 0.0,
        "matched_scene_ratio_candidate": matched_count / len(candidate_scenes) if candidate_scenes else 0.0,
        "duration_coverage": matched_duration / live_duration if live_duration > 0 else 0.0,
        "boundary_delta_mean_sec": float(mean(boundary_deltas)) if boundary_deltas else 0.0,
        "boundary_delta_max_sec": float(max(boundary_deltas)) if boundary_deltas else 0.0,
    }


def _extract_run_summary(result: Dict[str, Any], *, mode: str, runtime: Dict[str, Path]) -> Dict[str, Any]:
    scenes = _normalize_scenes(result)
    orchestration = result.get("orchestration") if isinstance(result.get("orchestration"), dict) else {}
    return {
        "mode": mode,
        "output": str(runtime["output"]),
        "workspace": str(runtime["workspace"]),
        "scene_count": len(scenes),
        "scene_total_duration": float(sum(scene["end"] - scene["start"] for scene in scenes)),
        "phase6_complete": bool(result.get("phase6_complete")),
        "qdrant_ok": result.get("qdrant_ok"),
        "faiss_ok": result.get("faiss_ok"),
        "orchestration": {
            "scene_backend_selected": orchestration.get("scene_backend_selected"),
            "scene_backend_effective": orchestration.get("scene_backend_effective"),
            "scene_backend_effective_reason": orchestration.get("scene_backend_effective_reason"),
        },
        "scenes": scenes,
    }


def _run_mode(
    *,
    video_path: Path,
    campaign_root: Path,
    campaign_id: str,
    base_cfg: Dict[str, Any],
    mode: str,
    verbose: bool,
) -> Dict[str, Any]:
    import cli.run_ingestion as run_ingestion_module

    episode_slug = _slugify(video_path.stem)
    mode_slug = "authoritative" if mode == "authoritative" else "legacy"
    runtime = _episode_runtime_layout(campaign_root, episode_slug, mode_slug)
    runtime["workspace"].mkdir(parents=True, exist_ok=True)
    runtime["input_dir"].mkdir(parents=True, exist_ok=True)
    _link_or_copy_file(video_path, runtime["input_dir"] / video_path.name)

    collection_prefix = f"segp5cmp_{campaign_id}_{episode_slug}_{mode_slug}"[:56]
    overrides = _build_run_overrides(
        campaign_root=campaign_root,
        episode_slug=episode_slug,
        mode_slug=mode_slug,
        collection_prefix=collection_prefix,
        base_cfg=base_cfg,
    )

    env_updates = {
        "GOODQ_SEGMENTATION_MODE": "authoritative" if mode == "authoritative" else None,
        "GOODQ_SEGMENTATION_BACKEND": "seg_p5" if mode == "authoritative" else None,
    }

    module, original_load_configs = _patch_load_configs(overrides)
    try:
        with _temporary_env(env_updates):
            module.run(
                input_dir=runtime["input_dir"],
                output=runtime["output"],
                workspace=runtime["workspace"],
                max_videos=1,
                force_reprocess=True,
                verbose=verbose,
            )
    finally:
        module.load_configs = original_load_configs

    raw = json.loads(runtime["output"].read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"No ingestion result produced for {video_path.name} ({mode})")
    return _extract_run_summary(raw[0], mode=mode, runtime=runtime)


def _compare_episode_runs(video_path: Path, legacy: Dict[str, Any], authoritative: Dict[str, Any]) -> Dict[str, Any]:
    comparison = _compare_scene_lists(
        legacy.get("scenes", []),
        authoritative.get("scenes", []),
    )
    return {
        "episode_name": video_path.stem,
        "video_path": str(video_path),
        "legacy": {key: value for key, value in legacy.items() if key != "scenes"},
        "authoritative": {key: value for key, value in authoritative.items() if key != "scenes"},
        "comparison": {
            **comparison,
            "scene_count_delta": authoritative["scene_count"] - legacy["scene_count"],
            "phase6_complete_legacy": legacy["phase6_complete"],
            "phase6_complete_authoritative": authoritative["phase6_complete"],
        },
    }


def _build_report(
    *,
    campaign_id: str,
    input_dir: Path,
    report_path: Path,
    campaign_root: Path,
    episodes: List[Dict[str, Any]],
    base_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "version": 1,
        "generated_at": _utc_now_iso(),
        "campaign_id": campaign_id,
        "input_dir": str(input_dir),
        "report_path": str(report_path),
        "campaign_root": str(campaign_root),
        "runtime": {
            "host_profile": (base_cfg.get("host") or {}).get("profile") if isinstance(base_cfg.get("host"), dict) else None,
            "models_cache": _base_models_cache(base_cfg),
            "qdrant_host": _base_qdrant_host(base_cfg),
        },
        "episodes": episodes,
        "aggregate": {
            "episode_count": len(episodes),
            "mean_matched_scene_ratio_live": _mean_or_none(
                episode.get("comparison", {}).get("matched_scene_ratio_live") for episode in episodes
            ),
            "mean_duration_coverage": _mean_or_none(
                episode.get("comparison", {}).get("duration_coverage") for episode in episodes
            ),
            "mean_boundary_delta_mean_sec": _mean_or_none(
                episode.get("comparison", {}).get("boundary_delta_mean_sec") for episode in episodes
            ),
            "mean_scene_count_delta": _mean_or_none(
                episode.get("comparison", {}).get("scene_count_delta") for episode in episodes
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run a manual SEG_P5 authoritative-vs-legacy comparison.")
    ap.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    ap.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    ap.add_argument("--limit", type=int, default=1, help="Maximum number of episodes to process.")
    ap.add_argument("--verbose", action="store_true", help="Emit verbose run_ingestion output.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    report_path = args.report.resolve()
    campaign_root_base = args.campaign_root.resolve()

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    videos = sorted(path for path in input_dir.iterdir() if path.is_file())
    if args.limit > 0:
        videos = videos[: args.limit]
    if not videos:
        raise RuntimeError(f"No videos found in {input_dir}")

    campaign_id = _campaign_id()
    campaign_root = campaign_root_base / campaign_id
    campaign_root.mkdir(parents=True, exist_ok=True)

    base_cfg = load_configs({})
    episodes = []
    for video_path in videos:
        legacy = _run_mode(
            video_path=video_path,
            campaign_root=campaign_root,
            campaign_id=campaign_id,
            base_cfg=base_cfg,
            mode="legacy",
            verbose=bool(args.verbose),
        )
        authoritative = _run_mode(
            video_path=video_path,
            campaign_root=campaign_root,
            campaign_id=campaign_id,
            base_cfg=base_cfg,
            mode="authoritative",
            verbose=bool(args.verbose),
        )
        episodes.append(_compare_episode_runs(video_path, legacy, authoritative))

    report = _build_report(
        campaign_id=campaign_id,
        input_dir=input_dir,
        report_path=report_path,
        campaign_root=campaign_root,
        episodes=episodes,
        base_cfg=base_cfg,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "episodes": len(episodes)}, indent=2))


if __name__ == "__main__":
    main()
