"""
Media API routes for GoodQ4All.
Serves frames, audio chunks, and other media files.
"""
from __future__ import annotations
import logging
import math
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Path as PathParam, Request
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from api.utils.loaders import DataLoader
from api.route_effects import is_loopback_client
from api.utils.desktop_player import DesktopPlayer, DesktopPlayerError

logger = logging.getLogger(__name__)

_desktop_player = None


@asynccontextmanager
async def _media_lifespan(app):
    yield
    if _desktop_player is not None:
        _desktop_player.close()


router = APIRouter(prefix="/api/media", tags=["media"], lifespan=_media_lifespan)

_data_loader = None


def get_desktop_player():
    global _desktop_player
    if _desktop_player is None:
        _desktop_player = DesktopPlayer()
    return _desktop_player


class PlayerWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    x: int = Field(ge=-32768, le=32768)
    y: int = Field(ge=-32768, le=32768)
    width: int = Field(ge=240, le=1920)
    height: int = Field(ge=180, le=1440)


class DesktopPlayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    video_id: str = Field(min_length=1, max_length=256, pattern=r"^[^/\\\x00-\x1f]+$")
    scene_id: str = Field(min_length=1, max_length=256)
    window: PlayerWindow | None = None


class DesktopDoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    playback_id: str = Field(min_length=1, max_length=128)


def _require_local_desktop(request: Request) -> None:
    if not is_loopback_client(request.scope.get("client")):
        raise HTTPException(403, "Desktop playback is available only on this computer")
    origin = request.headers.get("origin")
    expected = urlsplit(str(request.base_url))
    try:
        supplied = urlsplit(origin or "")
        same_origin = (supplied.scheme, supplied.hostname, supplied.port) == (
            expected.scheme, expected.hostname, expected.port)
    except ValueError:
        same_origin = False
    if not origin or not same_origin or supplied.username or supplied.password:
        raise HTTPException(403, "Desktop playback requires a same-origin request")


@router.get("/desktop-player/status")
def desktop_player_status(request: Request):
    if not is_loopback_client(request.scope.get("client")):
        return {"available": False, "state": "unavailable", "playback_id": None,
                "error": "Desktop playback is available only on this computer"}
    return get_desktop_player().status()


@router.post("/desktop-player/play")
def desktop_player_play(body: DesktopPlayRequest, request: Request):
    _require_local_desktop(request)
    loader = get_data_loader()
    path = loader.get_original_video_path(body.video_id)
    if path is None:
        raise HTTPException(404, "Original video not found")
    temporal = loader.load_temporal_index(body.video_id) or {}
    matches = [segment for segment in temporal.get("segments", []) if isinstance(segment, dict)
               and str(segment.get("scene_id")) == body.scene_id]
    if len(matches) != 1:
        raise HTTPException(404, "Scene not found or ambiguous")
    start = matches[0].get("start")
    if isinstance(start, bool) or not isinstance(start, (int, float)) or not math.isfinite(start) or start < 0:
        raise HTTPException(422, "Scene has no valid original-video timestamp")
    try:
        return get_desktop_player().play(path, float(start), body.video_id, body.scene_id,
                                         body.window.model_dump() if body.window else None)
    except DesktopPlayerError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/desktop-player/done")
def desktop_player_done(body: DesktopDoneRequest, request: Request):
    _require_local_desktop(request)
    try:
        return get_desktop_player().done(body.playback_id)
    except DesktopPlayerError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


def get_data_loader():
    """Lazy-load data loader."""
    global _data_loader
    
    if _data_loader is None:
        _data_loader = DataLoader()
        logger.info("[OK] Data loader initialized for media")
    
    return _data_loader


