<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-04-12 -->

# Season 3 Episode Forensic Audit - 03x05 "The Library"

## Scope

- Epoch: `epoch_2025_12_23`
- Episode: `03x05 - The Library`
- Feature under review: `scene_context_llm`
- Alignment surfaces under review:
  - interpretation: `scene_context_llm`
  - dominance: `interaction_dominance`
  - identity: `candidate_visible_people` and `conversation_owner`
  - graph persistence: `knowledge_graph.db`
  - memory persistence: `memory.db`

This audit is intentionally forensic rather than random. It maps one episode
deeply enough to show exactly how the interpretation layer aligns with
dominance, identity, and knowledge graph edges in the current validated
treatment epoch.

## Canonical Artifacts Reviewed

- `processing/03x05 - The Library/video/scene_manifest.json`
- `processing/03x05 - The Library/temporal_index.json`
- `reports/fresh_ingest_runs/20260411_194713_season3_feature_ladder/experiment_log.json`
- `memory.db`
- `knowledge_graph.db`

## Episode-Level Persistence Check

- `scene_count = 39`
- `segments_with_scene_context_llm = 39`
- `segments_with_interaction_dominance = 14`
- `segments_with_conversation_owner = 4`
- `segments_with_candidate_visible_people = 8`
- `knowledge_graph.db` contains `39` `video_scene` media nodes for this episode
- `memory.db` contains `39` `scene_summary` entries for this episode

This means the episode is fully persisted across both memory layers:

1. scene bundles and temporal index
2. long-term summaries in `memory.db`
3. media-linked nodes and edges in `knowledge_graph.db`

## Alignment Model

The interpretation layer is behaving correctly only when all four of these
conditions hold together:

1. `scene_context_llm` stays additive and grounded in local evidence
2. `interaction_dominance` explains who carried the spoken exchange
3. identity surfaces stay conservative unless visual or mention evidence
   supports escalation
4. the knowledge graph preserves the same topic, speaker, entity, and object
   evidence at scene scope

This episode is a good stress test because it includes:

- transcript-heavy library dispute scenes
- Bookman interrogation scenes with strong speaker dominance
- George-centered chain continuity
- anonymous visible-person candidates
- entity-rich scenes with books, library references, and named people

## High-Level Verdict

The system is aligned well enough to trust the current treatment logic, but it
is not perfect.

What is strong:

- identity boundaries are preserved
- dominance is not being hallucinated by the LLM
- `conversation_owner` is promoted from mention plus dominance chains, not from
  interpretation prose
- KG media links preserve scene-specific entities, speakers, and objects
- memory summaries are persisted for every scene in the episode

What still needs future polish:

- some interpretation summaries are underpowered or overly generic
- some scene-level entity extraction is conservative to the point of missing
  clearly spoken names like `Bookman`
- KG edges are strongest at co-occurrence and scene attachment, not richer
  semantic relations

The important point is that the system is now wrong in conservative ways, not
in dangerous ways.

## Anchor Scene 1 - Scene 2 - Transcript-Led Library Dispute

Scene:

- index `2`
- time `66.96s` -> `101.76s`

Transcript anchors:

- `The New York Public Library says that I took out Tropic of Cancer in 1971 and never returned it.`
- `I returned the book.`
- `I was with Sherry Becker.`

Dominance:

- `interaction_dominance.speaker_id = SPEAKER_01`
- `dominant_share = 0.7535`
- `confidence = strong`

Interpretation:

- summary:
  - `A group of coworkers discuss their recent work-related issues at the New York Public Library.`
- tags:
  - `New York Public Library`
  - `work-related issues`
  - `library staff`
  - `book return policy`

Identity:

- `candidate_visible_people = []`
- `conversation_owner = null`

KG evidence:

- entity nodes:
  - `New York Public Library`
  - `Tropic Of Cancer`
- object nodes:
  - `Book`
  - `Refrigerator`
- speaker nodes:
  - `...__speaker_00`
  - `...__speaker_01`
- strong local edges:
  - `object:Book --co_occurs--> speaker:SPEAKER_01`
  - `object:Book --co_occurs--> speaker:SPEAKER_00`
  - `scene --located_in--> Kitchen`
  - `scene --located_in--> Office`

Assessment:

- alignment is partial but informative
- transcript and KG agree strongly on the library and book dispute
- dominance correctly points to the complaining speaker
- identity correctly stays conservative

Residual mismatch:

- the interpretation layer overreaches with `coworkers` and `work-related
  issues`
- the local evidence supports a conversation about an overdue library book, not
  workplace problems

Meaning:

- the system kept the right topic spine
- the remaining weakness is interpretation phrasing, not authority drift

## Anchor Scene 2 - Scene 18 - Strong Dominance, Conservative Identity

Scene:

- index `18`
- time `584.28s` -> `615.8s`

Transcript anchors:

- `Look, Mr. Bookman, I returned that book.`
- `Bad year for libraries. Bad year for America.`
- `You put on a pair of shoes when you walk into the New York Public Library, fella.`

