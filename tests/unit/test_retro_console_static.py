from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RETRO_JS_PATH = REPO_ROOT / "ui" / "retro_console_v1" / "static" / "js" / "retro.js"
RETRO_JS = RETRO_JS_PATH.read_text(encoding="utf-8")


def test_sound_candidates_and_speech_estimates_have_separate_visible_scope():
    source = _function_source('renderAcousticEvidence')
    harness = r'''
const assert=require('node:assert/strict');
const document={createElement:()=>({children:[],appendChild(x){this.children.push(x);}})};
const appendText=(node,tag,text)=>node.children.push({tag,text});
const root=document.createElement('div');
eval(SOURCE);
renderAcousticEvidence(root,{sound_events:[{start:25,end:40,label:'crying'},{start:'bad',end:40,label:'invalid'}],
  emotion_input:{status:'insufficient_evidence'},emotion_segments:[]});
const text=JSON.stringify(root);
assert(text.includes('crying · sound candidate'));
assert(text.includes('approximate interval within scene'));
assert(text.includes('insufficient clear speech'));
assert(!text.includes('invalid'));
const second=document.createElement('div');
renderAcousticEvidence(second,{emotion_input:{status:'ready'},emotion_segments:[{start:0,end:2,speaker:'S0',label:'neutral'}]});
assert(JSON.stringify(second).includes('S0: neutral · speech estimate, unreviewed'));
'''.replace('SOURCE', json.dumps(source))
    result = subprocess.run(['node', '-e', harness], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_loaded_inspector_retains_crying_without_a_scene_emotion():
    observed = _scene_audio_journey(scene_overrides={
        'audio_emotion': None, 'audio_emotion_ranking': [],
        'sound_events': [{'start': 25, 'end': 40, 'label': 'crying'}],
        'emotion_input': {'status': 'insufficient_evidence'}, 'emotion_segments': [],
    })['before']['overviewText']
    assert 'crying · sound candidate' in observed
    assert 'insufficient clear speech' in observed


def test_inspector_explains_withheld_phrases_and_unqualified_scores():
    observed = _scene_audio_journey(scene_overrides={
        'emotion_input': {'status':'ready', 'phrase_selection': {'status':'insufficient_evidence',
            'rejected':[{'start':19,'end':21,'text':'Yay!', 'reason':'phrase_speakers_unresolved'}]}},
        'emotion_segments':[{'start':1,'end':2,'speaker':'S0','label':'disgust', 'scores':{'disgust':.95},
            'interpretation_status':'uncertain','uncertainty_reasons':['model_accuracy_not_qualified']}],
        'sound_events':[{'start':25,'end':40,'label':'crying'}],
    })['before']['overviewText']
    assert 'Speech may still be audible' in observed
    assert 'Yay! · scoring withheld: overlapping or unresolved speakers' in observed
    assert 'Emotion uncertain: model accuracy is not qualified' in observed
    assert 'crying · sound candidate' in observed
    assert 'insufficient clear speech' not in observed


@pytest.mark.parametrize('reason,explanation', [
    ('local_overlap_in_phrase', 'overlapping speech detected locally; individual speaker unresolved'),
    ('additional_overlap_in_phrase', 'additional overlap candidate; individual speaker unresolved'),
    ('overlap_detection_unavailable', 'overlap assessment unavailable'),
    ('phrase_boundary_timing_unavailable', 'phrase boundaries unresolved'),
])
def test_inspector_explains_local_overlap_without_assigning_an_individual(reason, explanation):
    observed = _scene_audio_journey(scene_overrides={
        'emotion_input': {'status':'insufficient_evidence', 'phrase_selection': {
            'status':'insufficient_evidence', 'rejected':[{'start':1,'end':3,
                'text':'Please come here.', 'reason':reason}]}},
        'emotion_segments': [],
    })['before']['overviewText']
    assert f'Please come here. · scoring withheld: {explanation}' in observed


def test_inspector_displays_local_overlap_candidates_separately_from_speaker_names():
    observed = _scene_audio_journey(scene_overrides={
        'emotion_input': {'status':'ready', 'speaker_purity': {'local_overlap': {
            'status':'ok', 'intervals':[None, {'start':19.09315625,'end':19.17753125},
                {'start':'bad','end':20}]}}}, 'emotion_segments': [],
    })['before']['overviewText']
    assert '19.09–19.18s: overlapping voices · local model candidate, unreviewed; speakers unresolved' in observed


@pytest.mark.parametrize('status', ['ok', 'error', 'unavailable'])
def test_inspector_discloses_additional_detector_evidence_and_failure(status):
    observed = _scene_audio_journey(scene_overrides={
        'emotion_input': {'status': 'unavailable' if status != 'ok' else 'ready',
            'speaker_purity': {'additional_overlap': {'status': status,
                'intervals': [None, {'start': 19.06, 'end': 19.52}]}}},
        'emotion_segments': [],
    })['before']['overviewText']
    if status == 'ok':
        assert '19.06–19.52s: overlapping voices · additional model candidate, unreviewed; speakers unresolved' in observed
    else:
        assert 'Additional overlap assessment unavailable; individual scoring withheld' in observed


def test_inspector_shows_vocal_distribution_and_vocabulary_context():
    text = _scene_audio_journey(scene_overrides={
        'emotion_input': {'status': 'ready'},
        'emotion_segments': [{'start': 0, 'end': 2, 'speaker': 'S0', 'label': 'disgust',
                             'scores': {'disgust': .36, 'sad': .33, 'happy': .31}}],
        'transcript_meta': {'transcription_context': {'status': 'applied', 'words': ['Joe', '<name>']}},
    })['before']['overviewText']
    assert 'disgust 36%' in text and 'sad 33%' in text and 'happy 31%' in text
    assert 'uncalibrated model scores' in text
    assert 'Vocabulary hints: Joe, <name>' in text
    assert 'does not confirm who is present' in text


def test_inspector_shows_untranscribed_regions_and_decoder_warnings():
    coverage = {'policy': 'source_regions_v1', 'status': 'completed',
        'detected_region_count': 3, 'completed_region_count': 3,
        'regions': [{'start': 10, 'end': 11, 'outcome': 'no_text_returned', 'quality_flags': []},
            {'start': 20, 'end': 21, 'outcome': 'text_returned',
             'quality_flags': ['compression_ratio_threshold_exceeded']},
            {'start': 25, 'end': 26, 'outcome': 'text_with_unavailable_timing', 'quality_flags': [],
             'unplaced_segments': [{'text': '<yay>', 'raw_start': 25.2, 'raw_end': 25.2}]}]}
    text = _scene_audio_journey(scene_overrides={
        'transcript_meta': {'transcription_decoding': {'source_regions': coverage}}})['before']['overviewText']
    assert '3 of 3 detected speech regions processed' in text
    assert '10.0–11.0s: no text returned' in text
    assert 'Decoder repetition warning' in text
    assert '<yay> · timing unavailable' in text
    assert 'does not prove that every word was recognized' in text


def test_inspector_separates_source_coverage_phrases_and_uncertain_word_timing():
    text = _scene_audio_journey(scene_overrides={'transcript_meta': {
        'transcription_decoding': {'source_regions': {'policy':'source_audio_v2','status':'completed',
            'detected_region_count':9,'recognition_region_count':1,'completed_region_count':1,'regions':[]}},
        'segments':[{'text':'Hello Joe.', 'phrase_timing':{'status':'model_estimated',
            'boundary_status':'model_estimated_complete_phrase','start':.1,'end':1.5,'timebase':'input_audio_seconds'}}],
        'word_alignment':{'timebase':'input_audio_seconds','words':[{'text':'Joe.','start':None,'end':None}]}
    }})['before']['overviewText']
    assert '1 of 1 original audio regions processed' in text
    assert '0.10–1.50s · Hello Joe. · estimated complete phrase' in text
    assert 'Joe. · timing unavailable' in text
    assert 'Phrase timing · separate from word alignment' in text


def test_loaded_inspector_retains_unresolved_overlap_words_without_identity():
    text = _scene_audio_journey(scene_overrides={
        'transcript_meta': {'segments':[{'start':19.7,'end':20.3,'text':'Yay!',
            'speaker':None,'speaker_candidates':['A','B'],
            'attribution_status':'unresolved','attribution_reason':'overlapping_speakers'}]},
    })['before']['overviewText']
    assert 'Yay! · Overlapping voices — speakers unresolved.' in text


def test_inspector_keeps_near_even_sentiment_score_visible():
    text = _scene_audio_journey(scene_overrides={
        'sentiment_label': 'NEGATIVE', 'sentiment_score': .5012416,
    })['before']['overviewText']
    assert 'Text: negative · 50.1% score' in text


def test_inspector_displays_recovered_timing_and_attributed_context():
    observed = _scene_audio_journey(scene_overrides={
        'transcript_meta': {'word_alignment': {'timebase': 'input_audio_seconds', 'words': [
            {'text': 'Yay!', 'start': 19.72, 'end': 20.32, 'timing_status': 'recovered_model_alignment'},
            {'text': 'invalid', 'start': 4, 'end': 4, 'timing_status': 'recovered_model_alignment'}]}},
        'scene_context_llm': {'narrative_summary': 'Speech about a birthday.',
                              'emotional_arc': 'Positive words with crying nearby.'},
    })['before']['overviewText']
    assert '19.72–20.32s · Yay!' in observed
    assert 'recovered timing, unreviewed' in observed
    assert 'invalid · timing unavailable' in observed
    assert 'Speech about a birthday.' in observed
    assert 'Tone assessment: Positive words with crying nearby.' in observed
    assert 'Stored model assessment; not verified scene facts.' in observed


@pytest.mark.parametrize("case", ["saved", "epoch", "person", "scene", "video", "incomplete", "read-error", "missing-scene", "close-error"])
def test_saved_people_watch_binds_source_without_search_and_returns_to_selection(case):
    source = _function_source("openSavedAppearance")
    harness = r'''
const assert=require('node:assert/strict');
const fixture=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const params=new URLSearchParams({watch_person:'p',watch_scene:'s',watch_video:'Movie',watch_epoch:'epoch'});
if(fixture.case==='incomplete')params.delete('watch_scene');
const elements=new Map();
const document={body:{classList:{add(){}}},getElementById:id=>{
  if(!elements.has(id))elements.set(id,{textContent:'',hidden:true,addEventListener(name,fn){this[name]=fn;}});
  return elements.get(id);
}};
let navigated=null, selected=null, loaded=0, dismissed=0;
const window={location:{search:'?'+params,assign:url=>{navigated=url;}}};
const state={videos:[{video_id:'Movie'}],scenes:[]};
const originalVideo={element:{pause(){}},desktop:{doneAndWait:async()=>{dismissed++;return fixture.case!=='close-error';}}};
const pauseOriginalAudio=()=>{},ttsStop=()=>{},formatTime=String;
const selectScene=id=>{selected=id;};
const loadDataset=async id=>{loaded++;state.activeVideoId=id;state.scenes=fixture.case==='missing-scene'?[]:[{id:'s',start:30,end:40}];};
const apiGet=async path=>{
  assert.equal(path,'/api/identity/appearances/saved?person_id=p');
  if(fixture.case==='read-error')throw Error('Offline');
  return {epoch_id:fixture.case==='epoch'?'other':'epoch',people:fixture.case==='person'?[]:[{id:'p',display_name:'Avery'}],
    appearances:[{person_id:'p',scene_id:fixture.case==='scene'?'other':'s',video_id:fixture.case==='video'?'other':'Movie'}]};
};
eval(fixture.source);
(async()=>{
  assert.equal(await openSavedAppearance(),true);
  const back=elements.get('return-to-people');
  if(['saved','close-error'].includes(fixture.case)){
    assert.equal(selected,'s');assert.equal(loaded,1);
    assert.match(elements.get('people-watch-status').textContent,/Avery.*30.*40/);
    assert.match(back.textContent,/Back to Avery/);
    await back.click({preventDefault(){}});
    assert.equal(dismissed,1);
    if(fixture.case==='close-error'){
      assert.equal(navigated,null);assert.match(elements.get('people-watch-status').textContent,/could not close/);
    }else assert.equal(navigated,'/ui/identity_workbench/?person=p&scene=s&epoch=epoch');
  }else{
    assert.equal(selected,null);
    assert.equal(loaded,fixture.case==='missing-scene'?1:0);
    assert.match(elements.get('people-watch-status').textContent,/Return to People/);
  }
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
'''
    subprocess.run(["node", "-e", harness], input=json.dumps({"case": case, "source": source}),
                   text=True, check=True, capture_output=True, cwd=REPO_ROOT)


@pytest.mark.parametrize("case", ["valid", "epoch", "scene", "video", "evidence", "applied", "missing-video"])
def test_proposed_match_watch_requires_exact_unapplied_evidence(case):
    source = _function_source("openSavedAppearance")
    harness = r'''
const assert=require('node:assert/strict');
const fixture=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const params=new URLSearchParams({watch_match:'report',watch_evidence:'evidence',watch_scene:'s',watch_video:'Movie',watch_epoch:'epoch'});
const elements=new Map();
const document={body:{classList:{add(){}}},getElementById:id=>{
  if(!elements.has(id))elements.set(id,{textContent:'',hidden:true,addEventListener(name,fn){this[name]=fn;}});
  return elements.get(id);
}};
let selected=null,navigated=null;
const window={location:{search:'?'+params,assign:url=>{navigated=url;}}};
const state={videos:fixture.case==='missing-video'?[]:[{video_id:'Movie'}],scenes:[]};
const originalVideo={element:{pause(){}},desktop:{doneAndWait:async()=>true}};
const pauseOriginalAudio=()=>{},ttsStop=()=>{},formatTime=String;
const selectScene=id=>{selected=id;};
const loadDataset=async id=>{state.activeVideoId=id;state.scenes=[{id:'s',start:30,end:40}];};
const apiGet=async path=>{
  assert.equal(path,'/api/identity/matches/report');
  return {epoch_id:fixture.case==='epoch'?'other':'epoch',video_id:fixture.case==='video'?'other':'Movie',
    applied:fixture.case==='applied',records:[{id:fixture.case==='evidence'?'other':'evidence',
      scene_id:fixture.case==='scene'?'other':'s',modality:'voice'}]};
};
eval(fixture.source);
(async()=>{
  assert.equal(await openSavedAppearance(),true);
  if(fixture.case==='valid'){
    assert.equal(selected,'s');assert.match(elements.get('people-watch-status').textContent,/not applied/);
    await elements.get('return-to-people').click({preventDefault(){}});
    assert.equal(navigated,'/ui/identity_workbench/?matches=report&match_kind=voice');
  }else assert.equal(selected,null);
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
'''
    subprocess.run(["node", "-e", harness], input=json.dumps({"case": case, "source": source}),
                   text=True, check=True, capture_output=True, cwd=REPO_ROOT)


def test_audio_inspector_distinguishes_evidence_absence_and_failure():
    source = _function_source("renderAudioSearchEvidence")
    harness = r'''
const source = JSON.parse(require('fs').readFileSync(0, 'utf8'));
class Element { constructor() { this.children = []; this.textContent = ''; } appendChild(child) { this.children.push(child); } }
const document = { createElement: () => new Element() };
const appendText = (parent, tag, value) => { const el = new Element(); el.textContent = value; parent.appendChild(el); };
eval(source);
const cases = [null,
  {status:'skipped', reason:'audio_silent', input_policy:'full_scene', duration_sec:5},
  {status:'error', reason:'chunk_decode_failed', error:'<decoder>', input_policy:'full_scene'},
  {status:'ok', input_policy:'full_scene', total_duration_s:45.012, chunks_processed:6, chunks_skipped_silent:0, faiss_committed:true, qdrant_committed:true},
  {status:'ok'}];
process.stdout.write(JSON.stringify(cases.map(meta => { const el = new Element(); renderAudioSearchEvidence(el,meta); return el.children[0].children.map(c => c.textContent).join('\n'); })));
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps(source), text=True, capture_output=True, encoding="utf-8", check=True, timeout=20)
    unknown, silent, failed, success, historical = json.loads(result.stdout)
    assert "No CLAP outcome recorded" in unknown
    assert "no audio vector" in silent and "5.000 seconds" in silent
    assert "chunk_decode_failed" in failed and "<decoder>" in failed
    assert "45.012 seconds" in success and "Windows embedded: 6" in success
    assert "FAISS committed; Qdrant committed" in success
    assert "historical outcome" in historical and "unconfirmed" in historical
    assert "renderAudioSearchEvidence(overviewDiv, scene.clap_meta)" in _function_source("renderInspector")


@pytest.mark.parametrize('outcome,label', [('no_speech','No speech detected'),
    ('no_intelligible_speech','Speech detected; no intelligible words returned'),
    ('runtime_failure','Transcription failed'), ('unclassified','Speech outcome unclassified'),
    (None,'No speech outcome recorded')])
def test_speech_outcome_reaches_loaded_scene_inspector(outcome, label):
    fields = {'transcript_outcome': outcome, 'transcript_meta': {'engine':'wsl_unified', 'model':'medium',
        'speech_detection': {'status':'completed','method':'silero_vad','input_duration_seconds':5,'speech_duration_seconds':0}}}
    observed = _scene_audio_journey(source_kind='audio', scene_overrides=fields)['before']['overviewText']
    assert label in observed
    assert 'Audio analyzed: 5.000 seconds; VAD speech candidates: 0.000 seconds' in observed


def test_speech_evidence_survives_search_result_inspector():
    result = {'scene_id':'other-scene','video_id':'video-one','timeline_video_id':'video-one','source_kind':'audio',
        'transcript_outcome':'no_speech','transcript_outcome_reason':'no_speech_detected',
        'transcript_meta':{'engine':'wsl_unified'},
        'diarization_status':'not_applicable','diarization_note':'no_speech_detected',
        'emotion_status':'not_applicable','emotion_note':'no_speech_detected'}
    observed = _scene_audio_journey(source_kind='audio', action='narrative-result', search_result=result)['before']['overviewText']
    assert 'No speech detected' in observed
    assert 'Transcriber: wsl_unified' in observed
    assert 'Speaker analysis: Not applicable (no speech detected)' in observed
    assert 'Vocal emotion: Not applicable (no speech detected)' in observed
    assert 'calm' not in observed.lower()


@pytest.mark.parametrize('status,note,expected', [
    ('not_applicable','no_speech_detected','Not applicable (no speech detected)'),
    ('skipped','disabled by runtime config','skipped (disabled by runtime config)'),
    ('error','worker failed','error (worker failed)'),
    ('unavailable','model unavailable','unavailable (model unavailable)'),
    ('success',None,'Speaker tracks recorded (unreviewed)'),
])
def test_speech_enrichment_status_survives_dataset_inspector(status, note, expected):
    observed = _scene_audio_journey(source_kind='audio', scene_overrides={
        'diarization_status':status, 'diarization_note':note,
        'emotion_status':status, 'emotion_note':note})['before']['overviewText']
    assert f'Speaker analysis: {expected}' in observed
    if status == 'success':
        assert 'Vocal emotion: Model estimate (not verified emotion)' in observed
    else:
        assert f'Vocal emotion: {expected}' in observed


def test_rejected_no_speech_candidate_remains_reviewable_as_plain_text():
    observed = _scene_audio_journey(source_kind='audio', scene_overrides={
        'transcript_outcome':'no_speech', 'transcript_meta':{'transcription_quality': {
            'status':'completed','threshold':0.6,'rejected_segments':[
                {'text':'<candidate>', 'no_speech_probability':0.9126}]}}})['before']['overviewText']
    assert 'Rejected candidate (91.3% no-speech probability): <candidate>' in observed
    assert 'excluded from the transcript' in observed


def test_mixed_speech_keeps_disputed_words_visible_for_review():
    observed = _scene_audio_journey(source_kind='audio', transcript='quiet family words', scene_overrides={
        'transcript_outcome':'transcript_available', 'transcript_meta':{'transcription_quality': {
            'status':'completed','threshold':0.6,'rejected_segments':[],
            'uncertain_segments':[{'text':'quiet family words', 'no_speech_probability':0.91}]}}})['before']
    assert 'Mixed speech evidence' in observed['overviewText']
    assert 'Review candidate: quiet family words' in observed['overviewText']


def _function_source(name: str) -> str:
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\(", RETRO_JS)
    assert match is not None, f"Missing JavaScript function: {name}"
    opening = RETRO_JS.index("{", match.end())
    depth = 0
    quote: str | None = None
    escaped = False
    line_comment = False
    block_comment = False
    index = opening
    while index < len(RETRO_JS):
        char = RETRO_JS[index]
        following = RETRO_JS[index + 1] if index + 1 < len(RETRO_JS) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and following == "/":
                block_comment = False
                index += 1
        elif quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == "/" and following == "/":
            line_comment = True
            index += 1
        elif char == "/" and following == "*":
            block_comment = True
            index += 1
        elif char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return RETRO_JS[match.start() : index + 1]
        index += 1
    raise AssertionError(f"Unclosed JavaScript function: {name}")


@pytest.mark.parametrize("empty", [False, True])
def test_emotion_rows_select_top_rank_in_their_own_channel(empty: bool) -> None:
    source = "\n".join(_function_source(name) for name in (
        "loadDataset", "buildSceneDialogue", "setIntelFilter", "clearIntelFilter",
        "scenePassesIntelFilter", "renderVideoIntelPanel",
    ))
    harness = r'''
const assert = require('node:assert/strict');
const fixture = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
class Element {
  constructor() { this.children=[]; this.style={}; this.attributes={}; this.textContent=''; }
  set innerHTML(v) { this.children=[]; this.textContent=v; }
  appendChild(el) { this.children.push(el); }
  setAttribute(k,v) { this.attributes[k]=v; }
  addEventListener(k,fn) { this[k]=fn; }
}
const elements = new Map(['intel-audio-emotions','intel-filter-bar'].map(id=>[id,new Element()]));
const document = {getElementById:id=>elements.get(id),createElement:()=>new Element()};
const state = {videos:[],scenes:[],videoMeta:null,intelFilter:null};
const resetOriginalAudio=()=>{}, resetOriginalVideo=()=>{}, ttsStop=()=>{}, drawGraph=()=>{},
  renderInspector=()=>{}, renderEntityFilterChecklist=()=>{}, logDataTrail=()=>{};
const normalizeEntityList=x=>x||[], buildEntityGraph=()=>({nodes:[]});
let selected=[];
const renderTimelineGrid=()=>{selected=state.scenes.filter(scenePassesIntelFilter).map(s=>s.id);};
const scenes = fixture.empty ? [] : [
  {scene_id:'both',audio_emotion:null,audio_emotion_top_candidate:{label:'joy',score:.2},
   audio_emotion_ranking:[{label:'joy',score:.2}],text_emotion_ranking:[{label:'joy',score:.8},{label:'anger',score:.1}]},
  {scene_id:'audio',audio_emotion:'joy',audio_emotion_ranking:[{label:'joy',score:.9}],
   text_emotion_ranking:[{label:'anger',score:.7},{label:'joy',score:.2}]},
  {scene_id:'missing',audio_emotion:null,audio_emotion_ranking:[],text_emotion_ranking:[]},
];
const metadata = fixture.empty ? {} : {
  top_audio_emotion_score_signals:[{emotion:'joy',count:2,average_score:.55}],
  top_text_emotions:[{emotion:'joy',count:1,average_score:.8},{emotion:'anger',count:1,average_score:.7}],
};
const apiGet=async p=>p.endsWith('/scenes')?scenes:{metadata};
console.error=(...args)=>{throw new Error(args.join(' '));};
eval(fixture.source);
(async()=>{
 await loadDataset('retained');
 const rows=()=>elements.get('intel-audio-emotions').children;
 if(fixture.empty) {
   assert.equal(rows().length,0);
   assert.match(elements.get('intel-audio-emotions').textContent,/No emotion data/);
   assert.deepEqual(selected,[]);
   return;
 }
 assert.equal(state.scenes[0].audio_emotion,null,'candidate must not become qualified label');
 assert.equal(state.scenes[1].audio_emotion,'joy');
 assert.equal(rows().length,3,'same label in different channels survives');
 const row=(label)=>rows().find(r=>r.children[0].textContent===label);
 row('Audio: joy').click();
 assert.deepEqual(selected,['both','audio']);
 assert.equal(row('Audio: joy').attributes['aria-pressed'],'true');
 assert.equal(row('Text: joy').attributes['aria-pressed'],'false');
 row('Text: joy').click();
 assert.deepEqual(selected,['both'],'same-label channel switch must not clear filter');
 assert.match(elements.get('intel-filter-bar').children[0].textContent,/text top-ranked/);
 row('Text: anger').click();
 assert.deepEqual(selected,['audio'],'lower ranked text label must not match');
 row('Text: anger').click();
 assert.equal(state.intelFilter,null);
 assert.deepEqual(selected,['both','audio','missing']);
 setIntelFilter('emotion','joy','text');
 elements.get('intel-filter-bar').children[0].click();
 assert.equal(state.intelFilter,null);
 setIntelFilter('sentiment','positive');setIntelFilter('sentiment','positive');
 assert.equal(state.intelFilter,null,'other filter toggles remain compatible');
 setIntelFilter('emotion','joy','audio');await loadDataset('second');
 assert.equal(state.intelFilter,null,'dataset switch clears scoped filter');
})();
'''
    subprocess.run(["node", "-e", harness], input=json.dumps({"source": source, "empty": empty}),
                   text=True, check=True, capture_output=True, cwd=REPO_ROOT)


@pytest.mark.parametrize("case", [
    "positive", "empty", "search-success", "search-error", "newer-search",
    "dataset-success", "dataset-error", "narrative-success", "narrative-error",
])
def test_dataset_switch_clears_search_and_ignores_superseded_responses(case):
    source = "\n".join(_function_source(name) for name in (
        "loadDataset", "buildSceneDialogue", "executeSearch", "executeNarrativeSearch",
    ))
    harness = r'''
const assert = require('node:assert/strict');
const fixture = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const elements = new Map(['query-input','search-status','narrative-summary-container'].map(id =>
  [id,{value:'old query',textContent:'1 ranked candidates',hidden:false}]));
const document = {getElementById:id=>elements.get(id)||null};
const state = {videos:[],scenes:[],graph:{nodes:[],edges:[]},modes:new Set(['text']),
  searchResults:[],searchActive:false,selectedEntities:[],activeVideoId:null,
  datasetGeneration:0,searchGeneration:0,temporalSummaryGeneration:0};
let timeline=[], inspector=null;
const resetOriginalAudio=()=>{},resetOriginalVideo=()=>{},ttsStop=()=>{},drawGraph=()=>{},
  renderEntityFilterChecklist=()=>{},renderVideoIntelPanel=()=>{},logDataTrail=()=>{};
const normalizeEntityList=x=>x||[],buildEntityGraph=()=>({nodes:[],edges:[]}),formatTime=String;
const renderTimelineGrid=()=>{timeline=(state.searchActive?state.searchResults:state.scenes).map(s=>s.scene_id||s.id);};
const renderInspector=()=>{inspector=state.selectedSceneId;};
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const pending=deferred();
let delayedGet=false, delayedPost=false;
const scene=id=>({scene_id:id,source_kind:'image'});
const apiGet=async path=>{
  if(path.endsWith('/timeline/full'))return {};
  if(delayedGet){delayedGet=false;return pending.promise;}
  return [scene(path.includes('/B/')?'B-scene':'A-scene')];
};
const apiPost=async()=>{
  if(delayedPost){delayedPost=false;return pending.promise;}
  return {results:[{scene_id:'new-result',video_id:state.activeVideoId}]};
};
eval(fixture.source);
(async()=>{
  await loadDataset('A');
  const status=elements.get('search-status'),input=elements.get('query-input');
  const assertReset=()=>{
    assert.equal(state.searchActive,false);
    assert.equal(state.lastQuery,'');
    assert.deepEqual(state.searchResults,[]);
    assert.equal(status.textContent,'');assert.equal(status.hidden,true);
    assert.equal(input.value,'');assert.equal(inspector,null);
    assert.equal(elements.get('narrative-summary-container').hidden,true);
  };
  if(['positive','empty'].includes(fixture.case)){
    state.searchActive=true;state.lastQuery='old query';input.value='old query';
    state.searchResults=fixture.case==='positive'?[{scene_id:'A-scene'}]:[];
    state.selectedSceneId='A-scene';status.hidden=false;status.textContent='Old count';
    const load=loadDataset('B');
    assertReset();assert.deepEqual(timeline,[],'old cards clear before network finishes');
    await load;assert.deepEqual(timeline,['B-scene']);
    await loadDataset('A');assertReset();assert.deepEqual(timeline,['A-scene']);
  } else if(fixture.case.startsWith('dataset')){
    delayedGet=true;const old=loadDataset('A');
    await loadDataset('B');await loadDataset('A'); // Same identity, newer request.
    if(fixture.case.endsWith('error'))pending.reject(Error('old load failed'));
    else pending.resolve([scene('stale-A-scene')]);
    await old;assert.deepEqual(timeline,['A-scene']);assertReset();
  } else {
    delayedPost=true;input.value='old query';
    const old=fixture.case.startsWith('narrative')?executeNarrativeSearch():executeSearch();
    if(fixture.case==='newer-search'){
      input.value='new query';await executeSearch();
    } else {await loadDataset('B');await loadDataset('A');}
    if(fixture.case.endsWith('error'))pending.reject(Error('old search failed'));
    else pending.resolve({results:[{scene_id:'stale-result',video_id:'A'}]});
    await old;
    if(fixture.case==='newer-search'){
      assert.equal(state.lastQuery,'new query');assert.deepEqual(timeline,['new-result']);
      assert.match(status.textContent,/1 ranked candidates/);
    } else {assertReset();assert.deepEqual(timeline,['A-scene']);}
  }
})().catch(err=>{console.error(err);process.exitCode=1;});
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps({"source": source, "case": case}),
                            text=True, capture_output=True, cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr


def test_temporal_summary_requires_native_confirmation_before_prepare() -> None:
    execution = _function_source("executeNarrativeSearch")

    assert "window.confirm(" in execution
    assert "if (!approved)" in execution
    assert execution.index("window.confirm(") < execution.index(
        'body: JSON.stringify({ action: "prepare", request: summaryRequest })'
    )


def test_temporal_summary_resubmits_one_exact_normalized_request() -> None:
    execution = _function_source("executeNarrativeSearch")
    request_block = execution[
        execution.index("const summaryRequest = {") : execution.index(
            "summaryBody.className", execution.index("const summaryRequest = {")
        )
    ]

    for field in (
        "entities",
        "start_date",
        "end_date",
        "time_hint",
        "source_file",
        "modality",
        "max_results",
        "grouping",
        "summary_style",
    ):
        assert re.search(rf"\b{field}\s*:", request_block)
    assert 'JSON.stringify({ action: "prepare", request: summaryRequest })' in execution
    assert re.search(
        r"body:\s*JSON\.stringify\(\{\s*"
        r'action:\s*"confirm",\s*'
        r"job_id:\s*jobId,\s*"
        r"epoch_id:\s*preparedScope\.epoch_id,\s*"
        r"request_sha256:\s*preparedScope\.request_sha256,\s*"
        r"execution_policy_sha256:\s*preparedScope\.execution_policy_sha256,\s*"
        r"confirmation_token:\s*confirmationToken,\s*"
        r"request:\s*summaryRequest\s*"
        r"\}\)",
        execution,
    )


def test_temporal_confirmation_token_is_local_and_cleared() -> None:
    execution = _function_source("executeNarrativeSearch")

    assert "let confirmationToken = prepareData && prepareData.confirmation_token;" in execution
    assert "prepareData.confirmation_token = null;" in execution
    assert execution.index("prepareData.confirmation_token = null;") < execution.index(
        "isSafeTemporalSummaryPrepare(prepareData, confirmationToken)"
    )
    assert "finally" in execution
    assert "confirmationToken = null;" in execution
    for line in execution.splitlines():
        if any(
            surface in line
            for surface in (
                "state.",
                "localStorage",
                "sessionStorage",
                "textContent",
                "innerHTML",
                "console.",
                "URLSearchParams",
            )
        ):
            assert "confirmationToken" not in line


def test_temporal_summary_polls_only_encoded_exact_job() -> None:
    poller = _function_source("pollTemporalSummaryJob")

    assert "encodeURIComponent(jobId)" in poller
    assert "isSafeTemporalSummaryJob(job, jobId, expectedScope)" in poller
    assert 'data.status !== job.state' in poller
    assert "state.activeTemporalSummaryJobId = jobId;" in poller
    assert "state.activeTemporalSummaryJobId !== jobId" in poller
    assert "state.activeTemporalSummaryJobId = null;" in poller
    assert "state.temporalSummaryGeneration !== generation" in poller
    assert re.search(
        r"fetch\(\s*`/api/search/temporal/summarize/"
        r"\$\{encodeURIComponent\(jobId\)\}`",
        poller,
    )
    assert "latest" not in poller.lower()


def test_temporal_success_requires_bound_receipt_and_reports_audit_failure() -> None:
    poller = _function_source("pollTemporalSummaryJob")
    validator = _function_source("isSafeTemporalSummaryReceipt")

    assert 'job.state === "succeeded"' in poller
    assert 'isSafeTemporalSummaryReceipt(data.receipt, job, "succeeded")' in poller
    assert '["recorded", "failed"].includes(job.audit_status)' in poller
    assert 'job.audit_status' in poller
    assert 'receipt.schema !== "goodq.temporal-summary-result.v1"' in validator
    assert "receipt.job_id !== job.job_id" in validator
    assert "receipt.request_sha256 !== job.scope.request_sha256" in validator
    assert "receipt.execution_policy_sha256 !== job.scope.execution_policy_sha256" in validator


def test_temporal_terminal_states_are_distinct_and_legacy_sync_path_is_gone() -> None:
    poller = _function_source("pollTemporalSummaryJob")
    execution = _function_source("executeNarrativeSearch")

    for state in ("failed", "interrupted", "expired"):
        assert f'job.state === "{state}"' in poller
    assert 'apiPost("/api/search/temporal/summarize"' not in execution
    assert "summaryResponse.status" not in execution


def test_overlapping_temporal_requests_cannot_reclaim_current_render() -> None:
    execution = _function_source("executeNarrativeSearch")
    poller = _function_source("pollTemporalSummaryJob")

    assert "const narrativeGeneration = state.temporalSummaryGeneration + 1;" in execution
    assert "state.temporalSummaryGeneration = narrativeGeneration;" in execution
    assert execution.count(
        "state.temporalSummaryGeneration !== narrativeGeneration"
    ) >= 6
    assert "generation" in poller.split("{", maxsplit=1)[0]
    assert "state.temporalSummaryGeneration !== generation" in poller


def test_confirm_conflict_preserves_exact_terminal_state() -> None:
    execution = _function_source("executeNarrativeSearch")

    assert "confirmResponse.status === 409" in execution
    assert "isSafeTemporalSummaryJob(conflictJob, jobId, preparedScope)" in execution
    assert 'conflictJob.state === "expired" || conflictJob.state === "failed"' in execution
    assert '"Summary confirmation expired. Start a new confirmed request."' in execution
    assert '"Summary authorization failed. Start a new confirmed request."' in execution


def test_lan_status_denial_stops_polling_and_explains_read_only_mode() -> None:
    api_get = _function_source("apiGet")
    polling = _function_source("pollStatus")

    assert "error.status = response.status;" in api_get
    assert "let shouldContinuePolling = true;" in polling
    assert "err.status === 403" in polling
    assert "shouldContinuePolling = false;" in polling
    assert (
        'headerStatus.textContent = "Status: LAN READ-ONLY — operator telemetry requires loopback";'
        in polling
    )
    assert re.search(
        r"if \(shouldContinuePolling\)\s*\{\s*"
        r"pollingTimeoutId = setTimeout\(pollStatus, currentPollInterval\);",
        polling,
    )


def _status_progress_journey(progress_updates: list[dict]) -> list[dict]:
    """Run the shipped status poller with local status receipts and a small DOM."""
    harness = r'''
const fixture = JSON.parse(require("fs").readFileSync(0, "utf8"));
class Element {
  constructor() {
    this.textContent = ""; this.style = {}; this.hidden = true;
    const classes = new Set();
    this.classList = {add: value => classes.add(value), remove: (...values) => values.forEach(value => classes.delete(value)),
      contains: value => classes.has(value)};
  }
  querySelector() { return title; }
}
const title = new Element();
const elements = new Map();
const document = {getElementById: id => {
  if (!elements.has(id)) elements.set(id, new Element());
  return elements.get(id);
}, querySelector: () => null};
let wasIngesting = false, ingestionStartTime = null, pollingTimeoutId = null,
  currentPollInterval = 3000, manuallyDismissedRunId = null;
const setTimeout = () => 1, clearTimeout = () => {};
let processing;
const apiGet = async path => {
  if (path !== "/api/status") throw new Error("Unexpected status route");
  return {processing};
};
console.warn = (...args) => { throw new Error(args.join(" ")); };
eval(fixture.source);
(async () => {
  const observations = [];
  for (processing of fixture.progress_updates) {
    await pollStatus();
    observations.push({
      label: document.getElementById("progress-scene-count").textContent,
      step: document.getElementById("progress-step").textContent,
      percent: document.getElementById("progress-text").textContent,
      bar: document.getElementById("progress-bar-fill").style.width,
      visible: !document.getElementById("ingestion-progress-widget").hidden,
      failed: document.getElementById("ingestion-progress-widget").classList.contains("failed-state"),
    });
  }
  process.stdout.write(JSON.stringify(observations));
})();
'''
    result = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps({"source": _function_source("pollStatus"), "progress_updates": progress_updates}),
        text=True, check=True, capture_output=True, cwd=REPO_ROOT,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("extension, source_kind", [
    (extension, "image") for extension in ("jpg", "JPEG", "png", "bmp", "gif", "tiff", "webp")
] + [
    (extension, "document") for extension in ("pdf", "txt", "md", "doc", "DOCX")
])
def test_status_polling_uses_source_progress_for_standalone_files(extension, source_kind):
    progress = {
        "active": True, "status": "processing", "run_id": "standalone-run",
        "current_video": f"upload-request_source.{extension}", "current_step": "text_embed",
        "stage": "text_embed", "progress_percent": 46, "scene_index": None, "scenes_total": None,
    }
    observed = _status_progress_journey([
        {"cli_progress": {"active": True, "status": "processing", "run_id": "video-run",
                          "current_video": "clip.mp4", "scene_index": 2, "scenes_total": 5}},
        {"cli_progress": progress},
        {"cli_progress": {**progress, "active": False, "status": "failed", "current_step": None,
                          "errors": [{"message": "Worker unavailable"}]}},
    ])
    assert observed[0]["label"] == "Scene: 2 of 5"
    assert observed[1]["label"] == f"Source: {source_kind}"
    assert observed[1]["step"] == "Step: text_embed"
    assert observed[1]["percent"] == observed[1]["bar"] == "46%"
    assert observed[1]["visible"] is True
    assert observed[2]["label"] == f"Source: {source_kind}"
    assert observed[2]["failed"] is True
    assert observed[2]["percent"] == "46%"


def test_status_polling_labels_document_failure_on_first_poll_with_filename_fallback():
    observed = _status_progress_journey([{
        "current_video": "legacy.DOC", "cli_progress": {
            "active": False, "status": "failed", "run_id": "failed-document",
            "progress_percent": 0, "stage": "retain_source",
        },
    }])[0]
    assert observed["label"] == "Source: document"
    assert observed["failed"] is True
    assert observed["percent"] == "0%"


@pytest.mark.parametrize("error_fields", [
    {},
    {"errors": []},
    {"errors": [{"message": r"failed at C:\private\family.doc token=secret-value"}]},
    {"errors": [{}]},
    {"errors": "unexpected private diagnostic"},
])
def test_status_polling_failure_guidance_keeps_raw_diagnostics_private(error_fields):
    observed = _status_progress_journey([{"cli_progress": {
        "available": True, "active": False, "fresh": True, "status": "failed",
        "current_video": "ingest_request__source.doc", "run_id": "failed-document",
        "current_step": None, "last_observed_step": None,
        "stale_reason": "progress_receipt_not_active", "progress_percent": 0,
        "stage": None, "scene_index": None, "scenes_total": None, **error_fields,
    }}])[0]
    assert observed["step"] == "Step: FAILED - check local processing logs for details"
    assert observed["label"] == "Source: document"
    assert observed["failed"] is True
    assert observed["visible"] is True
    assert observed["percent"] == observed["bar"] == "0%"
    assert "private" not in json.dumps(observed)
    assert "secret-value" not in json.dumps(observed)


@pytest.mark.parametrize("details, expected", [
    ({"scene_index": 3, "scenes_total": 8}, "Scene: 3 of 8"),
    ({"stage": "Processing additional scenes..."}, "Analyzing..."),
    ({"scene_index": "...", "scenes_total": "..."}, "Analyzing..."),
    ({}, "Scene: 0 of ?"),
])
def test_status_polling_preserves_video_scene_progress(details, expected):
    observed = _status_progress_journey([{"cli_progress": {
        "active": True, "status": "processing", "current_video": "clip.mp4", **details,
    }}])[0]
    assert observed["label"] == expected


def test_cognitive_scene_context_renders_persisted_values_as_text() -> None:
    inspector = _function_source("renderInspector")
    cognitive_context = inspector[
        inspector.index("const evidenceList =") : inspector.index("const conflicts =")
    ]

    assert "innerHTML" not in cognitive_context
    for value in ("kind", "ev.value || ev", "axis", "h.claim", "weight"):
        assert f"textContent = {value}" in cognitive_context
    assert "document.createTextNode(role)" in cognitive_context
    assert "document.createTextNode(`${family}claim: `)" in cognitive_context


def _submit_multimodal_search(responses: list[dict], modes: list[str]) -> list[dict]:
    """Run the shipped submit handler, search function and fetch wrapper in Node."""
    registration = RETRO_JS[
        RETRO_JS.index('// Search Form Submission'):
        RETRO_JS.index('// Narrative Form Submission')
    ]
    harness = r'''
const fs = require("fs");
const fixture = JSON.parse(fs.readFileSync(0, "utf8"));
const requests = [];
const logs = [];
const logArgs = [];
let submit;
let response;
const status = { textContent: "", hidden: true };
Object.defineProperty(status, "innerHTML", {
  set() { throw new Error("Search diagnostics must render as text."); }
});
const document = { getElementById(id) {
  if (id === "query-input") return { value: "  garden  " };
  if (id === "search-status") return status;
  if (id === "search-form") return { addEventListener(event, callback) {
    if (event !== "submit") throw new Error("Unexpected search event.");
    submit = callback;
  }};
  return null;
}};
const state = { graph: { nodes: [] }, activeVideoId: "video-1", scenes: [],
  modes: new Set(fixture.modes), searchResults: [] };
const fetch = async (path, options) => {
  requests.push({ path, method: options.method, body: JSON.parse(options.body) });
  return { ok: !response.http_error, status: response.http_error || 200,
    json: async () => response };
};
const renderTimelineGrid = () => {};
const logDataTrail = (...args) => { logs.push(args[4]); logArgs.push(args); };
eval(fixture.source);
(async () => {
  const observations = [];
  for (response of fixture.responses) {
    logs.length = 0;
    logArgs.length = 0;
    let prevented = false;
    submit({ preventDefault() { prevented = true; } });
    await new Promise(resolve => setImmediate(resolve));
    if (!prevented) throw new Error("Submit did not prevent navigation.");
    observations.push({ status: status.textContent, hidden: status.hidden,
      results: state.searchResults, logs: [...logs], logArgs: [...logArgs], request: requests.at(-1) });
  }
  process.stdout.write(JSON.stringify(observations));
})().catch(error => { console.error(error); process.exitCode = 1; });
'''
    result = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps({
            "source": "\n".join((
                _function_source("apiPost"), _function_source("executeSearch"), registration
            )),
            "responses": responses,
            "modes": modes,
        }),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


@pytest.mark.parametrize("actions,expected", [
    (["all"], ["text", "visual", "audio"]),
    (["visual", "audio", "text"], ["text"]),
    (["text", "all", "all"], ["text", "visual", "audio"]),
])
def test_mode_controls_always_keep_searchable_evidence(actions, expected):
    registration = RETRO_JS[RETRO_JS.index('// Modality Mode selector buttons mapping'):
                            RETRO_JS.index('      })\n      .catch', RETRO_JS.index('// Modality Mode selector buttons mapping'))]
    harness = r'''
const fs = require('fs');
const fixture = JSON.parse(fs.readFileSync(0, 'utf8'));
const state = { modes: new Set(['text', 'visual', 'audio']) };
const buttons = ['text', 'visual', 'audio', 'all'].map(mode => {
  let active = true;
  return { mode, attrs: {}, getAttribute: () => mode,
    setAttribute(key, value) { this.attrs[key] = value; },
    classList: { contains: () => active, toggle(name, force) {
      active = force === undefined ? !active : force; return active;
    } }, addEventListener(event, callback) { this.click = callback; }
  };
});
const document = { querySelectorAll: () => buttons,
  querySelector: () => buttons.find(b => b.mode === 'all') };
eval(fixture.source);
for (const action of fixture.actions) buttons.find(b => b.mode === action).click();
process.stdout.write(JSON.stringify({modes: [...state.modes],
  buttons: buttons.map(b => ({ mode: b.mode, active: b.classList.contains('active'), pressed: b.attrs['aria-pressed'] }))}));
'''
    result = subprocess.run(['node', '-e', harness], input=json.dumps({
        'source': registration, 'actions': actions,
    }), cwd=REPO_ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed['modes'] == expected
    for button in observed['buttons']:
        active = len(expected) == 3 if button['mode'] == 'all' else button['mode'] in expected
        assert button['active'] == active
        assert button['pressed'] == str(active).lower()


@pytest.mark.parametrize(
    ("diagnostic_status", "wording"),
    [("unavailable", "unavailable"), ("error", "failed"), ("disabled", "disabled")],
)
@pytest.mark.parametrize("has_text_match", [False, True])
def test_search_diagnostics_report_incomplete_results_from_submit(
    diagnostic_status: str, wording: str, has_text_match: bool
) -> None:
    results = [{"video_id": "video-1", "scene_id": "scene-1", "matched_modes": ["text"]}] if has_text_match else []
    modes = ["visual", "text"] if has_text_match else ["visual"]
    observed = _submit_multimodal_search([{
        "results": results,
        "diagnostics": {"visual": {
            "status": diagnostic_status,
            "label": "untrusted diagnostic label",
            "reason": "private model path and backend exception",
        }},
    }], modes)[0]

    expected = f"Visual search {wording}."
    if has_text_match:
        expected = "Search incomplete: " + expected
    assert observed["status"] == expected + f" {len(results)} ranked candidates for this source. Similarity does not confirm a match."
    assert observed["hidden"] is False
    assert observed["results"] == results
    assert not any("No results found" in entry for entry in observed["logs"])
    assert expected in observed["logs"]
    assert observed["request"] == {
        "path": "/api/search/multimodal", "method": "POST",
        "body": {"query": "garden", "modalities": modes, "top_k": 50},
    }


@pytest.mark.parametrize("diagnostic_status", ["ready", "no_results"])
def test_search_diagnostics_clear_failure_after_success(diagnostic_status: str) -> None:
    observed = _submit_multimodal_search([
        {"results": [], "diagnostics": {"visual": {"status": "unavailable"}}},
        {"results": [], "diagnostics": {"visual": {"status": diagnostic_status}}},
    ], ["visual"])

    assert observed[0]["hidden"] is False
    assert observed[1]["hidden"] is False
    assert observed[1]["status"] == "0 ranked candidates for this source. Similarity does not confirm a match."
    assert "No results found for active dataset." in observed[1]["logs"]


def test_search_diagnostics_ignore_unrequested_modality() -> None:
    observed = _submit_multimodal_search([{
        "results": [], "diagnostics": {"visual": {"status": "disabled"}},
    }], ["text"])[0]

    assert observed["hidden"] is False
    assert observed["status"] == "0 ranked candidates for this source. Similarity does not confirm a match."
    assert "No results found for active dataset." in observed["logs"]


@pytest.mark.parametrize(("status", "notice"), [
    ("fallback", "Document passage ranking unavailable; showing the original search passages."),
    ("limited", "Document passage ranking covered a limited candidate set."),
])
def test_document_passage_ranking_notice_preserves_results_and_clears(status, notice):
    match = {"video_id": "video-1", "scene_id": "scene-1", "matched_modes": ["text"]}
    observed = _submit_multimodal_search([
        {"results": [match], "diagnostics": {"text_passages": {
            "status": status, "label": "untrusted <script>", "reason": "private backend details",
        }}},
        {"results": [match], "diagnostics": {"text_passages": {"status": "ok"}}},
    ], ["text"])
    suffix = "1 ranked candidates for this source. Similarity does not confirm a match."
    assert observed[0]["status"] == notice + " " + suffix
    assert observed[0]["results"] == [match]
    assert notice in observed[0]["logs"]
    assert observed[1]["status"] == suffix


def test_document_passage_ranking_notice_ignores_unrequested_text():
    observed = _submit_multimodal_search([{
        "results": [], "diagnostics": {"text_passages": {"status": "fallback"}},
    }], ["audio"])[0]
    assert observed["status"] == "0 ranked candidates for this source. Similarity does not confirm a match."


def test_search_diagnostics_preserve_audio_matches_and_report_both_failures() -> None:
    match = {"video_id": "video-1", "scene_id": "scene-1", "matched_modes": ["audio"]}
    observed = _submit_multimodal_search([
        {"results": [match], "diagnostics": {
            "visual": {"status": "unavailable"}, "audio": {"status": "ready"},
        }},
        {"results": [], "diagnostics": {
            "visual": {"status": "unavailable"}, "audio": {"status": "error"},
        }},
    ], ["visual", "audio"])

    assert observed[0]["results"] == [match]
    assert observed[0]["status"] == "Search incomplete: Visual search unavailable. 1 ranked candidates for this source. Similarity does not confirm a match."
    assert observed[1]["status"] == "Search incomplete: Visual search unavailable. Audio search failed. 0 ranked candidates for this source. Similarity does not confirm a match."
    assert not any("No results found" in entry for entry in observed[1]["logs"])


def test_search_diagnostics_report_request_failure() -> None:
    observed = _submit_multimodal_search([{"http_error": 503}], ["visual"])[0]

    assert observed["hidden"] is False
    assert observed["status"] == "Search failed. Try again."
    assert not any("No results found" in entry for entry in observed["logs"])


@pytest.mark.parametrize("confidence", [None, 0.0, 0.83])
def test_search_trail_passes_rank_separately_from_evidence_confidence(confidence):
    observed = _submit_multimodal_search([{"results": [{
        "video_id": "video-1", "scene_id": "scene-1", "score": 0.51,
        "confidence": {"overall": confidence}, "modalities": ["text"],
    }]}], ["text"])[0]
    candidate = next(args for args in observed["logArgs"] if args[4].startswith("Ranked candidate"))
    assert candidate[5] == confidence
    assert candidate[7] == 0.51
    assert observed["logArgs"][0][5] is None


def test_data_trail_renders_rank_label_without_inventing_confidence():
    source = "\n".join(_function_source(n) for n in ("logDataTrail", "appendText", "safeString"))
    harness = r'''
const source=JSON.parse(require('fs').readFileSync(0,'utf8'));
class Element {
 constructor(){this.children=[];this.textContent='';}
 appendChild(c){this.children.push(c);} prepend(c){this.children.unshift(c);}
 querySelector(){return null;}
}
const container=new Element();
const document={getElementById:()=>container,createElement:()=>new Element()};
eval(source);
logDataTrail('absent event','/search','fixture','text','candidate',null,'',0.51);
logDataTrail('supported','/search','fixture','text','candidate',0,'',0.7);
const read=e=>[e.textContent,...e.children.flatMap(read)];
process.stdout.write(JSON.stringify(container.children.map(read)));
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps(source),
        capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, timeout=20, check=True)
    explicit, unavailable = json.loads(result.stdout)
    assert "Ranking score (not confidence):" in unavailable
    assert "0.51" in unavailable
    assert "Confidence:" not in unavailable
    assert "Confidence:" in explicit and "0" in explicit
    assert "Ranking score (not confidence):" in explicit and "0.7" in explicit


def test_search_diagnostics_status_is_accessible_in_search_form() -> None:
    html = (REPO_ROOT / "ui" / "retro_console_v1" / "index.html").read_text(encoding="utf-8")
    form = html[html.index('<form id="search-form"'):]
    form = form[:form.index("</form>")]
    assert re.search(r'id="search-status"[^>]*role="status"[^>]*aria-live="polite"', form)


def test_transcript_inspector_preserves_turn_assignments_and_unattributed_words():
    rows = [
        {"start": 0.2, "end": 1.4, "speaker": "SPEAKER_01", "text": "Did you bring it?"},
        {"start": 1.1, "end": 2.0, "speaker": "SPEAKER_00", "text": "Yes, right here."},
        {"start": 2.2, "end": 2.8, "speaker": None, "text": "Thank you."},
    ]
    observed = _scene_audio_journey(transcript="Did you bring it? Yes, right here. Thank you.",
        scene_overrides={"dominant_speaker_id": "SPEAKER_00", "transcript_meta": {"segments": rows}})["before"]
    assert observed["transcriptRows"] == [
        {"speaker": "SPEAKER_01 (unreviewed): ", "text": "Did you bring it?"},
        {"speaker": "SPEAKER_00 (unreviewed): ", "text": "Yes, right here."},
        {"speaker": "Unattributed: ", "text": "Thank you."},
    ]
    assert "not confirmed identities" in observed["transcriptText"]


@pytest.mark.parametrize("segments", [None, [], "invalid", [None],
    [{"speaker": "A", "text": "Only part."}],
    [{"speaker": "A", "text": "Wrong words."}],
])
def test_transcript_missing_or_incomplete_turns_never_assign_dominant_speaker(segments):
    observed = _scene_audio_journey(transcript="Only part. Remaining words.",
        scene_overrides={"dominant_speaker_id": "SPEAKER_00", "speaker_count": 1,
                         "transcript_meta": {"segments": segments}})["before"]
    assert observed["transcriptRows"] == [{"speaker": "Unattributed: ", "text": "Only part. Remaining words."}]


def test_transcript_turns_preserve_single_speaker_and_whitespace_without_dropping_text():
    observed = _scene_audio_journey(transcript="First line.\nSecond line.", scene_overrides={
        "transcript_meta": {"segments": [
            {"speaker": "A", "text": "First line."}, {"speaker": "A", "text": "Second line."}]}})["before"]
    assert [r["text"] for r in observed["transcriptRows"]] == ["First line.", "Second line."]
    assert all(r["speaker"] == "A (unreviewed): " for r in observed["transcriptRows"])


def test_transcript_search_result_uses_its_own_turn_evidence():
    result = {"scene_id": "other-scene", "video_id": "video-one", "source_kind": "audio",
        "evidence": {"transcript": "Hello there. Good morning."},
        "transcript_meta": {"segments": [{"speaker": "B", "text": "Hello there."},
                                            {"speaker": "C", "text": "Good morning."}]}}
    observed = _scene_audio_journey(action="narrative-result", search_result=result)["before"]
    assert observed["transcriptRows"] == [
        {"speaker": "B (unreviewed): ", "text": "Hello there."},
        {"speaker": "C (unreviewed): ", "text": "Good morning."}]


def test_transcript_empty_does_not_promote_stale_segments():
    observed = _scene_audio_journey(transcript="", scene_overrides={
        "transcript_meta": {"segments": [{"speaker": "A", "text": "Rejected candidate."}]}})["before"]
    assert observed["transcriptRows"] == []
    assert "Rejected candidate." not in observed["transcriptText"]


def _scene_audio_journey(*, endpoint=None, available=True, transcript="", action="inspect", scene_id="scene-hash",
                         video_endpoint="/api/media/video/video-one/source", video_available=True,
                         source_start=120.0, duration=180.0, video_width=640,
                         desktop_available=True, desktop_state="starting", desktop_failure=None,
                         desktop_done_failure=None, source_kind="video", document_text=None,
                         scene_overrides=None, search_result=None, search_next=None):
    html = (REPO_ROOT / "ui/retro_console_v1/index.html").read_text(encoding="utf-8")
    names = (
        "apiGet", "apiPost", "executeSearch", "loadDataset", "renderTimelineGrid", "appendIdentitySearchEvidence", "selectScene", "renderSpeechEvidence", "renderAcousticEvidence", "renderAudioSearchEvidence", "renderInspector",
        "renderVideoSelector", "objectEvidenceLabel", "renderStoredRelationships",
        "singleSelectEntity", "resolveGraphEntityId", "normalizeEntityList", "normalizeEntityName", "formatTime",
        "appendText", "safeString", "scenePassesIntelFilter", "formatEntityLabel", "resolveKeyframeUrl",
        "ttsStop", "ttsSpeak", "ttsPlayAll", "ttsPlayRow", "ttsVoiceLabel",
        "resetOriginalAudio", "pauseOriginalAudio", "renderOriginalAudio",
        "resetOriginalVideo", "pauseOriginalVideo", "renderOriginalVideo",
        "renderStandaloneSource", "buildSceneDialogue",
        "desktopPlayerCommand", "desktopPlayerWindow",
    )
    source = "\n".join(_function_source(name) for name in names
                       if re.search(rf"function\s+{name}\s*\(", RETRO_JS))
    for state_name in ("originalAudio", "originalVideo"):
        media_state = re.search(rf"const {state_name} = \{{.*?\n  \}};", RETRO_JS, re.S)
        if media_state:
            source = media_state.group(0) + "\n" + source
    harness = r'''
const fixture = JSON.parse(require("fs").readFileSync(0, "utf8"));
class Element {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {};
    this.style = {}; this.attributes = {}; this.className = ""; this.hidden = false;
    this.paused = true; this.currentTime = 0; this.pauseCount = 0;
    this.classList = { add() {}, remove() {}, toggle() {}, contains() { return false; } };
  }
  set innerHTML(value) { this.children = []; this.textContent = value; }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { this.children.push(...children); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? this[key] ?? null; }
  removeAttribute(key) { delete this.attributes[key]; if (key === "src") this.src = ""; }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  dispatch(name) {
    if (name === "play") this.paused = false;
    const event = { preventDefault() {}, stopPropagation() {}, target: this };
    for (const callback of this.listeners[name] || []) callback(event);
    if (this["on" + name]) this["on" + name](event);
  }
  pause() { this.paused = true; this.pauseCount++; this.dispatch("pause"); }
  play() { this.dispatch("play"); return Promise.resolve(); }
  getBoundingClientRect() { return { x: 720, y: 180, width: 340, height: 210 }; }
  load() {}
  scrollIntoView() {}
  querySelector() { return null; }
}
const elements = new Map(fixture.ids.map(id => [id, new Element()]));
function descendants() {
  const found = new Set();
  const visit = el => { if (!found.has(el)) { found.add(el); el.children.forEach(visit); } };
  elements.forEach(visit); return [...found];
}
const document = {
  getElementById: id => id === "graph-canvas" ? null : elements.get(id) || null,
  createElement: tag => new Element(tag),
  createTextNode: text => Object.assign(new Element("#text"), { textContent: text }),
  querySelectorAll: selector => descendants().filter(el => selector.startsWith(".")
    ? (el.className || "").split(" ").includes(selector.slice(1).split("[")[0])
    : el.tagName === selector.toUpperCase()),
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; },
};
const speech = [];
const timers = new Map(); let timerId = 0;
const setTimeout = callback => { timers.set(++timerId, callback); return timerId; };
const clearTimeout = id => timers.delete(id);
const window = { location: { origin: "http://127.0.0.1:30000" }, getSelection: () => "",
  screenX: 10, screenY: 20, outerHeight: 900, innerHeight: 820,
  screen: { availLeft: 0, availTop: 0, availWidth: 1920, availHeight: 1080 },
  speechSynthesis: { cancel() { speech.push("cancel"); }, speak(utterance) { speech.push(utterance.text); } } };
