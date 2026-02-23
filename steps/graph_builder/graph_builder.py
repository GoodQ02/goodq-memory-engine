"""
Knowledge Graph Builder Step
Constructs semantic graph from multimodal analysis results
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from zenml import step

logger = logging.getLogger(__name__)


@step
def build_knowledge_graph(
    analysis_results: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build knowledge graph from multimodal analysis results
    
    Args:
        analysis_results: Complete analysis results from pipeline
        config: Configuration including paths
    
    Returns:
        Graph statistics and metadata
    """
    from lib.knowledge_graph import KnowledgeGraph
    
    # Initialize knowledge graph
    kg_db = (config.get("paths") or {}).get("knowledge_graph_db")
    if not kg_db:
        raise RuntimeError("knowledge_graph_db missing from config paths")
    graph_db_path = Path(kg_db)
    graph_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Building knowledge graph at {graph_db_path}")
    
    with KnowledgeGraph(str(graph_db_path)) as kg:
        video_path = analysis_results.get('video_path', '')
        scenes = analysis_results.get('scenes', [])
        
        for scene_idx, scene in enumerate(scenes):
            scene_id = f"scene_{scene_idx:04d}"
            start_time = scene.get('start_time', 0.0)
            end_time = scene.get('end_time', 0.0)
            
            # Add media node for this scene
            media_id = kg.add_media_node(
                media_type='video_scene',
                media_path=video_path,
                scene_id=scene_id,
                timestamp_start=start_time,
                timestamp_end=end_time,
                properties={
                    'duration': end_time - start_time,
                    'confidence': scene.get('confidence', 0.0)
                }
            )
            
            # Extract and add entities from various sources
            _process_objects(kg, scene, media_id, start_time)
            _process_faces(kg, scene, media_id, start_time)
            _process_text(kg, scene, media_id, start_time, config)
            _process_audio(kg, scene, media_id, start_time)
            _process_emotions(kg, scene, media_id, start_time)
            _process_locations(kg, scene, media_id, start_time)
            
            # Create temporal event for scene
            event_id = kg.add_temporal_event(
                event_type='scene_change',
                timestamp=start_time,
                duration=end_time - start_time,
                properties={
                    'scene_id': scene_id,
                    'confidence': scene.get('confidence', 0.0)
                }
            )
        
        # Build co-occurrence relationships
        _build_cooccurrence_edges(kg)
        
        # Build temporal relationships
        _build_temporal_edges(kg)
        
        # Build semantic relationships
        _build_semantic_edges(kg)
        
        # Analyze emotional arc across scenes (LLM-powered)
        if config.get('llm', {}).get('enabled', False):
            _analyze_and_add_emotional_arc(kg, scenes, analysis_results.get('media_id'), config)
        
        # Get statistics
        stats = kg.get_statistics()
        
        logger.info(f"Knowledge graph built: {stats}")
        
        return {
            'graph_db_path': str(graph_db_path),
            'statistics': stats,
            'status': 'success'
        }


def _process_objects(kg, scene: Dict, media_id: int, timestamp: float):
    """Extract and add object entities"""
    # Handle both 'detections' and 'objects' fields
    detections = scene.get('detections', []) or scene.get('objects', [])
    
    for det in detections:
        label = det.get('label', 'unknown')
        confidence = det.get('confidence', 0.0)
        bbox = det.get('bbox', [])
        
        # Add object node
        node_id = kg.add_node(
            node_type='object',
            name=label,
            properties={
                'category': det.get('category', 'general')
            },
            timestamp=timestamp
        )
        
        # Link to media
        kg.link_node_to_media(
            node_id=node_id,
            media_id=media_id,
            confidence=confidence,
            context={'bbox': bbox, 'timestamp': timestamp}
        )


