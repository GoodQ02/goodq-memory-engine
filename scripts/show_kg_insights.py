# -*- coding: utf-8 -*-
import sqlite3
import json
import sys
import io

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

conn = sqlite3.connect('data/knowledge_graph.db')
c = conn.cursor()

print("\n=== LLM-GENERATED INSIGHTS ===\n")

# Emotional Arc
arc = c.execute('SELECT name, properties FROM nodes WHERE node_type="emotional_arc"').fetchone()
if arc:
    print(f"* Emotional Arc: {arc[0]}")
    props = json.loads(arc[1])
    print(f"   Description: {props.get('description', 'N/A')}\n")

# Themes
print("* Themes Identified:")
for row in c.execute('SELECT name FROM nodes WHERE node_type="theme"').fetchall():
    print(f"   - {row[0]}")

# Emotions
print("\n* Emotions Detected:")
for row in c.execute('SELECT name, occurrence_count FROM nodes WHERE node_type="emotion" ORDER BY occurrence_count DESC').fetchall():
    print(f"   - {row[0]} ({row[1]} occurrences)")

# Top Objects
print("\n* Key Objects:")
for row in c.execute('SELECT name, occurrence_count FROM nodes WHERE node_type="object" ORDER BY occurrence_count DESC LIMIT 5').fetchall():
    print(f"   - {row[0]} ({row[1]} appearances)")

# Top Tags
print("\n* Top Tags:")
for row in c.execute('SELECT name, occurrence_count FROM nodes WHERE node_type="tag" ORDER BY occurrence_count DESC LIMIT 5').fetchall():
    print(f"   - {row[0]} ({row[1]} occurrences)")

conn.close()
