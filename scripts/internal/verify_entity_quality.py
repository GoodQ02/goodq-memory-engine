from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from steps.common.config_loader import load_configs


STOPWORDS = {
    "i", "i'm", "you", "you're", "we", "we're", "they", "it's", "that's",
    "what", "well", "yeah", "okay", "why", "how", "look", "but", "and", "the",
}
CANONICAL_NAMES = ("Jerry", "George", "Elaine")


def _resolve_kg_db(args_db_path: str | None) -> Path:
    if args_db_path:
        return Path(args_db_path)
    cfg = load_configs()
    explicit = cfg.get("paths", {}).get("knowledge_graph_db")
    if isinstance(explicit, str) and explicit.strip():
        return Path(explicit)
    data_root = cfg.get("paths", {}).get("data_root")
    if isinstance(data_root, str) and data_root.strip():
        return Path(data_root) / "knowledge_graph.db"
    return Path("data") / "knowledge_graph.db"


def _resolve_memory_db(args_db_path: str | None) -> Path:
    if args_db_path:
        return Path(args_db_path)
    cfg = load_configs()
    explicit = cfg.get("paths", {}).get("db_path")
    if isinstance(explicit, str) and explicit.strip():
        return Path(explicit)
    data_root = cfg.get("paths", {}).get("data_root")
    if isinstance(data_root, str) and data_root.strip():
        return Path(data_root) / "epochs" / "epoch_2025_12_22" / "memory.db"
    return Path("data") / "memory.db"


