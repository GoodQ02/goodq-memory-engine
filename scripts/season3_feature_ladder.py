from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse, urlunparse

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import load_configs  # noqa: E402


DEFAULT_SOURCE_DIR = REPO_ROOT / "samples" / "ingestion" / "Sein_Experiment"
DEFAULT_EPOCH = "epoch_2025_12_23"
DEFAULT_REPORTS_ROOT = REPO_ROOT / "reports" / "fresh_ingest_runs"
DEFAULT_RUN_LABEL = "season3_feature_ladder"
CONFIG_LOCAL_PATH = REPO_ROOT / "configs" / "config.local.yaml"
BACKUP_SENTINEL = ".season3_feature_ladder_backup"
GENERIC_CONTEXT_PHRASES = {
    "people talk",
    "conversation happens",
    "scene shows",
    "people are talking",
    "characters interact",
}
SOCIAL_ROLE_TERMS = ("friend", "friends", "family", "couple")


@dataclass(frozen=True)
class FeatureRun:
    episode_prefix: str
    feature_name: str
    enable_scene_context_analysis: bool = False
    description: str = ""


DEFAULT_PLAN: tuple[FeatureRun, ...] = (
    FeatureRun(
        episode_prefix="03x01",
        feature_name="metadata_time_hints",
        description="Validate audio.metadata_time_hints surfacing",
    ),
    FeatureRun(
        episode_prefix="03x02",
        feature_name="scene_summarizer",
        description="Validate template summarizer modernization against nested scene payloads",
    ),
    FeatureRun(
        episode_prefix="03x03",
        feature_name="scene_context_llm",
        enable_scene_context_analysis=True,
        description="Validate additive scene_context_llm interpretation layer",
    ),
)


FEATURE_TEMPLATES: Dict[str, FeatureRun] = {
    feature_run.feature_name: feature_run for feature_run in DEFAULT_PLAN
}


def _parse_episode_prefixes(raw: Optional[str]) -> tuple[str, ...]:
    if not raw:
        return ()
    prefixes = tuple(prefix.strip() for prefix in str(raw).split(",") if prefix.strip())
    if not prefixes:
        raise ValueError("episode-prefixes was provided but no usable prefixes were found")
    return prefixes


def _sanitize_run_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    cleaned = cleaned.strip("._-")
    return cleaned or DEFAULT_RUN_LABEL


def _feature_template(feature_name: str) -> FeatureRun:
    template = FEATURE_TEMPLATES.get(feature_name)
    if template is None:
        raise ValueError(f"Unknown single-feature name: {feature_name}")
    return template


def _select_plan(
    start_at_prefix: Optional[str],
    episode_prefixes: tuple[str, ...] = (),
    single_feature_name: Optional[str] = None,
) -> tuple[FeatureRun, ...]:
    if episode_prefixes:
        if not single_feature_name:
            raise ValueError("single-feature must be provided when episode-prefixes is used")
        template = _feature_template(single_feature_name)
        plan = tuple(
            FeatureRun(
                episode_prefix=episode_prefix,
                feature_name=template.feature_name,
                enable_scene_context_analysis=template.enable_scene_context_analysis,
                description=f"{template.description} ({episode_prefix})",
            )
            for episode_prefix in episode_prefixes
        )
    else:
        plan = DEFAULT_PLAN
    if not start_at_prefix:
        return plan
    for index, feature_run in enumerate(plan):
        if feature_run.episode_prefix == start_at_prefix:
            return plan[index:]
    raise ValueError(f"Unknown start-at episode prefix: {start_at_prefix}")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    rendered = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    path.write_text(rendered, encoding="utf-8")


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(base.get(key), dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return value
    return None


def _find_episode_file(source_dir: Path, episode_prefix: str) -> Path:
    matches = sorted(source_dir.glob(f"{episode_prefix}*.mp4"))
    if not matches:
        raise FileNotFoundError(f"No episode found for prefix {episode_prefix!r} in {source_dir}")
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple episode matches found for {episode_prefix!r}: {', '.join(path.name for path in matches)}"
        )
    return matches[0]


