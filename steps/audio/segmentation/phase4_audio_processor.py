"""
Phase 4: Heavy Audio Processing Orchestrator

Processes segmented audio chunks through the full GPU audio pipeline:
- Faster-Whisper transcription (WSL2)
- Pyannote diarization (WSL2)
- CLAP embeddings (WSL2)
- Audio emotion detection (WSL2)
- Music detection
- Time hint extraction

All processing routes through existing WSL2 audio bridge to maintain
isolation and GPU safety.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging
import os
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from wsl2_audio.audio_bridge import transcribe_wsl2, transcribe_and_diarize_wsl2

logger = logging.getLogger(__name__)


class Phase4AudioProcessor:
    """
    Orchestrates heavy GPU audio processing on segmented chunks.
    
    Routes all processing through WSL2 audio bridge to maintain GPU isolation
    and leverage existing, validated audio pipeline infrastructure.
    """
    
    def __init__(self, cfg: Dict[str, Any]):
        """
        Initialize processor with configuration

        Args:
            cfg: Full GoodQ config dict
        """
        self.cfg = cfg
        self.audio_cfg = cfg.get("audio", {})
        self.transcribe_cfg = self.audio_cfg.get("transcribe", {})
        self.diarize_cfg = self.audio_cfg.get("diarize", {})
        run_cfg = cfg.get("run") if isinstance(cfg, dict) else None
        self.run_id = run_cfg.get("id") if isinstance(run_cfg, dict) else None
        
        # Processing parameters
        self.language = self.transcribe_cfg.get("language")  # None = auto-detect
        self.beam_size = self.transcribe_cfg.get("beam_size", 5)
        self.task = self.transcribe_cfg.get("task", "transcribe")
        self.chunk_timeout = self.audio_cfg.get("chunk_timeout", 600)  # 10 min per chunk
        
        # Parallel processing
        self.max_workers = self.audio_cfg.get("max_parallel_chunks", 2)
        
        logger.info(f"[PHASE 4] Initialized audio processor")
        logger.info(f"  Language: {self.language or 'auto-detect'}")
        logger.info(f"  Beam size: {self.beam_size}")
        logger.info(f"  Max parallel chunks: {self.max_workers}")
    
    def process_segments(
        self,
        segmentation_manifest: Dict[str, Any],
        video_path: str,
        output_dir: Path
    ) -> Dict[str, Any]:
        """
        Process all audio segments through heavy GPU pipeline
        
        Args:
            segmentation_manifest: Output from Phase 3 with chunks
            video_path: Original video path for context
            output_dir: Directory for storing results
            
        Returns:
            Enhanced manifest with transcription, diarization, embeddings
        """
        segments = segmentation_manifest.get("segments") or segmentation_manifest.get("chunks", [])
        
        if not segments:
            logger.warning("[PHASE 4] No segments to process")
            return segmentation_manifest
        
        logger.info(f"[PHASE 4] Processing {len(segments)} audio segments")
        logger.info(f"[PHASE 4] Using {self.max_workers} parallel workers")
        
        # Create results directory
        results_dir = output_dir / "audio_results"
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # Process chunks in parallel (but controlled)
        processed_segments = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_segment = {}
            for segment in segments:
                # Only process segments with actual speech
                if not segment.get("vad_speech", False):
                    # Skip non-speech segments but keep metadata
                    processed_segments.append(segment)
                    continue
                
                future = executor.submit(
                    self._process_single_chunk,
                    segment,
                    results_dir
                )
                future_to_segment[future] = segment
            
            # Collect results as they complete
            for future in as_completed(future_to_segment):
                segment = future_to_segment[future]
                try:
                    result = future.result()
                    processed_segments.append(result)
                except Exception as e:
                    logger.error(f"[PHASE 4] Failed to process segment {segment['id']}: {e}")
                    # Add error to segment
                    segment['processing_error'] = str(e)
                    processed_segments.append(segment)
        
        # Sort by segment ID to maintain order
        processed_segments.sort(key=lambda x: x['id'])
        
        # Update manifest
        enhanced_manifest = segmentation_manifest.copy()
        enhanced_manifest['segments'] = processed_segments
        enhanced_manifest['chunks'] = processed_segments
        enhanced_manifest['phase4_complete'] = True
        enhanced_manifest['processed_segment_count'] = len(processed_segments)
        
        # Save enhanced manifest
        manifest_path = output_dir / "metadata" / "segmentation_enhanced.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            json.dump(enhanced_manifest, f, indent=2)
        
        logger.info(f"[PHASE 4] Complete: {len(processed_segments)} segments processed")
        logger.info(f"[PHASE 4] Enhanced manifest saved: {manifest_path}")
        
        return enhanced_manifest
    
    def _process_single_chunk(
        self,
        segment: Dict[str, Any],
        results_dir: Path
    ) -> Dict[str, Any]:
        """
        Process a single audio chunk through all heavy steps
        
        Args:
            segment: Segment dict with chunk_path
            results_dir: Directory for results
            
        Returns:
            Enhanced segment with audio processing results
        """
        segment_id = segment['id']
        chunk_path = segment.get('chunk_path')
        
        if not chunk_path or not os.path.isfile(chunk_path):
            logger.warning(f"[PHASE 4] Segment {segment_id}: chunk file not found")
            return segment
        
        logger.info(f"[PHASE 4] Processing segment {segment_id}: {os.path.basename(chunk_path)}")
        
        enhanced = segment.copy()
        
        # Step 1: Transcription + Diarization (combined WSL2 call)
        try:
            result = transcribe_and_diarize_wsl2(
                chunk_path,
                language=self.language,
                beam_size=self.beam_size,
                timeout=self.chunk_timeout,
                run_id=self.run_id,
            )
            
            if result.get('status') == 'success':
                # Extract transcription
                enhanced['transcript'] = result.get('full_text', '')
                enhanced['transcript_segments'] = result.get('transcription', [])
                enhanced['language'] = result.get('info', {}).get('language')
                enhanced['language_probability'] = result.get('info', {}).get('language_probability')
                
                # Extract diarization
                enhanced['diarization'] = result.get('diarization', [])
                enhanced['speaker_count'] = result.get('speaker_count', 0)
                enhanced['speakers'] = self._extract_speaker_stats(result.get('diarization', []))
                
                # Merge transcription with speakers
                enhanced['merged_transcript'] = self._merge_transcript_speakers(
                    result.get('transcription', []),
                    result.get('diarization', [])
                )
                
                logger.info(f"[PHASE 4] Segment {segment_id}: transcription complete")
                logger.info(f"  Language: {enhanced.get('language', 'unknown')}")
                logger.info(f"  Speakers: {enhanced.get('speaker_count', 0)}")
            else:
                error = result.get('error', 'Unknown error')
                logger.error(f"[PHASE 4] Segment {segment_id}: WSL2 processing failed: {error}")
                enhanced['wsl2_error'] = error
        
        except Exception as e:
            logger.error(f"[PHASE 4] Segment {segment_id}: WSL2 exception: {e}")
            enhanced['wsl2_error'] = str(e)
        
        # Step 2: Audio embeddings (future integration point)
        # TODO: Add CLAP embedding extraction via WSL2
        # enhanced['audio_embedding'] = self._extract_clap_embedding(chunk_path)
        
        # Step 3: Emotion detection (future integration point)
        # TODO: Add audio emotion via WSL2
        # enhanced['audio_emotion'] = self._detect_audio_emotion(chunk_path)
        
        # Step 4: Music detection (future integration point)
        # TODO: Add music detection
        # enhanced['has_music'] = self._detect_music(chunk_path)
        
        return enhanced
    
    def _extract_speaker_stats(self, diarization: List[Dict]) -> List[Dict]:
        """Extract speaker statistics from diarization"""
        speakers_data = {}
        
        for seg in diarization:
            speaker = seg.get('speaker', 'UNKNOWN')
            duration = seg.get('duration', 0)
            
            if speaker not in speakers_data:
                speakers_data[speaker] = {
                    "speaker_id": speaker,
                    "total_duration": 0,
                    "segment_count": 0
                }
            
            speakers_data[speaker]['total_duration'] += duration
            speakers_data[speaker]['segment_count'] += 1
        
        speakers = list(speakers_data.values())
        speakers.sort(key=lambda x: x['total_duration'], reverse=True)
        
        return speakers
    
    def _merge_transcript_speakers(
        self,
        transcription: List[Dict],
        diarization: List[Dict]
    ) -> List[Dict]:
        """Merge transcription with speaker labels"""
        merged = []
        
        for trans_seg in transcription:
            trans_start = trans_seg['start']
            trans_end = trans_seg['end']
            
            # Find overlapping speaker
            speaker = "UNKNOWN"
            max_overlap = 0
            
            for diar_seg in diarization:
                diar_start = diar_seg['start']
                diar_end = diar_seg['end']
                
                # Calculate overlap
                overlap_start = max(trans_start, diar_start)
                overlap_end = min(trans_end, diar_end)
                overlap = max(0, overlap_end - overlap_start)
                
                if overlap > max_overlap:
                    max_overlap = overlap
                    speaker = diar_seg.get('speaker', 'UNKNOWN')
            
            merged.append({
                "start": trans_start,
                "end": trans_end,
                "text": trans_seg.get('text', ''),
                "speaker": speaker,
                "words": trans_seg.get('words', [])
            })
        
        return merged


def process_segmented_audio(
    segmentation_manifest_path: str,
    video_path: str,
    output_dir: str,
    cfg: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for Phase 4 processing
    
    Args:
        segmentation_manifest_path: Path to Phase 3 output manifest
        video_path: Original video path
        output_dir: Output directory for results
        cfg: Full GoodQ configuration
        
    Returns:
        Enhanced segmentation manifest with audio processing
    """
    logger.info("[PHASE 4] Starting heavy audio processing")
    
    # Load segmentation manifest
    with open(segmentation_manifest_path, 'r') as f:
        manifest = json.load(f)
    
    # Initialize processor
    processor = Phase4AudioProcessor(cfg)
    
    # Process all segments
    enhanced = processor.process_segments(
        manifest,
        video_path,
        Path(output_dir)
    )
    
    logger.info("[PHASE 4] Heavy audio processing complete")
    
    return enhanced


if __name__ == "__main__":
    """CLI for testing Phase 4"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Phase 4: Audio Processing")
    parser.add_argument("manifest", help="Path to segmentation manifest from Phase 3")
    parser.add_argument("video", help="Path to original video file")
    parser.add_argument("output", help="Output directory")
    parser.add_argument("--config", help="Config file path", 
                       default=str(project_root / "configs" / "goodq_config.yaml"))
    
    args = parser.parse_args()
    
    # Load config
    import yaml
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    # Run Phase 4
    result = process_segmented_audio(
        args.manifest,
        args.video,
        args.output,
        config
    )
    
    print(f"\n[OK] Phase 4 Complete!")
    print(f"Processed {len(result.get('segments', []))} segments")
    print(f"Output: {args.output}/metadata/segmentation_enhanced.json")
