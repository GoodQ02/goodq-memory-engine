"""
FFmpeg Utilities for GoodQ4All
Audio/Video extraction and normalization
"""

import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def get_ffmpeg_path() -> str:
    """Get FFmpeg executable path"""
    # Try system PATH first
    import shutil
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        return ffmpeg
    
    # Try L:/_TOOLS
    tools_ffmpeg = Path('L:/_TOOLS/ffmpeg/bin/ffmpeg.exe')
    if tools_ffmpeg.exists():
        return str(tools_ffmpeg)
    
    raise RuntimeError("FFmpeg not found in PATH or L:/_TOOLS")


def get_media_info(media_path: str) -> Dict:
    """
    Extract media metadata using ffprobe
    
    Returns:
        Dictionary with duration, fps, resolution, codec info
    """
    ffprobe = get_ffmpeg_path().replace('ffmpeg', 'ffprobe')
    
    cmd = [
        ffprobe,
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        media_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        # Extract useful metadata
        metadata = {
            'duration': float(data.get('format', {}).get('duration', 0)),
            'size': int(data.get('format', {}).get('size', 0)),
            'bit_rate': int(data.get('format', {}).get('bit_rate', 0)),
        }
        
        # Find video and audio streams
        for stream in data.get('streams', []):
            if stream['codec_type'] == 'video':
                metadata['video_codec'] = stream.get('codec_name')
                metadata['width'] = stream.get('width')
                metadata['height'] = stream.get('height')
                metadata['fps'] = eval(stream.get('r_frame_rate', '0/1'))
            elif stream['codec_type'] == 'audio':
                metadata['audio_codec'] = stream.get('codec_name')
                metadata['sample_rate'] = int(stream.get('sample_rate', 0))
                metadata['channels'] = stream.get('channels', 0)
        
        return metadata
    
    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe failed: {e}")
        return {}


def extract_audio_track(
    video_path: str,
    output_path: str,
    sample_rate: int = 16000,
    channels: int = 1,
    bit_depth: int = 16
) -> str:
    """
    Extract and normalize audio from video to WAV
    
    Args:
        video_path: Source video file
        output_path: Output WAV file path
        sample_rate: Target sample rate (default 16000 Hz)
        channels: Target channel count (1=mono, 2=stereo)
        bit_depth: Target bit depth (16 or 24)
    
    Returns:
        Path to output WAV file
    """
    ffmpeg = get_ffmpeg_path()
    
    # Build FFmpeg command
    cmd = [
        ffmpeg,
        '-i', video_path,
        '-vn',  # No video
        '-acodec', 'pcm_s16le' if bit_depth == 16 else 'pcm_s24le',
        '-ar', str(sample_rate),
        '-ac', str(channels),
        '-y',  # Overwrite
        output_path
    ]
    
    logger.info(f"Extracting audio: {Path(video_path).name} -> {Path(output_path).name}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        if not Path(output_path).exists():
            raise RuntimeError(f"FFmpeg succeeded but output file not created: {output_path}")
        
        logger.info(f"✓ Audio extracted: {output_path}")
        return output_path
    
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg audio extraction failed: {e.stderr}")
        raise


def extract_video_frames(
    video_path: str,
    output_dir: str,
    fps: Optional[float] = None,
    start_time: Optional[float] = None,
    duration: Optional[float] = None
) -> str:
    """
    Extract video frames as images
    
    Args:
        video_path: Source video file
        output_dir: Directory for output frames
        fps: Frame extraction rate (None = use source fps)
        start_time: Start time in seconds
        duration: Duration to extract in seconds
    
    Returns:
        Output directory path
    """
    ffmpeg = get_ffmpeg_path()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_pattern = str(output_dir / "frame_%06d.jpg")
    
    cmd = [ffmpeg, '-i', video_path]
    
    if start_time is not None:
        cmd.extend(['-ss', str(start_time)])
    
    if duration is not None:
        cmd.extend(['-t', str(duration)])
    
    if fps is not None:
        cmd.extend(['-vf', f'fps={fps}'])
    
    cmd.extend(['-y', output_pattern])
    
    logger.info(f"Extracting frames: {Path(video_path).name}")
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        logger.info(f"✓ Frames extracted: {output_dir}")
        return str(output_dir)
    
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg frame extraction failed: {e.stderr}")
        raise
