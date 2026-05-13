# GoodQ Analytics Quick Reference Guide

> Role: Active quick reference for the analytics sidecar (dashboards, queries, and configuration). This is not the canonical runtime authority for ingest, retrieval, or system status. For historical web analytics pages, see `docs/ANALYTICS_PAGES_COMPLETE.md`; for related scripts and reports, see `docs/ANALYTICS_INDEX.md`.

## Overview
The GoodQ Analytics system provides comprehensive insights into your video library through multi-modal analysis, LLM-powered insights, and interactive querying.

Current truth:
- analytics is a secondary reporting/inspection stack
- it can be useful for summaries, dashboards, and exploratory querying
- it should not be treated as the source of truth over persisted runtime artifacts, API runtime surfaces, or witness outputs

## Quick Start

### 1. Generate Global Dashboard
```bash
python scripts/analytics_cli.py dashboard
```
**Output:** `output/analytics_dashboard.md`
**Shows:** Global statistics, library overview, emotional trends, content summary

### 2. Analyze Specific Video
```bash
python scripts/analytics_cli.py analyze "path/to/video.mp4"
```
**Output:** 
- `output/[video]_analytics.json` (machine-readable)
- `output/[video]_analytics.md` (human-readable)

### 3. Interactive Query Session
```bash
python scripts/analytics_cli.py query --interactive
```
**Usage:** Ask natural language questions about your videos

## Query Examples

### Emotional Queries
- "What emotions are in the video?"
- "Show me the emotional arc"
- "When does the mood change?"
- "What are the key emotional moments?"

### Content Queries
- "What objects appear most often?"
- "Who is in the video?"
- "What themes are present?"
- "Show me all the people"

### Temporal Queries
- "When does the action happen?"
- "Show me the timeline"
- "How long is each scene?"
- "When does each person speak?"

### Relationship Queries
- "What relationships exist?"
- "Which entities co-occur?"
- "Show me interactions"
- "What connects these people?"

### Search Queries
- "Find scenes with music"
- "Search for bottle"
- "Show me moments with laughter"
- "Find all instances of person_0"

## Programmatic Usage

### Python API

```python
import yaml
from analytics_engine import AnalyticsEngine
from analytics_query import AnalyticsQuery
from analytics_dashboard import AnalyticsDashboard

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Generate comprehensive report
engine = AnalyticsEngine(config)
report = engine.generate_comprehensive_report('path/to/video.mp4')

# Access report data
summary = report['summary']
emotional = report['emotional_analysis']
content = report['content_analysis']
insights = report['key_insights']

# Query system
query_engine = AnalyticsQuery(config)
result = query_engine.query("What emotions are present?", video_path="video.mp4")
print(result['answer'])

# Generate dashboard
dashboard = AnalyticsDashboard(config)
dashboard.generate_dashboard(Path('output/dashboard.md'))
```

## Report Structure

### Comprehensive Analytics Report

```
{
  "video_path": "...",
  "generated_at": "...",
  "summary": {
    "total_scenes": int,
    "total_duration": float,
    "modalities_processed": [str],
    "embedding_counts": {modality: count},
    "entities_detected": int
  },
  "emotional_analysis": {
    "overall_sentiment": {label: {count, confidence}},
    "emotion_distribution": {emotion: count},
    "sentiment_timeline": [{time, sentiment, score}],
    "dominant_emotions": [{emotion, count}],
    "llm_emotional_arc": str
  },
  "content_analysis": {
    "objects": [{name, occurrences, properties}],
    "people": [{name, occurrences, properties}],
    "themes": [{name, properties}],
    "key_moments": [{name, time, properties}]
  },
  "temporal_analysis": {
    "scene_durations": [{start, end, duration}],
    "speaker_timeline": [{start, end, speaker}],
    "turning_points": [{time, properties}]
  },
  "relationship_networks": {
    "entity_co_occurrences": [{entity1, entity2, relationship, strength}],
    "relationship_types": {type: count}
  },
  "key_insights": [
    {
      "insight": str,
      "significance": str,
      "evidence": str
    }
  ],
  "recommendations": [str]
}
```

## Database Queries

### Direct Database Access

```python
import sqlite3
import os
from pathlib import Path

epoch = "<epoch>"
epoch_root = Path(os.environ["GOODQ_DATA_ROOT"]) / "GoodQ_Data" / "epochs" / epoch

# Memory database
conn = sqlite3.connect(epoch_root / 'memory.db')
cursor = conn.cursor()

# Get all videos
cursor.execute("SELECT DISTINCT video_hash FROM scenes")
videos = cursor.fetchall()

# Get scene info
cursor.execute("""
    SELECT id, start, end, meta 
    FROM scenes 
    WHERE video_hash = ?
    ORDER BY start
""", (video_hash,))
scenes = cursor.fetchall()

# Get embeddings by modality
cursor.execute("""
    SELECT modality, COUNT(*) 
    FROM embeddings 
    GROUP BY modality
""")
embeddings = cursor.fetchall()

conn.close()

# Knowledge graph database
conn = sqlite3.connect(epoch_root / 'knowledge_graph.db')
cursor = conn.cursor()

# Get all entities
cursor.execute("""
    SELECT node_type, name, occurrence_count 
    FROM nodes 
    ORDER BY occurrence_count DESC
""")
entities = cursor.fetchall()

# Get relationships
cursor.execute("""
    SELECT n1.name, e.edge_type, n2.name, e.weight
    FROM edges e
    JOIN nodes n1 ON e.source_id = n1.id
    JOIN nodes n2 ON e.target_id = n2.id
    ORDER BY e.weight DESC
    LIMIT 100
""")
relationships = cursor.fetchall()

conn.close()
```