def _process_faces(kg, scene: Dict, media_id: int, timestamp: float):
    """Extract and add face/person entities"""
    faces = scene.get('faces', [])
    
    for face_idx, face in enumerate(faces):
        # Create person node (could be enhanced with face recognition)
        person_name = f"person_{face_idx}"
        
        node_id = kg.add_node(
            node_type='person',
            name=person_name,
            properties={
                'face_embedding_available': True
            },
            timestamp=timestamp
        )
        
        kg.link_node_to_media(
            node_id=node_id,
            media_id=media_id,
            confidence=face.get('confidence', 1.0),
            context={'bbox': face.get('bbox', []), 'timestamp': timestamp}
        )


def _process_text(kg, scene: Dict, media_id: int, timestamp: float, cfg: Dict[str, Any] = None):
    """Extract and add text/concept entities"""
    # OCR text
    ocr_text = scene.get('ocr_text', '')
    if ocr_text:
        node_id = kg.add_node(
            node_type='text',
            name='ocr_content',
            properties={'content': ocr_text},
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=1.0)
    
    # Captions
    caption = scene.get('caption', '')
    if caption:
        # Extract concepts from caption
        # This could be enhanced with NLP/NER
        concepts = _extract_concepts(caption)
        for concept in concepts:
            node_id = kg.add_node(
                node_type='concept',
                name=concept,
                timestamp=timestamp
            )
            kg.link_node_to_media(node_id, media_id, confidence=0.8)
    
    # Tags
    tags = scene.get('tags', [])
    for tag in tags:
        node_id = kg.add_node(
            node_type='tag',
            name=tag,
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=0.9)
    
    # LLM-enhanced entity extraction
    if cfg and cfg.get('llm', {}).get('enabled', False):
        _process_llm_entities(kg, scene, media_id, timestamp, cfg)


def _process_audio(kg, scene: Dict, media_id: int, timestamp: float):
    """Extract and add audio-based entities"""
    audio_data = scene.get('audio', {})
    
    # Transcription
    transcript = audio_data.get('transcript', '')
    if transcript:
        # Extract speakers
        speakers = audio_data.get('speakers', [])
        for speaker in speakers:
            speaker_id = speaker.get('speaker_id', 'unknown')
            node_id = kg.add_node(
                node_type='speaker',
                name=speaker_id,
                timestamp=timestamp
            )
            kg.link_node_to_media(node_id, media_id, confidence=0.9)
        
        # Extract mentioned entities (could use NER)
        mentions = _extract_mentions(transcript)
        for mention in mentions:
            node_id = kg.add_node(
                node_type='mention',
                name=mention,
                timestamp=timestamp
            )
            kg.link_node_to_media(node_id, media_id, confidence=0.7)
    
    # Music/audio events
    music_events = audio_data.get('music_events', [])
    for event in music_events:
        event_type = event.get('type', 'audio_event')
        node_id = kg.add_node(
            node_type='audio_event',
            name=event_type,
            properties=event,
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=event.get('confidence', 0.8))


def _process_emotions(kg, scene: Dict, media_id: int, timestamp: float):
    """Extract and add emotion entities"""
    # Sentiment
    sentiment = scene.get('sentiment', {})
    if sentiment:
        score = sentiment.get('score', 0.0)
        label = sentiment.get('label', 'neutral')
        
        node_id = kg.add_node(
            node_type='emotion',
            name=f"sentiment_{label}",
            properties={'score': score},
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=abs(score))
    
    # Emotion classification
    emotions = scene.get('emotions', [])
    for emotion in emotions:
        node_id = kg.add_node(
            node_type='emotion',
            name=emotion.get('label', 'unknown'),
            properties={'score': emotion.get('score', 0.0)},
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=emotion.get('score', 0.5))


def _process_locations(kg, scene: Dict, media_id: int, timestamp: float):
    """Extract and add location entities
    
    Future enhancements:
    - GPS data extraction from EXIF metadata
    - Vision-based location recognition
    - NLP-based location extraction from transcripts
    """
    # Extract locations from scene metadata if available
    locations = scene.get('locations', [])
    for location in locations:
        node_id = kg.add_node(
            node_type='location',
            name=location.get('name', 'unknown'),
            properties=location,
            timestamp=timestamp
        )
        kg.link_node_to_media(node_id, media_id, confidence=location.get('confidence', 0.5))



