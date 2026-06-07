# Season 1 Semantic Comparison Report

Date: 2026-03-10

Source run: `20260309_235047_season1_reliability_rerun_v2`

Flight recorder:

- `ingestion_results.json`
- `step_runs.jsonl`
- `resolved_config_snapshot.json`

Structured metrics companion:

- `semantic_comparison_metrics.json`

## Top Recurring Entities

### People

| Entity | Scene Mentions |
| --- | ---: |
| Jerry | 28 |
| George | 20 |
| Elaine | 13 |
| Wilkinson | 7 |
| Vanessa | 5 |
| Bill | 4 |
| Joel | 4 |
| Laura | 4 |
| God | 3 |
| Nick | 3 |
| Pamela | 3 |
| Simon | 3 |

### Locations

| Entity | Scene Mentions |
| --- | ---: |
| Vermont | 8 |
| 48th Street | 2 |
| Atlanta | 2 |
| Boston | 2 |
| Connecticut | 2 |
| Europe | 2 |
| Finland | 2 |
| Georgia | 2 |
| Horn | 2 |
| Iceland | 2 |
| Krypton | 2 |
| Lansing | 2 |

This list is intentionally episode-grounded. It reflects recurring named presence in the season run, not a hand-authored cast list.

## Top Scene Clusters

### Cluster 1: Wilkinson / Simon

- Average text similarity: **0.6079**
- Episode spread: `{'01x05 - The Stock Tip': 3}`
- Dominant entities: `Wilkinson` (3), `Simon` (2), `Bill` (1)

- `01x05 - The Stock Tip` scene `6`: A stock. What stock? Did you ever meet my friend Simon's? Maybe. He knows this guy Wilkinson. He made a bit of fortune i...
- `01x05 - The Stock Tip` scene `32`: So big daddy, I'm just curious how much did you clear on your little transaction they're all told? I don't like to discu...
- `01x05 - The Stock Tip` scene `7`: All right, some sort of electronic thingy. Well, how much are you going to invest? 5,000. 10. 10,000. 5,000. What? Come ...

### Cluster 2: Jerry / Joel

- Average text similarity: **0.5793**
- Episode spread: `{'01x04 - Male Unbonding': 1, '01x03 - The Robbery': 1, '01x02 - The Stakeout': 1}`
- Dominant entities: `Jerry` (3), `Joel` (1), `George` (1), `Elaine` (1)

- `01x04 - Male Unbonding` scene `27`: One day, you'll bait me to make your own pie. Hi, Joel. This is Jerry. I hope you get this before you... Oh, hi, Joel. O...
- `01x03 - The Robbery` scene `32`: Hi. I care. I just wanted to introduce it to my husband, this is Larry, this is George, Elaine and Jerry. These are the ...
- `01x02 - The Stakeout` scene `33`: Yeah, Uncle Mack, you mentioned it. It's based on all my experiences. That's perfect. Could you excuse me one second? Oh...

### Cluster 3: Jerry / George

- Average text similarity: **0.5753**
- Episode spread: `{'01x03 - The Robbery': 2, '01x02 - The Stakeout': 1}`
- Dominant entities: `Jerry` (3), `George` (1), `Elaine` (1)

- `01x03 - The Robbery` scene `32`: Hi. I care. I just wanted to introduce it to my husband, this is Larry, this is George, Elaine and Jerry. These are the ...
- `01x03 - The Robbery` scene `26`: You got even right ready for the apartment Congratulations Congratulations Thanks I'm just going to Why did I put out to...
- `01x02 - The Stakeout` scene `33`: Yeah, Uncle Mack, you mentioned it. It's based on all my experiences. That's perfect. Could you excuse me one second? Oh...

### Cluster 4: Joel + greeting

- Average text similarity: **0.5696**
- Episode spread: `{'01x04 - Male Unbonding': 2, '01x01 - Good News, Bad News': 1}`
- Dominant entities: `Joel` (2)
- Dialogue hints: `greeting` (3)

- `01x04 - Male Unbonding` scene `14`: Oh, hey! Unbelievable. How can you talk to someone like that? What do you say? Well, you like turkey roll? Listen, Joel,...
- `01x04 - Male Unbonding` scene `6`: Who is it? Take it. Who is it? It's for you. Hello. Oh, hi, Joel. What? No, what? I was out of town. I just got back. Cr...
- `01x01 - Good News, Bad News` scene `27`: Yeah, hello. Yes, yes she is. Hold on. It's for you. Hello? Hi! No, no, it was great right on time. No, I'm going to sta...

### Cluster 5: Jerry / George

