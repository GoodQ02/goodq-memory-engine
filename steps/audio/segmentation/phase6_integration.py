"""
Phase 6: Final Integration and Harmonization
Orchestrates all phases and produces canonical segmentation manifest
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional
import os
import json
from datetime import datetime


def merge_all_segment_data(
    audio_segments: List[Dict[str, Any]],
    video_scenes: List[Dict[str, Any]],
    transcription_results: List[Dict[str, Any]],
    diarization_results: List[Dict[str, Any]],
    embeddings: List[Dict[str, Any]],
    metadata: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Merge all processing results into unified segment objects
    
    Args:
        audio_segments: Segments from Phase 3
        video_scenes: Scenes from Phase 5
        transcription_results: Whisper results from Phase 4
        diarization_results: Pyannote speaker data from Phase 4
        embeddings: CLAP/emotion embeddings from Phase 4
        metadata: Video/audio metadata
        
    Returns:
        Unified segment list with all enrichment data
    """
    unified = []
    
    for idx, segment in enumerate(audio_segments):
        seg_start = segment['start']
        seg_end = segment['end']
        
        # Initialize unified segment
        unified_seg = {
            'id': segment.get('id', idx),
            'start': seg_start,
            'end': seg_end,
            'duration': segment.get('duration', seg_end - seg_start),
            
            # Audio metadata
            'chunk_path': segment.get('chunk_path'),
            'vad_speech': segment.get('vad_speech', False),
            'overlap': segment.get('overlap', False),
            'speaker_changes': segment.get('speaker_changes', []),
            
            # Transcript data
            'transcript': None,
            'language': None,
            'confidence': None,
            
            # Speaker data
            'speakers': [],
            'primary_speaker': None,
            
            # Embeddings
            'clap_embedding': None,
            'emotion': None,
            'music_detected': False,
            
            # Video data
            'video_scenes': [],
            'scene_aligned': False,
            
            # Metadata
            'processing_timestamp': datetime.utcnow().isoformat(),
            'status': 'complete'
        }
        
        # Match transcription
        for trans in transcription_results:
            if trans.get('segment_id') == idx or (
                abs(trans.get('start', -999) - seg_start) < 0.1
            ):
                unified_seg['transcript'] = trans.get('text')
                unified_seg['language'] = trans.get('language')
                unified_seg['confidence'] = trans.get('avg_logprob')
                unified_seg['words'] = trans.get('words', [])
                break
        
        # Match diarization
        for diar in diarization_results:
            if diar.get('segment_id') == idx or (
                diar.get('start', -999) >= seg_start and 
                diar.get('end', -999) <= seg_end
            ):
                speaker_id = diar.get('speaker')
                if speaker_id and speaker_id not in unified_seg['speakers']:
                    unified_seg['speakers'].append(speaker_id)
                
                if not unified_seg['primary_speaker']:
                    unified_seg['primary_speaker'] = speaker_id
        
        # Match embeddings
        for emb in embeddings:
            if emb.get('segment_id') == idx or (
                abs(emb.get('start', -999) - seg_start) < 0.1
            ):
                unified_seg['clap_embedding'] = emb.get('clap_vector')
                unified_seg['emotion'] = emb.get('emotion')
                unified_seg['music_detected'] = emb.get('music', False)
                break
        
        # Match video scenes
        for scene in video_scenes:
            scene_start = scene.get('start', 0)
            scene_end = scene.get('end', 0)
            
            # Check for overlap
            if not (scene_end <= seg_start or scene_start >= seg_end):
                unified_seg['video_scenes'].append({
                    'start': scene_start,
                    'end': scene_end,
                    'confidence': scene.get('confidence', 0.5),
                    'strategy': scene.get('strategy', 'unknown')
                })
        
        # Check scene alignment
        if unified_seg['video_scenes']:
            for scene in unified_seg['video_scenes']:
                if abs(scene['start'] - seg_start) < 0.5 or abs(scene['end'] - seg_end) < 0.5:
                    unified_seg['scene_aligned'] = True
                    break
        
        unified.append(unified_seg)
    
    return unified


def create_frame_index(
    segments: List[Dict[str, Any]],
    fps: float
) -> List[Dict[str, Any]]:
    """
    Create frame-level index for video editing / export
    
    Args:
        segments: Unified segments
        fps: Video frame rate
        
    Returns:
        Frame index mapping frame numbers to segments
    """
    frame_index = []
    
    for segment in segments:
        start_frame = int(segment['start'] * fps)
        end_frame = int(segment['end'] * fps)
        
        frame_index.append({
            'segment_id': segment['id'],
            'start_frame': start_frame,
            'end_frame': end_frame,
            'frame_count': end_frame - start_frame,
            'has_speech': segment.get('vad_speech', False),
            'has_transcript': bool(segment.get('transcript')),
            'speakers': segment.get('speakers', []),
            'scenes': len(segment.get('video_scenes', []))
        })
    
    return frame_index


