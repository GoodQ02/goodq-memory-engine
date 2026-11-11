"""
GoodQ4All - Entity Extraction Pipeline Step
Extracts and resolves entities from multi-modal scene data
"""
import os
import json
import logging
import math
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
    "bathroom": "Bathroom",
    "office": "Office",
    "cafe": "Cafe",
    "coffee shop": "Cafe",
    "restaurant": "Restaurant",
    "diner": "Diner",
    "street": "Street",
    "sidewalk": "Street",
    "intersection": "Street",
}

# Model-generated descriptions hedge ("possibly a home office or living room").
# A place named only inside a hedged clause is a guess, not a scene place.
_HEDGE_CUE = re.compile(
    r"\b(?:possibly|perhaps|maybe|likely|probably|presumably|appears? to be|seems? to be|"
    r"could be|might be|may be|suggest(?:s|ing)?|resembl(?:es|ing)|or)\b"
)


def is_hedged_mention(text: str, start: int) -> bool:
    """Return True when the phrase at ``start`` sits after a hedge cue in its clause."""
    clause_start = max(text.rfind(mark, 0, start) for mark in (".", ";", "!", "?", "\n")) + 1
    return _HEDGE_CUE.search(text[clause_start:start].lower()) is not None


_OBJECT_PLACE_SIGNATURES = (
    # A sink occurs in several rooms; retain the detection without guessing a room.
    ({"refrigerator"}, "Kitchen", 0.78),
    ({"oven"}, "Kitchen", 0.78),
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
    confidence: Optional[float]
    source_modality: str  # vision, audio, text, metadata
    source_step: str  # face_embed, transcription, ocr, etc.
    properties: Dict[str, Any]
    timestamps: List[float]  # All timestamps where entity appears
    
    def to_dict(self):
        return asdict(self)


_ROSTER_NAME_CACHE: Dict[str, tuple[int, frozenset[str]]] = {}


def _load_roster_names_cached(raw_path: Any) -> Set[str]:
    if not isinstance(raw_path, (str, Path)) or not str(raw_path).strip():
        return set()
    try:
        candidate = Path(str(raw_path).strip())
        if candidate.suffix.lower() not in {".yaml", ".yml"}:
            candidate = candidate / "family_roster.yaml"
        if not candidate.is_file():
            return set()
        resolved = str(candidate.resolve())
        mtime_ns = candidate.stat().st_mtime_ns
        cached = _ROSTER_NAME_CACHE.get(resolved)
        if cached is not None and cached[0] == mtime_ns:
            return set(cached[1])
        import yaml
        payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        names: Set[str] = set()
        identities = payload.get("identities") if isinstance(payload, dict) else None
        if isinstance(identities, list):
            for entry in identities:
                if not isinstance(entry, dict):
                    continue
                display = str(entry.get("display_name") or "").strip().lower()
                if display:
                    names.add(display)
                aliases = entry.get("aliases")
                if isinstance(aliases, (list, tuple, set)):
                    for alias in aliases:
                        alias_val = str(alias or "").strip().lower()
                        if alias_val:
                            names.add(alias_val)
        _ROSTER_NAME_CACHE[resolved] = (mtime_ns, frozenset(names))
        return names
    except Exception:
        return set()


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
            'kiss', 'sit', 'happy', 'gaming', 'yay', 'whoa', 'wow',
        }
        self._non_person_single_tokens = {
            'lion', 'tiger', 'bear', 'puppy', 'kitty', 'bunny',
            'mayor', 'doctor', 'nurse', 'teacher', 'coach',
            'baby', 'child', 'kids', 'boys', 'girls', 'lady',
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
        """Load optional configured person/role terms without hardcoding a private family tree."""
        defaults: Set[str] = {
            "mom", "mother",
            "dad", "father",
            "grandma", "grandmother",
            "grandpa", "grandfather",
            "aunt", "uncle",
        }
        candidate_lists: List[Any] = [self.config.get("family_names")]
        user_cfg = self.config.get("user")
        if isinstance(user_cfg, dict):
            candidate_lists.append(user_cfg.get("family_names"))
        audio_cfg = self.config.get("audio")
        if isinstance(audio_cfg, dict):
            transcribe_cfg = audio_cfg.get("transcribe")
            if isinstance(transcribe_cfg, dict):
                candidate_lists.append(transcribe_cfg.get("vocabulary"))
        for configured in candidate_lists:
            if isinstance(configured, (list, tuple, set)):
                for item in configured:
                    val = str(item or "").strip().lower()
                    if val:
                        defaults.add(val)
        id_search = self.config.get("identity_search")
        if isinstance(id_search, dict):
            defaults.update(_load_roster_names_cached(id_search.get("roster_path")))
        id_matching = self.config.get("identity_matching")
        if isinstance(id_matching, dict):
            ref_sources = id_matching.get("reference_sources")
            if isinstance(ref_sources, list):
                for source in ref_sources:
                    if isinstance(source, dict):
                        defaults.update(_load_roster_names_cached(source.get("identity_path")))
        return defaults
    
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
            has_tags = bool(scene_data.get('tags'))
            has_faces = bool(scene_data.get('faces'))
            if has_transcript or has_caption or has_ocr or has_objects or has_tags or has_faces:
                logger.info(
                    "[ENTITY] Preliminary extraction pass resolved 0 entities; "
                    "later transcript/temporal KG passes may still resolve entities. "
                    "Inputs: transcript=%s, caption=%s, ocr=%s, objects=%s, tags=%s, faces=%s",
                    has_transcript,
                    has_caption,
                    has_ocr,
                    has_objects,
                    has_tags,
                    has_faces,
                )
            else:
                logger.info(
                    "[ENTITY] No entity-bearing inputs available yet for current extraction pass; "
                    "later audio/temporal passes may still resolve entities."
                )
        
        return entities
    
    def _extract_from_vision(self, scene_data: Dict, scene_id: str) -> List[ExtractedEntity]:
        """Extract entities from visual analysis (captions, descriptions)"""
        entities = []
        caption_texts: List[str] = []
        seen_texts: set[str] = set()

        primary_caption = scene_data.get("caption")
        if isinstance(primary_caption, str) and primary_caption.strip():
            seen_texts.add(primary_caption.strip().casefold())
            caption_texts.append(primary_caption.strip())

        keyframe_data = scene_data.get("keyframe") if isinstance(scene_data.get("keyframe"), dict) else {}
        cap_obs = scene_data.get("caption_observations") or keyframe_data.get("caption_observations")
        if isinstance(cap_obs, list):
            for obs in cap_obs:
                if isinstance(obs, dict):
                    obs_cap = obs.get("caption")
                    if isinstance(obs_cap, str) and obs_cap.strip():
                        norm_cap = obs_cap.strip().casefold()
                        if norm_cap not in seen_texts:
                            seen_texts.add(norm_cap)
                            caption_texts.append(obs_cap.strip())

        # From BLIP/BLIP2 captions
        for caption in caption_texts:
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
        audio_source = scene_data.get("audio") if isinstance(scene_data.get("audio"), dict) else scene_data
        from steps.common.tag_utils import reliable_transcript_for_entities

        transcript_text = reliable_transcript_for_entities(audio_source)
        
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
                    # Preserve observed detector scores; keep missing scores unknown (None) rather than inventing a default.
                    raw_score = obj.get("score") if "score" in obj else obj.get("confidence")
                    has_observed_score = isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool)
                    confidence = float(raw_score) if has_observed_score else None
                    raw_ts = (
                        obj.get("timestamp")
                        if isinstance(obj.get("timestamp"), (int, float)) and not isinstance(obj.get("timestamp"), bool)
                        else scene_data.get("start_time", 0)
                    )
                    
                    entities.append(ExtractedEntity(
                        entity_id=f"{scene_id}_obj_{obj_name}",
                        entity_type="object",
                        name=obj_name,
                        confidence=confidence,
                        source_modality="vision",
                        source_step="object_detect",
                        properties={
                            "bbox": obj.get("bbox"),
                            "detection": obj,
                            "verification_status": "candidate_unconfirmed",
                            "source_step": "object_detect",
                            "score_status": "observed" if has_observed_score else "unknown",
                            "detector_score": confidence,
                            "raw_score": confidence,
                            "establishes_visible_presence": False,
                        },
                        timestamps=[raw_ts]
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
                if self._is_family_name(tag_name) or normalized_name in {"santa", "santa claus"}:
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
                if self._is_family_name(tag) or normalized_tag in {"santa", "santa claus"}:
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
        ambiguous_person_labels = self._ambiguous_person_labels(payload)

        ner_entities = payload.get("ner_entities")
        if isinstance(ner_entities, list):
            for idx, entity in enumerate(ner_entities):
                if not isinstance(entity, dict):
                    continue
                name = entity.get("name") or entity.get("label")
                entity_type = self._normalize_typed_entity_type(entity.get("type"))
                if entity_type is None or not self._is_valid_entity_candidate(name):
                    continue
                if entity_type == "person":
                    if self._is_ambiguous_person_label(name, ambiguous_person_labels):
                        continue
                    if not self._is_meaningful_person_name(name):
                        continue
                resolved_step = str(entity.get("source_step") or default_step)
                ner_props: Dict[str, Any] = {"ner_entity": entity}
                if entity_type == "object":
                    ner_props["mention_scope"] = (
                        "spoken_mention"
                        if modality == "audio"
                        else ("written_text" if "ocr" in resolved_step.lower() else "caption_mention")
                    )
                    ner_props["verification_status"] = (
                        "mentioned_not_visibly_confirmed"
                        if modality == "audio" or "ocr" in resolved_step.lower()
                        else "candidate_unconfirmed"
                    )
                    ner_props["establishes_visible_presence"] = False
                entities.append(ExtractedEntity(
                    entity_id=f"{scene_id}_{modality}_ner_{idx}",
                    entity_type=entity_type,
                    name=str(name).strip(),
                    confidence=0.92,
                    source_modality=modality,
                    source_step=resolved_step,
                    properties=ner_props,
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
                if entity_type == "person":
                    if self._is_ambiguous_person_label(name, ambiguous_person_labels):
                        continue
                    if not self._is_meaningful_person_name(name):
                        continue

                detail_props: Dict[str, Any] = {"detail_sources": sorted(detail_sources), "detail": detail}
                if entity_type == "object":
                    detail_props["mention_scope"] = (
                        "spoken_mention"
                        if modality == "audio"
                        else ("written_text" if "ocr" in str(default_step).lower() else "caption_mention")
                    )
                    detail_props["verification_status"] = (
                        "mentioned_not_visibly_confirmed"
                        if modality == "audio" or "ocr" in str(default_step).lower()
                        else "candidate_unconfirmed"
                    )
                    detail_props["establishes_visible_presence"] = False

                entities.append(ExtractedEntity(
                    entity_id=f"{scene_id}_{modality}_detail_{idx}",
                    entity_type=entity_type,
                    name=str(name).strip(),
                    confidence=self._score_to_confidence(detail.get("score"), default=0.82),
                    source_modality=modality,
                    source_step=default_step,
                    properties=detail_props,
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
            matches = list(re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)", text_lower))
            if matches:
                if not any(self._is_valid_entity_candidate(text[m.start():m.end()]) for m in matches):
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
            matches = [m for m in re.finditer(rf"\b{re.escape(phrase)}\b", lowered)
                       if not is_hedged_mention(lowered, m.start())]
            if not matches:
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
        object_scores: Dict[str, float] = {}
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            label = self._normalize_name(str(obj.get("class") or obj.get("label") or ""))
            score = obj.get("score") if "score" in obj else obj.get("confidence")
            if (
                not label
                or not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not math.isfinite(score)
                or not 0.0 <= score <= 1.0
            ):
                continue
            object_scores[label] = max(object_scores.get(label, 0.0), float(score))
        if not object_scores:
            return entities

        for required_labels, location_name, confidence in _OBJECT_PLACE_SIGNATURES:
            normalized_required = {self._normalize_name(label) for label in required_labels}
            # Do not turn weak or unknown detections into a stronger room claim.
            # Every defining object must support the rule's existing confidence.
            if any(object_scores.get(label, 0.0) < confidence for label in normalized_required):
                continue
            entities.append(ExtractedEntity(
                entity_id=f"{scene_id}_vision_place_{self._normalize_name(location_name)}",
                entity_type="location",
                name=location_name,
                confidence=confidence,
                source_modality="vision",
                source_step="object_place_inference",
                properties={
                    "matched_objects": sorted(normalized_required),
                    "matched_object_scores": {
                        label: object_scores[label] for label in sorted(normalized_required)
                    },
                    "verification_status": "candidate_unconfirmed",
                    "depends_on": ["object_detect"],
                    "establishes_visible_presence": False,
                },
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
            numeric_confidences = [
                e.confidence
                for e in group
                if isinstance(e.confidence, (int, float)) and not isinstance(e.confidence, bool)
            ]
            all_timestamps = []
            for e in group:
                all_timestamps.extend(e.timestamps)
            
            # Aggregate properties
            properties = {}
            if etype == "object":
                detector_entities = [
                    e for e in group
                    if e.source_step == "object_detect" or "detection" in e.properties
                ]
                mention_entities = [e for e in group if e not in detector_entities]
                for e in mention_entities:
                    properties.update(e.properties)
                for e in detector_entities:
                    properties.update(e.properties)
                detector_scores = [
                    float(e.confidence)
                    for e in detector_entities
                    if isinstance(e.confidence, (int, float)) and not isinstance(e.confidence, bool)
                ]
                mention_confidences = [
                    float(e.confidence)
                    for e in mention_entities
                    if isinstance(e.confidence, (int, float)) and not isinstance(e.confidence, bool)
                ]
                detections = [
                    e.properties["detection"]
                    for e in detector_entities
                    if "detection" in e.properties
                ]
                bboxes = [
                    e.properties["bbox"]
                    for e in detector_entities
                    if e.properties.get("bbox") is not None
                ]
                detector_timestamps = [ts for e in detector_entities for ts in e.timestamps]
                mention_timestamps = [ts for e in mention_entities for ts in e.timestamps]
                properties["establishes_visible_presence"] = False
                if detector_entities:
                    detector_score = max(detector_scores) if detector_scores else None
                    properties["detector_score"] = detector_score
                    properties["raw_score"] = detector_score
                    properties["score_status"] = "observed" if detector_score is not None else "unknown"
                    properties["source_step"] = "object_detect"
                    properties["verification_status"] = "candidate_unconfirmed"
                    if detections:
                        properties["detection"] = detections[0]
                        properties["detections"] = detections
                        properties["bboxes"] = bboxes
                        properties["bbox"] = bboxes[0] if bboxes else None
                    properties["detector_timestamps"] = sorted(list(set(detector_timestamps)))
                    if mention_entities:
                        properties["mention_confidence"] = (
                            max(mention_confidences) if mention_confidences else None
                        )
                        properties["mention_sources"] = sorted(
                            {e.source_step for e in mention_entities if e.source_step}
                        )
                        properties["mention_modalities"] = sorted(
                            {e.source_modality for e in mention_entities if e.source_modality}
                        )
                        properties["mention_timestamps"] = sorted(list(set(mention_timestamps)))
                    merged_confidence = detector_score
                else:
                    mention_score = max(mention_confidences) if mention_confidences else None
                    properties["detector_score"] = None
                    properties["raw_score"] = None
                    properties["score_status"] = "unknown"
                    properties["mention_confidence"] = mention_score
                    properties["verification_status"] = (
                        properties.get("verification_status") or "mentioned_not_visibly_confirmed"
                    )
                    merged_confidence = mention_score
            else:
                for e in group:
                    properties.update(e.properties)
                merged_confidence = max(numeric_confidences) if numeric_confidences else None
            
            merged_entity = {
                "entity_id": group[0].entity_id,
                "entity_type": etype,
                "name": group[0].name,  # Use first occurrence name
                "confidence": merged_confidence,
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

    def _is_synthetic_entity_name(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        candidate = value.strip().upper()
        return bool(re.fullmatch(r"(SPEAKER|FACE)_\d+", candidate))

    def _is_meaningful_person_name(self, value: Any) -> bool:
        if not self._is_valid_entity_candidate(value):
            return False
        if self._is_synthetic_entity_name(value):
            return False
        lowered = str(value).strip().lower()
        if lowered in self._non_person_single_tokens and not self._is_family_name(value):
            return False
        return True

    def _entity_key(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return re.sub(r"[^a-z0-9]+", "", value.strip().lower())

    def _is_family_name(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return value.strip().lower() in self.family_names

    def _ambiguous_person_labels(self, payload: Dict[str, Any]) -> Set[str]:
        """Find labels that structured NER also typed as non-person evidence."""
        labels: Set[str] = set()
        for key in ("ner_entities", "entity_details"):
            records = payload.get(key)
            if not isinstance(records, list):
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                name = record.get("name") or record.get("label")
                entity_type = self._normalize_typed_entity_type(record.get("type"))
                if entity_type is None or entity_type == "person":
                    continue
                label_key = self._entity_key(name)
                if label_key:
                    labels.add(label_key)
        return labels

    def _is_ambiguous_person_label(self, value: Any, ambiguous_person_labels: Set[str]) -> bool:
        if self._is_family_name(value):
            return False
        label_key = self._entity_key(value)
        return bool(label_key and label_key in ambiguous_person_labels)

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
