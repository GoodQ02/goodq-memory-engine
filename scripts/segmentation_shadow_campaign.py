from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from steps.common.config_loader import load_configs


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = REPO_ROOT / "samples" / "ingestion" / "Sein_Experiment"
DEFAULT_REPORT_PATH = REPO_ROOT / "reports" / "segmentation_shadow_campaign.json"
DEFAULT_CAMPAIGN_ROOT = REPO_ROOT / "reports" / "segmentation_shadow_campaign_runs"


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


def _build_campaign_overrides(
    *,
    campaign_root: Path,
    episode_slug: str,
    collection_prefix: str,
    base_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_root = campaign_root / episode_slug / "runtime"
    data_root = runtime_root / "GoodQ_Data"
    epoch_root = data_root / "epochs" / "shadow_campaign"
    log_dir = epoch_root / "logs"
    faiss_dir = epoch_root / "faiss"
    output_dir = epoch_root / "output"
    processing_dir = epoch_root / "processing"
    models_cache = _base_models_cache(base_cfg)
    qdrant_host = _base_qdrant_host(base_cfg)

    overrides: Dict[str, Any] = {
        "segmentation": {
            "enabled": True,
            "activation": "shadow",
            "metrics_output": True,
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


def _episode_runtime_layout(campaign_root: Path, episode_slug: str) -> Dict[str, Path]:
    episode_root = campaign_root / episode_slug
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


def _extract_episode_metrics(result: Dict[str, Any], *, episode_name: str, video_path: Path, runtime: Dict[str, Path]) -> Dict[str, Any]:
    shadow = result.get("segmentation_shadow") if isinstance(result.get("segmentation_shadow"), dict) else {}
    metrics = shadow.get("metrics") if isinstance(shadow.get("metrics"), dict) else {}
    orchestration = result.get("orchestration") if isinstance(result.get("orchestration"), dict) else {}

    return {
        "episode_name": episode_name,
        "video_path": str(video_path),
        "workspace": str(runtime["workspace"]),
        "output": str(runtime["output"]),
        "status": "ok",
        "shadow_status": shadow.get("status"),
        "shadow_reason": shadow.get("reason"),
        "scene_backend_match_ratio_live": metrics.get("scene_backend_match_ratio_live"),
        "scene_backend_duration_coverage": metrics.get("scene_backend_duration_coverage"),
        "scene_backend_boundary_delta_mean_sec": metrics.get("scene_backend_boundary_delta_mean_sec"),
        "scene_count_live": metrics.get("scene_count_current"),
        "scene_count_shadow": metrics.get("scene_count_shadow"),
        "scene_count_delta": metrics.get("scene_count_delta"),
        "metrics_path": shadow.get("metrics_path"),
        "shadow_summary_path": shadow.get("summary_path"),
        "scene_manifest_path": shadow.get("scene_manifest_path"),
        "segmentation_manifest_path": shadow.get("segmentation_manifest_path"),
        "orchestration": {
            "scene_backend_selected": orchestration.get("scene_backend_selected"),
            "scene_backend_effective": orchestration.get("scene_backend_effective"),
            "scene_backend_effective_reason": orchestration.get("scene_backend_effective_reason"),
        },
    }


def _build_campaign_report(
    *,
    campaign_id: str,
    input_dir: Path,
    report_path: Path,
    campaign_root: Path,
    episodes: List[Dict[str, Any]],
    base_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    successful = [episode for episode in episodes if episode.get("status") == "ok"]
    return {
        "version": 1,
        "generated_at": _utc_now_iso(),
        "campaign_id": campaign_id,
        "input_dir": str(input_dir),
        "report_path": str(report_path),
        "campaign_root": str(campaign_root),
        "segmentation": {
            "activation": "shadow",
            "metrics_output": True,
            "shadow_audio_overlay": False,
        },
        "runtime": {
            "host_profile": (base_cfg.get("host") or {}).get("profile") if isinstance(base_cfg.get("host"), dict) else None,
            "models_cache": _base_models_cache(base_cfg),
            "qdrant_host": _base_qdrant_host(base_cfg),
        },
        "episodes": episodes,
        "aggregate": {
            "episode_count": len(episodes),
            "successful_episode_count": len(successful),
            "failed_episode_count": len(episodes) - len(successful),
            "mean_scene_backend_match_ratio_live": _mean_or_none(
                episode.get("scene_backend_match_ratio_live") for episode in successful
            ),
            "mean_scene_backend_duration_coverage": _mean_or_none(
                episode.get("scene_backend_duration_coverage") for episode in successful
            ),
            "mean_scene_backend_boundary_delta_mean_sec": _mean_or_none(
                episode.get("scene_backend_boundary_delta_mean_sec") for episode in successful
            ),
            "mean_scene_count_live": _mean_or_none(episode.get("scene_count_live") for episode in successful),
            "mean_scene_count_shadow": _mean_or_none(episode.get("scene_count_shadow") for episode in successful),
        },
    }


def _run_episode(
    *,
    video_path: Path,
    campaign_root: Path,
    campaign_id: str,
    base_cfg: Dict[str, Any],
    verbose: bool,
) -> Dict[str, Any]:
    import cli.run_ingestion as run_ingestion_module

    episode_slug = _slugify(video_path.stem)
    runtime = _episode_runtime_layout(campaign_root, episode_slug)
    runtime["workspace"].mkdir(parents=True, exist_ok=True)
    runtime["input_dir"].mkdir(parents=True, exist_ok=True)
    _link_or_copy_file(video_path, runtime["input_dir"] / video_path.name)

    collection_prefix = f"segshadow_{campaign_id}_{episode_slug}"[:56]
    overrides = _build_campaign_overrides(
        campaign_root=campaign_root,
        episode_slug=episode_slug,
        collection_prefix=collection_prefix,
        base_cfg=base_cfg,
    )

    module, original_load_configs = _patch_load_configs(overrides)
    try:
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
        raise RuntimeError(f"No ingestion result produced for {video_path.name}")
    result = raw[0]
    return _extract_episode_metrics(result, episode_name=video_path.stem, video_path=video_path, runtime=runtime)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run a controlled SEG_P5 shadow campaign and write aggregate metrics.")
    ap.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    ap.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    ap.add_argument("--limit", type=int, default=0, help="Maximum number of episodes to process (0 = all).")
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
    episodes: List[Dict[str, Any]] = []
    for video_path in videos:
        try:
            episode_report = _run_episode(
                video_path=video_path,
                campaign_root=campaign_root,
                campaign_id=campaign_id,
                base_cfg=base_cfg,
                verbose=bool(args.verbose),
            )
        except Exception as exc:  # noqa: BLE001
            episode_report = {
                "episode_name": video_path.stem,
                "video_path": str(video_path),
                "status": "error",
                "error": str(exc),
            }
        episodes.append(episode_report)

    report = _build_campaign_report(
        campaign_id=campaign_id,
        input_dir=input_dir,
        report_path=report_path,
        campaign_root=campaign_root,
        episodes=episodes,
        base_cfg=base_cfg,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[SEG_SHADOW] Wrote campaign report: {report_path}")


if __name__ == "__main__":
    main()
