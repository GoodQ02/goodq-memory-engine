#!/usr/bin/env python3
"""
UCF Phase 0.2 — Epoch-level Validator Script.
Verifies path hygiene, schema versioning, staged promotion status, temporal bounds,
payload hash consistency, metadata flatness, spatial regions, and 1-to-1 scene manifest correlation.
Emits reports in JSON and Markdown formats.
"""

import os
import sys
import json
import sqlite3
import hashlib
import re
import requests
import argparse
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

# Set sys.path to find steps modules
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import load_configs

def load_ucf_ledger():
    import importlib.util
    ucf_ledger_path = REPO_ROOT / 'scripts' / 'ucf' / 'ucf_ledger.py'
    if not ucf_ledger_path.exists():
        raise FileNotFoundError(f"ucf_ledger.py not found at {ucf_ledger_path}")
    spec = importlib.util.spec_from_file_location("ucf_ledger", str(ucf_ledger_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for ucf_ledger at {ucf_ledger_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ucf_ledger"] = module
    spec.loader.exec_module(module)
    return module

try:
    ucf_module = load_ucf_ledger()
    UCFLedgerClient = ucf_module.UCFLedgerClient
    UCFRecord = ucf_module.UCFRecord
except Exception as e:
    print(f"Error loading ucf_ledger module: {e}")
    sys.exit(1)

def is_overlapping(start1: float, end1: float, start2: float, end2: float) -> bool:
    """
    Checks if interval (start1, end1) overlaps with interval (start2, end2).
    An overlap exists if max(start1, start2) < min(end1, end2) (assuming start < end).
    If either is a point event (start == end), check start2 <= start1 <= end2.
    """
    if start1 == end1:
        return start2 <= start1 <= end2
    if start2 == end2:
        return start1 <= start2 <= end1
    return max(start1, start2) < min(end1, end2)
def make_scene_hash(video_hash: str, start: float, end: float) -> str:
    """Computes the deterministic scene_id hash matching ucf_ledger.py and memory.py"""
    h = hashlib.sha256()
    h.update("scene".encode("utf-8"))
    for p in [video_hash, f"{start:.3f}", f"{end:.3f}"]:
        h.update(str(p).encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


def validate_vector_key(key: str, backend: str) -> bool:
    if not key or not isinstance(key, str):
        return False
    if backend == "qdrant":
        uuid_pattern = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
        sha256_pattern = re.compile(r"^[0-9a-fA-F]{64}$")
        prefix_pattern = re.compile(r"^(clip|dino)_scene_[0-9a-fA-F]+_[0-9a-fA-F]+$")
        return bool(uuid_pattern.match(key) or sha256_pattern.match(key) or prefix_pattern.match(key))
    elif backend == "faiss":
        sha256_pattern = re.compile(r"^[0-9a-fA-F]{64}$")
        prefix_pattern = re.compile(r"^(clip|dino)_scene_[0-9a-fA-F]+_[0-9a-fA-F]+$")
        return bool(sha256_pattern.match(key) or prefix_pattern.match(key))
    return False


def get_video_stem_from_source_path(source_path: str, checked_stems: Set[str]) -> Optional[str]:
    p = Path(source_path)
    for part in p.parts:
        if part in checked_stems:
            return part
    return None


def resolve_path(p: Any) -> Optional[Path]:
    if not p:
        return None
    expanded = os.path.expandvars(str(p))
    return Path(expanded).resolve()


GOODQ_POINT_ID_NAMESPACE = uuid.UUID("2058b732-6666-5424-a820-5cf54ef071c4")

def normalize_qdrant_id(raw_id: str) -> str:
    s = raw_id.strip()
    # Check if already UUID
    hex_candidate = s.replace("-", "")
    if len(hex_candidate) == 32 and all(ch in "0123456789abcdefABCDEF" for ch in hex_candidate):
        try:
            return str(uuid.UUID(hex_candidate))
        except ValueError:
            pass
    if s.isdigit():
        return s
    return str(uuid.uuid5(GOODQ_POINT_ID_NAMESPACE, s))


def run_validation(mode: str = "offline") -> int:
    cfg = load_configs({})
    db_dir = cfg.get('paths', {}).get('db_dir')
    if not db_dir:
        print("ERROR: paths.db_dir is not configured in config.")
        return 1
    
    epoch_id = os.path.basename(db_dir)
    data_root = os.getenv("GOODQ_DATA_ROOT") or cfg.get('paths', {}).get('data_root')

    qdrant_cfg = cfg.get("qdrant", {})
    collections_cfg = qdrant_cfg.get("collections", {})
    dims_cfg = qdrant_cfg.get("embedding_dims", {})

    clip_collection = collections_cfg.get("clip", "clip")
    dino_collection = collections_cfg.get("dino", "dino")
    clip_dim = dims_cfg.get("clip", 768)
    dino_dim = dims_cfg.get("dino", 1024)

    audio_collection = collections_cfg.get("audio", "audio")
    text_collection = collections_cfg.get("text", "text")
    audio_dim = dims_cfg.get("audio", 512)
    text_dim = dims_cfg.get("text", 384)

    paths_cfg = cfg.get("paths", {})
    clip_index_path = paths_cfg.get("faiss_clip_path")
    dino_index_path = paths_cfg.get("faiss_dino_path")
    clip_map_db = paths_cfg.get("clip_id_map_db")
    dino_map_db = paths_cfg.get("dino_id_map_db")
    audio_index_path = paths_cfg.get("faiss_audio_path")
    clap_map_db = paths_cfg.get("clap_id_map_db")
    text_index_path = paths_cfg.get("faiss_index_path")
    memory_db_path = paths_cfg.get("db_path")

    qdrant_host = qdrant_cfg.get("host", "http://127.0.0.1:6333")

    VECTOR_REGISTRY = {
        "image_embed_dino": {
            "expected_dim": dino_dim,
            "allowed_modalities": {"video"},
            "allowed_backends": {"qdrant", "faiss"},
            "allowed_collections": {dino_collection, "dino", "goodq_dino_custom"},
            "allowed_model_tags": {"facebook/dinov2-large", "facebook/dinov2-base"}
        },
        "image_embed_clip": {
            "expected_dim": clip_dim,
            "allowed_modalities": {"video", "multimodal"},
            "allowed_backends": {"qdrant", "faiss"},
            "allowed_collections": {clip_collection, "clip"},
            "allowed_model_tags": {"openai/clip-vit-large-patch14", "openai/clip-vit-base-patch16", "openai/clip-vit-base-patch32"}
        },
        "scene_visual_embeddings_clip": {
            "expected_dim": clip_dim,
            "allowed_modalities": {"video"},
            "allowed_backends": {"qdrant", "faiss"},
            "allowed_collections": {clip_collection, "clip"},
            "allowed_model_tags": {"openai/clip-vit-large-patch14"}
        },
        "scene_visual_embeddings_dino": {
            "expected_dim": dino_dim,
            "allowed_modalities": {"video"},
            "allowed_backends": {"qdrant", "faiss"},
            "allowed_collections": {dino_collection, "dino"},
            "allowed_model_tags": {"facebook/dinov2-large"}
        },
        "audio_embed_clap": {
            "expected_dim": audio_dim,
            "allowed_modalities": {"audio"},
            "allowed_backends": {"qdrant", "faiss"},
            "allowed_collections": {audio_collection, "audio", "goodq_audio"},
            "allowed_model_tags": {"laion/clap-htsat-unfused"}
        },
        "text_embed": {
            "expected_dim": text_dim,
            "allowed_modalities": {"text"},
            "allowed_backends": {"qdrant", "faiss"},
            "allowed_collections": {text_collection, "text", "goodq_scene_summaries_384"},
            "allowed_model_tags": {"sentence-transformers/all-MiniLM-L6-v2", "all-MiniLM-L6-v2"}
        }
    }
    
    # Validation Report Structure
    report = {
        "epoch_id": epoch_id,
        "timestamp": "",  # To be filled
        "summary": {
            "success": True,
            "checks_run": 0,
            "checks_failed": 0,
            "total_context_frames_checked": 0,
            "total_videos_checked": 0
        },
        "path_hygiene": {
            "status": "passed",
            "db_path": "",
            "errors": []
        },
        "schema_version": {
            "status": "passed",
            "errors": []
        },
        "promotion_status": {
            "status": "passed",
            "errors": []
        },
        "temporal_bounds": {
            "status": "passed",
            "errors": []
        },
        "payload_hash": {
            "status": "passed",
            "errors": []
        },
        "flatness": {
            "status": "passed",
            "errors": []
        },
        "spatial_region": {
            "status": "passed",
            "errors": []
        },
        "manifest_reconciliation": {
            "status": "passed",
            "errors": []
        },
        "raw_ref_gate": {
            "status": "passed",
            "errors": []
        },
        "scene_overlap_gate": {
            "status": "passed",
            "errors": []
        },
        "raw_reconciliation": {
            "status": "passed",
            "errors": []
        },
        "absolute_timestamps": {
            "status": "passed",
            "errors": []
        },
        "media_sources_gate": {
            "status": "passed",
            "errors": []
        },
        "vector_integrity": {
            "status": "passed",
            "errors": [],
            "warnings": []
        },
        "transcript_coverage": {},
        "per_scene_coverage": []
    }
    
    # Get current DB UTC timestamp
    try:
        temp_conn = sqlite3.connect(":memory:")
        report["timestamp"] = temp_conn.execute("SELECT datetime('now')").fetchone()[0]
        temp_conn.close()
    except Exception:
        report["timestamp"] = "unknown"
    
    # 1. Path Hygiene Check
    if not db_dir:
        report["path_hygiene"]["status"] = "failed"
        report["path_hygiene"]["errors"].append("paths.db_dir config not set.")
    else:
        expected_db_path = Path(db_dir) / 'ucf' / 'ucf_ledger.db'
        report["path_hygiene"]["db_path"] = str(expected_db_path)
        
        # Check if DB actually exists at expected canonical path (db_dir/ucf/)
        if not expected_db_path.exists():
            report["path_hygiene"]["status"] = "failed"
            report["path_hygiene"]["errors"].append(
                f"UCF database not found at canonical path: '{expected_db_path}'."
            )
        else:
            # Canonical path exists!
            # Also verify no legacy database exists at the old reconstructed path
            if data_root:
                root_path = Path(data_root)
                if root_path.name == "GoodQ_Data":
                    root_path = root_path.parent
                legacy_db_path = root_path / 'epochs' / epoch_id / 'ucf' / 'ucf_ledger.db'
                if legacy_db_path.exists() and legacy_db_path.resolve() != expected_db_path.resolve():
                    report["path_hygiene"]["status"] = "failed"
                    report["path_hygiene"]["errors"].append(
                        f"Path hygiene violation: Canonical database exists, but a duplicate legacy database also exists at '{legacy_db_path}'. "
                        f"Please delete the legacy database file to prevent split-brain issues."
                    )
    
    # Determine which database path we should open for remaining checks
    target_db_path = report["path_hygiene"]["db_path"]
    if not target_db_path or not os.path.exists(target_db_path):
        print("ERROR: Cannot perform validation checks because ucf_ledger.db was not found.")
        report["summary"]["success"] = False
        report["summary"]["checks_failed"] += 1
        write_reports(report)
        return 1
            
    # Connect to database
    try:
        conn = sqlite3.connect(target_db_path)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        print(f"ERROR: Failed to connect to database at {target_db_path}: {e}")
        report["summary"]["success"] = False
        report["summary"]["checks_failed"] += 1
        write_reports(report)
        return 1
        
    try:
        # Fetch all media sources
        media_sources = {}
        cur = conn.execute("SELECT video_hash, file_path, duration, fps, width, height FROM media_sources")
        for row in cur.fetchall():
            media_sources[row["video_hash"]] = dict(row)
        report["summary"]["total_videos_checked"] = len(media_sources)
        
        # Fetch all context frames
        cur_cf = conn.execute(
            """
            SELECT frame_id, video_hash, ucf_schema_version, epoch_id, run_id, t_start, t_end,
                   modality, worker_name, model_tag, confidence, spatial_region, spatial_space,
                   vector_key, vector_backend, vector_collection, vector_dim, vector_model_tag,
                   source_artifact_id, raw_ref, payload, payload_hash, promotion_status
            FROM context_frames
            """
        )
        context_frames = [dict(row) for row in cur_cf.fetchall()]
        report["summary"]["total_context_frames_checked"] = len(context_frames)
        
        # 11. Media Sources Registration Gate (Phase 0.4)
        cf_video_hashes = set(cf["video_hash"] for cf in context_frames)
        registered_video_hashes = set(media_sources.keys())
        unregistered_refs = cf_video_hashes - registered_video_hashes
        if unregistered_refs:
            report["media_sources_gate"]["status"] = "failed"
            report["media_sources_gate"]["errors"].append(
                f"Media source gate violation: The following video hashes are referenced by context frames "
                f"but are not registered in the media_sources table: {list(unregistered_refs)}"
            )
        
        # Group scene detect frames by video hash for overlap checking
        scenes_by_video = {}
        for cf in context_frames:
            if cf["worker_name"] == "video_scene_detect":
                scenes_by_video.setdefault(cf["video_hash"], []).append(cf)

        # Map each vector_key to the list/set of frame_ids that reference it
        vector_key_to_frame_ids = {}
        for cf in context_frames:
            v_key = cf.get("vector_key")
            if v_key:
                vector_key_to_frame_ids.setdefault(v_key, set()).add(cf["frame_id"])

        # Check validation logic on each frame
        for cf in context_frames:
            fid = cf["frame_id"]
            vhash = cf["video_hash"]
            
            # Look up duration from media sources
            media = media_sources.get(vhash)
            duration = media["duration"] if media else 0.0
            
            # 2. Schema version check
            if cf["ucf_schema_version"] != "ucf.v0.1":
                report["schema_version"]["status"] = "failed"
                report["schema_version"]["errors"].append(
                    f"Frame {fid}: Schema version must be 'ucf.v0.1', got '{cf['ucf_schema_version']}'"
                )
                
            # 3. Promotion status check
            if cf["promotion_status"] not in {"staged", "validated", "promoted", "rejected", "superseded"}:
                report["promotion_status"]["status"] = "failed"
                report["promotion_status"]["errors"].append(
                    f"Frame {fid}: Invalid promotion status '{cf['promotion_status']}'"
                )
                
            # 4. Temporal bounds check
            t_start = cf["t_start"]
            t_end = cf["t_end"]
            if t_start < 0.0:
                report["temporal_bounds"]["status"] = "failed"
                report["temporal_bounds"]["errors"].append(
                    f"Frame {fid}: Negative t_start ({t_start})"
                )
            if t_end < t_start:
                report["temporal_bounds"]["status"] = "failed"
                report["temporal_bounds"]["errors"].append(
                    f"Frame {fid}: t_end ({t_end}) is before t_start ({t_start})"
                )
            if media and t_end > duration + 0.05: # 50ms tolerance
                report["temporal_bounds"]["status"] = "failed"
                report["temporal_bounds"]["errors"].append(
                    f"Frame {fid}: t_end ({t_end:.3f}) exceeds video duration ({duration:.3f}) beyond 50ms tolerance"
                )
                
            # 5. Payload hash check
            payload_str = cf["payload"]
            payload_hash = cf["payload_hash"]
            try:
                payload_dict = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                canonical_str = json.dumps(payload_dict, sort_keys=True)
                computed_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
                if computed_hash != payload_hash:
                    report["payload_hash"]["status"] = "failed"
                    report["payload_hash"]["errors"].append(
                        f"Frame {fid}: Stored payload_hash '{payload_hash}' does not match computed hash '{computed_hash}'"
                    )
            except Exception as e:
                report["payload_hash"]["status"] = "failed"
                report["payload_hash"]["errors"].append(
                    f"Frame {fid}: Failed to parse or verify payload hash: {e}"
                )
                payload_dict = {}
                
            # 6. Flatness check
            allowed_types = (str, int, float, bool, type(None))
            for k, val in payload_dict.items():
                if not isinstance(val, allowed_types):
                    report["flatness"]["status"] = "failed"
                    report["flatness"]["errors"].append(
                        f"Frame {fid}: Non-flat payload value under key '{k}' (type {type(val)})"
                    )
                    
            # 7. Spatial region check
            s_region = cf["spatial_region"]
            if s_region is not None:
                try:
                    region = json.loads(s_region) if isinstance(s_region, str) else s_region
                    if region is not None:
                        if len(region) != 4:
                            report["spatial_region"]["status"] = "failed"
                            report["spatial_region"]["errors"].append(
                                f"Frame {fid}: Spatial region must be list of exactly 4 elements"
                            )
                        else:
                            for val in region:
                                if not (0.0 <= val <= 1.0):
                                    report["spatial_region"]["status"] = "failed"
                                    report["spatial_region"]["errors"].append(
                                        f"Frame {fid}: Spatial region value {val} not normalized (0.0 - 1.0)"
                                    )
                            if region[0] > region[2] or region[1] > region[3]:
                                report["spatial_region"]["status"] = "failed"
                                report["spatial_region"]["errors"].append(
                                    f"Frame {fid}: Invalid bounding box bounds [ymin={region[0]}, xmin={region[1]}, ymax={region[2]}, xmax={region[3]}]"
                                )
                except Exception as e:
                    report["spatial_region"]["status"] = "failed"
                    report["spatial_region"]["errors"].append(
                        f"Frame {fid}: Failed to parse spatial region: {e}"
                    )
                    
            # 9. Raw Ref Gate
            if cf["modality"] in ("audio", "text") or cf["worker_name"] in ("object_detect", "face_embed", "image_embed_dino", "image_embed_clip", "scene_visual_embeddings_dino", "scene_visual_embeddings_clip"):
                raw_ref = cf.get("raw_ref")
                if not raw_ref:
                    report["raw_ref_gate"]["status"] = "failed"
                    report["raw_ref_gate"]["errors"].append(
                        f"Frame {fid}: Modality '{cf['modality']}' has missing or empty raw_ref"
                    )
                else:
                    resolved_raw_ref = os.path.expandvars(raw_ref)
                    if not os.path.exists(resolved_raw_ref):
                        report["raw_ref_gate"]["status"] = "failed"
                        report["raw_ref_gate"]["errors"].append(
                            f"Frame {fid}: raw_ref file does not exist on disk: '{resolved_raw_ref}' (raw_ref: '{raw_ref}')"
                        )

            # 10. Scene Overlap Gate
            if cf["worker_name"] == "audio_transcribe":
                video_scenes = scenes_by_video.get(cf["video_hash"], [])
                if video_scenes:
                    has_overlap = any(
                        is_overlapping(cf["t_start"], cf["t_end"], sf["t_start"], sf["t_end"])
                        for sf in video_scenes
                    )
                    if not has_overlap:
                        report["scene_overlap_gate"]["status"] = "failed"
                        report["scene_overlap_gate"]["errors"].append(
                            f"Frame {fid}: Transcript segment [{cf['t_start']:.3f}, {cf['t_end']:.3f}] does not overlap with any video scene detect frame"
                        )
                # else: no scene_detect frames for this video — skip gate;
                # manifest_reconciliation will catch the missing scene detect frames.

            # 12. Vector Reference Integrity Gate (Phase 0.7)
            if cf.get("vector_key") is not None:
                worker_name = cf["worker_name"]
                backend = cf["vector_backend"]
                collection = cf["vector_collection"]
                dim = cf["vector_dim"]
                model_tag = cf["vector_model_tag"]
                key = cf["vector_key"]
                
                # Check 1: Identity & Vector Registry Schema Validation
                if worker_name not in VECTOR_REGISTRY:
                    report["vector_integrity"]["status"] = "failed"
                    report["vector_integrity"]["errors"].append(
                        f"Frame {fid}: Worker '{worker_name}' is not registered in VECTOR_REGISTRY"
                    )
                else:
                    reg = VECTOR_REGISTRY[worker_name]
                    # Compare vector_dim
                    if dim != reg["expected_dim"]:
                        report["vector_integrity"]["status"] = "failed"
                        report["vector_integrity"]["errors"].append(
                            f"Frame {fid}: Dimension mismatch for '{worker_name}'. Expected {reg['expected_dim']}, got {dim}"
                        )
                    # Compare modality
                    if cf["modality"] not in reg["allowed_modalities"]:
                        report["vector_integrity"]["status"] = "failed"
                        report["vector_integrity"]["errors"].append(
                            f"Frame {fid}: Modality mismatch for '{worker_name}'. Expected one of {reg['allowed_modalities']}, got '{cf['modality']}'"
                        )
                    # Compare backend
                    if backend not in reg["allowed_backends"]:
                        report["vector_integrity"]["status"] = "failed"
                        report["vector_integrity"]["errors"].append(
                            f"Frame {fid}: Backend '{backend}' not allowed for '{worker_name}'"
                        )
                    # Compare collection
                    if collection not in reg["allowed_collections"]:
                        report["vector_integrity"]["status"] = "failed"
                        report["vector_integrity"]["errors"].append(
                            f"Frame {fid}: Collection '{collection}' not allowed for '{worker_name}'"
                        )
                    # Compare model_tag
                    if model_tag not in reg["allowed_model_tags"]:
                        report["vector_integrity"]["status"] = "failed"
                        report["vector_integrity"]["errors"].append(
                            f"Frame {fid}: Model tag mismatch for '{worker_name}'. Expected one of {reg['allowed_model_tags']}, got '{model_tag}'"
                        )
                
                # Check 2: Vector Key Format Validation
                if not validate_vector_key(key, backend):
                    report["vector_integrity"]["status"] = "failed"
                    report["vector_integrity"]["errors"].append(
                        f"Frame {fid}: Malformed vector key '{key}' for backend '{backend}'"
                    )
                
                if backend == "faiss":
                    try:
                        p_dict = json.loads(cf["payload"]) if isinstance(cf["payload"], str) else cf["payload"]
                        faiss_id = p_dict.get("faiss_id")
                        if faiss_id is None:
                            report["vector_integrity"]["status"] = "failed"
                            report["vector_integrity"]["errors"].append(
                                f"Frame {fid}: FAISS record missing 'faiss_id' in payload"
                            )
                        elif not isinstance(faiss_id, int):
                            report["vector_integrity"]["status"] = "failed"
                            report["vector_integrity"]["errors"].append(
                                f"Frame {fid}: FAISS 'faiss_id' in payload must be an integer, got {type(faiss_id)}"
                            )
                    except Exception as e:
                        report["vector_integrity"]["status"] = "failed"
                        report["vector_integrity"]["errors"].append(
                            f"Frame {fid}: Failed to parse payload: {e}"
                        )
                
                # Check 3: Live backend point existence and payload checks (online/strict modes)
                if mode in ("online", "strict"):
                    if backend == "qdrant":
                        try:
                            # Retrieve the point from Qdrant
                            normalized_key = normalize_qdrant_id(key)
                            url = f"{qdrant_host}/collections/{collection}/points"
                            r = requests.post(url, json={"ids": [normalized_key], "with_payload": True, "with_vector": False}, timeout=5)
                            if r.status_code != 200:
                                report["vector_integrity"]["status"] = "failed"
                                report["vector_integrity"]["errors"].append(
                                    f"Frame {fid}: Qdrant request to {url} failed with status {r.status_code}: {r.text}"
                                )
                            else:
                                points = r.json().get("result", [])
                                if not points:
                                    report["vector_integrity"]["status"] = "failed"
                                    report["vector_integrity"]["errors"].append(
                                        f"Frame {fid}: Qdrant point '{key}' not found in collection '{collection}'"
                                    )
                                else:
                                    p_payload = points[0].get("payload") or {}
                                    
                                    # Normalize video_hash / video_id
                                    p_video_hash = p_payload.get("video_hash") or p_payload.get("video_id")
                                    p_scene_id = p_payload.get("scene_id")
                                    p_modality = p_payload.get("modality")
                                    p_worker_name = p_payload.get("worker_name")
                                    p_vector_model_tag = p_payload.get("vector_model_tag") or p_payload.get("model")
                                    p_epoch_id = p_payload.get("epoch_id")
                                    p_scene_hash = p_payload.get("scene_hash")
                                    p_ucf_frame_id = p_payload.get("ucf_frame_id")
                                    
                                    if p_video_hash != cf["video_hash"]:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: Qdrant point video_hash mismatch. Expected '{cf['video_hash']}', got '{p_video_hash}'"
                                        )
                                    if p_scene_id != cf["source_artifact_id"]:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: Qdrant point scene_id mismatch. Expected '{cf['source_artifact_id']}', got '{p_scene_id}'"
                                        )
                                    
                                    # Modality, worker, and tag verification
                                    if worker_name in ("image_embed_clip", "scene_visual_embeddings_clip"):
                                        expected_modality = "video"
                                        expected_worker = worker_name
                                        expected_tag = "openai/clip-vit-large-patch14"
                                    elif worker_name in ("image_embed_dino", "scene_visual_embeddings_dino"):
                                        expected_modality = "video"
                                        expected_worker = worker_name
                                        expected_tag = "facebook/dinov2-large"
                                    elif worker_name == "audio_embed_clap":
                                        expected_modality = "audio"
                                        expected_worker = "audio_embed_clap"
                                        expected_tag = "laion/clap-htsat-unfused"
                                    elif worker_name == "text_embed":
                                        expected_modality = "text"
                                        expected_worker = "text_embed"
                                        expected_tag = cf.get("vector_model_tag", "sentence-transformers/all-MiniLM-L6-v2")
                                    else:
                                        expected_modality = cf["modality"]
                                        expected_worker = worker_name
                                        expected_tag = cf.get("vector_model_tag", "")
                                        
                                    is_modality_match = (p_modality == expected_modality) or (
                                        p_modality == worker_name.split("_")[-1]
                                    ) or (
                                        expected_modality == "text" and p_modality == "audio_transcript"
                                    )
                                    if p_modality and not is_modality_match:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: Qdrant point modality mismatch. Expected '{expected_modality}', got '{p_modality}'"
                                        )
                                        
                                    is_worker_match = (p_worker_name == expected_worker) or (
                                        expected_worker == "scene_visual_embeddings_clip" and p_worker_name == "image_embed_clip"
                                    ) or (
                                        expected_worker == "scene_visual_embeddings_dino" and p_worker_name == "image_embed_dino"
                                    )
                                    if p_worker_name and not is_worker_match:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: Qdrant point worker_name mismatch. Expected '{expected_worker}', got '{p_worker_name}'"
                                        )
                                        
                                    if p_vector_model_tag and p_vector_model_tag != expected_tag and p_vector_model_tag != worker_name.split("_")[-1]:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: Qdrant point vector_model_tag mismatch. Expected '{expected_tag}', got '{p_vector_model_tag}'"
                                        )
                                        
                                    if p_epoch_id and p_epoch_id != cf["epoch_id"]:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: Qdrant point epoch_id mismatch. Expected '{cf['epoch_id']}', got '{p_epoch_id}'"
                                        )
                                        
                                    if p_scene_hash and p_scene_hash != cf["vector_key"]:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: Qdrant point scene_hash mismatch. Expected '{cf['vector_key']}', got '{p_scene_hash}'"
                                        )
                                        
                                    allowed_fids = vector_key_to_frame_ids.get(cf["vector_key"], {cf["frame_id"]})
                                    if p_ucf_frame_id is not None and int(p_ucf_frame_id) not in allowed_fids:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: Qdrant point ucf_frame_id mismatch. Expected one of {allowed_fids}, got {p_ucf_frame_id}"
                                        )
                                        
                                    if mode == "strict":
                                        if not p_epoch_id and worker_name != "audio_embed_clap":
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: Qdrant point payload missing 'epoch_id' in strict mode"
                                            )
                                        if not p_scene_hash and worker_name not in ("scene_visual_embeddings_clip", "scene_visual_embeddings_dino", "audio_embed_clap"):
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: Qdrant point payload missing 'scene_hash' in strict mode"
                                            )
                                        if p_ucf_frame_id is None:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: Qdrant point payload missing 'ucf_frame_id' in strict mode"
                                            )
                        except requests.exceptions.RequestException as e:
                            msg = f"Qdrant connection error to host {qdrant_host}: {e}"
                            if mode == "strict":
                                report["vector_integrity"]["status"] = "failed"
                                report["vector_integrity"]["errors"].append(msg)
                            else:
                                report["vector_integrity"]["warnings"].append(msg)
                                
                    elif backend == "faiss":
                        if worker_name in ("image_embed_clip", "scene_visual_embeddings_clip"):
                            faiss_index_path_str = clip_index_path
                            sidecar_db_path_str = clip_map_db
                        elif worker_name in ("image_embed_dino", "scene_visual_embeddings_dino"):
                            faiss_index_path_str = dino_index_path
                            sidecar_db_path_str = dino_map_db
                        elif worker_name == "audio_embed_clap":
                            faiss_index_path_str = audio_index_path
                            sidecar_db_path_str = clap_map_db
                        elif worker_name == "text_embed":
                            faiss_index_path_str = text_index_path
                            sidecar_db_path_str = memory_db_path
                        else:
                            faiss_index_path_str = None
                            sidecar_db_path_str = None
                        faiss_index_path = resolve_path(faiss_index_path_str)
                        sidecar_db_path = resolve_path(sidecar_db_path_str)
                        
                        # Verify sidecar DB exists and matches
                        if not sidecar_db_path or not sidecar_db_path.exists():
                            msg = f"FAISS sidecar map DB does not exist: {sidecar_db_path}"
                            if mode == "strict":
                                report["vector_integrity"]["status"] = "failed"
                                report["vector_integrity"]["errors"].append(msg)
                            else:
                                report["vector_integrity"]["warnings"].append(msg)
                        else:
                            try:
                                try:
                                    p_dict = json.loads(cf["payload"]) if isinstance(cf["payload"], str) else cf["payload"]
                                    faiss_id = int(p_dict.get("faiss_id"))
                                except Exception:
                                    faiss_id = None
                                    
                                if faiss_id is not None:
                                    sidecar_conn = sqlite3.connect(str(sidecar_db_path))
                                    sidecar_conn.row_factory = sqlite3.Row
                                    if worker_name in ("image_embed_clip", "scene_visual_embeddings_clip"):
                                        table_name = "clip_id_map"
                                    elif worker_name in ("image_embed_dino", "scene_visual_embeddings_dino"):
                                        table_name = "dino_id_map"
                                    elif worker_name == "audio_embed_clap":
                                        table_name = "clap_id_map"
                                    elif worker_name == "text_embed":
                                        table_name = "embeddings"
                                    else:
                                        sidecar_conn.close()
                                        table_name = None
                                    
                                    if table_name:
                                        # Check if video_hash column exists to query with composite key if available
                                        cursor_cols = sidecar_conn.execute(f"PRAGMA table_info({table_name})")
                                        columns = [r[1] for r in cursor_cols.fetchall()]
                                        
                                        if "video_hash" in columns:
                                            cursor = sidecar_conn.execute(
                                                f"SELECT * FROM {table_name} WHERE video_hash = ? AND faiss_id = ?",
                                                (cf["video_hash"], faiss_id)
                                            )
                                        else:
                                            cursor = sidecar_conn.execute(
                                                f"SELECT * FROM {table_name} WHERE faiss_id = ?",
                                                (faiss_id,)
                                            )
                                        row = cursor.fetchone()
                                    else:
                                        row = None

                                    if not row:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: FAISS ID {faiss_id} not found in sidecar database {sidecar_db_path}"
                                        )
                                    else:
                                        db_hash = row["hash"]
                                        db_source_path = row["source_path"]
                                        row_keys = row.keys()
                                        
                                        if db_hash != key:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: FAISS ID {faiss_id} hash mismatch. Expected '{key}', got '{db_hash}'"
                                            )
                                        if Path(db_source_path).name.startswith("scene_") and Path(db_source_path).stem != cf["source_artifact_id"]:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: FAISS ID {faiss_id} source_path stem '{Path(db_source_path).stem}' does not match scene ID '{cf['source_artifact_id']}'"
                                            )
                                            
                                        # Strict checks on identity columns
                                        db_epoch_id = row["epoch_id"] if "epoch_id" in row_keys else None
                                        db_video_hash = row["video_hash"] if "video_hash" in row_keys else None
                                        db_scene_id = row["scene_id"] if "scene_id" in row_keys else None
                                        db_worker_name = row["worker_name"] if "worker_name" in row_keys else None
                                        db_vector_model_tag = row["vector_model_tag"] if "vector_model_tag" in row_keys else None
                                        db_modality = row["modality"] if "modality" in row_keys else None
                                        db_ucf_frame_id = row["ucf_frame_id"] if "ucf_frame_id" in row_keys else None
                                        
                                        if db_epoch_id and db_epoch_id != cf["epoch_id"]:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: FAISS sidecar epoch_id mismatch. Expected '{cf['epoch_id']}', got '{db_epoch_id}'"
                                            )
                                        if db_video_hash and db_video_hash != cf["video_hash"]:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: FAISS sidecar video_hash mismatch. Expected '{cf['video_hash']}', got '{db_video_hash}'"
                                            )
                                        if db_scene_id and db_scene_id != cf["source_artifact_id"]:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: FAISS sidecar scene_id mismatch. Expected '{cf['source_artifact_id']}', got '{db_scene_id}'"
                                            )
                                        is_faiss_worker_match = (db_worker_name == cf["worker_name"]) or (
                                            cf["worker_name"] == "scene_visual_embeddings_clip" and db_worker_name == "image_embed_clip"
                                        ) or (
                                            cf["worker_name"] == "scene_visual_embeddings_dino" and db_worker_name == "image_embed_dino"
                                        )
                                        if db_worker_name and not is_faiss_worker_match:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: FAISS sidecar worker_name mismatch. Expected '{cf['worker_name']}', got '{db_worker_name}'"
                                            )
                                        if db_vector_model_tag and db_vector_model_tag != cf["vector_model_tag"]:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: FAISS sidecar vector_model_tag mismatch. Expected '{cf['vector_model_tag']}', got '{db_vector_model_tag}'"
                                            )
                                        if db_modality and db_modality != cf["modality"]:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: FAISS sidecar modality mismatch. Expected '{cf['modality']}', got '{db_modality}'"
                                            )
                                        allowed_fids = vector_key_to_frame_ids.get(cf["vector_key"], {cf["frame_id"]})
                                        if db_ucf_frame_id is not None and int(db_ucf_frame_id) not in allowed_fids:
                                            report["vector_integrity"]["status"] = "failed"
                                            report["vector_integrity"]["errors"].append(
                                                f"Frame {fid}: FAISS sidecar ucf_frame_id mismatch. Expected one of {allowed_fids}, got {db_ucf_frame_id}"
                                            )
                                            
                                        if mode == "strict":
                                            if not db_epoch_id:
                                                report["vector_integrity"]["status"] = "failed"
                                                report["vector_integrity"]["errors"].append(
                                                    f"Frame {fid}: FAISS sidecar missing 'epoch_id' in strict mode"
                                                )
                                            if not db_video_hash:
                                                report["vector_integrity"]["status"] = "failed"
                                                report["vector_integrity"]["errors"].append(
                                                    f"Frame {fid}: FAISS sidecar missing 'video_hash' in strict mode"
                                                )
                                            if db_ucf_frame_id is None:
                                                report["vector_integrity"]["status"] = "failed"
                                                report["vector_integrity"]["errors"].append(
                                                    f"Frame {fid}: FAISS sidecar missing 'ucf_frame_id' in strict mode"
                                                )
                                    sidecar_conn.close()
                            except Exception as e:
                                report["vector_integrity"]["status"] = "failed"
                                report["vector_integrity"]["errors"].append(
                                    f"Frame {fid}: Failed to query FAISS sidecar DB at {sidecar_db_path}: {e}"
                                )
                                
                        # Verify Index exists and load it
                        if not faiss_index_path or not faiss_index_path.exists():
                            msg = f"FAISS index file does not exist: {faiss_index_path}"
                            if mode == "strict":
                                report["vector_integrity"]["status"] = "failed"
                                report["vector_integrity"]["errors"].append(msg)
                            else:
                                report["vector_integrity"]["warnings"].append(msg)
                        else:
                            try:
                                import faiss
                                index = faiss.read_index(str(faiss_index_path))
                                if not hasattr(index, "id_map"):
                                    msg = f"FAISS index {faiss_index_path} does not support ID map (no id_map attribute)"
                                    if mode == "strict":
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(msg)
                                    else:
                                        report["vector_integrity"]["warnings"].append(msg)
                                else:
                                    import numpy as np
                                    ids = faiss.vector_to_array(index.id_map)
                                    if faiss_id is not None and faiss_id not in ids:
                                        report["vector_integrity"]["status"] = "failed"
                                        report["vector_integrity"]["errors"].append(
                                            f"Frame {fid}: FAISS ID {faiss_id} not present in FAISS index file {faiss_index_path}"
                                        )
                            except Exception as e:
                                report["vector_integrity"]["status"] = "failed"
                                report["vector_integrity"]["errors"].append(
                                    f"Frame {fid}: Failed to load/verify FAISS index at {faiss_index_path}: {e}"
                                )
                    
        # 8. Scene Manifest 1-to-1 Reconciliation Check
        processing_root = Path(cfg.get('paths', {}).get('processing', ''))
        # If processing is relative or needs to be resolved with data_root
        if not processing_root.is_absolute() and data_root:
            processing_root = Path(data_root) / 'epochs' / epoch_id / 'processing'
            
        for vhash, media in media_sources.items():
            file_path = Path(media["file_path"])
            video_stem = file_path.stem
            
            # Canonical path to scene_manifest.json
            manifest_path = processing_root / video_stem / 'video' / 'scene_manifest.json'
            if not manifest_path.exists():
                manifest_path = processing_root / video_stem / 'scene_manifest.json'
                
            if not manifest_path.exists():
                report["manifest_reconciliation"]["status"] = "warning"
                report["manifest_reconciliation"]["errors"].append(
                    f"Video {video_stem}: scene_manifest.json not found under '{processing_root / video_stem}'"
                )
                continue
                
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                manifest_scenes = manifest_data.get('scenes', [])
                
                # Fetch ucf context frames logged by video_scene_detect
                ucf_scenes = [
                    cf for cf in context_frames
                    if cf["video_hash"] == vhash and cf["worker_name"] == "video_scene_detect"
                ]
                
                # Compare sizes
                if len(manifest_scenes) != len(ucf_scenes):
                    report["manifest_reconciliation"]["status"] = "failed"
                    report["manifest_reconciliation"]["errors"].append(
                        f"Video {video_stem}: Count mismatch. Manifest has {len(manifest_scenes)} scenes, "
                        f"but UCF has {len(ucf_scenes)} context frames for 'video_scene_detect'."
                    )
                
                # Check 1-to-1 correlation (by index or time bounds within 50ms)
                # Map manifest scenes by index
                manifest_by_idx = {int(s.get('index', i)): s for i, s in enumerate(manifest_scenes)}
                ucf_by_idx = {}
                for cf in ucf_scenes:
                    # Get index from payload
                    try:
                        p_dict = json.loads(cf["payload"]) if isinstance(cf["payload"], str) else cf["payload"]
                        idx = p_dict.get("scene_index")
                        if idx is not None:
                            ucf_by_idx[int(idx)] = cf
                    except Exception:
                        pass
                
                for idx, m_scene in manifest_by_idx.items():
                    cf = ucf_by_idx.get(idx)
                    if cf is None:
                        report["manifest_reconciliation"]["status"] = "failed"
                        report["manifest_reconciliation"]["errors"].append(
                            f"Video {video_stem}: Manifest scene {idx} has no corresponding UCF context frame."
                        )
                    else:
                        # Compare timestamps with 50ms tolerance
                        m_start = float(m_scene.get('start', 0.0))
                        m_end = float(m_scene.get('end', 0.0))
                        cf_start = cf["t_start"]
                        cf_end = cf["t_end"]
                        
                        if abs(m_start - cf_start) > 0.05 or abs(m_end - cf_end) > 0.05:
                            report["manifest_reconciliation"]["status"] = "failed"
                            report["manifest_reconciliation"]["errors"].append(
                                f"Video {video_stem}: Temporal mismatch on scene {idx}. "
                                f"Manifest: [{m_start:.3f}, {m_end:.3f}], UCF: [{cf_start:.3f}, {cf_end:.3f}]"
                            )
                            
                # Check for orphans: UCF scenes that don't exist in manifest
                for idx, cf in ucf_by_idx.items():
                    if idx not in manifest_by_idx:
                        report["manifest_reconciliation"]["status"] = "failed"
                        report["manifest_reconciliation"]["errors"].append(
                            f"Video {video_stem}: Orphan context frame index {idx} in UCF not found in scene_manifest.json."
                        )
                        
            except Exception as e:
                report["manifest_reconciliation"]["status"] = "failed"
                report["manifest_reconciliation"]["errors"].append(
                    f"Video {video_stem}: Failed to read or reconcile manifest: {e}"
                )

        # --- Grouping and Video-Level Auditing (Phase 0.3b) ---
        scenes_by_video_local = {}
        transcripts_by_video_local = {}
        speaker_turns_by_video_local = {}
        for cf in context_frames:
            vh = cf["video_hash"]
            if cf["worker_name"] == "video_scene_detect":
                scenes_by_video_local.setdefault(vh, []).append(cf)
            elif cf["worker_name"] == "audio_transcribe":
                transcripts_by_video_local.setdefault(vh, []).append(cf)
            elif cf["worker_name"] == "speaker_merge":
                speaker_turns_by_video_local.setdefault(vh, []).append(cf)

        global_scene_bins = set()
        global_transcript_bins = set()
        total_scene_duration = 0.0
        total_transcript_duration = 0.0
        
        orphan_audio_segments = 0
        cross_boundary_segments = 0
        silent_scenes_by_type = {}
        per_scene_coverage = []

        for vh, media in media_sources.items():
            file_path = Path(media["file_path"])
            video_stem = file_path.stem
            
            video_scenes = scenes_by_video_local.get(vh, [])
            video_transcripts = transcripts_by_video_local.get(vh, [])
            video_speaker_turns = speaker_turns_by_video_local.get(vh, [])
            
            # Map scenes by scene_hash
            scenes_by_hash = {make_scene_hash(vh, sf["t_start"], sf["t_end"]): sf for sf in video_scenes}
            
            # 1. Absolute-vs-Scene-Relative Timestamp Check (R4)
            for tf in video_transcripts:
                sf = scenes_by_hash.get(tf["source_artifact_id"])
                if sf:
                    if tf["t_start"] < sf["t_start"] - 5.0 or tf["t_end"] > sf["t_end"] + 5.0:
                        msg = (
                            f"Frame {tf['frame_id']} ({tf['worker_name']}): Event bounds [{tf['t_start']:.3f}, {tf['t_end']:.3f}] "
                            f"are out of scene {sf['source_artifact_id']} absolute bounds [{sf['t_start']:.3f}, {sf['t_end']:.3f}]."
                        )
                        report["absolute_timestamps"]["status"] = "failed"
                        report["absolute_timestamps"]["errors"].append(msg)
                        
            for df in video_speaker_turns:
                sf = scenes_by_hash.get(df["source_artifact_id"])
                if sf:
                    if df["t_start"] < sf["t_start"] - 5.0 or df["t_end"] > sf["t_end"] + 5.0:
                        msg = (
                            f"Frame {df['frame_id']} ({df['worker_name']}): Event bounds [{df['t_start']:.3f}, {df['t_end']:.3f}] "
                            f"are out of scene {sf['source_artifact_id']} absolute bounds [{sf['t_start']:.3f}, {sf['t_end']:.3f}]."
                        )
                        report["absolute_timestamps"]["status"] = "failed"
                        report["absolute_timestamps"]["errors"].append(msg)

            # Calculate durations and bins
            for sf in video_scenes:
                total_scene_duration += sf["t_end"] - sf["t_start"]
                start_bin = int(sf["t_start"] * 10)
                end_bin = int(sf["t_end"] * 10)
                for b in range(start_bin, end_bin + 1):
                    global_scene_bins.add((vh, b))
                        
            for tf in video_transcripts:
                total_transcript_duration += tf["t_end"] - tf["t_start"]
                start_bin = int(tf["t_start"] * 10)
                end_bin = int(tf["t_end"] * 10)
                for b in range(start_bin, end_bin + 1):
                    global_transcript_bins.add((vh, b))

            # Cross boundary / orphan checks
            for tf in video_transcripts:
                overlaps = 0
                for sf in video_scenes:
                    if is_overlapping(tf["t_start"], tf["t_end"], sf["t_start"], sf["t_end"]):
                        overlaps += 1
                if overlaps == 0:
                    orphan_audio_segments += 1
                elif overlaps > 1:
                    cross_boundary_segments += 1

            # Check if this video has any raw files at all
            video_has_any_raw = False
            for sf in video_scenes:
                scene_id = sf["source_artifact_id"]
                scene_hash = make_scene_hash(vh, sf["t_start"], sf["t_end"])
                t_path = processing_root / video_stem / 'audio' / f"{scene_hash}_raw_transcript.json"
                d_path = processing_root / video_stem / 'audio' / f"{scene_hash}_raw_diarization.json"
                if t_path.exists() or d_path.exists():
                    video_has_any_raw = True
                    break

            # Per-scene Analysis
            for sf in video_scenes:
                scene_id = sf["source_artifact_id"]
                scene_dur = sf["t_end"] - sf["t_start"]
                
                # Compute the scene hash to match with audio/text source_artifact_id
                scene_hash = make_scene_hash(vh, sf["t_start"], sf["t_end"])
                
                overlapping_trans = [tf for tf in video_transcripts if tf["source_artifact_id"] == scene_hash]
                overlapping_turns = [df for df in video_speaker_turns if df["source_artifact_id"] == scene_hash]
                
                seg_count = len(overlapping_trans)
                turn_count = len(overlapping_turns)
                
                t_dur = sum(
                    min(tf["t_end"], sf["t_end"]) - max(tf["t_start"], sf["t_start"])
                    for tf in overlapping_trans
                )
                
                # Coverage percentage
                scene_bins = set(range(int(sf["t_start"] * 10), int(sf["t_end"] * 10) + 1))
                transcript_bins = set()
                for tf in overlapping_trans:
                    start_bin = int(tf["t_start"] * 10)
                    end_bin = int(tf["t_end"] * 10)
                    for b in range(start_bin, end_bin + 1):
                        transcript_bins.add(b)
                overlap_bins = scene_bins.intersection(transcript_bins)
                cov_pct = (len(overlap_bins) / len(scene_bins)) * 100.0 if len(scene_bins) > 0 else 0.0
                
                # Reconciliations and Silent Classifications
                scene_idx = 0
                try:
                    p_dict = json.loads(sf["payload"]) if isinstance(sf["payload"], str) else sf["payload"]
                    scene_idx = int(p_dict.get("scene_index", 0))
                except Exception:
                    pass
                    
                raw_transcript_path = processing_root / video_stem / 'audio' / f"{scene_hash}_raw_transcript.json"
                raw_diarization_path = processing_root / video_stem / 'audio' / f"{scene_hash}_raw_diarization.json"
                wav_path = processing_root / video_stem / 'audio' / 'chunks' / f"scene_{scene_idx:04d}.wav"
                
                t_exists = raw_transcript_path.exists()
                d_exists = raw_diarization_path.exists()
                w_exists = wav_path.exists()
                
                raw_ref_ok = True
                
                # 2. Raw Transcript Reconciliation (R2)
                raw_segments_count = 0
                if t_exists:
                    try:
                        with open(raw_transcript_path, 'r', encoding='utf-8') as rf:
                            raw_data = json.load(rf)
                        raw_segments_count = len(raw_data) if isinstance(raw_data, list) else 0
                        
                        if raw_segments_count != seg_count:
                            msg = (
                                f"Reconciliation Mismatch in {video_stem}:{scene_id} ({scene_hash[:8]}...): "
                                f"Raw transcript segments count = {raw_segments_count}, but UCF text events count = {seg_count}."
                            )
                            report["raw_reconciliation"]["status"] = "failed"
                            report["raw_reconciliation"]["errors"].append(msg)
                    except Exception as e:
                        raw_ref_ok = False
                        report["raw_reconciliation"]["status"] = "failed"
                        report["raw_reconciliation"]["errors"].append(f"Failed to parse raw transcript for {scene_id} ({scene_hash[:8]}...): {e}")
                else:
                    if seg_count > 0:
                        raw_ref_ok = False
                        report["raw_reconciliation"]["status"] = "failed"
                        report["raw_reconciliation"]["errors"].append(f"Raw transcript file missing for scene {scene_id} ({scene_hash[:8]}...) which has UCF events.")
                
                # 3. Raw Diarization Reconciliation (R3)
                raw_turns_count = 0
                if d_exists:
                    try:
                        with open(raw_diarization_path, 'r', encoding='utf-8') as rf:
                            raw_data = json.load(rf)
                        raw_turns_count = len(raw_data) if isinstance(raw_data, list) else 0
                        
                        if raw_turns_count != turn_count:
                            msg = (
                                f"Reconciliation Mismatch in {video_stem}:{scene_id} ({scene_hash[:8]}...): "
                                f"Raw diarization turns count = {raw_turns_count}, but UCF speaker turn events count = {turn_count}."
                            )
                            report["raw_reconciliation"]["status"] = "failed"
                            report["raw_reconciliation"]["errors"].append(msg)
                    except Exception as e:
                        raw_ref_ok = False
                        report["raw_reconciliation"]["status"] = "failed"
                        report["raw_reconciliation"]["errors"].append(f"Failed to parse raw diarization for {scene_id} ({scene_hash[:8]}...): {e}")
                else:
                    if turn_count > 0:
                        raw_ref_ok = False
                        report["raw_reconciliation"]["status"] = "failed"
                        report["raw_reconciliation"]["errors"].append(f"Raw diarization file missing for scene {scene_id} ({scene_hash[:8]}...) which has UCF events.")

                # Silent scene classification
                if seg_count == 0:
                    classification = "unknown"
                    if t_exists:
                        if raw_segments_count == 0:
                            classification = "speech_not_detected"
                            if d_exists and raw_turns_count == 0:
                                classification = "true_silent"
                        elif raw_segments_count > 0:
                            classification = "below_threshold"
                    else:
                        if not video_has_any_raw:
                            classification = "no_audio_stream"
                        else:
                            if w_exists:
                                classification = "audio_failed"
                            else:
                                classification = "raw_missing"
                                
                    silent_scenes_by_type.setdefault(classification, []).append(f"{video_stem}:{scene_id}")
                    
                per_scene_coverage.append({
                    "video_stem": video_stem,
                    "scene_id": scene_id,
                    "scene_duration": round(scene_dur, 3),
                    "transcript_duration": round(t_dur, 3),
                    "coverage_pct": round(cov_pct, 2),
                    "segment_count": seg_count,
                    "speaker_turn_count": turn_count,
                    "raw_ref_ok": raw_ref_ok
                })

        intersection_bins = global_scene_bins.intersection(global_transcript_bins)
        percent_scene_time_with_transcript = (
            (len(intersection_bins) / len(global_scene_bins)) * 100.0
            if len(global_scene_bins) > 0 else 0.0
        )
        
        report["transcript_coverage"] = {
            "total_scene_duration": round(total_scene_duration, 3),
            "total_transcript_duration": round(total_transcript_duration, 3),
            "percent_scene_time_with_transcript": round(percent_scene_time_with_transcript, 2),
            "orphan_audio_segments": orphan_audio_segments,
            "cross_boundary_segments": cross_boundary_segments,
            "silent_scenes_by_type": silent_scenes_by_type
        }
        report["per_scene_coverage"] = per_scene_coverage

        # Check 4: Scoped Orphan Detection (online/strict modes)
        if mode in ("online", "strict"):
            # 1. Qdrant Scoped Orphans
            for collection in {clip_collection, dino_collection, audio_collection, text_collection}:
                expected_qdrant_keys = set(
                    normalize_qdrant_id(cf["vector_key"]) for cf in context_frames
                    if cf["vector_key"] is not None
                    and cf["vector_collection"] == collection
                )
                
                checked_video_hashes = list(registered_video_hashes)
                qdrant_points = set()
                for vh in checked_video_hashes:
                    next_page_offset = None
                    while True:
                        scroll_payload = {
                            "filter": {
                              "should": [
                                {
                                  "key": "video_hash",
                                  "match": {
                                    "value": vh
                                  }
                                },
                                {
                                  "key": "video_id",
                                  "match": {
                                    "value": vh
                                  }
                                }
                              ]
                            },
                            "limit": 100,
                            "with_payload": True,
                            "with_vector": False
                        }
                        if next_page_offset is not None:
                            scroll_payload["offset"] = next_page_offset
                            
                        try:
                            scroll_url = f"{qdrant_host}/collections/{collection}/points/scroll"
                            scroll_res = requests.post(scroll_url, json=scroll_payload, timeout=5)
                            if scroll_res.status_code == 200:
                                res_obj = scroll_res.json().get("result", {})
                                points_list = res_obj.get("points", [])
                                for pt in points_list:
                                    qdrant_points.add(pt["id"])
                                next_page_offset = res_obj.get("next_page_offset")
                                if not next_page_offset or not points_list:
                                    break
                            else:
                                break
                        except Exception:
                            break
                
                qdrant_orphans = qdrant_points - expected_qdrant_keys
                for orphan_id in qdrant_orphans:
                    msg = f"Orphan vector detected in Qdrant collection '{collection}': '{orphan_id}' (exists in vector store but not in ucf_ledger.db for checked videos)"
                    if mode == "strict":
                        report["vector_integrity"]["status"] = "failed"
                        report["vector_integrity"]["errors"].append(msg)
                    else:
                        report["vector_integrity"]["warnings"].append(msg)

            # 2. FAISS Scoped Orphans
            checked_stems = {Path(media["file_path"]).stem for media in media_sources.values()}
            for worker_name, col_name, idx_path_cfg, map_db_cfg, _table_name in [
                ("image_embed_clip", "clip", clip_index_path, clip_map_db, "clip_id_map"),
                ("image_embed_dino", "dino", dino_index_path, dino_map_db, "dino_id_map"),
                ("audio_embed_clap", "audio", audio_index_path, clap_map_db, "clap_id_map"),
                ("text_embed", "text", text_index_path, memory_db_path, "embeddings"),
            ]:
                faiss_index_path = resolve_path(idx_path_cfg)
                sidecar_db_path = resolve_path(map_db_cfg)
                
                expected_faiss_ids = set()
                for cf in context_frames:
                    is_match = cf["worker_name"] == worker_name or (
                        worker_name == "image_embed_clip" and cf["worker_name"] == "scene_visual_embeddings_clip"
                    ) or (
                        worker_name == "image_embed_dino" and cf["worker_name"] == "scene_visual_embeddings_dino"
                    )
                    if is_match and cf["vector_key"] is not None:
                        try:
                            p_dict = json.loads(cf["payload"]) if isinstance(cf["payload"], str) else cf["payload"]
                            faiss_id = p_dict.get("faiss_id")
                            if faiss_id is None:
                                from steps.common.memory import to_faiss_id
                                faiss_id = to_faiss_id(cf["vector_key"])
                            if faiss_id is not None:
                                expected_faiss_ids.add(int(faiss_id))
                        except Exception:
                            pass
                
                index_ids = set()
                if faiss_index_path and faiss_index_path.exists():
                    try:
                        import faiss
                        index = faiss.read_index(str(faiss_index_path))
                        if hasattr(index, "id_map"):
                            index_ids = set(int(x) for x in faiss.vector_to_array(index.id_map))
                    except Exception:
                        pass
                
                in_scope_index_ids = set()
                if sidecar_db_path and sidecar_db_path.exists():
                    try:
                        sidecar_conn = sqlite3.connect(str(sidecar_db_path))
                        sidecar_conn.row_factory = sqlite3.Row
                        table_name = _table_name
                        if table_name == "embeddings":
                            cursor = sidecar_conn.execute(f"SELECT faiss_id, source_path FROM {table_name} WHERE modality = 'text'")
                        else:
                            cursor = sidecar_conn.execute(f"SELECT faiss_id, source_path FROM {table_name}")
                        for row in cursor.fetchall():
                            fid_val = row["faiss_id"]
                            source_path = row["source_path"]
                            if fid_val in index_ids:
                                stem = get_video_stem_from_source_path(source_path, checked_stems)
                                if stem is not None:
                                    in_scope_index_ids.add(fid_val)
                        sidecar_conn.close()
                    except Exception:
                        pass
                        
                faiss_orphans = in_scope_index_ids - expected_faiss_ids
                for orphan_fid in faiss_orphans:
                    msg = f"Orphan vector detected in FAISS index '{faiss_index_path}': ID {orphan_fid} (exists in index but not in ucf_ledger.db for checked videos)"
                    if mode == "strict":
                        report["vector_integrity"]["status"] = "failed"
                        report["vector_integrity"]["errors"].append(msg)
                    else:
                        report["vector_integrity"]["warnings"].append(msg)
                
    except Exception as e:
        print(f"ERROR: Exception during validation checks: {e}")
        report["summary"]["success"] = False
        
    finally:
        conn.close()
        
    # Aggregate results
    check_categories = [
        "path_hygiene", "schema_version", "promotion_status",
        "temporal_bounds", "payload_hash", "flatness",
        "spatial_region", "manifest_reconciliation",
        "raw_ref_gate", "scene_overlap_gate",
        "raw_reconciliation", "absolute_timestamps", "media_sources_gate",
        "vector_integrity"
    ]
    
    report["summary"]["checks_run"] = len(check_categories)
    failed_categories = []
    
    for cat in check_categories:
        if report[cat]["status"] == "failed":
            report["summary"]["checks_failed"] += 1
            failed_categories.append(cat)
            
    if report["summary"]["checks_failed"] > 0:
        report["summary"]["success"] = False
        print(f"Validation FAILED in categories: {failed_categories}")
    else:
        print("Validation PASSED successfully 100%!")
        
    write_reports(report)
    return 0 if report["summary"]["success"] else 1

