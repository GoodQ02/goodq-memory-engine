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


_SCENE_PLACE_LABELS = {
    "apartment": "Apartment",
    "kitchen": "Kitchen",
    "living room": "Living Room",
    "bedroom": "Bedroom",
    "office": "Office",
    "cafe": "Cafe",
    "coffee shop": "Cafe",
    "restaurant": "Restaurant",
    "diner": "Diner",
    "street": "Street",
    "sidewalk": "Street",
    "intersection": "Street",
}

_OBJECT_PLACE_SIGNATURES = (
    ({"refrigerator"}, "Kitchen", 0.78),
    ({"oven"}, "Kitchen", 0.78),
    ({"sink"}, "Kitchen", 0.78),
    ({"traffic light"}, "Street", 0.76),
    ({"couch", "chair"}, "Living Room", 0.68),
    ({"dining table", "chair"}, "Dining Room", 0.66),
)


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
        
        # Stopwords to filter out (common words that aren't names/entities)
        self.stopwords = {
            "i", "i'm", "you", "you're", "we", "we're", "they", "it's", "that's",
            "what", "well", "yeah", "okay", "why", "how", "look", "but", "and", "the",
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
        self._contraction_parts = {"'m", "'re", "'s", "'ll", "'ve", "'d", "n't"}
        self._typed_entity_type_map = {
            "PER": "person",
            "PERSON": "person",
            "LOC": "location",
            "LOCATION": "location",
            "GPE": "location",
            "FAC": "location",
            "ORG": "organization",
            "ORGANIZATION": "organization",
            "EVENT": "event",
            "PRODUCT": "object",
            "OBJECT": "object",
            "WORK_OF_ART": "concept",
            "LANGUAGE": "concept",
            "LAW": "concept",
            "MISC": "concept",
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

        # 0. Prefer structured semantic entities already produced by upstream steps.
        entities.extend(self._extract_from_structured_entities(scene_data, scene_id, "metadata", "scene_payload"))
        if isinstance(scene_data.get("audio"), dict):
            entities.extend(self._extract_from_structured_entities(scene_data["audio"], scene_id, "audio", "tagger"))
        if isinstance(scene_data.get("keyframe"), dict):
            entities.extend(self._extract_from_structured_entities(scene_data["keyframe"], scene_id, "vision", "tagger"))
        
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
            entities.extend(self._extract_place_entities_from_text(
                caption, scene_id, "vision", "image_caption", confidence=0.8
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
        
        # Preserve real speaker identities when available, but avoid placeholder
        # diarization labels because speaker_ids already carry that structure.
        if "speakers" in scene_data:
            speakers = scene_data["speakers"]
            if isinstance(speakers, list):
                for idx, speaker_data in enumerate(speakers):
                    speaker_name = None
                    if isinstance(speaker_data, dict):
                        speaker_name = (
                            speaker_data.get("name")
                            or speaker_data.get("identity")
                            or speaker_data.get("person")
                        )
                    if not self._is_meaningful_person_name(speaker_name):
                        continue

                    entities.append(ExtractedEntity(
                        entity_id=f"{scene_id}_speaker_{idx}",
                        entity_type="person",
                        name=str(speaker_name).strip(),
                        confidence=0.85,
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
                    if not self._is_valid_entity_candidate(obj_name):
                        continue
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
            entities.extend(self._infer_locations_from_objects(objects, scene_id, scene_data))
        
        return entities
    
    def _extract_from_tags(self, scene_data: Dict, scene_id: str) -> List[ExtractedEntity]:
        """Extract concept entities from tags"""
        entities = []
        object_labels = self._object_label_set(scene_data)
        timestamps = [scene_data.get("start_time", 0)]

        tag_details = scene_data.get("tag_details")
        if isinstance(tag_details, list):
            for idx, detail in enumerate(tag_details):
                if not isinstance(detail, dict):
                    continue
                tag_name = detail.get("label") or detail.get("name")
                if not self._is_valid_entity_candidate(tag_name):
                    continue
                normalized_name = self._normalize_name(str(tag_name))
                detail_sources = {
                    str(source).strip().lower()
                    for source in detail.get("sources", [])
                    if isinstance(source, str) and source.strip()
                }
                if normalized_name in object_labels:
                    continue
                if detail_sources and detail_sources.issubset({"object"}):
                    continue

                entity_type = self._normalize_typed_entity_type(detail.get("type")) or "concept"
                if entity_type == "concept" and self._is_scene_place_tag(tag_name, detail_sources):
                    entity_type = "location"
                entities.append(ExtractedEntity(
                    entity_id=f"{scene_id}_concept_{idx}",
                    entity_type=entity_type,
                    name=str(tag_name).strip(),
                    confidence=self._score_to_confidence(detail.get("score"), default=0.72),
                    source_modality="metadata",
                    source_step="tagger",
                    properties={"detail_sources": sorted(detail_sources), "detail": detail},
                    timestamps=timestamps,
                ))
            return entities

        tags = scene_data.get("tags")
        if isinstance(tags, list):
            for idx, tag in enumerate(tags):
                if not isinstance(tag, str) or not self._is_valid_entity_candidate(tag):
                    continue
                normalized_tag = self._normalize_name(tag)
                if normalized_tag in object_labels:
                    continue
                entity_type = "location" if self._is_scene_place_tag(tag, set()) else "concept"
                entities.append(ExtractedEntity(
                    entity_id=f"{scene_id}_concept_{idx}",
                    entity_type=entity_type,
                    name=tag.strip(),
                    confidence=0.7,
                    source_modality="metadata",
                    source_step="tagger",
                    properties={},
                    timestamps=timestamps,
                ))
        
        return entities
    
    def _extract_from_faces(self, scene_data: Dict, scene_id: str) -> List[ExtractedEntity]:
        """Extract person entities from face detections"""
        entities = []
        
        if "faces" in scene_data:
            faces = scene_data.get("faces", [])
            for idx, face in enumerate(faces):
                face_name = None
                if isinstance(face, dict):
                    face_name = face.get("name") or face.get("identity") or face.get("label")
                if not self._is_meaningful_person_name(face_name):
                    continue

                entities.append(ExtractedEntity(
                    entity_id=f"{scene_id}_face_{idx}",
                    entity_type="person",
                    name=str(face_name).strip(),
                    confidence=0.8,
                    source_modality="vision",
                    source_step="face_embed",
                    properties={"face_index": idx, "face": face},
                    timestamps=[scene_data.get("start_time", 0)]
                ))
        
        return entities

    def _extract_from_structured_entities(
        self,
        payload: Dict[str, Any],
        scene_id: str,
        modality: str,
        default_step: str,
    ) -> List[ExtractedEntity]:
        entities: List[ExtractedEntity] = []
        if not isinstance(payload, dict):
            return entities

        timestamps = [payload.get("start_time", 0)]

        ner_entities = payload.get("ner_entities")
        if isinstance(ner_entities, list):
            for idx, entity in enumerate(ner_entities):
                if not isinstance(entity, dict):
                    continue
                name = entity.get("name") or entity.get("label")
                entity_type = self._normalize_typed_entity_type(entity.get("type"))
                if entity_type is None or not self._is_valid_entity_candidate(name):
                    continue
                if entity_type == "person" and not self._is_meaningful_person_name(name):
                    continue
                entities.append(ExtractedEntity(
                    entity_id=f"{scene_id}_{modality}_ner_{idx}",
                    entity_type=entity_type,
                    name=str(name).strip(),
                    confidence=0.92,
                    source_modality=modality,
                    source_step=str(entity.get("source_step") or default_step),
                    properties={"ner_entity": entity},
                    timestamps=timestamps,
                ))

        entity_details = payload.get("entity_details")
        if isinstance(entity_details, list):
            for idx, detail in enumerate(entity_details):
                if not isinstance(detail, dict):
                    continue
                name = detail.get("label") or detail.get("name")
                if not self._is_valid_entity_candidate(name):
                    continue

                detail_sources = {
                    str(source).strip().lower()
                    for source in detail.get("sources", [])
                    if isinstance(source, str) and source.strip()
                }
                entity_type = self._normalize_typed_entity_type(detail.get("type"))
                if entity_type is None and "ner" not in detail_sources:
                    continue
                entity_type = entity_type or "concept"
                if entity_type == "person" and not self._is_meaningful_person_name(name):
                    continue

                entities.append(ExtractedEntity(
                    entity_id=f"{scene_id}_{modality}_detail_{idx}",
                    entity_type=entity_type,
                    name=str(name).strip(),
                    confidence=self._score_to_confidence(detail.get("score"), default=0.82),
                    source_modality=modality,
                    source_step=default_step,
                    properties={"detail_sources": sorted(detail_sources), "detail": detail},
                    timestamps=timestamps,
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
                if not self._is_valid_entity_candidate(name):
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

    def _extract_place_entities_from_text(
        self,
        text: str,
        scene_id: str,
        modality: str,
        step: str,
        *,
        confidence: float,
    ) -> List[ExtractedEntity]:
        entities: List[ExtractedEntity] = []
        if not isinstance(text, str) or not text.strip():
            return entities

        lowered = text.lower()
        for phrase, canonical in _SCENE_PLACE_LABELS.items():
            if not re.search(rf"\b{re.escape(phrase)}\b", lowered):
                continue
            entities.append(ExtractedEntity(
                entity_id=f"{scene_id}_{modality}_place_{self._normalize_name(canonical)}",
                entity_type="location",
                name=canonical,
                confidence=confidence,
                source_modality=modality,
                source_step=step,
                properties={"matched_phrase": phrase, "matched_text": text[:120]},
                timestamps=[0.0],
            ))

        return entities

    def _infer_locations_from_objects(
        self,
        objects: List[Dict[str, Any]],
        scene_id: str,
        scene_data: Dict[str, Any],
    ) -> List[ExtractedEntity]:
        entities: List[ExtractedEntity] = []
        object_labels = {
            self._normalize_name(str(obj.get("class") or obj.get("label") or ""))
            for obj in objects
            if isinstance(obj, dict)
        }
        object_labels.discard("")
        if not object_labels:
            return entities

        for required_labels, location_name, confidence in _OBJECT_PLACE_SIGNATURES:
            normalized_required = {self._normalize_name(label) for label in required_labels}
            if not normalized_required.issubset(object_labels):
                continue
            entities.append(ExtractedEntity(
                entity_id=f"{scene_id}_vision_place_{self._normalize_name(location_name)}",
                entity_type="location",
                name=location_name,
                confidence=confidence,
                source_modality="vision",
                source_step="object_place_inference",
                properties={"matched_objects": sorted(normalized_required)},
                timestamps=[scene_data.get("start_time", 0)],
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

    def _normalize_typed_entity_type(self, raw_type: Any) -> Optional[str]:
        if not isinstance(raw_type, str):
            return None
        normalized = raw_type.strip().upper()
        if not normalized:
            return None
        return self._typed_entity_type_map.get(normalized, "concept")

    def _score_to_confidence(self, score: Any, *, default: float) -> float:
        if isinstance(score, (int, float)):
            return max(0.5, min(0.99, float(score) / 15.0))
        return default

    def _is_placeholder_entity_name(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        candidate = value.strip().upper()
        return bool(re.fullmatch(r"(SPEAKER|FACE)_\d+", candidate))

    def _is_meaningful_person_name(self, value: Any) -> bool:
        if not self._is_valid_entity_candidate(value):
            return False
        return not self._is_placeholder_entity_name(value)

    def _is_scene_place_tag(self, value: Any, detail_sources: Set[str]) -> bool:
        if not isinstance(value, str):
            return False
        normalized = self._normalize_name(value)
        if not normalized:
            return False
        if "place" in detail_sources:
            return True
        return normalized in {self._normalize_name(label) for label in _SCENE_PLACE_LABELS}

    def _object_label_set(self, scene_data: Dict[str, Any]) -> Set[str]:
        labels: Set[str] = set()
        objects = scene_data.get("objects") or scene_data.get("detected_objects") or []
        if not isinstance(objects, list):
            return labels
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            label = obj.get("class") or obj.get("label")
            if isinstance(label, str) and label.strip():
                labels.add(self._normalize_name(label))
        return labels

    def _is_valid_entity_candidate(self, token: Any) -> bool:
        """Filter filler tokens and low-signal fragments from becoming entities."""
        if not isinstance(token, str):
            return False
        raw = token.strip()
        if not raw:
            return False
        lower_raw = raw.lower()

        # Explicit stopword filter (case-insensitive).
        if lower_raw in self.stopwords:
            return False

        # Skip punctuation-only fragments and isolated contraction suffixes.
        if re.fullmatch(r"[^\w]+", raw):
            return False
        if lower_raw in self._contraction_parts:
            return False

        # Skip very short lowercase fragments unless they appear capitalized.
        compact = re.sub(r"[^A-Za-z0-9]+", "", raw)
        if compact and len(compact) < 2:
            return False
        is_capitalized = bool(raw[:1].isupper())
        if compact and len(compact) < 3 and not is_capitalized:
            return False

        return True


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
