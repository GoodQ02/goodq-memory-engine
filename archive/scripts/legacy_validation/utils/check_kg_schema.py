#!/usr/bin/env python3
"""Check knowledge graph database schema and content."""

import sqlite3
import json
import os

kg_path = "L:\\goodq4all\\data\\knowledge_graph.db"

if not os.path.exists(kg_path):
    print(f"KNOWLEDGE GRAPH DATABASE DOES NOT EXIST: {kg_path}")
    exit(1)

print(f"Knowledge Graph Database exists: {kg_path}")
print(f"Size: {os.path.getsize(kg_path) / 1024:.2f} KB\n")

conn = sqlite3.connect(kg_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all tables
tables = cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()

print(f"=== TABLES IN KNOWLEDGE GRAPH ({len(tables)}) ===\n")
for table_row in tables:
    table_name = table_row['name']
    print(f"  {table_name}")
    
    # Get row count
    try:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"    Rows: {count}")
    except Exception as e:
        print(f"    Error counting: {e}")
    
    # Get schema
    schema = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    print(f"    Columns:")
    for col in schema:
        print(f"      {col['name']} ({col['type']})")
    
    # Show sample data for key tables
    if count > 0 and count < 100:
        if table_name in ['nodes', 'media_nodes', 'edges', 'temporal_events']:
            print(f"    Sample data (first 5):")
            rows = cursor.execute(f"SELECT * FROM {table_name} LIMIT 5").fetchall()
            for row in rows:
                row_dict = dict(row)
                # Truncate long fields
                for key in row_dict:
                    if isinstance(row_dict[key], str) and len(row_dict[key]) > 100:
                        row_dict[key] = row_dict[key][:100] + "..."
                print(f"      {row_dict}")
    print()

# Check for sample.mp4 data
print("=== CHECKING FOR sample.mp4 DATA ===\n")
sample_media = cursor.execute(
    "SELECT * FROM media_nodes WHERE media_path LIKE '%sample.mp4%'"
).fetchall()
print(f"Media nodes for sample.mp4: {len(sample_media)}")
if sample_media:
    for media in sample_media[:3]:
        print(f"  {dict(media)}")

# Count nodes by type
print("\n=== NODE TYPES ===")
node_types = cursor.execute(
    "SELECT node_type, COUNT(*) as count FROM nodes GROUP BY node_type ORDER BY count DESC"
).fetchall()
for row in node_types:
    print(f"  {row['node_type']}: {row['count']}")

# Count edges by type
print("\n=== EDGE TYPES ===")
edge_types = cursor.execute(
    "SELECT edge_type, COUNT(*) as count FROM edges GROUP BY edge_type ORDER BY count DESC"
).fetchall()
for row in edge_types:
    print(f"  {row['edge_type']}: {row['count']}")

conn.close()
