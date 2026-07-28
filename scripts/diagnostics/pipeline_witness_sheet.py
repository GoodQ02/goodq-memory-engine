"""Verify and publish a compact, evidence-backed GoodQ pipeline witness sheet.

The witness is intentionally epoch-isolated.  It must therefore prove durable
FAISS/Qdrant/UCF/ledger outputs without claiming that its non-authoritative
SQLite compatibility database was populated.
"""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _qdrant_collection(url: str, name: str) -> dict[str, Any]:
    request = urllib.request.Request(f"{url.rstrip('/')}/collections/{name}")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))["result"]


def _table_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {table: int(connection.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]) for table in tables}
    finally:
        connection.close()


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _completed_steps(stdout_path: Path) -> collections.Counter[str]:
    completed: collections.Counter[str] = collections.Counter()
    for line in stdout_path.read_text(encoding="utf-8", errors="replace").splitlines():
        event = _read_json_line(line)
        if not isinstance(event, dict) or event.get("event") != "step_end":
            continue
        step = event.get("step")
        if isinstance(step, str) and step:
            completed[step] += 1
    return completed


def _run_id(stdout_path: Path) -> str | None:
    for line in stdout_path.read_text(encoding="utf-8", errors="replace").splitlines():
        event = _read_json_line(line)
        if isinstance(event, dict) and isinstance(event.get("run_id"), str):
            return event["run_id"]
    return None


