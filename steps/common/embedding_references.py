"""Expand validated document passages without changing scalar UCF identities."""
from __future__ import annotations

import hashlib
import json
import re

from steps.common.memory import to_faiss_id


MAX_DOCUMENT_EMBEDDING_CHUNKS = 16384


def frame_payload(frame: dict) -> dict:
    payload = frame.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("Embedding frame payload must be an object")
    return payload


def expand_embedding_references(frame: dict, *, document_text: str | None = None) -> list[dict]:
    """Return scalar-like references; one frame continues to own all passages.

    Group text is reconstructed with overlap agreement and exact coverage before
    any reference is admitted. Callers with the source anchor also bind it to
    the original extracted text. Ordinary scalar records retain their shape.
    """
    payload = frame_payload(frame)
    if "embedding_chunks" not in payload:
        return [frame] if frame.get("vector_key") is not None else []

    def require(condition, message):
        if not condition:
            raise ValueError(f"Document embedding group: {message}")

    require(payload.get("source_kind") == "document" and frame.get("worker_name") == "text_embed"
            and frame.get("modality") == "text", "only document text_embed frames may contain chunks")
    require(frame.get("vector_key") is None, "group must not also declare a scalar vector_key")
    require(frame.get("t_start") == 0 and frame.get("t_end") == 0, "document bounds must remain [0,0]")
    chunks = payload["embedding_chunks"]
    require(isinstance(chunks, list) and 0 < len(chunks) <= MAX_DOCUMENT_EMBEDDING_CHUNKS,
            "chunk list is empty, invalid or exceeds the bounded limit")
    require(type(payload.get("chunk_count")) is int and payload["chunk_count"] == len(chunks), "chunk_count mismatch")
    length, token_limit = payload.get("text_length"), payload.get("chunk_token_limit")
    require(type(length) is int and length > 0, "text_length must be positive")
    require(type(token_limit) is int and 0 < token_limit <= 4096, "invalid chunk_token_limit")
    require(isinstance(payload.get("text_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", payload["text_sha256"]) is not None, "invalid text_sha256")
    covered = ""
    previous_start = -1
    identifiers = set()
    faiss_identifiers = set()
    references = []
    common_payload = {key: value for key, value in payload.items() if key != "embedding_chunks"}
    scalar_types = (str, int, float, bool, type(None))
    require(all(isinstance(value, scalar_types) for value in common_payload.values()),
            "other group payload fields must remain flat")
    for index, chunk in enumerate(chunks):
        require(isinstance(chunk, dict), "chunk must be an object")
        require(all(isinstance(value, scalar_types) for value in chunk.values()), "chunk fields must remain flat")
        require(type(chunk.get("chunk_index")) is int and chunk["chunk_index"] == index, "chunk indexes must be contiguous")
        start, end, text = chunk.get("char_start"), chunk.get("char_end"), chunk.get("text")
        require(type(start) is int and type(end) is int and previous_start < start <= len(covered) < end <= length,
                "chunk spans must advance without gaps")
        require(isinstance(text, str) and len(text) == end - start, "chunk text length differs from its span")
        overlap = len(covered) - start
        require(covered[start:] == text[:overlap], "overlap text mismatch")
        covered += text[overlap:]
        previous_start = start
        count = chunk.get("token_count")
        require(type(count) is int and 0 < count <= token_limit, "chunk exceeds its token budget")
        key = chunk.get("embedding_id")
        require(isinstance(key, str) and re.fullmatch(r"[0-9a-f]{64}", key) is not None
                and key not in identifiers, "embedding IDs must be unique SHA256 identities")
        require(type(chunk.get("faiss_id")) is int and chunk["faiss_id"] == to_faiss_id(key)
                and chunk["faiss_id"] not in faiss_identifiers, "FAISS identity mismatch or duplicate")
        identifiers.add(key)
        faiss_identifiers.add(chunk["faiss_id"])
        references.append({**frame, "vector_key": key,
                           "payload": {**common_payload, **chunk, "document_chunk": dict(chunk)}})
    require(len(covered) == length, "final chunk does not cover the entire document")
    require(hashlib.sha256(covered.encode("utf-8")).hexdigest() == payload["text_sha256"], "document text hash mismatch")
    if document_text is not None:
        require(covered == document_text, "chunks differ from the retained document text")
    return references


def vector_sync_references(frames) -> list[tuple]:
    """Expand every reference for the existing exact-point lifecycle delivery."""
    return [(ref["vector_key"], ref.get("vector_collection"), ref.get("vector_backend"))
            for frame in frames for ref in expand_embedding_references(dict(frame))]
