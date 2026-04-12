from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import load_configs
from steps.common.context_analyzer_llm import analyze_scene_context_llm
from steps.video.cross_modal_harmonizer import _derive_scene_context_epistemic


def _load_manifest(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_scene(manifest: Dict[str, Any], scene_index: int) -> Dict[str, Any]:
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list):
        raise ValueError("Manifest does not contain a scenes list")
    for scene in scenes:
        if isinstance(scene, dict) and int(scene.get("index", -1)) == scene_index:
            return scene
    raise ValueError(f"Scene index {scene_index} not found in manifest")


def _build_emotions_payload(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    emotion_scores = scene.get("audio_emotion_scores")
    if isinstance(emotion_scores, dict):
        sorted_emotions = sorted(
            (
                (str(label).strip().lower(), score)
                for label, score in emotion_scores.items()
                if str(label).strip()
            ),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        for label, score in sorted_emotions[:3]:
            try:
                payload.append({"label": label, "score": float(score)})
            except (TypeError, ValueError):
                continue
        return payload

    fallback_label = scene.get("audio_emotion")
    if isinstance(fallback_label, str) and fallback_label.strip():
        payload.append({"label": fallback_label.strip().lower(), "score": 1.0})
    return payload


def _build_scene_meta(scene: Dict[str, Any]) -> Dict[str, Any]:
    keyframe = scene.get("keyframe") if isinstance(scene.get("keyframe"), dict) else {}
    audio = scene.get("audio") if isinstance(scene.get("audio"), dict) else {}
    objects = keyframe.get("objects")
    if not isinstance(objects, list):
        objects = []

    transcript = (
        audio.get("transcript")
        or audio.get("full_text")
        or scene.get("transcript")
        or ""
    )
    speakers = scene.get("speaker_ids")
    if not isinstance(speakers, list):
        speakers = []

    return {
        "index": scene.get("index"),
        "start": scene.get("start"),
        "end": scene.get("end"),
        "caption": scene.get("caption") or keyframe.get("caption") or "",
        "transcript": str(transcript or "").strip(),
        "objects": objects,
        "face_count": int(scene.get("visible_face_count") or 0),
        "emotions": _build_emotions_payload(scene),
        "speakers": speakers,
    }


def _print_json(label: str, payload: Any) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run scene_context_llm on a single scene for fast, local debugging.",
    )
    parser.add_argument("--scene-manifest", required=True, help="Absolute path to scene_manifest.json")
    parser.add_argument("--scene-index", required=True, type=int, help="Scene index to analyze")
    parser.add_argument(
        "--show-existing",
        action="store_true",
        help="Print the currently persisted scene_context_llm and scene_context_epistemic payloads",
    )
    args = parser.parse_args()

    manifest_path = Path(args.scene_manifest)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Scene manifest not found: {manifest_path}")

    manifest = _load_manifest(manifest_path)
    scene = _select_scene(manifest, args.scene_index)
    scene_meta = _build_scene_meta(scene)
    cfg = load_configs()

    if args.show_existing:
        _print_json("EXISTING scene_context_llm", scene.get("scene_context_llm"))
        _print_json("EXISTING scene_context_epistemic", scene.get("scene_context_epistemic"))

    _print_json("SCENE META", scene_meta)

    regenerated = analyze_scene_context_llm(scene_meta, cfg)
    epistemic = _derive_scene_context_epistemic(scene_meta, regenerated) if regenerated else None

    _print_json("REGENERATED scene_context_llm", regenerated)
    _print_json("REGENERATED scene_context_epistemic", epistemic)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