def _build_cooccurrence_edges(kg):
    """Build edges between entities that co-occur in media"""
    logger.info("Building co-occurrence edges")
    
    # Get all media nodes
    cursor = kg.conn.cursor()
    media_nodes = cursor.execute("SELECT id FROM media_nodes").fetchall()
    
    for (media_id,) in media_nodes:
        # Get all nodes in this media
        nodes = cursor.execute("""
            SELECT node_id FROM node_media WHERE media_id = ?
        """, (media_id,)).fetchall()
        
        node_ids = [n[0] for n in nodes]
        
        # Create co-occurrence edges
        for i, node1 in enumerate(node_ids):
            for node2 in node_ids[i+1:]:
                kg.add_edge(
                    source_id=node1,
                    target_id=node2,
                    edge_type='co_occurs',
                    weight=1.0
                )


def _build_temporal_edges(kg):
    """Build edges between temporally adjacent entities"""
    logger.info("Building temporal edges")
    
    cursor = kg.conn.cursor()
    
    # Get all media nodes ordered by time
    media_nodes = cursor.execute("""
        SELECT id, timestamp_start, timestamp_end
        FROM media_nodes
        ORDER BY timestamp_start ASC
    """).fetchall()
    
    # Connect entities in adjacent time windows
    for i in range(len(media_nodes) - 1):
        media1_id, start1, end1 = media_nodes[i]
        media2_id, start2, end2 = media_nodes[i + 1]
        
        # Get nodes from both media
        nodes1 = [n[0] for n in cursor.execute(
            "SELECT node_id FROM node_media WHERE media_id = ?", (media1_id,)
        ).fetchall()]
        
        nodes2 = [n[0] for n in cursor.execute(
            "SELECT node_id FROM node_media WHERE media_id = ?", (media2_id,)
        ).fetchall()]
        
        # Create temporal edges
        for node1 in nodes1:
            for node2 in nodes2:
                kg.add_edge(
                    source_id=node1,
                    target_id=node2,
                    edge_type='temporal_next',
                    weight=0.5
                )


def _build_semantic_edges(kg):
    """Build semantic relationship edges"""
    logger.info("Building semantic edges")
    
    cursor = kg.conn.cursor()
    
    # Example: Connect emotions to objects/people they're associated with
    # This could be expanded with more sophisticated semantic analysis
    
    # Connect objects to locations they appear in
    objects = cursor.execute("""
        SELECT id FROM nodes WHERE node_type = 'object'
    """).fetchall()
    
    locations = cursor.execute("""
        SELECT id FROM nodes WHERE node_type = 'location'
    """).fetchall()
    
    for (obj_id,) in objects:
        for (loc_id,) in locations:
            # Check if they co-occur
            co_occurs = cursor.execute("""
                SELECT COUNT(*) FROM node_media nm1
                JOIN node_media nm2 ON nm1.media_id = nm2.media_id
                WHERE nm1.node_id = ? AND nm2.node_id = ?
            """, (obj_id, loc_id)).fetchone()[0]
            
            if co_occurs > 0:
                kg.add_edge(
                    source_id=obj_id,
                    target_id=loc_id,
                    edge_type='located_in',
                    weight=float(co_occurs)
                )


def _extract_concepts(text: str) -> List[str]:
    """Extract key concepts from text using simple heuristics
    
    Future enhancement: Replace with proper NLP (spaCy, BERT-based NER)
    Current: Uses capitalization patterns and word length filters
    """
    concepts = []
    
    # Simple extraction based on capitalization and common patterns
    words = text.split()
    for word in words:
        if len(word) > 3 and word[0].isupper():
            concepts.append(word.lower())
    
    return list(set(concepts))[:10]  # Limit to top 10


