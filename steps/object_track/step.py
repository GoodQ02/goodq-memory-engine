from __future__ import annotations
from typing import Any, Dict, List, Tuple


def _iou(a: List[float], b: List[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    a_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = a_area + b_area - inter
    return float(inter / union) if union > 0 else 0.0


def object_track(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Lightweight temporal association based on IoU and label.
    frames: List[Dict[str, Any]] = item.get("frames") or []
    tracks: List[Dict[str, Any]] = []
    next_id = 1
    last_boxes: List[Tuple[int, str, List[float]]] = []
    track_map: Dict[int, Dict[str, Any]] = {}

    for fr in frames:
        current: List[Tuple[str, List[float]]] = []
        for obj in (fr.get("objects") or []):
            bb = obj.get("bbox")
            lbl = obj.get("label")
            if isinstance(bb, list) and len(bb) == 4 and lbl:
                current.append((str(lbl), [float(x) for x in bb]))
        # greedy matching to previous
        used = set()
        for lbl, bb in current:
            best_id, best_iou = None, 0.0
            for tid, tlbl, tbb in last_boxes:
                if tlbl != lbl or tid in used:
                    continue
                i = _iou(bb, tbb)
                if i > 0.3 and i > best_iou:
                    best_id, best_iou = tid, i
            if best_id is not None:
                used.add(best_id)
                tr = track_map.get(best_id)
                if tr:
                    tr["count"] += 1
                    tr["last_bbox"] = bb
            else:
                tid = next_id; next_id += 1
                track_map[tid] = {"id": tid, "label": lbl, "count": 1, "last_bbox": bb}
                used.add(tid)
        # rebuild last_boxes
        last_boxes = [(tid, tr["label"], tr["last_bbox"]) for tid, tr in track_map.items()]

    # summarize top tracked by label
    by_label: Dict[str, int] = {}
    for tr in track_map.values():
        by_label[tr["label"]] = by_label.get(tr["label"], 0) + int(tr["count"])
    top = sorted(by_label.items(), key=lambda kv: kv[1], reverse=True)[:10]
    top_tracked = [{"label": k, "count": v} for k, v in top]
    return {"tracks": {"count": len(track_map), "top_tracked": top_tracked}}

