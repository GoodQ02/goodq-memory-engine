"""
Data loaders for GoodQ4All API.
Handles loading temporal indexes, scene manifests, and other processed data.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DataLoader:
    """Centralized data loading for API endpoints."""
    
    def __init__(self, data_root: str = "L:/_DATA/GoodQ_Data"):
        """
        Initialize data loader.
        
        Args:
            data_root: Root directory for processed data
        """
        self.data_root = Path(data_root)
        self.processing_dir = self.data_root / "processing"
        self.completed_dir = self.data_root / "completed"
    
    def load_temporal_index(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Load temporal index for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Temporal index data or None if not found
        """
        # Try processing directory first
        path = self.processing_dir / video_id / "temporal_index.json"
        
        if not path.exists():
            # Try completed directory
            path = self.completed_dir / video_id / "temporal_index.json"
        
        if not path.exists():
            logger.warning(f"Temporal index not found for video: {video_id}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load temporal index: {e}")
            return None
    
    def load_scene_manifest(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Load scene manifest for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Scene manifest data or None if not found
        """
        path = self.processing_dir / video_id / "video" / "scene_manifest.json"
        
        if not path.exists():
            path = self.completed_dir / video_id / "video" / "scene_manifest.json"
        
        if not path.exists():
            logger.warning(f"Scene manifest not found for video: {video_id}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load scene manifest: {e}")
            return None
    
    def load_segmentation(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Load audio segmentation for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Segmentation data or None if not found
        """
        path = self.processing_dir / video_id / "audio" / "segmentation.json"
        
        if not path.exists():
            path = self.completed_dir / video_id / "audio" / "segmentation.json"
        
        if not path.exists():
            logger.warning(f"Segmentation not found for video: {video_id}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load segmentation: {e}")
            return None
    
    def get_frame_path(self, video_id: str, scene_id: int, frame_index: int = 0) -> Optional[Path]:
        """
        Get path to a specific frame.
        
        Args:
            video_id: Video identifier
            scene_id: Scene identifier
            frame_index: Frame index within scene (default: 0 for representative frame)
            
        Returns:
            Path to frame file or None if not found
        """
        # Load temporal index to get frame paths
        temporal_index = self.load_temporal_index(video_id)
        
        if not temporal_index:
            return None
        
        # Find the scene segment
        for segment in temporal_index.get('segments', []):
            if segment.get('scene_id') == scene_id:
                frame_paths = segment.get('frame_paths', [])
                
                if frame_index < len(frame_paths):
                    frame_path = Path(frame_paths[frame_index])
                    
                    # Convert to absolute path if relative
                    if not frame_path.is_absolute():
                        frame_path = self.processing_dir / video_id / "video" / "frames" / frame_path.name
                    
                    if frame_path.exists():
                        return frame_path
        
        return None
    
    def get_audio_chunk_path(self, video_id: str, chunk_id: int) -> Optional[Path]:
        """
        Get path to an audio chunk.
        
        Args:
            video_id: Video identifier
            chunk_id: Chunk identifier
            
        Returns:
            Path to audio chunk or None if not found
        """
        chunk_path = self.processing_dir / video_id / "audio" / "chunks" / f"segment_{chunk_id}.wav"
        
        if not chunk_path.exists():
            chunk_path = self.completed_dir / video_id / "audio" / "chunks" / f"segment_{chunk_id}.wav"
        
        if chunk_path.exists():
            return chunk_path
        
        return None
    
    def list_processed_videos(self) -> List[str]:
        """
        List all processed videos.
        
        Returns:
            List of video IDs
        """
        video_ids = []
        
        # Scan processing directory
        if self.processing_dir.exists():
            for item in self.processing_dir.iterdir():
                if item.is_dir():
                    # Check if temporal index exists
                    if (item / "temporal_index.json").exists():
                        video_ids.append(item.name)
        
        # Scan completed directory
        if self.completed_dir.exists():
            for item in self.completed_dir.iterdir():
                if item.is_dir() and item.name not in video_ids:
                    if (item / "temporal_index.json").exists():
                        video_ids.append(item.name)
        
        return sorted(video_ids)
    
    def get_video_metadata(self, video_id: str) -> Dict[str, Any]:
        """
        Get basic metadata for a video.
        
        Args:
            video_id: Video identifier
            
        Returns:
            Video metadata dict
        """
        temporal_index = self.load_temporal_index(video_id)
        
        if not temporal_index:
            return {'video_id': video_id, 'error': 'not_found'}
        
        metadata = {
            'video_id': video_id,
            'duration': temporal_index.get('duration', 0.0),
            'total_scenes': len(temporal_index.get('segments', [])),
            'total_segments': len(temporal_index.get('segments', [])),
            'phase6_complete': temporal_index.get('phase6_complete', False),
            'phase6_harmonized': temporal_index.get('phase6_harmonized', False)
        }
        
        return metadata
