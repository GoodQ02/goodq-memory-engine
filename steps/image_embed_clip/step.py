from __future__ import annotations
from typing import Any, Dict
from contextlib import nullcontext
import sqlite3
from datetime import datetime

import os


_CLIP = {"model": None, "proc": None, "device": "cpu"}


def _load() -> None:
    if _CLIP["model"] is not None:
        return
    try:
        import torch  # type: ignore
        from transformers import CLIPModel, CLIPProcessor  # type: ignore
        device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
        proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
        model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16").to(device).eval()
        _CLIP.update({"model": model, "proc": proc, "device": device})
    except Exception as e:
        _CLIP.update({"model": None, "proc": None})


def image_embed_clip(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"clip_meta": {"status": "no_file"}}
    _load()
    if _CLIP["model"] is None:
        return {"clip_meta": {"status": "unavailable"}}
    try:
        import torch  # type: ignore
        import numpy as np  # type: ignore
        from PIL import Image  # type: ignore
        import faiss  # type: ignore
        img = Image.open(path).convert("RGB")
        ipt = _CLIP["proc"](images=img, return_tensors="pt").to(_CLIP["device"])
        if _CLIP["device"] == "cuda":
            with torch.cuda.amp.autocast():
                out = _CLIP["model"](**ipt).image_embeds
        else:
            out = _CLIP["model"](**ipt).image_embeds
        feats = out.detach().cpu().numpy().astype("float32")
        index_path = (cfg.get("paths", {}) or {}).get("faiss_clip_path")
        if not index_path:
            return {"clip_meta": {"status": "no_index_path"}}
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        if os.path.isfile(index_path):
            index = faiss.read_index(index_path)
        else:
            index = faiss.IndexHNSWFlat(feats.shape[1], 32)
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 50
        # stable ID from content fingerprint
        from goodq4all.steps.text_embed.step import _content_fingerprint
        h = _content_fingerprint(item)
        try:
            import numpy as np  # type: ignore
            uid = np.array([int(h[:16], 16) % (2**63 - 1)], dtype='int64')
            index.add_with_ids(feats.astype("float32"), uid)
            faiss_id = int(uid[0])
        except Exception as e:
            index.add(feats.astype("float32"))
            faiss_id = getattr(index, 'ntotal', 0) - 1
        faiss.write_index(index, index_path)
        # map table
        map_db = (cfg.get("paths", {}) or {}).get("clip_id_map_db")
        if map_db:
            try:
                os.makedirs(os.path.dirname(map_db), exist_ok=True)
                con = sqlite3.connect(map_db, check_same_thread=False)
                with con:
                    con.execute(
                        "CREATE TABLE IF NOT EXISTS clip_id_map (faiss_id INTEGER PRIMARY KEY, hash TEXT, source_path TEXT, created_at TEXT)"
                    )
                    con.execute(
                        "INSERT OR REPLACE INTO clip_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
                        (faiss_id, h, path, datetime.utcnow().isoformat()),
                    )
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 83: {str(e)}')
                pass
            finally:
                try:
                    con.close()  # type: ignore
                except Exception as e:
                    print(f'[ERROR] Exception in step.py line 89: {str(e)}')
                    pass
        # Upsert generic embedding metadata for recall
        # NOTE: CLIP uses modality="image" (not "clip") by design.
        # This allows CLIP and DINO embeddings to be queried together as visual content.
        # To distinguish: check clip_id_map.sqlite or the specific FAISS index used.
        # See docs/ARCHITECTURE_REFERENCE.md for full explanation.
        try:
            from goodq4all.steps.common.memory import upsert_embedding
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "image") or "image")
        except Exception as e:
            print(f'[ERROR] Exception in step.py line 96: {str(e)}')
            pass
        return {"clip_meta": {"status": "ok", "index_path": index_path, "faiss_id": faiss_id}}
    except Exception as e:
        print(f"[ERROR] CLIP embedding failed: {str(e)}")
        return {"clip_meta": {"status": "error", "error": str(e)}}