def _stage_episode(input_dir: Path, episode_file: Path) -> Path:
    input_dir.mkdir(parents=True, exist_ok=True)
    staged_file = input_dir / episode_file.name
    if staged_file.exists():
        staged_file.unlink()
    try:
        os.link(episode_file, staged_file)
    except OSError:
        shutil.copy2(episode_file, staged_file)
    return staged_file


def _build_epoch_override(cfg: Dict[str, Any], epoch: str, enable_scene_context: bool) -> Dict[str, Any]:
    host_cfg = cfg.get("host") if isinstance(cfg.get("host"), dict) else {}
    host_data_root = str(
        _first_non_empty(
            os.environ.get("GOODQ_DATA_ROOT"),
            host_cfg.get("data_root"),
            "L:/_DATA",
        )
    ).rstrip("/\\")
    wsl_distro = str(_first_non_empty(os.environ.get("GOODQ_WSL_DISTRO"), host_cfg.get("wsl_distro"), "Ubuntu")).strip()
    wsl_user = _first_non_empty(os.environ.get("GOODQ_WSL_USER"), host_cfg.get("wsl_user"))
    wsl_workspace = _first_non_empty(os.environ.get("GOODQ_WSL_WORKSPACE"), host_cfg.get("wsl_workspace"))
    llm_cfg = cfg.get("llm") if isinstance(cfg.get("llm"), dict) else {}

    def _loopback_url(raw_url: Any, default_url: str) -> str:
        candidate = str(_first_non_empty(raw_url, default_url)).strip()
        try:
            parsed = urlparse(candidate)
            if not parsed.scheme:
                raise ValueError("missing scheme")
            netloc = "127.0.0.1"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        except Exception:
            return default_url

    vllm_url = _loopback_url(llm_cfg.get("vllm_url"), "http://127.0.0.1:38005/v1")
    api_url = _loopback_url(llm_cfg.get("api_url"), "http://127.0.0.1:38005/v1/chat/completions")
    vllm_model = str(
        _first_non_empty(
            llm_cfg.get("vllm_model"),
            llm_cfg.get("model_id"),
            os.environ.get("GOODQ_WSL_MODEL_PATH"),
            "/home/jdben/models/Qwen2.5-0.5B-Instruct",
        )
    ).strip()

    epoch_root = f"{host_data_root}/GoodQ_Data/epochs/{epoch}"
    override: Dict[str, Any] = {
        "host": {
            "data_root": host_data_root,
            "wsl_distro": wsl_distro,
        },
        "paths": {
            "log_dir": f"{epoch_root}/logs",
            "output_directory": f"{epoch_root}/output",
            "db_dir": epoch_root,
            "db_path": f"{epoch_root}/memory.db",
            "knowledge_graph_db": f"{epoch_root}/knowledge_graph.db",
            "faiss_dir": f"{epoch_root}/faiss",
            "faiss_audio_path": f"{epoch_root}/faiss/goodq_audio_{epoch}.index",
            "watchdog_state_file": f"{epoch_root}/logs/watchdog_state.json",
            "watchdog_lock_file": f"{epoch_root}/logs/watchdog.lock",
            "processing": f"{epoch_root}/processing",
            "csv_path": f"{epoch_root}/logs/system_metrics.csv",
        },
        "qdrant": {
            "collections": {
                "clip": f"goodq_clip_{epoch}",
                "dino": f"goodq_dino_{epoch}",
                "text": f"goodq_text_{epoch}",
                "audio": f"goodq_audio_{epoch}",
            }
        },
        "phase6": {
            "clip_collection": f"goodq_clip_{epoch}",
            "dino_collection": f"goodq_dino_{epoch}",
        },
        "llm": {
            "api_url": api_url,
            "vllm_url": vllm_url,
            "vllm_model": vllm_model,
            "features": {
                "scene_context_analysis": bool(enable_scene_context),
            }
        },
    }
    if isinstance(wsl_user, str) and wsl_user.strip():
        override["host"]["wsl_user"] = wsl_user
    if isinstance(wsl_workspace, str) and wsl_workspace.strip():
        override["host"]["wsl_workspace"] = wsl_workspace
    return override


