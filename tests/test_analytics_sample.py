"""Test analytics for sample.mp4"""
import yaml
from pathlib import Path
from analytics_engine import AnalyticsEngine, export_markdown_report

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Generate report for sample.mp4
engine = AnalyticsEngine(config)
report = engine.generate_comprehensive_report('L:/goodq4all/import_inbox/sample.mp4')

# Save report
output_path = Path('output/sample_analytics_report.md')
export_markdown_report(report, output_path)

print(f'Report generated: {output_path}')
print(f'Key insights: {len(report.get("key_insights", []))}')
print(f'Recommendations: {len(report.get("recommendations", []))}')
print(f'\n=== SUMMARY ===')
print(f'Scenes: {report["summary"].get("total_scenes", 0)}')
print(f'Duration: {report["summary"].get("total_duration", 0):.1f}s')
print(f'Entities: {report["summary"].get("entities_detected", 0)}')
print(f'Modalities: {", ".join(report["summary"].get("modalities_processed", []))}')
