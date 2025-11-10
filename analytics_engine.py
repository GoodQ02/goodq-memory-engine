"""
GoodQ Analytics Engine - Phase 7
Comprehensive analytics for multi-modal video analysis with LLM-powered insights
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import requests
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Main analytics engine for GoodQ pipeline"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.memory_db = Path(config['paths']['db_path'])
        self.kg_db = Path(config['paths']['knowledge_graph_db'])
        self.llm_config = config.get('llm', {})
        self.llm_enabled = self.llm_config.get('enabled', False)
        
    def generate_comprehensive_report(self, video_path: str) -> Dict[str, Any]:
        """
        Generate comprehensive analytics report for a video
        
        Returns detailed insights across all modalities with LLM enrichment
        """
        logger.info(f"Generating comprehensive analytics for: {video_path}")
        
        report = {
            'video_path': video_path,
            'generated_at': datetime.now().isoformat(),
            'summary': {},
            'emotional_analysis': {},
            'content_analysis': {},
            'temporal_analysis': {},
            'relationship_networks': {},
            'key_insights': [],
            'recommendations': []
        }
        
        try:
            # Get basic statistics
            report['summary'] = self._get_summary_stats(video_path)
            
            # Emotional journey analysis
            report['emotional_analysis'] = self._analyze_emotional_journey(video_path)
            
            # Content analysis (objects, people, themes)
            report['content_analysis'] = self._analyze_content(video_path)
            
            # Temporal patterns
            report['temporal_analysis'] = self._analyze_temporal_patterns(video_path)
            
            # Relationship networks
            report['relationship_networks'] = self._analyze_relationships(video_path)
            
            # LLM-powered synthesis
            if self.llm_enabled:
                report['key_insights'] = self._generate_llm_insights(report)
                report['recommendations'] = self._generate_recommendations(report)
            
            logger.info(f"Analytics report generated with {len(report['key_insights'])} insights")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate analytics report: {e}", exc_info=True)
            report['error'] = str(e)
            return report
    
    def _get_summary_stats(self, video_path: str) -> Dict[str, Any]:
        """Get basic statistics about the video processing"""
        stats = {
            'total_scenes': 0,
            'total_duration': 0.0,
            'modalities_processed': [],
            'embedding_counts': {},
            'entities_detected': 0,
            'processing_metadata': {}
        }
        
        try:
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                # Get video hash
                video_hash = Path(video_path).stem
                
                # Scene count
                cursor.execute("SELECT COUNT(*) FROM scenes WHERE video_hash=?", (video_hash,))
                stats['total_scenes'] = cursor.fetchone()[0]
                
                # Duration
                cursor.execute("""
                    SELECT MAX(end) - MIN(start) 
                    FROM scenes 
                    WHERE video_hash=?
                """, (video_hash,))
                result = cursor.fetchone()
                stats['total_duration'] = result[0] if result[0] else 0.0
                
                # Modalities
                cursor.execute("""
                    SELECT modality, COUNT(*) 
                    FROM embeddings 
                    WHERE source_path LIKE ?
                    GROUP BY modality
                """, (f"%{video_hash}%",))
                for modality, count in cursor.fetchall():
                    stats['modalities_processed'].append(modality)
                    stats['embedding_counts'][modality] = count
                
            # Knowledge graph entities
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(DISTINCT n.id)
                    FROM nodes n
                    JOIN node_media nm ON n.id = nm.node_id
                    JOIN media_nodes m ON nm.media_id = m.id
                    WHERE m.media_path LIKE ?
                """, (f"%{video_hash}%",))
                stats['entities_detected'] = cursor.fetchone()[0]
                
        except Exception as e:
            logger.error(f"Error getting summary stats: {e}")
            
        return stats
    
    def _analyze_emotional_journey(self, video_path: str) -> Dict[str, Any]:
        """Analyze emotional arc and patterns"""
        analysis = {
            'overall_sentiment': {},
            'emotion_distribution': {},
            'emotional_peaks': [],
            'sentiment_timeline': [],
            'dominant_emotions': []
        }
        
        try:
            video_hash = Path(video_path).stem
            
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                # Get sentiment distribution
                cursor.execute("""
                    SELECT sentiment_label, COUNT(*), AVG(sentiment_score)
                    FROM embeddings
                    WHERE source_path LIKE ? AND sentiment_label IS NOT NULL
                    GROUP BY sentiment_label
                """, (f"%{video_hash}%",))
                
                sentiment_counts = {}
                for label, count, avg_score in cursor.fetchall():
                    sentiment_counts[label] = {
                        'count': count,
                        'average_confidence': round(avg_score, 3)
                    }
                
                analysis['overall_sentiment'] = sentiment_counts
                
                # Get emotion distribution from scenes
                cursor.execute("""
                    SELECT s.id, s.start, s.end, s.meta
                    FROM scenes s
                    WHERE s.video_hash = ?
                    ORDER BY s.start
                """, (video_hash,))
                
                emotions_counter = Counter()
                timeline = []
                
                for scene_id, start, end, meta_json in cursor.fetchall():
                    if meta_json:
                        meta = json.loads(meta_json)
                        emotions = meta.get('emotions', [])
                        sentiment = meta.get('sentiment', {})
                        
                        # Track timeline
                        if sentiment:
                            timeline.append({
                                'time': start,
                                'sentiment': sentiment.get('label', 'NEUTRAL'),
                                'score': sentiment.get('score', 0.5)
                            })
                        
                        # Count emotions
                        for emotion in emotions:
                            emotion_label = emotion.get('label', '')
                            if emotion_label:
                                emotions_counter[emotion_label] += 1
                
                analysis['emotion_distribution'] = dict(emotions_counter)
                analysis['sentiment_timeline'] = timeline
                analysis['dominant_emotions'] = [
                    {'emotion': e, 'count': c} 
                    for e, c in emotions_counter.most_common(5)
                ]
                
            # Get LLM-generated emotional arc from KG
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT n.name, n.properties
                    FROM nodes n
                    JOIN node_media nm ON n.id = nm.node_id
                    JOIN media_nodes m ON nm.media_id = m.id
                    WHERE n.node_type = 'emotional_arc' 
                    AND m.media_path LIKE ?
                """, (f"%{video_hash}%",))
                
                arc_data = cursor.fetchone()
                if arc_data:
                    props = json.loads(arc_data[1])
                    analysis['llm_emotional_arc'] = props.get('description', '')
                    
        except Exception as e:
            logger.error(f"Error analyzing emotional journey: {e}")
            
        return analysis
    
    def _analyze_content(self, video_path: str) -> Dict[str, Any]:
        """Analyze content: objects, people, themes, concepts"""
        analysis = {
            'objects': [],
            'people': [],
            'themes': [],
            'concepts': [],
            'locations': [],
            'key_moments': []
        }
        
        try:
            video_hash = Path(video_path).stem
            
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                # Get top objects
                cursor.execute("""
                    SELECT n.name, n.occurrence_count, n.properties
                    FROM nodes n
                    JOIN node_media nm ON n.id = nm.node_id
                    JOIN media_nodes m ON nm.media_id = m.id
                    WHERE n.node_type = 'object'
                    AND m.media_path LIKE ?
                    GROUP BY n.id
                    ORDER BY n.occurrence_count DESC
                    LIMIT 10
                """, (f"%{video_hash}%",))
                
                analysis['objects'] = [
                    {
                        'name': name,
                        'occurrences': count,
                        'properties': json.loads(props) if props else {}
                    }
                    for name, count, props in cursor.fetchall()
                ]
                
                # Get people
                cursor.execute("""
                    SELECT n.name, n.occurrence_count, n.properties
                    FROM nodes n
                    JOIN node_media nm ON n.id = nm.node_id
                    JOIN media_nodes m ON nm.media_id = m.id
                    WHERE n.node_type = 'person'
                    AND m.media_path LIKE ?
                    GROUP BY n.id
                    ORDER BY n.occurrence_count DESC
                """, (f"%{video_hash}%",))
                
                analysis['people'] = [
                    {
                        'name': name,
                        'occurrences': count,
                        'properties': json.loads(props) if props else {}
                    }
                    for name, count, props in cursor.fetchall()
                ]
                
                # Get themes
                cursor.execute("""
                    SELECT n.name, n.properties
                    FROM nodes n
                    JOIN node_media nm ON n.id = nm.node_id
                    JOIN media_nodes m ON nm.media_id = m.id
                    WHERE n.node_type = 'theme'
                    AND m.media_path LIKE ?
                    GROUP BY n.id
                """, (f"%{video_hash}%",))
                
                analysis['themes'] = [
                    {
                        'name': name,
                        'properties': json.loads(props) if props else {}
                    }
                    for name, props in cursor.fetchall()
                ]
                
                # Get key moments
                cursor.execute("""
                    SELECT n.name, n.properties, n.first_seen
                    FROM nodes n
                    JOIN node_media nm ON n.id = nm.node_id
                    JOIN media_nodes m ON nm.media_id = m.id
                    WHERE n.node_type = 'emotional_moment'
                    AND m.media_path LIKE ?
                    ORDER BY n.first_seen
                """, (f"%{video_hash}%",))
                
                analysis['key_moments'] = [
                    {
                        'name': name,
                        'time': timestamp,
                        'properties': json.loads(props) if props else {}
                    }
                    for name, props, timestamp in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Error analyzing content: {e}")
            
        return analysis
    
    def _analyze_temporal_patterns(self, video_path: str) -> Dict[str, Any]:
        """Analyze temporal patterns and events"""
        analysis = {
            'scene_durations': [],
            'activity_density': [],
            'speaker_timeline': [],
            'turning_points': []
        }
        
        try:
            video_hash = Path(video_path).stem
            
            with sqlite3.connect(self.memory_db) as conn:
                cursor = conn.cursor()
                
                # Scene durations
                cursor.execute("""
                    SELECT start, end, (end - start) as duration
                    FROM scenes
                    WHERE video_hash = ?
                    ORDER BY start
                """, (video_hash,))
                
                analysis['scene_durations'] = [
                    {'start': s, 'end': e, 'duration': d}
                    for s, e, d in cursor.fetchall()
                ]
                
                # Speaker timeline
                cursor.execute("""
                    SELECT start, end, speaker
                    FROM segments
                    WHERE video_hash = ?
                    ORDER BY start
                """, (video_hash,))
                
                analysis['speaker_timeline'] = [
                    {'start': s, 'end': e, 'speaker': spk}
                    for s, e, spk in cursor.fetchall()
                ]
                
            # Turning points from KG
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT n.name, n.properties, n.first_seen
                    FROM nodes n
                    JOIN node_media nm ON n.id = nm.node_id
                    JOIN media_nodes m ON nm.media_id = m.id
                    WHERE n.node_type = 'emotional_turning_point'
                    AND m.media_path LIKE ?
                    ORDER BY n.first_seen
                """, (f"%{video_hash}%",))
                
                analysis['turning_points'] = [
                    {
                        'time': timestamp,
                        'properties': json.loads(props) if props else {}
                    }
                    for name, props, timestamp in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Error analyzing temporal patterns: {e}")
            
        return analysis
    
    def _analyze_relationships(self, video_path: str) -> Dict[str, Any]:
        """Analyze entity relationships and co-occurrences"""
        analysis = {
            'entity_co_occurrences': [],
            'relationship_types': {},
            'interaction_graph': {}
        }
        
        try:
            video_hash = Path(video_path).stem
            
            with sqlite3.connect(self.kg_db) as conn:
                cursor = conn.cursor()
                
                # Get relationship types and counts
                cursor.execute("""
                    SELECT e.edge_type, COUNT(*) as count
                    FROM edges e
                    JOIN nodes n1 ON e.source_id = n1.id
                    JOIN node_media nm ON n1.id = nm.node_id
                    JOIN media_nodes m ON nm.media_id = m.id
                    WHERE m.media_path LIKE ?
                    GROUP BY e.edge_type
                    ORDER BY count DESC
                """, (f"%{video_hash}%",))
                
                analysis['relationship_types'] = {
                    edge_type: count
                    for edge_type, count in cursor.fetchall()
                }
                
                # Get top co-occurrences
                cursor.execute("""
                    SELECT n1.name, n1.node_type, n2.name, n2.node_type, e.weight, e.edge_type
                    FROM edges e
                    JOIN nodes n1 ON e.source_id = n1.id
                    JOIN nodes n2 ON e.target_id = n2.id
                    JOIN node_media nm ON n1.id = nm.node_id
                    JOIN media_nodes m ON nm.media_id = m.id
                    WHERE m.media_path LIKE ?
                    ORDER BY e.weight DESC
                    LIMIT 20
                """, (f"%{video_hash}%",))
                
                analysis['entity_co_occurrences'] = [
                    {
                        'entity1': {'name': n1, 'type': t1},
                        'entity2': {'name': n2, 'type': t2},
                        'relationship': edge_type,
                        'strength': weight
                    }
                    for n1, t1, n2, t2, weight, edge_type in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Error analyzing relationships: {e}")
            
        return analysis
    
    def _generate_llm_insights(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use LLM to generate high-level insights from analytics"""
        if not self.llm_enabled:
            return []
        
        insights = []
        
        try:
            # Prepare summary for LLM
            summary_text = self._prepare_report_summary(report)
            
            prompt = f"""Analyze this video analytics report and provide 3-5 key insights:

{summary_text}

Provide insights in JSON format:
[
  {{
    "insight": "brief description",
    "significance": "why this matters",
    "evidence": "what supports this"
  }}
]

Focus on:
- Emotional patterns and narrative arc
- Relationships between people/objects
- Key moments and turning points
- Thematic elements
- Overall story or message"""

            api_url = self.llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
            
            response = requests.post(
                api_url,
                json={
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert video analyst. Provide deep, meaningful insights from multi-modal video analytics. Return valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.5,
                    "max_tokens": 500,
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                insights = self._parse_json_response(content)
                if isinstance(insights, list):
                    logger.info(f"Generated {len(insights)} LLM insights")
                    return insights
                    
        except Exception as e:
            logger.error(f"Error generating LLM insights: {e}")
            
        return []
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analytics"""
        recommendations = []
        
        summary = report.get('summary', {})
        emotional = report.get('emotional_analysis', {})
        content = report.get('content_analysis', {})
        
        # Check data quality
        if summary.get('total_scenes', 0) < 5:
            recommendations.append("Consider longer videos for better emotional arc analysis")
        
        # Check modality coverage
        modalities = summary.get('modalities_processed', [])
        if 'audio' not in modalities:
            recommendations.append("Audio transcription would enhance understanding")
        if 'image' not in modalities:
            recommendations.append("Visual analysis would provide richer context")
        
        # Check emotional diversity
        emotions = emotional.get('emotion_distribution', {})
        if len(emotions) < 2:
            recommendations.append("Limited emotional range detected - consider more varied content")
        
        # Check entity richness
        if summary.get('entities_detected', 0) < 10:
            recommendations.append("More entity detection could provide deeper insights")
        
        return recommendations
    
    def _prepare_report_summary(self, report: Dict[str, Any]) -> str:
        """Prepare concise summary for LLM processing"""
        lines = []
        
        summary = report.get('summary', {})
        lines.append(f"SCENES: {summary.get('total_scenes', 0)}")
        lines.append(f"DURATION: {summary.get('total_duration', 0):.1f}s")
        lines.append(f"ENTITIES: {summary.get('entities_detected', 0)}")
        
        emotional = report.get('emotional_analysis', {})
        if emotional.get('dominant_emotions'):
            top_emotions = [e['emotion'] for e in emotional['dominant_emotions'][:3]]
            lines.append(f"TOP EMOTIONS: {', '.join(top_emotions)}")
        
        if emotional.get('llm_emotional_arc'):
            lines.append(f"EMOTIONAL ARC: {emotional['llm_emotional_arc'][:200]}")
        
        content = report.get('content_analysis', {})
        if content.get('objects'):
            top_objects = [o['name'] for o in content['objects'][:5]]
            lines.append(f"KEY OBJECTS: {', '.join(top_objects)}")
        
        if content.get('themes'):
            themes = [t['name'] for t in content['themes'][:3]]
            lines.append(f"THEMES: {', '.join(themes)}")
        
        return "\n".join(lines)
    
    def _parse_json_response(self, content: str) -> Any:
        """Parse JSON from LLM response"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract from markdown
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                if end > start:
                    try:
                        return json.loads(content[start:end].strip())
                    except:
                        pass
            
            # Try to find JSON boundaries
            start = content.find('[')
            if start < 0:
                start = content.find('{')
            end = max(content.rfind(']'), content.rfind('}')) + 1
            
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end])
                except:
                    pass
        
        return None


def export_report_to_file(report: Dict[str, Any], output_path: Path):
    """Export analytics report to JSON file"""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Report exported to: {output_path}")
    except Exception as e:
        logger.error(f"Failed to export report: {e}")


def export_markdown_report(report: Dict[str, Any], output_path: Path):
    """Export analytics report as readable markdown"""
    try:
        lines = []
        lines.append(f"# Video Analytics Report")
        lines.append(f"\n**Video:** `{report['video_path']}`")
        lines.append(f"**Generated:** {report['generated_at']}\n")
        
        # Summary
        summary = report.get('summary', {})
        lines.append("## Summary")
        lines.append(f"- Total Scenes: {summary.get('total_scenes', 0)}")
        lines.append(f"- Duration: {summary.get('total_duration', 0):.1f}s")
        lines.append(f"- Entities Detected: {summary.get('entities_detected', 0)}")
        lines.append(f"- Modalities: {', '.join(summary.get('modalities_processed', []))}")
        
        # Emotional Analysis
        emotional = report.get('emotional_analysis', {})
        if emotional:
            lines.append("\n## Emotional Analysis")
            
            if emotional.get('llm_emotional_arc'):
                lines.append(f"\n**Arc:** {emotional['llm_emotional_arc']}")
            
            if emotional.get('dominant_emotions'):
                lines.append("\n**Dominant Emotions:**")
                for e in emotional['dominant_emotions']:
                    lines.append(f"- {e['emotion']}: {e['count']} occurrences")
        
        # Content Analysis
        content = report.get('content_analysis', {})
        if content:
            lines.append("\n## Content Analysis")
            
            if content.get('objects'):
                lines.append("\n**Key Objects:**")
                for obj in content['objects'][:10]:
                    lines.append(f"- {obj['name']} ({obj['occurrences']} times)")
            
            if content.get('themes'):
                lines.append("\n**Themes:**")
                for theme in content['themes']:
                    lines.append(f"- {theme['name']}")
            
            if content.get('key_moments'):
                lines.append("\n**Key Moments:**")
                for moment in content['key_moments']:
                    props = moment['properties']
                    lines.append(f"- **{moment['time']:.1f}s:** {props.get('description', 'N/A')}")
        
        # Key Insights
        insights = report.get('key_insights', [])
        if insights:
            lines.append("\n## Key Insights")
            for i, insight in enumerate(insights, 1):
                if isinstance(insight, dict):
                    lines.append(f"\n### {i}. {insight.get('insight', 'N/A')}")
                    lines.append(f"**Significance:** {insight.get('significance', 'N/A')}")
                    lines.append(f"**Evidence:** {insight.get('evidence', 'N/A')}")
        
        # Recommendations
        recommendations = report.get('recommendations', [])
        if recommendations:
            lines.append("\n## Recommendations")
            for rec in recommendations:
                lines.append(f"- {rec}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Markdown report exported to: {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to export markdown report: {e}")
