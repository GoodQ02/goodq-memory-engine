"""
Phased Segmentation Engine - Core Module

Multi-stage audio segmentation pipeline:
  Phase 0: Pre-normalization (audio extraction, conversion)
  Phase 1: WebRTC VAD segmentation (CPU-based speech detection)
  Phase 2: Pyannote segmentation (GPU-based speaker boundaries)
  Phase 3: Smart chunk builder (merge/split/padding)
  Phase 4: Chunk-level processing preparation
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import wave
import numpy as np

logger = logging.getLogger(__name__)


class SegmentationConfig:
    """Configuration for phased segmentation pipeline"""
    
    def __init__(self, **kwargs):
        # Phase 1: VAD Config
        self.vad_aggressiveness = kwargs.get('vad_aggressiveness', 3)
        self.vad_frame_duration_ms = kwargs.get('vad_frame_duration_ms', 30)
        self.vad_padding_duration_ms = kwargs.get('vad_padding_duration_ms', 300)
        
        # Phase 2: Pyannote Config
        self.pyannote_min_duration_off = kwargs.get('pyannote_min_duration_off', 0.0)
        self.pyannote_min_duration_on = kwargs.get('pyannote_min_duration_on', 0.0)
        
        # Phase 3: Chunking Config
        self.min_chunk_duration = kwargs.get('min_chunk_duration', 1.0)
        self.max_chunk_duration = kwargs.get('max_chunk_duration', 40.0)
        self.chunk_padding_ms = kwargs.get('chunk_padding_ms', 250)
        self.chunk_overlap_ms = kwargs.get('chunk_overlap_ms', 500)
        
        # Audio normalization
        self.target_sample_rate = kwargs.get('target_sample_rate', 16000)
        self.target_channels = kwargs.get('target_channels', 1)
        self.target_bit_depth = kwargs.get('target_bit_depth', 16)
        
        # Output paths
        self.output_base = kwargs.get('output_base', 'L:/_DATA/GoodQ_Data/processing')


class AudioSegment:
    """Represents a single audio segment with metadata"""
    
    def __init__(self, segment_id: int, start: float, end: float, **kwargs):
        self.id = segment_id
        self.start = start
        self.end = end
        self.duration = end - start
        
        # VAD metadata
        self.vad_speech = kwargs.get('vad_speech', True)
        
        # Pyannote metadata
        self.speaker_changes = kwargs.get('speaker_changes', [])
        self.overlap_detected = kwargs.get('overlap_detected', False)
        
        # Chunk metadata
        self.chunk_path = kwargs.get('chunk_path', None)
        self.is_merged = kwargs.get('is_merged', False)
        self.is_split = kwargs.get('is_split', False)
        self.parent_segments = kwargs.get('parent_segments', [])
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'start': self.start,
            'end': self.end,
            'duration': self.duration,
            'vad_speech': self.vad_speech,
            'speaker_changes': self.speaker_changes,
            'overlap_detected': self.overlap_detected,
            'chunk_path': self.chunk_path,
            'is_merged': self.is_merged,
            'is_split': self.is_split,
            'parent_segments': self.parent_segments
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AudioSegment':
        """Create from dictionary"""
        return cls(
            segment_id=data['id'],
            start=data['start'],
            end=data['end'],
            vad_speech=data.get('vad_speech', True),
            speaker_changes=data.get('speaker_changes', []),
            overlap_detected=data.get('overlap_detected', False),
            chunk_path=data.get('chunk_path'),
            is_merged=data.get('is_merged', False),
            is_split=data.get('is_split', False),
            parent_segments=data.get('parent_segments', [])
        )


class SegmentationManifest:
    """Container for segmentation results"""
    
    def __init__(self, video_id: str, source_path: str):
        self.video_id = video_id
        self.source_path = source_path
        self.audio_path = None
        self.duration = 0.0
        self.sample_rate = 16000
        self.channels = 1
        self.segments: List[AudioSegment] = []
        self.metadata = {}
    
    def add_segment(self, segment: AudioSegment):
        """Add a segment to the manifest"""
        self.segments.append(segment)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'video_id': self.video_id,
            'source_path': self.source_path,
            'audio_path': self.audio_path,
            'duration': self.duration,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'segments': [seg.to_dict() for seg in self.segments],
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SegmentationManifest':
        """Create from dictionary"""
        manifest = cls(data['video_id'], data['source_path'])
        manifest.audio_path = data.get('audio_path')
        manifest.duration = data.get('duration', 0.0)
        manifest.sample_rate = data.get('sample_rate', 16000)
        manifest.channels = data.get('channels', 1)
        manifest.segments = [AudioSegment.from_dict(seg) for seg in data.get('segments', [])]
        manifest.metadata = data.get('metadata', {})
        return manifest


# ============================================================================
# PHASE 0: PRE-NORMALIZATION
# ============================================================================

def extract_and_normalize_audio(
    video_path: str,
    output_dir: str,
    config: SegmentationConfig
) -> Tuple[str, Dict]:
    """
    Phase 0: Extract audio from video and normalize to 16kHz mono PCM WAV
    
    Returns:
        Tuple of (audio_path, metadata_dict)
    """
    from goodq4all.lib.ffmpeg_utils import extract_audio_track, get_media_info
    
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Output normalized audio path
    audio_path = output_dir / f"{video_path.stem}_normalized.wav"
    
    logger.info(f"Phase 0: Extracting and normalizing audio from {video_path.name}")
    
    # Extract basic metadata first
    metadata = get_media_info(str(video_path))
    
    # Extract audio with ffmpeg normalization
    extract_audio_track(
        str(video_path),
        str(audio_path),
        sample_rate=config.target_sample_rate,
        channels=config.target_channels,
        bit_depth=config.target_bit_depth
    )
    
    # Verify output
    if not audio_path.exists():
        raise RuntimeError(f"Audio extraction failed: {audio_path} not created")
    
    logger.info(f"✓ Phase 0 complete: {audio_path.name} ({metadata.get('duration', 0):.2f}s)")
    
    return str(audio_path), metadata


# ============================================================================
# PHASE 1: WEBRTC VAD SEGMENTATION
# ============================================================================

def segment_with_vad(
    audio_path: str,
    config: SegmentationConfig
) -> List[Tuple[float, float]]:
    """
    Phase 1: Use WebRTC VAD to detect speech regions (CPU-based)
    
    Returns:
        List of (start_time, end_time) tuples for speech segments
    """
    import webrtcvad
    
    logger.info("Phase 1: Running WebRTC VAD segmentation")
    
    vad = webrtcvad.Vad(config.vad_aggressiveness)
    
    # Read WAV file
    with wave.open(audio_path, 'rb') as wf:
        sample_rate = wf.getframerate()
        num_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        
        if sample_rate != 16000:
            raise ValueError(f"VAD requires 16kHz audio, got {sample_rate}Hz")
        if num_channels != 1:
            raise ValueError(f"VAD requires mono audio, got {num_channels} channels")
        
        # Read all frames
        audio_data = wf.readframes(wf.getnframes())
    
    # Process in frames
    frame_duration = config.vad_frame_duration_ms
    frame_size = int(sample_rate * frame_duration / 1000) * sample_width
    
    segments = []
    current_speech_start = None
    
    for i, offset in enumerate(range(0, len(audio_data), frame_size)):
        frame = audio_data[offset:offset + frame_size]
        
        if len(frame) < frame_size:
            break
        
        timestamp = i * frame_duration / 1000.0
        
        is_speech = vad.is_speech(frame, sample_rate)
        
        if is_speech and current_speech_start is None:
            # Start of speech
            current_speech_start = timestamp
        elif not is_speech and current_speech_start is not None:
            # End of speech
            segments.append((current_speech_start, timestamp))
            current_speech_start = None
    
    # Close final segment if needed
    if current_speech_start is not None:
        final_time = len(audio_data) / (sample_rate * sample_width)
        segments.append((current_speech_start, final_time))
    
    logger.info(f"✓ Phase 1 complete: {len(segments)} speech segments detected")
    
    return segments


# ============================================================================
# PHASE 2: PYANNOTE SEGMENTATION
# ============================================================================

def refine_with_pyannote(
    audio_path: str,
    vad_segments: List[Tuple[float, float]],
    config: SegmentationConfig
) -> List[AudioSegment]:
    """
    Phase 2: Refine segments with Pyannote speaker boundaries and overlap detection
    
    NOTE: This requires Pyannote model access and GPU
    Currently returns VAD segments as-is (TODO: implement full Pyannote integration)
    """
    logger.info("Phase 2: Pyannote refinement (placeholder - using VAD segments)")
    
    # Convert VAD tuples to AudioSegment objects
    segments = []
    for i, (start, end) in enumerate(vad_segments):
        seg = AudioSegment(
            segment_id=i,
            start=start,
            end=end,
            vad_speech=True
        )
        segments.append(seg)
    
    logger.info(f"✓ Phase 2 complete: {len(segments)} refined segments")
    
    return segments


# ============================================================================
# PHASE 3: SMART CHUNK BUILDER
# ============================================================================

def build_smart_chunks(
    segments: List[AudioSegment],
    config: SegmentationConfig
) -> List[AudioSegment]:
    """
    Phase 3: Merge short segments, split long ones, add padding
    """
    logger.info("Phase 3: Building smart chunks")
    
    merged_segments = []
    current_chunk = None
    next_id = 0
    
    for seg in segments:
        # If segment is too short and we have a current chunk, try to merge
        if seg.duration < config.min_chunk_duration and current_chunk is not None:
            # Merge into current chunk
            current_chunk.end = seg.end
            current_chunk.duration = current_chunk.end - current_chunk.start
            current_chunk.is_merged = True
            current_chunk.parent_segments.append(seg.id)
        
        # If segment is too long, split it
        elif seg.duration > config.max_chunk_duration:
            # Flush current chunk if exists
            if current_chunk is not None:
                merged_segments.append(current_chunk)
                current_chunk = None
            
            # Split into max_chunk_duration pieces
            num_splits = int(np.ceil(seg.duration / config.max_chunk_duration))
            split_duration = seg.duration / num_splits
            
            for split_idx in range(num_splits):
                split_start = seg.start + (split_idx * split_duration)
                split_end = min(seg.start + ((split_idx + 1) * split_duration), seg.end)
                
                split_seg = AudioSegment(
                    segment_id=next_id,
                    start=split_start,
                    end=split_end,
                    vad_speech=seg.vad_speech,
                    is_split=True,
                    parent_segments=[seg.id]
                )
                merged_segments.append(split_seg)
                next_id += 1
        
        else:
            # Normal segment
            if current_chunk is not None:
                merged_segments.append(current_chunk)
            
            current_chunk = AudioSegment(
                segment_id=next_id,
                start=seg.start,
                end=seg.end,
                vad_speech=seg.vad_speech
            )
            next_id += 1
    
    # Flush final chunk
    if current_chunk is not None:
        merged_segments.append(current_chunk)
    
    logger.info(f"✓ Phase 3 complete: {len(merged_segments)} smart chunks created")
    
    return merged_segments


def export_chunk_wavs(
    audio_path: str,
    segments: List[AudioSegment],
    output_dir: str,
    config: SegmentationConfig
) -> List[AudioSegment]:
    """
    Export individual WAV files for each chunk with padding
    Updates segment.chunk_path
    """
    logger.info(f"Exporting {len(segments)} chunk WAV files")
    
    output_dir = Path(output_dir) / "chunks"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load source audio
    with wave.open(audio_path, 'rb') as wf:
        sample_rate = wf.getframerate()
        sample_width = wf.getsampwidth()
        num_channels = wf.getnchannels()
        
        # Read all frames
        audio_data = wf.readframes(wf.getnframes())
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
    
    padding_samples = int((config.chunk_padding_ms / 1000.0) * sample_rate)
    
    for seg in segments:
        # Calculate sample boundaries with padding
        start_sample = max(0, int(seg.start * sample_rate) - padding_samples)
        end_sample = min(len(audio_array), int(seg.end * sample_rate) + padding_samples)
        
        chunk_data = audio_array[start_sample:end_sample]
        
        # Export chunk WAV
        chunk_filename = f"segment_{seg.id:04d}.wav"
        chunk_path = output_dir / chunk_filename
        
        with wave.open(str(chunk_path), 'wb') as chunk_wf:
            chunk_wf.setnchannels(num_channels)
            chunk_wf.setsampwidth(sample_width)
            chunk_wf.setframerate(sample_rate)
            chunk_wf.writeframes(chunk_data.tobytes())
        
        # Update segment
        seg.chunk_path = f"chunks/{chunk_filename}"
    
    logger.info(f"✓ Exported {len(segments)} chunk WAV files")
    
    return segments


# ============================================================================
# MAIN PIPELINE ORCHESTRATOR
# ============================================================================

def segment_audio_phased(
    video_path: str,
    video_id: str,
    output_base: Optional[str] = None,
    config: Optional[SegmentationConfig] = None
) -> SegmentationManifest:
    """
    Main phased segmentation pipeline orchestrator
    
    Args:
        video_path: Path to source video file
        video_id: Unique identifier for this video
        output_base: Base directory for outputs (default from config)
        config: SegmentationConfig instance (creates default if None)
    
    Returns:
        SegmentationManifest with all segment data
    """
    if config is None:
        config = SegmentationConfig()
    
    if output_base is not None:
        config.output_base = output_base
    
    # Create video-specific output directory
    output_dir = Path(config.output_base) / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"=== PHASED SEGMENTATION PIPELINE START ===")
    logger.info(f"Video: {video_path}")
    logger.info(f"Output: {output_dir}")
    
    # Initialize manifest
    manifest = SegmentationManifest(video_id, video_path)
    
    # Phase 0: Extract and normalize audio
    audio_path, metadata = extract_and_normalize_audio(
        video_path,
        str(output_dir / "audio"),
        config
    )
    manifest.audio_path = audio_path
    manifest.duration = metadata.get('duration', 0.0)
    manifest.metadata = metadata
    
    # Phase 1: VAD segmentation
    vad_segments = segment_with_vad(audio_path, config)
    
    # Phase 2: Pyannote refinement
    refined_segments = refine_with_pyannote(audio_path, vad_segments, config)
    
    # Phase 3: Smart chunking
    smart_chunks = build_smart_chunks(refined_segments, config)
    
    # Export chunk WAVs
    final_segments = export_chunk_wavs(
        audio_path,
        smart_chunks,
        str(output_dir),
        config
    )
    
    # Add to manifest
    for seg in final_segments:
        manifest.add_segment(seg)
    
    logger.info(f"=== PHASED SEGMENTATION COMPLETE ===")
    logger.info(f"Total segments: {len(manifest.segments)}")
    logger.info(f"Total duration: {manifest.duration:.2f}s")
    
    return manifest


# ============================================================================
# MANIFEST I/O
# ============================================================================

def save_segmentation_manifest(manifest: SegmentationManifest, output_path: str):
    """Save segmentation manifest to JSON file"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ Manifest saved: {output_path}")


def load_segmentation_manifest(manifest_path: str) -> SegmentationManifest:
    """Load segmentation manifest from JSON file"""
    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    manifest = SegmentationManifest.from_dict(data)
    logger.info(f"✓ Manifest loaded: {manifest_path} ({len(manifest.segments)} segments)")
    
    return manifest
