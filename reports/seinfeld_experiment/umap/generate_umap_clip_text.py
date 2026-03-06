from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib import request

import matplotlib
import numpy as np
import umap

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(r"L:\GOODCUBE\projects\goodq4all")
PROCESSING = Path(r"L:\_DATA\GoodQ_Data\epochs\epoch_2025_12_22\processing")
REPORT_DIR = PROJECT_ROOT / "reports" / "seinfeld_experiment"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PNG = REPORT_DIR / "scene_umap_clip_text.png"
OUT_CSV = REPORT_DIR / "scene_umap_clip_text_coords.csv"
OUT_META = REPORT_DIR / "scene_umap_clip_text_meta.json"

QHOST = "http://127.0.0.1:6333"
COL_CLIP = "goodq_clip_epoch_2025_12_22"
COL_TEXT = "goodq_text_epoch_2025_12_22"


def http_json(method: str, url: str, body: dict | None = None) -> dict:
    data = None
    headers: dict[str, str] = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, method=method, headers=headers)
    with request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def scroll_collection(name: str) -> list[dict]:
    points: list[dict] = []
    offset = None
    while True:
        body = {"limit": 256, "with_payload": True, "with_vector": True}
        if offset is not None:
            body["offset"] = offset
        res = http_json("POST", f"{QHOST}/collections/{name}/points/scroll", body)
        result = res.get("result") or {}
        batch = result.get("points") or []
        points.extend(batch)
        offset = result.get("next_page_offset")
        if not offset:
            break
    return points


def l2_normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n <= 1e-12:
        return np.zeros_like(v)
    return v / n


def parse_episode_map() -> tuple[dict[str, str], dict[str, int | str]]:
    scene_to_episode: dict[str, str] = {}
    scene_to_index: dict[str, int | str] = {}
    for ep_dir in sorted([p for p in PROCESSING.iterdir() if p.is_dir()], key=lambda p: p.name):
        manifest = ep_dir / "video" / "scene_manifest.json"
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        for s in data.get("scenes") or []:
            sid = s.get("scene_id")
            if not sid:
                continue
            scene_to_episode[sid] = ep_dir.name
            scene_to_index[sid] = s.get("index", "")
    return scene_to_episode, scene_to_index


def extract_vectors(points: list[dict]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for p in points:
        payload = p.get("payload") or {}
        sid = payload.get("scene_id")
        vec = p.get("vector")
        if isinstance(vec, dict):
            vec = next(iter(vec.values())) if vec else []
        if not sid or not isinstance(vec, list) or not vec:
            continue
        out[sid] = np.asarray(vec, dtype=np.float32)
    return out


def main() -> None:
    scene_to_episode, scene_to_index = parse_episode_map()
    clip_points = scroll_collection(COL_CLIP)
    text_points = scroll_collection(COL_TEXT)

    clip_by_scene = extract_vectors(clip_points)
    text_by_scene = extract_vectors(text_points)
    common_scene_ids = sorted(set(clip_by_scene.keys()) & set(text_by_scene.keys()))
    if not common_scene_ids:
        raise SystemExit("No overlapping scene_ids found between clip and text collections.")

    X = []
    rows = []
    for sid in common_scene_ids:
        c = l2_normalize(clip_by_scene[sid])
        t = l2_normalize(text_by_scene[sid])
        X.append(np.concatenate([c, t], axis=0))
        rows.append(
            {
                "scene_id": sid,
                "episode": scene_to_episode.get(sid, "unknown"),
                "scene_index": scene_to_index.get(sid, ""),
            }
        )
    X_arr = np.vstack(X)

    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=15,
        min_dist=0.1,
        metric="cosine",
        random_state=42,
    )
    coords = reducer.fit_transform(X_arr)

    for i, row in enumerate(rows):
        row["umap_x"] = float(coords[i, 0])
        row["umap_y"] = float(coords[i, 1])

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["scene_id", "episode", "scene_index", "umap_x", "umap_y"]
        )
        writer.writeheader()
        writer.writerows(rows)

    episodes = sorted({r["episode"] for r in rows})
    colors = plt.cm.tab10(np.linspace(0, 1, max(10, len(episodes))))
    color_map = {ep: colors[i % len(colors)] for i, ep in enumerate(episodes)}

    plt.figure(figsize=(13, 9))
    for ep in episodes:
        idx = [i for i, r in enumerate(rows) if r["episode"] == ep]
        if not idx:
            continue
        ep_coords = coords[idx]
        plt.scatter(
            ep_coords[:, 0],
            ep_coords[:, 1],
            s=35,
            alpha=0.85,
            color=color_map[ep],
            label=f"{ep} (n={len(idx)})",
        )

    for ep in episodes:
        idx = [i for i, r in enumerate(rows) if r["episode"] == ep]
        if not idx:
            continue
        centroid = coords[idx].mean(axis=0)
        plt.text(
            centroid[0],
            centroid[1],
            ep.replace("01x0", "E"),
            fontsize=9,
            ha="center",
            va="center",
        )

    plt.title("Seinfeld S1 Scene UMAP (Combined CLIP + Text Embeddings)")
    plt.xlabel("UMAP-1")
    plt.ylabel("UMAP-2")
    plt.legend(loc="best", fontsize=8, frameon=True)
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=220)
    plt.close()

    meta = {
        "method": "UMAP on concatenated L2-normalized CLIP(512)+Text(384) vectors",
        "clip_collection": COL_CLIP,
        "text_collection": COL_TEXT,
        "scene_count": len(rows),
        "vector_dim_combined": int(X_arr.shape[1]),
        "umap_params": {
            "n_components": 2,
            "n_neighbors": 15,
            "min_dist": 0.1,
            "metric": "cosine",
            "random_state": 42,
        },
        "episodes": episodes,
        "output_png": str(OUT_PNG),
        "output_csv": str(OUT_CSV),
    }
    OUT_META.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"scene_count={len(rows)}")
    print(f"png={OUT_PNG}")
    print(f"csv={OUT_CSV}")
    print(f"meta={OUT_META}")


if __name__ == "__main__":
    main()
