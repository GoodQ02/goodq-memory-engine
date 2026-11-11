"""Bind standalone workers to the existing scene artifacts and staged UCF lifecycle."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave

from steps.common.atomic_io import atomic_write_json
from steps.common.memory import _make_id, compute_file_hash


def _audio_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
    except (wave.Error, EOFError):
        from steps.common.tool_resolver import ToolResolver
        probe = ToolResolver.resolve_tool("ffprobe")
        if not probe.get("found") or not probe.get("path"):
            raise RuntimeError("Cannot measure standalone audio duration: ffprobe unavailable")
        result = subprocess.run(
            [str(probe["path"]), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, check=True, timeout=60,
        )
        duration = float(json.loads(result.stdout)["format"]["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Standalone audio requires a positive measured duration")
    return duration


def prepare_source(cfg: dict, source: Path, source_kind: str) -> dict:
    """Retain exact bytes and bind canonical identity before any model worker runs."""
    if not source.is_file():
        raise FileNotFoundError(source)
    if source_kind not in {"image", "document", "audio"}:
        raise ValueError(f"Unsupported standalone source kind: {source_kind}")
    source_hash = compute_file_hash(str(source))
    root = Path(cfg["paths"]["processing"]).resolve() / source_hash
    root.mkdir(parents=True, exist_ok=True)
    retained = root / f"{source_hash}{source.suffix.lower()}"
    if retained.exists():
        if compute_file_hash(str(retained)) != source_hash:
            raise ValueError("Retained standalone source hash mismatch")
    elif source.resolve() != retained.resolve():
        shutil.copy2(source, retained)
    if compute_file_hash(str(retained)) != source_hash:
        raise ValueError("Standalone source copy failed hash verification")
    duration, width, height = 0.0, 0, 0
    if source_kind == "audio":
        duration = _audio_duration(retained)
    elif source_kind == "image":
        from PIL import Image
        with Image.open(retained) as image:
            width, height = image.size
    from api.utils.ingest_requests import resolve_ingest_original_name
    original_name = resolve_ingest_original_name(
        cfg["paths"].get("ingest_requests"), source.name, source_hash,
    )
    scene_id = _make_id("scene", [source_hash, "0.000", f"{duration:.3f}"])
    return {
        "source_kind": source_kind, "source_hash": source_hash,
        "video_hash": source_hash, "video_id": source_hash,
        "scene_id": scene_id, "scene_index": 0,
        "source_path": str(retained), "original_filename": original_name,
        "filename": original_name, "start": 0.0, "end": duration,
        "duration": duration, "width": width, "height": height,
        "scene": {"start": 0.0, "end": duration, "duration": duration},
    }


def merge_worker_result(item: dict, result: dict, step: str) -> None:
    """Keep raw worker evidence while preserving the source's measured identity."""
    item.setdefault("worker_results", {})[step] = dict(result)
    bound = {"source_kind", "source_hash", "video_hash", "video_id", "scene_id", "scene_index",
             "source_path", "original_filename", "filename", "start", "end", "duration", "width", "height", "scene", "worker_results"}
    item.update({key: value for key, value in result.items() if key not in bound})


def _log_document_embeddings(ledger, cfg: dict, item: dict, root: Path) -> None:
    """One static UCF frame owns every bounded passage vector for the document."""
    from steps.common.embedding_references import expand_embedding_references

    meta = item["audio_text_embed_meta"]
    payload = {key: meta[key] for key in (
        "embedding_chunks", "text_length", "text_sha256", "chunk_count", "chunk_token_limit",
    )}
    payload.update({"source_kind": "document", "embedding_source": "document_text",
                    "origin_modality": "document", "engine": meta.get("engine", "all-MiniLM-L6-v2")})
    raw_ref = root / "video" / f"{item['scene_id']}_raw_document_embeddings.json"
    frame = {
        "video_hash": item["video_hash"], "epoch_id": Path(cfg["paths"]["db_dir"]).name,
        "run_id": cfg["run"]["id"], "t_start": 0.0, "t_end": 0.0,
        "modality": "text", "worker_name": "text_embed",
        "model_tag": "sentence-transformers/all-MiniLM-L6-v2",
        "source_artifact_id": item["scene_id"], "raw_ref": str(raw_ref), "payload": payload,
        "promotion_status": "staged", "vector_key": None,
        "vector_backend": "qdrant" if meta.get("qdrant_committed") else "faiss",
        "vector_dim": 384, "vector_model_tag": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_collection": meta["vector_collection"],
    }
    refs = expand_embedding_references(frame, document_text=item["document_text"])
    atomic_write_json(raw_ref, payload)
    frame_id = ledger.log_frame(**frame)
    if meta.get("qdrant_committed"):
        from steps.common.qdrant_client import build_qdrant_client
        client = build_qdrant_client(cfg, dim=384, key="text")
        if client is None:
            raise RuntimeError("Document embeddings committed without a Qdrant client")
        response = client.session.post(
            f"{client.cfg.host}/collections/{client.cfg.collection}/points/payload?wait=true",
            json={"payload": {"ucf_frame_id": frame_id},
                  "points": [client._normalize_point_id(ref["vector_key"]) for ref in refs]},
            timeout=15,
        )
        response.raise_for_status()


