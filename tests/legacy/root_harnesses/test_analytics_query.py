"""Test analytics query system"""
import yaml
from analytics_query import AnalyticsQuery

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Test queries
query_engine = AnalyticsQuery(config)

# Test different types of queries
questions = [
    ('What emotions are in the video?', None),
    ('What objects appear most often?', None),
    ('Who is in the video?', None),
    ('What are the main themes?', None)
]

for q, video_path in questions:
    print(f'\n{"="*60}')
    print(f'QUESTION: {q}')
    print(f'{"="*60}')
    result = query_engine.query(q, video_path)
    
    if result.get('answer'):
        print(f'\nANSWER: {result["answer"]}')
        print(f'Confidence: {result.get("confidence", 0.0):.2f}')
    
    if result.get('data'):
        print(f'\nDATA SUMMARY:')
        for key, value in result['data'].items():
            if isinstance(value, dict):
                print(f'  {key}: {len(value)} items')
            elif isinstance(value, list):
                print(f'  {key}: {len(value)} items')
            else:
                print(f'  {key}: {value}')
    
    if result.get('error'):
        print(f'\nERROR: {result["error"]}')

print(f'\n{"="*60}')
print('Analytics query test complete!')