class SpeechSynthesisUtterance { constructor(text) { this.text = text; } }
const tts = { supported: true, voices: [], voice: null, playing: false };
const state = { videos: [{video_id: "video-one", source_kind: fixture.scenes[0].source_kind, phase6_complete: false}], scenes: [], graph: { nodes: [] }, searchResults: [],
  selectedEntities: [], modes: new Set(["text"]), activeSearchTab: "multimodal", selectedSceneId: null, selectedEntity: null };
const requests = [];
const commands = []; let desktopResolve;
const desktopSnapshot = () => ({ available: fixture.desktopAvailable, state: fixture.desktopState,
  video_id: "video-one", scene_id: String(fixture.scenes[0].scene_id), playback_id: "fixture-playback",
  playing: fixture.desktopState === "playing", error: fixture.desktopAvailable ? null : "Desktop playback is local only." });
const fetch = async (path, options = {}) => {
  requests.push(path);
  if (path === "/api/search/multimodal") return { ok: true, json: async () => ({ results: fixture.searchNext }) };
  if (path.includes("/desktop-player/")) {
    if (options.method === "POST") commands.push({ path, body: JSON.parse(options.body) });
    if (path.endsWith("/play") && fixture.action.includes("pending")) {
      await new Promise(resolve => { desktopResolve = resolve; });
    }
    const failed = path.endsWith("/play") ? fixture.desktopFailure : path.endsWith("/done") ? fixture.desktopDoneFailure : null;
    return { ok: !failed, status: failed ? 404 : 200, json: async () => failed
      ? { detail: failed } : desktopSnapshot() };
  }
  return { ok: true, json: async () => path.endsWith("/scenes")
    ? { scenes: fixture.scenes } : { metadata: {} } };
};
const buildEntityGraph = () => ({ nodes: [] });
const drawGraph = () => {};
const renderEntityFilterChecklist = () => {};
const renderVideoIntelPanel = () => {};
const trailEntries = [];
const logDataTrail = (...args) => trailEntries.push(args);
const switchInspectorTab = () => {};
console.error = (...args) => { throw new Error(args.join(" ")); };
let waitForDesktopReturn;
eval(fixture.source + '\nwaitForDesktopReturn = () => originalVideo.desktop.doneAndWait();');
const audio = () => document.querySelector("audio");
const video = () => document.querySelector("video");
const status = (kind = "audio") => {
  const panel = document.getElementById("inspector-original-" + kind);
  const visit = el => [el.textContent || "", ...el.children.map(visit)].join(" ");
  return panel ? visit(panel) : "";
};
const inspect = () => ({ src: audio()?.src || null, paused: audio()?.paused,
  trailEntries: [...trailEntries],
  entityText: descendants().map(el => el.textContent || "").join(" "),
  contextLogs: (() => { const visit = el => [el.textContent || "", ...el.children.map(visit)].join(" "); return visit(document.getElementById("inspector-details-logs")); })(),
  overviewText: (() => { const visit = el => [el.textContent || "", ...el.children.map(visit)].join(" "); return visit(document.getElementById("inspector-details-overview")); })(),
  transcriptText: (() => { const visit = el => [el.textContent || "", ...el.children.map(visit)].join(" "); return visit(document.getElementById("inspector-transcript-zone")); })(),
  transcriptRows: document.querySelectorAll(".transcript-row").map(row => ({
    speaker: row.children.find(el => el.className === "transcript-speaker")?.textContent,
    text: row.children.find(el => el.className === "transcript-text")?.textContent })),
  cardSummary: document.querySelector(".scene-card-summary")?.textContent || null,
  cardQualification: document.querySelector(".scene-card-summary-qualification")?.textContent || null,
  overviewSummary: document.querySelector(".details-summary")?.textContent || null,
  loadedObjectDetails: state.scenes[0]?.object_details || [],
  selectorLabels: document.getElementById("dataset-select").children.map(el => el.textContent),
  partialVisible: !document.getElementById("active-ingestion-badge").hidden,
  cardPartialCount: document.querySelectorAll(".ingestion-active-badge").length,
  timing: document.getElementById("inspector-keyframe-timecode").textContent,
  sourceLink: document.querySelector("a")?.href || null,
  documentText: document.querySelector(".document-text-block")?.textContent || null,
  matchedDocumentText: document.querySelector(".document-match-block")?.textContent || null,
  matchedDocumentMarkup: document.querySelector(".document-match-block")?.innerHTML || null,
  documentContextText: document.querySelector(".document-context-block")?.textContent || null,
  documentContextMarkup: document.querySelector(".document-context-block")?.innerHTML || null,
  lexicalDocumentText: document.querySelector(".document-lexical-block")?.textContent || null,
  lexicalDocumentMarkup: document.querySelector(".document-lexical-block")?.innerHTML || null,
  imageSource: document.getElementById("inspector-keyframe-img").src || null,
  currentTime: audio()?.currentTime, status: status(), speech: [...speech],
  video: { src: video()?.src || null, paused: video()?.paused ?? null,
    currentTime: video()?.currentTime ?? null, status: status("video"),
    playButton: document.querySelector(".original-video-play")?.textContent || null,
    playDisabled: document.querySelector(".original-video-play")?.disabled ?? null,
    doneHidden: document.querySelector(".original-video-done")?.hidden ?? true,
    keyframeHidden: document.getElementById("inspector-keyframe-zone").hidden },
  ttsLabel: document.querySelector(".tts-play-all-btn")?.textContent || null });