## Configuration

### Enable/Disable Analytics Features

Edit `config.yaml`:

```yaml
llm:
  enabled: true  # Enable LLM-powered analytics
  features:
    scene_summarization: true
    video_summarization: true
    relationship_extraction: true
    emotion_arc_analysis: true  # Enable emotional arc analysis
  temperature: 0.3
  max_tokens: 200
  timeout: 30
```

## Output Locations

### Default Paths
- **Dashboard:** `output/analytics_dashboard.md`
- **Video Reports:** `output/[video]_analytics.json` and `.md`
- **Logs:** `logs/analytics.log`

### Custom Output
```python
from pathlib import Path

# Custom output directory
output_dir = Path('custom/output/path')
output_dir.mkdir(exist_ok=True, parents=True)

# Export to custom location
export_report_to_file(report, output_dir / 'my_report.json')
export_markdown_report(report, output_dir / 'my_report.md')
```

## Performance Tips

### Optimize for Large Libraries
1. **Use specific video queries** instead of querying all videos
2. **Limit result sets** with pagination
3. **Cache frequently accessed data**
4. **Run analytics during off-hours** for resource-intensive operations

### LLM Timeout Adjustment
For complex analyses, increase timeout in `config.yaml`:
```yaml
llm:
  timeout: 60  # Increase for longer videos
```

### Database Optimization
```python
# Add indexes for frequent queries
cursor.execute("CREATE INDEX IF NOT EXISTS idx_custom ON table(column)")
```

## Troubleshooting

### Common Issues

**No data found:**
- Check video has been processed through pipeline
- Verify video hash in database
- Ensure LLM server is running (if using LLM features)

**Slow queries:**
- Check database indexes
- Reduce result set size
- Optimize query conditions

**LLM timeouts:**
- Increase timeout in config
- Reduce prompt size
- Check LLM server performance

**Missing insights:**
- Verify `llm.enabled: true` in config
- Check LLM server at `http://localhost:1234`
- Review LLM logs for errors

## Advanced Features

### Custom Insight Generation

```python
def custom_insight_analyzer(report):
    """Generate custom insights"""
    # Access report data
    emotions = report['emotional_analysis']['dominant_emotions']
    objects = report['content_analysis']['objects']
    
    # Generate custom insights
    insights = []
    if emotions:
        top_emotion = emotions[0]['emotion']
        insights.append(f"Dominant emotion: {top_emotion}")
    
    if objects:
        top_object = objects[0]['name']
        count = objects[0]['occurrences']
        insights.append(f"Most frequent object: {top_object} ({count} times)")
    
    return insights
```

### Batch Processing

```python
import sqlite3
import os
from pathlib import Path

epoch = "<epoch>"
epoch_root = Path(os.environ["GOODQ_DATA_ROOT"]) / "GoodQ_Data" / "epochs" / epoch

# Get all videos
conn = sqlite3.connect(epoch_root / 'memory.db')
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT video_hash FROM scenes")
video_hashes = [row[0] for row in cursor.fetchall()]
conn.close()

# Process all videos
for video_hash in video_hashes:
    print(f"Processing {video_hash}...")
    report = engine.generate_comprehensive_report(video_hash)
    
    output_path = Path(f'output/{video_hash}_analytics.json')
    export_report_to_file(report, output_path)
    print(f"  Saved: {output_path}")
```

### Export to CSV

```python
import csv
import json

# Export entities to CSV
with open('output/entities.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Type', 'Name', 'Occurrences'])
    
    for entity in report['content_analysis']['objects']:
        writer.writerow([
            'object',
            entity['name'],
            entity['occurrences']
        ])
```

## Best Practices

1. **Generate dashboards regularly** to track processing progress
2. **Use specific queries** for targeted insights
3. **Export important reports** in both JSON and Markdown
4. **Review LLM insights** for quality and accuracy
5. **Monitor processing health** through dashboard
6. **Back up analytics data** along with databases

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review `PHASE7_ANALYTICS_COMPLETE.md` for details
3. Test with `test_phase7_analytics.py`
4. Verify configuration in `config.yaml`

---

**Analytics System Version:** 1.0
**Last Updated:** 2025-11-08
**Status:** Functional secondary tooling; not canonical runtime authority
