"""Token-bound one-scene signature-only backfill with rollback."""
from __future__ import annotations
import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from steps.common.atomic_io import atomic_write_json_for_concurrent_readers

class SignatureBackfillError(RuntimeError): pass

def _read(path: Path) -> dict[str, Any]:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise SignatureBackfillError(f"expected object: {path}")
    return value
def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def _digest(value: Any) -> str: return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def build_plan(manifest_path: Path, temporal_path: Path, scene_id: str, proof_result_path: Path) -> dict[str, Any]:
    manifest=_read(manifest_path); temporal=_read(temporal_path); proof=_read(proof_result_path)
    scenes=[s for s in manifest.get("scenes",[]) if isinstance(s,dict) and s.get("scene_id")==scene_id]
    segments=[s for s in temporal.get("segments",[]) if isinstance(s,dict) and s.get("scene_id")==scene_id]
    if len(scenes)!=1 or len(segments)!=1: raise SignatureBackfillError("scene authority is ambiguous or missing")
    audio=scenes[0].get("audio") if isinstance(scenes[0].get("audio"),dict) else {}
    meta=audio.get("speaker_voice_signature_meta") if isinstance(audio.get("speaker_voice_signature_meta"),dict) else {}
    signatures=proof.get("speaker_voice_signatures")
    proof_meta=proof.get("speaker_voice_signature_meta")
    if (meta.get("status"),meta.get("reason")) != ("error","embedding_step_failed"): raise SignatureBackfillError("scene is not an eligible historical signature failure")
    if proof.get("status")!="success" or proof.get("mode")!="signature_only" or not isinstance(signatures,list) or not signatures or not isinstance(proof_meta,dict): raise SignatureBackfillError("proof receipt lacks successful signature evidence")
    if not all(isinstance(s,dict) and int(s.get("embedding_dim") or 0)==768 for s in signatures): raise SignatureBackfillError("proof signatures are not 768-dimensional")
    return {"status":"ready","kind":"signature_only_scene_backfill","scene_id":scene_id,"manifest_path":str(manifest_path),"temporal_path":str(temporal_path),"proof_result_path":str(proof_result_path),"manifest_sha256":_sha(manifest_path),"temporal_sha256":_sha(temporal_path),"proof_sha256":_sha(proof_result_path),"signature_count":len(signatures),"provenance_policy":{"kind":"signature_only_backfill","retrieval_effect":"none","ranking_effect":"none","confidence_effect":"none"}}

def plan_digest(plan: dict[str,Any]) -> str: return _digest({k:plan[k] for k in plan if k!="status"})

def execute_plan(plan: dict[str,Any], token: str) -> dict[str,Any]:
    if plan.get("status")!="ready" or token!=plan_digest(plan): raise SignatureBackfillError("confirmation token does not match inspected plan")
    manifest_path=Path(plan["manifest_path"]); temporal_path=Path(plan["temporal_path"]); proof_path=Path(plan["proof_result_path"])
    if _sha(manifest_path)!=plan["manifest_sha256"] or _sha(temporal_path)!=plan["temporal_sha256"] or _sha(proof_path)!=plan["proof_sha256"]: raise SignatureBackfillError("authority changed after planning")
    epoch_root=manifest_path.parents[3]; op=f"signature_backfill_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{token[:12]}"; root=epoch_root/"signature_backfills"/op; backup=root/"backup"; backup.mkdir(parents=True)
    originals={manifest_path:manifest_path.read_bytes(),temporal_path:temporal_path.read_bytes()}
    for path,raw in originals.items(): (backup/path.name).write_bytes(raw)
    try:
        manifest=_read(manifest_path); temporal=_read(temporal_path); proof=_read(proof_path); scene_id=plan["scene_id"]
        scene=next(s for s in manifest["scenes"] if isinstance(s,dict) and s.get("scene_id")==scene_id); segment=next(s for s in temporal["segments"] if isinstance(s,dict) and s.get("scene_id")==scene_id)
        audio=scene["audio"]; audio["speaker_voice_signatures"]=proof["speaker_voice_signatures"]; audio["speaker_voice_signature_meta"]={**proof["speaker_voice_signature_meta"],"provenance":plan["provenance_policy"]}
        segment["speaker_voice_signature_count"]=len(proof["speaker_voice_signatures"]); segment["speaker_voice_signature_meta"]=audio["speaker_voice_signature_meta"]
        temporal["segments_with_speaker_voice_signatures"]=sum(1 for s in temporal["segments"] if isinstance(s,dict) and int(s.get("speaker_voice_signature_count") or 0)>0)
        atomic_write_json_for_concurrent_readers(manifest_path,manifest); atomic_write_json_for_concurrent_readers(temporal_path,temporal)
    except Exception as exc:
        for path,raw in originals.items(): path.write_bytes(raw)
        raise SignatureBackfillError(f"backfill rolled back: {exc}") from exc
    receipt={"status":"signature_backfill_committed","operation_id":op,"plan_digest":token,"scene_id":plan["scene_id"],"signature_count":plan["signature_count"],"backup_root":str(backup),"manifest_sha256":_sha(manifest_path),"temporal_sha256":_sha(temporal_path),"provenance_policy":plan["provenance_policy"]}
    atomic_write_json_for_concurrent_readers(root/"receipt.json",receipt); return receipt
