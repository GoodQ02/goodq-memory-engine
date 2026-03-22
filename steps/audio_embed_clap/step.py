from __future__ import annotations
# GPU Configuration - Auto-configured on import
from steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats
from steps.common.qdrant_client import build_qdrant_client


from typing import Any, Dict, Optional
from contextlib import nullcontext
import sqlite3
from datetime import datetime
import importlib.util
from pathlib import Path
import audioop
import wave

import os
import logging

logger = logging.getLogger(__name__)


_CLAP_MODEL_ID = "laion/clap-htsat-unfused"
_CLAP = {"model": None, "proc": None, "device": "cpu", "model_dir": None}
_CLAP_INSTALL_HINT = "conda run -n goodq_core python scripts/bootstrap_models.py"
_TORCHAUDIO_INSTALL_HINT = (
    "conda run -n goodq_audio_embed pip install "
    "torchaudio==2.3.1 --extra-index-url https://download.pytorch.org/whl/cu121"
)
_MIN_AUDIO_DURATION_SEC = 0.35
_MIN_AUDIO_BYTES = 512
_SILENCE_RMS_THRESHOLD = 8
_SILENCE_PEAK_THRESHOLD = 24


def _torchaudio_preflight() -> bool:
    if importlib.util.find_spec("torchaudio") is not None:
        return True
    logger.error(
        "audio_embed_clap preflight failed missing_dependency=%s install_hint=\"%s\"",
        "torchaudio",
        _TORCHAUDIO_INSTALL_HINT,
    )
    return False


def _resolve_models_root() -> str:
    from steps.common.config_loader import get_runtime_paths, load_configs

    runtime_paths = get_runtime_paths(load_configs({}), "models_cache")
    return str(Path(runtime_paths["models_cache"]).resolve())