(async () => {
  renderVideoSelector();
  await loadDataset("video-one");
  const grid = document.getElementById("timeline-grid");
  if (fixture.searchResult) {
    state.searchActive = true;
    if (fixture.action === "narrative-result") state.activeSearchTab = "narrative";
    state.searchResults = [fixture.searchResult];
    renderTimelineGrid();
  }
  grid.children[0].dispatch("click");
  const before = inspect();
  const settle = async () => { for (let index = 0; index < 15; index++) await Promise.resolve(); };
  if (fixture.action === "clear-document-search") {
    state.searchActive = false;
    renderInspector();
  }
  if (fixture.action === "next-document-search") {
    document.getElementById("query-input").value = "new passage";
    await executeSearch();
  }
  if (fixture.action.startsWith("desktop")) {
    if (fixture.action.includes("cross")) {
      state.searchActive = true; state.activeSearchTab = "narrative";
      state.searchResults = [{ scene_id: 0, video_id: "video-two", start_time: 40,
        original_video_endpoint: "/api/media/video/video-two/source", original_video_available: true }];
      renderTimelineGrid(); grid.children[0].dispatch("click");
    }
    const old = video();
    if (old) {
      old.duration = fixture.duration; old.videoWidth = fixture.videoWidth; old.videoHeight = fixture.videoWidth ? 360 : 0;
      old.dispatch("loadedmetadata"); old.dispatch("loadeddata");
    }
    await settle();
    const passive = { ...inspect(), commands: [...commands] };
    if (!fixture.action.includes("quiet")) document.querySelector(".original-video-play")?.dispatch("click");
    await settle();
    if (fixture.action.includes("decode")) {
      old.error = { code: 3 }; old.dispatch("error"); old.dispatch("error"); await settle();
    }
    const launched = inspect();
    if (fixture.action.includes("audio")) audio()?.dispatch("play");
    if (fixture.action.includes("tts")) document.querySelector(".tts-play-all-btn")?.dispatch("click");
    if (fixture.action.includes("done")) document.querySelector(".original-video-done")?.dispatch("click");
    if (fixture.action.includes("reset") || (fixture.action.includes("pending") && !fixture.action.includes("return"))) grid.children[1].dispatch("click");
    if (fixture.action.includes("entity")) singleSelectEntity("someone");
    if (fixture.action.includes("dataset")) await loadDataset("video-two");
    let returnReady, returnPending;
    const returning = fixture.action.includes("return") ? waitForDesktopReturn().then(result => { returnReady = result; }) : null;
    await settle();
    if (returning) returnPending = returnReady === undefined;
    if (desktopResolve) desktopResolve();
    if (returning) await returning;
    await settle();
    if (fixture.action.includes("retry")) {
      fixture.desktopDoneFailure = null;
      document.querySelector(".original-video-done")?.dispatch("click");
      await settle();
    }
    if (fixture.action.includes("poll")) {
      fixture.desktopState = "playing";
      for (const [id, callback] of [...timers]) { timers.delete(id); callback(); }
      await settle();
    }
    process.stdout.write(JSON.stringify({ before, passive, launched, after: inspect(), commands,
      requests, timers: timers.size, returnReady, returnPending })); return;
  } else if (fixture.action.startsWith("video") && video()) {
    const old = video();
    old.duration = fixture.duration;
    old.videoWidth = fixture.videoWidth; old.videoHeight = fixture.videoWidth ? 360 : 0;
    if (fixture.action === "video-seek-error") Object.defineProperty(old, "currentTime", {
      get() { return 0; }, set() { throw new Error("Fixture seek failure"); }
    });
    old.dispatch("loadedmetadata"); old.dispatch("loadeddata");
    if (fixture.action === "video-error") {
      old.error = { code: 4 }; old.dispatch("error"); old.pause();
    } else if (fixture.action === "video-lifecycle") {
      const lateError = old.onerror; const lateMetadata = old.onloadedmetadata;
      old.dispatch("play"); old.dispatch("playing");
      audio().dispatch("play");
      const audioPausedVideo = old.paused;
      old.dispatch("play");
      const videoPausedAudio = audio().paused;
      document.querySelector(".tts-play-all-btn").dispatch("click");
      const ttsPausedVideo = old.paused;
      old.dispatch("play");
      const videoStoppedTts = !tts.playing;
      grid.children[1].dispatch("click");
      const switched = inspect();
      if (lateError) lateError({ target: old });
      if (lateMetadata) lateMetadata({ target: old });
      const staleIgnored = status("video") === switched.video.status;
      const next = video(); next.dispatch("play"); singleSelectEntity("someone");
      const entityStopped = next.paused && !next.src;
      selectScene(fixture.scenes[0].scene_id);
      const last = video(); last.dispatch("play"); await loadDataset("video-two");
      process.stdout.write(JSON.stringify({ before, audioPausedVideo, videoPausedAudio,
        ttsPausedVideo, videoStoppedTts, oldStopped: old.paused && !old.src, staleIgnored,
        entityStopped, datasetStopped: last.paused && !last.src })); return;
    } else if (fixture.action === "video-once") {
      const firstSeek = old.currentTime;
      old.currentTime = 135; old.dispatch("loadedmetadata");
      process.stdout.write(JSON.stringify({ before, firstSeek, after: inspect() })); return;
    }
  } else if (fixture.action === "word-seek" && audio()) {
    const seek = document.querySelector(".word-timing-seek");
    seek.dispatch("click");
    const aligned = inspect();
    grid.children[1].dispatch("click");
    seek.dispatch("click");
    process.stdout.write(JSON.stringify({before, aligned, after:inspect()})); return;
  } else if (fixture.action === "error" && audio()) {
    audio().error = { code: 4 }; audio().dispatch("error"); audio().pause();
  } else if (fixture.action === "lifecycle" && audio()) {
    const old = audio(); const lateError = old.onerror;
    old.dispatch("play"); old.dispatch("playing");
    document.querySelector(".tts-play-all-btn").dispatch("click");
    const ttsPausedAudio = old.paused;
    old.dispatch("play"); old.dispatch("playing");
    grid.children[1].dispatch("click");
    const switched = inspect();
    if (lateError) lateError({ target: old });
    const staleIgnored = status() === switched.status;
    const next = audio(); next.dispatch("play"); singleSelectEntity("someone");
    const entityStopped = next.paused && !next.src;
    selectScene(fixture.scenes[0].scene_id);
    const last = audio(); last.dispatch("play"); await loadDataset("video-two");
    process.stdout.write(JSON.stringify({ before, ttsPausedAudio, oldStopped: old.paused && !old.src,
      staleIgnored, entityStopped, datasetStopped: last.paused && !last.src, switched, speech })); return;
  } else if (fixture.action === "music-switch") {
    grid.children[1].dispatch("click");
  } else if (fixture.action.startsWith("cross")) {
    const sceneId = fixture.action === "cross" ? "other-scene" : fixture.scenes[0].scene_id;
    state.searchResults = [{ scene_id: sceneId, source_file: "other.mp4", start_time: 40, end_time: 45,
      original_audio_endpoint: fixture.crossEndpoint, original_audio_available: !!fixture.crossEndpoint,
      original_video_endpoint: fixture.crossVideoEndpoint,
      original_video_available: !!fixture.crossVideoEndpoint }];
    if (fixture.action === "cross") selectScene(sceneId);
    else {
      state.searchActive = true; state.activeSearchTab = "narrative";
      renderTimelineGrid(); grid.children[0].dispatch("click");
    }
    if (video()) { video().duration = fixture.duration; video().dispatch("loadedmetadata"); }
  }
  process.stdout.write(JSON.stringify({ before, after: inspect(), requests }));
})().catch(error => { process.stderr.write(error.stack); process.exitCode = 1; });
'''
    if endpoint is None:
        endpoint = f"/api/media/video/video-one/scene/{scene_id}/audio"
    scene = {"scene_id": scene_id, "video_id": "video-one", "start": source_start, "end": 125.0,
             "source_kind": source_kind, "document_text": document_text,
             "original_source_endpoint": video_endpoint, "original_source_available": video_available,
             "representative_frame_endpoint": video_endpoint if source_kind == "image" else None,
             "audio_chunks": [], "original_audio_endpoint": endpoint,
             "original_audio_available": available, "transcript": transcript,
             "original_video_endpoint": video_endpoint, "original_video_available": video_available}
    scene.update(scene_overrides or {})
    second = {**scene, "scene_id": "second-hash", "original_audio_endpoint":
              "/api/media/video/video-one/scene/second-hash/audio"}
    if action == "music-switch":
        second["music_events"] = []
    result = subprocess.run(["node", "-e", harness], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
                            input=json.dumps({"source": source, "ids": re.findall(r'id="([^"]+)"', html),
                                              "scenes": [scene, second], "action": action, "duration": duration,
                                              "searchResult": search_result,
                                              "searchNext": search_next,
                                              "videoWidth": video_width,
                                              "desktopAvailable": desktop_available,
                                              "desktopState": desktop_state,
                                              "desktopFailure": desktop_failure,
                                              "desktopDoneFailure": desktop_done_failure,
                                              "crossVideoEndpoint": "/api/media/video/video-two/source"
                                              if action in ("cross", "cross-card") and video_available else None,
                                              "crossEndpoint": (endpoint if available else None) if action == "cross"
                                              else "/api/media/video/video-two/scene/scene-hash/audio" if action == "cross-card" else None}),
                            check=False, timeout=20)
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_clap_outcome_survives_dataset_load_and_scene_selection():
    observed = _scene_audio_journey(scene_overrides={"clap_meta": {
        "status": "skipped", "reason": "audio_silent", "input_policy": "full_scene", "duration_sec": 5,
    }})["before"]
    assert "Silence / below energy threshold" in observed["overviewText"]
    assert "no audio vector" in observed["overviewText"]
    assert "5.000 seconds" in observed["overviewText"]


def test_search_result_inspector_keeps_its_own_clap_outcome():
    observed = _scene_audio_journey(action="narrative-result", search_result={
        "scene_id": "another-scene", "video_id": "another-video", "start_time": 0, "end_time": 5,
        "clap_meta": {"status": "error", "reason": "chunk_decode_failed", "input_policy": "full_scene"},
    })["before"]
    assert "chunk_decode_failed" in observed["overviewText"]
    assert "No CLAP outcome recorded" not in observed["overviewText"]


@pytest.mark.parametrize("conflict_flag", [False, None, True])
def test_scene_context_conflicts_and_unresolved_axes_survive_actual_inspector(conflict_flag):
    epistemic = {"state": "partially_supported", "evidence_family": "transcript+audio",
                 "evidence": [{"kind": "transcript_topic", "role": "support", "value": "<topic>"}]}
    if conflict_flag is not None:
        epistemic["conflict_detected"] = conflict_flag
    observed = _scene_audio_journey(scene_overrides={
        "scene_context_llm": {"primary_tags": ["<topic>"]},
        "scene_context_epistemic": epistemic,
        "scene_context_arbitration": {"resolved_by": "transcript", "unresolved_axes": ["tone"],
            "evidence_conflicts": [{"axis": "tone", "reason": "audio_emotion_not_reflected"}]},
    })["before"]
    assert "CLEAR (No conflicts)" not in observed["contextLogs"]
    assert "CONFLICTS / UNRESOLVED AXES PRESENT" in observed["contextLogs"]
    assert "Unresolved axes: tone" in observed["contextLogs"]
    assert "Unresolved: tone" in observed["overviewText"]
    assert "Arbitration basis: transcript" in observed["overviewText"]
    assert "Stored model assessment; not verified scene facts." in observed["overviewText"]
    assert "<topic>" in observed["contextLogs"]


def test_scene_context_unknown_and_missing_flags_do_not_invent_clear_state():
    observed = _scene_audio_journey(scene_overrides={
        "scene_context_llm": {"primary_tags": []},
        "scene_context_epistemic": {"state": "unknown", "limits": ["evidence_coverage_limited"]},
    })["before"]
    assert "Not recorded" in observed["contextLogs"]
    assert "evidence_coverage_limited" in observed["contextLogs"]
    absent = _scene_audio_journey()["before"]
    assert "Cognitive Arbitration" not in absent["contextLogs"]


def test_scene_selection_log_does_not_claim_verified_narrative():
    observed = _scene_audio_journey(scene_overrides={"visual_caption": "A model caption"})["before"]
    selected = [entry for entry in observed["trailEntries"] if entry[0].startswith("Select Scene #")]
    assert len(selected) == 1
    assert selected[0][1] == "Scene inspection / source linkage"
    assert selected[0][4] == 'Selected scene evidence: "A model caption"'


def test_music_event_cues_survive_dataset_inspector_and_clear_on_selection():
    cues = [{"label": "birthday_song", "start": 40, "end": 43,
             "context": "Happy birthday <cue>", "confidence": 0.7}] * 8
    result = _scene_audio_journey(scene_overrides={"music_events": cues}, action="music-switch")
    text = result["before"]["overviewText"]
    assert "Transcript music/event cues" in text
    assert "8 cue occurrences in this scene" in text
    assert "Transcript-pattern matches; not confirmed events or detected music." in text
    assert text.count("birthday_song") == 8
    assert text.count("Happy birthday <cue>") == 8
    assert "Scene-relative offset: 40–43 s" in text
    assert "Heuristic score: 0.7 (not calibrated confidence)" in text
    after = result["after"]["overviewText"]
    assert "No music/event cues retained for this scene." in after
    assert "Execution status is not available in this view." in after
    assert "birthday_song" not in after


def test_music_event_missing_evidence_does_not_claim_successful_absence():
    text = _scene_audio_journey()["before"]["overviewText"]
    assert "Music/event cue evidence is not recorded for this scene." in text
    assert "Execution status is not available in this view." in text
    assert "No music/event cues retained" not in text


def test_music_event_legacy_cue_does_not_invent_score_or_offset():
    text = _scene_audio_journey(scene_overrides={"music_events": ["singing"]})["before"]["overviewText"]
    assert "1 cue occurrence in this scene" in text
    assert "singing" in text
    assert "Scene-relative offset: not recorded" in text
    assert "Heuristic score: not recorded" in text


def test_scene_card_exposes_original_audio_without_transcript_or_chunk_id():
    result = _scene_audio_journey()["before"]
    assert result["src"] == "/api/media/video/video-one/scene/scene-hash/audio"
    assert result["paused"] is True
    assert result["currentTime"] == 0  # Extracted scene WAV starts at zero, not source time 120.
    assert "Original scene audio" in result["status"]
    assert not any(item != "cancel" for item in result["speech"])
    assert result["partialVisible"] is True
    assert any("[PARTIAL INDEX]" in label for label in result["selectorLabels"])


@pytest.mark.parametrize("kind", ["image", "document", "audio"])
def test_standalone_scene_card_uses_actual_source_controls(kind):
    result = _scene_audio_journey(source_kind=kind, source_start=0,
                                  document_text="Family picnic <script>not markup</script>")["before"]
    assert result["video"]["src"] is None
    assert result["video"]["playButton"] is None
    assert f"Original {kind}" in result["video"]["status"]
    assert result["sourceLink"] == "/api/media/video/video-one/source"
    assert result["partialVisible"] is False
    assert result["cardPartialCount"] == 0
    assert not any("[PARTIAL INDEX]" in label for label in result["selectorLabels"])
    if kind in {"image", "document"}:
        assert result["timing"] == "Static source"
    if kind == "audio":
        assert result["src"] == "/api/media/video/video-one/source"
        assert result["currentTime"] == 0
    elif kind == "image":
        assert result["imageSource"].endswith("/api/media/video/video-one/source")
        assert result["src"] is None
    else:
        assert result["documentText"] == "Family picnic <script>not markup</script>"
        assert result["src"] is None


@pytest.mark.parametrize("text_scope", [None, "main_document_body"])
def test_standalone_document_overview_explains_partial_extraction_scope(text_scope):
    result = _scene_audio_journey(
        source_kind="document", source_start=0, document_text="Family picnic notes",
        scene_overrides={"document_meta": {"text_scope": text_scope} if text_scope else None},
    )["before"]
    note = ("Main document body only. Headers, footers, notes, comments, embedded content "
            "and text in images are not extracted.")
    assert (note in result["overviewText"]) is (text_scope == "main_document_body")
    assert result["documentText"] == "Family picnic notes"


@pytest.mark.parametrize("prefix", ["Early notes. ", "Early \U0001f600 notes. "])
def test_document_search_match_renders_exact_passage_with_offsets_and_clears(prefix):
    text = prefix + "<script>late answer</script>"
    start = text.index("<script>")
    result = _scene_audio_journey(
        source_kind="document", source_start=0, document_text=text,
        action="clear-document-search", search_result={
            "scene_id": "scene-hash", "video_id": "video-one", "source_kind": "document",
            "matched_document_span": {"chunk_index": 7, "char_start": start, "char_end": len(text),
                                      "text": text[start:], "token_count": 8},
        })
    before = result["before"]
    assert before["matchedDocumentText"] == text[start:]
    assert before["matchedDocumentMarkup"] is None
    assert "Matching document passage" in before["overviewText"]
    assert f"Extracted text characters {start}–{len(text)} (start inclusive, end exclusive)." in before["overviewText"]
    assert before["documentText"] == text
    assert before["sourceLink"] == "/api/media/video/video-one/source"
    assert before["timing"] == "Static source"
    assert result["after"]["matchedDocumentText"] is None


@pytest.mark.parametrize("change", [{"char_end": 200}, {"char_start": -1}, {"char_start": "0"},
                                    {"text": "forged answer"}, {"text": ["answer"]}])
def test_document_search_match_rejects_unbound_passage_in_actual_inspector(change):
    span = {"chunk_index": 0, "char_start": 0, "char_end": 6, "text": "answer", "token_count": 1}
    span.update(change)
    result = _scene_audio_journey(source_kind="document", source_start=0, document_text="answer", search_result={
        "scene_id": "scene-hash", "video_id": "video-one", "matched_document_span": span,
    })["before"]
    assert result["matchedDocumentText"] is None
    assert result["documentText"] == "answer"


@pytest.mark.parametrize("change", [None, {}, {"char_start": -1}, {"char_end": 9000},
                                    {"char_start": "0"}, {"text": "forged context"},
                                    {"matched_char_start": 0}, {"matched_char_end": 1}])
def test_document_search_context_is_separate_exact_text_and_clears(change):
    text = "Earlier \U0001f600 evidence. <script>answer</script> Later evidence."
    start, end = text.index("<script>"), text.index(" Later")
    context = {"char_start": 0, "char_end": len(text), "text": text,
               "matched_char_start": start, "matched_char_end": end}
    if change:
        context.update(change)
    result = _scene_audio_journey(source_kind="document", source_start=0, document_text=text,
        action="clear-document-search", search_result={
            "scene_id": "scene-hash", "video_id": "video-one",
            "matched_document_span": {"chunk_index": 0, "char_start": start, "char_end": end,
                                      "text": text[start:end], "token_count": 2},
            "document_context_span": context if change is not None else None,
        })
    before = result["before"]
    assert before["matchedDocumentText"] == text[start:end]
    assert before["documentContextText"] == (text if change == {} else None)
    assert before["documentContextMarkup"] is None
    assert ("Surrounding document context" in before["overviewText"]) == (change == {})
    assert before["documentText"] == text
    assert result["after"]["documentContextText"] is None


@pytest.mark.parametrize("anchor_valid,extra", [(False, 20), (True, 1025), (True, 5000)])
def test_document_search_context_rejects_invalid_anchor_or_unbounded_context(anchor_valid, extra):
    text = "prefix " + "answer " + "x" * extra
    span = {"char_start": 7, "char_end": 13, "text": "answer" if anchor_valid else "forged"}
    context = {"char_start": 0, "char_end": len(text), "text": text,
               "matched_char_start": 7, "matched_char_end": 13}
    before = _scene_audio_journey(source_kind="document", source_start=0, document_text=text,
        search_result={"scene_id": "scene-hash", "video_id": "video-one",
                       "matched_document_span": span, "document_context_span": context})["before"]
    assert before["documentContextText"] is None


@pytest.mark.parametrize("has_match", [True, False])
def test_document_search_updates_selected_passage_when_query_changes(has_match):
    text = "early answer and late answer"
    def result(start, end):
        return {"scene_id": "scene-hash", "video_id": "video-one", "source_kind": "document",
                "matched_document_span": {"chunk_index": 0, "char_start": start, "char_end": end,
                                          "text": text[start:end], "token_count": 2},
                "document_context_span": {"char_start": 0, "char_end": len(text), "text": text,
                                          "matched_char_start": start, "matched_char_end": end}}
    observed = _scene_audio_journey(source_kind="document", source_start=0, document_text=text,
        search_result=result(0, 12), search_next=[result(17, len(text))] if has_match else [],
        action="next-document-search")
    assert observed["before"]["matchedDocumentText"] == "early answer"
    assert observed["after"]["matchedDocumentText"] == ("late answer" if has_match else None)
    assert observed["after"]["documentText"] == text
    assert observed["before"]["documentContextText"] == text
    assert observed["after"]["documentContextText"] == (text if has_match else None)


@pytest.mark.parametrize("change", [{}, {"text": "forged"}, {"char_end": 9999}, {"char_start": "0"}])
def test_additional_lexical_passage_is_bound_plain_text_and_clears(change):
    text = "\U0001f600 <script>no automatic action</script> later match"
    end = text.index(" later")
    extra = {"char_start": 0, "char_end": end, "text": text[:end]}
    extra.update(change)
    result = _scene_audio_journey(source_kind="document", source_start=0, document_text=text,
        action="clear-document-search", search_result={
            "scene_id": "scene-hash", "video_id": "video-one",
            "matched_document_span": {"char_start": end+1, "char_end": len(text), "text": text[end+1:]},
            "lexical_document_span": extra,
        })
    assert result["before"]["lexicalDocumentText"] == (text[:end] if not change else None)
    assert result["before"]["lexicalDocumentMarkup"] is None
    assert result["after"]["lexicalDocumentText"] is None


def test_standalone_audio_card_and_overview_use_labeled_transcript_excerpt():
    transcript = "Fresh audio transcript evidence. " * 12
    observed = _scene_audio_journey(source_kind="audio", source_start=0, transcript=transcript)["before"]
    excerpt = f"Transcript excerpt: {transcript[:240]}"
    assert observed["cardSummary"] == excerpt
    assert observed["overviewSummary"] == excerpt
    assert observed["src"] == "/api/media/video/video-one/source"
    assert observed["paused"] is True
    assert observed["currentTime"] == 0
    assert observed["video"]["src"] is None
    assert "READ TRANSCRIPT" in observed["ttsLabel"]


@pytest.mark.parametrize('source_kind', ['audio', 'video'])
def test_model_word_alignment_seeks_scene_audio_and_ignores_stale_scene(source_kind):
    result = _scene_audio_journey(source_kind=source_kind, source_start=120, transcript='hello quiet',
        action='word-seek', scene_overrides={'transcript_outcome':'transcript_available',
        'transcript_meta':{'word_alignment':{'timebase':'input_audio_seconds','words':[
            {'text':'hello','start':1.25,'end':1.6,'timing_status':'aligned'},
            {'text':'quiet','start':None,'end':None,'timing_status':'invalid_model_alignment'}]}}})
    assert 'model alignment, unreviewed' in result['before']['overviewText']
    assert 'quiet · timing unavailable' in result['before']['overviewText']
    assert result['aligned']['currentTime'] == 1.25
    assert result['aligned']['paused'] is True
    assert result['after']['currentTime'] == 0


@pytest.mark.parametrize('source_kind,expected_seek', [('video', 1.25), ('audio', 121.25)])
def test_offset_word_alignment_seeks_the_correct_source_player(source_kind, expected_seek):
    from cli.run_ingestion import _offset_local_audio_result_to_scene
    result = _offset_local_audio_result_to_scene({'transcript_meta': {'word_alignment': {
        'timebase': 'input_audio_seconds', 'words': [
            {'text': 'hello', 'start': 1.25, 'end': 1.6, 'timing_status': 'aligned'},
            {'text': 'unclear', 'start': None, 'end': None, 'timing_status': 'invalid_model_alignment'}]}}}, 120.)
    observed = _scene_audio_journey(source_kind=source_kind, source_start=120, transcript='hello unclear',
        action='word-seek', scene_overrides={'transcript_outcome': 'transcript_available', **result})
    assert observed['aligned']['currentTime'] == expected_seek
    assert 'unclear · timing unavailable' in observed['before']['overviewText']
    assert observed['after']['currentTime'] == 0


def test_video_timebase_without_an_origin_does_not_seek_scene_audio():
    observed = _scene_audio_journey(transcript='hello', scene_overrides={
        'transcript_outcome': 'transcript_available', 'transcript_meta': {'word_alignment': {
            'timebase': 'video_seconds', 'words': [
                {'text': 'hello', 'start': 121.25, 'end': 121.6, 'timing_status': 'aligned'}]}}})
    assert 'Word timing not recorded' in observed['before']['overviewText']


def test_historical_transcript_does_not_claim_word_alignment():
    result = _scene_audio_journey(source_kind='audio', transcript='hello',
        scene_overrides={'transcript_outcome':'transcript_available'})
    assert 'Word timing not recorded' in result['before']['overviewText']


@pytest.mark.parametrize('sampled', [None, 0, 2])
def test_decoder_sampling_diagnostic_is_visible_without_claiming_word_accuracy(sampled):
    result = _scene_audio_journey(source_kind='audio', transcript='repeated words',
        scene_overrides={'transcript_outcome':'transcript_available', 'transcript_meta':{
            'transcription_quality':{'sampled_segment_count':sampled}}})
    shown = result['before']['overviewText']
    assert ('Decoder retry: 2 segments used sampling.' in shown) == (sampled == 2)
    if sampled == 2:
        assert 'Words may vary between runs; review the original audio.' in shown


def test_first_numeric_scene_card_keeps_its_original_audio_identity():
    result = _scene_audio_journey(scene_id=0)["before"]
    assert result["src"] == "/api/media/video/video-one/scene/0/audio"


@pytest.mark.parametrize("endpoint,available", [
    ("", False), ("https://outside.invalid/audio.wav", True), ("//outside.invalid/audio.wav", True),
])
def test_scene_card_reports_unavailable_without_guessing_media(endpoint, available):
    result = _scene_audio_journey(endpoint=endpoint, available=available)["before"]
    assert result["src"] is None
    assert "unavailable" in result["status"].lower()


def test_original_audio_load_failure_does_not_substitute_transcript_speech():
    result = _scene_audio_journey(transcript="Known fixture text.", action="error")["after"]
    assert "could not be loaded or played" in result["status"].lower()
    assert not any(item != "cancel" for item in result["speech"])


def test_original_audio_selection_lifecycle_and_synthetic_transcript_are_separate():
    result = _scene_audio_journey(transcript="Known fixture text.", action="lifecycle")
    assert "READ TRANSCRIPT" in result["before"]["ttsLabel"]
    assert result["ttsPausedAudio"] and result["oldStopped"]
    assert result["entityStopped"] and result["datasetStopped"] and result["staleIgnored"]
    assert result["switched"]["src"].endswith("/scene/second-hash/audio")
    assert any("Known fixture text." in item for item in result["speech"])


@pytest.mark.parametrize("available", [False, True])
def test_unloaded_search_scene_uses_only_its_explicit_original_audio_endpoint(available):
    result = _scene_audio_journey(endpoint="/api/media/video/other/scene/other-scene/audio",
                                  available=available, action="cross")["after"]
    assert result["src"] == ("/api/media/video/other/scene/other-scene/audio" if available else None)
    if not available:
        assert "unavailable" in result["status"].lower()


@pytest.mark.parametrize("action", ["cross-card", "cross-card-unavailable"])
def test_cross_video_card_does_not_borrow_loaded_scene_with_same_id(action):
    result = _scene_audio_journey(action=action)["after"]
    assert result["src"] == (
        "/api/media/video/video-two/scene/scene-hash/audio" if action == "cross-card" else None
    )
    if action == "cross-card-unavailable":
        assert "unavailable" in result["status"].lower()


@pytest.mark.parametrize("scene_id", ["scene-hash", 0])
def test_scene_card_source_video_seeks_to_source_time_without_autoplay(scene_id):
    result = _scene_audio_journey(action="video", scene_id=scene_id)
    assert result["before"]["video"]["src"] == "/api/media/video/video-one/source"
    assert result["before"]["video"]["paused"] is True
    assert result["before"]["video"]["keyframeHidden"] is False
    assert result["after"]["video"]["currentTime"] == 120.0
    assert result["after"]["video"]["paused"] is True
    assert result["after"]["video"]["keyframeHidden"] is True
    assert result["after"]["currentTime"] == 0  # Scene WAV has a separate local time origin.
    assert not any(item != "cancel" for item in result["after"]["speech"])


def test_source_video_metadata_does_not_repeat_initial_seek():
    result = _scene_audio_journey(action="video-once")
    assert result["before"]["video"]["src"] == "/api/media/video/video-one/source"
    assert result["firstSeek"] == 120.0
    assert result["after"]["video"]["currentTime"] == 135


def test_source_video_audio_only_decode_is_not_reported_as_usable_video():
    result = _scene_audio_journey(action="video", video_width=0)["after"]
    assert "no video frames" in result["video"]["status"].lower()
    assert result["video"]["keyframeHidden"] is False
    assert result["video"]["paused"] is True


@pytest.mark.parametrize("video_endpoint,video_available", [
    (None, False), ("https://outside.invalid/video.mp4", True), ("//outside.invalid/video.mp4", True),
])
def test_source_video_unavailable_keeps_keyframe_and_does_not_guess(video_endpoint, video_available):
    result = _scene_audio_journey(video_endpoint=video_endpoint, video_available=video_available)["before"]
    assert result["video"]["src"] is None
    assert "unavailable" in result["video"]["status"].lower()
    assert result["video"]["keyframeHidden"] is False
    assert result["src"]  # Original scene audio remains independently available.


@pytest.mark.parametrize("source_start", [None, -1, "120"])
def test_source_video_invalid_time_is_not_silently_replaced_with_zero(source_start):
    result = _scene_audio_journey(source_start=source_start)["before"]["video"]
    assert result["src"] is None
    assert "invalid" in result["status"].lower()
    assert result["keyframeHidden"] is False


@pytest.mark.parametrize("action,duration,expected", [
    ("video-error", 180.0, "could not be loaded or played"),
    ("video", 119.0, "outside"),
    ("video-seek-error", 180.0, "could not seek"),
])
def test_source_video_failure_keeps_keyframe_without_synthetic_substitution(action, duration, expected):
    result = _scene_audio_journey(action=action, duration=duration, transcript="Fixture words.")["after"]
    assert expected in result["video"]["status"].lower()
    assert result["video"]["keyframeHidden"] is False
    assert result["video"]["paused"] is True
    assert not any(item != "cancel" for item in result["speech"])


def test_source_video_lifecycle_excludes_audio_and_tts_and_ignores_stale_callbacks():
    result = _scene_audio_journey(action="video-lifecycle", transcript="Fixture words.")
    assert result["before"]["video"]["src"] == "/api/media/video/video-one/source"
    for key in ("audioPausedVideo", "videoPausedAudio", "ttsPausedVideo", "videoStoppedTts",
                "oldStopped", "staleIgnored", "entityStopped", "datasetStopped"):
        assert result[key], key


@pytest.mark.parametrize("action", ["cross", "cross-card", "cross-card-unavailable"])
def test_source_video_uses_selected_search_card_identity_and_its_own_time(action):
    result = _scene_audio_journey(action=action)["after"]["video"]
    if action == "cross-card-unavailable":
        assert result["src"] is None
        assert "unavailable" in result["status"].lower()
    else:
        assert result["src"] == "/api/media/video/video-two/source"
        assert result["currentTime"] == 40


def test_desktop_fallback_waits_for_play_intent_after_audio_only_decode():
    result = _scene_audio_journey(action="desktop", video_width=0)
    assert result["passive"]["commands"] == []
    assert result["passive"]["video"]["playButton"] == "Play original video"
    assert result["commands"][0]["path"].endswith("/desktop-player/play")
    assert result["commands"][0]["body"] == {
        "video_id": "video-one", "scene_id": "scene-hash",
        "window": {"x": 730, "y": 280, "width": 340, "height": 210},
    }
    assert "opening" in result["launched"]["video"]["status"].lower()
    assert "playing" not in result["launched"]["video"]["status"].lower()


def test_desktop_fallback_routes_decode_failure_once_after_native_play_intent():
    result = _scene_audio_journey(action="desktop-decode")
    assert len(result["commands"]) == 1
    assert result["commands"][0]["path"].endswith("/play")


def test_desktop_fallback_supported_video_stays_in_browser():
    result = _scene_audio_journey(action="desktop")
    assert result["commands"] == []
    assert result["after"]["video"]["paused"] is False


def test_desktop_fallback_remote_or_missing_player_is_visible_without_launch():
    result = _scene_audio_journey(action="desktop-quiet", video_width=0, desktop_available=False)
    assert result["commands"] == []
    assert result["after"]["video"]["playDisabled"] is True
    assert "local only" in result["after"]["video"]["status"].lower()


@pytest.mark.parametrize("scene_id", ["scene-hash", 0])
def test_desktop_fallback_sends_scene_identity_without_client_supplied_path_or_time(scene_id):
    result = _scene_audio_journey(action="desktop", video_width=0, scene_id=scene_id)
    body = result["commands"][0]["body"]
    assert body["scene_id"] == str(scene_id)
    assert set(body) == {"video_id", "scene_id", "window"}


def test_desktop_fallback_cross_video_card_does_not_borrow_active_dataset_identity():
    result = _scene_audio_journey(action="desktop-cross", video_width=0)
    body = result["commands"][0]["body"]
    assert body["video_id"] == "video-two"
    assert body["scene_id"] == "0"


@pytest.mark.parametrize("kwargs", [
    {"source_start": None}, {"source_start": -1}, {"duration": 100},
    {"video_available": False}, {"video_endpoint": "https://outside.invalid/video.mp4"},
])
def test_desktop_fallback_does_not_launch_for_missing_source_or_invalid_scene(kwargs):
    result = _scene_audio_journey(action="desktop", video_width=0, **kwargs)
    assert result["commands"] == []


@pytest.mark.parametrize("action", ["desktop-audio", "desktop-tts", "desktop-done", "desktop-reset",
                                    "desktop-entity", "desktop-dataset", "desktop-pending"])
def test_desktop_fallback_releases_only_its_playback_and_stops_polling(action):
    result = _scene_audio_journey(action=action, video_width=0, transcript="Fixture text.")
    assert [command["path"].rsplit("/", 1)[1] for command in result["commands"]] == ["play", "done"]
    assert result["commands"][-1]["body"] == {"playback_id": "fixture-playback"}
    assert result["timers"] == 0
    if action in ("desktop-reset", "desktop-pending"):
        assert "Opening" not in result["after"]["video"]["status"]


def test_desktop_fallback_only_reports_playing_after_status_confirms_it():
    result = _scene_audio_journey(action="desktop-poll", video_width=0)
    assert "opening" in result["launched"]["video"]["status"].lower()
    assert "playing" in result["after"]["video"]["status"].lower()


def test_desktop_fallback_reports_source_disappearing_without_claiming_playback():
    result = _scene_audio_journey(action="desktop", video_width=0,
                                  desktop_failure="Original video not found")
    assert "Original video not found" in result["after"]["video"]["status"]
    assert result["timers"] == 0


def test_desktop_fallback_failed_dismissal_preserves_retry_done_control():
    result = _scene_audio_journey(action="desktop-done", video_width=0,
                                  desktop_done_failure="Player did not acknowledge stop")
    assert "could not dismiss" in result["after"]["video"]["status"].lower()
    assert "dismissed" not in result["after"]["video"]["status"].lower()
    assert result["after"]["video"]["doneHidden"] is False
    assert result["after"]["video"]["playDisabled"] is True


@pytest.mark.parametrize("action,failure", [("desktop-return", None), ("desktop-return-pending", None),
                                           ("desktop-return", "Player did not acknowledge stop")])
def test_return_to_people_waits_for_owned_player_and_retains_failed_dismissal(action, failure):
    result = _scene_audio_journey(action=action, video_width=0, desktop_done_failure=failure)
    assert result["returnReady"] is (failure is None)
    assert [c["path"].rsplit("/", 1)[1] for c in result["commands"]] == ["play", "done"]
    assert result["commands"][1]["body"] == {"playback_id": "fixture-playback"}
    if "pending" in action:
        assert result["returnPending"] is True
    if failure:
        assert result["after"]["video"]["doneHidden"] is False


def test_desktop_fallback_retries_failed_dismissal_with_same_owned_token():
    result = _scene_audio_journey(action="desktop-done-retry", video_width=0,
                                  desktop_done_failure="Player did not acknowledge stop")
    assert [command["path"].rsplit("/", 1)[1] for command in result["commands"]] == ["play", "done", "done"]
    assert result["commands"][1]["body"] == result["commands"][2]["body"] == {"playback_id": "fixture-playback"}
    assert "dismissed" in result["after"]["video"]["status"].lower()
    assert result["after"]["video"]["doneHidden"] is True


@pytest.mark.parametrize("desktop_state,expected,timers", [
    ("paused", "paused", 1), ("ended", "ended", 0), ("closed", "closed", 0), ("error", "unavailable", 0),
])
def test_desktop_fallback_reports_player_state_and_stops_terminal_polling(desktop_state, expected, timers):
    result = _scene_audio_journey(action="desktop", video_width=0, desktop_state=desktop_state)
    assert expected in result["after"]["video"]["status"].lower()
    assert result["timers"] == timers
    assert result["after"]["video"]["playDisabled"] is (desktop_state == "paused")


@pytest.mark.parametrize("mode", ["multimodal", "narrative"])
def test_identity_search_cards_preserve_appearance_mention_and_identity_only_limits(mode):
    names = ("renderTimelineGrid", "appendIdentitySearchEvidence", "formatTime", "appendText")
    source = "\n".join(_function_source(name) for name in names
                       if re.search(rf"function\s+{name}\s*\(", RETRO_JS))
    harness = r'''
