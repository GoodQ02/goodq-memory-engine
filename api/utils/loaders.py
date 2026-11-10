"""
Data loaders for GoodQ4All API.
Handles loading temporal indexes, scene manifests, and other processed data.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from collections import Counter, OrderedDict
from contextlib import closing
import hashlib
import os
import json
import logging
import math
import mimetypes
from pathlib import Path, PureWindowsPath
import re
import sqlite3
import threading

from api.utils.media_projection import project_legacy_name_matches

logger = logging.getLogger(__name__)

_DEFAULT_PROCESSING_ROOT: Optional[Path] = None
_DEFAULT_PROCESSED_ROOT: Optional[Path] = None
_DEFAULT_UCF_SCOPE: Optional[tuple[Path, Path, str]] = None
_DEFAULT_MEDIA_ROOTS = (Path(__file__).resolve().parents[2],)
_DEFAULT_DATA_ROOT_WARNED = False
_VIDEO_HASH_CACHE: OrderedDict[tuple, str] = OrderedDict()
_VIDEO_HASH_CACHE_LOCK = threading.Lock()
_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}
_SOURCE_EXTENSIONS = {
    "video": _VIDEO_EXTENSIONS,
    "image": {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"},
    "document": {".pdf", ".txt", ".md", ".markdown", ".docx"},
    "audio": {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".aiff", ".aif"},
}


def source_media_type(path: Path) -> str:
    return {
        ".wav": "audio/wav", ".md": "text/markdown", ".markdown": "text/markdown",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(
        path.suffix.lower(), mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    )


def scene_is_retired(scene: dict, retirements: List[dict]) -> bool:
    """Match exact durable scene identities, including legacy temporal bounds."""
    ids = {str(scene[key]) for key in ("scene_id", "source_artifact_id", "id") if scene.get(key) is not None}
    try:
        start = float(scene.get("start", scene.get("t_start")))
        end = float(scene.get("end", scene.get("t_end")))
        bounds = (round(start, 3), round(end, 3)) if math.isfinite(start) and math.isfinite(end) else None
    except (TypeError, ValueError):
        bounds = None
    return any(ids.intersection(item["aliases"]) or bounds == (item["start"], item["end"])
               for item in retirements)


def read_retired_scene_ids(ledger_path: Path, *, epoch_id: str) -> set[str]:
    """Resolve saved scene references from durable evidence, even after SQL delivery."""
    from scripts.ucf.ucf_ledger import read_scene_retirements

    if not ledger_path.exists():
        return set()
    with closing(sqlite3.connect(f"{ledger_path.resolve().as_uri()}?mode=ro", uri=True)) as conn:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ucf_status_transitions'"
        ).fetchone():
            return set()
        sources = conn.execute(
            "SELECT DISTINCT video_hash FROM ucf_status_transitions "
            "WHERE epoch_id=? AND scope LIKE 'scene_retirement:%'", (epoch_id,),
        ).fetchall()
    return {
        alias for (source,) in sources
        for evidence in read_scene_retirements(ledger_path, video_hash=source, epoch_id=epoch_id)
        for alias in evidence["aliases"]
    }


def _contained_file(path: Path, directory: Path) -> Optional[Path]:
    try:
        resolved = path.resolve()
        resolved.relative_to(directory.resolve())
        return resolved if resolved.is_file() else None
    except (OSError, ValueError):
        return None


def _verified_video_file(path: Path, expected_hash: str) -> bool:
    """Cache verified bytes only while the source file's identity and timestamps agree."""
    def fingerprint():
        stat = path.stat()
        return (str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)

    try:
        before = fingerprint()
        with _VIDEO_HASH_CACHE_LOCK:
            if _VIDEO_HASH_CACHE.get(before) == expected_hash:
                _VIDEO_HASH_CACHE.move_to_end(before)
                return True
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if fingerprint() != before or digest.hexdigest() != expected_hash:
            return False
    except (OSError, ValueError):
        return False
    with _VIDEO_HASH_CACHE_LOCK:
        _VIDEO_HASH_CACHE[before] = expected_hash
        _VIDEO_HASH_CACHE.move_to_end(before)
        while len(_VIDEO_HASH_CACHE) > 64:
            _VIDEO_HASH_CACHE.popitem(last=False)
    return True


def _resolve_default_data_root() -> Path:
    explicit = os.environ.get("GOODQ_DATA_ROOT")
    if explicit:
        return Path(explicit) / "GoodQ_Data"
    raise ValueError("GOODQ_DATA_ROOT environment variable is not set. A valid data root is required.")