def _llm_endpoint_ready(cfg: Dict[str, Any], timeout_seconds: int = 15) -> tuple[bool, str, Dict[str, Any]]:
    import urllib.error
    import urllib.request

    llm_cfg = cfg.get("llm") if isinstance(cfg.get("llm"), dict) else {}
    api_url = str(llm_cfg.get("api_url") or "").strip()
    if not api_url:
        return False, "llm.api_url missing", {
            "llm_models_probe": {
                "timestamp_utc": _iso_now(),
                "endpoint": None,
                "llm_model_id_used": [],
            }
        }
    models_url = api_url
    for suffix in ("/chat/completions", "/completions"):
        if models_url.endswith(suffix):
            models_url = models_url[: -len(suffix)]
            break
    models_url = models_url.rstrip("/") + "/models"
    probe: Dict[str, Any] = {
        "llm_models_probe": {
            "timestamp_utc": _iso_now(),
            "endpoint": models_url,
            "llm_model_id_used": [],
        }
    }
    try:
        with urllib.request.urlopen(models_url, timeout=timeout_seconds) as response:
            status_code = getattr(response, "status", 200)
            if status_code == 200:
                payload = json.loads(response.read().decode("utf-8"))
                data = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(data, list):
                    model_ids = [
                        entry.get("id")
                        for entry in data
                        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry.get("id").strip()
                    ]
                    probe["llm_models_probe"]["llm_model_id_used"] = model_ids
            return bool(status_code == 200), f"{models_url} -> {status_code}", probe
    except urllib.error.URLError as exc:
        return False, f"{models_url} unavailable: {exc.reason}", probe
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"{models_url} unavailable: {exc}", probe


def _load_json(path: Path) -> Dict[str, Any] | List[Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _temporal_index_path(cfg: Dict[str, Any], video_name: str) -> Path:
    processing_root = Path(cfg["paths"]["processing"])
    return processing_root / Path(video_name).stem / "temporal_index.json"


def _scene_manifest_path(cfg: Dict[str, Any], video_name: str) -> Path:
    processing_root = Path(cfg["paths"]["processing"])
    return processing_root / Path(video_name).stem / "video" / "scene_manifest.json"


def _summary_probe(db_path: Path, scene_ids: Iterable[str]) -> Dict[str, Any]:
    scene_ids = {scene_id for scene_id in scene_ids if isinstance(scene_id, str) and scene_id}
    result = {
        "summary_count": 0,
        "scene_coverage": 0,
        "visual_nested_proven": False,
        "audio_nested_proven": False,
        "unique_ratio": 0.0,
        "sample_summaries": [],
    }
    if not scene_ids or not db_path.exists():
        return result

    summaries: List[str] = []
    covered_ids: set[str] = set()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT content FROM summaries WHERE category = 'scene_summary'"
        ).fetchall()
    for (content,) in rows:
        try:
            payload = json.loads(content)
        except Exception:
            continue
        scene_id = payload.get("scene_id")
        summary = str(payload.get("summary") or "").strip()
        if scene_id not in scene_ids or not summary:
            continue
        covered_ids.add(scene_id)
        summaries.append(summary)
    result["summary_count"] = len(summaries)
    result["scene_coverage"] = len(covered_ids)
    if summaries:
        result["unique_ratio"] = len(set(summaries)) / float(len(summaries))
        result["sample_summaries"] = summaries[:3]
    return result


def _scene_manifest_nested_signal_probes(scene_manifest: Dict[str, Any]) -> Dict[str, Any]:
    scenes = scene_manifest.get("scenes") if isinstance(scene_manifest.get("scenes"), list) else []
    audio_nested_scene_id = None
    visual_nested_scene_id = None
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = scene.get("scene_id")
        keyframe = scene.get("keyframe") if isinstance(scene.get("keyframe"), dict) else {}
        audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
        if not visual_nested_scene_id and not scene.get("caption") and keyframe.get("caption"):
            visual_nested_scene_id = scene_id
        if not audio_nested_scene_id and not scene.get("transcript") and audio.get("transcript"):
            audio_nested_scene_id = scene_id
        if visual_nested_scene_id and audio_nested_scene_id:
            break
    return {
        "visual_nested_scene_id": visual_nested_scene_id,
        "audio_nested_scene_id": audio_nested_scene_id,
    }