const fixture = JSON.parse(require('fs').readFileSync(0, 'utf8'));
class Element {
  constructor() { this.children = []; this.style = {}; this.textContent = ''; }
  set innerHTML(value) { this.children = []; }
  appendChild(child) { this.children.push(child); }
  setAttribute() {} addEventListener() {}
}
const grid = new Element();
const document = { getElementById: id => id === 'timeline-grid' ? grid : null,
  createElement: () => new Element() };
const window = { location: { origin: 'http://localhost' } };
const state = { scenes: [{id: 'one', start: 0, end: 5}], videos: [],
  graph: {nodes: []}, selectedEntities: [], activeSearchTab: fixture.mode,
  searchActive: true, searchResults: [{scene_id: 'one', start_time: 0, end_time: 5,
    identity_match: 'appearance', identity_only: true, identity_evidence: [
      {display_name: 'Dad', strength: 'appearance'},
      {display_name: 'Mom <script>', strength: 'mention'}]}] };
const scenePassesIntelFilter = () => true;
const resolveKeyframeUrl = () => null;
eval(fixture.source);
const read = el => [el.textContent, ...el.children.flatMap(read)];
renderTimelineGrid(); const searching = read(grid);
state.searchActive = false; renderTimelineGrid(); const cleared = read(grid);
process.stdout.write(JSON.stringify({searching, cleared}));
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps({"source": source, "mode": mode}),
                            capture_output=True, text=True, cwd=REPO_ROOT, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert "Dad: face-backed appearance" in observed["searching"]
    assert "Mom <script>: transcript mention only" in observed["searching"]
    assert "Person match only; event relevance unverified" in observed["searching"]
    assert not any("face-backed" in value or "transcript mention" in value for value in observed["cleared"])


