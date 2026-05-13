"""
Phase 3: Smart Chunk Builder
Merges short segments, splits long ones, adds padding/overlap, creates chunk WAVs
"""

import os
import json
import wave
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np

try:
    import soundfile as sf
except ImportError:
    sf = None

class ChunkBuilder:
    """
    Smart chunk builder that optimizes segment boundaries for downstream processing
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize chunk builder with configuration
        
        Args:
            config: Configuration dictionary containing:
                - min_chunk_duration: Minimum chunk length in seconds (default: 1.0)
                - max_chunk_duration: Maximum chunk length in seconds (default: 40.0)
                - target_chunk_duration: Target chunk length (default: 30.0)
                - padding_ms: Padding to add before/after in milliseconds (default: 250)
                - overlap_ms: Overlap between chunks in milliseconds (default: 500)
                - merge_gap_threshold: Max gap to merge across in seconds (default: 0.5)
        """
        self.min_chunk_duration = config.get('min_chunk_duration', 1.0)
        self.max_chunk_duration = config.get('max_chunk_duration', 40.0)
        self.target_chunk_duration = config.get('target_chunk_duration', 30.0)
        self.padding_ms = config.get('padding_ms', 250)
        self.overlap_ms = config.get('overlap_ms', 500)
        self.merge_gap_threshold = config.get('merge_gap_threshold', 0.5)
        
        # Convert ms to seconds
        self.padding_sec = self.padding_ms / 1000.0
        self.overlap_sec = self.overlap_ms / 1000.0
        
    def build_chunks(
        self,
        segments: List[Dict[str, Any]],
        audio_path: str,
        output_dir: str
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Build optimized chunks from segments
        
        Args:
            segments: List of segment dictionaries from Phase 1/2
            audio_path: Path to normalized audio file
            output_dir: Directory to write chunk WAVs
            
        Returns:
            Tuple of (optimized_chunks, manifest_path)
        """
        # Step 1: Merge short segments and gaps
        merged = self._merge_segments(segments)
        
        # Step 2: Split long segments
        split_chunks = self._split_long_segments(merged)
        
        # Step 3: Add padding and overlap
        padded_chunks = self._add_padding_and_overlap(split_chunks)
        
        # Step 4: Load audio for chunking
        audio_data = None
        audio_frames = None
        channels = 1
        sample_width = 2
        if sf is not None:
            audio_data, sample_rate = sf.read(audio_path)
            audio_duration = len(audio_data) / sample_rate
        else:
            with wave.open(audio_path, 'rb') as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_count = wf.getnframes()
                audio_frames = wf.readframes(frame_count)
            audio_duration = frame_count / sample_rate if sample_rate else 0.0
        
        # Step 5: Create chunk WAVs
        chunks_dir = Path(output_dir) / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        
        final_chunks = []
        for idx, chunk in enumerate(padded_chunks):
            chunk_id = idx
            start_sec = max(0.0, chunk['start'])
            end_sec = min(audio_duration, chunk['end'])
            
            # Extract audio segment
            chunk_filename = f"chunk_{chunk_id:04d}.wav"
            chunk_path = chunks_dir / chunk_filename
            if sf is not None and audio_data is not None:
                start_sample = int(start_sec * sample_rate)
                end_sample = int(end_sec * sample_rate)
                chunk_audio = audio_data[start_sample:end_sample]
                sf.write(str(chunk_path), chunk_audio, sample_rate)
            else:
                start_frame = int(start_sec * sample_rate)
                end_frame = int(end_sec * sample_rate)
                bytes_per_frame = channels * sample_width
                chunk_bytes = (audio_frames or b"")[start_frame * bytes_per_frame:end_frame * bytes_per_frame]
                with wave.open(str(chunk_path), 'wb') as chunk_wav:
                    chunk_wav.setnchannels(channels)
                    chunk_wav.setsampwidth(sample_width)
                    chunk_wav.setframerate(sample_rate)
                    chunk_wav.writeframes(chunk_bytes)
            
            # Build chunk metadata
            chunk_meta = {
                'id': chunk_id,
                'start': start_sec,
                'end': end_sec,
                'duration': end_sec - start_sec,
                'chunk_path': f"chunks/{chunk_filename}",
                'vad_speech': chunk.get('vad_speech', True),
                'overlap': chunk.get('overlap', False),
                'speaker_changes': chunk.get('speaker_changes', []),
                'pyannote_labels': chunk.get('pyannote_labels', [])
            }
            final_chunks.append(chunk_meta)
        
        # Step 6: Write manifest
        manifest_path = Path(output_dir) / "segmentation.json"
        manifest = {
            'audio_file': str(Path(audio_path).name),
            'total_duration': audio_duration,
            'sample_rate': sample_rate,
            'num_chunks': len(final_chunks),
            # Keep both keys while the live pipeline and the phased engine
            # converge on a single canonical artifact shape.
            'segments': final_chunks,
            'chunks': final_chunks,
            'config': {
                'min_chunk_duration': self.min_chunk_duration,
                'max_chunk_duration': self.max_chunk_duration,
                'padding_ms': self.padding_ms,
                'overlap_ms': self.overlap_ms
            },
        }
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        return final_chunks, str(manifest_path)
    
    def _merge_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge short segments and small gaps
        """
        if not segments:
            return []
        
        merged = []
        current = segments[0].copy()
        
        for next_seg in segments[1:]:
            gap = next_seg['start'] - current['end']
            current_duration = current['end'] - current['start']
            next_duration = next_seg['end'] - next_seg['start']
            
            # Merge if:
            # - Gap is small AND
            # - Combined duration doesn't exceed max OR current is too short
            should_merge = (
                gap <= self.merge_gap_threshold and
                (current_duration + gap + next_duration <= self.max_chunk_duration or
                 current_duration < self.min_chunk_duration)
            )
            
            if should_merge:
                # Merge segments
                current['end'] = next_seg['end']
                current['vad_speech'] = current.get('vad_speech', True) or next_seg.get('vad_speech', True)
                current['overlap'] = current.get('overlap', False) or next_seg.get('overlap', False)
                
                # Merge speaker changes
                if 'speaker_changes' in next_seg:
                    if 'speaker_changes' not in current:
                        current['speaker_changes'] = []
                    current['speaker_changes'].extend(next_seg['speaker_changes'])
                
                # Merge pyannote labels
                if 'pyannote_labels' in next_seg:
                    if 'pyannote_labels' not in current:
                        current['pyannote_labels'] = []
                    current['pyannote_labels'].extend(next_seg['pyannote_labels'])
            else:
                # Save current and start new
                merged.append(current)
                current = next_seg.copy()
        
        # Don't forget last segment
        merged.append(current)
        
        return merged
    
    def _split_long_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Split segments that exceed max_chunk_duration
        """
        split_chunks = []
        
        for seg in segments:
            duration = seg['end'] - seg['start']
            
            if duration <= self.max_chunk_duration:
                split_chunks.append(seg)
            else:
                # Split into multiple chunks
                num_chunks = int(np.ceil(duration / self.target_chunk_duration))
                chunk_duration = duration / num_chunks
                
                for i in range(num_chunks):
                    chunk_start = seg['start'] + (i * chunk_duration)
                    chunk_end = min(seg['start'] + ((i + 1) * chunk_duration), seg['end'])
                    
                    chunk = {
                        'start': chunk_start,
                        'end': chunk_end,
                        'vad_speech': seg.get('vad_speech', True),
                        'overlap': seg.get('overlap', False),
                        'speaker_changes': [],  # Will be recalculated if needed
                        'pyannote_labels': []   # Will be recalculated if needed
                    }
                    split_chunks.append(chunk)
        
        return split_chunks
    
    def _add_padding_and_overlap(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add padding and overlap to chunk boundaries
        """
        padded = []
        
        for i, chunk in enumerate(chunks):
            # Add padding
            padded_start = chunk['start'] - self.padding_sec
            padded_end = chunk['end'] + self.padding_sec
            
            # Add overlap with next chunk
            if i < len(chunks) - 1:
                # Extend end to overlap with next chunk's start
                next_start = chunks[i + 1]['start']
                if padded_end < next_start:
                    padded_end = min(padded_end + self.overlap_sec, next_start)
            
            # Ensure non-negative start
            padded_start = max(0.0, padded_start)
            
            padded_chunk = chunk.copy()
            padded_chunk['start'] = padded_start
            padded_chunk['end'] = padded_end
            padded_chunk['original_start'] = chunk['start']
            padded_chunk['original_end'] = chunk['end']
            
            padded.append(padded_chunk)
        
        return padded


def run_phase3_chunk_builder(
    phase2_output: Dict[str, Any],
    audio_path: str,
    output_dir: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for Phase 3
    
    Args:
        phase2_output: Output from Phase 2 (pyannote segmentation)
        audio_path: Path to normalized audio WAV
        output_dir: Directory to write chunks and manifest
        config: Chunk builder configuration
        
    Returns:
        Dictionary containing:
            - chunks: List of chunk metadata
            - manifest_path: Path to segmentation.json
            - num_chunks: Total number of chunks created
    """
    builder = ChunkBuilder(config)
    
    # Get segments from Phase 2
    segments = phase2_output.get('segments', [])
    
    if not segments:
        raise ValueError("No segments provided from Phase 2")
    
    # Build chunks
    chunks, manifest_path = builder.build_chunks(segments, audio_path, output_dir)
    
    return {
        'chunks': chunks,
        'manifest_path': manifest_path,
        'num_chunks': len(chunks),
        'output_dir': output_dir
    }


if __name__ == '__main__':
    # Test harness
    print("Phase 3: Smart Chunk Builder - Test Mode")
    print("=" * 60)
    
    # Example usage
    test_config = {
        'min_chunk_duration': 1.0,
        'max_chunk_duration': 40.0,
        'target_chunk_duration': 30.0,
        'padding_ms': 250,
        'overlap_ms': 500,
        'merge_gap_threshold': 0.5
    }
    
    # Mock segments
    test_segments = [
        {'start': 0.0, 'end': 2.5, 'vad_speech': True},
        {'start': 3.0, 'end': 25.0, 'vad_speech': True},
        {'start': 26.0, 'end': 80.0, 'vad_speech': True},  # Will be split
    ]
    
    builder = ChunkBuilder(test_config)
    merged = builder._merge_segments(test_segments)
    split = builder._split_long_segments(merged)
    padded = builder._add_padding_and_overlap(split)
    
    print(f"Original segments: {len(test_segments)}")
    print(f"After merge: {len(merged)}")
    print(f"After split: {len(split)}")
    print(f"After padding: {len(padded)}")
    print("\nFinal chunks:")
    for i, chunk in enumerate(padded):
        print(f"  Chunk {i}: {chunk['start']:.2f}s -> {chunk['end']:.2f}s ({chunk['end']-chunk['start']:.2f}s)")
