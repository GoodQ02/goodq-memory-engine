"""
GoodQ4All — Phase 2: Speaker Candidate Cluster Builder
=======================================================
Post-promotion identity enrichment tool. Does NOT modify the knowledge graph.

IMPORTANT: Speaker clusters are HYPOTHESIS ONLY.
PyAnnote speaker d-vectors are not available for this epoch. All cross-video
speaker linkages are derived from co-occurrence with face clusters (Phase 1)
and acoustic heuristics (speaking time, turn rate). These are weak signals.

Hard acceptance criterion:
  No speaker cluster becomes a person identity without explicit human
  confirmation in family_roster.yaml. The status field is always 'hypothesis'.

Usage:
    conda run -n goodq_core python scripts/identity/build_speaker_clusters.py \\
        --epoch-id epoch_2026_07_05_home_memory_clean_01 \\
        [--data-path L:/_DATA/GoodQ_Data/identity]

Output (all gitignored, written to data-path):
    speaker_clusters.json — hypothesis cluster manifest
"""

import argparse
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DEFAULT_EPOCH_ROOT = "L:/_DATA/GoodQ_Data/epochs"
DEFAULT_DATA_PATH  = "L:/_DATA/GoodQ_Data/identity"


def _epoch_dir(epoch_root: str, epoch_id: str) -> Path:
    p = Path(epoch_root) / epoch_id
    if not p.exists():
        raise FileNotFoundError(f"Epoch directory not found: {p}")
    return p