Dominance:

- `interaction_dominance.speaker_id = SPEAKER_00`
- `dominant_share = 1.0`
- `confidence = strong`

Interpretation:

- summary:
  - `Conversation about bad year.`
- tags:
  - `desk`
  - `book`
  - `sitting`
  - `reading`
  - `bad year`

Identity:

- `candidate_visible_people = []`
- `conversation_owner = null`

KG evidence:

- location nodes:
  - `America`
  - `New York Public Library`
- object nodes:
  - `Book`
  - `Tie`
- speaker nodes:
  - `...__speaker_00`
  - `...__speaker_01`
- strong local edges:
  - `location:New York Public Library --co_occurs--> speaker:SPEAKER_00`
  - `object:Book --co_occurs--> speaker:SPEAKER_00`
  - `scene --located_in--> New York Public Library`

Assessment:

- dominance is excellent here
- the scene is clearly driven by one speaker and the dominance layer says so
- identity remains conservative, which is correct
- KG preserves the library/book evidence cleanly

Residual mismatch:

- interpretation is underpowered
- transcript explicitly supports `Bookman` and the library dispute, but the
  summary collapses to `Conversation about bad year.`

Meaning:

- this is a good example of the system choosing under-assertion over false
  certainty
- the failure mode is loss of specificity, not identity contamination

## Anchor Scene 3 - Scene 22 - Heard-About Person vs Seen Person

Scene:

- index `22`
- time `734.0s` -> `765.12s`

Transcript anchors:

- `I have a witness, Sherry Becker.`
- `She wore an orange dress.`

Interpretation:

- summary:
  - `Conversation about theres way.`
- tags:
  - `bottle`
  - `witness`
  - `Sherry Becker`

Identity:

- `candidate_visible_people` contains one supported `anonymous_person_1`
- visual evidence:
  - `object_detect`
  - `face_embed`
  - `visible_person_object_count = 1`
  - `visible_face_count = 1`

Dominance:

- `interaction_dominance = null`
- `conversation_owner = null`

KG evidence:

- person nodes:
  - `Becker`
  - `She`
- object node:
  - `Bottle`
- speaker node:
  - `...__speaker_00`
- local edges:
  - `person:Becker --co_occurs--> speaker:SPEAKER_00`
  - `person:Becker --appears_in--> scene`
  - `speaker:SPEAKER_00 --speaks_in--> scene`

Assessment:

- this is one of the best identity-boundary examples in the episode
- the system correctly separates:
  - the visible person in frame, who remains anonymous
  - the spoken-about witness, who is captured as a transcript-backed person
- no LLM layer tries to assign the visible face to `Sherry Becker`

Residual mismatch:

- the interpretation text is weak and garbled
- the boundary behavior itself is correct

Meaning:

- the identity contract is holding
- the system is capable of representing spoken-about people without confusing
  them with seen people

## Anchor Scene 4 - Scenes 27-30 - George Continuity Chain

These four scenes are the strongest single chain in the episode for showing how
dominance, owner inference, anonymous visual identity, and KG persistence work
together.

Shared chain facts:

- continuity key:
  - `conversation:SPEAKER_00|SPEAKER_01`
- `interaction_dominance.speaker_id = SPEAKER_01`
- `dominant_share = 0.6767`
- `stability = 0.75`
- `confidence = stable`

Conversation owner:

- `conversation_owner = George`
- `confidence = candidate`
- `source = interaction_chain`
- `chain_length = 4`
- `mention_dominance_ratio = 1.0`
- `speaker_dominance_ratio = 0.6767`

This is exactly the intended contract:

- the owner is not produced by the LLM
- the owner is promoted by a chain that combines mention evidence and stable
  speaker dominance

### Scene 27

Transcript anchors:

- `Mr. Bookman`
- `private life`
- `final warning`

Interpretation:

- summary:
  - `Conversation about private life.`
- tags:
  - `private life`
  - `bookman remember`

Identity:

- one supported `anonymous_person_1`

KG:

- object nodes:
  - `Laptop`
  - `Tie`
- speaker co-occurrence is strong:
  - `speaker_00 --co_occurs--> speaker_01` weight `50`

Assessment:

- interpretation is topic-relevant but shallow
- dominance chain is strong
- visible identity stays anonymous

### Scene 28

Transcript anchors:

- `Littman wants to see me in his office.`
- `It's George. George is on his way up.`

Interpretation:

- summary:
  - `Conversation about littman wants.`
- tags:
  - `George`
  - `office`
  - `littman wants`

Identity:

- one supported `anonymous_person_1`

KG:

- person node:
  - `George`
- local edges:
  - `person:George --appears_in--> scene`
  - `face --identity_candidate--> person:George` weight `0.3`

Assessment:

- this is the cleanest scene in the chain for identity alignment
- interpretation references George because transcript does
- KG contains George as a person node and a low-confidence face candidate
- visible identity still remains additive rather than promoted to certainty