def write_reports(report: Dict[str, Any]):
    # Ensure reports folder exists
    reports_dir = REPO_ROOT / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = reports_dir / 'ucf_validation_report.json'
    md_path = reports_dir / 'ucf_validation_report.md'
    
    # Write JSON report
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f"JSON validation report written to '{json_path}'")
    
    # Write Markdown report
    md_content = generate_markdown_report(report)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"Markdown validation report written to '{md_path}'")

def generate_markdown_report(report: Dict[str, Any]) -> str:
    success_str = "✅ PASSED" if report["summary"]["success"] else "❌ FAILED"
    
    md = f"""# UCF Invariant Ingestion Validation Report

- **Epoch ID**: `{report["epoch_id"]}`
- **Verification Time**: `{report["timestamp"]}`
- **Overall Status**: **{success_str}**

## Summary Statistics

- **Checks Executed**: {report["summary"]["checks_run"]}
- **Checks Failed**: {report["summary"]["checks_failed"]}
- **Total Registered Videos**: {report["summary"]["total_videos_checked"]}
- **Total Context Frames Scanned**: {report["summary"]["total_context_frames_checked"]}

## Detailed Checks

| Check Area | Status | Description / Errors |
|------------|--------|----------------------|
"""
    
    categories = [
        ("path_hygiene", "Path Hygiene Check"),
        ("schema_version", "Schema Version (ucf.v0.1)"),
        ("promotion_status", "Promotion Status Verification"),
        ("temporal_bounds", "Temporal Boundaries Check"),
        ("payload_hash", "Payload Hash Integrity Check"),
        ("flatness", "Metadata Flatness Check"),
        ("spatial_region", "Spatial Bounding Box Check"),
        ("manifest_reconciliation", "Scene Manifest 1-to-1 Correlation"),
        ("raw_ref_gate", "Raw Ref Gate Check"),
        ("scene_overlap_gate", "Scene Overlap Gate Check"),
        ("raw_reconciliation", "Raw Ref & Event Reconciliation"),
        ("absolute_timestamps", "Absolute Timeline Alignment Check"),
        ("media_sources_gate", "Media Sources Registration Check"),
        ("vector_integrity", "Vector Reference Integrity Gate")
    ]
    
    for key, name in categories:
        cat_data = report[key]
        status_emoji = "✅ PASSED" if cat_data["status"] == "passed" else ("⚠️ WARNING" if cat_data["status"] == "warning" else "❌ FAILED")
        
        errors = "<br>".join(cat_data["errors"]) if cat_data["errors"] else "No issues detected."
        warnings_list = cat_data.get("warnings", [])
        if warnings_list:
            warnings_str = "<br>".join(f"Warning: {w}" for w in warnings_list)
            if errors != "No issues detected.":
                errors += "<br>" + warnings_str
            else:
                errors = warnings_str
            if cat_data["status"] == "passed":
                status_emoji = "⚠️ WARNING"
        md += f"| {name} | {status_emoji} | {errors} |\n"
        
    cov = report.get("transcript_coverage", {})
    md += f"""
## Transcript Coverage Report

- **Total Scene Duration**: {cov.get('total_scene_duration', 0.0)}s
- **Total Transcript Duration**: {cov.get('total_transcript_duration', 0.0)}s
- **Percent Scene Time with Transcript (100ms bins)**: {cov.get('percent_scene_time_with_transcript', 0.0)}%
- **Orphan Audio Segments**: {cov.get('orphan_audio_segments', 0)}
- **Cross-Boundary Segments**: {cov.get('cross_boundary_segments', 0)}

"""

    # Group per_scene_coverage by video_stem
    by_video = {}
    for entry in report.get("per_scene_coverage", []):
        by_video.setdefault(entry["video_stem"], []).append(entry)
        
    md += "## Per-Scene Coverage Report\n\n"
    for video_stem, entries in by_video.items():
        md += f"### Video: `{video_stem}`\n\n"
        md += "| Scene ID | Scene Duration | Transcript Duration | Coverage Pct | Segment Count | Speaker Turn Count | Raw Ref OK |\n"
        md += "|---|---|---|---|---|---|---|\n"
        for entry in entries:
            ref_emoji = "✅ OK" if entry["raw_ref_ok"] else "❌ ERR"
            md += (
                f"| {entry['scene_id']} | {entry['scene_duration']:.2f}s | {entry['transcript_duration']:.2f}s | "
                f"{entry['coverage_pct']:.2f}% | {entry['segment_count']} | {entry['speaker_turn_count']} | {ref_emoji} |\n"
            )
        md += "\n"

    # Silent Scene classification breakdown
    md += "### Silent Scene Classification Breakdown\n\n"
    silent_types = cov.get("silent_scenes_by_type", {})
    if not silent_types:
        md += "No silent scenes detected.\n"
    else:
        for t, scenes in silent_types.items():
            nice_type = t.replace("_", " ").title()
            md += f"- **{nice_type}** ({len(scenes)} scenes):\n"
            scenes_str = ", ".join(f"`{s}`" for s in scenes[:10])
            if len(scenes) > 10:
                scenes_str += f", and {len(scenes) - 10} more..."
            md += f"  {scenes_str or 'None'}\n"

    md += f"""
## Path Provenance Notes
- Expected Clean Path: `${{GOODQ_DATA_ROOT}}/epochs/<epoch>/ucf/ucf_ledger.db`
- Actual Target Database: `{report["path_hygiene"]["db_path"]}`
"""
    return md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UCF Epoch-level Validator with Vector Reference Integrity Gate")
    parser.add_argument("--mode", choices=["offline", "online", "strict"], default="offline", help="Validation mode")
    args = parser.parse_args()
    sys.exit(run_validation(mode=args.mode))
