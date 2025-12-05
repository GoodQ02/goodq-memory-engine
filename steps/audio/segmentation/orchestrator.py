"""
Phased Segmentation Engine - Master Orchestrator
Coordinates all 6 phases of video/audio segmentation pipeline
"""
from __future__ import annotations
from typing import Dict, List, Any, Optional
import os
import json
import time
from pathlib import Path

# Import all phase modules
from .phase0_normalization import normalize_media, extract_metadata
from .phase1_vad_segmentation import segment_with_webrtc_vad
from .phase2_pyannote import segment_with_pyannote, enhance_segments_with_pyannote
from .phase3_chunk_builder import run_phase3_chunk_builder
from .phase4_audio_processor import Phase4AudioProcessor, process_segmented_audio
from .phase5_video_scene_integration import (
    process_video_chunks_with_scenes,
    upgrade_analysis_for_legacy_scene_detect
)
from .phase6_integration import (
    merge_all_segment_data,
    generate_segmentation_manifest,
    validate_manifest
)


class PhasedSegmentationEngine:
    """
    Master orchestrator for phased video/audio segmentation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the segmentation engine
        
        Args:
            config: Configuration dictionary with all phase settings
        """
        self.config = config
        self.phase_results = {}
        self.timings = {}
        
    def run_full_pipeline(
        self,
        video_path: str,
        output_base_dir: str,
        skip_phases: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete 6-phase segmentation pipeline
        
        Args:
            video_path: Path to input video file
            output_base_dir: Base directory for all outputs
            skip_phases: Optional list of phases to skip (for testing)
            
        Returns:
            Complete pipeline results including manifest path
        """
        skip_phases = skip_phases or []
        
        print("=" * 80)
        print("PHASED SEGMENTATION ENGINE - FULL PIPELINE")
        print("=" * 80)
        print(f"Input: {video_path}")
        print(f"Output: {output_base_dir}")
        print()
        
        # Create output structure
        video_name = Path(video_path).stem
        video_output_dir = os.path.join(output_base_dir, video_name)
        
        dirs = {
            'base': video_output_dir,
            'audio': os.path.join(video_output_dir, 'audio'),
            'chunks': os.path.join(video_output_dir, 'audio', 'chunks'),
            'metadata': os.path.join(video_output_dir, 'metadata'),
            'transcripts': os.path.join(video_output_dir, 'transcripts'),
            'embeddings': os.path.join(video_output_dir, 'embeddings')
        }
        
        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        # PHASE 0: Pre-Normalization
        if 'phase0' not in skip_phases:
            print("\n[PHASE 0] Pre-Normalization")
            print("-" * 80)
            start_time = time.time()
            
            audio_path = os.path.join(dirs['audio'], 'normalized.wav')
            normalize_media(video_path, audio_path, self.config.get('phase0', {}))
            
            metadata = extract_metadata(video_path)
            metadata_path = os.path.join(dirs['metadata'], 'source_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.phase_results['phase0'] = {
                'audio_path': audio_path,
                'metadata': metadata
            }
            self.timings['phase0'] = time.time() - start_time
            print(f"✓ Phase 0 complete in {self.timings['phase0']:.2f}s")
        else:
            print("\n[PHASE 0] SKIPPED")
            
        # PHASE 1: WebRTC-VAD Segmentation
        if 'phase1' not in skip_phases:
            print("\n[PHASE 1] WebRTC-VAD Segmentation")
            print("-" * 80)
            start_time = time.time()
            
            audio_path = self.phase_results['phase0']['audio_path']
            vad_segments = segment_with_webrtc_vad(
                audio_path,
                self.config.get('phase1', {})
            )
            
            vad_path = os.path.join(dirs['metadata'], 'vad_segments.json')
            with open(vad_path, 'w') as f:
                json.dump({'segments': vad_segments}, f, indent=2)
            
            self.phase_results['phase1'] = {
                'vad_segments': vad_segments,
                'vad_path': vad_path
            }
            self.timings['phase1'] = time.time() - start_time
            print(f"✓ Phase 1 complete in {self.timings['phase1']:.2f}s")
            print(f"  Detected {len(vad_segments)} VAD segments")
        else:
            print("\n[PHASE 1] SKIPPED")
            
        # PHASE 2: Pyannote Segmentation
        if 'phase2' not in skip_phases:
            print("\n[PHASE 2] Pyannote Segmentation")
            print("-" * 80)
            start_time = time.time()
            
            audio_path = self.phase_results['phase0']['audio_path']
            pyannote_segments = segment_with_pyannote(
                audio_path,
                self.config.get('phase2', {})
            )
            
            # Enhance VAD segments with Pyannote data
            vad_segments = self.phase_results['phase1']['vad_segments']
            enhanced_segments = enhance_segments_with_pyannote(
                vad_segments,
                pyannote_segments
            )
            
            pyannote_path = os.path.join(dirs['metadata'], 'pyannote_segments.json')
            with open(pyannote_path, 'w') as f:
                json.dump({'segments': enhanced_segments}, f, indent=2)
            
            self.phase_results['phase2'] = {
                'enhanced_segments': enhanced_segments,
                'pyannote_path': pyannote_path
            }
            self.timings['phase2'] = time.time() - start_time
            print(f"✓ Phase 2 complete in {self.timings['phase2']:.2f}s")
            print(f"  Enhanced {len(enhanced_segments)} segments with Pyannote data")
        else:
            print("\n[PHASE 2] SKIPPED")
            
        # PHASE 3: Smart Chunk Building
        if 'phase3' not in skip_phases:
            print("\n[PHASE 3] Smart Chunk Building")
            print("-" * 80)
            start_time = time.time()
            
            enhanced_segments = self.phase_results['phase2']['enhanced_segments']
            audio_path = self.phase_results['phase0']['audio_path']
            
            smart_chunks = build_smart_chunks(
                enhanced_segments,
                self.config.get('phase3', {})
            )
            
            # Save chunk WAV files
            chunk_paths = save_chunk_wavs(
                audio_path,
                smart_chunks,
                dirs['chunks']
            )
            
            chunks_path = os.path.join(dirs['metadata'], 'smart_chunks.json')
            with open(chunks_path, 'w') as f:
                json.dump({'chunks': smart_chunks}, f, indent=2)
            
            self.phase_results['phase3'] = {
                'smart_chunks': smart_chunks,
                'chunk_paths': chunk_paths,
                'chunks_path': chunks_path
            }
            self.timings['phase3'] = time.time() - start_time
            print(f"✓ Phase 3 complete in {self.timings['phase3']:.2f}s")
            print(f"  Created {len(smart_chunks)} smart chunks")
        else:
            print("\n[PHASE 3] SKIPPED")
            
        # PHASE 4: Heavy Audio Processing (WSL2)
        if 'phase4' not in skip_phases:
            print("\n[PHASE 4] Heavy Audio Processing (WSL2)")
            print("-" * 80)
            start_time = time.time()
            
            smart_chunks = self.phase_results['phase3']['smart_chunks']
            audio_config = AudioProcessingConfig(**self.config.get('phase4', {}))
            
            audio_results = process_chunks_with_wsl2(
                smart_chunks,
                audio_config,
                dirs['transcripts'],
                dirs['embeddings']
            )
            
            self.phase_results['phase4'] = audio_results
            self.timings['phase4'] = time.time() - start_time
            print(f"✓ Phase 4 complete in {self.timings['phase4']:.2f}s")
            print(f"  Processed {len(audio_results.get('transcriptions', []))} chunks")
        else:
            print("\n[PHASE 4] SKIPPED")
            
        # PHASE 5: Video Scene Detection
        if 'phase5' not in skip_phases:
            print("\n[PHASE 5] Video Scene Detection")
            print("-" * 80)
            start_time = time.time()
            
            smart_chunks = self.phase_results['phase3']['smart_chunks']
            
            scene_results = process_video_chunks_with_scenes(
                video_path,
                smart_chunks,
                dirs['metadata'],
                self.config.get('phase5', {})
            )
            
            self.phase_results['phase5'] = scene_results
            self.timings['phase5'] = time.time() - start_time
            print(f"✓ Phase 5 complete in {self.timings['phase5']:.2f}s")
            print(f"  Detected {scene_results.get('total_scenes', 0)} video scenes")
        else:
            print("\n[PHASE 5] SKIPPED")
            
        # PHASE 6: Final Integration
        if 'phase6' not in skip_phases:
            print("\n[PHASE 6] Final Integration")
            print("-" * 80)
            start_time = time.time()
            
            # Gather all data
            audio_segments = self.phase_results['phase3']['smart_chunks']
            video_scenes = self.phase_results['phase5'].get('video_scenes', [])
            audio_results = self.phase_results['phase4']
            metadata = self.phase_results['phase0']['metadata']
            
            # Merge everything
            unified_segments = merge_all_segment_data(
                audio_segments,
                video_scenes,
                audio_results.get('transcriptions', []),
                audio_results.get('diarizations', []),
                audio_results.get('embeddings', []),
                metadata
            )
            
            # Generate manifest
            manifest_path = generate_segmentation_manifest(
                video_path,
                unified_segments,
                metadata,
                dirs['metadata']
            )
            
            # Validate
            validation = validate_manifest(manifest_path)
            
            self.phase_results['phase6'] = {
                'manifest_path': manifest_path,
                'unified_segments': unified_segments,
                'validation': validation
            }
            self.timings['phase6'] = time.time() - start_time
            print(f"✓ Phase 6 complete in {self.timings['phase6']:.2f}s")
        else:
            print("\n[PHASE 6] SKIPPED")
        
        # Final summary
        print("\n" + "=" * 80)
        print("PIPELINE COMPLETE")
        print("=" * 80)
        total_time = sum(self.timings.values())
        print(f"Total time: {total_time:.2f}s")
        print(f"\nPhase timings:")
        for phase, duration in self.timings.items():
            print(f"  {phase}: {duration:.2f}s ({duration/total_time*100:.1f}%)")
        
        if 'phase6' in self.phase_results:
            print(f"\n✓ Segmentation manifest: {self.phase_results['phase6']['manifest_path']}")
        
        return {
            'phase_results': self.phase_results,
            'timings': self.timings,
            'total_time': total_time,
            'output_dir': video_output_dir
        }


def create_default_config() -> Dict[str, Any]:
    """
    Create default configuration for all phases
    
    Returns:
        Default configuration dictionary
    """
    return {
        'phase0': {
            'target_sample_rate': 16000,
            'channels': 1,
            'bit_depth': 16
        },
        'phase1': {
            'aggressiveness': 3,
            'frame_duration_ms': 30,
            'min_speech_duration': 0.3,
            'min_silence_duration': 0.5
        },
        'phase2': {
            'min_duration_off': 0.0,
            'use_auth_token': None  # Set if using private Hugging Face models
        },
        'phase3': {
            'max_chunk_duration': 40.0,
            'min_chunk_duration': 1.0,
            'target_chunk_duration': 20.0,
            'padding_sec': 0.25,
            'overlap_sec': 0.5
        },
        'phase4': {
            'enable_transcription': True,
            'enable_diarization': True,
            'enable_embeddings': True,
            'enable_emotion': True,
            'enable_music_detection': True,
            'whisper_model': 'medium',
            'language': None  # Auto-detect
        },
        'phase5': {
            'scene_threshold': 30.0,
            'min_scene_len_sec': 2.0
        }
    }


if __name__ == '__main__':
    # Example usage
    print("Phased Segmentation Engine - Master Orchestrator")
    print("=" * 80)
    
    # Show upgrade analysis
    analysis = upgrade_analysis_for_legacy_scene_detect()
    print("\nLegacy Scene Detect Upgrade Analysis:")
    print(json.dumps(analysis, indent=2))
    
    print("\nDefault Configuration:")
    config = create_default_config()
    print(json.dumps(config, indent=2))
