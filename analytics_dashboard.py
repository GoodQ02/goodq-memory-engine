"""
GoodQ Analytics Dashboard
Comprehensive visualization and reporting for video analytics
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from collections import Counter, defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalyticsDashboard:
    """Generate comprehensive analytics dashboard"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.memory_db = Path(config['paths']['db_path'])
        self.kg_db = Path(config['paths']['knowledge_graph_db'])
        
    def generate_dashboard(self, output_path: Path):
        """Generate full analytics dashboard as markdown report"""
        logger.info("Generating analytics dashboard...")
        
        sections = []
        
        # Header
        sections.append(self._generate_header())
        
        # Global statistics
        sections.append(self._generate_global_stats())
        
        # Video library overview
        sections.append(self._generate_video_library())
        
        # Emotional analytics
        sections.append(self._generate_emotional_analytics())
        
        # Content discovery
        sections.append(self._generate_content_discovery())
        
        # Knowledge graph insights
        sections.append(self._generate_kg_insights())
        
        # Processing health
        sections.append(self._generate_processing_health())
        
        # Recent activity
        sections.append(self._generate_recent_activity())
        
        # Combine and save
        dashboard_content = '\n\n'.join(sections)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(dashboard_content)
        
        logger.info(f"Dashboard generated: {output_path}")
        return output_path
    
    def _generate_header(self) -> str:
        """Generate dashboard header"""
        now = datetime.now()
        return f"""# GoodQ Analytics Dashboard
**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S')}
**System:** GoodQ Family Memory Archive

---
"""
    
    def _generate_global_stats(self) -> str:
        """Generate global statistics section"""
        lines = ["## Global Statistics"]
        
        try:
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                # Total videos
                cursor.execute("SELECT COUNT(DISTINCT video_hash) FROM scenes")
                total_videos = cursor.fetchone()[0]
                
                # Total scenes
                cursor.execute("SELECT COUNT(*) FROM scenes")
                total_scenes = cursor.fetchone()[0]
                
                # Total duration
                cursor.execute("SELECT SUM(end - start) FROM scenes")
                total_duration = cursor.fetchone()[0] or 0.0
                
                # Total embeddings by modality
                cursor.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality")
                embeddings = dict(cursor.fetchall())
                
                # Total segments
                cursor.execute("SELECT COUNT(*) FROM segments")
                total_segments = cursor.fetchone()[0]
                
                lines.append(f"\n### Processing Summary")
                lines.append(f"- **Total Videos Processed:** {total_videos}")
                lines.append(f"- **Total Scenes:** {total_scenes}")
                lines.append(f"- **Total Duration:** {total_duration/60:.1f} minutes ({total_duration/3600:.2f} hours)")
                lines.append(f"- **Total Speech Segments:** {total_segments}")
                
                lines.append(f"\n### Embeddings Generated")
                for modality, count in embeddings.items():
                    lines.append(f"- **{modality.title()}:** {count:,}")
                
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                # Knowledge graph stats
                cursor.execute("SELECT COUNT(*) FROM nodes")
                total_nodes = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM edges")
                total_edges = cursor.fetchone()[0]
                
                cursor.execute("SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type")
                node_types = dict(cursor.fetchall())
                
                lines.append(f"\n### Knowledge Graph")
                lines.append(f"- **Total Entities:** {total_nodes:,}")
                lines.append(f"- **Total Relationships:** {total_edges:,}")
                lines.append(f"\n**Entity Breakdown:**")
                for node_type, count in sorted(node_types.items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"  - {node_type.title()}: {count}")
                
        except Exception as e:
            lines.append(f"\n*Error generating stats: {e}*")
        
        return '\n'.join(lines)
    
    def _generate_video_library(self) -> str:
        """Generate video library overview"""
        lines = ["## Video Library"]
        
        try:
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                # Get all videos with stats
                cursor.execute("""
                    SELECT 
                        video_hash,
                        COUNT(*) as scene_count,
                        MIN(start) as first_scene,
                        MAX(end) as last_scene,
                        MAX(created_at) as processed_date
                    FROM scenes
                    GROUP BY video_hash
                    ORDER BY processed_date DESC
                    LIMIT 20
                """)
                
                lines.append("\n### Recently Processed Videos")
                lines.append("\n| Video | Scenes | Duration | Processed |")
                lines.append("|-------|--------|----------|-----------|")
                
                for video_hash, scene_count, first, last, processed in cursor.fetchall():
                    duration = (last - first) if last else 0
                    duration_str = f"{duration/60:.1f}min" if duration > 0 else "N/A"
                    processed_date = processed[:10] if processed else "Unknown"
                    
                    lines.append(f"| {video_hash[:30]} | {scene_count} | {duration_str} | {processed_date} |")
                
        except Exception as e:
            lines.append(f"\n*Error: {e}*")
        
        return '\n'.join(lines)
    
    def _generate_emotional_analytics(self) -> str:
        """Generate emotional analytics section"""
        lines = ["## Emotional Analytics"]
        
        try:
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                # Overall sentiment distribution
                cursor.execute("""
                    SELECT sentiment_label, COUNT(*), AVG(sentiment_score)
                    FROM embeddings
                    WHERE sentiment_label IS NOT NULL
                    GROUP BY sentiment_label
                    ORDER BY COUNT(*) DESC
                """)
                
                lines.append("\n### Sentiment Distribution")
                lines.append("\n| Sentiment | Count | Avg Confidence |")
                lines.append("|-----------|-------|----------------|")
                
                for label, count, avg_score in cursor.fetchall():
                    lines.append(f"| {label} | {count} | {avg_score:.3f} |")
                
                # Emotion distribution from JSON
                cursor.execute("""
                    SELECT emotions_json
                    FROM embeddings
                    WHERE emotions_json IS NOT NULL
                """)
                
                emotion_counter = Counter()
                for (emotions_json,) in cursor.fetchall():
                    try:
                        emotions = json.loads(emotions_json)
                        for emotion in emotions:
                            label = emotion.get('label', '')
                            if label:
                                emotion_counter[label] += 1
                    except:
                        pass
                
                if emotion_counter:
                    lines.append("\n### Top Emotions Detected")
                    lines.append("\n| Emotion | Occurrences |")
                    lines.append("|---------|-------------|")
                    
                    for emotion, count in emotion_counter.most_common(10):
                        lines.append(f"| {emotion} | {count} |")
                
        except Exception as e:
            lines.append(f"\n*Error: {e}*")
        
        return '\n'.join(lines)
    
    def _generate_content_discovery(self) -> str:
        """Generate content discovery section"""
        lines = ["## Content Discovery"]
        
        try:
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                # Top objects
                cursor.execute("""
                    SELECT name, occurrence_count
                    FROM nodes
                    WHERE node_type = 'object'
                    ORDER BY occurrence_count DESC
                    LIMIT 15
                """)
                
                lines.append("\n### Most Common Objects")
                lines.append("\n| Object | Appearances |")
                lines.append("|--------|-------------|")
                
                for name, count in cursor.fetchall():
                    lines.append(f"| {name} | {count} |")
                
                # People detected
                cursor.execute("""
                    SELECT name, occurrence_count
                    FROM nodes
                    WHERE node_type = 'person'
                    ORDER BY occurrence_count DESC
                    LIMIT 10
                """)
                
                people = cursor.fetchall()
                if people:
                    lines.append("\n### People Identified")
                    lines.append("\n| Person | Appearances |")
                    lines.append("|--------|-------------|")
                    
                    for name, count in people:
                        lines.append(f"| {name} | {count} |")
                
                # Themes
                cursor.execute("""
                    SELECT name, properties
                    FROM nodes
                    WHERE node_type = 'theme'
                    ORDER BY occurrence_count DESC
                """)
                
                themes = cursor.fetchall()
                if themes:
                    lines.append("\n### Identified Themes")
                    for name, props_json in themes:
                        props = json.loads(props_json) if props_json else {}
                        category = props.get('category', 'general')
                        lines.append(f"- **{name}** ({category})")
                
                # Top tags
                cursor.execute("""
                    SELECT name, occurrence_count
                    FROM nodes
                    WHERE node_type = 'tag'
                    ORDER BY occurrence_count DESC
                    LIMIT 20
                """)
                
                tags = cursor.fetchall()
                if tags:
                    lines.append("\n### Popular Tags")
                    tag_list = [f"{name} ({count})" for name, count in tags]
                    lines.append(", ".join(tag_list))
                
        except Exception as e:
            lines.append(f"\n*Error: {e}*")
        
        return '\n'.join(lines)
    
    def _generate_kg_insights(self) -> str:
        """Generate knowledge graph insights"""
        lines = ["## Knowledge Graph Insights"]
        
        try:
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                # Relationship types
                cursor.execute("""
                    SELECT edge_type, COUNT(*) as count
                    FROM edges
                    GROUP BY edge_type
                    ORDER BY count DESC
                """)
                
                lines.append("\n### Relationship Types")
                lines.append("\n| Relationship | Count |")
                lines.append("|-------------|-------|")
                
                for edge_type, count in cursor.fetchall():
                    lines.append(f"| {edge_type} | {count} |")
                
                # Emotional arcs
                cursor.execute("""
                    SELECT name, properties
                    FROM nodes
                    WHERE node_type = 'emotional_arc'
                """)
                
                arcs = cursor.fetchall()
                if arcs:
                    lines.append("\n### Emotional Arcs (LLM Generated)")
                    for name, props_json in arcs:
                        props = json.loads(props_json) if props_json else {}
                        description = props.get('description', 'N/A')
                        lines.append(f"\n**{name}:**")
                        lines.append(f"> {description}")
                
                # Key moments
                cursor.execute("""
                    SELECT name, properties, first_seen
                    FROM nodes
                    WHERE node_type = 'emotional_moment'
                    ORDER BY first_seen
                    LIMIT 10
                """)
                
                moments = cursor.fetchall()
                if moments:
                    lines.append("\n### Key Emotional Moments")
                    for name, props_json, timestamp in moments:
                        props = json.loads(props_json) if props_json else {}
                        description = props.get('description', 'N/A')
                        significance = props.get('significance', '')
                        lines.append(f"\n**{timestamp:.1f}s:** {description}")
                        if significance:
                            lines.append(f"  - *Significance:* {significance}")
                
                # Turning points
                cursor.execute("""
                    SELECT name, properties
                    FROM nodes
                    WHERE node_type = 'emotional_turning_point'
                    LIMIT 5
                """)
                
                turning_points = cursor.fetchall()
                if turning_points:
                    lines.append("\n### Emotional Turning Points")
                    for name, props_json in turning_points:
                        props = json.loads(props_json) if props_json else {}
                        from_emotion = props.get('from_emotion', '?')
                        to_emotion = props.get('to_emotion', '?')
                        trigger = props.get('trigger', 'N/A')
                        lines.append(f"\n**{name}:**")
                        lines.append(f"  - Shift: {from_emotion} → {to_emotion}")
                        lines.append(f"  - Trigger: {trigger}")
                
        except Exception as e:
            lines.append(f"\n*Error: {e}*")
        
        return '\n'.join(lines)
    
    def _generate_processing_health(self) -> str:
        """Generate processing health metrics"""
        lines = ["## Processing Health"]
        
        try:
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                # Check for workflow executions
                cursor.execute("""
                    SELECT workflow_name, status, COUNT(*) as count
                    FROM workflow_executions
                    GROUP BY workflow_name, status
                    ORDER BY workflow_name, count DESC
                """)
                
                workflows = cursor.fetchall()
                if workflows:
                    lines.append("\n### Workflow Execution Summary")
                    lines.append("\n| Workflow | Status | Count |")
                    lines.append("|----------|--------|-------|")
                    
                    for wf_name, status, count in workflows:
                        lines.append(f"| {wf_name or 'N/A'} | {status} | {count} |")
                
                # Recent completions
                cursor.execute("""
                    SELECT workflow_name, end_time, duration_seconds, steps_completed
                    FROM workflow_executions
                    WHERE status = 'completed'
                    ORDER BY end_time DESC
                    LIMIT 5
                """)
                
                recent = cursor.fetchall()
                if recent:
                    lines.append("\n### Recent Successful Runs")
                    lines.append("\n| Workflow | Completed | Duration | Steps |")
                    lines.append("|----------|-----------|----------|-------|")
                    
                    for wf_name, end_time, duration, steps in recent:
                        end_str = end_time[:19] if end_time else "N/A"
                        dur_str = f"{duration:.1f}s" if duration else "N/A"
                        lines.append(f"| {wf_name or 'N/A'} | {end_str} | {dur_str} | {steps or 0} |")
                
        except Exception as e:
            lines.append(f"\n*Error: {e}*")
        
        return '\n'.join(lines)
    
    def _generate_recent_activity(self) -> str:
        """Generate recent activity section"""
        lines = ["## Recent Activity"]
        
        try:
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                # Recent embeddings
                cursor.execute("""
                    SELECT modality, source_path, created_at
                    FROM embeddings
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                
                lines.append("\n### Latest Processed Content")
                lines.append("\n| Type | Source | Processed |")
                lines.append("|------|--------|-----------|")
                
                for modality, source, created in cursor.fetchall():
                    source_short = Path(source).name if source else "N/A"
                    created_str = created[:19] if created else "Unknown"
                    lines.append(f"| {modality} | {source_short[:40]} | {created_str} |")
                
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                # Recently added nodes
                cursor.execute("""
                    SELECT node_type, name, created_at
                    FROM nodes
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                
                lines.append("\n### Recent Knowledge Graph Additions")
                lines.append("\n| Type | Entity | Added |")
                lines.append("|------|--------|-------|")
                
                for node_type, name, created in cursor.fetchall():
                    created_str = created[:19] if created else "Unknown"
                    lines.append(f"| {node_type} | {name[:40]} | {created_str} |")
                
        except Exception as e:
            lines.append(f"\n*Error: {e}*")
        
        return '\n'.join(lines)


def generate_video_report(config: Dict[str, Any], video_path: str, output_dir: Path):
    """Generate detailed report for a specific video"""
    from analytics_engine import AnalyticsEngine, export_markdown_report, export_report_to_file
    
    logger.info(f"Generating report for: {video_path}")
    
    engine = AnalyticsEngine(config)
    report = engine.generate_comprehensive_report(video_path)
    
    # Export both JSON and Markdown
    video_name = Path(video_path).stem
    json_path = output_dir / f"{video_name}_analytics.json"
    md_path = output_dir / f"{video_name}_analytics.md"
    
    export_report_to_file(report, json_path)
    export_markdown_report(report, md_path)
    
    logger.info(f"Report generated: {md_path}")
    return report


if __name__ == "__main__":
    import yaml
    import sys
    
    # Load config
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    output_dir = Path(config['paths']['output_directory'])
    output_dir.mkdir(exist_ok=True, parents=True)
    
    if len(sys.argv) > 1 and sys.argv[1] != "--dashboard":
        # Generate report for specific video
        video_path = sys.argv[1]
        generate_video_report(config, video_path, output_dir)
    else:
        # Generate dashboard
        dashboard = AnalyticsDashboard(config)
        dashboard_path = output_dir / "analytics_dashboard.md"
        dashboard.generate_dashboard(dashboard_path)
        print(f"\nDashboard generated: {dashboard_path}")