def build_sheet(
    report_root: Path,
    epoch_root: Path,
    qdrant_url: str,
    preflight_path: Path | None = None,
) -> tuple[str, list[str]]:
    results_path = report_root / "scene_ingest_results.json"
    result_items = _read_json(results_path)
    errors: list[str] = []
    _require(isinstance(result_items, list) and len(result_items) == 1, "result envelope must contain one video", errors)
    result = result_items[0] if isinstance(result_items, list) and result_items else {}
    stdout_path = report_root / "stdout.log"
    completed_steps = _completed_steps(stdout_path)
    run_id = _run_id(stdout_path)
    _require(completed_steps.get("pipeline.ingestion") == 1, "pipeline completion receipt missing", errors)
    _require(run_id is not None, "structured run ID missing from stdout log", errors)
    _require(
        result.get("knowledge_graph_status") == "not_applicable_isolated_epoch",
        f"isolated witness has incorrect graph status: {result.get('knowledge_graph_status')!r}",
        errors,
    )
    scenes = result.get("scenes") if isinstance(result, dict) else None
    _require(isinstance(scenes, list) and len(scenes) == 2, "witness must contain exactly two scenes", errors)
    scenes = scenes if isinstance(scenes, list) else []
    indices = [scene.get("index") for scene in scenes]
    _require(indices == [0, 1], f"witness scene indices must be [0, 1], got {indices!r}", errors)

    temporal_path = Path(str(result.get("temporal_index_path") or ""))
    temporal = _read_json(temporal_path)
    committed = temporal.get("committed_modalities") or {}
    _require(temporal.get("total_scenes") == 2, "temporal index must contain exactly two scenes", errors)
    _require(committed == {
        "available": True,
        "audio": True,
        "audio_transcript": True,
        "audio_scene_count": 2,
        "transcript_scene_count": 2,
    }, f"unexpected committed temporal projection: {committed!r}", errors)

    ledger_path = epoch_root / "logs" / "memory_commit_events.jsonl"
    events = [_read_json_line(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    events = [event for event in events if isinstance(event, dict)]
    event_counts = collections.Counter((event.get("modality"), event.get("attempted"), event.get("committed")) for event in events)
    _require(not any("sqlite_embeddings" in (event.get("targets") or {}) for event in events), "isolated ledger must not claim sqlite embeddings", errors)

    per_scene: list[dict[str, Any]] = []
    for scene in scenes:
        audio = scene.get("audio") or {}
        keyframe = scene.get("keyframe") or {}
        clap = audio.get("clap_meta") or {}
        signature = audio.get("speaker_voice_signature_meta") or {}
        statuses = {
            "audio": audio.get("status"),
            "transcript": (audio.get("transcript_meta") or {}).get("status"),
            "diarization": audio.get("diarization_status"),
            "signature": signature.get("status"),
            "clap": clap.get("status"),
            "ocr": (keyframe.get("ocr_meta") or {}).get("status"),
            "caption": (keyframe.get("caption_meta") or {}).get("status"),
            "faces": (keyframe.get("faces_meta") or {}).get("status"),
            "dino": (keyframe.get("dino_meta") or {}).get("status"),
            "clip": (keyframe.get("clip_meta") or {}).get("status"),
            "frame_text": (keyframe.get("frame_text_embed_meta") or {}).get("status"),
        }
        _require(scene.get("audio_backend_effective") == "wsl" and scene.get("audio_backend_downgraded") is False, f"scene {scene.get('index')} did not retain strict WSL audio", errors)
        _require(all(status == "ok" or status == "success" for status in statuses.values()), f"scene {scene.get('index')} has non-success stage statuses: {statuses!r}", errors)
        _require(int(signature.get("emitted") or 0) > 0, f"scene {scene.get('index')} has no Wav2Vec signature", errors)
        _require(clap.get("qdrant_committed") is True and clap.get("faiss_committed") is True, f"scene {scene.get('index')} lacks committed CLAP proof", errors)
        _require(clap.get("sqlite_embeddings_state") == "not_applicable_isolated_epoch", f"scene {scene.get('index')} has incorrect isolated SQLite state", errors)
        per_scene.append({"index": scene.get("index"), "id": scene.get("scene_id"), "statuses": statuses, "signatures": signature.get("emitted")})

    collections_expected = {
        f"goodq_audio_{epoch_root.name}": 2,
        f"goodq_clip_{epoch_root.name}": 4,
        f"goodq_dino_{epoch_root.name}": 4,
        f"goodq_text_{epoch_root.name}": 6,
    }
    collection_rows = []
    for name, expected_points in collections_expected.items():
        collection = _qdrant_collection(qdrant_url, name)
        points = collection.get("points_count")
        _require(collection.get("status") == "green" and points == expected_points, f"Qdrant {name} expected green/{expected_points}, got {collection.get('status')}/{points}", errors)
        collection_rows.append((name, points, collection.get("status")))

    ucf_counts = _table_counts(epoch_root / "ucf" / "ucf_ledger.db")
    _require(ucf_counts.get("media_sources") == 1, f"UCF media source count must be 1, got {ucf_counts!r}", errors)
    _require(ucf_counts.get("context_frames", 0) > 0, f"UCF must contain context frames, got {ucf_counts!r}", errors)

    faiss_files = sorted(str(path.relative_to(epoch_root / "faiss")) for path in (epoch_root / "faiss").rglob("*.index"))
    _require(len(faiss_files) >= 4, f"expected audio, clip, dino, and text FAISS indexes; got {faiss_files!r}", errors)
    memory_counts = _table_counts(epoch_root / "memory.db")

    preflight: dict[str, Any] | None = None
    if preflight_path is not None:
        preflight = _read_json(preflight_path)
        _require(preflight.get("ready") is True, "WSL audio preflight is not ready", errors)
        _require(preflight.get("diarization_ready") is True, "WSL diarization is not ready", errors)
        _require(preflight.get("wav2vec_enrichment_ready") is True, "WSL Wav2Vec enrichment is not ready", errors)

    rows = [
        ("Scene detection + selected scope", "input file + --scene-indices 0,1", "two canonical scene IDs", "scene manifest + temporal index"),
        ("Vision", "keyframe extraction then OCR/caption/faces/object/CLIP/DINO", "all per-scene statuses ok", "manifest, FAISS, Qdrant"),
        ("Strict audio", "GOODQ_REQUIRE_WSL_AUDIO=1", "WSL transcript + diarization + signatures", "audio artifacts + canonical manifest"),
        ("Audio model preflight", "configured Ubuntu WSL worker", "CUDA, Faster-Whisper, Pyannote, Wav2Vec, FFmpeg ready", "preflight receipt"),
        ("Audio/text vectors", "CLAP and text embedding stages", "two audio; transcript and frame text commits", "FAISS, Qdrant, epoch ledger"),
        ("Temporal fusion", "cross_modal_harmonization after scene processing", "2-scene index and committed modality projection", "canonical temporal_index.json"),
        ("Knowledge graph", "incremental graph writer", "explicitly not applicable in isolated witness", "result receipt"),
        ("Provenance", "UCF context-frame registration", "one media source and context frames", "ucf/ucf_ledger.db"),
        ("Isolation", "epoch-local run contract", "SQLite explicitly not applicable", "receipt metadata and JSONL ledger"),
    ]
    table = "\n".join(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows)
    scene_lines = "\n".join(f"| {row['index']} | `{row['id']}` | WSL | {row['signatures']} | ok |" for row in per_scene)
    qdrant_lines = "\n".join(f"| `{name}` | {points} | {status} |" for name, points, status in collection_rows)
    step_lines = "\n".join(
        f"| `{step}` | {count} |"
        for step, count in sorted(completed_steps.items())
        if step.startswith("step.") or step.startswith("pipeline.")
    )
    status = "PASS" if not errors else "FAIL"
    error_section = "None." if not errors else "\n".join(f"- {error}" for error in errors)
    preflight_section = "Not supplied." if preflight is None else (
        f"`ready={preflight.get('ready')}`, `gpu_ready={preflight.get('gpu_ready')}`, "
        f"`diarization_ready={preflight.get('diarization_ready')}`, "
        f"`wav2vec_enrichment_ready={preflight.get('wav2vec_enrichment_ready')}`, "
        f"`torchcodec_ready={preflight.get('torchcodec_ready')}`. "
        "TorchCodec is reported as unavailable and is not selected by this FFmpeg-based pipeline."
    )
    text = f"""# GoodQ Two-Scene Pipeline Witness — {status}

**Run:** `{run_id or 'unavailable'}`
**Source:** `{result.get('video_name')}`  
**Epoch:** `{epoch_root.name}`  
**Scope:** exactly scene indices `[0, 1]`; isolated from July production authority.

## End-to-end contract

| When / stage | How it fires | What it proves | Where it persists |
|---|---|---|---|
{table}

## Scene receipts

| Index | Scene ID | Audio backend | Wav2Vec signatures | Core stage status |
|---:|---|---|---:|---|
{scene_lines}

## Store receipts

| Qdrant collection | Points | Status |
|---|---:|---|
{qdrant_lines}

- FAISS indexes: {', '.join(f'`{path}`' for path in faiss_files)}
- UCF counts: `{json.dumps(ucf_counts, sort_keys=True)}`
- Epoch `memory.db` counts: `{json.dumps(memory_counts, sort_keys=True)}`. This is expected to have no scene/vector rows because `ingestion_isolation=true`; the ledger, FAISS, Qdrant, UCF, and artifacts are the run's authoritative persistence surfaces.
- Commit ledger: `{json.dumps({f'{modality}/{attempted}/{committed}': count for (modality, attempted, committed), count in sorted(event_counts.items())}, sort_keys=True)}`
- Temporal committed modalities: `{json.dumps(committed, sort_keys=True)}`
- WSL audio preflight: {preflight_section}

## Executed-stage receipt

The following is parsed from the run's structured `step_end` events. Repeated
per-scene stages have a count of two; this is execution evidence, not merely a
configured capability list.

| Step | Completed events |
|---|---:|
{step_lines}

## Verification result

{error_section}
"""
    return text, errors


def _read_json_line(line: str) -> Any:
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--epoch-root", type=Path, required=True)
    parser.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    parser.add_argument("--preflight-json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sheet, errors = build_sheet(args.report_root, args.epoch_root, args.qdrant_url, args.preflight_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(sheet, encoding="utf-8")
    print(args.output)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