def generate_segmentation_manifest(
    video_path: str,
    unified_segments: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    output_dir: str
) -> str:
    """
    Generate final canonical segmentation manifest
    
    Args:
        video_path: Source video path
        unified_segments: All segments with full enrichment
        metadata: Video/audio metadata
        output_dir: Output directory
        
    Returns:
        Path to saved manifest file
    """
    fps = metadata.get('fps', 30.0)
    
    manifest = {
        'version': '1.0.0',
        'schema': 'goodq4all_segmentation_v1',
        'generated': datetime.utcnow().isoformat(),
        
        # Source info
        'source': {
            'video_path': video_path,
            'duration': metadata.get('duration', 0),
            'fps': fps,
            'resolution': metadata.get('resolution'),
            'audio_sample_rate': metadata.get('audio_sample_rate', 16000)
        },
        
        # Processing summary
        'summary': {
            'total_segments': len(unified_segments),
            'speech_segments': sum(1 for s in unified_segments if s.get('vad_speech')),
            'transcribed_segments': sum(1 for s in unified_segments if s.get('transcript')),
            'unique_speakers': len(set(
                speaker 
                for seg in unified_segments 
                for speaker in seg.get('speakers', [])
            )),
            'total_scenes': sum(len(s.get('video_scenes', [])) for s in unified_segments),
            'scene_aligned_segments': sum(1 for s in unified_segments if s.get('scene_aligned'))
        },
        
        # Segments
        'segments': unified_segments,
        
        # Frame index
        'frame_index': create_frame_index(unified_segments, fps),
        
        # Processing metadata
        'processing': {
            'phases_completed': [
                'phase0_normalization',
                'phase1_vad_segmentation',
                'phase2_pyannote_segmentation',
                'phase3_smart_chunking',
                'phase4_audio_processing',
                'phase5_video_scene_detection',
                'phase6_integration'
            ],
            'pipeline_version': '1.0.0',
            'environment': 'goodq_core + wsl2_audio'
        }
    }
    
    # Save manifest
    manifest_path = os.path.join(output_dir, 'segmentation.json')
    os.makedirs(output_dir, exist_ok=True)
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"[PHASE6] Segmentation manifest saved to: {manifest_path}")
    print(f"[PHASE6] Total segments: {len(unified_segments)}")
    print(f"[PHASE6] Speech segments: {manifest['summary']['speech_segments']}")
    print(f"[PHASE6] Unique speakers: {manifest['summary']['unique_speakers']}")
    print(f"[PHASE6] Total scenes: {manifest['summary']['total_scenes']}")
    
    return manifest_path


def validate_manifest(manifest_path: str) -> Dict[str, Any]:
    """
    Validate the segmentation manifest for completeness and quality
    
    Args:
        manifest_path: Path to manifest file
        
    Returns:
        Validation report
    """
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    segments = manifest.get('segments', [])
    
    validation = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'stats': {}
    }
    
    # Check segment continuity
    for i in range(len(segments) - 1):
        current_end = segments[i]['end']
        next_start = segments[i+1]['start']
        
        gap = next_start - current_end
        if gap > 1.0:  # More than 1 second gap
            validation['warnings'].append(
                f"Large gap between segment {i} and {i+1}: {gap:.2f}s"
            )
        elif gap < -0.1:  # Overlapping segments
            validation['warnings'].append(
                f"Overlapping segments {i} and {i+1}: {gap:.2f}s overlap"
            )
    
    # Check for missing data
    missing_transcripts = sum(1 for s in segments if not s.get('transcript'))
    missing_speakers = sum(1 for s in segments if not s.get('speakers'))
    
    validation['stats'] = {
        'total_segments': len(segments),
        'missing_transcripts': missing_transcripts,
        'missing_speakers': missing_speakers,
        'transcript_coverage': (len(segments) - missing_transcripts) / len(segments) if segments else 0,
        'speaker_coverage': (len(segments) - missing_speakers) / len(segments) if segments else 0
    }
    
    # Warnings for low coverage
    if validation['stats']['transcript_coverage'] < 0.8:
        validation['warnings'].append(
            f"Low transcript coverage: {validation['stats']['transcript_coverage']*100:.1f}%"
        )
    
    if validation['stats']['speaker_coverage'] < 0.8:
        validation['warnings'].append(
            f"Low speaker coverage: {validation['stats']['speaker_coverage']*100:.1f}%"
        )
    
    print("[VALIDATION] Manifest validation complete")
    print(f"  - Segments: {validation['stats']['total_segments']}")
    print(f"  - Transcript coverage: {validation['stats']['transcript_coverage']*100:.1f}%")
    print(f"  - Speaker coverage: {validation['stats']['speaker_coverage']*100:.1f}%")
    print(f"  - Warnings: {len(validation['warnings'])}")
    
    return validation


if __name__ == '__main__':
    print("Phase 6: Final Integration Module")
    print("=" * 60)
    print("Merges all processing phases into canonical segmentation manifest")
