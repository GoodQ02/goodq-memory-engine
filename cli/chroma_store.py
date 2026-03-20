from __future__ import annotations
import argparse
import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from steps.common.config_loader import load_configs
from steps.discover_sources.step import discover_sources

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_step(env: str, step: str, item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        from steps.common.tool_paths import resolve_conda

        in_p = os.path.join(td, 'in.json')
        out_p = os.path.join(td, 'out.json')
        cfg_p = os.path.join(td, 'cfg.json')
        with open(in_p, 'w', encoding='utf-8') as f:
            json.dump(item, f)
        with open(cfg_p, 'w', encoding='utf-8') as f:
            json.dump(cfg, f)
        conda_exe = resolve_conda()
        cmd = [
            conda_exe,'run','-n',env,'python','-m','cli.step_runner',
            '--step',step,'--in',in_p,'--out',out_p,'--cfg',cfg_p
        ]
        subprocess.run(cmd, check=True, capture_output=True, cwd=REPO_ROOT)
        if os.path.isfile(out_p):
            with open(out_p, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except Exception:
                    return {}
        return {}


def _text_for_item(item: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    mod = item.get('modality')
    if mod == 'text':
        try:
            p = item.get('source_path');
            if isinstance(p, str) and os.path.isfile(p):
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
        except Exception:
            return ''
    if mod == 'pdf':
        res = _run_step('goodq_text_embed','pdf_text', item, cfg)
        text = res.get('text') or res.get('content') or ''
        return text if isinstance(text, str) else ''
    if mod == 'image':
        # OCR + caption
        out: List[str] = []
        res_ocr = _run_step('goodq_image_caption','image_ocr', item, cfg)
        t = res_ocr.get('ocr_text');
        if isinstance(t, str) and t.strip(): out.append(t)
        res_cap = _run_step('goodq_image_caption','image_caption', item, cfg)
        c = res_cap.get('caption');
        if isinstance(c, str) and c.strip(): out.append(c)
        return '\n'.join(out)
    if mod == 'audio':
        # Transcribe only (fast)
        res_tr = _run_step('goodq_audio_transcribe','audio_transcribe', item, cfg)
        tr = res_tr.get('transcript')
        return tr if isinstance(tr, str) else ''
    return ''


def _ensure_chroma(collection: str, persist_dir: str):
    from chromadb.config import Settings
    import chromadb
    client = chromadb.PersistentClient(path=persist_dir, settings=Settings(anonymized_telemetry=False))
    try:
        coll = client.get_collection(collection)
    except Exception:
        coll = client.create_collection(collection)
    return coll


def _split_texts(texts: List[str]) -> List[List[str]]:
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        return [ [c] if len(t) <= 1100 else [x for x in splitter.split_text(t)] for t in texts ]
    except Exception:
        return [ [t] for t in texts ]


def _embed_and_upsert(docs: List[Dict[str, Any]], cfg: Dict[str, Any], collection: str, persist_dir: str) -> int:
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import HuggingFaceEmbeddings

    os.makedirs(persist_dir, exist_ok=True)
    embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
    vectordb = Chroma(collection_name=collection, persist_directory=persist_dir, embedding_function=embeddings)

    raw_texts: List[str] = []
    raw_metas: List[Dict[str, Any]] = []
    raw_ids: List[str] = []

    for d in docs:
        text = d.get('text') or ''
        if not isinstance(text, str) or not text.strip():
            continue
        meta = d.get('metadata') or {}
        sid = meta.get('id') or meta.get('source_path') or str(len(ids))
        raw_texts.append(text)
        raw_metas.append(meta)  # type: ignore[arg-type]
        raw_ids.append(str(sid))

    if raw_texts:
        chunked = _split_texts(raw_texts)
        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []
        for base_text, chunks, meta, rid in zip(raw_texts, chunked, raw_metas, raw_ids):
            total = len(chunks)
            for idx, c in enumerate(chunks):
                texts.append(c)
                m = dict(meta)
                m.update({"chunk_index": idx, "chunk_total": total})
                metadatas.append(m)
                ids.append(f"{rid}#c{idx}")
        vectordb.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        vectordb.persist()
        return len(texts)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--collection', default='goodq')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--persist_dir', help='Override chroma persist dir')
    args = ap.parse_args()

    cfg = load_configs({})
    paths = cfg.get('paths', {}) or {}
    persist_dir = args.persist_dir or (paths.get('chroma_dir') or os.path.join(os.getcwd(), 'chroma'))

    items = discover_sources(cfg)
    docs: List[Dict[str, Any]] = []
    count = 0
    for it in items:
        if args.limit and count >= args.limit:
            break
        text = _text_for_item(it, cfg)
        if not text:
            continue
        # Optional: enrich with tags/entities and audio insights for filters
        # Tagger (NER)
        try:
            res_tag = _run_step('goodq_emotion_classify','tagger', it, cfg)
        except Exception:
            res_tag = {}
        tags = res_tag.get('tags') or []
        entities = res_tag.get('entities') or []
        # Sentiment (label only)
        try:
            res_sent = _run_step('goodq_sentiment','sentiment', it, cfg)
        except Exception:
            res_sent = {}
        sent = None
        if isinstance(res_sent.get('sentiment'), dict):
            sent = res_sent['sentiment'].get('label')
        # Audio time hints / music events if applicable
        events = []
        time_hints = {}
        if (it.get('modality') == 'audio'):
            try:
                th = _run_step('goodq_audio_metadata','audio_time_hints', it, cfg)
                time_hints = th.get('time_hints') or {}
            except Exception:
                time_hints = {}
            try:
                me = _run_step('goodq_audio_metadata','audio_music_events', it, cfg)
                events = [e.get('label') for e in (me.get('music_events') or []) if isinstance(e, dict) and e.get('label')]
            except Exception:
                events = []
        docs.append({
            'text': text,
            'metadata': {
                'source_path': it.get('source_path'),
                'filename': it.get('filename'),
                'modality': it.get('modality'),
                'id': it.get('source_path'),
                'tags': tags,
                'entities': entities,
                'sentiment': sent,
                'events': events,
                'time_hints': time_hints,
            }
        })
        count += 1

    n = _embed_and_upsert(docs, cfg, args.collection, persist_dir)
    print(json.dumps({'upserted': n, 'collection': args.collection, 'persist_dir': persist_dir}))


if __name__ == '__main__':
    main()
