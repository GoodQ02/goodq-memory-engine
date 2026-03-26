"""
Phased Segmentation Engine - Master Orchestrator.

Coordinates segmentation engine phases SEG_P0-SEG_P6. These SEG_P labels are
distinct from later project milestone phases documented elsewhere in the repo.
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

    def _phase_cfg(self, phase_name: str) -> Dict[str, Any]:
        if isinstance(self.config.get(phase_name), dict):
            return dict(self.config.get(phase_name) or {})
        segmentation_cfg = self.config.get('segmentation')
        if isinstance(segmentation_cfg, dict) and isinstance(segmentation_cfg.get(phase_name), dict):
            return dict(segmentation_cfg.get(phase_name) or {})
        return {}

    def _phase_enabled(self, phase_name: str, *, default: bool = True) -> bool:
        phase_cfg = self._phase_cfg(phase_name)
        if 'enabled' in phase_cfg:
            return bool(phase_cfg.get('enabled'))
        return default

    def _phase3_builder_cfg(self) -> Dict[str, Any]:
        phase3_cfg = self._phase_cfg('phase3')
        return {
            'min_chunk_duration': phase3_cfg.get('min_chunk_duration', 1.0),
            'max_chunk_duration': phase3_cfg.get('max_chunk_duration', 40.0),
            'target_chunk_duration': phase3_cfg.get('target_chunk_duration', 20.0),
            'padding_ms': phase3_cfg.get('padding_ms', phase3_cfg.get('chunk_padding_ms', 250)),
            'overlap_ms': phase3_cfg.get('overlap_ms', phase3_cfg.get('chunk_overlap_ms', 500)),
            'merge_gap_threshold': phase3_cfg.get('merge_gap_threshold', phase3_cfg.get('merge_threshold', 0.5)),
        }

    def _phase4_runtime_cfg(self) -> Dict[str, Any]:
        runtime_cfg: Dict[str, Any] = {}
        if isinstance(self.config.get('audio'), dict):
            runtime_cfg['audio'] = dict(self.config.get('audio') or {})
        else:
            runtime_cfg['audio'] = dict(self._phase_cfg('phase4') or {})
        if isinstance(self.config.get('run'), dict):
            runtime_cfg['run'] = dict(self.config.get('run') or {})
        return runtime_cfg

    def _phase4_results_for_phase6(self, audio_results: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        processed_segments = audio_results.get('segments') or audio_results.get('chunks') or []
        transcriptions: List[Dict[str, Any]] = []
        diarizations: List[Dict[str, Any]] = []
        embeddings: List[Dict[str, Any]] = []

        for segment in processed_segments:
            segment_id = segment.get('id')
            transcript_segments = segment.get('transcript_segments') or []
            transcript_text = segment.get('transcript')
            if not transcript_text and transcript_segments:
                transcript_text = " ".join(
                    str(part.get('text', '')).strip()
                    for part in transcript_segments
                    if str(part.get('text', '')).strip()
                ).strip()
            if transcript_text:
                words: List[Dict[str, Any]] = []
                for transcript_segment in transcript_segments:
                    segment_words = transcript_segment.get('words')
                    if isinstance(segment_words, list):
                        words.extend(segment_words)
                transcriptions.append(
                    {
                        'segment_id': segment_id,
                        'start': segment.get('start'),
                        'end': segment.get('end'),
                        'text': transcript_text,
                        'language': segment.get('language'),
                        'words': words,
                    }
                )

            for diarization in segment.get('diarization') or []:
                diarization_entry = dict(diarization)
                diarization_entry.setdefault('segment_id', segment_id)
                diarizations.append(diarization_entry)

            if any(
                [
                    segment.get('audio_embedding') is not None,
                    segment.get('emotion') is not None,
                    bool(segment.get('music_detected') or segment.get('has_music')),
                ]
            ):
                embeddings.append(
                    {
                        'segment_id': segment_id,
                        'start': segment.get('start'),
                        'clap_vector': segment.get('audio_embedding'),
                        'emotion': segment.get('emotion'),
                        'music': bool(segment.get('music_detected') or segment.get('has_music')),
                    }
                )

        return {
            'transcriptions': transcriptions,
            'diarizations': diarizations,
            'embeddings': embeddings,
        }
        
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
        print("PHASED SEGMENTATION ENGINE - FULL PIPELINE (SEG_P0-SEG_P6)")
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
            'video': os.path.join(video_output_dir, 'video'),
            'metadata': os.path.join(video_output_dir, 'metadata'),
            'transcripts': os.path.join(video_output_dir, 'transcripts'),
            'embeddings': os.path.join(video_output_dir, 'embeddings')
        }
        
        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        # SEG_P0: Pre-Normalization
        if 'phase0' not in skip_phases:
            print("\n[SEG_P0] Pre-Normalization")
            print("-" * 80)
            start_time = time.time()
            
            audio_path = os.path.join(dirs['audio'], 'normalized.wav')
            normalize_media(video_path, audio_path, self._phase_cfg('phase0'))
            
            metadata = extract_metadata(video_path)
            metadata_path = os.path.join(dirs['metadata'], 'source_metadata.json')
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.phase_results['phase0'] = {
                'audio_path': audio_path,
                'metadata': metadata
            }
            self.timings['phase0'] = time.time() - start_time
            print(f"[SYMBOL] SEG_P0 complete in {self.timings['phase0']:.2f}s")
        else:
            print("\n[SEG_P0] SKIPPED")
            
        # SEG_P1: WebRTC-VAD Segmentation
        if 'phase1' not in skip_phases:
            print("\n[SEG_P1] WebRTC-VAD Segmentation")
            print("-" * 80)
            start_time = time.time()
            
            audio_path = self.phase_results['phase0']['audio_path']
            vad_segments = segment_with_webrtc_vad(
                audio_path,
                self._phase_cfg('phase1')
            )
            
            vad_path = os.path.join(dirs['metadata'], 'vad_segments.json')
            with open(vad_path, 'w') as f:
                json.dump({'segments': vad_segments}, f, indent=2)
            
            self.phase_results['phase1'] = {
                'vad_segments': vad_segments,
                'vad_path': vad_path
            }
            self.timings['phase1'] = time.time() - start_time
            print(f"[SYMBOL] SEG_P1 complete in {self.timings['phase1']:.2f}s")
            print(f"  Detected {len(vad_segments)} VAD segments")
        else:
            print("\n[SEG_P1] SKIPPED")
            
        # SEG_P2: Pyannote Segmentation
        phase2_enabled = self._phase_enabled('phase2', default=True)
        if 'phase2' not in skip_phases and phase2_enabled:
            print("\n[SEG_P2] Pyannote Segmentation")
            print("-" * 80)
            start_time = time.time()
            
            audio_path = self.phase_results['phase0']['audio_path']
            pyannote_segments = segment_with_pyannote(
                audio_path,
                self._phase_cfg('phase2')
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
            print(f"[SYMBOL] SEG_P2 complete in {self.timings['phase2']:.2f}s")
            print(f"  Enhanced {len(enhanced_segments)} segments with Pyannote data")
        else:
            print("\n[SEG_P2] SKIPPED")
            self.phase_results['phase2'] = {
                'enhanced_segments': list(self.phase_results['phase1']['vad_segments']),
                'pyannote_path': None,
                'skipped': True,
            }
            
        # SEG_P3: Smart Chunk Building
        if 'phase3' not in skip_phases:
            print("\n[SEG_P3] Smart Chunk Building")
            print("-" * 80)
            start_time = time.time()
            
            enhanced_segments = self.phase_results['phase2']['enhanced_segments']
            audio_path = self.phase_results['phase0']['audio_path']
            
            phase3_output = run_phase3_chunk_builder(
                {'segments': enhanced_segments},
                audio_path,
                dirs['audio'],
                self._phase3_builder_cfg(),
            )

            self.phase_results['phase3'] = {
                'smart_chunks': list(phase3_output.get('chunks') or []),
                'chunks': list(phase3_output.get('chunks') or []),
                'chunk_paths': [
                    chunk.get('chunk_path')
                    for chunk in phase3_output.get('chunks', [])
                    if isinstance(chunk, dict) and chunk.get('chunk_path')
                ],
                'chunks_path': phase3_output.get('manifest_path'),
                'manifest_path': phase3_output.get('manifest_path'),
                'audio_manifest_path': phase3_output.get('manifest_path'),
            }
            self.timings['phase3'] = time.time() - start_time
            print(f"[SYMBOL] SEG_P3 complete in {self.timings['phase3']:.2f}s")
            print(f"  Created {len(self.phase_results['phase3']['chunks'])} smart chunks")
        else:
            print("\n[SEG_P3] SKIPPED")
            
        # SEG_P4: Heavy Audio Processing (WSL2)
        if 'phase4' not in skip_phases:
            print("\n[SEG_P4] Heavy Audio Processing (WSL2)")
            print("-" * 80)
            start_time = time.time()
            
            phase3_manifest_path = self.phase_results['phase3'].get('manifest_path')
            if not phase3_manifest_path:
                raise RuntimeError("Phase 3 did not produce segmentation.json")

            audio_results = process_segmented_audio(
                phase3_manifest_path,
                video_path,
                dirs['base'],
                self._phase4_runtime_cfg(),
            )
            
            self.phase_results['phase4'] = audio_results
            self.timings['phase4'] = time.time() - start_time
            print(f"[SYMBOL] SEG_P4 complete in {self.timings['phase4']:.2f}s")
            processed_segments = audio_results.get('segments') or audio_results.get('chunks') or []
            print(f"  Processed {len(processed_segments)} chunks")
        else:
            print("\n[SEG_P4] SKIPPED")
            
        # SEG_P5: Video Scene Detection
        phase5_enabled = self._phase_enabled('phase5', default=True)
        if 'phase5' not in skip_phases and phase5_enabled:
            print("\n[SEG_P5] Video Scene Detection")
            print("-" * 80)
            start_time = time.time()
            
            smart_chunks = self.phase_results['phase3']['chunks']
            
            scene_results = process_video_chunks_with_scenes(
                video_path,
                smart_chunks,
                dirs['video'],
                self._phase_cfg('phase5')
            )
            
            self.phase_results['phase5'] = scene_results
            self.timings['phase5'] = time.time() - start_time
            print(f"[SYMBOL] SEG_P5 complete in {self.timings['phase5']:.2f}s")
            print(f"  Detected {scene_results.get('total_scenes', 0)} video scenes")
        else:
            print("\n[SEG_P5] SKIPPED")
            self.phase_results['phase5'] = {
                'video_scenes': [],
                'scene_manifest_path': None,
                'video_scenes_path': None,
                'unified_segments': [],
                'total_scenes': 0,
                'total_chunks': len(self.phase_results['phase3'].get('chunks') or []),
                'skipped': True,
            }
            
        # SEG_P6: Final Integration
        phase6_dependencies_ready = 'phase4' in self.phase_results and 'phase5' in self.phase_results
        if 'phase6' not in skip_phases and phase6_dependencies_ready:
            print("\n[SEG_P6] Final Integration")
            print("-" * 80)
            start_time = time.time()
            
            # Gather all data
            audio_segments = self.phase_results['phase3']['smart_chunks']
            video_scenes = self.phase_results['phase5'].get('video_scenes', [])
            audio_results = self.phase_results['phase4']
            metadata = self.phase_results['phase0']['metadata']
            phase6_inputs = self._phase4_results_for_phase6(audio_results)
            
            # Merge everything
            unified_segments = merge_all_segment_data(
                audio_segments,
                video_scenes,
                phase6_inputs.get('transcriptions', []),
                phase6_inputs.get('diarizations', []),
                phase6_inputs.get('embeddings', []),
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
            print(f"[SYMBOL] SEG_P6 complete in {self.timings['phase6']:.2f}s")
        else:
            print("\n[SEG_P6] SKIPPED")
        
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
            print(f"\n[SYMBOL] Segmentation manifest: {self.phase_results['phase6']['manifest_path']}")
        
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
            'chunk_padding_ms': 250,
            'chunk_overlap_ms': 500,
            'merge_threshold': 0.5,
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
