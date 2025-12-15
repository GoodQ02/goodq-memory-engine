"""
GoodQ4All - Entity Extraction Pipeline Step
Extracts and resolves entities from multi-modal scene data
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
import re

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """Single extracted entity with source provenance"""
    entity_id: str
    entity_type: str  # person, object, location, event, concept
    name: str
    confidence: float
    source_modality: str  # vision, audio, text, metadata
    source_step: str  # face_embed, transcription, ocr, etc.
    properties: Dict[str, Any]
    timestamps: List[float]  # All timestamps where entity appears
    
    def to_dict(self):
        return asdict(self)


class EntityExtractor:
    """
    Extracts entities from processed scene data across all modalities
    
    Sources:
    - Vision: detected objects, faces, OCR text
    - Audio: speaker names, transcribed entities, locations mentioned
    - Text: NER on captions, OCR text, transcripts
    - Metadata: tags, classifications
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.family_names = self._load_family_names()
        self.entity_cache = {}
        
        # Stopwords to filter out (common words that aren't names)
        self.stopwords = {
            'okay', 'ok', 'yes', 'no', 'yeah', 'yep', 'nope',
            'thank', 'thanks', 'please', 'hey', 'hi', 'hello',
            'can', 'could', 'would', 'should', 'will', 'shall',
            'does', 'do', 'did', 'done',
            'what', 'where', 'when', 'why', 'who', 'how',
            'the', 'a', 'an', 'and', 'or', 'but',
            'you', 'i', 'me', 'my', 'your', 'he', 'she', 'it', 'they',
            'emotion', 'sentiment', 'man', 'woman', 'person',
            'hose', 'mathias',  # Add specific false positives as found
        }
        
    def _load_family_names(self) -> Set[str]:
        """Load known family member names from config"""
        # These should come from your config.yaml user section
        return {
            "grace", "gracie",
            "joe", "joseph", "joey",
            "mom", "mother", "donna",
            "dad", "father", "dominick", "dom",
            "jamie",
            "katy", "kate", "katie",
            "ryder",
            "suzie", "susan", "aunt suzie",
            # Add more from your family tree
        }
    
    def extract_from_scene(
        self,
        scene_data: Dict[str, Any],
        scene_id: str,
        video_id: str
    ) -> List[ExtractedEntity]:
        """
        Extract all entities from a single scene's processed data
        
        Args:
            scene_data: Complete scene processing results
            scene_id: Scene identifier
            video_id: Parent video identifier
            
        Returns:
            List of extracted entities with provenance
        """
        # Flatten nested data structures if present
        if 'keyframe' in scene_data and isinstance(scene_data['keyframe'], dict):
            keyframe = scene_data['keyframe']
            # Merge keyframe data to top level
            for key, value in keyframe.items():
                if key not in scene_data:
                    scene_data[key] = value
        
        if 'audio' in scene_data and isinstance(scene_data['audio'], dict):
            audio = scene_data['audio']
            # Merge audio data to top level
            for key, value in audio.items():
                if key not in scene_data:
                    scene_data[key] = value
        
        entities = []
        
        # 1. Extract from visual data
        entities.extend(self._extract_from_vision(scene_data, scene_id))
        
        # 2. Extract from audio/transcription
        entities.extend(self._extract_from_audio(scene_data, scene_id))
        
        # 3. Extract from OCR text
        entities.extend(self._extract_from_ocr(scene_data, scene_id))
        
        # 4. Extract from detected objects
        entities.extend(self._extract_from_objects(scene_data, scene_id))
        
        # 5. Extract from tags/classifications
        entities.extend(self._extract_from_tags(scene_data, scene_id))
        
        # 6. Extract from face detections
        entities.extend(self._extract_from_faces(scene_data, scene_id))
        
        # Debug logging
        logger.info(f"[ENTITY] Extracted {len(entities)} entities from scene {scene_id}")
        if entities:
            entity_names = [e.name for e in entities[:5]]  # First 5
            logger.info(f"[ENTITY] Sample entities: {entity_names}")
        else:
            # Log what data we had available
            has_transcript = bool(scene_data.get('transcript') or scene_data.get('transcription'))
            has_caption = bool(scene_data.get('caption'))
            has_ocr = bool(scene_data.get('ocr_text'))
            has_objects = bool(scene_data.get('objects') or scene_data.get('detected_objects'))
            logger.warning(f"[ENTITY] No entities found. Data available: transcript={has_transcript}, caption={has_caption}, ocr={has_ocr}, objects={has_objects}")
        
        return entities
    
    def _extract_from_vision(self, scene_data: Dict, scene_id: str) -> List[ExtractedEntity]:
        """Extract entities from visual analysis (captions, descriptions)"""
        entities = []
        
        # From BLIP/BLIP2 captions
        if "caption" in scene_data:
            caption = scene_data["caption"]
            # Simple keyword extraction (can be enhanced with NER)
            entities.extend(self._extract_names_from_text(
                caption, scene_id, "vision", "image_caption"
            ))
        
        return entities
    
    def _extract_from_audio(self, scene_data: Dict, scene_id: str) -> List[ExtractedEntity]:
        """Extract entities from audio transcription and speaker data"""
        entities = []
        
        # From Whisper transcription - check both 'transcript' (WSL2 output) and 'transcription' (legacy)
        transcript_text = scene_data.get("transcript") or scene_data.get("transcription", "")
        if isinstance(transcript_text, dict):
            transcript_text = transcript_text.get("text", "")
        
        if transcript_text and isinstance(transcript_text, str) and transcript_text.strip():
            entities.extend(self._extract_names_from_text(
                transcript_text, scene_id, "audio", "transcription"
            ))
        
        # From speaker diarization
        if "speakers" in scene_data:
            speakers = scene_data["speakers"]
            if isinstance(speakers, list):
                for idx, speaker_data in enumerate(speakers):
                    if isinstance(speaker_data, dict):
                        speaker_label = speaker_data.get("label", f"SPEAKER_{idx}")
                    else:
                        speaker_label = f"SPEAKER_{idx}"
                    
                    entities.append(ExtractedEntity(
                        entity_id=f"{scene_id}_speaker_{idx}",
                        entity_type="person",
                        name=speaker_label,
                        confidence=0.8,
                        source_modality="audio",
                        source_step="diarization",
                        properties={"speaker_index": idx, "diarization_data": speaker_data},
                        timestamps=[scene_data.get("start_time", 0)]
                    ))
        
        return entities
    
    def _extract_from_ocr(self, scene_data: Dict, scene_id: str) -> List[ExtractedEntity]:
        """Extract entities from OCR text"""
        entities = []
        
        if "ocr_text" in scene_data:
            ocr_text = scene_data["ocr_text"]
            if ocr_text and ocr_text.strip():
                # Extract names from OCR
                entities.extend(self._extract_names_from_text(
                    ocr_text, scene_id, "text", "ocr"
                ))
                
                # Extract dates/locations/events from OCR
                # (Can be enhanced with regex patterns for dates, locations)
                
        return entities
    
    def _extract_from_objects(self, scene_data: Dict, scene_id: str) -> List[ExtractedEntity]:
        """Extract object entities from YOLO/detection"""
        entities = []
        
        # Check both 'objects' (actual field name from step) and 'detected_objects' (legacy)
        objects = scene_data.get("objects") or scene_data.get("detected_objects", [])
        if objects:
            for obj in objects:
                if isinstance(obj, dict):
                    obj_name = obj.get("class", obj.get("label", "unknown"))
                    confidence = obj.get("confidence", 0.5)
                    
                    entities.append(ExtractedEntity(
                        entity_id=f"{scene_id}_obj_{obj_name}",
                        entity_type="object",
                        name=obj_name,
                        confidence=confidence,
                        source_modality="vision",
                        source_step="object_detect",
                        properties={"bbox": obj.get("bbox"), "detection": obj},
                        timestamps=[scene_data.get("start_time", 0)]
                    ))
        
        return entities
    
    def _extract_from_tags(self, scene_data: Dict, scene_id: str) -> List[ExtractedEntity]:
        """Extract concept entities from tags"""
        entities = []
        
        if "tags" in scene_data:
            tags = scene_data["tags"]
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, str):
                        entities.append(ExtractedEntity(
                            entity_id=f"{scene_id}_concept_{tag}",
                            entity_type="concept",
                            name=tag,
                            confidence=0.7,
                            source_modality="metadata",
                            source_step="tagger",
                            properties={},
                            timestamps=[scene_data.get("start_time", 0)]
                        ))
        
        return entities
    
    def _extract_from_faces(self, scene_data: Dict, scene_id: str) -> List[ExtractedEntity]:
        """Extract person entities from face detections"""
        entities = []
        
        if "faces" in scene_data:
            faces = scene_data.get("faces", [])
            for idx, face in enumerate(faces):
                # Face embeddings exist but no identity yet
                # This is where face recognition would plug in
                entities.append(ExtractedEntity(
                    entity_id=f"{scene_id}_face_{idx}",
                    entity_type="person",
                    name=f"FACE_{idx}",  # Placeholder until face recognition
                    confidence=0.6,
                    source_modality="vision",
                    source_step="face_embed",
                    properties={"face_index": idx, "embedding": face.get("embedding")},
                    timestamps=[scene_data.get("start_time", 0)]
                ))
        
        return entities
    
    def _extract_names_from_text(
        self,
        text: str,
        scene_id: str,
        modality: str,
        step: str
    ) -> List[ExtractedEntity]:
        """
        Extract person names from text using family name matching
        (Can be enhanced with spaCy NER or similar)
        """
        entities = []
        
        if not text:
            return entities
        
        text_lower = text.lower()
        
        # Check for family names
        for name in self.family_names:
            if name in text_lower:
                # Skip if it's a stopword
                if name.lower() in self.stopwords:
                    continue
                    
                entities.append(ExtractedEntity(
                    entity_id=f"{scene_id}_{modality}_{name}",
                    entity_type="person",
                    name=name.title(),
                    confidence=0.9,  # High confidence for family names
                    source_modality=modality,
                    source_step=step,
                    properties={"matched_text": text[:100]},  # Sample
                    timestamps=[]
                ))
        
        return entities
    
    def merge_entities(self, entities: List[ExtractedEntity]) -> List[Dict[str, Any]]:
        """
        Merge duplicate entities across modalities
        
        Returns:
            List of merged entity dictionaries with combined provenance
        """
        # Group by normalized name and type
        groups = {}
        
        for entity in entities:
            key = (self._normalize_name(entity.name), entity.entity_type)
            if key not in groups:
                groups[key] = []
            groups[key].append(entity)
        
        # Merge each group
        merged = []
        for (name, etype), group in groups.items():
            # Combine all sources
            sources = [e.source_modality for e in group]
            steps = [e.source_step for e in group]
            confidences = [e.confidence for e in group]
            all_timestamps = []
            for e in group:
                all_timestamps.extend(e.timestamps)
            
            # Aggregate properties
            properties = {}
            for e in group:
                properties.update(e.properties)
            
            merged_entity = {
                "entity_id": group[0].entity_id,
                "entity_type": etype,
                "name": group[0].name,  # Use first occurrence name
                "confidence": max(confidences),  # Highest confidence
                "occurrences": len(group),
                "source_modalities": list(set(sources)),
                "source_steps": list(set(steps)),
                "properties": properties,
                "timestamps": sorted(list(set(all_timestamps)))
            }
            
            merged.append(merged_entity)
        
        return merged
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for matching"""
        return re.sub(r'\s+', ' ', name.lower().strip())


def extract_entities_from_scene(
    scene_data: Dict[str, Any],
    scene_id: str,
    video_id: str,
    config: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Main entry point for entity extraction step
    
    Returns:
        Dictionary with extracted and merged entities
    """
    extractor = EntityExtractor(config)
    
    # Extract all entities
    raw_entities = extractor.extract_from_scene(scene_data, scene_id, video_id)
    
    # Merge duplicates
    merged_entities = extractor.merge_entities(raw_entities)
    
    return {
        "entity_count": len(merged_entities),
        "entities": merged_entities,
        "raw_entity_count": len(raw_entities)
    }