def _extract_mentions(text: str) -> List[str]:
    """Extract entity mentions from text using pattern matching
    
    Future enhancement: Integrate spaCy NER or similar NLP library
    Current: Uses simple capitalization heuristic for proper nouns
    """
    mentions = []
    
    # Simple pattern matching for now
    words = text.split()
    for i, word in enumerate(words):
        if word[0].isupper() and i > 0:  # Capitalized mid-sentence
            mentions.append(word)
    
    return list(set(mentions))


def _process_llm_entities(kg, scene: Dict, media_id: int, timestamp: float, cfg: Dict[str, Any]):
    """Use LLM to extract and enrich entities from scene data"""
    try:
        from .llm_enrichment import extract_entities_with_llm, generate_scene_narrative
        
        # Gather text for entity extraction
        text_sources = []
        
        audio = scene.get('audio', {})
        if audio.get('transcript'):
            text_sources.append(audio['transcript'])
        
        if scene.get('caption'):
            text_sources.append(scene['caption'])
        
        if scene.get('ocr_text'):
            text_sources.append(scene['ocr_text'])
        
        combined_text = " ".join(text_sources)
        
        if not combined_text or len(combined_text) < 20:
            return
        
        # Build context for LLM
        context = {
            'objects': scene.get('objects', []),
            'emotions': scene.get('emotions', []),
            'sentiment': scene.get('sentiment', {}),
            'audio': audio
        }
        
        # Extract entities using LLM
        llm_entities = extract_entities_with_llm(combined_text, context, cfg)
        
        # Add extracted entities to knowledge graph
        for entity_type, entities in llm_entities.items():
            for entity in entities:
                name = entity.get('name', '').strip()
                if not name:
                    continue
                
                confidence = entity.get('confidence', 0.7)
                
                # Map entity types to node types
                node_type_map = {
                    'people': 'person',
                    'locations': 'location',
                    'objects': 'object',
                    'events': 'event',
                    'topics': 'topic',
                    'temporal_references': 'temporal_ref'
                }
                
                node_type = node_type_map.get(entity_type, 'entity')
                
                # Add node with LLM-extracted metadata
                properties = {k: v for k, v in entity.items() if k not in ['name', 'confidence']}
                properties['llm_extracted'] = True
                
                node_id = kg.add_node(
                    node_type=node_type,
                    name=name,
                    properties=properties,
                    timestamp=timestamp
                )
                
                # Link to media
                kg.link_node_to_media(
                    node_id=node_id,
                    media_id=media_id,
                    confidence=confidence,
                    context={'extraction_method': 'llm', 'timestamp': timestamp}
                )
        
        # Generate and store scene narrative
        narrative = generate_scene_narrative(scene, cfg)
        if narrative:
            node_id = kg.add_node(
                node_type='narrative',
                name='scene_narrative',
                properties={'content': narrative, 'llm_generated': True},
                timestamp=timestamp
            )
            kg.link_node_to_media(node_id, media_id, confidence=0.9)
        
        logger.info(f"LLM enrichment added {sum(len(v) for v in llm_entities.values())} entities")
        
    except ImportError:
        logger.warning("LLM enrichment module not available")
    except Exception as e:
        logger.error(f"LLM entity processing failed: {e}")


def _analyze_and_add_emotional_arc(kg, scenes: List[Dict], video_media_id: Optional[int], cfg: Dict[str, Any]):
    """Analyze emotional arc across all scenes and add to knowledge graph"""
    try:
        from .emotion_arc_analyzer import analyze_emotional_arc, add_emotional_arc_to_kg
        
        # Analyze emotional arc
        arc_analysis = analyze_emotional_arc(scenes, cfg)
        
        if arc_analysis and video_media_id:
            # Add to knowledge graph
            add_emotional_arc_to_kg(kg, arc_analysis, video_media_id, cfg)
        elif arc_analysis:
            logger.warning("Emotional arc generated but no video_media_id provided")
        
    except ImportError:
        logger.warning("Emotion arc analyzer module not available")
    except Exception as e:
        logger.error(f"Emotional arc analysis failed: {e}")