def _extract_summary_by_scene_id(db_path: Path, target_scene_ids: set[str]) -> Dict[str, str]:
    if not db_path.exists() or not target_scene_ids:
        return {}
    found: Dict[str, str] = {}
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT content FROM summaries WHERE category = 'scene_summary'"
        ).fetchall()
    for (content,) in rows:
        try:
            payload = json.loads(content)
        except Exception:
            continue
        scene_id = payload.get("scene_id")
        summary = str(payload.get("summary") or "").strip()
        if scene_id in target_scene_ids and summary:
            found[scene_id] = summary
        if len(found) == len(target_scene_ids):
            break
    return found


def _segment_transcript_text(segment: Dict[str, Any]) -> str:
    transcript = _first_non_empty(
        segment.get("full_transcript"),
        segment.get("transcript"),
        segment.get("speaker_transcript"),
        segment.get("dialogue_text"),
    )
    return str(transcript or "").strip()


def _social_role_supported(term: str, transcript: str) -> bool:
    normalized = str(transcript or "").strip().lower()
    if not normalized:
        return False
    variants = {
        "friend": ("friend", "friends"),
        "friends": ("friend", "friends"),
        "family": ("family", "families"),
        "couple": ("couple", "couples"),
    }.get(term, (term,))
    return any(re.search(rf"\b{re.escape(variant)}\b", normalized) for variant in variants)


