from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from steps.common.config_loader import load_configs


def _normalize_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return " ".join(normalized.split())


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_projected_scenes(projected_output: Any) -> List[Dict[str, Any]]:
    if isinstance(projected_output, dict):
        scenes = projected_output.get("scenes")
        return [scene for scene in scenes if isinstance(scene, dict)] if isinstance(scenes, list) else []

    if isinstance(projected_output, list):
        flattened: List[Dict[str, Any]] = []
        for item in projected_output:
            if not isinstance(item, dict):
                continue
            scenes = item.get("scenes")
            if isinstance(scenes, list):
                flattened.extend(scene for scene in scenes if isinstance(scene, dict))
            elif "summary" in item or "tags" in item or "key_moments" in item:
                flattened.append(item)
        return flattened

    return []


def _resolve_processing_root(epoch: str) -> Path:
    cfg = load_configs({})
    host_cfg = cfg.get("host") if isinstance(cfg.get("host"), dict) else {}
    data_root = os.environ.get("GOODQ_DATA_ROOT") or host_cfg.get("data_root")
    if not isinstance(data_root, str) or not data_root.strip():
        raise RuntimeError("GOODQ_DATA_ROOT or host.data_root is required for episode reference evaluation")
    data_root = data_root.rstrip("/\\")
    return Path(f"{data_root}/GoodQ_Data/epochs/{epoch}/processing")


def _collect_scene_surfaces(scene: Dict[str, Any]) -> Dict[str, List[str]]:
    scene_context = scene.get("scene_context_llm") if isinstance(scene.get("scene_context_llm"), dict) else {}
    arbitration = scene.get("scene_context_arbitration") if isinstance(scene.get("scene_context_arbitration"), dict) else {}
    hypotheses = arbitration.get("hypotheses") if isinstance(arbitration.get("hypotheses"), list) else []

    primary_hypotheses: List[str] = []
    contextual_hypotheses: List[str] = []
    for item in hypotheses:
        if not isinstance(item, dict):
            continue
        claim = item.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            continue
        if item.get("weight") == "primary":
            primary_hypotheses.append(claim)
        else:
            contextual_hypotheses.append(claim)

    key_moments = scene_context.get("key_moments") if isinstance(scene_context.get("key_moments"), list) else []
    context_tags = scene_context.get("context_tags") if isinstance(scene_context.get("context_tags"), list) else []
    primary_tags = scene_context.get("primary_tags") if isinstance(scene_context.get("primary_tags"), list) else []
    contextual_tags = scene_context.get("contextual_tags") if isinstance(scene_context.get("contextual_tags"), list) else []
    structural_tags = scene_context.get("structural_tags") if isinstance(scene_context.get("structural_tags"), list) else []

    return {
        "summary": [scene_context.get("narrative_summary")] if isinstance(scene_context.get("narrative_summary"), str) else [],
        "key_moments": [value for value in key_moments if isinstance(value, str)],
        "context_tags": [value for value in context_tags if isinstance(value, str)],
        "primary_tags": [value for value in primary_tags if isinstance(value, str)],
        "contextual_tags": [value for value in contextual_tags if isinstance(value, str)],
        "structural_tags": [value for value in structural_tags if isinstance(value, str)],
        "primary_hypotheses": primary_hypotheses,
        "contextual_hypotheses": contextual_hypotheses,
    }


def _surface_matches(
    phrases: Iterable[str],
    scene_surfaces: Dict[str, List[str]],
) -> Tuple[bool, bool]:
    normalized_phrases = [_normalize_text(phrase) for phrase in phrases if _normalize_text(phrase)]
    if not normalized_phrases:
        return False, False

    primary_buckets = (
        scene_surfaces["primary_tags"]
        + scene_surfaces["primary_hypotheses"]
        + scene_surfaces["summary"]
        + scene_surfaces["key_moments"]
    )
    contextual_buckets = (
        scene_surfaces["contextual_tags"]
        + scene_surfaces["contextual_hypotheses"]
        + scene_surfaces["context_tags"]
    )

    def _bucket_has_match(values: Iterable[str]) -> bool:
        normalized_values = [_normalize_text(value) for value in values if _normalize_text(value)]
        for phrase in normalized_phrases:
            for value in normalized_values:
                if phrase in value or value in phrase:
                    return True
        return False

    primary_hit = _bucket_has_match(primary_buckets)
    contextual_hit = _bucket_has_match(contextual_buckets)
    return primary_hit, contextual_hit


