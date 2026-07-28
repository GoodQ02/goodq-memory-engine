import json
from pathlib import Path
import pytest
from cli.signature_backfill_execute import SignatureBackfillError
from cli.signature_backfill_execute import build_plan, execute_plan, plan_digest
def put(path, value): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value),encoding="utf-8")
def test_token_bound_scene_backfill_updates_only_signature_fields(tmp_path):
 m=tmp_path/'epoch/processing/v/video/scene_manifest.json'; t=tmp_path/'epoch/processing/v/temporal_index.json'; p=tmp_path/'proof/result.json'
 put(m,{"scenes":[{"scene_id":"s","audio":{"speaker_voice_signature_meta":{"status":"error","reason":"embedding_step_failed"},"full_text":"keep"}}]}); put(t,{"segments":[{"scene_id":"s","full_transcript":"keep"},{"scene_id":"other","x":1}]}); put(p,{"status":"success","mode":"signature_only","speaker_voice_signatures":[{"embedding_dim":768}],"speaker_voice_signature_meta":{"status":"ok","emitted":1}})
 plan=build_plan(m,t,"s",p); receipt=execute_plan(plan,plan_digest(plan)); out=json.loads(m.read_text()); temporal=json.loads(t.read_text())
 assert receipt["status"]=="signature_backfill_committed"; assert out["scenes"][0]["audio"]["full_text"]=="keep"; assert out["scenes"][0]["audio"]["speaker_voice_signature_meta"]["status"]=="ok"; assert temporal["segments"][1]=={"scene_id":"other","x":1}; assert Path(receipt["backup_root"]).is_dir()

def test_backfill_rejects_an_unbound_token(tmp_path):
 m=tmp_path/'epoch/processing/v/video/scene_manifest.json'; t=tmp_path/'epoch/processing/v/temporal_index.json'; p=tmp_path/'proof/result.json'
 put(m,{"scenes":[{"scene_id":"s","audio":{"speaker_voice_signature_meta":{"status":"error","reason":"embedding_step_failed"}}}]}); put(t,{"segments":[{"scene_id":"s"}]}); put(p,{"status":"success","mode":"signature_only","speaker_voice_signatures":[{"embedding_dim":768}],"speaker_voice_signature_meta":{"status":"ok"}})
 plan=build_plan(m,t,"s",p)
 with pytest.raises(SignatureBackfillError, match="confirmation token"):
  execute_plan(plan,"wrong-token")
 assert json.loads(m.read_text())["scenes"][0]["audio"]["speaker_voice_signature_meta"]["status"]=="error"
