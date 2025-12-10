import sqlite3
import json

conn = sqlite3.connect('L:/_DATA/GoodQ_Data/memory.db')
c = conn.cursor()
c.execute('SELECT meta FROM scenes LIMIT 1')
meta = json.loads(c.fetchone()[0])

print('='*80)
print('PHASE 2 ENHANCED SCENE DATA - SAMPLE')
print('='*80)
print(f'\nScene Index: {meta.get("index")}')
print(f'Timestamp: {meta.get("start"):.1f}s - {meta.get("end"):.1f}s')
print(f'Duration: {meta.get("duration"):.1f}s')

print('\n--- LLM CONTEXT ANALYSIS ---')
ctx = meta.get('context', {})
print(f'Narrative: {ctx.get("narrative_summary", "N/A")}')
print(f'Key Moments: {ctx.get("key_moments", [])}')
print(f'Activity: {ctx.get("activity_description", "N/A")}')
print(f'Emotional Arc: {ctx.get("emotional_arc", "N/A")}')
print(f'Context Tags: {ctx.get("context_tags", [])}')

print('\n--- INTELLIGENT TAGS (LLM) ---')
print(f'Tags: {meta.get("tags", [])}')
print(f'Themes: {meta.get("themes", [])}')
print(f'Keywords: {meta.get("keywords", [])}')
print(f'Tagging Method: {meta.get("tagging_method", "N/A")}')

print('\n--- RELATIONSHIPS DETECTED ---')
rels = ctx.get('relationships', [])
for r in rels:
    print(f'  • {r}')

print('\n--- ORIGINAL DATA (for comparison) ---')
print(f'Original Caption: {meta.get("caption", "N/A")}')
print(f'Transcript: {meta.get("transcript", "N/A")[:100]}...')
print(f'Old Tags: {meta.get("tags", [])}')

conn.close()
print('\n' + '='*80)
