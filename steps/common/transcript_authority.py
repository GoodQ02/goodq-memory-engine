"""Scene/run transcript authority stored in the existing UCF ledger."""
import hashlib
import json
import sqlite3
from pathlib import Path
from contextlib import closing
from steps.common.sqlite_read_authority import open_sqlite_read_connection
from steps.common.ucf_retirement import assert_scene_write_allowed
# Persisted worker identity is retained for compatibility with qualified records.
WORKER='transcript_outcome_binding_candidate'
def canonical(v):return json.dumps(v,sort_keys=True)
def sha(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def dbpath(cfg):return Path(cfg['paths']['db_dir'])/'ucf'/'ucf_ledger.db'
def fetch(conn,video,scene,epoch,*,allow_promoted=False):
    rows=conn.execute('SELECT run_id,payload,payload_hash,promotion_status FROM context_frames WHERE video_hash=? AND epoch_id=? AND source_artifact_id=? AND worker_name=?',(video,epoch,scene,WORKER)).fetchall()
    if len(rows)!=1:return None
    run,raw,h,status=rows[0]
    try:r=json.loads(raw)
    except (ValueError,TypeError):return None
    if not isinstance(r,dict) or sha(r)!=h or status not in ({'validated','promoted'} if allow_promoted else {'validated'}):return None
    if any(r.get(k)!=v for k,v in [('video_id',video),('scene_id',scene),('epoch_id',epoch),('run_id',run)]):return None
    return r
def lookup(video,scene,cfg):
    if not isinstance(cfg, dict) or not (cfg.get('paths') or {}).get('db_dir'):
        return None
    p=dbpath(cfg);epoch=p.parents[1].name
    if not p.is_file():return None
    try:
        with closing(open_sqlite_read_connection(p)) as c:return fetch(c,video,scene,epoch,allow_promoted=True)
    except (sqlite3.Error, OSError):return None
def emit(scene,video,run,cfg,previous_digest=None):
    from steps.common import transcript_binding as b
    epoch=Path(cfg['paths']['db_dir']).name
    if scene.get('video_id')!=video:raise ValueError('producer source mismatch')
    audio=scene.get('audio') or {}
    if not isinstance(audio,dict):raise ValueError('invalid audio')
    text=audio.get('full_text',audio.get('transcript',''))
    if not isinstance(text,str):raise ValueError('invalid text')
    text=text.strip()  # Matches harmonizer transcript normalization.
    record={'schema':1,'video_id':video,'scene_id':scene.get('scene_id'),'run_id':run,'epoch_id':epoch,
            'outcome':scene.get('transcript_outcome'),'outcome_reason':scene.get('transcript_outcome_reason'),
            'text_sha256':b.digest(text)}
    checked=b.validate(record,{k:record[k] for k in b.KEYS},text)
    if checked['status']!='bound':raise ValueError(checked['reason'])
    if audio.get('transcript_outcome') not in (None,record['outcome']):raise ValueError('producer outcome conflict')
    if audio.get('transcript_outcome_reason') not in (None,record['outcome_reason']):raise ValueError('producer reason conflict')
    if (scene.get('audio_error') or audio.get('error')) and record['outcome']!='runtime_failure':raise ValueError('producer error conflict')
    meta=audio.get('transcript_meta') or {}
    if not isinstance(meta,dict):raise ValueError('invalid worker metadata')
    if meta.get('status') in {'failed','error','no_transcript_output'} and record['outcome']!='runtime_failure':raise ValueError('worker failure conflict')
    p=dbpath(cfg)
    raw={'transcript_outcome_evidence':record,'audio':audio,'audio_error':scene.get('audio_error')}
    raw_path=p.parent/'raw_refs'/(sha(raw)+'.json')
    raw_path.parent.mkdir(parents=True,exist_ok=True)
    from steps.common.atomic_io import atomic_write_json
    if not raw_path.exists():atomic_write_json(raw_path,raw)
    if json.loads(raw_path.read_text(encoding='utf-8'))!=raw:raise ValueError('raw reference conflict')
    # Caller initializes/registers its disposable UCF ledger via existing API.
    with closing(sqlite3.connect(p)) as c, c:
        c.execute('BEGIN IMMEDIATE')
        rows=c.execute('SELECT frame_id FROM context_frames WHERE video_hash=? AND epoch_id=? AND source_artifact_id=? AND worker_name=?',(video,epoch,scene['scene_id'],WORKER)).fetchall()
        assert_scene_write_allowed(
            c, video_hash=video, epoch_id=epoch, source_artifact_id=scene['scene_id'],
            payload=record,
        )
        for row in rows:
            assert_scene_write_allowed(
                c, video_hash=video, epoch_id=epoch, source_artifact_id=scene['scene_id'],
                payload=record, conflict_frame_id=row[0],
            )
        current=fetch(c,video,scene['scene_id'],epoch)
        if rows and current is None:raise ValueError('ambiguous or corrupt authority')
        if current==record:return record  # Exact idempotent completion only.
        if (sha(current) if current else None)!=previous_digest:raise ValueError('stale producer attempt')
        values=(run,canonical(record),sha(record),str(raw_path.resolve()))
        if rows:
            c.execute('UPDATE context_frames SET run_id=?,payload=?,payload_hash=?,raw_ref=? WHERE frame_id=?',(*values,rows[0][0]))
        else:
            c.execute('INSERT INTO context_frames (video_hash,ucf_schema_version,epoch_id,run_id,t_start,t_end,modality,worker_name,model_tag,source_artifact_id,payload,payload_hash,promotion_status,raw_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (video,'ucf.v0.1',epoch,run,scene['start'],scene['end'],'audio',WORKER,'binding-v1',scene['scene_id'],canonical(record),sha(record),'validated',str(raw_path.resolve())))
    return record