def test_search_grid_preserves_relevance_order_and_labels_candidates():
    source = "\n".join(_function_source(n) for n in
        ("renderTimelineGrid", "appendIdentitySearchEvidence", "formatTime", "appendText"))
    harness = r'''
const source = JSON.parse(require('fs').readFileSync(0, 'utf8'));
class Element {
  constructor() { this.children=[]; this.style={}; this.attrs={}; }
  set innerHTML(v) { this.children=[]; }
  appendChild(v) { this.children.push(v); }
  setAttribute(k,v) { this.attrs[k]=v; } addEventListener() {}
}
const grid=new Element(); const heading=new Element();
const document={getElementById:id=>id==='timeline-grid'?grid:id==='timeline-heading'?heading:null,createElement:()=>new Element()};
const window={location:{origin:'http://localhost'}};
const state={scenes:[{id:'early',start:0,end:5},{id:'late',start:10,end:15}],videos:[],graph:{nodes:[]},
 selectedEntities:[],lastQuery:'fixture',activeSearchTab:'multimodal',searchActive:true,searchResults:[{scene_id:'late'},{scene_id:'early'}]};
const scenePassesIntelFilter=()=>true;
eval(source); renderTimelineGrid();
const ranked=grid.children.map(c=>c.attrs);
const rankedHeading=heading.textContent;
state.searchActive=false; state.searchResults=[]; renderTimelineGrid();
process.stdout.write(JSON.stringify({ranked,rankedHeading,cleared:grid.children.map(c=>c.attrs)}));
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps(source),
        capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT, timeout=20, check=True)
    observed = json.loads(result.stdout)
    assert observed["rankedHeading"] == 'Timeline  //  2 ranked candidates  ·  "fixture"'
    assert [x["data-scene-id"] for x in observed["ranked"]] == ["late", "early"]
    assert [x["data-search-label"] for x in observed["ranked"]] == ["RESULT #1", "RESULT #2"]
    assert [x["data-scene-id"] for x in observed["cleared"]] == ["early", "late"]
    assert all("data-search-label" not in x for x in observed["cleared"])

def test_object_detections_are_unconfirmed_in_loaded_scene_inspector():
    result = _scene_audio_journey(scene_overrides={
        "objects": ["elephant", "car"],
        "entities": [{"name": "elephant", "entity_type": "object", "confidence": 0.5},
                     {"name": "car", "entity_type": "object", "confidence": 0.5}],
    })["before"]
    assert "elephant (unconfirmed object)" in result["entityText"]
    assert "car (unconfirmed object)" in result["entityText"]
    assert "Detected Objects (Unconfirmed)" in result["entityText"]

@pytest.mark.parametrize("case", ["aliases", "distinct-scenes", "channels", "anonymous", "edge-evidence", "normalization"])
def test_graph_preserves_evidence_without_inventing_identity(case):
    # Execute the shipped normalizers/graph builder, including the actual alias policy.
    names = RETRO_JS[RETRO_JS.index("  // Helper Utility: Entity Name"):RETRO_JS.index("  // DOM Text Insertion Helper")]
    source = names + "\n" + "\n".join(_function_source(name) for name in (
        "normalizeEntityList", "buildEntityGraph",
    ))
    harness = r'''