def _generic_context_detected(scene_context_segments: List[Dict[str, Any]]) -> bool:
    for segment in scene_context_segments:
        payload = segment.get("scene_context_llm")
        if not isinstance(payload, dict):
            continue
        transcript = _segment_transcript_text(segment)
        samples: List[str] = []
        for key in ("narrative_summary", "activity_description", "emotional_arc"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                samples.append(value.strip().lower())
        for value in payload.get("key_moments") or []:
            if isinstance(value, str) and value.strip():
                samples.append(value.strip().lower())
        if any(phrase in sample for sample in samples for phrase in GENERIC_CONTEXT_PHRASES):
            return True
        role_samples = list(samples)
        for value in payload.get("context_tags") or []:
            if isinstance(value, str) and value.strip():
                role_samples.append(value.strip().lower())
        for term in SOCIAL_ROLE_TERMS:
            if any(f" {term} " in f" {sample} " for sample in role_samples):
                if not _social_role_supported(term, transcript):
                    return True
    return False


def _evaluate_feature(
    feature_name: str,
    cfg: Dict[str, Any],
    video_result: Dict[str, Any],
    temporal_index: Dict[str, Any],
    scene_manifest: Dict[str, Any],
) -> tuple[bool, Dict[str, Any]]:
    diagnostics: Dict[str, Any] = {}
    common_ok = (
        bool(video_result.get("phase6_complete"))
        and bool(video_result.get("qdrant_ok"))
        and int(video_result.get("scene_meta", {}).get("scene_count") or 0) > 0
    )
    diagnostics["common"] = {
        "scene_count": int(video_result.get("scene_meta", {}).get("scene_count") or 0),
        "phase6_complete": bool(video_result.get("phase6_complete")),
        "qdrant_ok": bool(video_result.get("qdrant_ok")),
    }
    if not common_ok:
        return False, diagnostics

    if feature_name == "metadata_time_hints":
        segments_with = int(temporal_index.get("segments_with_metadata_time_hints") or 0)
        top_hints = temporal_index.get("top_metadata_time_hints") or []
        corpus_signal_present = bool(segments_with > 0 and top_hints)
        diagnostics["metadata_time_hints"] = {
            "segments_with_metadata_time_hints": segments_with,
            "top_metadata_time_hints": top_hints[:10],
            "corpus_signal_present": corpus_signal_present,
            "no_signal_expected_on_chunked_wav": not corpus_signal_present,
        }
        success = True
        return success, diagnostics

    if feature_name == "scene_summarizer":
        db_path = Path(cfg["paths"]["db_path"])
        scenes = scene_manifest.get("scenes") if isinstance(scene_manifest.get("scenes"), list) else []
        scene_ids = [scene.get("scene_id") for scene in scenes if isinstance(scene, dict)]
        summary_probe = _summary_probe(db_path, scene_ids)
        nested_probe = _scene_manifest_nested_signal_probes(scene_manifest)
        target_scene_ids = {
            nested_probe["visual_nested_scene_id"],
            nested_probe["audio_nested_scene_id"],
        }
        target_scene_ids.discard(None)
        target_summaries = _extract_summary_by_scene_id(db_path, target_scene_ids)
        summary_probe["visual_nested_proven"] = bool(
            nested_probe["visual_nested_scene_id"]
            and "Visual:" in (target_summaries.get(nested_probe["visual_nested_scene_id"]) or "")
        )
        summary_probe["audio_nested_proven"] = bool(
            nested_probe["audio_nested_scene_id"]
            and "Transcript:" in (target_summaries.get(nested_probe["audio_nested_scene_id"]) or "")
        )
        diagnostics["scene_summarizer"] = summary_probe
        coverage_ok = summary_probe["scene_coverage"] >= max(1, int(len(scene_ids) * 0.8))
        specificity_ok = summary_probe["unique_ratio"] >= 0.5
        signal_uptake_ok = summary_probe["visual_nested_proven"] or summary_probe["audio_nested_proven"]
        return bool(coverage_ok and specificity_ok and signal_uptake_ok), diagnostics

    if feature_name == "scene_context_llm":
        segments = temporal_index.get("segments") if isinstance(temporal_index.get("segments"), list) else []
        scene_context_segments = [
            segment for segment in segments
            if isinstance(segment, dict) and isinstance(segment.get("scene_context_llm"), dict)
        ]
        top_tags = temporal_index.get("top_scene_context_tags") or []
        unique_tags = {
            str(entry.get("tag")).strip()
            for entry in top_tags
            if isinstance(entry, dict) and str(entry.get("tag") or "").strip()
        }
        diagnostics["scene_context_llm"] = {
            "segments_with_scene_context_llm": int(temporal_index.get("segments_with_scene_context_llm") or 0),
            "top_scene_context_tags": top_tags[:10],
            "unique_tag_count": len(unique_tags),
            "generic_context_detected": _generic_context_detected(scene_context_segments),
        }
        success = (
            diagnostics["scene_context_llm"]["segments_with_scene_context_llm"] > 0
            and len(unique_tags) >= 3
            and not diagnostics["scene_context_llm"]["generic_context_detected"]
        )
        return bool(success), diagnostics

    diagnostics["error"] = f"Unsupported feature {feature_name}"
    return False, diagnostics


def _prepare_run_record(feature_run: FeatureRun, episode_file: Path, run_dir: Path) -> Dict[str, Any]:
    return {
        "ts_utc": _iso_now(),
        "episode": episode_file.name,
        "feature_enabled": feature_run.feature_name,
        "description": feature_run.description,
        "run_dir": str(run_dir),
        "status": "pending",
        "metrics": {},
        "notes": [],
    }


def _safe_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _restore_config_local(original_bytes: Optional[bytes], backup_path: Optional[Path]) -> None:
    if original_bytes is None:
        if CONFIG_LOCAL_PATH.exists():
            CONFIG_LOCAL_PATH.unlink()
    else:
        CONFIG_LOCAL_PATH.write_bytes(original_bytes)
    if backup_path and backup_path.exists():
        try:
            backup_path.unlink()
        except OSError:
            pass


def _run_ingestion(
    episode_file: Path,
    run_dir: Path,
    workspace_root: Path,
) -> tuple[int, Path]:
    input_dir = workspace_root / "input"
    _stage_episode(input_dir, episode_file)
    output_path = run_dir / "output" / "scene_ingest_results.json"
    workspace_path = run_dir / "workspace"
    stdout_path = run_dir / "ingest.stdout.log"
    stderr_path = run_dir / "ingest.stderr.log"
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_path.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-u",
        "-m",
        "cli.run_ingestion",
        "--input-dir",
        str(input_dir),
        "--output",
        str(output_path),
        "--workspace",
        str(workspace_path),
        "--max-videos",
        "1",
        "--force",
        "--verbose",
    ]
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
        process = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            stdout=stdout_handle,
            stderr=stderr_handle,
            check=False,
        )
    return process.returncode, output_path


