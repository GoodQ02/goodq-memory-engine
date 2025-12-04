"""
GoodQ4All Phased Segmentation Engine
Multi-stage GPU-safe inference pipeline for video/audio processing
"""

__version__ = '1.0.0'
__author__ = 'GoodQ4All'

# Import orchestrator (master controller)
from .orchestrator import (
    PhasedSegmentationEngine,
    create_default_config
)

# Import individual phase modules
from .phase0_normalization import (
    normalize_media,
    extract_metadata
)

from .phase1_vad_segmentation import (
    segment_with_webrtc_vad
)

from .phase2_pyannote_segmentation import (
    segment_with_pyannote,
    enhance_segments_with_pyannote
)

from .phase3_smart_chunking import (
    build_smart_chunks,
    save_chunk_wavs
)

from .phase4_audio_processing import (
    process_chunks_with_wsl2,
    AudioProcessingConfig
)

from .phase5_video_scene_integration import (
    process_video_chunks_with_scenes,
    detect_scenes_for_chunk,
    align_scenes_with_audio_segments,
    upgrade_analysis_for_legacy_scene_detect
)

from .phase6_integration import (
    merge_all_segment_data,
    generate_segmentation_manifest,
    validate_manifest
)

__all__ = [
    # Main orchestrator
    'PhasedSegmentationEngine',
    'create_default_config',
    
    # Phase 0
    'normalize_media',
    'extract_metadata',
    
    # Phase 1
    'segment_with_webrtc_vad',
    
    # Phase 2
    'segment_with_pyannote',
    'enhance_segments_with_pyannote',
    
    # Phase 3
    'build_smart_chunks',
    'save_chunk_wavs',
    
    # Phase 4
    'process_chunks_with_wsl2',
    'AudioProcessingConfig',
    
    # Phase 5
    'process_video_chunks_with_scenes',
    'detect_scenes_for_chunk',
    'align_scenes_with_audio_segments',
    'upgrade_analysis_for_legacy_scene_detect',
    
    # Phase 6
    'merge_all_segment_data',
    'generate_segmentation_manifest',
    'validate_manifest',
]