const assert = require('node:assert/strict');
const {source,case:which} = JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const CHANNEL_PRIORITY = {scene_present:3,dialogue_mentioned:2,candidate:1,generic:0};
eval(source);
const person = name => ({name,type:'person'});
if(which==='aliases') {
  for(const name of ['Anthony','Tony S.','speaker 2','male speaker 2','man in black jacket','Joseph','Charles'])
    assert.equal(normalizeEntityName(name),name.toLowerCase(),'labels must not become unsupported identities');
} else if(which==='distinct-scenes') {
  const graph = buildEntityGraph([
    {id:'one',entities:[person('Alice'),person('Alice')],dialogue_mentioned_entities:[person('Alice')]},
    {id:'two',scene_present_entities:[person('Alice')]},
  ]);
  assert.equal(graph.nodes[0].count,2,'count distinct scenes, not channel duplicates');
  assert.deepEqual(graph.nodes[0].sceneIds,['one','two']);
} else if(which==='channels') {
  const graph=buildEntityGraph([
    {id:'one',scene_present_entities:[person('Alice')]},
    {id:'two',dialogue_mentioned_entities:[person('Alice')]},
    {id:'three',candidate_visible_people:[person('Alice')]},
  ]);
  const node=graph.nodes[0];
  assert.equal(node.channel,'mixed','one presence claim must not upgrade all other observations');
  assert.deepEqual(node.observations.map(x=>[x.sceneId,x.channel]),[
    ['one','scene_present'],['two','dialogue_mentioned'],['three','candidate']]);
} else if(which==='anonymous') {
  const graph=buildEntityGraph([
    {id:'one',candidate_visible_people:[person('anonymous_person_1'),person('speaker 2')]},
    {id:'two',candidate_visible_people:[person('anonymous_person_1'),person('speaker 2')]},
  ]);
  assert.equal(graph.nodes.length,4,'scene-local anonymous labels must not be merged across scenes');
  assert.equal(new Set(graph.nodes.map(x=>x.id)).size,4);
  assert.ok(graph.nodes.every(x=>x.count===1));
} else if(which==='edge-evidence') {
  const graph=buildEntityGraph([
    {id:'one',scene_present_entities:[person('Alice')],dialogue_mentioned_entities:[person('Bob')],entities:[person('Bob')]},
    {id:'two',candidate_visible_people:[person('Alice')],dialogue_mentioned_entities:[person('Bob')]},
  ]);
  const edge=graph.edges[0];
  assert.equal(edge.relation,'shared_scene');
  assert.equal(edge.weight,2);
  assert.deepEqual(edge.evidence.map(x=>[x.sceneId,x.sourceChannels,x.targetChannels]),[
    ['one',['scene_present'],['dialogue_mentioned','generic']],
    ['two',['candidate'],['dialogue_mentioned']],
  ]);
} else {
  const raw={label:'Alice',entity_type:'person',confidence:.4,source_step:'entity_extract',
    properties:{verification_status:'candidate',evidence:'Alice is mentioned, not identified.'}};
  const normalized=normalizeEntityList([null,raw,'Bob',{}]);
  assert.equal(normalized.length,2);
  assert.equal(normalized[0].source_step,'entity_extract');
  assert.deepEqual(normalized[0].properties,raw.properties);
  assert.equal(normalized[0].confidence,.4);
  assert.equal(raw.name,undefined,'do not mutate source payload');
}
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps({"source": source, "case": case}),
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind", ["video", "audio", "image", "document"])
def test_graph_evidence_button_opens_exact_scene_and_invalidates_old_search(kind):
    source = "\n".join(_function_source(name) for name in (
        "renderGraphEvidence", "graphChannelLabel", "openGraphEvidence", "resetAllFilters",
        "selectScene", "appendText", "formatTime", "objectEvidenceLabel",
    ))
    harness = r'''
const assert=require('node:assert/strict');
const {source,kind}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
class Element {
 constructor(){this.children=[];this.textContent='';this.hidden=false;this.value='old';}
 appendChild(e){this.children.push(e);}
 addEventListener(name,fn){this[name]=fn;}
 set innerHTML(value){throw new Error('Evidence must render as text');}
}
const elements=new Map(['query-input','search-status','narrative-summary-container'].map(id=>[id,new Element()]));
const document={createElement:()=>new Element(),getElementById:id=>elements.get(id),querySelector:()=>null};
const scene={id:'support',start:12,end:18,source_kind:kind,summary:'Retained scene'};
const unrelated={id:'other',start:30,end:40};
const state={scenes:[scene,unrelated],selectedEntities:['a'],selectedEntity:'a',selectedSceneId:'other',
 searchGeneration:4,temporalSummaryGeneration:8,intelFilter:{type:'emotion'},lastQuery:'old',
 searchActive:true,searchResults:[{scene_id:'other'}],activeVideoId:'video',activeSearchTab:'multimodal'};
let selected,tab;
const renderTimelineGrid=()=>{},drawGraph=()=>{},renderEntityFilterChecklist=()=>{},
 triggerGraphAnimation=()=>{},logDataTrail=()=>{},renderVideoIntelPanel=()=>{};
const renderInspector=()=>{selected=state.selectedSceneId;};
const switchInspectorTab=value=>{tab=value;};
eval(source);
const alice={id:'a',label:'Alice',sceneIds:['support'],observations:[{
 sceneId:'support',channel:'dialogue_mentioned',entity:{name:'Alice',source_step:'tagger',
 properties:{evidence:'<img src=x onerror=bad()>',verification_status:'candidate'}}}]};
const bob={id:'b',label:'Bob'};
state.graph={nodes:[alice,bob]};
const edge={source:'a',target:'b',sceneIds:['support'],evidence:[{sceneId:'support',
 sourceChannels:['dialogue_mentioned'],targetChannels:['candidate']}]};
const container=new Element();renderGraphEvidence(container,alice,edge);
const read=e=>[e.textContent,...e.children.flatMap(read)];
const text=read(container).join('\n');
assert.match(text,/Bob: Visibility candidate/);
assert.match(text,/Dialogue mention · source: tagger/);
assert.match(text,/<img src=x onerror=bad\(\)>/);
const row=container.children[0];
const range=kind==='image'?'Image':kind==='document'?'Document passage':'0:12–0:18';
row.children.find(e=>e.textContent===`Open scene evidence ${range}`).click();
assert.equal(selected,'support');assert.equal(state.selectedOriginalMedia,scene);
assert.equal(tab,'entities');assert.deepEqual(state.selectedEntities,[]);
assert.equal(state.searchGeneration,5);assert.equal(state.temporalSummaryGeneration,9);
assert.equal(state.searchActive,false);assert.deepEqual(state.searchResults,[]);
assert.equal(state.intelFilter,null);assert.equal(state.lastQuery,'');
assert.equal(elements.get('query-input').value,'');
assert.equal(elements.get('search-status').hidden,true);
assert.equal(elements.get('narrative-summary-container').hidden,true);
openGraphEvidence('missing');assert.equal(selected,'support');
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps({"source": source, "kind": kind}),
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mode", ["ok", "dataset", "scene", "detached", "error", "unavailable"])
def test_stored_relationship_load_and_evidence_navigation_guard_stale_ui(mode):
    source = "\n".join(_function_source(name) for name in (
        "renderStoredRelationships", "appendText", "formatTime",
    ))
    harness = r'''