- Average text similarity: **0.5651**
- Episode spread: `{'01x03 - The Robbery': 3}`
- Dominant entities: `Jerry` (2), `George` (1), `Elaine` (1)

- `01x03 - The Robbery` scene `26`: You got even right ready for the apartment Congratulations Congratulations Thanks I'm just going to Why did I put out to...
- `01x03 - The Robbery` scene `32`: Hi. I care. I just wanted to introduce it to my husband, this is Larry, this is George, Elaine and Jerry. These are the ...
- `01x03 - The Robbery` scene `19`: Geez! Is that incredible? Congratulations. What about the couch? You like the couch? Tell you what I'm going to do. What...

## Cross-Episode Similarity Groups

### Group 1: Jerry / Joel

- Average text similarity: **0.5793**
- Episodes represented: 01x04 - Male Unbonding, 01x03 - The Robbery, 01x02 - The Stakeout
- Shared entities: `Jerry`, `Joel`, `George`, `Elaine`

- `01x04 - Male Unbonding` scene `27`: One day, you'll bait me to make your own pie. Hi, Joel. This is Jerry. I hope you get this before you... Oh, hi, Joel. O...
- `01x03 - The Robbery` scene `32`: Hi. I care. I just wanted to introduce it to my husband, this is Larry, this is George, Elaine and Jerry. These are the ...
- `01x02 - The Stakeout` scene `33`: Yeah, Uncle Mack, you mentioned it. It's based on all my experiences. That's perfect. Could you excuse me one second? Oh...

### Group 2: Jerry / George

- Average text similarity: **0.5753**
- Episodes represented: 01x03 - The Robbery, 01x02 - The Stakeout
- Shared entities: `Jerry`, `George`, `Elaine`

- `01x03 - The Robbery` scene `32`: Hi. I care. I just wanted to introduce it to my husband, this is Larry, this is George, Elaine and Jerry. These are the ...
- `01x03 - The Robbery` scene `26`: You got even right ready for the apartment Congratulations Congratulations Thanks I'm just going to Why did I put out to...
- `01x02 - The Stakeout` scene `33`: Yeah, Uncle Mack, you mentioned it. It's based on all my experiences. That's perfect. Could you excuse me one second? Oh...

### Group 3: Joel + greeting

- Average text similarity: **0.5696**
- Episodes represented: 01x04 - Male Unbonding, 01x01 - Good News, Bad News
- Shared entities: `Joel`
- Shared dialogue hints: `greeting`

- `01x04 - Male Unbonding` scene `14`: Oh, hey! Unbelievable. How can you talk to someone like that? What do you say? Well, you like turkey roll? Listen, Joel,...
- `01x04 - Male Unbonding` scene `6`: Who is it? Take it. Who is it? It's for you. Hello. Oh, hi, Joel. What? No, what? I was out of town. I just got back. Cr...
- `01x01 - Good News, Bad News` scene `27`: Yeah, hello. Yes, yes she is. Hold on. It's for you. Hello? Hi! No, no, it was great right on time. No, I'm going to sta...

### Group 4: Elaine / Jerry

- Average text similarity: **0.5580**
- Episodes represented: 01x02 - The Stakeout, 01x03 - The Robbery
- Shared entities: `Elaine`, `Jerry`, `George`

- `01x02 - The Stakeout` scene `18`: ... eight problem. No, it's not that. It wasn't all one side. You know, you can't be so particular. Nobody's perfect. I ...
- `01x03 - The Robbery` scene `32`: Hi. I care. I just wanted to introduce it to my husband, this is Larry, this is George, Elaine and Jerry. These are the ...
- `01x02 - The Stakeout` scene `16`: ... , and I know where she works, but I don't know her name. So why don't you ask someone who was at the party? No, the ...

### Group 5: Joel / George + greeting / awkward

- Average text similarity: **0.5528**
- Episodes represented: 01x04 - Male Unbonding, 01x01 - Good News, Bad News
- Shared entities: `Joel`, `George`, `Laura`
- Shared dialogue hints: `greeting`, `awkward`, `reunion`

- `01x04 - Male Unbonding` scene `6`: Who is it? Take it. Who is it? It's for you. Hello. Oh, hi, Joel. What? No, what? I was out of town. I just got back. Cr...
- `01x04 - Male Unbonding` scene `14`: Oh, hey! Unbelievable. How can you talk to someone like that? What do you say? Well, you like turkey roll? Listen, Joel,...
- `01x01 - Good News, Bad News` scene `24`: ... Oh! Oh! Oh! You're back! You're back! Oh, I'm sorry. Thank you. But that was an interesting greeting. Did you notice...

## Dialogue Archetypes

