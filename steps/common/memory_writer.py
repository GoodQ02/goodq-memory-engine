#!/usr/bin/env python3
"""
Centralized Memory Database Writer
DRAFT - awaiting approval for integration
"""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class MemoryWriter:
    """
    Unified interface for saving all analysis results to memory database.
    Handles all data types and ensures consistent storage patterns.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Try to find memory DB in standard locations
            possible_paths = [
                Path("L:/GoodQ_Data/memory.db"),
                Path("L:/_DATA/GoodQ_Data/data/memory_db/memory.db"),
                Path("L:/zenml_project/data/memory.db"),
            ]
            for p in possible_paths:
                if p.exists():
                    db_path = str(p)
                    break
        
        if db_path is None:
            raise ValueError("Could not find memory database")
        
        self.db_path = db_path
        logger.info(f"MemoryWriter initialized with DB: {db_path}")
    
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def save_scene(self, video_hash: str, scene_id: str, start_time: float, 
                   end_time: float, metadata: Dict = None):
        """Save or update scene record"""
        conn = self._get_connection()
        c = conn.cursor()
        
        try:
            meta_json = json.dumps(metadata or {})
            created_at = datetime.now().isoformat()
            
            c.execute('''
                INSERT OR REPLACE INTO scenes 
                (id, video_hash, start, end, meta, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (scene_id, video_hash, start_time, end_time, meta_json, created_at))
            
            conn.commit()
            logger.debug(f"Saved scene: {scene_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save scene {scene_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def update_scene_metadata(self, scene_id: str, updates: Dict):
        """Update scene metadata (merge with existing)"""
        conn = self._get_connection()
        c = conn.cursor()
        
        try:
            # Get existing metadata
            row = c.execute('SELECT meta FROM scenes WHERE id = ?', (scene_id,)).fetchone()
            if not row:
                logger.warning(f"Scene {scene_id} not found")
                return False
            
            # Merge metadata
            existing_meta = json.loads(row['meta']) if row['meta'] else {}
            existing_meta.update(updates)
            
            # Save back
            c.execute('''
                UPDATE scenes SET meta = ? WHERE id = ?
            ''', (json.dumps(existing_meta), scene_id))
            
            conn.commit()
            logger.debug(f"Updated scene metadata: {scene_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update scene metadata: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def save_caption(self, scene_id: str, caption: str, confidence: float = None):
        """Save image caption"""
        return self.update_scene_metadata(scene_id, {
            'caption': caption,
            'caption_confidence': confidence
        })
    
    def save_objects(self, scene_id: str, objects: List[Dict]):
        """Save detected objects"""
        return self.update_scene_metadata(scene_id, {
            'objects': objects,
            'object_count': len(objects)
        })
    
    def save_ocr_text(self, scene_id: str, text: str, regions: List[Dict] = None):
        """Save OCR results"""
        return self.update_scene_metadata(scene_id, {
            'ocr_text': text,
            'ocr_regions': regions or []
        })
    
    def save_transcription(self, scene_id: str, transcription: Dict):
        """Save audio transcription"""
        return self.update_scene_metadata(scene_id, {
            'transcription': transcription.get('text', ''),
            'transcription_segments': transcription.get('segments', []),
            'transcription_confidence': transcription.get('confidence'),
            'language': transcription.get('language')
        })
    
    def save_sentiment(self, scene_id: str, sentiment: Dict):
        """Save sentiment analysis"""
        return self.update_scene_metadata(scene_id, {
            'sentiment_label': sentiment.get('label', 'neutral'),
            'sentiment_score': sentiment.get('score', 0.0),
            'sentiment_details': sentiment
        })
    
    def save_emotions(self, scene_id: str, emotions: Dict):
        """Save emotion classification"""
        return self.update_scene_metadata(scene_id, {
            'emotions': emotions,
            'dominant_emotion': max(emotions.items(), key=lambda x: x[1])[0] if emotions else None
        })
    
    def save_tags(self, scene_id: str, tags: List[str], source: str = 'auto'):
        """Save tags/labels"""
        return self.update_scene_metadata(scene_id, {
            f'tags_{source}': tags
        })
    
    def save_embedding(self, embedding_hash: str, embedding_vector: List[float],
                      source_path: str, modality: str, scene_id: str = None,
                      metadata: Dict = None):
        """Save embedding to embeddings table"""
        conn = self._get_connection()
        c = conn.cursor()
        
        try:
            meta = metadata or {}
            created_at = datetime.now().isoformat()
            
            # Note: Actual vector storage might use FAISS
            # This is just metadata
            c.execute('''
                INSERT OR REPLACE INTO embeddings 
                (hash, faiss_id, source_path, modality, scene_id, created_at,
                 sentiment_label, sentiment_score, emotions_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                embedding_hash,
                meta.get('faiss_id'),
                source_path,
                modality,
                scene_id,
                created_at,
                meta.get('sentiment_label'),
                meta.get('sentiment_score'),
                json.dumps(meta.get('emotions', {}))
            ))
            
            conn.commit()
            logger.debug(f"Saved embedding: {embedding_hash}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save embedding: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def save_analysis_batch(self, scene_id: str, analysis_results: Dict):
        """
        Save multiple analysis results at once.
        analysis_results should be dict with keys like 'caption', 'objects', etc.
        """
        updates = {}
        
        # Map analysis types to their storage format
        for key, value in analysis_results.items():
            if value is None:
                continue
            
            if key == 'caption':
                updates['caption'] = value
            elif key == 'objects':
                updates['objects'] = value
                updates['object_count'] = len(value) if isinstance(value, list) else 0
            elif key == 'ocr':
                updates['ocr_text'] = value.get('text', '') if isinstance(value, dict) else value
            elif key == 'transcription':
                if isinstance(value, dict):
                    updates['transcription'] = value.get('text', '')
                    updates['transcription_segments'] = value.get('segments', [])
            elif key == 'sentiment':
                if isinstance(value, dict):
                    updates['sentiment_label'] = value.get('label', 'neutral')
                    updates['sentiment_score'] = value.get('score', 0.0)
            elif key == 'emotions':
                updates['emotions'] = value
            elif key == 'tags':
                updates['tags_auto'] = value
            else:
                # Generic storage
                updates[key] = value
        
        return self.update_scene_metadata(scene_id, updates)
    
    def get_scene(self, scene_id: str) -> Optional[Dict]:
        """Retrieve scene with all metadata"""
        conn = self._get_connection()
        c = conn.cursor()
        
        try:
            row = c.execute('''
                SELECT * FROM scenes WHERE id = ?
            ''', (scene_id,)).fetchone()
            
            if not row:
                return None
            
            result = dict(row)
            # Parse JSON metadata
            if result.get('meta'):
                result['meta'] = json.loads(result['meta'])
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get scene: {e}")
            return None
        finally:
            conn.close()
    
    def get_scenes_for_video(self, video_hash: str) -> List[Dict]:
        """Get all scenes for a video"""
        conn = self._get_connection()
        c = conn.cursor()
        
        try:
            rows = c.execute('''
                SELECT * FROM scenes WHERE video_hash = ? ORDER BY start
            ''', (video_hash,)).fetchall()
            
            scenes = []
            for row in rows:
                scene = dict(row)
                if scene.get('meta'):
                    scene['meta'] = json.loads(scene['meta'])
                scenes.append(scene)
            
            return scenes
            
        except Exception as e:
            logger.error(f"Failed to get scenes for video: {e}")
            return []
        finally:
            conn.close()


# Convenience functions for use in steps
_writer_instance = None

def get_memory_writer() -> MemoryWriter:
    """Get singleton memory writer instance"""
    global _writer_instance
    if _writer_instance is None:
        _writer_instance = MemoryWriter()
    return _writer_instance


def save_step_results(scene_id: str, step_name: str, results: Any):
    """
    Convenience function to save step results.
    Automatically maps common step outputs to appropriate storage.
    """
    writer = get_memory_writer()
    
    if results is None:
        logger.warning(f"Step {step_name} returned None for scene {scene_id}")
        return False
    
    # Handle different result types
    if isinstance(results, dict):
        return writer.save_analysis_batch(scene_id, results)
    elif isinstance(results, str):
        # Assume it's caption or transcription
        if step_name in ['image_caption', 'caption']:
            return writer.save_caption(scene_id, results)
        elif step_name in ['audio_transcribe', 'transcription']:
            return writer.save_transcription(scene_id, {'text': results})
    elif isinstance(results, list):
        # Assume it's objects or tags
        if step_name in ['object_detect', 'objects']:
            return writer.save_objects(scene_id, results)
        elif step_name in ['tagger', 'tags']:
            return writer.save_tags(scene_id, results)
    
    # Generic storage
    return writer.update_scene_metadata(scene_id, {step_name: results})


if __name__ == "__main__":
    # Test the writer
    writer = MemoryWriter()
    
    # Test scene creation
    writer.save_scene(
        video_hash="test123",
        scene_id="scene_0000",
        start_time=0.0,
        end_time=10.0,
        metadata={'test': True}
    )
    
    # Test updating with analysis results
    writer.save_caption("scene_0000", "A person standing in a room")
    writer.save_objects("scene_0000", [
        {'label': 'person', 'confidence': 0.95},
        {'label': 'chair', 'confidence': 0.87}
    ])
    
    # Retrieve and verify
    scene = writer.get_scene("scene_0000")
    print(json.dumps(scene, indent=2))