def persist_result(cfg: dict, item: dict) -> None:
    """Publish artifacts and staged evidence; promotion remains a separate action."""
    from cli.run_ingestion import _log_audio_to_ucf_ledger, _log_visual_to_ucf_ledger
    from scripts.ucf.ucf_ledger import UCFLedgerClient
    from steps.video.cross_modal_harmonizer import (
        _AUDIO_EMOTION_PROMOTION_THRESHOLD, _build_entity_channels,
        _rank_audio_emotion_scores, _rank_text_emotions, _resolve_audio_emotion,
        _resolve_audio_sentiment, _resolve_scene_time_hints,
    )

    source = Path(item["source_path"])
    root = source.parent
    source_hash, scene_id = item["video_hash"], item["scene_id"]
    if compute_file_hash(str(source)) != source_hash:
        raise ValueError("Standalone source changed during processing")
    kind = item["source_kind"]
    if kind == "document" and (item.get("audio_text_embed_meta") or {}).get("status") == "error":
        raise RuntimeError("Document text embedding failed: " + str(item["audio_text_embed_meta"].get("error", "unknown error")))
    db_dir = Path(cfg["paths"]["db_dir"])
    epoch_id = db_dir.name
    run_id = cfg["run"]["id"]
    raw_ref = root / "raw_result.json"
    atomic_write_json(raw_ref, item)
    cfg_path = root / "resolved_config.json"
    atomic_write_json(cfg_path, cfg)
    scene = {
        "scene_id": scene_id, "video_id": source_hash, "index": 0,
        "start": 0.0, "end": item["end"], "duration": item["duration"],
        "source_kind": kind, "source_path": str(source),
        "original_filename": item["original_filename"],
    }
    segment = {
        **scene, "frame_paths": [str(source)] if kind == "image" else [],
        "has_audio": kind == "audio", "has_transcript": bool(item.get("transcript")) if kind == "audio" else False,
    }
    sentiment, sentiment_label, sentiment_score = _resolve_audio_sentiment(item)
    segment.update({
        "sentiment": sentiment, "sentiment_label": sentiment_label, "sentiment_score": sentiment_score,
        "sentiment_meta": item.get("sentiment_meta"), "text_emotion_ranking": _rank_text_emotions(item.get("emotions")),
        "text_emotion_meta": item.get("emotion_meta"), "tags": item.get("tags", []),
        "tag_details": item.get("tag_details", []),
        "entities": [{**entity, "source_modalities": ["audio" if kind == "audio" else "text"]}
                     for entity in item.get("ner_entities", []) if isinstance(entity, dict)],
    })
    if kind == "image":
        scene["keyframe"] = {**item, "path": str(source)}
        segment.update({key: item[key] for key in (
            "ocr_text", "ocr_meta", "ocr_observations", "faces", "tags", "caption_meta", "detect_meta",
        ) if key in item})
        segment["time_hints"] = _resolve_scene_time_hints(item)
        segment["visual_caption"] = item.get("caption")
        segment["detected_objects"] = item.get("objects") or []
        segment["objects"] = [str(obj["label"]) for obj in segment["detected_objects"]
                              if isinstance(obj, dict) and obj.get("label")]
        segment["representative_frame"] = str(source)
    elif kind == "audio":
        from cli.run_ingestion import _extract_speaker_ids
        scene["audio"] = {**item, "path": str(source)}
        segment.update({key: item[key] for key in (
            "transcript", "speakers", "speaker_segments", "tags", "tag_details", "clap_meta",
            "transcript_meta", "transcript_outcome", "transcript_outcome_reason",
            "sentiment_meta", "speaker_voice_signature_meta", "diarization_status", "diarization_error",
            "emotion_status", "emotion_error", "emotion_note", "diarization_note",
            "audio_emotion_meta", "music_events", "metadata_time_hints",
            "emotion_segments", "emotion_input", "sound_events", "sound_event_meta",
            "audio_evidence", "music_events_meta", "time_hints_meta",
        ) if key in item})
        segment["full_transcript"] = item.get("transcript", "")
        segment["audio_path"] = str(source)
        segment["speaker_ids"] = _extract_speaker_ids(item)
        segment["speaker_count"] = item.get("speaker_count", len(segment["speaker_ids"]))
        segment["speaker_voice_signature_count"] = len(item.get("speaker_voice_signatures") or [])
        emotion, scores = _resolve_audio_emotion(item)
        ranking = _rank_audio_emotion_scores(scores, promoted_label=emotion)
        segment.update({
            "audio_emotion": emotion, "audio_emotion_scores": scores, "audio_emotion_ranking": ranking,
            "audio_emotion_top_candidate": ranking[0] if ranking else None,
            "audio_emotion_promotion_threshold": _AUDIO_EMOTION_PROMOTION_THRESHOLD,
            "time_hints": _resolve_scene_time_hints(item),
        })
        # Transcript entities are mentions, never evidence of visible identity.
        channels = _build_entity_channels(segment["entities"])
        for key in ("dialogue_mentioned_entities", "mentioned_people", "dialogue_topics"):
            segment[key] = channels[key]
    else:
        for key in ("document_text", "document_meta"):
            scene[key] = item.get(key)
            segment[key] = item.get(key)
    common = {
        "video_id": source_hash, "video_hash": source_hash,
        "video_path": str(source), "source_path": str(source),
        "source_kind": kind, "original_filename": item["original_filename"],
        "duration": item["duration"],
    }
    manifest = {**common, "phase5_complete": True, "total_scenes": 1, "scenes": [scene]}
    temporal = {**common, "segments": [segment], "total_segments": 1}
    (db_dir / "ucf").mkdir(parents=True, exist_ok=True)
    ledger = UCFLedgerClient(str(db_dir / "ucf" / "ucf_ledger.db"))
    try:
        ledger.init_schema()
        ledger.register_media(source_hash, str(source), item["duration"], 0.0, item["width"], item["height"])
        artifact_dir = root / ("audio" if kind == "audio" else "video")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if kind == "audio":
            if item.get("audio_evidence") is not None:
                from steps.audio.recording_ingestion import ucf_transcript_segments
                raw_tx_rows = ucf_transcript_segments(item["audio_evidence"])
            else:
                raw_tx_rows = item.get("segments", [])
            atomic_write_json(artifact_dir / f"{scene_id}_raw_transcript.json", raw_tx_rows)
            atomic_write_json(artifact_dir / f"{scene_id}_raw_diarization.json", item.get("speaker_segments", []))
            _log_audio_to_ucf_ledger(cfg_path, source_hash, scene_id, scene, artifact_dir, item, strict=True)
        elif kind == "image":
            _log_visual_to_ucf_ledger(cfg_path, source_hash, scene_id, scene, artifact_dir, item, strict=True)
        elif (item.get("audio_text_embed_meta") or {}).get("embedding_chunks") is not None:
            _log_document_embeddings(ledger, cfg, item, root)
        else:
            _log_audio_to_ucf_ledger(cfg_path, source_hash, scene_id, scene, artifact_dir, item, strict=True)
        atomic_write_json(root / "video" / "scene_manifest.json", manifest)
        anchor = {key: item[key] for key in (
            "source_kind", "source_hash", "source_path", "original_filename", "scene_id",
            "scene_index", "start", "end", "duration", "width", "height",
        )}
        if kind == "document":
            anchor["document_text"] = item.get("document_text", "")
        ledger.log_frame(
            video_hash=source_hash, epoch_id=epoch_id, run_id=run_id,
            t_start=0.0, t_end=item["end"],
            modality={"image": "multimodal", "document": "text", "audio": "audio"}[kind],
            worker_name="standalone_source", model_tag="source_sha256",
            source_artifact_id=scene_id, raw_ref=str(raw_ref), payload=anchor,
            promotion_status="staged",
        )
        atomic_write_json(root / "temporal_index.json", temporal)
    finally:
        ledger.close()


def preserve_failure(item: dict, error: Exception) -> None:
    """Retain the last aggregate and attributable failure without claiming completion."""
    from steps.common.worker_launch import WorkerResultError

    root = Path(item["source_path"]).parent
    failed_item = item
    if isinstance(error, WorkerResultError) and error.step_name and isinstance(error.outputs, dict):
        failed_item = copy.deepcopy(item)
        merge_worker_result(failed_item, error.outputs, error.step_name)
    atomic_write_json(root / "failed_result.json", {
        "status": "error", "error": str(error), "error_type": type(error).__name__, "item": failed_item,
    })