def _normalize_for_stopword_check(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9']+", "", name.strip().lower())


def _fetch_top_entities(conn: sqlite3.Connection, limit: int = 20) -> List[Dict[str, object]]:
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT name, node_type, occurrence_count
        FROM nodes
        ORDER BY occurrence_count DESC, name ASC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    return [
        {"name": str(row[0]), "node_type": str(row[1]), "occurrence_count": int(row[2] or 0)}
        for row in rows
    ]


def _find_stopword_entities(conn: sqlite3.Connection) -> List[str]:
    cur = conn.cursor()
    rows = cur.execute("SELECT DISTINCT name FROM nodes").fetchall()
    offenders: List[str] = []
    for (name_raw,) in rows:
        if not isinstance(name_raw, str):
            continue
        normalized = _normalize_for_stopword_check(name_raw)
        if normalized in STOPWORDS:
            offenders.append(name_raw)
    return sorted(set(offenders))


def _canonical_name_status(conn: sqlite3.Connection, names: Sequence[str]) -> Dict[str, bool]:
    cur = conn.cursor()
    status: Dict[str, bool] = {}
    for name in names:
        row = cur.execute(
            "SELECT 1 FROM nodes WHERE name = ? COLLATE BINARY LIMIT 1",
            (name,),
        ).fetchone()
        status[name] = row is not None
    return status


def _iter_text_tokens(value: Any) -> Iterable[str]:
    if isinstance(value, str) and value.strip():
        yield value.strip()
        return
    if not isinstance(value, list):
        return
    for item in value:
        if isinstance(item, str) and item.strip():
            yield item.strip()
            continue
        if not isinstance(item, dict):
            continue
        for key in ("name", "label", "text", "tag", "entity", "value"):
            raw = item.get(key)
            if isinstance(raw, str) and raw.strip():
                yield raw.strip()
                break


def _tally_tokens(tokens: Iterable[str], *, limit: int = 20) -> List[Dict[str, object]]:
    counts: Counter[str] = Counter()
    display: Dict[str, str] = {}
    for token in tokens:
        normalized = _normalize_for_stopword_check(token)
        if not normalized:
            continue
        display.setdefault(normalized, str(token).strip())
        counts[normalized] += 1
    rows: List[Dict[str, object]] = []
    for normalized, count in counts.most_common(int(limit)):
        rows.append({"label": display[normalized], "count": int(count)})
    return rows


def _find_stopword_tokens(tokens: Iterable[str]) -> List[str]:
    offenders: List[str] = []
    for token in tokens:
        normalized = _normalize_for_stopword_check(token)
        if normalized in STOPWORDS:
            offenders.append(str(token).strip())
    return sorted(set(offenders))


def _fetch_memory_taxonomy(conn: sqlite3.Connection, limit: int = 100) -> Dict[str, List[str]]:
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT meta
        FROM scenes
        ORDER BY created_at DESC, start DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()

    tags: List[str] = []
    entities: List[str] = []
    for (meta_raw,) in rows:
        if not isinstance(meta_raw, str) or not meta_raw.strip():
            continue
        try:
            meta = json.loads(meta_raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(meta, dict):
            continue
        for source in (meta, meta.get("keyframe"), meta.get("audio")):
            if not isinstance(source, dict):
                continue
            tags.extend(_iter_text_tokens(source.get("tags")))
            entities.extend(_iter_text_tokens(source.get("entities")))
    return {"tags": tags, "entities": entities}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify KG entity quality after stopword and canonicalization fixes.")
    parser.add_argument("--kg-db", dest="kg_db", default=None, help="Optional explicit knowledge_graph.db path")
    parser.add_argument("--memory-db", dest="memory_db", default=None, help="Optional explicit memory.db path")
    args = parser.parse_args()

    kg_db = _resolve_kg_db(args.kg_db).resolve()
    if not kg_db.exists():
        print(f"[ERROR] knowledge_graph.db not found: {kg_db}")
        return 2

    conn = sqlite3.connect(str(kg_db))
    try:
        top_entities = _fetch_top_entities(conn, limit=20)
        stopword_entities = _find_stopword_entities(conn)
        canonical_status = _canonical_name_status(conn, CANONICAL_NAMES)
    finally:
        conn.close()

    memory_db = _resolve_memory_db(args.memory_db).resolve()
    memory_taxonomy: Dict[str, List[str]] = {"tags": [], "entities": []}
    if memory_db.exists():
        memory_conn = sqlite3.connect(str(memory_db))
        try:
            memory_taxonomy = _fetch_memory_taxonomy(memory_conn, limit=100)
        finally:
            memory_conn.close()

    print("Top Entities After Fix:")
    for row in top_entities:
        print(f" - {row['name']} ({row['node_type']}, count={row['occurrence_count']})")

    print("\nStopword Entity Check:")
    if stopword_entities:
        for name in stopword_entities:
            print(f" - [FAIL] stopword entity present: {name}")
    else:
        print(" - [PASS] no configured stopword entities found")

    print("\nCanonical Name Check:")
    for name, exists in canonical_status.items():
        print(f" - {name}: {'present' if exists else 'missing'}")

    print("\nRecent Memory Taxonomy Check:")
    if memory_db.exists():
        top_memory_tags = _tally_tokens(memory_taxonomy["tags"], limit=10)
        top_memory_entities = _tally_tokens(memory_taxonomy["entities"], limit=10)
        tag_stopwords = _find_stopword_tokens(memory_taxonomy["tags"])
        entity_stopwords = _find_stopword_tokens(memory_taxonomy["entities"])

        print(" - Top tags:")
        for row in top_memory_tags:
            print(f"   - {row['label']} (count={row['count']})")
        print(" - Top entities:")
        for row in top_memory_entities:
            print(f"   - {row['label']} (count={row['count']})")

        if tag_stopwords or entity_stopwords:
            print(" - [WARN] semantic leakage detected in stored scene memory")
            if tag_stopwords:
                print(f"   - tag stopwords: {', '.join(tag_stopwords[:10])}")
            if entity_stopwords:
                print(f"   - entity stopwords: {', '.join(entity_stopwords[:10])}")
        else:
            print(" - [PASS] no configured stopword leakage found in recent scene memory")
    else:
        print(f" - [WARN] memory.db not found: {memory_db}")

    has_stopword_leak = bool(stopword_entities)
    missing_canonical = [name for name, exists in canonical_status.items() if not exists]
    if has_stopword_leak or missing_canonical:
        print("\n[RESULT] FAILED quality gates")
        if missing_canonical:
            print(f"Missing canonical names: {', '.join(missing_canonical)}")
        return 1

    print("\n[RESULT] PASSED quality gates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