| Archetype | Scenes | Representative Pattern |
| --- | ---: | --- |
| `complaint` | 8 | Can you relax? It's a cup of coffee. Claire's a professional waitress. Trust me, George. No one has any interest in seei... |
| `confrontation` | 7 | Can you relax? It's a cup of coffee. Claire's a professional waitress. Trust me, George. No one has any interest in seei... |
| `greeting` | 6 | ... I mean, I felt so uncomfortable and you were so annoyed in the cab. Well, Jerry, I never saw you flirt with anyone b... |
| `reunion` | 3 | ... I mean, I felt so uncomfortable and you were so annoyed in the cab. Well, Jerry, I never saw you flirt with anyone b... |
| `awkward` | 1 | ... Oh! Oh! Oh! You're back! You're back! Oh, I'm sorry. Thank you. But that was an interesting greeting. Did you notice... |

### Archetype: complaint

- Scene count: **8**
- `01x01 - Good News, Bad News` scene `3` with `Claire`, `George`, `Laura`, `Michigan`: Can you relax? It's a cup of coffee. Claire's a professional waitress. Trust me, George. No one has any interest in seei...
- `01x02 - The Stakeout` scene `24` with `Lane`, `Art Corvalle`, `Van Delay`, `Corvalle`: He's an importer. Just imports? No exports? He's an importer exporter, okay? Lane never call you back. No, I guess she's...
- `01x03 - The Robbery` scene `9` with `Bloomingdale`, `Jerry`: ... Yeah, and? Well, I got caught up watching a soap opera. Bold and the beautiful. Should I have the door was wide open...

### Archetype: confrontation

- Scene count: **7**
- `01x01 - Good News, Bad News` scene `3` with `Claire`, `George`, `Laura`, `Michigan`: Can you relax? It's a cup of coffee. Claire's a professional waitress. Trust me, George. No one has any interest in seei...
- `01x02 - The Stakeout` scene `24` with `Lane`, `Art Corvalle`, `Van Delay`, `Corvalle`: He's an importer. Just imports? No exports? He's an importer exporter, okay? Lane never call you back. No, I guess she's...
- `01x01 - Good News, Bad News` scene `15` with `Laura`, `George`: I know. No, I can be very persuasive. You know that I was almost a lawyer? Back close, huh? You better believe it. Hello...

### Archetype: greeting

- Scene count: **6**
- `01x02 - The Stakeout` scene `34` with `Jerry`, `Elaine`, `Art`, `Levine`: ... I mean, I felt so uncomfortable and you were so annoyed in the cab. Well, Jerry, I never saw you flirt with anyone b...
- `01x01 - Good News, Bad News` scene `24` with `George`, `Laura`: ... Oh! Oh! Oh! You're back! You're back! Oh, I'm sorry. Thank you. But that was an interesting greeting. Did you notice...
- `01x04 - Male Unbonding` scene `6` with `Joel`: Who is it? Take it. Who is it? It's for you. Hello. Oh, hi, Joel. What? No, what? I was out of town. I just got back. Cr...

### Archetype: reunion

- Scene count: **3**
- `01x02 - The Stakeout` scene `34` with `Jerry`, `Elaine`, `Art`, `Levine`: ... I mean, I felt so uncomfortable and you were so annoyed in the cab. Well, Jerry, I never saw you flirt with anyone b...
- `01x01 - Good News, Bad News` scene `24` with `George`, `Laura`: ... Oh! Oh! Oh! You're back! You're back! Oh, I'm sorry. Thank you. But that was an interesting greeting. Did you notice...
- `01x03 - The Robbery` scene `12` with no strong named entities: Well, thanks anyway. You're back. I didn't get that joke either. The cook has the machine. The messages aren't for him. ...

### Archetype: awkward

- Scene count: **1**
- `01x01 - Good News, Bad News` scene `24` with `George`, `Laura`: ... Oh! Oh! Oh! You're back! You're back! Oh, I'm sorry. Thank you. But that was an interesting greeting. Did you notice...

## Readout

- The recurring-entity layer is now strong enough to expose stable season actors like `Jerry`, `George`, and `Elaine`, while still preserving episode-specific figures like `Wilkinson`, `Vanessa`, `Joel`, and `Laura`.
- The text collection shows cross-episode conversational motifs rather than isolated episode blobs; similar introductions, complaint scenes, and social handoff scenes cluster together across the season.
- Dialogue archetypes are present and countable in the live payloads: `complaint`, `confrontation`, `greeting`, `reunion`, and `awkward` are all observable without additional post-hoc model passes.
- The main remaining semantic caveat is residual one-off entity noise in the long tail. It no longer dominates the graph, but it still appears in some cluster member payloads.