_DEFAULT_DATA_ROOT = _resolve_default_data_root()


def configure_from_cfg(cfg: Dict[str, Any]) -> None:
    """Configure loader roots from canonical runtime config (api/main.py owns cfg loading)."""
    global _DEFAULT_PROCESSING_ROOT, _DEFAULT_PROCESSED_ROOT, _DEFAULT_MEDIA_ROOTS, _DEFAULT_UCF_SCOPE
    _DEFAULT_UCF_SCOPE = None
    try:
        paths_cfg = (cfg.get("paths") or {}) if isinstance(cfg, dict) else {}
        processing_root = paths_cfg.get("processing")
        if processing_root:
            _DEFAULT_PROCESSING_ROOT = Path(processing_root)
        processed_root = paths_cfg.get("processed")
        _DEFAULT_PROCESSED_ROOT = Path(processed_root) if processed_root else None
        _DEFAULT_MEDIA_ROOTS = tuple(
            Path(paths_cfg[key]) for key in (
                "data_root", "processing", "processed", "import_inbox", "failed", "nas_path"
            ) if paths_cfg.get(key)
        ) + (Path(__file__).resolve().parents[2],)
        if processing_root and paths_cfg.get("db_dir"):
            db_dir = Path(paths_cfg["db_dir"]).resolve()
            _DEFAULT_UCF_SCOPE = (
                Path(processing_root).resolve(),
                db_dir / "ucf" / "ucf_ledger.db",
                db_dir.name,  # The ingestion producer's epoch authority is paths.db_dir.
            )
    except Exception:
        return


