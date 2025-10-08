from __future__ import annotations
from typing import Any, Dict

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Any, Dict

app = FastAPI(title="GoodQ Retrieval API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/search")
def search(q: str = Query(..., description="Search text"), topk: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    # Import lazily so the process starts fast and errors show clearly
    from steps.cli.retrieve import search_text_index

    results = search_text_index(q, topk=topk)
    return results


# Optional root
@app.get("/")
def root() -> Dict[str, Any]:
    return {"status": "ok", "endpoints": ["/search?q=..."]}


@app.get("/vector_search")
def vector_search(
    q: str = Query(..., description="Search text"),
    topk: int = Query(20, ge=1, le=200),
    modality: Optional[str] = Query(None, description="Filter by modality"),
    event: Optional[str] = Query(None, description="Filter by music/event label"),
    tag: Optional[str] = Query(None, description="Filter by tag/entity"),
) -> Dict[str, Any]:
    # Lazy imports to keep startup fast
    from steps.steps.common.config_loader import load_configs
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
    import os

    cfg = load_configs({})
    paths = cfg.get("paths", {}) or {}
    persist_dir = paths.get("chroma_dir") or os.path.join(os.getcwd(), "chroma")

    emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectordb = Chroma(collection_name="goodq", persist_directory=persist_dir, embedding_function=emb)

    # Fetch more than topk to allow filtering, then trim
    k0 = max(topk * 5, topk)
    docs = vectordb.similarity_search(q, k=k0)

    def _pass_filters(md: Dict[str, Any]) -> bool:
        if modality and str(md.get("modality") or "") != modality:
            return False
        if event:
            evs = md.get("events") or []
            if isinstance(evs, list):
                if event not in [str(e) for e in evs]:
                    return False
            else:
                return False
        if tag:
            tags = md.get("tags") or md.get("entities") or []
            hay = [str(t).lower() for t in (tags if isinstance(tags, list) else [])]
            if tag.lower() not in hay:
                return False
        return True

    matches: List[Dict[str, Any]] = []
    for d in docs:
        md = d.metadata or {}
        if not _pass_filters(md):
            continue
        matches.append({
            "source_path": md.get("source_path"),
            "filename": md.get("filename"),
            "modality": md.get("modality"),
            "score": None,  # Chroma doesn't return distance via this API
            "snippet": (d.page_content or "")[:280],
            "metadata": md,
        })
        if len(matches) >= topk:
            break

    return {"matches": matches, "persist_dir": persist_dir}