def _evaluate_reference_episode(
    anchor: Dict[str, Any],
    canonical_manifest: Dict[str, Any],
    projected_output: Any,
) -> Dict[str, Any]:
    scenes = canonical_manifest.get("scenes") if isinstance(canonical_manifest.get("scenes"), list) else []
    projected_scenes = _extract_projected_scenes(projected_output)
    projected_text = "\n".join(
        " ".join(
            str(value)
            for value in (
                scene.get("summary"),
                " ".join(scene.get("tags") or []),
                " ".join(scene.get("key_moments") or []),
            )
            if isinstance(value, str) and value.strip()
        )
        for scene in projected_scenes
        if isinstance(scene, dict)
    )
    normalized_projected = _normalize_text(projected_text)

    beat_results: List[Dict[str, Any]] = []
    salience_results: List[Dict[str, Any]] = []
    drift_candidates: Dict[str, List[int]] = defaultdict(list)

    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_index = int(scene.get("index", -1))
        surfaces = _collect_scene_surfaces(scene)
        for claim in surfaces["primary_tags"] + surfaces["primary_hypotheses"]:
            normalized_claim = _normalize_text(claim)
            if normalized_claim:
                drift_candidates[normalized_claim].append(scene_index)

    reference_terms: List[str] = []
    for beat in anchor.get("beats", []):
        if isinstance(beat, dict):
            reference_terms.append(str(beat.get("text") or ""))
            reference_terms.extend(str(alias) for alias in beat.get("aliases") or [])
    for concept in anchor.get("salient_concepts", []):
        if isinstance(concept, dict):
            reference_terms.append(str(concept.get("concept") or ""))
            reference_terms.extend(str(alias) for alias in concept.get("aliases") or [])
    normalized_reference_terms = {_normalize_text(term) for term in reference_terms if _normalize_text(term)}

    for beat in anchor.get("beats", []):
        if not isinstance(beat, dict):
            continue
        phrases = [str(beat.get("text") or "")] + [str(alias) for alias in beat.get("aliases") or []]
        matched_scenes: List[int] = []
        partial_scenes: List[int] = []
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            scene_index = int(scene.get("index", -1))
            primary_hit, contextual_hit = _surface_matches(phrases, _collect_scene_surfaces(scene))
            if primary_hit:
                matched_scenes.append(scene_index)
            elif contextual_hit:
                partial_scenes.append(scene_index)
        status = "covered" if matched_scenes else "partial" if partial_scenes else "missed"
        beat_results.append(
            {
                "id": beat.get("id"),
                "text": beat.get("text"),
                "importance": beat.get("importance", "supporting"),
                "status": status,
                "matched_scenes": matched_scenes,
                "partial_scenes": partial_scenes,
            }
        )

    for concept in anchor.get("salient_concepts", []):
        if not isinstance(concept, dict):
            continue
        phrases = [str(concept.get("concept") or "")] + [str(alias) for alias in concept.get("aliases") or []]
        matched_scenes: List[int] = []
        partial_scenes: List[int] = []
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            scene_index = int(scene.get("index", -1))
            primary_hit, contextual_hit = _surface_matches(phrases, _collect_scene_surfaces(scene))
            if concept.get("tier") == "contextual":
                if primary_hit or contextual_hit:
                    matched_scenes.append(scene_index)
            else:
                if primary_hit:
                    matched_scenes.append(scene_index)
                elif contextual_hit:
                    partial_scenes.append(scene_index)
        concept_text = str(concept.get("concept") or "")
        salience_results.append(
            {
                "concept": concept_text,
                "tier": concept.get("tier", "primary"),
                "weight": float(concept.get("weight", 1.0) or 1.0),
                "status": "aligned" if matched_scenes else "partial" if partial_scenes else "missed",
                "matched_scenes": matched_scenes,
                "partial_scenes": partial_scenes,
                "projected_visible": any(_normalize_text(phrase) in normalized_projected for phrase in phrases if _normalize_text(phrase)),
            }
        )

    drift_flags: List[Dict[str, Any]] = []
    for claim, scene_indices in sorted(drift_candidates.items()):
        if claim in normalized_reference_terms:
            continue
        drift_flags.append({"claim": claim, "scene_indices": scene_indices[:5]})

    core_beats = [item for item in beat_results if item["importance"] == "core"]
    core_covered = sum(1 for item in core_beats if item["status"] == "covered")
    core_partial = sum(1 for item in core_beats if item["status"] == "partial")
    salience_weight_total = sum(item["weight"] for item in salience_results)
    salience_weight_hit = sum(
        item["weight"]
        for item in salience_results
        if item["status"] == "aligned"
    ) + sum(
        item["weight"] * 0.5
        for item in salience_results
        if item["status"] == "partial"
    )

    projected_visible = sum(1 for item in salience_results if item["projected_visible"])

    return {
        "episode_code": anchor.get("episode_code"),
        "title": anchor.get("title"),
        "reference_summary": anchor.get("reference_summary"),
        "beat_results": beat_results,
        "salience_results": salience_results,
        "drift_flags": drift_flags[:12],
        "metrics": {
            "core_beats_total": len(core_beats),
            "core_beats_covered": core_covered,
            "core_beats_partial": core_partial,
            "salience_weight_total": round(salience_weight_total, 3),
            "salience_weight_hit": round(salience_weight_hit, 3),
            "projected_visible_concepts": projected_visible,
            "projected_total_concepts": len(salience_results),
        },
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, episode_results: List[Dict[str, Any]], summary_metrics: Dict[str, Any]) -> None:
    lines: List[str] = [
        "# Episode Reference Eval",
        "",
        f"- Episodes evaluated: {summary_metrics['episodes_evaluated']}",
        f"- Core beats covered: {summary_metrics['core_beats_covered']}/{summary_metrics['core_beats_total']}",
        f"- Salience weight hit: {summary_metrics['salience_weight_hit']}/{summary_metrics['salience_weight_total']}",
        "",
    ]
    for result in episode_results:
        metrics = result["metrics"]
        lines.extend(
            [
                f"## {result['episode_code']} - {result['title']}",
                "",
                f"- Core beats covered: {metrics['core_beats_covered']}/{metrics['core_beats_total']}",
                f"- Salience weight hit: {metrics['salience_weight_hit']}/{metrics['salience_weight_total']}",
                f"- Projected visible concepts: {metrics['projected_visible_concepts']}/{metrics['projected_total_concepts']}",
                "",
                "### Beat Coverage",
            ]
        )
        for beat in result["beat_results"]:
            lines.append(
                f"- `{beat['status']}` {beat['id']}: {beat['text']} "
                f"(matched={beat['matched_scenes']}, partial={beat['partial_scenes']})"
            )
        lines.append("")
        lines.append("### Drift Flags")
        if result["drift_flags"]:
            for flag in result["drift_flags"]:
                lines.append(f"- `{flag['claim']}` scenes={flag['scene_indices']}")
        else:
            lines.append("- None")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate witness outputs against local episode reference anchors.")
    parser.add_argument("--run-root", required=True, type=Path, help="Path to a witness run root.")
    parser.add_argument(
        "--reference-root",
        required=True,
        type=Path,
        help="Directory containing local *.reference.json anchor files.",
    )
    args = parser.parse_args()

    run_root = args.run_root.resolve()
    experiment_log_path = run_root / "experiment_log.json"
    if not experiment_log_path.is_file():
        raise FileNotFoundError(f"Experiment log not found: {experiment_log_path}")

    experiment_log = _read_json(experiment_log_path)
    processing_root = _resolve_processing_root(str(experiment_log.get("epoch") or ""))
    eval_root = run_root / "episode_reference_eval"
    eval_root.mkdir(parents=True, exist_ok=True)

    episode_results: List[Dict[str, Any]] = []
    for plan_item in experiment_log.get("plan", []):
        if not isinstance(plan_item, dict):
            continue
        episode_name = str(plan_item.get("episode") or "")
        episode_stem = Path(episode_name).stem
        episode_code = episode_stem.split(" ", 1)[0]
        anchor_matches = sorted(args.reference_root.glob(f"{episode_code}_*.reference.json"))
        if not anchor_matches:
            continue
        anchor = _read_json(anchor_matches[0])

        run_dir = Path(str(plan_item.get("run_dir") or ""))
        projected_output_path = run_dir / "output" / "scene_ingest_results.json"
        canonical_manifest_path = processing_root / episode_stem / "video" / "scene_manifest.json"

        if not projected_output_path.is_file() or not canonical_manifest_path.is_file():
            continue

        projected_output = _read_json(projected_output_path)
        canonical_manifest = _read_json(canonical_manifest_path)
        result = _evaluate_reference_episode(anchor, canonical_manifest, projected_output)
        episode_results.append(result)
        _write_json(eval_root / f"{episode_code}.reference_eval.json", result)

    summary_metrics = {
        "episodes_evaluated": len(episode_results),
        "core_beats_total": sum(item["metrics"]["core_beats_total"] for item in episode_results),
        "core_beats_covered": sum(item["metrics"]["core_beats_covered"] for item in episode_results),
        "salience_weight_total": round(sum(item["metrics"]["salience_weight_total"] for item in episode_results), 3),
        "salience_weight_hit": round(sum(item["metrics"]["salience_weight_hit"] for item in episode_results), 3),
    }

    _write_json(eval_root / "episode_reference_eval_metrics.json", summary_metrics)
    _write_markdown(eval_root / "episode_reference_eval_report.md", episode_results, summary_metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
