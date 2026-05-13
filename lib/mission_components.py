#!/usr/bin/env python3
"""
GoodQ Mission Components - Branded Component Names for Each Pipeline Step
Maps pipeline steps to Q Branch approved component designations
"""
from typing import Dict

# Mission component designations (Q Branch approved)
MISSION_COMPONENTS: Dict[str, str] = {
    # Video Operations
    'video_scene_detect': 'Recon Scanner',
    'video_ingest': 'Asset Acquisition',
    'image_caption': 'Visual Intel',
    'image_ocr': 'Document Decoder',
    'image_embed_clip': 'Visual Signature',
    'image_embed_dino': 'Visual Biometrics',
    'image_exif': 'Metadata Forensics',
    'object_detect': 'Target Identification',
    'object_track': 'Surveillance Tracking',
    'object_track_yolo': 'Rapid Target Track',
    'face_embed': 'Facial Recognition',
    
    # Audio Operations
    'audio_metadata': 'Audio Intel',
    'audio_diarize': 'Voice Separation',
    'audio_transcribe': 'Comms Decrypt',
    'audio_speaker_merge': 'Identity Fusion',
    'audio_music_events': 'Acoustic Analysis',
    'audio_time_hints': 'Temporal Markers',
    'audio_emotion': 'Emotional Profiling',
    'audio_embed_clap': 'Audio Signature',
    
    # Text & NLP Operations
    'text_embed': 'Linguistic Analysis',
    'sentiment': 'Sentiment Intel',
    'emotion_classify': 'Emotion Detection',
    'tagger': 'Entity Cataloging',
    'pdf_text': 'Document Extraction',
    
    # Knowledge & Memory
    'graph_builder': 'Network Mapping',
    'discover_sources': 'Asset Discovery',
    'overview': 'Mission Briefing',
    
    # System Operations
    'system_metrics': 'System Diagnostics',
    'home_assistant_status': 'Safe House Status',
    
    # Communication
    'llm_chat': 'Q Branch Comms',
    'tts': 'Voice Synthesis',
}

# Mission phase descriptions
PHASE_DESCRIPTIONS: Dict[str, str] = {
    'init': 'Mission initialization',
    'discover': 'Asset discovery and reconnaissance',
    'video_analysis': 'Visual intelligence gathering',
    'audio_analysis': 'Audio intelligence analysis',
    'text_analysis': 'Textual intelligence processing',
    'embedding': 'Signature generation and indexing',
    'knowledge_graph': 'Intelligence network construction',
    'finalize': 'Mission debrief and secure storage',
}

# Progress bar descriptions (Q Branch style)
PROGRESS_DESCRIPTIONS: Dict[str, str] = {
    'scenes': 'Analyzing surveillance footage',
    'frames': 'Extracting visual intel',
    'audio_segments': 'Processing audio intercepts',
    'transcripts': 'Decrypting communications',
    'embeddings': 'Generating biometric signatures',
    'entities': 'Cataloging identified entities',
    'relationships': 'Mapping intelligence networks',
    'files': 'Processing classified assets',
}

# Status messages (Mission-aligned)
STATUS_MESSAGES: Dict[str, str] = {
    'loading_model': 'Deploying Q Branch technology',
    'model_loaded': 'Technology online and operational',
    'processing_start': 'Operation commenced',
    'processing_complete': 'Operation successful',
    'cache_hit': 'Intel retrieved from secure archive',
    'cache_miss': 'Fresh intelligence required',
    'gpu_enabled': 'GPU acceleration enabled',
    'gpu_disabled': 'CPU fallback mode active',
    'error': 'Operation compromised',
    'warning': 'Proceed with caution',
    'success': 'Mission objective achieved',
}


def get_component_name(step_name: str) -> str:
    """
    Get Q Branch approved component name for pipeline step
    
    Args:
        step_name: Pipeline step identifier
        
    Returns:
        Mission-branded component name
    """
    return MISSION_COMPONENTS.get(step_name, step_name.replace('_', ' ').title())


def get_progress_description(operation: str, count: int) -> str:
    """
    Get mission-styled progress description
    
    Args:
        operation: Operation type (scenes, frames, etc.)
        count: Number of items
        
    Returns:
        Formatted progress description
    """
    base_desc = PROGRESS_DESCRIPTIONS.get(operation, f'Processing {operation}')
    return f"{base_desc} ({count} items)"


def format_duration(seconds: float) -> str:
    """Format duration in mission time style"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def format_file_size(bytes_size: int) -> str:
    """Format file size in intelligence report style"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}PB"


# Mission status emoji/symbol mapping for different contexts
MISSION_SYMBOLS = {
    'start': '[MISSION START]',
    'progress': '[IN PROGRESS]',
    'success': '[SUCCESS]',
    'warning': '[CAUTION]',
    'error': '[FAILED]',
    'complete': '[COMPLETE]',
    'intel': '[INTEL]',
    'target': '[TARGET]',
    'agent': '007',
    'gadget': '[Q-TECH]',
    'classified': '[CLASSIFIED]',
}
