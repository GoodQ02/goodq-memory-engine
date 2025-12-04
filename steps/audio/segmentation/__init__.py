"""
GoodQ4All Phased Segmentation Engine
Audio/Video intelligent chunking with VAD, diarization hints, and scene alignment
"""

from .phase1_vad import run_vad_segmentation
from .phase2_pyannote import run_pyannote_segmentation, merge_vad_and_pyannote
from .phase3_chunk_builder import build_smart_chunks
from .phase4_audio_processor import process_segmented_audio, Phase4AudioProcessor

__all__ = [
    'run_vad_segmentation',
    'run_pyannote_segmentation',
    'merge_vad_and_pyannote',
    'build_smart_chunks',
    'process_segmented_audio',
    'Phase4AudioProcessor',
]