const assert=require('node:assert/strict');
const {source,mode}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
class Element {
 constructor(){this.children=[];this.textContent='';this.isConnected=true;}
 appendChild(e){this.children.push(e);}
 addEventListener(name,fn){this[name]=fn;}
 set innerHTML(v){throw new Error('Must render evidence as text');}
}
const document={createElement:()=>new Element()};
const state={activeVideoId:'video-a',datasetGeneration:1,selectedSceneId:'scene-a',selectedEntity:null};
let resolve,reject,requested,opened;
const apiGet=url=>{requested=url;return new Promise((a,b)=>{resolve=a;reject=b})};
const openGraphEvidence=id=>{opened=id};
eval(source);
(async()=>{
 const parent=new Element();renderStoredRelationships(parent,{id:'scene-a'});
 const section=parent.children[0],load=section.children.find(e=>e.textContent==='Load stored relationships');
 const pending=load.click();
 assert.equal(requested,'/api/videos/video-a/scenes/scene-a/relationships');
 assert.equal(load.disabled,true);
 if(mode==='dataset')state.datasetGeneration++;
 if(mode==='scene')state.selectedSceneId='other';
 if(mode==='detached')section.isConnected=false;
 const payload={status:mode==='unavailable'?'not_materialized':'ok',epoch_id:'test',relationships:[{
  id:4,type:'identity_evidence',review_status:'reviewed_revoked',source:{type:'speaker_pattern',name:'pattern'},
  target:{type:'person',name:'<img src=x>'},evidence:{scene_id:'scene-a',provenance:'operator_manual_override',mapping_id:'m1'}
 }]};
 if(mode==='error')reject(new Error('private path'));else resolve(payload);
 await pending;
 const all=e=>[e,...e.children.flatMap(all)],text=all(parent).map(e=>e.textContent).join('\n');
 if(['dataset','scene','detached'].includes(mode)){assert.ok(!text.includes('reviewed_revoked'));return;}
 assert.equal(load.disabled,false);
 if(mode==='error'){assert.match(text,/read failed/);assert.ok(!text.includes('private path'));return;}
 if(mode==='unavailable'){assert.match(text,/not_materialized/);return;}
 assert.match(text,/identity_evidence · reviewed_revoked/);assert.match(text,/<img src=x>/);
 all(parent).find(e=>e.textContent==='Open supporting scene').click();assert.equal(opened,'scene-a');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps({"source": source, "mode": mode}),
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_object_graph_filter_keeps_identity_and_marks_uncertainty():
    source = "\n".join(_function_source(name) for name in (
        "normalizeEntityName", "getCanonicalLabel", "buildEntityGraph",
        "objectEvidenceLabel", "renderEntityFilterChecklist",
    ))
    harness = r'''
const source = JSON.parse(require("fs").readFileSync(0, "utf8"));
const entityAliases = {}, canonicalDisplayNames = {};
const CHANNEL_PRIORITY = {scene_present:3, dialogue_mentioned:2, candidate:1, generic:0};
const make = () => ({children:[], attributes:{}, appendChild(el){this.children.push(el)},
  setAttribute(k,v){this.attributes[k]=v}, addEventListener(){}});
const list = make();
const document = {getElementById:()=>list, createElement:make};
const state = {selectedEntities:[]};
eval(source);
state.graph = buildEntityGraph([{id:"scene-one", entities:[
  {name:"elephant", type:"object"}, {name:"car", type:"object"},
  {name:"Alice", type:"person"}]}]);
renderEntityFilterChecklist();
process.stdout.write(JSON.stringify({nodes:state.graph.nodes,
  filters:list.children.map(row=>({id:row.attributes["data-entity-id"],text:row.children[1].textContent}))}));
'''
    result = subprocess.run(["node", "-e", harness], input=json.dumps(source),
                            capture_output=True, text=True, check=True, timeout=20)
    observed = json.loads(result.stdout)
    assert {row["id"]: row["text"] for row in observed["filters"]} == {
        "elephant": "Elephant (unconfirmed object) (1)",
        "car": "Car (unconfirmed object) (1)", "alice": "Alice (1)",
    }
    elephant = next(row for row in observed["nodes"] if row["id"] == "elephant")
    assert elephant["label"] == "Elephant"
    assert elephant["sceneIds"] == ["scene-one"]
    assert elephant["channel"] == "generic"


def test_inspector_renders_provenance_and_historical_supported_qualifications_without_mutating_canonical_fields():
    # Historical persisted "supported" state + visual_signal "support" + observed vs unknown object scores
    observed = _scene_audio_journey(scene_overrides={
        "summary": "Table conversation.",
        "visual_caption": "a man and a woman sitting at a table",
        "transcript": "Why didn't you say something?",
        "objects": ["sandwich", "cup"],
        "entities": [
            {
                "name": "sandwich",
                "entity_type": "object",
                "confidence": 0.377349,
                "source_modality": "vision",
                "properties": {
                    "score_status": "observed",
                    "verification_status": "candidate_unconfirmed",
                    "source_step": "object_detect",
                    "establishes_visible_presence": False,
                },
            },
            {
                "name": "cup",
                "entity_type": "object",
                "confidence": None,
                "source_modality": "vision",
                "properties": {
                    "score_status": "unknown",
                    "verification_status": "candidate_unconfirmed",
                    "source_step": "object_detect",
                    "establishes_visible_presence": False,
                },
            },
        ],
        "scene_context_llm": {
            "narrative_summary": "Table conversation.",
            "primary_tags": ["table"],
            "source": "scene_context_llm",
            "claim_provenance": {
                "narrative_summary": {
                    "source": "scene_context_llm",
                    "depends_on": ["image_caption", "object_detect", "transcribe"],
                    "qualification": "model_derived_summary_from_qualified_visual_and_transcript_inputs",
                    "establishes_visible_presence": False,
                }
            },
        },
        "scene_context_epistemic": {
            "state": "supported",
            "evidence_family": "transcript+visual",
            "conflict_detected": False,
            "evidence": [
                {
                    "kind": "visual_signal",
                    "role": "support",
                    "value": "sandwich",
                    "source_step": "object_detect",
                    "depends_on": ["object_detect"],
                    "score": 0.377349,
                    "score_status": "observed",
                }
            ],
        },
        "scene_context_arbitration": {
            "resolved_by": "visual",
            "hypotheses": [
                {
                    "axis": "setting",
                    "claim": "restaurant",
                    "evidence_family": "visual",
                    "weight": "supporting",
                }
            ],
            "evidence_conflicts": [],
            "unresolved_axes": [],
        },
    })["before"]

    # Canonical summary text is unaltered while presentation metadata renders provenance/qualification
    assert observed["overviewSummary"] == "Table conversation."
    assert observed["cardSummary"] == "Table conversation."
    assert observed["cardQualification"] == "Summary source: model-generated context summary (unverified; check evidence channels)."
    assert "Summary source: model-generated context summary (unverified; check evidence channels)." in observed["overviewText"]
    assert "Unverified model observation (image_caption); not confirmed scene fact." in observed["overviewText"]
    assert "sandwich (unconfirmed, score 0.38)" in observed["entityText"]
    assert "cup (unconfirmed, score unknown)" in observed["entityText"]
    assert "sandwich (unconfirmed object)" in observed["entityText"]
    assert "cup (unconfirmed object)" in observed["entityText"]
    assert "SUPPORTED (UNVERIFIED MODEL ALIGNMENT)" in observed["contextLogs"]
    assert "candidate; historical support label" in observed["contextLogs"]
    assert "[source: object_detect; depends_on: object_detect; score: 0.38]" in observed["contextLogs"]
    assert "candidate; historical supporting label" in observed["contextLogs"]

    # Visual-caption fallback summary (e.g., Scene 9 when summary is absent) retains canonical text and renders caption provenance
    caption_fallback = _scene_audio_journey(scene_overrides={
        "summary": None,
        "visual_caption": "a man and a woman are brushing their teeth",
    })["before"]
    assert caption_fallback["overviewSummary"] == "a man and a woman are brushing their teeth"
    assert caption_fallback["cardSummary"] == "a man and a woman are brushing their teeth"
    assert caption_fallback["cardQualification"] == "Summary source: visual caption (unverified model observation; not confirmed scene fact)."
    assert "Summary source: visual caption (unverified model observation; not confirmed scene fact)." in caption_fallback["overviewText"]

    # Historical persisted summary without claim_provenance renders unknown provenance on card and inspector without mutating text
    historical = _scene_audio_journey(scene_overrides={
        "summary": "Historical persisted summary without provenance metadata.",
        "visual_caption": "a man and a woman sitting at a table",
        "scene_context_llm": {
            "narrative_summary": "Historical persisted summary without provenance metadata.",
            "primary_tags": ["table"],
        },
    })["before"]
    assert historical["overviewSummary"] == "Historical persisted summary without provenance metadata."
    assert historical["cardSummary"] == "Historical persisted summary without provenance metadata."
    assert historical["cardQualification"] == "Summary source: unknown provenance (historical or unattributed summary; unverified, check evidence channels)."
    assert "Summary source: unknown provenance (historical or unattributed summary; unverified, check evidence channels)." in historical["overviewText"]


def test_ui_mapping_and_cards_preserve_mixed_modality_detector_scores_and_search_card_qualifications():
    from steps.video.entity_extractor import extract_entities_from_scene

    extracted = extract_entities_from_scene(
        scene_data={
            "keyframe": {
                "caption": "a man and a woman sitting at a table",
                "objects": [
                    {"label": "sandwich", "score": 0.377349, "bbox": [10, 20, 50, 60], "timestamp": 22.5},
                    {"label": "cup", "bbox": [100, 120, 140, 180], "timestamp": 23.0},
                ],
            },
            "audio": {
                "start_time": 20.0,
                "transcript": "Pass the sandwich and the cup.",
                "ner_entities": [
                    {"name": "sandwich", "type": "OBJECT", "confidence": 0.92, "source_step": "tagger"},
                    {"name": "cup", "type": "OBJECT", "confidence": 0.92, "source_step": "tagger"},
                ],
            },
            "start_time": 20.0,
        },
        scene_id="scene_mixed_ui",
        video_id="video_123",
    )
    # Also include legacy/mixed entities where top-level confidence was 0.92 to verify UI never substitutes merged entity confidence
    legacy_mixed_entities = [
        {
            "name": "knife",
            "entity_type": "object",
            "confidence": 0.92,
            "source_modalities": ["audio", "vision"],
            "source_steps": ["tagger", "object_detect"],
            "properties": {
                "detection": {"label": "knife", "score": 0.377349, "bbox": [5, 5, 15, 15], "timestamp": 24.0},
                "bbox": [5, 5, 15, 15],
                "verification_status": "candidate_unconfirmed",
            },
            "timestamps": [20.0, 24.0],
        },
        {
            "name": "fork",
            "entity_type": "object",
            "confidence": 0.92,
            "source_modalities": ["audio", "vision"],
            "source_steps": ["tagger", "object_detect"],
            "properties": {
                "detection": {"label": "fork", "bbox": [25, 25, 35, 35], "timestamp": 24.5},
                "bbox": [25, 25, 35, 35],
                "verification_status": "candidate_unconfirmed",
            },
            "timestamps": [20.0, 24.5],
        },
    ]

    observed = _scene_audio_journey(scene_overrides={
        "summary": "Table conversation.",
        "objects": ["sandwich", "cup", "knife", "fork"],
        "entities": extracted["entities"] + legacy_mixed_entities,
    })["before"]

    assert "sandwich (unconfirmed, score 0.38)" in observed["entityText"]
    assert "sandwich (unconfirmed, score 0.38) @ 20.00s, 22.50s" in observed["entityText"]
    assert "cup (unconfirmed, score unknown)" in observed["entityText"]
    assert "knife (unconfirmed, score 0.38)" in observed["entityText"]
    assert "fork (unconfirmed, score unknown)" in observed["entityText"]
    assert "score 0.92" not in observed["entityText"]

    details_by_label = {item["label"]: item for item in observed["loadedObjectDetails"]}
    assert details_by_label["sandwich"]["score"] == 0.377349
    assert details_by_label["sandwich"]["detector_score"] == 0.377349
    assert details_by_label["sandwich"]["mention_confidence"] == 0.92
    assert details_by_label["sandwich"]["score_status"] == "observed"
    assert details_by_label["sandwich"]["bboxes"] == [[10, 20, 50, 60]]
    assert details_by_label["sandwich"]["timestamps"] == [20.0, 22.5]

    assert details_by_label["cup"]["score"] is None
    assert details_by_label["cup"]["detector_score"] is None
    assert details_by_label["cup"]["mention_confidence"] == 0.92
    assert details_by_label["cup"]["score_status"] == "unknown"
    assert details_by_label["cup"]["bboxes"] == [[100, 120, 140, 180]]
    assert details_by_label["cup"]["timestamps"] == [20.0, 23.0]

    # Verify search cards in both multimodal and narrative search modes show qualification alongside unchanged canonical summary text
    source = "\n".join(_function_source(n) for n in (
        "renderTimelineGrid", "appendIdentitySearchEvidence", "formatTime", "appendText"
    ))
    harness = r'''
const source = JSON.parse(require('fs').readFileSync(0, 'utf8'));
class Element {
  constructor(tag='') { this.tag=tag; this.children=[]; this.style={}; this.attrs={}; this.className=''; this.textContent=''; }
  set innerHTML(v) { this.children=[]; this.textContent=''; }
  appendChild(v) { this.children.push(v); return v; }
  setAttribute(k,v) { this.attrs[k]=v; }
  addEventListener() {}
}
const grid = new Element('div');
const heading = new Element('div');
const document = {
  getElementById: id => id === 'timeline-grid' ? grid : id === 'timeline-heading' ? heading : null,
  createElement: tag => new Element(tag),
};
const window = { location: { origin: 'http://localhost' } };
const state = {
  scenes: [
    {
      id: 'scene-attributed',
      start: 0,
      end: 5,
      summary: 'Canonical attributed summary.',
      summary_meta: {
        source: 'explicit_summary',
        provenance_status: 'observed',
        qualification: 'Summary source: model-generated context summary (unverified; check evidence channels).',
      },
    },
    {
      id: 'scene-historical',
      start: 5,
      end: 10,
      summary: 'Canonical historical summary.',
    },
  ],
  videos: [],
  graph: { nodes: [] },
  selectedEntities: [],
  lastQuery: 'table',
  activeSearchTab: 'multimodal',
  searchActive: true,
  searchResults: [
    { scene_id: 'scene-attributed', start_time: 0, end_time: 5 },
    { scene_id: 'scene-historical', start_time: 5, end_time: 10, summary: 'Historical search result summary.' },
  ],
};
const scenePassesIntelFilter = () => true;
const resolveKeyframeUrl = () => null;
eval(source);
const findByClass = (root, cls) => {
  const out = [];
  const visit = el => {
    if ((el.className || '').split(/\s+/).includes(cls)) out.push(el.textContent);
    (el.children || []).forEach(visit);
  };
  visit(root);
  return out;
};
renderTimelineGrid();
const multimodalSummaries = findByClass(grid, 'scene-card-summary');
const multimodalQuals = findByClass(grid, 'scene-card-summary-qualification');
state.activeSearchTab = 'narrative';
renderTimelineGrid();
const narrativeSummaries = findByClass(grid, 'scene-card-summary');
const narrativeQuals = findByClass(grid, 'scene-card-summary-qualification');
process.stdout.write(JSON.stringify({
  multimodalSummaries,
  multimodalQuals,
  narrativeSummaries,
  narrativeQuals,
}));
'''
    res = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps(source),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        timeout=20,
        check=True,
    )
    cards = json.loads(res.stdout)
    assert cards["multimodalSummaries"] == [
        "Canonical attributed summary.",
        "Canonical historical summary.",
    ]
    assert cards["multimodalQuals"] == [
        "Summary source: model-generated context summary (unverified; check evidence channels).",
        "Summary source: unknown provenance (historical or unattributed summary; unverified, check evidence channels).",
    ]
    assert cards["narrativeSummaries"] == [
        "Canonical attributed summary.",
        "Historical search result summary.",
    ]
    assert cards["narrativeQuals"] == [
        "Summary source: model-generated context summary (unverified; check evidence channels).",
        "Summary source: unknown provenance (historical or unattributed summary; unverified, check evidence channels).",
    ]
