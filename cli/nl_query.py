"""
Natural Language Query Interface for Knowledge Graph
Allows querying the KG using natural language powered by LLM
"""
import sqlite3
import json
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

from lib.knowledge_graph import KnowledgeGraph
from steps.common.config_loader import load_configs


class KnowledgeGraphNLQuery:
    """Natural language query interface for the knowledge graph"""
    
    def __init__(self, kg_db_path: str, cfg: Optional[Dict[str, Any]] = None):
        self.kg_db_path = kg_db_path
        self.cfg = cfg or load_configs({})
        self.kg = KnowledgeGraph(kg_db_path)
        
    def _call_llm(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call LLM for natural language processing"""
        llm_config = self.cfg.get('llm', {})
        api_url = llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        
        try:
            response = requests.post(
                api_url,
                json={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,  # Lower temperature for more factual responses
                    "max_tokens": 500
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
        
        return None
    
    def parse_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Parse natural language query to determine intent and extract parameters
        
        Query types:
        - Entity lookup: "Who is in scene 5?"
        - Relationship: "How are X and Y connected?"
        - Temporal: "What happened before/after X?"
        - Attribute: "What emotions are in the video?"
        - Narrative: "Summarize the video"
        """
        system_prompt = """You are a query parser for a knowledge graph about video content.
Parse the user's natural language query and output JSON with:
{
  "intent": "entity_lookup" | "relationship" | "temporal" | "attribute" | "narrative",
  "entity": "name of entity if applicable",
  "entity_type": "person" | "object" | "location" | "concept" | null,
  "relationship_type": "co_occurs" | "causes" | "temporal_next" | null,
  "temporal_operator": "before" | "after" | "during" | null,
  "attribute": "emotion" | "sentiment" | "tag" | "theme" | null,
  "scope": "scene" | "video" | "all"
}

Examples:
Q: "Who was present in scene 5?"
A: {"intent": "entity_lookup", "entity_type": "person", "scope": "scene"}

Q: "What objects appear with the bottle?"
A: {"intent": "relationship", "entity": "bottle", "entity_type": "object", "relationship_type": "co_occurs"}

Q: "What emotions are detected?"
A: {"intent": "attribute", "attribute": "emotion", "scope": "all"}

Q: "What happened after the music started?"
A: {"intent": "temporal", "entity": "music", "temporal_operator": "after"}

Only output JSON, no explanation."""
        
        response = self._call_llm(system_prompt, query)
        
        if response:
            try:
                # Extract JSON from response (handle cases where LLM adds text)
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    return json.loads(response[json_start:json_end])
            except Exception as e:
                logger.warning(f"Failed to parse query intent: {e}")
        
        # Default fallback
        return {
            "intent": "entity_lookup",
            "entity": None,
            "entity_type": None,
            "scope": "all"
        }
    
    def entity_lookup(self, entity_name: Optional[str] = None, entity_type: Optional[str] = None) -> List[Dict]:
        """Look up entities in the graph"""
        conn = sqlite3.connect(self.kg_db_path)
        cursor = conn.cursor()
        
        query = "SELECT id, node_type, name, properties, occurrence_count, first_seen, last_seen FROM nodes WHERE 1=1"
        params = []
        
        if entity_name:
            query += " AND name LIKE ?"
            params.append(f"%{entity_name}%")
        
        if entity_type:
            query += " AND node_type = ?"
            params.append(entity_type)
        
        query += " ORDER BY occurrence_count DESC LIMIT 20"
        
        results = []
        for row in cursor.execute(query, params):
            props = json.loads(row[3]) if row[3] else {}
            results.append({
                'id': row[0],
                'type': row[1],
                'name': row[2],
                'properties': props,
                'occurrences': row[4],
                'first_seen': row[5],
                'last_seen': row[6]
            })
        
        conn.close()
        return results
    
    def find_relationships(self, entity_name: str, relationship_type: Optional[str] = None) -> List[Dict]:
        """Find entities related to the specified entity"""
        # First find the entity
        entities = self.entity_lookup(entity_name=entity_name)
        if not entities:
            return []
        
        node_id = entities[0]['id']
        
        # Use KG's find_related_nodes method
        related = self.kg.find_related_nodes(node_id, edge_type=relationship_type, max_depth=2)
        return related
    
    def temporal_query(self, entity_name: Optional[str], operator: str = "after") -> List[Dict]:
        """Find events before/after an entity or timestamp"""
        # Find entity first
        entities = self.entity_lookup(entity_name=entity_name)
        if not entities:
            return []
        
        # Get the entity's timeline
        media = self.kg.get_node_media(entities[0]['id'])
        
        if not media:
            return []
        
        # Get timestamp
        timestamp = media[0]['timestamp_start']
        time_window = 60.0  # Search within 60 seconds
        
        if operator == "before":
            # Events before this timestamp
            neighbors = self.kg.find_temporal_neighbors(timestamp - time_window / 2, time_window)
            return [e for e in neighbors if e['timestamp'] < timestamp]
        else:  # after
            neighbors = self.kg.find_temporal_neighbors(timestamp + time_window / 2, time_window)
            return [e for e in neighbors if e['timestamp'] > timestamp]
    
    def attribute_query(self, attribute: str) -> List[Dict]:
        """Query by attribute (emotion, sentiment, tag, theme)"""
        type_map = {
            'emotion': 'emotion',
            'sentiment': 'emotion',  # Stored as emotion nodes with sentiment_ prefix
            'tag': 'tag',
            'theme': 'theme',
            'concept': 'concept'
        }
        
        entity_type = type_map.get(attribute)
        return self.entity_lookup(entity_type=entity_type)
    
    def generate_narrative_response(self, query: str, data: Any) -> str:
        """Generate natural language response from query results using LLM"""
        system_prompt = """You are a helpful assistant that answers questions about video content.
Given raw query results from a knowledge graph, generate a concise, natural language response.
Focus on the most relevant information and present it clearly."""
        
        # Format data for LLM
        data_str = json.dumps(data, indent=2)[:2000]  # Limit size
        
        user_prompt = f"""Question: {query}

Query Results:
{data_str}

Generate a natural, concise answer based on the query results above."""
        
        response = self._call_llm(system_prompt, user_prompt)
        return response or "I found some results but couldn't generate a summary."
    
    def query(self, query: str, return_raw: bool = False) -> str:
        """
        Main query interface - takes natural language query and returns answer
        
        Args:
            query: Natural language query
            return_raw: If True, return raw data instead of natural language response
        
        Returns:
            Natural language answer or JSON string if return_raw=True
        """
        # Parse query intent
        intent_data = self.parse_query_intent(query)
        intent = intent_data.get('intent', 'entity_lookup')
        
        logger.info(f"Query intent: {intent_data}")
        
        # Execute appropriate query
        results = []
        
        if intent == 'entity_lookup':
            results = self.entity_lookup(
                entity_name=intent_data.get('entity'),
                entity_type=intent_data.get('entity_type')
            )
        
        elif intent == 'relationship':
            results = self.find_relationships(
                entity_name=intent_data.get('entity', ''),
                relationship_type=intent_data.get('relationship_type')
            )
        
        elif intent == 'temporal':
            results = self.temporal_query(
                entity_name=intent_data.get('entity'),
                operator=intent_data.get('temporal_operator', 'after')
            )
        
        elif intent == 'attribute':
            results = self.attribute_query(
                attribute=intent_data.get('attribute', 'tag')
            )
        
        elif intent == 'narrative':
            # Get overall statistics
            stats = self.kg.get_statistics()
            results = stats
        
        # Return raw data if requested
        if return_raw:
            return json.dumps(results, indent=2)
        
        # Generate natural language response
        return self.generate_narrative_response(query, results)
    
    def close(self):
        """Close knowledge graph connection"""
        if self.kg:
            self.kg.close()


def main():
    """Interactive query interface"""
    import sys
    
    cfg = load_configs({})
    kg_path = Path(cfg.get('data_dir', 'data')) / 'knowledge_graph.db'
    
    if not kg_path.exists():
        print(f"[FAIL] Knowledge graph not found at {kg_path}")
        print("Run ingestion first to build the knowledge graph.")
        return
    
    qi = KnowledgeGraphNLQuery(str(kg_path), cfg)
    
    print("\n" + "="*80)
    print("KNOWLEDGE GRAPH NATURAL LANGUAGE QUERY INTERFACE")
    print("="*80)
    print("\nExample queries:")
    print("  - Who appears in the video?")
    print("  - What objects are shown with the person?")
    print("  - What emotions are detected?")
    print("  - What happened after scene 5?")
    print("  - Summarize the video")
    print("\nType 'quit' to exit, 'stats' for statistics")
    print("="*80 + "\n")
    
    while True:
        try:
            query = input("\n[SEARCH] Query: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            if query.lower() == 'stats':
                stats = qi.kg.get_statistics()
                print("\n" + json.dumps(stats, indent=2))
                continue
            
            # Execute query
            print("\n[SYMBOL] Processing...")
            response = qi.query(query)
            print(f"\n[STATS] Answer:\n{response}\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[FAIL] Error: {e}")
    
    qi.close()
    print("\n[SYMBOL] Goodbye!\n")


if __name__ == '__main__':
    main()
