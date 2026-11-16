"""
Natural Language Query Interface for Knowledge Graph
Allows querying the KG using natural language powered by LLM
"""
from __future__ import annotations

from collections import deque
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from api.utils.loaders import scene_is_retired
from lib.kg_realtime_integration import _resolve_graph_db_path
from lib.summary_aggregator import _project_node_statistics, _retirement_graph_projection
from steps.common import sqlite_read_authority
from steps.common.config_loader import load_configs

logger = logging.getLogger(__name__)

_LOOPBACK_LLM_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _validate_loopback_llm_url(api_url: str) -> str:
    parsed = urlparse(str(api_url or "").strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or hostname not in _LOOPBACK_LLM_HOSTS:
        raise ValueError(f"Refusing non-loopback LLM endpoint: {api_url}")
    return str(api_url).strip()


class _ReadOnlyGraphStatsFacade:
    """Compatibility shim for callers expecting ``qi.kg.get_statistics()``."""

    def __init__(self, owner: "KnowledgeGraphNLQuery") -> None:
        self._owner = owner

    def get_statistics(self) -> Dict[str, Any]:
        return self._owner.get_statistics()

    def close(self) -> None:
        return None


class KnowledgeGraphNLQuery:
    """Natural language query interface for the knowledge graph (strictly read-only)."""

    def __init__(self, kg_db_path: Optional[str] = None, cfg: Optional[Dict[str, Any]] = None):
        self.cfg = cfg if cfg is not None else load_configs({})
        resolved_path = Path(kg_db_path) if kg_db_path else _resolve_graph_db_path(self.cfg)
        self.kg_db_path = str(resolved_path)
        self.kg = _ReadOnlyGraphStatsFacade(self)

    def _open_read_conn(self) -> sqlite3.Connection:
        conn = sqlite_read_authority.open_sqlite_read_connection(
            self.kg_db_path,
            unavailable_message="Knowledge graph database is unavailable",
        )
        conn.row_factory = sqlite3.Row
        return conn

    def _retired_scene_names(self, conn: sqlite3.Connection, retired_media: set) -> set[str]:
        if not retired_media:
            return set()
        placeholders = ",".join("?" for _ in retired_media)
        rows = conn.execute(
            f"SELECT DISTINCT scene_id FROM media_nodes WHERE id IN ({placeholders}) AND scene_id IS NOT NULL",
            tuple(sorted(retired_media)),
        ).fetchall()
        retired_scenes = {str(r[0]) for r in rows if r[0]}
        # Exclude only scene_ids that have zero surviving media_nodes rows.
        if retired_scenes:
            surviving_placeholders = ",".join("?" for _ in retired_scenes)
            surviving = conn.execute(
                f"SELECT DISTINCT scene_id FROM media_nodes WHERE scene_id IN ({surviving_placeholders}) "
                f"AND id NOT IN ({placeholders})",
                tuple(sorted(retired_scenes)) + tuple(sorted(retired_media)),
            ).fetchall()
            retired_scenes -= {str(r[0]) for r in surviving if r[0]}
        return retired_scenes

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Call local loopback LLM for natural language processing without proxy leakage."""
        llm_config = self.cfg.get("llm", {}) if isinstance(self.cfg, dict) else {}
        api_url = _validate_loopback_llm_url(
            llm_config.get("api_url", "http://localhost:1234/v1/chat/completions")
        )

        session = requests.Session()
        session.trust_env = False
        try:
            response = session.post(
                api_url,
                json={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
        finally:
            session.close()

        return None

    def parse_query_intent(self, query: str) -> Dict[str, Any]:
        """Parse natural language query to determine intent and extract parameters."""
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
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    return json.loads(response[json_start:json_end])
            except Exception as e:
                logger.warning(f"Failed to parse query intent: {e}")

        return {
            "intent": "entity_lookup",
            "entity": None,
            "entity_type": None,
            "scope": "all",
        }

    def entity_lookup(
        self, entity_name: Optional[str] = None, entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Look up active entities in the graph without write authority."""
        conn = self._open_read_conn()
        try:
            retired_media, retired_stats = _retirement_graph_projection(
                conn, Path(self.kg_db_path)
            )
            retired_scenes = self._retired_scene_names(conn, retired_media)

            query = (
                "SELECT id, node_type, name, properties, occurrence_count, first_seen, last_seen "
                "FROM nodes WHERE 1=1"
            )
            params: List[Any] = []

            if entity_name:
                query += " AND name LIKE ?"
                params.append(f"%{entity_name}%")

            if entity_type:
                query += " AND node_type = ?"
                params.append(entity_type)

            query += " ORDER BY occurrence_count DESC"

            results: List[Dict[str, Any]] = []
            for row in conn.execute(query, params):
                projected = _project_node_statistics(row, retired_stats)
                if projected["node_type"] == "scene" and str(projected["name"]) in retired_scenes:
                    continue
                if row["id"] in retired_stats and int(projected["occurrence_count"] or 0) == 0:
                    continue
                props = json.loads(projected["properties"]) if projected["properties"] else {}
                results.append(
                    {
                        "id": projected["id"],
                        "type": projected["node_type"],
                        "name": projected["name"],
                        "properties": props,
                        "occurrences": projected["occurrence_count"],
                        "first_seen": projected["first_seen"],
                        "last_seen": projected["last_seen"],
                    }
                )
            results.sort(key=lambda item: int(item["occurrences"] or 0), reverse=True)
            return results[:20]
        finally:
            conn.close()

    def find_relationships(
        self, entity_name: str, relationship_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find active entities related to the specified entity via read-only traversal."""
        entities = self.entity_lookup(entity_name=entity_name)
        if not entities:
            return []

        root_id = entities[0]["id"]
        conn = self._open_read_conn()
        try:
            retired_media, retired_stats = _retirement_graph_projection(
                conn, Path(self.kg_db_path)
            )
            retired_scenes = self._retired_scene_names(conn, retired_media)

            visited = {root_id}
            queue: deque[tuple[int, int]] = deque([(root_id, 0)])
            related: List[Dict[str, Any]] = []
            max_depth = 2

            while queue:
                current_id, depth = queue.popleft()
                if depth >= max_depth:
                    continue
                edge_sql = (
                    "SELECT source_id, target_id, edge_type, weight FROM edges "
                    "WHERE (source_id = ? OR target_id = ?)"
                )
                edge_params: List[Any] = [current_id, current_id]
                if relationship_type:
                    edge_sql += " AND edge_type = ?"
                    edge_params.append(relationship_type)
                for edge_row in conn.execute(edge_sql, edge_params):
                    neighbor_id = (
                        edge_row["target_id"]
                        if edge_row["source_id"] == current_id
                        else edge_row["source_id"]
                    )
                    if neighbor_id in visited:
                        continue
                    visited.add(neighbor_id)
                    node_row = conn.execute(
                        "SELECT id, node_type, name, properties, occurrence_count, first_seen, last_seen "
                        "FROM nodes WHERE id = ?",
                        (neighbor_id,),
                    ).fetchone()
                    if node_row is None:
                        continue
                    projected = _project_node_statistics(node_row, retired_stats)
                    if projected["node_type"] == "scene" and str(projected["name"]) in retired_scenes:
                        continue
                    if node_row["id"] in retired_stats and int(projected["occurrence_count"] or 0) == 0:
                        continue
                    props = json.loads(projected["properties"]) if projected["properties"] else {}
                    related.append(
                        {
                            "id": projected["id"],
                            "type": projected["node_type"],
                            "name": projected["name"],
                            "edge_type": edge_row["edge_type"],
                            "weight": edge_row["weight"],
                            "depth": depth + 1,
                            "properties": props,
                        }
                    )
                    queue.append((neighbor_id, depth + 1))
            return related
        finally:
            conn.close()

    def temporal_query(
        self, entity_name: Optional[str], operator: str = "after"
    ) -> List[Dict[str, Any]]:
        """Find active events before/after an entity or timestamp."""
        entities = self.entity_lookup(entity_name=entity_name)
        if not entities:
            return []

        conn = self._open_read_conn()
        try:
            retired_media, _retired_stats = _retirement_graph_projection(
                conn, Path(self.kg_db_path)
            )
            retired_scenes = self._retired_scene_names(conn, retired_media)
            retired_clause = (
                f"AND m.id NOT IN ({','.join('?' for _ in retired_media)})"
                if retired_media
                else ""
            )
            retired_params = sorted(retired_media)

            media_rows = conn.execute(
                f"""
                SELECT m.id, m.scene_id, m.timestamp_start, m.timestamp_end, m.media_path
                FROM node_media nm
                JOIN media_nodes m ON m.id = nm.media_id
                WHERE nm.node_id = ? AND m.timestamp_start IS NOT NULL
                {retired_clause}
                ORDER BY m.timestamp_start ASC
                """,
                [entities[0]["id"], *retired_params],
            ).fetchall()
            if not media_rows:
                return []

            timestamp = float(media_rows[0]["timestamp_start"])
            time_window = 60.0
            center = (
                timestamp - time_window / 2.0
                if operator == "before"
                else timestamp + time_window / 2.0
            )
            low = center - time_window / 2.0
            high = center + time_window / 2.0

            neighbor_rows = conn.execute(
                f"""
                SELECT n.id, n.node_type, n.name, m.scene_id, m.timestamp_start AS timestamp
                FROM node_media nm
                JOIN media_nodes m ON m.id = nm.media_id
                JOIN nodes n ON n.id = nm.node_id
                WHERE m.timestamp_start BETWEEN ? AND ?
                {retired_clause}
                ORDER BY m.timestamp_start ASC
                """,
                [low, high, *retired_params],
            ).fetchall()

            events: List[Dict[str, Any]] = []
            for row in neighbor_rows:
                if row["node_type"] == "scene" and str(row["name"]) in retired_scenes:
                    continue
                row_ts = float(row["timestamp"])
                if operator == "before" and not (row_ts < timestamp):
                    continue
                if operator != "before" and not (row_ts > timestamp):
                    continue
                events.append(
                    {
                        "id": row["id"],
                        "type": row["node_type"],
                        "name": row["name"],
                        "scene_id": row["scene_id"],
                        "timestamp": row_ts,
                    }
                )
            return events
        finally:
            conn.close()

    def attribute_query(self, attribute: str) -> List[Dict[str, Any]]:
        """Query by attribute (emotion, sentiment, tag, theme)."""
        type_map = {
            "emotion": "emotion",
            "sentiment": "emotion",
            "tag": "tag",
            "theme": "theme",
            "concept": "concept",
        }

        entity_type = type_map.get(attribute)
        return self.entity_lookup(entity_type=entity_type)

    def get_statistics(self) -> Dict[str, Any]:
        """Compute active graph statistics via read-only connection."""
        conn = self._open_read_conn()
        try:
            retired_media, retired_stats = _retirement_graph_projection(
                conn, Path(self.kg_db_path)
            )
            retired_scenes = self._retired_scene_names(conn, retired_media)

            node_counts: Dict[str, int] = {}
            total_nodes = 0
            for row in conn.execute("SELECT id, node_type, name, occurrence_count FROM nodes"):
                projected = _project_node_statistics(row, retired_stats)
                if projected["node_type"] == "scene" and str(projected["name"]) in retired_scenes:
                    continue
                if row["id"] in retired_stats and int(projected["occurrence_count"] or 0) == 0:
                    continue
                ntype = str(projected["node_type"])
                node_counts[ntype] = node_counts.get(ntype, 0) + 1
                total_nodes += 1

            edge_counts = {
                str(r[0]): int(r[1])
                for r in conn.execute(
                    "SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type"
                ).fetchall()
            }
            retired_clause = (
                f"WHERE id NOT IN ({','.join('?' for _ in retired_media)})"
                if retired_media
                else ""
            )
            media_count = int(
                conn.execute(
                    f"SELECT COUNT(*) FROM media_nodes {retired_clause}",
                    tuple(sorted(retired_media)),
                ).fetchone()[0]
            )
            return {
                "total_nodes": total_nodes,
                "total_edges": sum(edge_counts.values()),
                "media_nodes": media_count,
                "node_counts": node_counts,
                "edge_counts": edge_counts,
            }
        finally:
            conn.close()

    def generate_narrative_response(self, query: str, data: Any) -> str:
        """Generate natural language response from query results using LLM."""
        system_prompt = """You are a helpful assistant that answers questions about video content.
Given raw query results from a knowledge graph, generate a concise, natural language response.
Focus on the most relevant information and present it clearly."""

        data_str = json.dumps(data, indent=2)[:2000]

        user_prompt = f"""Question: {query}

Query Results:
{data_str}

Generate a natural, concise answer based on the query results above."""

        response = self._call_llm(system_prompt, user_prompt)
        return response or "I found some results but couldn't generate a summary."

    def query(self, query: str, return_raw: bool = False) -> str:
        """Main query interface - takes natural language query and returns answer."""
        intent_data = self.parse_query_intent(query)
        intent = intent_data.get("intent", "entity_lookup")

        logger.info(f"Query intent: {intent_data}")

        results: Any = []

        if intent == "entity_lookup":
            results = self.entity_lookup(
                entity_name=intent_data.get("entity"),
                entity_type=intent_data.get("entity_type"),
            )
        elif intent == "relationship":
            results = self.find_relationships(
                entity_name=intent_data.get("entity", ""),
                relationship_type=intent_data.get("relationship_type"),
            )
        elif intent == "temporal":
            results = self.temporal_query(
                entity_name=intent_data.get("entity"),
                operator=intent_data.get("temporal_operator", "after"),
            )
        elif intent == "attribute":
            results = self.attribute_query(
                attribute=intent_data.get("attribute", "tag")
            )
        elif intent == "narrative":
            results = self.get_statistics()

        if return_raw:
            return json.dumps(results, indent=2)

        return self.generate_narrative_response(query, results)

    def close(self) -> None:
        """Close knowledge graph handle (no persistent write handle is held)."""
        return None


def main() -> None:
    """Interactive query interface."""
    cfg = load_configs({})
    kg_path = _resolve_graph_db_path(cfg)

    if not kg_path.exists():
        print(f"[FAIL] Knowledge graph not found at {kg_path}")
        print("Run ingestion first to build the knowledge graph.")
        return

    qi = KnowledgeGraphNLQuery(str(kg_path), cfg)

    print("\n" + "=" * 80)
    print("KNOWLEDGE GRAPH NATURAL LANGUAGE QUERY INTERFACE")
    print("=" * 80)
    print("\nExample queries:")
    print("  - Who appears in the video?")
    print("  - What objects are shown with the person?")
    print("  - What emotions are detected?")
    print("  - What happened after scene 5?")
    print("  - Summarize the video")
    print("\nType 'quit' to exit, 'stats' for statistics")
    print("=" * 80 + "\n")

    while True:
        try:
            query = input("\n[SEARCH] Query: ").strip()

            if not query:
                continue

            if query.lower() in ["quit", "exit", "q"]:
                break

            if query.lower() == "stats":
                stats = qi.get_statistics()
                print("\n" + json.dumps(stats, indent=2))
                continue

            print("\n[SYMBOL] Processing...")
            response = qi.query(query)
            print(f"\n[STATS] Answer:\n{response}\n")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[FAIL] Error: {e}")

    qi.close()
    print("\n[SYMBOL] Goodbye!\n")


if __name__ == "__main__":
    main()