def _configure_model_env() -> Path:
    models_root = Path(_resolve_models_root())
    os.environ["HF_HOME"] = str(models_root)
    os.environ["TORCH_HOME"] = str(models_root)
    os.environ.setdefault("HF_HUB_CACHE", str(models_root / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(models_root / "transformers"))
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    return models_root


def _resolve_local_model_dir(models_root: Path) -> Optional[str]:
    repo_cache = models_root / "hub" / f"models--{_CLAP_MODEL_ID.replace('/', '--')}"
    snapshots_dir = repo_cache / "snapshots"
    refs_main = repo_cache / "refs" / "main"
    required = ("config.json", "preprocessor_config.json", "pytorch_model.bin")
    candidates = []

    if refs_main.is_file():
        revision = refs_main.read_text(encoding="utf-8").strip()
        if revision:
            candidates.append(snapshots_dir / revision)

    if snapshots_dir.is_dir():
        candidates.extend(sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.is_dir():
            continue
        seen.add(candidate)
        if all((candidate / name).is_file() for name in required):
            return str(candidate)
    return None


def _preferred_device() -> str:
    try:
        import torch  # type: ignore

        if getattr(torch, "cuda", None) and torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _should_retry_on_cpu(exc: Exception) -> bool:
    message = f"{type(exc).__name__}: {exc}".lower()
    return any(
        token in message
        for token in (
            "cuda",
            "cublas",
            "cudnn",
            "out of memory",
            "device-side",
            "device type",
            "driver shutting down",
        )
    )


def _inspect_audio_input(path: str) -> Optional[Dict[str, Any]]:
    try:
        file_size = os.path.getsize(path)
    except OSError as exc:
        return {"status": "skipped", "reason": "audio_stat_failed", "error": str(exc)}
    if file_size < _MIN_AUDIO_BYTES:
        return {"status": "skipped", "reason": "audio_too_small", "bytes": file_size}

    if Path(path).suffix.lower() != ".wav":
        return None

    try:
        with wave.open(path, "rb") as wav:
            frame_count = wav.getnframes()
            sample_rate = wav.getframerate()
            sample_width = wav.getsampwidth()
            if frame_count <= 0 or sample_rate <= 0 or sample_width <= 0:
                return {"status": "skipped", "reason": "invalid_audio"}

            duration_sec = frame_count / float(sample_rate)
            if duration_sec < _MIN_AUDIO_DURATION_SEC:
                return {
                    "status": "skipped",
                    "reason": "audio_too_short",
                    "duration_sec": round(duration_sec, 4),
                }

            raw = wav.readframes(frame_count)
            if not raw:
                return {"status": "skipped", "reason": "audio_empty"}

            rms = int(audioop.rms(raw, sample_width))
            peak = int(audioop.max(raw, sample_width))
            if rms <= _SILENCE_RMS_THRESHOLD and peak <= _SILENCE_PEAK_THRESHOLD:
                return {
                    "status": "skipped",
                    "reason": "audio_silent",
                    "duration_sec": round(duration_sec, 4),
                }
    except (wave.Error, EOFError, OSError) as exc:
        return {"status": "skipped", "reason": "invalid_audio", "error": str(exc)}

    return None


def _load(preferred_device: Optional[str] = None) -> tuple[bool, Optional[str]]:
    target_device = preferred_device or _preferred_device()
    if _CLAP["model"] is not None:
        if _CLAP["device"] == target_device:
            return True, None
        try:
            _CLAP["model"] = _CLAP["model"].to(target_device).eval()
            _CLAP["device"] = target_device
            return True, None
        except Exception as exc:
            logger.warning(
                "audio_embed_clap model move failed target_device=%s exc_type=%s exc=%s",
                target_device,
                type(exc).__name__,
                exc,
            )
            _CLAP.update({"model": None, "proc": None, "device": "cpu", "model_dir": None})
    try:
        models_root = _configure_model_env()
        model_source = _resolve_local_model_dir(models_root)
        if not model_source:
            logger.warning(
                "audio_embed_clap model cache missing model_id=%s models_root=%s install_hint=\"%s\"",
                _CLAP_MODEL_ID,
                models_root,
                _CLAP_INSTALL_HINT,
            )
            return False, f"model_not_cached:{models_root}"

        import torch  # type: ignore
        from transformers import AutoFeatureExtractor, ClapModel  # type: ignore

        # GPU Isolation - Phase 2
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
        
        device = target_device if target_device == "cpu" or (getattr(torch, "cuda", None) and torch.cuda.is_available()) else "cpu"
        
        # Set memory fraction for this process (20% of GPU)
        if device == "cuda":
            torch.cuda.set_per_process_memory_fraction(0.2, 0)
            torch.backends.cudnn.benchmark = False
            torch.backends.cudnn.deterministic = True
        
        proc = AutoFeatureExtractor.from_pretrained(model_source, local_files_only=True)
        model = ClapModel.from_pretrained(model_source, local_files_only=True).to(device).eval()
        _CLAP.update({"model": model, "proc": proc, "device": device, "model_dir": model_source})
        logger.info("audio_embed_clap model loaded device=%s memory_fraction=%s", device, 0.2)
        return True, None
    except Exception as e:
        logger.error(
            "audio_embed_clap operation failed operation=%s exc_type=%s exc=%s",
            "load_model",
            type(e).__name__,
            e,
        )
        _CLAP.update({"model": None, "proc": None, "device": "cpu", "model_dir": None})
        return False, f"{type(e).__name__}: {e}"


def _ensure_clap_map(db_path: str) -> None:
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        con = sqlite3.connect(db_path, check_same_thread=False)
        with con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS clap_id_map (
                    faiss_id INTEGER PRIMARY KEY,
                    hash TEXT,
                    source_path TEXT,
                    created_at TEXT
                )
                """
            )
    finally:
        try:
            con.close()  # type: ignore
        except Exception as e:
            logger.warning(
                "audio_embed_clap operation failed operation=%s db_path=%s exc_type=%s exc=%s",
                "ensure_clap_map.close",
                db_path,
                type(e).__name__,
                e,
            )


def audio_embed_clap(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"clap_meta": {"status": "no_file"}}
    audio_guard = _inspect_audio_input(path)
    if audio_guard is not None:
        return {"clap_meta": audio_guard}
    if not _torchaudio_preflight():
        return {
            "clap_meta": {
                "status": "unavailable",
                "reason": "missing_torchaudio",
                "install_hint": _TORCHAUDIO_INSTALL_HINT,
            }
        }
    load_ok, load_error = _load(_preferred_device())
    if not load_ok and _preferred_device() == "cuda":
        clear_cache()
        load_ok, load_error = _load("cpu")
    if not load_ok or _CLAP["model"] is None:
        if isinstance(load_error, str) and load_error.startswith("model_not_cached:"):
            models_root = load_error.split(":", 1)[1] or _resolve_models_root()
            return {
                "clap_meta": {
                    "status": "unavailable",
                    "reason": "model_not_cached",
                    "model": _CLAP_MODEL_ID,
                    "models_root": models_root,
                    "install_hint": _CLAP_INSTALL_HINT,
                }
            }
        return {
            "clap_meta": {
                "status": "error",
                "reason": "model_load_failed",
                "error": load_error or "model unavailable",
            }
        }
    try:
        import torch  # type: ignore
        import librosa  # type: ignore
        import numpy as np  # type: ignore
        import faiss  # type: ignore
        from steps.text_embed.step import _content_fingerprint
        
        # VAD Preprocessing - filter silence before embedding
        vad_enabled = cfg.get("vad_enabled", True)
        audio_path_to_use = path
        
        if vad_enabled:
            try:
                from steps.common.vad_preprocessor import preprocess_audio_with_vad
                logger.info("audio_embed_clap vad preprocessing source_path=%s", path)
                
                vad_path, vad_segments = preprocess_audio_with_vad(
                    path,
                    threshold=0.5,
                    min_speech_duration_ms=400,
                    min_silence_duration_ms=200,
                    extract_to_file=True
                )
                
                if vad_path and vad_segments:
                    audio_path_to_use = vad_path
                    logger.info(
                        "audio_embed_clap vad preprocessing complete source_path=%s segments=%s",
                        path,
                        len(vad_segments),
                    )
                else:
                    logger.warning(
                        "audio_embed_clap vad fallback operation=%s source_path=%s reason=%s",
                        "preprocess_audio_with_vad",
                        path,
                        "no_speech_detected",
                    )
            except Exception as vad_exc:
                logger.warning(
                    "audio_embed_clap operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                    "preprocess_audio_with_vad",
                    path,
                    type(vad_exc).__name__,
                    vad_exc,
                )
        
        try:
            wave_data, sr = librosa.load(audio_path_to_use, sr=48000, mono=True)
        except Exception as decode_exc:
            logger.warning(
                "audio_embed_clap decode failed source_path=%s exc_type=%s exc=%s",
                audio_path_to_use,
                type(decode_exc).__name__,
                decode_exc,
            )
            return {"clap_meta": {"status": "skipped", "reason": "audio_decode_failed", "error": str(decode_exc)}}
        if wave_data is None or len(wave_data) == 0:
            return {"clap_meta": {"status": "skipped", "reason": "audio_empty"}}
        if not np.isfinite(wave_data).all():
            return {"clap_meta": {"status": "skipped", "reason": "invalid_audio"}}
        if float(np.max(np.abs(wave_data))) <= 1e-5:
            return {"clap_meta": {"status": "skipped", "reason": "audio_silent"}}

        def _run_inference() -> Any:
            batch = _CLAP["proc"](raw_speech=wave_data, sampling_rate=48000, return_tensors="pt")
            input_features = batch.get("input_features")
            if input_features is None:
                raise RuntimeError("CLAP processor did not return input_features for audio")
            input_features = input_features.to(_CLAP["device"])  # type: ignore[attr-defined]
            if _CLAP["device"] == "cuda":
                with torch.amp.autocast("cuda"):
                    return _CLAP["model"].get_audio_features(input_features=input_features)
            return _CLAP["model"].get_audio_features(input_features=input_features)

        try:
            out = _run_inference()
        except Exception as infer_exc:
            logger.warning(
                "audio_embed_clap inference failed device=%s source_path=%s exc_type=%s exc=%s",
                _CLAP.get("device"),
                path,
                type(infer_exc).__name__,
                infer_exc,
            )
            if _CLAP.get("device") == "cuda" and _should_retry_on_cpu(infer_exc):
                clear_cache()
                retry_ok, retry_error = _load("cpu")
                if retry_ok:
                    try:
                        out = _run_inference()
                    except Exception as retry_exc:
                        return {
                            "clap_meta": {
                                "status": "error",
                                "reason": "cpu_retry_failed",
                                "error": str(retry_exc),
                            }
                        }
                else:
                    return {
                        "clap_meta": {
                            "status": "error",
                            "reason": "retry_model_load_failed",
                            "error": retry_error or str(infer_exc),
                        }
                    }
            else:
                return {"clap_meta": {"status": "error", "reason": "inference_failed", "error": str(infer_exc)}}
        feats = out.detach().cpu().numpy().astype("float32")
        index_path = (cfg.get("paths", {}) or {}).get("faiss_audio_path")
        if not index_path:
            try:
                from steps.common.memory_commit_events import MemoryCommitEvent, emit_memory_commit_event, utc_now_iso

                scene_id = item.get("scene_id") or item.get("scene_index")
                if scene_id is not None and not isinstance(scene_id, str):
                    scene_id = f"scene_{int(scene_id):04d}"
                elif scene_id is not None:
                    scene_id = str(scene_id)
                emit_memory_commit_event(
                    cfg,
                    MemoryCommitEvent(
                        ts_utc=utc_now_iso(),
                        scene_id=scene_id,
                        video_id=str(item.get("video_id")) if item.get("video_id") is not None else None,
                        modality=str(item.get("modality") or "audio") or "audio",
                        model="laion/clap-htsat-unfused",
                        embedding_id=None,
                        component="audio_embed_clap",
                        attempted=False,
                        committed=False,
                        reason="no_index_path",
                        targets={"faiss": {"attempted": False, "committed": False, "ref": None, "reason": "no_index_path"}},
                        details={"source_path": path},
                    ),
                )
            except Exception as e:
                logger.warning(
                    "audio_embed_clap operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                    "emit_memory_commit_event.no_index_path",
                    path,
                    type(e).__name__,
                    e,
                )
            return {"clap_meta": {"status": "no_index_path"}}
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        if os.path.isfile(index_path):
            index = faiss.read_index(index_path)
        else:
            index = faiss.IndexHNSWFlat(feats.shape[1], 32)
            index.hnsw.efConstruction = 200
            index.hnsw.efSearch = 50

        # Stable 64-bit ID derived from content fingerprint
        h = _content_fingerprint(item)
        try:
            uid = np.array([int(h[:16], 16) % (2**63 - 1)], dtype='int64')
            index.add_with_ids(feats.astype("float32"), uid)
            faiss_id = int(uid[0])
        except Exception as e:
            logger.warning(
                "audio_embed_clap operation fallback operation=%s source_path=%s exc_type=%s exc=%s",
                "faiss.add_with_ids_to_add",
                path,
                type(e).__name__,
                e,
            )
            index.add(feats.astype("float32"))
            # best-effort: last ID is ntotal-1 but only valid for flat add
            faiss_id = getattr(index, 'ntotal', 0) - 1
        faiss.write_index(index, index_path)
        faiss_ok = True

        # Optional Qdrant dual-write
        qdrant_attempted = False
        qdrant_ok = False
        qdrant_reason = None
        qdrant_collection = None
        try:
            q_client = build_qdrant_client(cfg, dim=feats.shape[1], key="audio")
            if q_client:
                qdrant_collection = getattr(getattr(q_client, "cfg", None), "collection", None)
                qdrant_attempted = True
                qdrant_ok = bool(q_client.upsert([{
                    "id": h,
                    "vector": feats[0].tolist(),
                    "payload": {
                        "source_path": path,
                        "modality": "audio",
                        "faiss_id": faiss_id,
                    }
                }]))
                if not qdrant_ok:
                    qdrant_reason = "upsert_failed"
        except Exception as e:
            qdrant_attempted = True
            qdrant_ok = False
            qdrant_reason = f"exception:{type(e).__name__}"
            logger.warning(
                "audio_embed_clap operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "qdrant.upsert",
                path,
                type(e).__name__,
                e,
            )
        # Map FAISS ID -> fingerprint/source in dedicated SQLite
        map_db = (cfg.get("paths", {}) or {}).get("clap_id_map_db")
        map_ok = False
        map_reason = None
        if map_db:
            try:
                _ensure_clap_map(map_db)
                con = sqlite3.connect(map_db, check_same_thread=False)
                with con:
                    con.execute(
                        "INSERT OR REPLACE INTO clap_id_map(faiss_id, hash, source_path, created_at) VALUES (?,?,?,?)",
                        (faiss_id, h, path, datetime.utcnow().isoformat()),
                    )
                map_ok = True
            except Exception as e:
                map_reason = f"exception:{type(e).__name__}"
                logger.warning(
                    "audio_embed_clap operation failed operation=%s map_db=%s exc_type=%s exc=%s",
                    "sqlite_map.upsert",
                    map_db,
                    type(e).__name__,
                    e,
                )
            finally:
                try:
                    con.close()  # type: ignore
                except Exception as e:
                    logger.warning(
                        "audio_embed_clap operation failed operation=%s map_db=%s exc_type=%s exc=%s",
                        "sqlite_map.close",
                        map_db,
                        type(e).__name__,
                        e,
                    )
        # Upsert generic embedding metadata for recall
        embedding_ok = False
        embedding_reason = None
        try:
            from steps.common.memory import upsert_embedding
            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            upsert_embedding(cfg, h, faiss_id, path, item.get("modality", "audio") or "audio", scene_id=scene_id)
            embedding_ok = True
        except Exception as e:
            embedding_reason = f"exception:{type(e).__name__}"
            logger.warning(
                "audio_embed_clap operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "sqlite_embeddings.upsert",
                path,
                type(e).__name__,
                e,
            )

        try:
            from steps.common.memory_commit_events import MemoryCommitEvent, emit_memory_commit_event, utc_now_iso

            scene_id = item.get("scene_id") or item.get("scene_index")
            if scene_id is not None and not isinstance(scene_id, str):
                scene_id = f"scene_{int(scene_id):04d}"
            elif scene_id is not None:
                scene_id = str(scene_id)
            emit_memory_commit_event(
                cfg,
                MemoryCommitEvent(
                    ts_utc=utc_now_iso(),
                    scene_id=scene_id,
                    video_id=str(item.get("video_id")) if item.get("video_id") is not None else None,
                    modality=str(item.get("modality") or "audio") or "audio",
                    model="laion/clap-htsat-unfused",
                    embedding_id=h,
                    component="audio_embed_clap",
                    targets={
                        "faiss": {"attempted": True, "committed": bool(faiss_ok), "ref": index_path, "reason": None if faiss_ok else "write_failed"},
                        "qdrant": {"attempted": bool(qdrant_attempted), "committed": bool(qdrant_ok), "ref": qdrant_collection, "reason": qdrant_reason},
                        "sqlite_map": {"attempted": bool(map_db), "committed": bool(map_ok), "ref": map_db, "reason": map_reason},
                        "sqlite_embeddings": {
                            "attempted": True,
                            "committed": bool(embedding_ok),
                            "ref": (cfg.get("paths", {}) or {}).get("db_path"),
                            "reason": embedding_reason,
                        },
                    },
                    details={"faiss_id": faiss_id, "source_path": path},
                ),
            )
        except Exception as e:
            logger.warning(
                "audio_embed_clap operation failed operation=%s source_path=%s exc_type=%s exc=%s",
                "emit_memory_commit_event",
                path,
                type(e).__name__,
                e,
            )
        return {"clap_meta": {"status": "ok", "index_path": index_path, "faiss_id": faiss_id}}
    except Exception as e:
        return {"clap_meta": {"status": "error", "error": str(e)}}
