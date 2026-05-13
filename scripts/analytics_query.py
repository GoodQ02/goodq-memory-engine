"""
Interactive Analytics Query Interface
Allows natural language queries against the knowledge graph and memory database
"""
import sqlite3
import json
import logging
import requests
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger(__name__)


class AnalyticsQuery:
    """Interactive query interface with LLM-powered natural language support"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.memory_db = Path(config['paths']['db_path'])
        self.kg_db = Path(config['paths']['knowledge_graph_db'])
        self.llm_config = config.get('llm', {})
        self.llm_enabled = self.llm_config.get('enabled', False)
        
    def query(self, question: str, video_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Answer natural language questions about video content
        
        Args:
            question: Natural language query
            video_path: Optional specific video to query
            
        Returns:
            Structured answer with data and narrative response
        """
        logger.info(f"Processing query: {question}")
        
        result = {
            'question': question,
            'video_path': video_path,
            'timestamp': datetime.now().isoformat(),
            'data': {},
            'answer': '',
            'confidence': 0.0
        }
        
        try:
            # Classify query intent
            intent = self._classify_query_intent(question)
            logger.info(f"Query intent: {intent}")
            
            # Execute appropriate query
            if intent == 'emotional':
                result['data'] = self._query_emotions(question, video_path)
            elif intent == 'content':
                result['data'] = self._query_content(question, video_path)
            elif intent == 'temporal':
                result['data'] = self._query_temporal(question, video_path)
            elif intent == 'relationship':
                result['data'] = self._query_relationships(question, video_path)
            elif intent == 'search':
                result['data'] = self._query_search(question, video_path)
            else:
                result['data'] = self._query_general(question, video_path)
            
            # Generate natural language answer with LLM
            if self.llm_enabled and result['data']:
                answer, confidence = self._generate_answer(question, result['data'])
                result['answer'] = answer
                result['confidence'] = confidence
            
            return result
            
        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            result['error'] = str(e)
            return result
    
    def _classify_query_intent(self, question: str) -> str:
        """Classify the intent of the query"""
        question_lower = question.lower()
        
        # Emotional queries
        if any(word in question_lower for word in ['emotion', 'feel', 'sentiment', 'mood', 'happy', 'sad']):
            return 'emotional'
        
        # Content queries
        if any(word in question_lower for word in ['what', 'who', 'object', 'person', 'show', 'appear']):
            return 'content'
        
        # Temporal queries
        if any(word in question_lower for word in ['when', 'time', 'during', 'moment', 'scene']):
            return 'temporal'
        
        # Relationship queries
        if any(word in question_lower for word in ['relationship', 'interact', 'together', 'with']):
            return 'relationship'
        
        # Search queries
        if any(word in question_lower for word in ['find', 'search', 'look for', 'contains']):
            return 'search'
        
        return 'general'
    
    def _query_emotions(self, question: str, video_path: Optional[str]) -> Dict[str, Any]:
        """Query emotional data"""
        data = {
            'emotion_distribution': {},
            'sentiment_timeline': [],
            'emotional_peaks': [],
            'dominant_emotion': None
        }
        
        try:
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                # Build query
                if video_path:
                    video_hash = Path(video_path).stem
                    query = """
                        SELECT sentiment_label, sentiment_score, emotions_json
                        FROM embeddings
                        WHERE source_path LIKE ? AND sentiment_label IS NOT NULL
                    """
                    cursor.execute(query, (f"%{video_hash}%",))
                else:
                    query = """
                        SELECT sentiment_label, sentiment_score, emotions_json
                        FROM embeddings
                        WHERE sentiment_label IS NOT NULL
                    """
                    cursor.execute(query)
                
                emotions_count = {}
                sentiment_scores = []
                
                for sent_label, sent_score, emotions_json in cursor.fetchall():
                    sentiment_scores.append({'label': sent_label, 'score': sent_score})
                    
                    if emotions_json:
                        try:
                            emotions = json.loads(emotions_json)
                            for emotion in emotions:
                                label = emotion.get('label', '')
                                if label:
                                    emotions_count[label] = emotions_count.get(label, 0) + 1
                        except:
                            pass
                
                data['emotion_distribution'] = emotions_count
                data['sentiment_timeline'] = sentiment_scores[:100]  # Limit for performance
                
                if emotions_count:
                    dominant = max(emotions_count.items(), key=lambda x: x[1])
                    data['dominant_emotion'] = {'emotion': dominant[0], 'count': dominant[1]}
                
        except Exception as e:
            logger.error(f"Error querying emotions: {e}")
        
        return data
    
    def _query_content(self, question: str, video_path: Optional[str]) -> Dict[str, Any]:
        """Query content (objects, people, themes)"""
        data = {
            'entities': [],
            'themes': [],
            'transcripts': []
        }
        
        try:
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                # Extract key terms from question for search
                search_terms = self._extract_search_terms(question)
                
                if video_path:
                    video_hash = Path(video_path).stem
                    
                    # Search for entities matching terms
                    if search_terms:
                        placeholders = ' OR '.join(['n.name LIKE ?' for _ in search_terms])
                        params = [f"%{term}%" for term in search_terms]
                        params.append(f"%{video_hash}%")
                        
                        cursor.execute(f"""
                            SELECT DISTINCT n.node_type, n.name, n.occurrence_count, n.properties
                            FROM nodes n
                            JOIN node_media nm ON n.id = nm.node_id
                            JOIN media_nodes m ON nm.media_id = m.id
                            WHERE ({placeholders})
                            AND m.media_path LIKE ?
                            ORDER BY n.occurrence_count DESC
                            LIMIT 20
                        """, params)
                    else:
                        # Return top entities
                        cursor.execute("""
                            SELECT DISTINCT n.node_type, n.name, n.occurrence_count, n.properties
                            FROM nodes n
                            JOIN node_media nm ON n.id = nm.node_id
                            JOIN media_nodes m ON nm.media_id = m.id
                            WHERE m.media_path LIKE ?
                            ORDER BY n.occurrence_count DESC
                            LIMIT 20
                        """, (f"%{video_hash}%",))
                    
                    for node_type, name, count, props_json in cursor.fetchall():
                        props = json.loads(props_json) if props_json else {}
                        data['entities'].append({
                            'type': node_type,
                            'name': name,
                            'occurrences': count,
                            'properties': props
                        })
                    
                    # Get themes
                    cursor.execute("""
                        SELECT DISTINCT n.name, n.properties
                        FROM nodes n
                        JOIN node_media nm ON n.id = nm.node_id
                        JOIN media_nodes m ON nm.media_id = m.id
                        WHERE n.node_type = 'theme'
                        AND m.media_path LIKE ?
                    """, (f"%{video_hash}%",))
                    
                    for name, props_json in cursor.fetchall():
                        props = json.loads(props_json) if props_json else {}
                        data['themes'].append({
                            'name': name,
                            'properties': props
                        })
                
        except Exception as e:
            logger.error(f"Error querying content: {e}")
        
        return data
    
    def _query_temporal(self, question: str, video_path: Optional[str]) -> Dict[str, Any]:
        """Query temporal/time-based data"""
        data = {
            'scenes': [],
            'events': [],
            'timeline': []
        }
        
        try:
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                if video_path:
                    video_hash = Path(video_path).stem
                    
                    # Get scenes
                    cursor.execute("""
                        SELECT id, start, end, meta
                        FROM scenes
                        WHERE video_hash = ?
                        ORDER BY start
                    """, (video_hash,))
                    
                    for scene_id, start, end, meta_json in cursor.fetchall():
                        meta = json.loads(meta_json) if meta_json else {}
                        data['scenes'].append({
                            'id': scene_id,
                            'start': start,
                            'end': end,
                            'duration': end - start,
                            'metadata': meta
                        })
                    
                    # Get segments (speaker timeline)
                    cursor.execute("""
                        SELECT start, end, speaker, meta
                        FROM segments
                        WHERE video_hash = ?
                        ORDER BY start
                    """, (video_hash,))
                    
                    for start, end, speaker, meta_json in cursor.fetchall():
                        meta = json.loads(meta_json) if meta_json else {}
                        data['timeline'].append({
                            'start': start,
                            'end': end,
                            'speaker': speaker,
                            'metadata': meta
                        })
                
        except Exception as e:
            logger.error(f"Error querying temporal data: {e}")
        
        return data
    
    def _query_relationships(self, question: str, video_path: Optional[str]) -> Dict[str, Any]:
        """Query relationships between entities"""
        data = {
            'relationships': [],
            'co_occurrences': [],
            'network_stats': {}
        }
        
        try:
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                if video_path:
                    video_hash = Path(video_path).stem
                    
                    # Get relationships
                    cursor.execute("""
                        SELECT n1.name, n1.node_type, n2.name, n2.node_type, 
                               e.edge_type, e.weight, e.properties
                        FROM edges e
                        JOIN nodes n1 ON e.source_id = n1.id
                        JOIN nodes n2 ON e.target_id = n2.id
                        JOIN node_media nm ON n1.id = nm.node_id
                        JOIN media_nodes m ON nm.media_id = m.id
                        WHERE m.media_path LIKE ?
                        ORDER BY e.weight DESC
                        LIMIT 50
                    """, (f"%{video_hash}%",))
                    
                    for n1_name, n1_type, n2_name, n2_type, edge_type, weight, props_json in cursor.fetchall():
                        props = json.loads(props_json) if props_json else {}
                        data['relationships'].append({
                            'source': {'name': n1_name, 'type': n1_type},
                            'target': {'name': n2_name, 'type': n2_type},
                            'relationship': edge_type,
                            'strength': weight,
                            'properties': props
                        })
                    
                    # Get network statistics
                    cursor.execute("""
                        SELECT COUNT(DISTINCT e.id) as edge_count,
                               COUNT(DISTINCT n.id) as node_count
                        FROM edges e
                        JOIN nodes n ON e.source_id = n.id
                        JOIN node_media nm ON n.id = nm.node_id
                        JOIN media_nodes m ON nm.media_id = m.id
                        WHERE m.media_path LIKE ?
                    """, (f"%{video_hash}%",))
                    
                    result = cursor.fetchone()
                    if result:
                        data['network_stats'] = {
                            'total_edges': result[0],
                            'total_nodes': result[1]
                        }
                
        except Exception as e:
            logger.error(f"Error querying relationships: {e}")
        
        return data
    
    def _query_search(self, question: str, video_path: Optional[str]) -> Dict[str, Any]:
        """Full-text search across all data"""
        data = {
            'matching_scenes': [],
            'matching_entities': [],
            'matching_transcripts': []
        }
        
        try:
            # Extract search terms
            search_terms = self._extract_search_terms(question)
            
            if not search_terms:
                return data
            
            # Search in memory database
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                if video_path:
                    video_hash = Path(video_path).stem
                    
                    # Search scenes metadata
                    cursor.execute("""
                        SELECT id, start, end, meta
                        FROM scenes
                        WHERE video_hash = ? AND meta LIKE ?
                        ORDER BY start
                    """, (video_hash, f"%{search_terms[0]}%"))
                    
                    for scene_id, start, end, meta_json in cursor.fetchall():
                        meta = json.loads(meta_json) if meta_json else {}
                        data['matching_scenes'].append({
                            'id': scene_id,
                            'start': start,
                            'end': end,
                            'metadata': meta
                        })
            
            # Search in knowledge graph
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                for term in search_terms[:3]:  # Limit to top 3 terms
                    cursor.execute("""
                        SELECT DISTINCT n.node_type, n.name, n.properties, n.occurrence_count
                        FROM nodes n
                        WHERE n.name LIKE ?
                        ORDER BY n.occurrence_count DESC
                        LIMIT 10
                    """, (f"%{term}%",))
                    
                    for node_type, name, props_json, count in cursor.fetchall():
                        props = json.loads(props_json) if props_json else {}
                        data['matching_entities'].append({
                            'type': node_type,
                            'name': name,
                            'occurrences': count,
                            'properties': props
                        })
                
        except Exception as e:
            logger.error(f"Error in search query: {e}")
        
        return data
    
    def _query_general(self, question: str, video_path: Optional[str]) -> Dict[str, Any]:
        """General query - retrieve overview data"""
        data = {
            'overview': {},
            'highlights': []
        }
        
        try:
            # Get overview statistics
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                if video_path:
                    video_hash = Path(video_path).stem
                    
                    cursor.execute("""
                        SELECT COUNT(*) as scene_count,
                               MIN(start) as first_scene,
                               MAX(end) as last_scene
                        FROM scenes
                        WHERE video_hash = ?
                    """, (video_hash,))
                    
                    result = cursor.fetchone()
                    if result:
                        data['overview'] = {
                            'total_scenes': result[0],
                            'start_time': result[1],
                            'end_time': result[2],
                            'duration': result[2] - result[1] if result[2] else 0
                        }
            
            # Get highlights from KG
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                if video_path:
                    video_hash = Path(video_path).stem
                    
                    # Get top entities
                    cursor.execute("""
                        SELECT n.node_type, n.name, n.occurrence_count
                        FROM nodes n
                        JOIN node_media nm ON n.id = nm.node_id
                        JOIN media_nodes m ON nm.media_id = m.id
                        WHERE m.media_path LIKE ?
                        ORDER BY n.occurrence_count DESC
                        LIMIT 10
                    """, (f"%{video_hash}%",))
                    
                    data['highlights'] = [
                        {'type': t, 'name': n, 'count': c}
                        for t, n, c in cursor.fetchall()
                    ]
                
        except Exception as e:
            logger.error(f"Error in general query: {e}")
        
        return data
    
    def _extract_search_terms(self, question: str) -> List[str]:
        """Extract meaningful search terms from question"""
        # Remove common question words
        stop_words = {'what', 'when', 'where', 'who', 'how', 'why', 'is', 'are', 'was', 'were',
                     'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'about',
                     'show', 'tell', 'find', 'search', 'look', 'me', 'you', 'does', 'do'}
        
        words = question.lower().replace('?', '').split()
        terms = [w for w in words if w not in stop_words and len(w) > 2]
        
        return terms[:5]  # Limit to 5 most relevant terms
    
    def _generate_answer(self, question: str, data: Dict[str, Any]) -> tuple[str, float]:
        """Generate natural language answer using LLM"""
        if not self.llm_enabled:
            return "LLM not enabled", 0.0
        
        try:
            # Prepare data summary
            data_summary = json.dumps(data, indent=2)[:2000]  # Limit size
            
            prompt = f"""Answer this question based on the data provided:

QUESTION: {question}

DATA:
{data_summary}

Provide a clear, concise answer that directly addresses the question. 
Include specific details from the data. If the data is insufficient, say so.
Be conversational but precise."""

            api_url = self.llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
            
            response = requests.post(
                api_url,
                json={
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful video analytics assistant. Answer questions based on provided data. Be specific and cite evidence."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.4,
                    "max_tokens": 300,
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                confidence = 0.8  # Could be enhanced with model confidence scores
                return answer, confidence
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
        
        return "Unable to generate answer", 0.0


def interactive_query_session(config: Dict[str, Any]):
    """Run an interactive query session"""
    print("\n=== GoodQ Analytics Query Interface ===")
    print("Ask questions about your video content. Type 'quit' to exit.\n")
    
    query_engine = AnalyticsQuery(config)
    
    while True:
        try:
            question = input("\nYour question: ").strip()
            
            if not question or question.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            # Optional: ask for specific video
            video_path = input("Specific video (or press Enter for all): ").strip()
            if not video_path:
                video_path = None
            
            # Execute query
            result = query_engine.query(question, video_path)
            
            # Display results
            print("\n" + "="*60)
            if result.get('answer'):
                print(f"\nANSWER: {result['answer']}")
                print(f"Confidence: {result.get('confidence', 0.0):.2f}")
            
            if result.get('data'):
                print(f"\nDATA SUMMARY:")
                print(json.dumps(result['data'], indent=2)[:500])  # Limit output
                
            if result.get('error'):
                print(f"\nERROR: {result['error']}")
            
            print("="*60)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    from steps.common.config_loader import load_configs
    
    config = load_configs({})
    interactive_query_session(config)
