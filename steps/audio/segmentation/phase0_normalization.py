"""
Phase 0: Media Pre-Normalization
Extracts and normalizes audio from video, ensures consistent format
"""
from __future__ import annotations
from typing import Dict, Any, Optional
import os
import subprocess
import json


def normalize_media(
    video_path: str,
    output_audio_path: str,
    config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Extract and normalize audio from video file
    
    Args:
        video_path: Path to input video file
        output_audio_path: Path for normalized audio output
        config: Optional configuration (sample_rate, channels, bit_depth)
        
    Returns:
        Path to normalized audio file
    """
    config = config or {}
    
    sample_rate = config.get('target_sample_rate', 16000)
    channels = config.get('channels', 1)
    codec = config.get('codec', 'pcm_s16le')
    
    print(f"[PHASE0] Extracting audio from: {video_path}")
    print(f"[PHASE0] Output: {output_audio_path}")
    print(f"[PHASE0] Format: {sample_rate}Hz, {channels}ch, {codec}")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_audio_path), exist_ok=True)
    
    # FFmpeg command for audio extraction and normalization
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vn',  # No video
        '-acodec', codec,
        '-ar', str(sample_rate),
        '-ac', str(channels),
        '-y',  # Overwrite
        output_audio_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"[PHASE0] Audio extraction complete")
        return output_audio_path
        
    except subprocess.CalledProcessError as e:
        print(f"[PHASE0-ERROR] FFmpeg failed: {e.stderr}")
        raise RuntimeError(f"Failed to extract audio: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")


def extract_metadata(video_path: str) -> Dict[str, Any]:
    """
    Extract video/audio metadata using ffprobe
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with duration, fps, resolution, audio properties
    """
    print(f"[PHASE0] Extracting metadata from: {video_path}")
    
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        video_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        data = json.loads(result.stdout)
        
        # Extract video stream info
        video_stream = next(
            (s for s in data.get('streams', []) if s.get('codec_type') == 'video'),
            None
        )
        
        # Extract audio stream info
        audio_stream = next(
            (s for s in data.get('streams', []) if s.get('codec_type') == 'audio'),
            None
        )
        
        # Parse format info
        format_data = data.get('format', {})
        
        metadata = {
            'duration': float(format_data.get('duration', 0)),
            'size_bytes': int(format_data.get('size', 0)),
            'bit_rate': int(format_data.get('bit_rate', 0)),
        }
        
        if video_stream:
            # Parse FPS
            fps_str = video_stream.get('r_frame_rate', '30/1')
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                fps = num / den if den != 0 else 30.0
            else:
                fps = float(fps_str)
            
            metadata.update({
                'fps': fps,
                'width': int(video_stream.get('width', 0)),
                'height': int(video_stream.get('height', 0)),
                'resolution': f"{video_stream.get('width')}x{video_stream.get('height')}",
                'video_codec': video_stream.get('codec_name'),
                'pixel_format': video_stream.get('pix_fmt')
            })
        
        if audio_stream:
            metadata.update({
                'audio_sample_rate': int(audio_stream.get('sample_rate', 0)),
                'audio_channels': int(audio_stream.get('channels', 0)),
                'audio_codec': audio_stream.get('codec_name'),
                'audio_bit_rate': int(audio_stream.get('bit_rate', 0))
            })
        
        print(f"[PHASE0] Metadata extracted:")
        print(f"  Duration: {metadata.get('duration', 0):.2f}s")
        print(f"  FPS: {metadata.get('fps', 0):.2f}")
        print(f"  Resolution: {metadata.get('resolution', 'unknown')}")
        print(f"  Audio: {metadata.get('audio_sample_rate', 0)}Hz")
        
        return metadata
        
    except subprocess.CalledProcessError as e:
        print(f"[PHASE0-ERROR] FFprobe failed: {e.stderr}")
        return {}
    except FileNotFoundError:
        raise RuntimeError("FFprobe not found. Please install FFmpeg/FFprobe.")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[PHASE0-ERROR] Failed to parse metadata: {e}")
        return {}


if __name__ == '__main__':
    print("Phase 0: Media Pre-Normalization Module")
    print("=" * 60)
    print("Extracts and normalizes audio from video files")
