"""
GoodQ4All — Phase 1: Face Candidate Cluster Builder
=====================================================
Post-promotion identity enrichment tool. Does NOT modify the knowledge graph.
Output is a candidate cluster manifest and an HTML review sheet.

IMPORTANT: Face clusters are CANDIDATE GROUPINGS ONLY.
VHS-era faces are low-resolution, motion-blurred, angled, and variably lit.
DBSCAN with eps=0.4 is a starting hypothesis. No cluster is an identity until
a human labels it in family_roster.yaml.

Usage:
    conda run -n goodq_core python scripts/identity/build_face_clusters.py \\
        --epoch-id epoch_public_example \\
        [--eps 0.4] \\
        [--min-samples 2] \\
        [--data-path L:/_DATA/GoodQ_Data/identity]

Output (all gitignored, written to data-path):
    face_clusters.json          — cluster manifest
    reports/face_cluster_sheet.html — browser-viewable labeling sheet

Requires: scikit-learn (confirmed available in goodq_core 1.7.2)
"""

import argparse
import base64
import hashlib
import io
import json
import logging
import math
import os
import re
import sqlite3
import sys
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

# The API invokes this file directly; resolve shared product code from its checkout.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Config defaults ────────────────────────────────────────────────────────────
DEFAULT_EPOCH_ROOT = "L:/_DATA/GoodQ_Data/epochs"
DEFAULT_DATA_PATH  = "L:/_DATA/GoodQ_Data/identity"
DEFAULT_EPS        = 0.4
DEFAULT_MIN_SAMPLES = 2
_JOB_ID_RE = re.compile(r"^job_[0-9a-f]{32}$")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _epoch_dir(epoch_root: str, epoch_id: str) -> Path:
    p = Path(epoch_root) / epoch_id
    if not p.exists():
        raise FileNotFoundError(f"Epoch directory not found: {p}")
    return p


def _start_gate_job_id(value: str) -> str:
    if not _JOB_ID_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("invalid start-gate job ID")
    return value


def _wait_for_start_gate(job_id: str) -> bool:
    expected = f"START {job_id}".encode("ascii")
    binary_stdin = getattr(sys.stdin, "buffer", None)
    if binary_stdin is not None:
        marker = binary_stdin.readline()
        return marker in {expected + b"\n", expected + b"\r\n"}
    marker = sys.stdin.readline()
    return marker in {
        expected.decode("ascii") + "\n",
        expected.decode("ascii") + "\r\n",
    }


def _ucf_db(epoch_dir: Path) -> Path:
    p = epoch_dir / "ucf" / "ucf_ledger.db"
    if not p.exists():
        raise FileNotFoundError(f"UCF ledger not found: {p}")
    return p


