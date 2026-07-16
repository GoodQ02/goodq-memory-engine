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
        --epoch-id epoch_2026_07_05_home_memory_clean_01 \\
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
import json
import logging
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Config defaults ────────────────────────────────────────────────────────────
DEFAULT_EPOCH_ROOT = "L:/_DATA/GoodQ_Data/epochs"
DEFAULT_DATA_PATH  = "L:/_DATA/GoodQ_Data/identity"
DEFAULT_EPS        = 0.4
DEFAULT_MIN_SAMPLES = 2


# ── Helpers ────────────────────────────────────────────────────────────────────

def _epoch_dir(epoch_root: str, epoch_id: str) -> Path:
    p = Path(epoch_root) / epoch_id
    if not p.exists():
        raise FileNotFoundError(f"Epoch directory not found: {p}")
    return p


def _ucf_db(epoch_dir: Path) -> Path:
    p = epoch_dir / "ucf" / "ucf_ledger.db"
    if not p.exists():
        raise FileNotFoundError(f"UCF ledger not found: {p}")
    return p


def load_face_ucf_provenance(ucf_db_path: Path) -> dict:
    """
    Returns a mapping of raw_ref (face JSON path) -> {video_hash, frame_id, t_start}.
    Only promoted face_embed frames are included.
    """
    conn = sqlite3.connect(str(ucf_db_path))
    cur = conn.cursor()
    cur.execute(
        """
        SELECT frame_id, video_hash, raw_ref, t_start
        FROM context_frames
        WHERE worker_name = 'face_embed'
          AND promotion_status = 'promoted'
        """
    )
    rows = cur.fetchall()
    conn.close()
    provenance = {}
    for frame_id, video_hash, raw_ref, t_start in rows:
        provenance[raw_ref] = {
            "frame_id": frame_id,
            "video_hash": video_hash,
            "t_start": t_start,
        }
    log.info("Loaded %d promoted face_embed UCF frames", len(provenance))
    return provenance


def collect_face_detections(epoch_dir: Path, provenance: dict) -> list:
    """
    Walks all processing/<video_hash>/video/frames/*_raw_faces.json files.
    Returns a list of detection dicts with embedding, provenance, and path.
    """
    processing_dir = epoch_dir / "processing"
    detections = []
    missing_provenance = 0

    for video_dir in sorted(processing_dir.iterdir()):
        frames_dir = video_dir / "video" / "frames"
        if not frames_dir.exists():
            continue
        for fname in sorted(frames_dir.iterdir()):
            if "raw_faces" not in fname.name:
                continue
            raw_ref = str(fname)
            prov = provenance.get(raw_ref)
            if prov is None:
                # Try with forward slashes
                prov = provenance.get(raw_ref.replace("\\", "/"))
            if prov is None:
                missing_provenance += 1
                continue
            try:
                with open(fname, encoding="utf-8") as f:
                    faces = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Could not read %s: %s", fname, e)
                continue
            if not isinstance(faces, list):
                log.warning("Unexpected face file format in %s", fname)
                continue
            for face_idx, face in enumerate(faces):
                enc = face.get("encoding")
                if enc is None:
                    continue
                detections.append({
                    "detection_id": f"{prov['frame_id']}_{face_idx}",
                    "frame_id": prov["frame_id"],
                    "video_hash": prov["video_hash"],
                    "t_start": prov["t_start"],
                    "raw_ref": raw_ref,
                    "face_idx": face_idx,
                    "bbox": face.get("bbox"),
                    "embedding": enc,
                    "image_path": str(fname).replace("_raw_faces.json", ".jpg"),
                })

    log.info(
        "Collected %d face detections (%d files missing UCF provenance)",
        len(detections), missing_provenance,
    )
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


def _crop_face_b64(image_path: str, bbox: dict | None) -> str | None:
    """Tries to crop and base64-encode a face thumbnail for the HTML sheet."""
    try:
        import cv2
        if not os.path.exists(image_path):
            return None
        img = cv2.imread(image_path)
        if img is None:
            return None
        if bbox:
            # bbox may be {left, top, right, bottom} or similar
            left = int(bbox.get("left", bbox.get(0, 0)))
            top  = int(bbox.get("top",  bbox.get(1, 0)))
            right = int(bbox.get("right", bbox.get(2, img.shape[1])))
            bottom = int(bbox.get("bottom", bbox.get(3, img.shape[0])))
            # Clamp to image bounds
            left, top = max(0, left), max(0, top)
            right  = min(right,  img.shape[1])
            bottom = min(bottom, img.shape[0])
            if right > left and bottom > top:
                img = img[top:bottom, left:right]
        img = cv2.resize(img, (80, 80))
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return base64.b64encode(buf).decode()
    except Exception:
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
                thumbs.append(
                    f'<img src="data:image/jpeg;base64,{b64}" '
                    f'title="v={m["video_hash"][:8]} t={m["t_start"]:.1f}s" '
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
    args = parser.parse_args()

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