@router.get("/video/{video_id}/scene/{scene_id}/frame/{frame_index}")
async def get_scene_frame(
    video_id: str = PathParam(..., description="Video identifier"),
    scene_id: int = PathParam(..., description="Scene identifier"),
    frame_index: int = PathParam(..., description="Frame index (0 for representative)")
):
    """
    Retrieve a specific frame from a scene.
    
    Args:
        video_id: Video identifier
        scene_id: Scene identifier
        frame_index: Frame index within scene (0 = representative frame)
        
    Returns:
        JPEG image file
    """
    try:
        loader = get_data_loader()
        frame_path = loader.get_frame_path(video_id, scene_id, frame_index)
        
        if not frame_path or not frame_path.exists():
            raise HTTPException(status_code=404, detail="Frame not found")
        
        # Security: Ensure path doesn't escape data directory
        try:
            frame_path.resolve().relative_to(loader.data_root.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return FileResponse(
            path=str(frame_path),
            media_type="image/jpeg",
            filename=frame_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve frame: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to serve frame: {str(e)}")


@router.get("/audio/{video_id}/{chunk_id}.wav")
async def get_audio_chunk(
    video_id: str = PathParam(..., description="Video identifier"),
    chunk_id: int = PathParam(..., description="Audio chunk identifier")
):
    """
    Retrieve a specific audio chunk.
    
    Args:
        video_id: Video identifier
        chunk_id: Chunk identifier
        
    Returns:
        WAV audio file
    """
    try:
        loader = get_data_loader()
        chunk_path = loader.get_audio_chunk_path(video_id, chunk_id)
        
        if not chunk_path or not chunk_path.exists():
            raise HTTPException(status_code=404, detail="Audio chunk not found")
        
        # Security: Ensure path doesn't escape data directory
        try:
            chunk_path.resolve().relative_to(loader.data_root.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return FileResponse(
            path=str(chunk_path),
            media_type="audio/wav",
            filename=chunk_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve audio chunk: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to serve audio chunk: {str(e)}")


@router.get("/video/{video_id}/scene/{scene_id}/audio")
async def get_scene_audio(video_id: str, scene_id: str):
    """Serve the recorded audio for one exact manifest scene, starting at local time zero."""
    path = get_data_loader().get_scene_audio_paths(video_id).get(scene_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Original scene audio not found")
    return FileResponse(path=str(path), media_type="audio/wav")


@router.get("/video/{video_id}/source")
async def get_original_video(video_id: str):
    """Serve verified original bytes, retaining the legacy URL for every source kind."""
    from api.utils.loaders import source_media_type
    loader = get_data_loader()
    temporal = loader.load_temporal_index(video_id) or {}
    kind = temporal.get("source_kind") or "video"
    resolver = loader.get_original_video_path if kind == "video" else loader.get_original_source_path
    path = await run_in_threadpool(resolver, video_id)
    if path is None:
        detail = "Original video not found" if kind == "video" else "Original source not found"
        raise HTTPException(status_code=404, detail=detail)
    return FileResponse(path=str(path), media_type=source_media_type(path))


@router.get("/video/{video_id}/frame/{frame_name}")
async def get_frame_by_name(
    video_id: str = PathParam(..., description="Video identifier"),
    frame_name: str = PathParam(..., description="Frame filename")
):
    """
    Retrieve a frame by filename.
    
    Args:
        video_id: Video identifier
        frame_name: Frame filename (e.g., "frame_0001.jpg")
        
    Returns:
        JPEG image file
    """
    try:
        loader = get_data_loader()
        
        # Construct frame path
        if not loader.is_scene_media_active(video_id, frame_name):
            raise HTTPException(status_code=404, detail="Frame not found")
        frame_path = loader.processing_dir / video_id / "video" / "frames" / frame_name
        
        if not frame_path.exists():
            # Try completed directory
            frame_path = loader.completed_dir / video_id / "video" / "frames" / frame_name
        
        if not frame_path.exists():
            raise HTTPException(status_code=404, detail="Frame not found")
        
        # Security: Ensure path doesn't escape data directory and filename is safe
        try:
            frame_path.resolve().relative_to(loader.data_root.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if ".." in frame_name or "/" in frame_name or "\\" in frame_name:
            raise HTTPException(status_code=403, detail="Invalid filename")
        
        return FileResponse(
            path=str(frame_path),
            media_type="image/jpeg",
            filename=frame_path.name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve frame: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to serve frame: {str(e)}")