class DataLoader:
    """Centralized data loading for API endpoints."""
    
    def __init__(self, data_root: str = str(_DEFAULT_DATA_ROOT), processing_root: Optional[str] = None,
                 *, source_roots: Optional[List[Path | str]] = None, processed_root: Optional[Path | str] = None):
        """
        Initialize data loader.
        
        Args:
            data_root: Root directory for processed data
            processing_root: Optional override for processing root directory
        """
        if processing_root is None and _DEFAULT_PROCESSING_ROOT is not None:
            self.processing_dir = _DEFAULT_PROCESSING_ROOT
            self.data_root = self.processing_dir.parent
        elif processing_root:
            self.processing_dir = Path(processing_root)
            self.data_root = self.processing_dir.parent
        else:
            self.data_root = Path(data_root)
            self.processing_dir = self.data_root / "processing"
        self.completed_dir = self.data_root / "completed"
        self.processed_source_dir = Path(processed_root or _DEFAULT_PROCESSED_ROOT or self.data_root / "processed")
        self.source_roots = tuple(Path(root).resolve() for root in (
            *(source_roots if source_roots is not None else _DEFAULT_MEDIA_ROOTS),
            self.data_root, self.processing_dir, self.completed_dir, self.processed_source_dir,
        ))
        # An explicit alternate processing root must not inherit another epoch's ledger.
        self._ucf_scope = (
            _DEFAULT_UCF_SCOPE
            if _DEFAULT_UCF_SCOPE and self.processing_dir.resolve() == _DEFAULT_UCF_SCOPE[0]
            else None
        )

    def _scene_retirements(self, video_id: str, record: Optional[dict] = None) -> List[dict]:
        if self._ucf_scope is None:
            return []
        from scripts.ucf.ucf_ledger import read_scene_retirements

        if record is None and video_id and PureWindowsPath(video_id).name == video_id and ":" not in video_id and video_id not in {".", ".."}:
            for root in (self.processing_dir, self.completed_dir):
                path = _contained_file(root / video_id / "temporal_index.json", root / video_id)
                if path:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    break
        source_hash = (record or {}).get("video_hash") or (record or {}).get("video_id") or video_id
        _, ledger_path, epoch_id = self._ucf_scope
        try:
            return read_scene_retirements(ledger_path, video_hash=source_hash, epoch_id=epoch_id)
        except (OSError, ValueError, sqlite3.Error) as exc:
            logger.error("UCF scene retirement visibility unavailable for %s: %s", video_id, exc)
            raise RuntimeError("UCF scene retirement visibility unavailable") from exc

    def _filter_retired_scenes(self, video_id: str, record: dict) -> dict:
        retirements = self._scene_retirements(video_id, record)
        if not retirements:
            return record
        projected = dict(record)
        changed = False
        for key in ("segments", "scenes"):
            rows = record.get(key)
            if isinstance(rows, list):
                projected[key] = [row for row in rows if not isinstance(row, dict) or not scene_is_retired(row, retirements)]
                changed |= len(projected[key]) != len(rows)
        if changed:
            projected["total_scenes"] = len(projected.get("scenes", projected.get("segments", [])))
            # These persisted aggregates describe the pre-retirement source;
            # leave the surviving scene evidence available without stale totals.
            for key in list(projected):
                if key.startswith(("top_", "segments_with_")) or key in {
                    "total_entities", "unique_entities", "scene_context_meta", "content_summary",
                    "speaker_aligned_mention_variant_groups", "transcript_entity_disagreement_category_counts",
                    "audio_emotion_policy",
                }:
                    projected.pop(key)
        return projected

    def is_scene_media_active(self, video_id: str, filename: str) -> bool:
        """After retirement, direct artifact routes require a surviving scene owner."""
        if not self.is_video_active(video_id):
            return False
        if not self._scene_retirements(video_id):
            return True
        expected = PureWindowsPath(filename).name.casefold()

        def references(value):
            if isinstance(value, str):
                yield PureWindowsPath(value).name.casefold()
            elif isinstance(value, dict):
                for item in value.values():
                    yield from references(item)
            elif isinstance(value, list):
                for item in value:
                    yield from references(item)

        for record, key in ((self.load_temporal_index(video_id), "segments"),
                            (self.load_scene_manifest(video_id), "scenes")):
            for scene in (record or {}).get(key, []):
                if not isinstance(scene, dict):
                    continue
                for field in ("frame_paths", "representative_frame", "keyframe", "keyframes", "audio"):
                    if expected in references(scene.get(field)):
                        return True
                index = scene.get("index")
                if type(index) is int and expected == f"scene_{index:04d}.wav":
                    return True
                segment_id = scene.get("segment_id")
                if type(segment_id) is int and expected == f"segment_{segment_id}.wav":
                    return True
        return False

    def is_video_active(self, video_id: str) -> bool:
        """Exclude known terminal UCF scopes without deleting retained artifacts.

        Legacy files without a configured ledger or matching frame scope retain
        their existing visibility. Standalone sources require promoted evidence;
        legacy video staged/validated frames retain their inspection behavior.
        """
        if not video_id or video_id in (".", "..") or PureWindowsPath(video_id).name != video_id or ":" in video_id:
            return False
        if self._ucf_scope and not any((root / video_id).is_dir() for root in (self.processing_dir, self.completed_dir)):
            return False
        try:
            record = {}
            for root in (self.processing_dir, self.completed_dir):
                directory = root / video_id
                for relative in ("temporal_index.json", "video/scene_manifest.json", "scene_manifest.json"):
                    path = _contained_file(directory / relative, directory)
                    if path is not None:
                        record = json.loads(path.read_text(encoding="utf-8"))
                        break
                if record:
                    break
            standalone = (record.get("source_kind") or "video") != "video"
            if self._ucf_scope is None:
                return not standalone
            _, ledger_path, epoch_id = self._ucf_scope
            video_hash = record.get("video_hash") or record.get("video_id") or video_id
            # mode=ro never creates a missing ledger. Close each connection so
            # a later lifecycle transition is observed by an existing loader.
            with closing(sqlite3.connect(f"{ledger_path.as_uri()}?mode=ro", uri=True)) as conn:
                rows = conn.execute(
                    "SELECT DISTINCT promotion_status FROM context_frames WHERE epoch_id = ? AND video_hash = ?",
                    (epoch_id, video_hash),
                ).fetchall()
            retirements = self._scene_retirements(video_id, record)
            scene_rows = record.get("segments", record.get("scenes", []))
            if retirements and scene_rows and all(
                isinstance(scene, dict) and scene_is_retired(scene, retirements) for scene in scene_rows
            ):
                return False
        except (OSError, ValueError, AttributeError, sqlite3.Error) as exc:
            logger.error("UCF lifecycle visibility unavailable for video %s: %s", video_id, exc)
            raise RuntimeError("UCF lifecycle visibility unavailable") from exc
        if standalone:
            return any(row[0] == "promoted" for row in rows)
        return not rows or any(row[0] not in {"rejected", "superseded"} for row in rows)

    def is_search_result_active(self, payload: dict) -> bool:
        """Do not expose a stale candidate for a locally governed source."""
        source_id = str(payload.get("video_id") or payload.get("video_hash") or "")
        if source_id and any((root / source_id).is_dir() for root in (self.processing_dir, self.completed_dir)):
            return self.is_video_active(source_id) and not scene_is_retired(payload, self._scene_retirements(source_id))
        # Legacy video vectors may use an identity alias instead of a directory ID.
        return (payload.get("source_kind") or "video") == "video" and not scene_is_retired(
            payload, self._scene_retirements(str(payload.get("video_hash") or source_id))
        )
    
    def load_temporal_index(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Load temporal index for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Temporal index data or None if not found
        """
        if not self.is_video_active(video_id):
            return None
        # Try processing directory first
        path = self.processing_dir / video_id / "temporal_index.json"
        
        if not path.exists():
            # Try completed directory
            path = self.completed_dir / video_id / "temporal_index.json"
        
        if not path.exists():
            logger.warning(f"Temporal index not found for video: {video_id}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                record = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load temporal index: {e}")
            return None
        record = self._filter_retired_scenes(video_id, record)
        if isinstance(record.get("segments"), list):
            record["segments"] = [project_legacy_name_matches(row) if isinstance(row, dict) else row
                                  for row in record["segments"]]
        return record

    def get_temporal_index_path(self, video_id: str) -> Optional[Path]:
        """Resolve the canonical temporal index path for a processed video."""
        if not self.is_video_active(video_id):
            return None
        path = self.processing_dir / video_id / "temporal_index.json"
        if path.exists():
            return path

        path = self.completed_dir / video_id / "temporal_index.json"
        if path.exists():
            return path

        return None
    
    def load_scene_manifest(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Load scene manifest for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Scene manifest data or None if not found
        """
        if not self.is_video_active(video_id):
            return None
        path = self.processing_dir / video_id / "video" / "scene_manifest.json"
        
        if not path.exists():
            alt_path = self.processing_dir / video_id / "scene_manifest.json"
            if alt_path.exists():
                path = alt_path
            else:
                path = self.completed_dir / video_id / "video" / "scene_manifest.json"
        
        if not path.exists():
            logger.warning(f"Scene manifest not found for video: {video_id}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                record = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load scene manifest: {e}")
            return None
        return self._filter_retired_scenes(video_id, record)
    
    def load_segmentation(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Load audio segmentation for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Segmentation data or None if not found
        """
        path = self.processing_dir / video_id / "audio" / "segmentation.json"
        
        if not path.exists():
            path = self.completed_dir / video_id / "audio" / "segmentation.json"
        
        if not path.exists():
            logger.warning(f"Segmentation not found for video: {video_id}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load segmentation: {e}")
            return None
    
    def get_frame_path(self, video_id: str, scene_id: int, frame_index: int = 0) -> Optional[Path]:
        """
        Get path to a specific frame.
        
        Args:
            video_id: Video identifier
            scene_id: Scene identifier
            frame_index: Frame index within scene (default: 0 for representative frame)
            
        Returns:
            Path to frame file or None if not found
        """
        # Load temporal index to get frame paths
        temporal_index = self.load_temporal_index(video_id)
        
        if not temporal_index:
            return None
        
        # Find the scene segment
        for segment in temporal_index.get('segments', []):
            if segment.get('scene_id') == scene_id:
                frame_paths = segment.get('frame_paths', [])
                
                if frame_index < len(frame_paths):
                    frame_path = Path(frame_paths[frame_index])
                    
                    # Convert to absolute path if relative
                    if not frame_path.is_absolute():
                        frame_path = self.processing_dir / video_id / "video" / "frames" / frame_path.name
                    
                    if frame_path.exists():
                        return frame_path
        
        return None
    
    def get_audio_chunk_path(self, video_id: str, chunk_id: int) -> Optional[Path]:
        """
        Get path to an audio chunk.
        
        Args:
            video_id: Video identifier
            chunk_id: Legacy segment identifier or canonical extraction scene index
            
        Returns:
            Path to audio chunk or None if not found
        """
        if not self.is_video_active(video_id):
            return None
        # Preserve legacy segment precedence; the canonical scene extractor
        # writes scene_<index:04d>.wav into the same audio/chunks directory.
        for filename in (f"segment_{chunk_id}.wav", f"scene_{chunk_id:04d}.wav"):
            for root in (self.processing_dir, self.completed_dir):
                chunk_path = root / video_id / "audio" / "chunks" / filename
                if chunk_path.exists() and self.is_scene_media_active(video_id, filename):
                    return chunk_path
        
        return None

    def _active_video_directory(self, video_id: str) -> Optional[Path]:
        """Match temporal-index precedence without mixing processing/completed artifacts."""
        if not self.is_video_active(video_id):
            return None
        if (
            not video_id or video_id in (".", "..")
            or PureWindowsPath(video_id).name != video_id
            or ":" in video_id
        ):
            return None

        video_dirs = []
        for root in (self.processing_dir, self.completed_dir):
            directory = (root / video_id).resolve()
            try:
                directory.relative_to(root.resolve())
                directory.relative_to(self.data_root.resolve())
            except ValueError:
                continue
            video_dirs.append(directory)

        return next((
            directory for directory in video_dirs
            if _contained_file(directory / "temporal_index.json", directory)
        ), None)

    def get_scene_audio_paths(self, video_id: str) -> Dict[str, Path]:
        """Resolve canonical scene WAVs from one manifest, without legacy chunk aliases."""
        active_directory = self._active_video_directory(video_id)
        if active_directory is None:
            return {}

        manifest = None
        manifest_directory = None
        for relative in ("video/scene_manifest.json", "scene_manifest.json"):
            path = _contained_file(active_directory / relative, active_directory)
            if path:
                manifest_directory = active_directory
                try:
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    logger.warning("Scene audio manifest unavailable for video: %s", video_id)
                    return {}
                break
        if manifest_directory is None or not isinstance(manifest, dict) or not isinstance(manifest.get("scenes"), list):
            return {}
        manifest = self._filter_retired_scenes(video_id, manifest)

        filenames = {}
        seen_ids = set()
        ambiguous_ids = set()
        for scene in manifest["scenes"]:
            if not isinstance(scene, dict):
                continue
            scene_id = scene.get("scene_id", scene.get("id"))
            if isinstance(scene_id, bool) or not isinstance(scene_id, (str, int)) or str(scene_id) == "":
                continue
            key = str(scene_id)
            if key in seen_ids:
                ambiguous_ids.add(key)
            seen_ids.add(key)
            if scene.get("id") is not None and str(scene["id"]) != key:
                continue
            index = scene.get("index")
            if index is not None and (isinstance(index, bool) or not isinstance(index, int) or index < 0):
                continue
            filename = f"scene_{index:04d}.wav" if index is not None else None
            audio = scene.get("audio")
            reference = audio.get("path") if isinstance(audio, dict) else None
            if reference is not None:
                if not isinstance(reference, str):
                    continue
                recorded_name = PureWindowsPath(reference).name
                if not re.fullmatch(r"scene_[0-9]{4,}\.wav", recorded_name):
                    continue
                if filename is not None and filename != recorded_name:
                    continue
                filename = recorded_name
            if filename:
                filenames[key] = filename

        paths = {}
        filename_counts = Counter(filenames.values())
        for key, filename in filenames.items():
            if key in ambiguous_ids or filename_counts[filename] != 1:
                continue
            path = _contained_file(manifest_directory / "audio" / "chunks" / filename, manifest_directory)
            if path:
                paths[key] = path
        return paths

    def get_original_video_path(self, video_id: str) -> Optional[Path]:
        """Retain the video-only contract used by the desktop player."""
        temporal = self.load_temporal_index(video_id)
        if not temporal or (temporal.get("source_kind") or "video") != "video":
            return None
        return self.get_original_source_path(video_id)

    def get_original_source_path(self, video_id: str) -> Optional[Path]:
        """Resolve a persisted original by content identity, including Watchdog's retained moves."""
        directory = self._active_video_directory(video_id)
        if directory is None:
            return None
        temporal_path = _contained_file(directory / "temporal_index.json", directory)
        manifest_path = next((
            path for relative in ("video/scene_manifest.json", "scene_manifest.json")
            if (path := _contained_file(directory / relative, directory)) is not None
        ), None)
        if temporal_path is None or manifest_path is None:
            return None
        try:
            records = [json.loads(path.read_text(encoding="utf-8")) for path in (temporal_path, manifest_path)]
        except (OSError, ValueError):
            return None

        identities = set()
        source_kinds = set()
        locators = []
        for record in records:
            if not isinstance(record, dict):
                return None
            record_hashes = set()
            for key in ("video_hash", "video_id"):
                value = record.get(key)
                if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value):
                    record_hashes.add(value.lower())
                elif key == "video_hash" and value is not None:
                    return None
            if len(record_hashes) != 1:
                return None
            identities.update(record_hashes)
            kind = record.get("source_kind") or "video"
            source_kinds.add(kind)
            locator = record.get("source_path") or record.get("video_path")
            if (
                not isinstance(locator, str) or not locator
                or locator.startswith(("\\\\", "//")) or "://" in locator
                or not Path(locator).is_absolute()
                or Path(locator).suffix.lower() not in _SOURCE_EXTENSIONS.get(kind, set())
            ):
                return None
            if record.get("source_path") and record.get("video_path"):
                if Path(record["source_path"]).resolve() != Path(record["video_path"]).resolve():
                    return None
            locators.append(Path(locator))
        if len(identities) != 1 or len(source_kinds) != 1:
            return None
        try:
            if locators[0].resolve() != locators[1].resolve():
                return None
        except (OSError, ValueError):
            return None
        expected_hash = next(iter(identities))
        standalone = next(iter(source_kinds)) != "video"

        def verified_candidate(candidate: Path) -> Optional[Path]:
            if standalone:
                # Standalone intake owns a hash-named retained copy beside its projections.
                path = _contained_file(candidate, directory)
                return path if path and path.stem == expected_hash and _verified_video_file(path, expected_hash) else None
            for root in self.source_roots:
                path = _contained_file(candidate, root)
                if path is not None:
                    return path if _verified_video_file(path, expected_hash) else None
            return None

        original = verified_candidate(locators[0])
        if original is not None:
            return original
        if standalone:
            return None
        # safe_move_file retains originals as PROCESSED_<name>[_N].<extension>.
        # Only inspect that exact non-recursive family; every candidate still needs SHA256 proof.
        source_name = locators[0].name
        filename = Path(source_name)
        pattern = re.compile(r"PROCESSED_" + re.escape(filename.stem) + r"(?:_[1-9][0-9]*)?" + re.escape(filename.suffix), re.IGNORECASE)
        try:
            candidates = sorted(
                (path for path in self.processed_source_dir.iterdir() if pattern.fullmatch(path.name)),
                key=lambda path: path.name.casefold(),
            )
        except OSError:
            return None
        for candidate in candidates:
            original = verified_candidate(candidate)
            if original is not None:
                return original
        return None
    
    def list_processed_videos(self) -> List[str]:
        """
        List all processed videos.
        
        Returns:
            List of video IDs
        """
        video_ids = []
        
        # Scan processing directory
        if self.processing_dir.exists():
            for item in self.processing_dir.iterdir():
                if item.is_dir():
                    # Check if temporal index exists
                    if (item / "temporal_index.json").exists():
                        video_ids.append(item.name)
        
        # Scan completed directory
        if self.completed_dir.exists():
            for item in self.completed_dir.iterdir():
                if item.is_dir() and item.name not in video_ids:
                    if (item / "temporal_index.json").exists():
                        video_ids.append(item.name)
        
        return sorted(video_id for video_id in video_ids if self.is_video_active(video_id))
    
    def get_video_metadata(self, video_id: str) -> Dict[str, Any]:
        """
        Get basic metadata for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Video metadata dict
        """
        temporal_index_path = self.get_temporal_index_path(video_id)
        temporal_index = self.load_temporal_index(video_id)
        
        if not temporal_index:
            return {'video_id': video_id, 'error': 'not_found'}

        title = temporal_index.get('title')
        if not isinstance(title, str) or not title.strip():
            source_name = temporal_index.get('original_filename') or temporal_index.get('source_name')
            if isinstance(source_name, str) and source_name.strip():
                title = Path(source_name).stem
            else:
                title = video_id

        processed_date = None
        if temporal_index_path and temporal_index_path.exists():
            processed_date = temporal_index_path.stat().st_mtime

        metadata = {
            'video_id': video_id,
            'source_kind': temporal_index.get('source_kind') or 'video',
            'title': title,
            # Video harmonization writes total_duration; standalone sources use
            # duration. Do not infer source length from filtered/retired scenes.
            'duration': temporal_index.get('total_duration', temporal_index.get('duration', 0.0)),
            'total_scenes': len(temporal_index.get('segments', [])),
            'total_segments': len(temporal_index.get('segments', [])),
            'phase6_complete': temporal_index.get('phase6_complete', False),
            'phase6_harmonized': temporal_index.get('phase6_harmonized', False),
            'processed_date': processed_date,
        }
        
        return metadata