def _load_video_result(output_path: Path, video_name: str) -> Dict[str, Any]:
    payload = _load_json(output_path)
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected ingestion output payload at {output_path}")
    for entry in payload:
        if isinstance(entry, dict) and entry.get("video_name") == video_name:
            return entry
    if len(payload) == 1 and isinstance(payload[0], dict):
        return payload[0]
    raise KeyError(f"Video result for {video_name} not found in {output_path}")


def _run_plan(args: argparse.Namespace) -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_label = _sanitize_run_label(args.run_label)
    root_run_dir = args.reports_root / f"{timestamp}_{run_label}"
    root_run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = root_run_dir / "experiment_log.json"

    original_bytes = CONFIG_LOCAL_PATH.read_bytes() if CONFIG_LOCAL_PATH.exists() else None
    backup_path = root_run_dir / f"{CONFIG_LOCAL_PATH.name}.{BACKUP_SENTINEL}"
    if original_bytes is not None:
        backup_path.write_bytes(original_bytes)
    try:
        base_local_cfg = _read_yaml(CONFIG_LOCAL_PATH)
        base_cfg = load_configs({})

        experiment_log: Dict[str, Any] = {
            "ts_utc": _iso_now(),
            "epoch": args.epoch,
            "source_dir": str(args.source_dir),
            "plan": [],
            "status": "running",
        }
        _safe_write_json(summary_path, experiment_log)

        for feature_run in _select_plan(
            args.start_at_prefix,
            _parse_episode_prefixes(args.episode_prefixes),
            args.single_feature,
        ):
            episode_file = _find_episode_file(args.source_dir, feature_run.episode_prefix)
            run_slug = f"{feature_run.episode_prefix}_{feature_run.feature_name}"
            run_dir = root_run_dir / run_slug
            workspace_root = root_run_dir / "_staging" / run_slug
            record = _prepare_run_record(feature_run, episode_file, run_dir)
            experiment_log["plan"].append(record)
            _safe_write_json(summary_path, experiment_log)

            override_cfg = json.loads(json.dumps(base_local_cfg))
            _deep_merge(
                override_cfg,
                _build_epoch_override(base_cfg, args.epoch, feature_run.enable_scene_context_analysis),
            )
            _write_yaml(CONFIG_LOCAL_PATH, override_cfg)

            if feature_run.enable_scene_context_analysis and not args.plan_only:
                effective_cfg = load_configs({})
                llm_ready, llm_reason, llm_probe = _llm_endpoint_ready(effective_cfg)
                record["metrics"]["llm_endpoint_ready"] = llm_ready
                record["metrics"].update(llm_probe)
                record["notes"].append(llm_reason)
                if not llm_ready:
                    record["status"] = "blocked"
                    experiment_log["status"] = "blocked"
                    _safe_write_json(run_dir / "experiment_log.json", record)
                    _safe_write_json(summary_path, experiment_log)
                    return 2

            if args.plan_only:
                record["status"] = "planned"
                _safe_write_json(run_dir / "experiment_log.json", record)
                _safe_write_json(summary_path, experiment_log)
                continue

            start_time = time.time()
            return_code, output_path = _run_ingestion(episode_file, run_dir, workspace_root)
            elapsed_seconds = round(time.time() - start_time, 2)
            record["metrics"]["return_code"] = return_code
            record["metrics"]["elapsed_seconds"] = elapsed_seconds
            record["metrics"]["output_path"] = str(output_path)
            if return_code != 0 or not output_path.exists():
                record["status"] = "failed"
                record["notes"].append("Ingestion did not produce a successful output artifact.")
                experiment_log["status"] = "failed"
                _safe_write_json(run_dir / "experiment_log.json", record)
                _safe_write_json(summary_path, experiment_log)
                return 1

            effective_cfg = load_configs({})
            video_result = _load_video_result(output_path, episode_file.name)
            temporal_index_path = _temporal_index_path(effective_cfg, episode_file.name)
            scene_manifest_path = _scene_manifest_path(effective_cfg, episode_file.name)
            if not temporal_index_path.exists() or not scene_manifest_path.exists():
                record["status"] = "failed"
                record["notes"].append("Canonical temporal_index.json or scene_manifest.json missing after run.")
                experiment_log["status"] = "failed"
                _safe_write_json(run_dir / "experiment_log.json", record)
                _safe_write_json(summary_path, experiment_log)
                return 1

            temporal_index = _load_json(temporal_index_path)
            scene_manifest = _load_json(scene_manifest_path)
            if not isinstance(temporal_index, dict) or not isinstance(scene_manifest, dict):
                record["status"] = "failed"
                record["notes"].append("Canonical outputs were not valid JSON objects.")
                experiment_log["status"] = "failed"
                _safe_write_json(run_dir / "experiment_log.json", record)
                _safe_write_json(summary_path, experiment_log)
                return 1

            success, diagnostics = _evaluate_feature(
                feature_run.feature_name,
                effective_cfg,
                video_result,
                temporal_index,
                scene_manifest,
            )
            record["metrics"].update(diagnostics)
            if feature_run.feature_name == "metadata_time_hints":
                metadata_diag = diagnostics.get("metadata_time_hints") if isinstance(diagnostics, dict) else None
                if isinstance(metadata_diag, dict) and not metadata_diag.get("corpus_signal_present", True):
                    record["notes"].append(
                        "No metadata_time_hints were present in this chunked-audio corpus; wiring validated without source signal."
                    )
            record["metrics"]["temporal_index_path"] = str(temporal_index_path)
            record["metrics"]["scene_manifest_path"] = str(scene_manifest_path)
            record["status"] = "passed" if success else "failed"
            if not success:
                record["notes"].append("Feature-specific success criteria were not met.")
                experiment_log["status"] = "failed"
                _safe_write_json(run_dir / "experiment_log.json", record)
                _safe_write_json(summary_path, experiment_log)
                return 1

            _safe_write_json(run_dir / "experiment_log.json", record)
            _safe_write_json(summary_path, experiment_log)

        experiment_log["status"] = "passed" if args.plan_only else "completed"
        _safe_write_json(summary_path, experiment_log)
        return 0
    finally:
        _restore_config_local(original_bytes, backup_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a one-feature-per-episode feature witness against an isolated epoch."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing the Season 3 episode files.",
    )
    parser.add_argument(
        "--epoch",
        default=DEFAULT_EPOCH,
        help="Treatment epoch name to isolate outputs into.",
    )
    parser.add_argument(
        "--reports-root",
        type=Path,
        default=DEFAULT_REPORTS_ROOT,
        help="Root directory for experiment run folders.",
    )
    parser.add_argument(
        "--run-label",
        default=DEFAULT_RUN_LABEL,
        help="Suffix label for the witness run root, e.g. season4_release_witness.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Write the run plan and config backups without executing ingestion.",
    )
    parser.add_argument(
        "--start-at-prefix",
        help="Resume the ladder starting at a specific episode prefix, e.g. 03x02.",
    )
    parser.add_argument(
        "--episode-prefixes",
        help="Comma-separated episode prefixes for a custom campaign, e.g. 03x03,03x04,03x05.",
    )
    parser.add_argument(
        "--single-feature",
        choices=tuple(FEATURE_TEMPLATES.keys()),
        help="When running a custom campaign, apply this single validated feature template to every listed episode.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    return _run_plan(args)


if __name__ == "__main__":
    raise SystemExit(main())