### Scene 29

Transcript anchors:

- `Remember that biography I recommended?`
- `Remember that Columbus book?`

Interpretation:

- summary:
  - `Table conversation about nothing remember.`
- tags:
  - `group conversation`
  - `biography recommended`

KG:

- entity node:
  - `Columbus Euro Trash`
- location node:
  - `Columbus`

Assessment:

- this is the weakest interpretation scene in the chain
- KG captures the episode-specific book reference more cleanly than the LLM
- owner and dominance still remain stable and correct across the chain

### Scene 30

Transcript anchors:

- `Heyman, the gym teacher?`
- `George Costanza`
- `steps of the library`

Interpretation:

- summary:
  - `Conversation about who heyman.`
- tags:
  - `gym teacher`
  - `library`
  - `heyman`

Identity:

- one supported `anonymous_person_1`

KG:

- person node:
  - `George`
- local edges:
  - `person:George --appears_in--> scene`
  - `face --identity_candidate--> person:George` weight `0.3`

Assessment:

- interpretation stays on the correct topic spine
- owner remains George through the chain
- KG again supports George as a low-confidence visual candidate rather than a
  hard identity assignment

Chain-level conclusion:

- this is the best proof in the episode that the system now layers cognition in
  the right order:
  - transcript + dominance produce owner continuity
  - visual presence remains anonymous unless supported
  - KG records the person/media links without turning them into certainty
  - interpretation adds retrieval-friendly scene meaning but does not own the
    authority boundary

## Anchor Scene 5 - Scene 33 - Multi-Speaker Memory Persistence

Scene:

- index `33`
- time `1099.44s` -> `1129.48s`

Transcript anchors:

- `George, here's the book.`
- `I'm late for Hammond's hygiene.`
- `Your underwear was sticking out of your shorts during gym class.`

Interpretation:

- summary:
  - `George returns a book from his locker at Hammond's hygiene.`
- tags:
  - `locker`
  - `book`
  - `Hammond's hygiene`
  - `boxer shorts`

Dominance:

- `interaction_dominance = null`
- `conversation_owner = null`

KG:

- person nodes:
  - `George`
  - `Jerry`
  - `Hammond`
- temporal context node:
  - `Relative_phrases_tomorrow`
- many speaker nodes linked into the scene

Memory persistence:

- `memory.db` scene summary explicitly stores this scene and its transcript-led
  summary

Assessment:

- this scene shows that the system can still preserve a strong semantic memory
  even without a clean dominance signal
- interpretation and KG both retain the locker/book/Hammond thread
- the absence of `conversation_owner` here is correct rather than missing

Meaning:

- this is good evidence that the stack does not require every scene to fit the
  same dominance template in order to preserve useful memory

## Synthesis - Exact Alignment by Layer

### Interpretation vs Dominance

Strong alignment:

- when a scene has stable dominance, interpretation usually follows the same
  local topic spine
- the George chain in scenes `27` to `30` is the clearest example

Important limit:

- interpretation still sometimes summarizes the topic too weakly even when
  dominance is strong
- scene `18` is the cleanest example of this underpowered phrasing

### Interpretation vs Identity

Strong alignment:

- interpretation does not directly assign visible faces to named people
- scene `22` is the clearest example of this boundary holding

Important limit:

- interpretation may mention a named person from transcript while the visible
  person stays anonymous
- this is correct behavior and should not be treated as a mismatch

### Interpretation vs KG Edges

Strong alignment:

- KG reliably preserves scene-linked objects, speakers, and many dialogue
  entities
- scene `2` and scene `33` show the best topic-to-KG alignment

Important limit:

- KG semantic richness still lags behind raw co-occurrence structure
- scene `29` shows this clearly: the KG captures `Columbus Euro Trash` more
  precisely than the interpretation summary, but only as a local node/edge
  network rather than a richer semantic statement

## Bottom-Line Verdict

`03x05 - The Library` confirms that the current cognition stack is behaving in
the right order of authority.

The core result:

1. interpretation adds useful, retrievable context
2. dominance explains who drove the exchange
3. identity remains conservative and auditable
4. the KG preserves the scene-linked evidence that those layers sit on top of

What is proven by this episode:

- the LLM layer is no longer rewriting scenes into invented social narratives
- `conversation_owner` is grounded in chain evidence, not prose
- visible identity candidates stay anonymous unless supported
- scene memory is fully embedded across both `memory.db` and
  `knowledge_graph.db`

What remains true:

- some interpretation summaries are still too generic
- some dialogue names are still captured more cleanly by KG than by the LLM
- this is now a refinement problem, not a trust or architecture problem

## Recommendation

Treat the current `scene_context_llm` stack as production-worthy for continued
Season 3 treatment runs, with future work focused on:

1. improving transcript-specific wording in underpowered scenes like `18` and
   `29`
2. enriching KG semantic relations beyond co-occurrence where justified
3. preserving the current identity boundary exactly as-is