def load_face_ucf_provenance(ucf_db_path: Path) -> dict:
    """Read every promoted face row in this epoch, without modifying the ledger."""
    with closing(sqlite3.connect(f"{ucf_db_path.resolve().as_uri()}?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT frame_id,video_hash,raw_ref,t_start,payload,payload_hash,model_tag,source_artifact_id "
            "FROM context_frames WHERE worker_name='face_embed' AND promotion_status='promoted' "
            "AND epoch_id=? ORDER BY frame_id", (ucf_db_path.parent.parent.name,),
        ).fetchall()
    provenance = defaultdict(list)
    for row in rows:
        record = dict(row)
        payload = json.loads(record["payload"])
        if not isinstance(payload, dict):
            raise ValueError("Face UCF payload must be an object")
        if record["payload_hash"] and hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest() != record["payload_hash"]:
            raise ValueError("Face UCF payload hash mismatch")
        if not record["raw_ref"]:
            raise ValueError("Promoted face row has no raw reference")
        record["payload"] = payload
        provenance[os.path.normcase(str(Path(record["raw_ref"]).resolve()))].append(record)
    log.info("Loaded %d promoted face_embed UCF frames", len(rows))
    return dict(provenance)


def _face_authorities(rows: list, face_count: int) -> dict:
    """Only explicit image aggregates may authorize multiple unindexed faces."""
    result = {}
    for row in rows:
        payload = row["payload"]
        if "face_index" in payload:
            index = payload["face_index"]
            if type(index) is not int or not 0 <= index < face_count:
                raise ValueError("Invalid face_index in promoted UCF row")
            indices = [index]
        elif payload.get("source_kind") == "image" and type(payload.get("face_count")) is int:
            if len(rows) != 1 or payload["face_count"] != face_count:
                raise ValueError("Ambiguous or inconsistent image face_count authority")
            indices = range(face_count)
        elif len(rows) == 1 and face_count == 1 and "face_count" not in payload:
            indices = [0]  # Unambiguous historical single-face artifact.
        else:
            raise ValueError("Ambiguous missing face_index authority")
        for index in indices:
            if index in result:
                raise ValueError("Ambiguous duplicate face_index authority")
            result[index] = row
    return result


def _face_image(epoch_dir: Path, raw_path: Path, rows: list, *, manifest_cache: dict | None = None) -> tuple[Path, float | None]:
    """Resolve the image actually embedded, rather than a different scene sample."""
    from lib.face_observation import resolve_sampled_face
    sampled = resolve_sampled_face(epoch_dir, raw_path, rows, manifest_cache=manifest_cache)
    if sampled is not None:
        return sampled
    source_ids = {row["source_artifact_id"] for row in rows}
    hashes = {row["video_hash"] for row in rows}
    if len(source_ids) != 1 or len(hashes) != 1:
        raise ValueError("Face raw reference has conflicting source authority")
    processing_root = (epoch_dir / "processing").resolve()
    media_root = processing_root / raw_path.relative_to(processing_root).parts[0]
    manifest_path = raw_path.parent.parent / "scene_manifest.json"
    if not manifest_path.resolve().is_relative_to(processing_root):
        raise ValueError("Face manifest escapes the selected epoch")
    if not manifest_path.exists():
        image = raw_path.with_name(raw_path.name.replace("_raw_faces.json", ".jpg"))
        timestamp = next((row["t_start"] for row in rows if row["payload"].get("face_index", 0) == 0), None)
    else:
        if manifest_cache is None:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            if manifest_path not in manifest_cache:
                manifest_cache[manifest_path] = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = manifest_cache[manifest_path]
        declared_hash = manifest.get("video_hash", manifest.get("video_id"))
        if declared_hash and declared_hash not in hashes:
            raise ValueError("Face manifest video identity mismatch")
        if manifest.get("epoch_id", epoch_dir.name) != epoch_dir.name:
            raise ValueError("Face manifest epoch mismatch")
        matches = [scene for scene in manifest.get("scenes", [])
                   if (scene.get("scene_id") or scene.get("id")) in source_ids]
        if len(matches) != 1:
            raise ValueError("Face manifest scene authority is missing or ambiguous")
        keyframe = matches[0].get("keyframe") or {}
        path = keyframe.get("path") if isinstance(keyframe, dict) else keyframe
        if not isinstance(path, str) or not path:
            raise ValueError("Face manifest keyframe path is missing")
        image = Path(path)
        if not image.is_absolute():
            image = manifest_path.parent / image
        timestamp = keyframe.get("timestamp") if isinstance(keyframe, dict) else None
        if timestamp is not None and (type(timestamp) not in (int, float) or not math.isfinite(timestamp)):
            raise ValueError("Face manifest keyframe timestamp is invalid")
        if timestamp is not None:
            scene = matches[0]
            start, end = scene.get("start"), scene.get("end")
            if any(type(value) not in (int, float) or not math.isfinite(value) for value in (start, end)) or not start <= timestamp <= end:
                raise ValueError("Face manifest timestamp is outside its scene")
            for row in rows:
                index = row["payload"].get("face_index", 0)
                expected = timestamp + (0.001 * index if row["payload"].get("source_kind") != "image" else 0)
                if abs(row["t_start"] - expected) > 0.00051:
                    raise ValueError("Face manifest timestamp disagrees with UCF authority")
    image = image.resolve()
    if not image.is_relative_to(processing_root):
        raise ValueError("Face image escapes the selected processing root")
    if not image.is_relative_to(media_root):
        raise ValueError("Face image escapes its source media directory")
    return image, timestamp


def _bbox_coordinates(bbox) -> tuple | None:
    if isinstance(bbox, dict):
        bbox = [bbox.get(key, bbox.get(index, bbox.get(str(index))))
                for index, key in enumerate(("left", "top", "right", "bottom"))]
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or any(
        type(value) not in (int, float) or not math.isfinite(value) for value in bbox
    ):
        return None
    return tuple(bbox)


def collect_face_detections(epoch_dir: Path, provenance: dict) -> list:
    """Join each raw detection to its exact promoted authority and source image."""
    processing_dir = (epoch_dir / "processing").resolve()
    detections = []
    manifest_cache: dict[Path, dict] = {}
    for raw_ref, rows in sorted(provenance.items()):
        fname = Path(raw_ref).resolve()
        if not fname.is_relative_to(processing_dir):
            raise ValueError("Face raw reference escapes selected processing root")
        faces = json.loads(fname.read_text(encoding="utf-8"))
        if not isinstance(faces, list):
            raise ValueError("Face raw artifact must be a list")
        authorities = _face_authorities(rows, len(faces))
        image, timestamp = _face_image(epoch_dir, fname, rows, manifest_cache=manifest_cache)
        for face_idx, prov in sorted(authorities.items()):
            face = faces[face_idx]
            payload = prov["payload"]
            # An explicit image aggregate seals only its first detection's box.
            # Indexed video rows and historical single-face rows seal their own.
            aggregate = payload.get("source_kind") == "image" and "face_index" not in payload
            box_keys = ("x1", "y1", "x2", "y2")
            if (not aggregate or face_idx == 0) and any(key in payload for key in box_keys):
                sealed_box = _bbox_coordinates([payload.get(key) for key in box_keys])
                raw_box = _bbox_coordinates(face.get("bbox"))
                if sealed_box is None or raw_box is None or any(abs(a - b) > 1e-6 for a, b in zip(sealed_box, raw_box)):
                    raise ValueError("Face bbox disagrees with promoted UCF authority")
            enc = face.get("encoding")
            if not isinstance(enc, list) or not enc or any(type(v) not in (int, float) or not math.isfinite(v) for v in enc) or not any(enc):
                raise ValueError("Face embedding must be a nonzero finite vector")
            if face.get("embedding_dimension", len(enc)) != len(enc):
                raise ValueError("Face embedding dimension metadata mismatch")
            engines = {str(value) for value in (face.get("engine"), prov["payload"].get("engine"), prov["model_tag"])
                       if value and value not in {"unknown", "legacy_unsealed"}}
            if len(engines) > 1:
                raise ValueError("Face engine disagrees with UCF model authority")
            detections.append({
                    "detection_id": f"{prov['frame_id']}_{face_idx}",
                    "frame_id": prov["frame_id"],
                    "video_hash": prov["video_hash"],
                    "t_start": timestamp,
                    "raw_ref": raw_ref,
                    "face_idx": face_idx,
                    "bbox": face.get("bbox"),
                    "embedding": enc,
                    "engine": next(iter(engines), "legacy_unsealed"),
                    "image_path": str(image),
                })

    engine_dimensions = {
        (str(item.get("engine") or "legacy_unsealed"), len(item["embedding"]))
        for item in detections
    }
    if len(engine_dimensions) > 1:
        raise RuntimeError(
            "Face cluster rebuild refused mixed or legacy embedding contracts: "
            f"{sorted(engine_dimensions)}. Re-ingest into a clean epoch before clustering."
        )

    log.info("Collected %d promoted face detections", len(detections))
    return detections


def run_dbscan(detections: list, eps: float, min_samples: int) -> np.ndarray:
    """Runs DBSCAN with cosine metric on face embeddings. Returns label array."""
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import normalize

    embeddings = np.array([d["embedding"] for d in detections], dtype=np.float32)
    embeddings = normalize(embeddings)  # L2-normalize for cosine equivalence

    log.info(
        "Running DBSCAN: %d faces, eps=%.3f, min_samples=%d",
        len(embeddings), eps, min_samples,
    )
    db = DBSCAN(eps=eps, min_samples=min_samples, metric="cosine", n_jobs=-1)
    labels = db.fit_predict(embeddings)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int((labels == -1).sum())
    log.info("DBSCAN result: %d candidate clusters, %d unassigned detections", n_clusters, n_noise)
    return labels


def build_cluster_manifest(detections: list, labels: np.ndarray, epoch_id: str, eps: float) -> dict:
    """Assembles the cluster manifest dict."""
    cluster_groups: dict[int, list] = defaultdict(list)
    for detection, label in zip(detections, labels):
        cluster_groups[int(label)].append(detection)

    clusters = []
    for label, members in sorted(cluster_groups.items()):
        if label == -1:
            continue  # handled as unassigned below
        video_hashes = sorted(set(m["video_hash"] for m in members))
        t_values = [m["t_start"] for m in members if m["t_start"] is not None]
        clusters.append({
            "cluster_id": f"face_cluster_{label}",
            "status": "candidate",
            "label": None,
            "confirmed": False,
            "face_count": len(members),
            "video_count": len(video_hashes),
            "video_hashes": video_hashes,
            "timestamp_range": [min(t_values), max(t_values)] if t_values else [],
            "face_ids": [m["detection_id"] for m in members],
            "representative_frame": members[0]["raw_ref"],
        })

    unassigned = [d for d, l in zip(detections, labels) if l == -1]

    return {
        "epoch_id": epoch_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "eps_used": eps,
        "note": (
            "Face clusters are CANDIDATE GROUPINGS only. "
            "VHS-era face quality is low. Set label and confirmed=true "
            "in family_roster.yaml — not here — before identity promotion."
        ),
        "cluster_count": len(clusters),
        "unassigned_count": len(unassigned),
        "clusters": clusters,
        "unassigned_face_ids": [d["detection_id"] for d in unassigned],
    }


def _crop_face_b64(image_path: str, bbox: dict | list | None) -> str | None:
    """Tries to crop and base64-encode a face thumbnail for the HTML sheet."""
    try:
        from PIL import Image
        with Image.open(image_path) as source:
            img = source.convert("RGB")
        if bbox is not None:
            bbox = _bbox_coordinates(bbox)
            if bbox is None:
                return None
            left, top, right, bottom = map(int, bbox)
            left, top = max(0, left), max(0, top)
            right, bottom = min(right, img.width), min(bottom, img.height)
            if right <= left or bottom <= top:
                return None
            img = img.crop((left, top, right, bottom))
        img = img.resize((80, 80))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode()
    except (ImportError, OSError, ValueError):
        log.warning("Face thumbnail unavailable: %s", image_path)
        return None


def generate_html_sheet(detections: list, labels: np.ndarray, manifest: dict, output_path: Path) -> None:
    """Generates a browsable face cluster sheet for human labeling."""
    cluster_members: dict[int, list] = defaultdict(list)
    for det, label in zip(detections, labels):
        cluster_members[int(label)].append(det)

    rows_html = []
    for cluster_info in manifest["clusters"]:
        label_int = int(cluster_info["cluster_id"].split("_")[-1])
        members = cluster_members[label_int]
        thumbs = []
        for m in members[:12]:  # cap at 12 thumbnails per cluster
            b64 = _crop_face_b64(m.get("image_path", ""), m.get("bbox"))
            if b64:
                timestamp = f"{m['t_start']:.1f}s" if m["t_start"] is not None else "unknown"
                thumbs.append(
                    f'<img src="data:image/jpeg;base64,{b64}" '
                    f'title="v={m["video_hash"][:8]} t={timestamp}" '
                    f'style="width:80px;height:80px;object-fit:cover;margin:2px;border-radius:4px;">'
                )
            else:
                thumbs.append(
                    f'<div style="width:80px;height:80px;background:#333;display:inline-block;'
                    f'margin:2px;border-radius:4px;font-size:10px;color:#aaa;'
                    f'text-align:center;line-height:80px;">no img</div>'
                )
        overflow = len(members) - 12
        overflow_html = f'<div style="color:#888;font-size:11px">+{overflow} more</div>' if overflow > 0 else ""
        vids = ", ".join(v[:8] for v in cluster_info["video_hashes"])
        rows_html.append(f"""
        <tr style="border-bottom:1px solid #333">
          <td style="padding:8px;font-family:monospace;color:#4af">{cluster_info['cluster_id']}</td>
          <td style="padding:8px;color:#fa4">candidate</td>
          <td style="padding:8px">{cluster_info['face_count']}</td>
          <td style="padding:8px;font-size:11px;color:#888">{vids}</td>
          <td style="padding:8px">{''.join(thumbs)}{overflow_html}</td>
        </tr>""")

    n_unassigned = manifest["unassigned_count"]
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Face Cluster Candidates — {manifest['epoch_id']}</title>
<style>
  body {{ background:#1a1a1a; color:#eee; font-family:sans-serif; margin:24px; }}
  h1 {{ color:#4af; }}
  table {{ border-collapse:collapse; width:100%; }}
  th {{ background:#222; color:#aaa; text-align:left; padding:8px; }}
  tr:hover {{ background:#1e2a3a; }}
</style>
</head>
<body>
<h1>Face Cluster Candidates</h1>
<p style="color:#888">Epoch: <code>{manifest['epoch_id']}</code> &nbsp;|&nbsp;
Generated: {manifest['generated_at']} &nbsp;|&nbsp;
eps={manifest['eps_used']} &nbsp;|&nbsp;
{manifest['cluster_count']} candidate clusters &nbsp;|&nbsp;
{n_unassigned} unassigned faces</p>
<p style="color:#f84;background:#2a1a00;padding:8px;border-radius:4px">
⚠ These are CANDIDATE GROUPINGS only. VHS-era face quality is low. Label clusters
in <code>family_roster.yaml</code> after reviewing this sheet.</p>
<table>
  <thead>
    <tr>
      <th>Cluster ID</th><th>Status</th><th>Faces</th><th>Videos</th><th>Thumbnails</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows_html)}
  </tbody>
</table>
<p style="color:#555;font-size:11px;margin-top:16px">
{n_unassigned} unassigned faces (singletons or noise) not shown above.
</p>
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    log.info("Cluster sheet written: %s", output_path)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GoodQ4All Phase 1: Face Candidate Cluster Builder"
    )
    parser.add_argument("--epoch-id", required=True, help="Active epoch ID")
    parser.add_argument("--epoch-root", default=DEFAULT_EPOCH_ROOT)
    parser.add_argument("--data-path", default=DEFAULT_DATA_PATH)
    parser.add_argument(
        "--eps", type=float, default=DEFAULT_EPS,
        help="DBSCAN eps (cosine distance threshold). Default=0.4. "
             "Increase to merge more aggressively; decrease for stricter separation.",
    )
    parser.add_argument(
        "--min-samples", type=int, default=DEFAULT_MIN_SAMPLES,
        help="DBSCAN min_samples. Default=2 (pair of faces to form a cluster).",
    )
    parser.add_argument(
        "--start-gate-job-id",
        type=_start_gate_job_id,
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if (
        args.start_gate_job_id is not None
        and not _wait_for_start_gate(args.start_gate_job_id)
    ):
        log.error("Authorized rebuild start gate was not satisfied")
        raise SystemExit(2)

    data_path = Path(args.data_path)
    data_path.mkdir(parents=True, exist_ok=True)
    manifest_path = data_path / "face_clusters.json"
    sheet_path    = data_path / "reports" / "face_cluster_sheet.html"

    log.info("=== GoodQ4All Phase 1: Face Candidate Cluster Builder ===")
    log.info("Epoch: %s | eps=%.3f | min_samples=%d", args.epoch_id, args.eps, args.min_samples)

    epoch_dir = _epoch_dir(args.epoch_root, args.epoch_id)
    ucf_db_path = _ucf_db(epoch_dir)

    provenance = load_face_ucf_provenance(ucf_db_path)
    if not provenance:
        log.error("No promoted face_embed frames found. Aborting.")
        sys.exit(1)

    detections = collect_face_detections(epoch_dir, provenance)
    if len(detections) < args.min_samples:
        log.error("Not enough face detections (%d) to cluster. Aborting.", len(detections))
        sys.exit(1)

    labels = run_dbscan(detections, args.eps, args.min_samples)
    manifest = build_cluster_manifest(detections, labels, args.epoch_id, args.eps)

    log.info(
        "Result: %d candidate clusters, %d unassigned — writing manifest to %s",
        manifest["cluster_count"], manifest["unassigned_count"], manifest_path,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    log.info("Generating HTML cluster sheet...")
    generate_html_sheet(detections, labels, manifest, sheet_path)

    log.info("=== Phase 1 complete ===")
    log.info("Review the cluster sheet in your browser: %s", sheet_path)
    log.info(
        "Next step: label clusters by adding face_cluster_ids to family_roster.yaml "
        "(copy from family_roster.template.yaml). Run validate_roster.py before Phase 5A."
    )


if __name__ == "__main__":
    main()
