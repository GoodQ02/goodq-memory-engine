# Character and Entity Discovery Report

## Top Entities

| Entity | Type | Occurrence Count | Episode Recurrence |
| --- | --- | --- | --- |
| I'm | entity | 33 | 5 |
| You | entity | 30 | 5 |
| Jerry | entity | 27 | 5 |
| What | entity | 22 | 5 |
| George | entity | 19 | 4 |
| It's | entity | 15 | 4 |
| That's | entity | 13 | 5 |
| Well | entity | 13 | 5 |
| Elaine | entity | 13 | 4 |
| Yeah | entity | 10 | 5 |
| This | entity | 10 | 4 |
| I'll | entity | 9 | 5 |
| Okay | entity | 9 | 3 |
| Why | entity | 8 | 4 |
| And | entity | 7 | 4 |
| How | entity | 7 | 3 |
| You're | entity | 7 | 3 |
| Wilkinson | entity | 7 | 1 |
| They | entity | 6 | 4 |
| But | entity | 6 | 3 |
| Let | entity | 6 | 3 |
| The | entity | 6 | 3 |
| We're | entity | 6 | 3 |
| Look | entity | 5 | 4 |
| All | entity | 5 | 3 |

## Character Focus

| Character | Transcript Scene Mentions | Transcript Episode Span | KG Matching Nodes | KG Occurrence Sum |
| --- | --- | --- | --- | --- |
| Jerry | 28 | 5 | 3 | 29 |
| George | 19 | 4 | 2 | 20 |
| Elaine | 15 | 4 | 4 | 16 |
| Kramer | 2 | 1 | 1 | 2 |

## Entity Frequency Histogram (Top 12)

- `I'm` (entity) 33: ████████████████████████
- `You` (entity) 30: ██████████████████████
- `Jerry` (entity) 27: ████████████████████
- `What` (entity) 22: ████████████████
- `George` (entity) 19: ██████████████
- `It's` (entity) 15: ███████████
- `That's` (entity) 13: █████████
- `Well` (entity) 13: █████████
- `Elaine` (entity) 13: █████████
- `Yeah` (entity) 10: ███████
- `This` (entity) 10: ███████
- `I'll` (entity) 9: ███████

## Co-occurrence / Relationship Signals

| Edge Type | Source | Target | Weight |
| --- | --- | --- | --- |
| co_occurs | speech (concept) | I'm (entity) | 33.00 |
| co_occurs | speech (concept) | You (entity) | 30.00 |
| co_occurs | speech (concept) | Jerry (entity) | 27.00 |
| co_occurs | speech (concept) | What (entity) | 22.00 |
| co_occurs | speech (concept) | months_may (temporal_context) | 21.00 |
| co_occurs | speech (concept) | George (entity) | 19.00 |
| co_occurs | speech (concept) | It's (entity) | 15.00 |
| co_occurs | You (entity) | I'm (entity) | 14.00 |
| co_occurs | speech (concept) | Elaine (entity) | 13.00 |
| co_occurs | speech (concept) | Well (entity) | 13.00 |
| co_occurs | speech (concept) | That's (entity) | 13.00 |
| co_occurs | speech (concept) | relative_phrases_tomorrow (temporal_context) | 13.00 |
| co_occurs | What (entity) | I'm (entity) | 12.00 |
| co_occurs | It's (entity) | I'm (entity) | 11.00 |
| co_occurs | You (entity) | What (entity) | 11.00 |

## Assessment

- Characters are partially detected; recurrence exists but identity consistency remains uneven.
- KG relationships are forming and recurring entities are visible across episodes.