def load_diarization_stats(epoch_dir: Path) -> dict:
    """
    Reads all *_raw_diarization.json files and computes per-video,
    per-speaker acoustic statistics.

    Returns: {video_hash: {speaker_id: {total_seconds, turn_count, avg_duration, ...}}}
    """
    processing_dir = epoch_dir / "processing"
    stats: dict[str, dict[str, dict]] = {}

    for video_dir in sorted(processing_dir.iterdir()):
        audio_dir = video_dir / "audio"
        if not audio_dir.exists():
            continue
        video_hash = video_dir.name

        # Aggregate across all diarization files for this video
        speaker_data: dict[str, dict] = defaultdict(lambda: {
            "total_seconds": 0.0,
            "turn_count": 0,
            "durations": [],
        })

        for fname in sorted(audio_dir.iterdir()):
            if "raw_diarization" not in fname.name:
                continue
            try:
                with open(fname, encoding="utf-8") as f:
                    segments = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Could not read %s: %s", fname, e)
                continue
            if not isinstance(segments, list):
                continue
            for seg in segments:
                spk = seg.get("speaker", "unknown")
                duration = max(0.0, seg.get("end", 0.0) - seg.get("start", 0.0))
                speaker_data[spk]["total_seconds"] += duration
                speaker_data[spk]["turn_count"] += 1
                speaker_data[spk]["durations"].append(duration)

        for spk, data in speaker_data.items():
            durs = data["durations"]
            data["avg_duration"] = sum(durs) / len(durs) if durs else 0.0
            data["median_duration"] = sorted(durs)[len(durs) // 2] if durs else 0.0
            del data["durations"]  # don't store full list

        if speaker_data:
            stats[video_hash] = dict(speaker_data)

    log.info("Loaded diarization stats for %d videos", len(stats))
    return stats


def load_transcript_by_speaker(mem_db_path: Path) -> dict:
    """
    Returns {video_hash: {speaker: [transcript_text, ...]}} from memory.db.
    """
    conn = sqlite3.connect(str(mem_db_path))
    cur = conn.cursor()
    cur.execute(
        "SELECT video_hash, speaker, meta FROM segments "
        "WHERE speaker IS NOT NULL AND meta IS NOT NULL"
    )
    rows = cur.fetchall()
    conn.close()

    result: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for video_hash, speaker, meta_json in rows:
        try:
            meta = json.loads(meta_json)
        except (json.JSONDecodeError, TypeError):
            continue
        transcript = meta.get("transcript", "")
        if transcript and len(transcript.strip()) > 3:
            result[video_hash][speaker].append(transcript.strip())
    return result


def load_face_clusters(data_path: Path) -> dict:
    """
    Loads face_clusters.json if present. Returns cluster_id -> {video_hashes, timestamp_range}.
    """
    clusters_path = data_path / "face_clusters.json"
    if not clusters_path.exists():
        log.warning(
            "face_clusters.json not found at %s. "
            "Speaker-face co-occurrence analysis will be skipped. "
            "Run Phase 1 (build_face_clusters.py) first for better speaker hypotheses.",
            clusters_path,
        )
        return {}
    with open(clusters_path, encoding="utf-8") as f:
        manifest = json.load(f)
    return {c["cluster_id"]: c for c in manifest.get("clusters", [])}


def compute_cooccurrence(
    diar_stats: dict,
    face_clusters: dict,
) -> dict:
    """
    Builds a soft co-occurrence map: which speaker IDs from which videos
    appear in scenes that also contain labeled face clusters.

    Since we don't have precise scene-level timestamps here, we use video
    co-presence as the proxy: a speaker and a face cluster are "co-present"
    if they share the same video_hash.

    Returns: {video_hash: {speaker_id: [face_cluster_ids]}}
    """
    cooccurrence: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for cluster_id, cluster_info in face_clusters.items():
        for vh in cluster_info.get("video_hashes", []):
            if vh in diar_stats:
                for speaker_id in diar_stats[vh]:
                    cooccurrence[vh][speaker_id].append(cluster_id)
    return cooccurrence


def build_speaker_cluster_manifest(
    diar_stats: dict,
    cooccurrence: dict,
    transcript_data: dict,
    epoch_id: str,
) -> dict:
    """
    Produces hypothesis speaker clusters by ranking speakers across videos
    by total speaking time and co-occurrence with face clusters.

    Strategy:
    - For each unique speaking rank (most-prominent talker = rank 0),
      group the speaker from each video who holds that rank.
    - This is weak: the most-prominent talker may differ per video.
    - All produced clusters are labeled status='hypothesis'.
    """
    # Rank speakers per video by total speaking time
    per_video_ranked: dict[str, list] = {}
    for vh, speakers in diar_stats.items():
        ranked = sorted(speakers.items(), key=lambda x: -x[1]["total_seconds"])
        per_video_ranked[vh] = [spk for spk, _ in ranked]

    # Determine max speaker rank across all videos
    max_rank = max((len(v) for v in per_video_ranked.values()), default=0)

    clusters = []
    for rank in range(max_rank):
        per_video_assignments = {}
        total_speaking = 0.0
        face_cooc: list[str] = []
        sample_transcripts: list[str] = []

        for vh, ranked_speakers in per_video_ranked.items():
            if rank >= len(ranked_speakers):
                continue
            spk = ranked_speakers[rank]
            per_video_assignments[vh] = spk
            total_speaking += diar_stats[vh][spk]["total_seconds"]
            # Face co-occurrence
            fc = cooccurrence.get(vh, {}).get(spk, [])
            face_cooc.extend(fc)
            # Transcript sample
            txts = transcript_data.get(vh, {}).get(spk, [])
            if txts:
                sample_transcripts.append(txts[0][:120])

        if not per_video_assignments:
            continue

        unique_face_cooc = sorted(set(face_cooc))
        clusters.append({
            "cluster_id": f"spk_cluster_{rank}",
            "status": "hypothesis",
            "label": None,
            "confirmed": False,
            "method": "prominence_rank_heuristic",
            "note": (
                "Grouped by speaking prominence rank across videos. "
                "PyAnnote d-vectors not available. This is a weak hypothesis — "
                "the same rank does not guarantee the same person across videos."
            ),
            "videos_present": len(per_video_assignments),
            "per_video_assignments": per_video_assignments,
            "total_speaking_seconds": round(total_speaking, 2),
            "face_cluster_co_occurrences": unique_face_cooc,
            "confidence": "low",
            "transcript_samples": sample_transcripts[:3],
        })

    return {
        "epoch_id": epoch_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": "co_occurrence_heuristic",
        "note": (
            "PyAnnote speaker d-vectors not available for this epoch. "
            "All speaker cluster linkages are HYPOTHESIS ONLY. "
            "No speaker cluster may become a person identity without explicit "
            "human confirmation in family_roster.yaml."
        ),
        "cluster_count": len(clusters),
        "clusters": clusters,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GoodQ4All Phase 2: Speaker Candidate Cluster Builder"
    )
    parser.add_argument("--epoch-id", required=True)
    parser.add_argument("--epoch-root", default=DEFAULT_EPOCH_ROOT)
    parser.add_argument("--data-path", default=DEFAULT_DATA_PATH)
    args = parser.parse_args()

    data_path = Path(args.data_path)
    data_path.mkdir(parents=True, exist_ok=True)
    manifest_path = data_path / "speaker_clusters.json"

    log.info("=== GoodQ4All Phase 2: Speaker Candidate Cluster Builder ===")
    log.info("Epoch: %s", args.epoch_id)
    log.info("NOTE: PyAnnote d-vectors not available — using co-occurrence heuristics only")

    epoch_dir = _epoch_dir(args.epoch_root, args.epoch_id)
    mem_db = epoch_dir / "memory.db"
    if not mem_db.exists():
        log.error("memory.db not found at %s", mem_db)
        sys.exit(1)

    diar_stats = load_diarization_stats(epoch_dir)
    if not diar_stats:
        log.error("No diarization data found. Aborting.")
        sys.exit(1)

    transcript_data = load_transcript_by_speaker(mem_db)
    face_clusters   = load_face_clusters(data_path)

    cooccurrence = compute_cooccurrence(diar_stats, face_clusters)

    manifest = build_speaker_cluster_manifest(
        diar_stats, cooccurrence, transcript_data, args.epoch_id
    )

    log.info(
        "Result: %d hypothesis speaker clusters — writing to %s",
        manifest["cluster_count"], manifest_path,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log.info("=== Phase 2 complete ===")
    log.info(
        "Next step: review speaker_clusters.json, then map confirmed speakers "
        "to identities in family_roster.yaml. Speaker clusters are hypothesis-only "
        "until you manually confirm them in the roster."
    )


if __name__ == "__main__":
    main()
