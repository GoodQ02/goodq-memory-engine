from __future__ import annotations
from typing import Any, Dict, List, Tuple


def object_track_yolo(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    # Heavy tracker using deep-sort-realtime if available; falls back to IoU association.
    frames: List[Dict[str, Any]] = item.get("frames") or []
    try:
        import numpy as np  # type: ignore
        import cv2  # type: ignore
        from deep_sort_realtime.deepsort_tracker import DeepSort  # type: ignore

        tracker = DeepSort(max_age=15)
        tracks_count: Dict[int, Dict[str, Any]] = {}

        for fr in frames:
            path = fr.get("source_path") or ""
            try:
                img = cv2.imread(path)
            except Exception as e:
                img = None
            dets = []
            for obj in (fr.get("objects") or []):
                bb = obj.get("bbox")
                lbl = obj.get("label")
                conf = float(obj.get("score", 0.5))
                if isinstance(bb, list) and len(bb) == 4 and lbl:
                    x1, y1, x2, y2 = [float(x) for x in bb]
                    dets.append([x1, y1, x2, y2, conf, str(lbl)])
            if not dets:
                continue
            tracks = tracker.update_tracks(dets, frame=img)
            for t in tracks:
                if not t.is_confirmed():
                    continue
                tid = int(t.track_id)
                l = str(t.get_det_class()) if hasattr(t, 'get_det_class') else str(t.det_class)
                if tid not in tracks_count:
                    tracks_count[tid] = {"id": tid, "label": l, "count": 0}
                tracks_count[tid]["count"] += 1

        by_label: Dict[str, int] = {}
        for tr in tracks_count.values():
            by_label[tr["label"]] = by_label.get(tr["label"], 0) + int(tr["count"])
        top = sorted(by_label.items(), key=lambda kv: kv[1], reverse=True)[:10]
        top_tracked = [{"label": k, "count": v} for k, v in top]
        return {"tracks": {"count": len(tracks_count), "top_tracked": top_tracked}}
    except Exception as e:
        # Fallback to lightweight IoU association if heavy deps unavailable
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
            last_boxes = [(tid, tr["label"], tr["last_bbox"]) for tid, tr in track_map.items()]
        by_label: Dict[str, int] = {}
        for tr in track_map.values():
            by_label[tr["label"]] = by_label.get(tr["label"], 0) + int(tr["count"])
        top = sorted(by_label.items(), key=lambda kv: kv[1], reverse=True)[:10]
        top_tracked = [{"label": k, "count": v} for k, v in top]
        return {"tracks": {"count": len(track_map), "top_tracked": top_tracked, "fallback": True}}

