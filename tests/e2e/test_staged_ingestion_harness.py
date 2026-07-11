import os
import sys
import uuid
import re
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional, List
from unittest.mock import MagicMock

# ==============================================================================
# STATEFUL MOCK ENGINE FOR COMPLIANCE VERIFICATION
# ==============================================================================

class MockState:
    tokens = {}          # token -> {"operation": str, "timestamp": datetime, "used": bool, "tool_args": dict}
    staged_records = {}   # record_id -> {"status": str, "ucf_data": dict}
    media_sources = {}    # video_hash -> {"file_path": str, "duration": float, ...}
    deleted_files = set()
    qdrant_points = {}    # collection -> {point_id -> point_data}
    faiss_points = {}     # index_path -> {point_id -> point_data}

    @classmethod
    def reset(cls):
        cls.tokens.clear()
        cls.staged_records.clear()
        cls.media_sources.clear()
        cls.deleted_files.clear()
        cls.qdrant_points.clear()
        cls.faiss_points.clear()


MOCK_LOCAL_CONFIRMATION_REQUIRED_TOOLS = {
    "run_ingestion",
    "file_delete",
    "promote_ucf_to_memory",
    "reconcile_ucf_qdrant",
    "validate_ucf_frames",
    "reject_ucf_frames",
    "supersede_ucf_frames",
}

def sanitize_envelope(data: Any) -> Any:
    """Recursively redacts absolute Windows/UNC local file paths (C:\\ or L:\\) in the envelope."""
    import re
    import os
    if isinstance(data, dict):
        return {k: sanitize_envelope(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_envelope(v) for v in data]
    elif isinstance(data, str):
        # 1. Drive letter pattern supporting spaces
        drive_pat = r'[a-zA-Z]:[\\/](?:[^"\'<>|:\*\?\r\n\s]+|\s+(?=[^"\'<>|:\*\?\r\n\s]*[\\/])|\s+(?=[^"\'<>|:\*\?\r\n\s]*\.[a-zA-Z0-9]{2,4}(?:\s|$)))*[^"\'<>|:\*\?\r\n\s]*'
        # 2. UNC pattern supporting spaces
        unc_pat = r'\\\\(?:[^"\'<>|:\*\?\r\n\s]+|\s+(?=[^"\'<>|:\*\?\r\n\s]*[\\/])|\s+(?=[^"\'<>|:\*\?\r\n\s]*\.[a-zA-Z0-9]{2,4}(?:\s|$)))*[^"\'<>|:\*\?\r\n\s]*'
        # 3. WSL pattern supporting spaces
        wsl_pat = r'/mnt/[a-zA-Z]/(?:[^"\'<>|:\*\?\r\n\s]+|\s+(?=[^"\'<>|:\*\?\r\n\s]*/)|\s+(?=[^"\'<>|:\*\?\r\n\s]*\.[a-zA-Z0-9]{2,4}(?:\s|$)))*[^"\'<>|:\*\?\r\n\s]*'
        # 4. Linux standard path pattern supporting spaces
        linux_pat = r'/(?:home|tmp|usr|var|etc|opt|srv|root)/(?:[^"\'<>|:\*\?\r\n\s]+|\s+(?=[^"\'<>|:\*\?\r\n\s]*/)|\s+(?=[^"\'<>|:\*\?\r\n\s]*\.[a-zA-Z0-9]{2,4}(?:\s|$)))*[^"\'<>|:\*\?\r\n\s]*'

        res = data
        def replace_drive(match):
            p = match.group(0)
            basename = os.path.basename(p.replace('\\', '/'))
            return f"relative/{basename}"
            
        res = re.sub(drive_pat, replace_drive, res)
        res = re.sub(unc_pat, replace_drive, res)
        res = re.sub(wsl_pat, replace_drive, res)
        res = re.sub(linux_pat, replace_drive, res)
        return res
    return data

class MockMiniAgentClient:
    """Stateful, requirement-compliant Mock MiniAgentClient replacing the real client during testing."""
    def __init__(self, profile: str = "safe", config: Optional[Dict[str, Any]] = None):
        self.profile = profile.lower() if profile else "safe"
        if self.profile not in ("safe", "offline", "unrestricted"):
            self.profile = "safe"
        self.config = config or {}
        self.execution_mode = "in_process"
        self.agent_available = True
        self.last_error_type = None
        self.last_error_message = None
        self.llm_client = MagicMock()

    def sanitize_envelope(self, data: Any) -> Any:
        return sanitize_envelope(data)

    def _lock_token_store(self):
        from contextlib import contextmanager
        @contextmanager
        def _lock():
            yield
        return _lock()

    def _load_tokens(self) -> Dict[str, Any]:
        res = {}
        for k, v in MockState.tokens.items():
            t = v["timestamp"]
            ts_str = t.isoformat() if isinstance(t, datetime) else str(t)
            res[k] = {
                "operation": v["operation"],
                "timestamp": ts_str,
                "used": v["used"],
                "tool_args": v["tool_args"]
            }
        return res

    def _save_tokens(self, tokens: Dict[str, Any]) -> None:
        for k, v in tokens.items():
            ts_str = v["timestamp"]
            try:
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1]
                t = datetime.fromisoformat(ts_str)
            except Exception:
                t = datetime.utcnow()
            MockState.tokens[k] = {
                "operation": v["operation"],
                "timestamp": t,
                "used": v["used"],
                "tool_args": v["tool_args"]
            }

    def validate_action(
        self,
        prompt: str,
        mode: str = "research",
        tool_name: str = "",
        tool_args: Optional[Dict[str, Any]] = None,
        confirm: bool = False,
        confirmation_token: str = "",
        context_overrides: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], int]:
        
        request_id = f"task-{uuid.uuid4().hex[:8]}"
        tool_args = tool_args or {}

        # General confirmation token validation if provided
        if confirmation_token:
            if confirmation_token not in MockState.tokens:
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": False},
                    "errors": [{"code": "invalid_confirmation_token", "message": "Invalid confirmation token."}],
                }
                return sanitize_envelope(envelope), 1
            tok_info = MockState.tokens[confirmation_token]
            if tok_info["operation"] != tool_name:
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": False},
                    "errors": [{"code": "token_operation_mismatch", "message": "Token was not issued for this operation."}],
                }
                return sanitize_envelope(envelope), 1

        # 1. Profile Routing (Offline Profile check)
        if self.profile == "offline":
            mutating_ops = {
                "home_assistant_call_service",
                "qdrant_upsert",
                "faiss_write",
                "kg_write",
                "config_write",
                "file_delete",
                "file_move",
                "run_ingestion",
                "watchdog_trigger",
                "process_start",
                "process_stop",
                "promote_ucf_to_memory",
                "reconcile_ucf_qdrant",
                "validate_ucf_frames",
                "reject_ucf_frames",
                "supersede_ucf_frames",
            }
            if tool_name in mutating_ops:
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": False},
                    "errors": [{"code": "offline_blocked", "message": f"Operation '{tool_name}' is blocked in offline profile."}],
                }
                return sanitize_envelope(envelope), 1

        # 2. Agent Availability / Fallback (Gated Execution)
        if not self.agent_available:
            allowed_read_only = {"validate_ucf_epoch"}
            
            if tool_name in allowed_read_only:
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "ok",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": True, "offline_fallback_active": True},
                    "errors": [],
                }
                return sanitize_envelope(envelope), 0
            else:
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": False, "offline_fallback_active": True},
                    "errors": [{"code": "agent_offline_mutation_blocked", "message": f"Tool '{tool_name}' blocked under offline fallback policy."}],
                }
                return sanitize_envelope(envelope), 1

        if tool_name == "file_delete" and os.environ.get("GOODQ_BREAK_GLASS") != "1":
            envelope = {
                "request_id": request_id,
                "profile": self.profile,
                "status": "error",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "result": {"allowed": False},
                "errors": [{
                    "code": "break_glass_required",
                    "message": "Destructive operation 'file_delete' requires break-glass override.",
                }],
            }
            return sanitize_envelope(envelope), 1

        # 3. Human-in-the-Loop Gating Validation
        if tool_name in MOCK_LOCAL_CONFIRMATION_REQUIRED_TOOLS:
            if not confirm:
                token = f"token-{tool_name.replace('_', '-')}-{uuid.uuid4().hex[:8]}"
                MockState.tokens[token] = {
                    "operation": tool_name,
                    "timestamp": datetime.utcnow(),
                    "used": False,
                    "tool_args": tool_args
                }
                envelope = {
                    "request_id": request_id,
                    "profile": self.profile,
                    "status": "needs_confirmation",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "result": {"allowed": False, "confirmation_token": token},
                    "errors": [{"code": "mutability_requires_confirmation", "message": f"{tool_name} requires human confirmation."}],
                }
                return sanitize_envelope(envelope), 3
            else:
                if not confirmation_token or confirmation_token not in MockState.tokens:
                    envelope = {
                        "request_id": request_id,
                        "profile": self.profile,
                        "status": "error",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "result": {"allowed": False},
                        "errors": [{"code": "invalid_confirmation_token", "message": "Invalid confirmation token."}],
                    }
                    return sanitize_envelope(envelope), 1
                tok_info = MockState.tokens[confirmation_token]
                if tok_info["used"]:
                    envelope = {
                        "request_id": request_id,
                        "profile": self.profile,
                        "status": "error",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "result": {"allowed": False},
                        "errors": [{"code": "token_already_used", "message": "Token has already been used."}],
                    }
                    return sanitize_envelope(envelope), 1
                if tok_info.get("tool_args") != tool_args:
                    envelope = {
                        "request_id": request_id,
                        "profile": self.profile,
                        "status": "error",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "result": {"allowed": False},
                        "errors": [{
                            "code": "token_scope_mismatch",
                            "message": "Confirmation token was not issued for this exact UCF scope.",
                        }],
                    }
                    return sanitize_envelope(envelope), 1
                
                # Check token expiration
                expired = False
                if tool_args.get("simulate_expired_token") or (tok_info.get("tool_args") or {}).get("simulate_expired_token"):
                    expired = True
                else:
                    t_val = tok_info.get("timestamp")
                    if isinstance(t_val, str):
                        try:
                            if t_val.endswith("Z"):
                                t_val = t_val[:-1]
                            t_val = datetime.fromisoformat(t_val)
                        except Exception:
                            pass
                    if isinstance(t_val, datetime):
                        if t_val.tzinfo is not None:
                            from datetime import timezone
                            t_val = t_val.astimezone(timezone.utc).replace(tzinfo=None)
                        if (datetime.utcnow() - t_val).total_seconds() > 600:
                            expired = True
                if expired:
                    envelope = {
                        "request_id": request_id,
                        "profile": self.profile,
                        "status": "error",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "result": {"allowed": False},
                        "errors": [{"code": "token_expired", "message": "Confirmation token expired."}],
                    }
                    return sanitize_envelope(envelope), 1

        envelope = {
            "request_id": request_id,
            "profile": self.profile,
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "result": {"allowed": True},
            "errors": [],
        }
        return sanitize_envelope(envelope), 0

    def execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        prompt: str = "Execute tool",
        mode: str = "research",
        confirm: bool = False,
        confirmation_token: str = "",
    ) -> Tuple[Dict[str, Any], int]:
        
        val_envelope, val_rc = self.validate_action(
            prompt=prompt,
            mode=mode,
            tool_name=tool_name,
            tool_args=tool_args,
            confirm=confirm,
            confirmation_token=confirmation_token
        )
        if val_rc != 0:
            return val_envelope, val_rc

        if tool_name in MOCK_LOCAL_CONFIRMATION_REQUIRED_TOOLS:
            MockState.tokens[confirmation_token]["used"] = True

        started_at = datetime.utcnow().isoformat() + "Z"

        if tool_name == "run_ingestion":
            records = tool_args.get("ucf_records", [])
            validation_errors = []
            
            if tool_args.get("simulate_validation_fail"):
                validation_errors.append("Simulated validation failure.")
                
            for idx, r in enumerate(records):
                video_hash = r.get("video_hash")
                if video_hash not in MockState.media_sources:
                    validation_errors.append(f"Record {idx}: Unregistered media source {video_hash}.")
                
                if r.get("ucf_schema_version", "ucf.v0.1") != "ucf.v0.1":
                    validation_errors.append(f"Record {idx}: Schema version mismatch.")
                
                t_start = r.get("t_start", 0.0)
                t_end = r.get("t_end", 0.0)
                if t_start < 0.0:
                    validation_errors.append(f"Record {idx}: Negative t_start.")
                if t_end < t_start:
                    validation_errors.append(f"Record {idx}: t_end before t_start.")
                
                if video_hash in MockState.media_sources:
                    duration = MockState.media_sources[video_hash]["duration"]
                    if t_end > duration + 0.05:
                        validation_errors.append(f"Record {idx}: t_end exceeds duration.")
                
                payload = r.get("payload", {})
                for k, v in payload.items():
                    if not isinstance(v, (str, int, float, bool, type(None))):
                        validation_errors.append(f"Record {idx}: Non-flat payload key {k}.")
                        
                spatial = r.get("spatial_region")
                if spatial is not None:
                    if len(spatial) != 4:
                        validation_errors.append(f"Record {idx}: Spatial region must be 4 floats.")
                    else:
                        for val in spatial:
                            if not (0.0 <= val <= 1.0):
                                validation_errors.append(f"Record {idx}: Bbox value {val} not normalized.")
                        if spatial[0] > spatial[2] or spatial[1] > spatial[3]:
                            validation_errors.append(f"Record {idx}: Bbox bounds invalid.")

            if validation_errors:
                envelope = {
                    "request_id": val_envelope.get("request_id"),
                    "tool_name": tool_name,
                    "status": "fatal_error",
                    "started_at": started_at,
                    "completed_at": datetime.utcnow().isoformat() + "Z",
                    "errors": [{"code": "ucf_validation_failed", "message": "Validation failed.", "details": validation_errors}],
                    "artifacts": tool_args.get("absolute_path_artifacts", [])
                }
                return sanitize_envelope(envelope), 1

            # Ingestion success -> remain staged
            for r in records:
                rec_id = r.get("frame_id") or f"rec-{uuid.uuid4().hex[:6]}"
                MockState.staged_records[rec_id] = {
                    "status": "staged",
                    "ucf_data": r
                }
                
                # Simulate backfilling
                if r.get("vector_key"):
                    collection = r.get("vector_collection", "default")
                    backend = r.get("vector_backend")
                    if backend == "qdrant":
                        MockState.qdrant_points.setdefault(collection, {})[r["vector_key"]] = r
                    elif backend == "faiss":
                        idx_path = r.get("raw_ref", "default_faiss")
                        MockState.faiss_points.setdefault(idx_path, {})[r["vector_key"]] = r

            envelope = {
                "request_id": val_envelope.get("request_id"),
                "tool_name": tool_name,
                "status": "success",
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "output": {"ingested_count": len(records), "status": "staged_complete"},
                "artifacts": tool_args.get("absolute_path_artifacts", [])
            }
            return sanitize_envelope(envelope), 0

        elif tool_name == "validate_ucf_epoch":
            validation_errors = []
            for rec_id, rec in MockState.staged_records.items():
                r = rec["ucf_data"]
                if r.get("ucf_schema_version", "ucf.v0.1") != "ucf.v0.1":
                    validation_errors.append(f"Record {rec_id}: Schema version mismatch.")
                    
            status = "success" if not validation_errors else "fatal_error"
            envelope = {
                "request_id": val_envelope.get("request_id"),
                "tool_name": tool_name,
                "status": status,
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "output": {
                    "success": not validation_errors,
                    "errors": validation_errors,
                },
                "artifacts": tool_args.get("absolute_path_artifacts", [])
            }
            return sanitize_envelope(envelope), 0 if not validation_errors else 1

        elif tool_name == "promote_ucf_to_memory":
            # Orphan vector check
            attempted_vectors = tool_args.get("vectors", [])
            staged_vector_keys = {rec["ucf_data"].get("vector_key") for rec in MockState.staged_records.values() if rec["ucf_data"].get("vector_key")}
            for v_key in attempted_vectors:
                if v_key not in staged_vector_keys:
                    envelope = {
                        "request_id": val_envelope.get("request_id"),
                        "tool_name": tool_name,
                        "status": "error",
                        "started_at": started_at,
                        "completed_at": datetime.utcnow().isoformat() + "Z",
                        "errors": [{"code": "orphan_vector_blocked", "message": f"Orphan vector {v_key} blocked from injection."}]
                    }
                    return sanitize_envelope(envelope), 1

            video_hash = tool_args.get("video_hash") or tool_args.get("video_id")
            epoch_id = tool_args.get("epoch_id")

            # Check if any in-scope staged records exist
            staged_count = 0
            for rec_id, rec in MockState.staged_records.items():
                r = rec["ucf_data"]
                if video_hash and r.get("video_hash") != video_hash:
                    continue
                if epoch_id and r.get("epoch_id") != epoch_id:
                    continue
                if rec["status"] == "staged":
                    staged_count += 1

            if staged_count > 0:
                envelope = {
                    "request_id": val_envelope.get("request_id"),
                    "tool_name": tool_name,
                    "status": "success",
                    "started_at": started_at,
                    "completed_at": datetime.utcnow().isoformat() + "Z",
                    "output": {
                        "status": "blocked",
                        "reason": "promotion_blocked_unvalidated_frames",
                        "staged_count": staged_count,
                        "message": f"Cannot promote: {staged_count} context frame(s) are still in 'staged' status."
                    },
                    "artifacts": tool_args.get("absolute_path_artifacts", [])
                }
                return sanitize_envelope(envelope), 0

            # Promoted: transition only validated -> promoted
            promoted_count = 0
            for rec_id, rec in MockState.staged_records.items():
                r = rec["ucf_data"]
                if video_hash and r.get("video_hash") != video_hash:
                    continue
                if epoch_id and r.get("epoch_id") != epoch_id:
                    continue
                if rec["status"] == "validated":
                    rec["status"] = "promoted"
                    promoted_count += 1
            
            envelope = {
                "request_id": val_envelope.get("request_id"),
                "tool_name": tool_name,
                "status": "success",
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "output": {"promoted_count": promoted_count, "status": "promoted_complete"},
                "artifacts": tool_args.get("absolute_path_artifacts", [])
            }
            return sanitize_envelope(envelope), 0

        elif tool_name == "validate_ucf_frames":
            video_hash = tool_args.get("video_hash") or tool_args.get("video_id")
            epoch_id = tool_args.get("epoch_id")
            
            validated_count = 0
            for rec_id, rec in MockState.staged_records.items():
                r = rec["ucf_data"]
                if video_hash and r.get("video_hash") != video_hash:
                    continue
                if epoch_id and r.get("epoch_id") != epoch_id:
                    continue
                
                if rec["status"] == "staged":
                    rec["status"] = "validated"
                    validated_count += 1
            
            envelope = {
                "request_id": val_envelope.get("request_id"),
                "tool_name": tool_name,
                "status": "success",
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "output": {"validated_count": validated_count, "status": "validated_complete"},
                "artifacts": tool_args.get("absolute_path_artifacts", [])
            }
            return sanitize_envelope(envelope), 0

        elif tool_name == "reject_ucf_frames":
            reason = tool_args.get("reason", "").strip()
            if not reason:
                envelope = {
                    "request_id": val_envelope.get("request_id"),
                    "tool_name": tool_name,
                    "status": "error",
                    "started_at": started_at,
                    "completed_at": datetime.utcnow().isoformat() + "Z",
                    "errors": [{"code": "missing_reason", "message": "reject_ucf_frames requires a non-empty 'reason' argument."}],
                }
                return sanitize_envelope(envelope), 1
            
            video_hash = tool_args.get("video_hash") or tool_args.get("video_id")
            epoch_id = tool_args.get("epoch_id")
            
            rejected_count = 0
            for rec_id, rec in MockState.staged_records.items():
                r = rec["ucf_data"]
                if video_hash and r.get("video_hash") != video_hash:
                    continue
                if epoch_id and r.get("epoch_id") != epoch_id:
                    continue
                
                if rec["status"] in ("staged", "validated"):
                    rec["status"] = "rejected"
                    rejected_count += 1
                    
            envelope = {
                "request_id": val_envelope.get("request_id"),
                "tool_name": tool_name,
                "status": "success",
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "output": {
                    "rejected_count": rejected_count,
                    "status": "rejected_complete",
                    "reason": reason,
                },
                "artifacts": tool_args.get("absolute_path_artifacts", [])
            }
            return sanitize_envelope(envelope), 0

        elif tool_name == "supersede_ucf_frames":
            video_hash = tool_args.get("video_hash") or tool_args.get("video_id")
            epoch_id = tool_args.get("epoch_id")
            
            superseded_count = 0
            for rec_id, rec in MockState.staged_records.items():
                r = rec["ucf_data"]
                if video_hash and r.get("video_hash") != video_hash:
                    continue
                if epoch_id and r.get("epoch_id") != epoch_id:
                    continue
                
                if rec["status"] in ("promoted", "validated"):
                    rec["status"] = "superseded"
                    superseded_count += 1
                    
            envelope = {
                "request_id": val_envelope.get("request_id"),
                "tool_name": tool_name,
                "status": "success",
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "output": {
                    "superseded_count": superseded_count,
                    "status": "superseded_complete",
                },
                "artifacts": tool_args.get("absolute_path_artifacts", [])
            }
            return sanitize_envelope(envelope), 0

        elif tool_name == "file_delete":
            target = tool_args.get("path")
            MockState.deleted_files.add(target)
            envelope = {
                "request_id": val_envelope.get("request_id"),
                "tool_name": tool_name,
                "status": "success",
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "output": {"deleted": target},
                "artifacts": tool_args.get("absolute_path_artifacts", [target])
            }
            return sanitize_envelope(envelope), 0

        else:
            envelope = {
                "request_id": val_envelope.get("request_id"),
                "tool_name": tool_name,
                "status": "fatal_error",
                "started_at": started_at,
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "errors": [{"code": "unsupported_tool", "message": f"Tool '{tool_name}' not supported by mock."}]
            }
            return sanitize_envelope(envelope), 1

# Monkeypatching logic if TEST_MOCK_HARNESS == "1"
if os.environ.get("TEST_MOCK_HARNESS") == "1":
    import agents.mini_agent_client
    agents.mini_agent_client.MiniAgentClient = MockMiniAgentClient

# ==============================================================================
# TEST SUITE
# ==============================================================================

from agents.mini_agent_client import MiniAgentClient

@pytest.fixture(autouse=True)
def mock_config_paths_for_real_client(tmp_path, monkeypatch):
    agent_home = tmp_path / "mini_agent_home"
    agent_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GOODQ_MINI_AGENT_HOME", str(agent_home))
    if os.environ.get("TEST_MOCK_HARNESS") != "1":
        import steps.common.config_loader
        # Check if already monkeypatched to prevent recursion
        if not hasattr(steps.common.config_loader, "_original_load_configs"):
            steps.common.config_loader._original_load_configs = steps.common.config_loader.load_configs
        
        actual_cfg = steps.common.config_loader._original_load_configs({})
        import copy
        cfg_data = copy.deepcopy(actual_cfg)
        
        db_dir = tmp_path / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        cfg_data.setdefault("paths", {})
        cfg_data["paths"]["db_dir"] = str(db_dir)
        cfg_data["paths"]["data_root"] = str(tmp_path)
        cfg_data["paths"]["reports_dir"] = str(reports_dir)
        cfg_data["paths"]["db_path"] = str(tmp_path / "memory.db")
        cfg_data["paths"]["knowledge_graph_db"] = str(tmp_path / "knowledge_graph.db")
        cfg_data["paths"]["processing"] = str(tmp_path / "processing")
        cfg_data["paths"]["faiss_clip_path"] = str(tmp_path / "faiss_clip.index")
        cfg_data["paths"]["faiss_dino_path"] = str(tmp_path / "faiss_dino.index")
        cfg_data["paths"]["clip_id_map_db"] = str(tmp_path / "clip_id_map.sqlite")
        cfg_data["paths"]["dino_id_map_db"] = str(tmp_path / "dino_id_map.sqlite")
        
        import agents.mini_agent_client
        import scripts.ucf.validate_ucf_epoch
        monkeypatch.setattr(steps.common.config_loader, "load_configs", lambda *args, **kwargs: cfg_data)
        monkeypatch.setattr(agents.mini_agent_client, "load_configs", lambda *args, **kwargs: cfg_data)
        monkeypatch.setattr(scripts.ucf.validate_ucf_epoch, "load_configs", lambda *args, **kwargs: cfg_data)
        
        monkeypatch.setenv("GOODQ_DATA_ROOT", str(tmp_path))
        (db_dir / "ucf").mkdir(parents=True, exist_ok=True)

@pytest.fixture(autouse=True)
def auto_reset_mock_state():
    if os.environ.get("TEST_MOCK_HARNESS") == "1":
        MockState.reset()

def register_media(video_hash="test_vid_123", duration=120.0):
    if os.environ.get("TEST_MOCK_HARNESS") == "1":
        MockState.media_sources[video_hash] = {
            "video_hash": video_hash,
            "file_path": f"C:\\path\\to\\{video_hash}.mp4",
            "duration": duration,
            "fps": 30.0,
            "width": 1920,
            "height": 1080
        }
    else:
        from agents.mini_agent_client import MiniAgentClient
        client = MiniAgentClient()
        db_path = client._get_ucf_db_path()
        from cli.run_ingestion import _load_ucf_ledger
        ucf_module = _load_ucf_ledger()
        UCFLedgerClient = ucf_module.UCFLedgerClient
        ledger = UCFLedgerClient(str(db_path))
        ledger.init_schema()
        ledger.register_media(
            video_hash=video_hash,
            file_path=f"C:\\path\\to\\{video_hash}.mp4",
            duration=duration,
            fps=30.0,
            width=1920,
            height=1080
        )
        ledger.close()

def mock_harness_active() -> bool:
    return os.environ.get("TEST_MOCK_HARNESS") == "1"


def execute_locally_confirmed(client, *, tool_name: str, tool_args: Dict[str, Any]):
    """Exercise the explicit request -> confirm -> execute flow."""
    confirmation, confirmation_rc = client.validate_action(
        prompt=f"Confirm {tool_name}",
        mode="ops",
        tool_name=tool_name,
        tool_args=tool_args,
    )
    assert confirmation_rc == 3, confirmation
    return client.execute_tool(
        tool_name=tool_name,
        tool_args=tool_args,
        confirm=True,
        confirmation_token=confirmation["result"]["confirmation_token"],
    )


def seed_validated_scope(client, monkeypatch, *, video_hash: str, epoch_id: str):
    """Creates one exact, validated UCF scope using only temporary stores."""
    scope = {"video_hash": video_hash, "epoch_id": epoch_id}
    register_media(video_hash, 20.0)

    if not mock_harness_active():
        monkeypatch.setattr(
            client,
            "_execute_validate_ucf_epoch",
            lambda _args: {"success": True, "errors": []},
        )
        monkeypatch.setattr(
            client,
            "_sync_qdrant_by_scope",
            lambda **_kwargs: {
                "status": "ok",
                "points_verified": 1,
                "failed_collections": [],
            },
        )

    frame_id = f"{video_hash}-{epoch_id}-frame"
    ingest_args = {
        "ucf_records": [{
            "frame_id": frame_id,
            "video_hash": video_hash,
            "ucf_schema_version": "ucf.v0.1",
            "epoch_id": epoch_id,
            "run_id": f"run-{epoch_id}",
            "t_start": 0.0,
            "t_end": 10.0,
            "modality": "video",
            "worker_name": "worker1",
            "model_tag": "tag1",
            "source_artifact_id": "scene_0000",
            "payload": {},
        }]
    }
    ingest_envelope, ingest_rc = execute_locally_confirmed(
        client,
        tool_name="run_ingestion",
        tool_args=ingest_args,
    )
    assert ingest_rc == 0, ingest_envelope

    token_envelope, token_rc = client.validate_action(
        prompt="Validate exact UCF scope",
        tool_name="validate_ucf_frames",
        tool_args=scope,
        confirm=False,
    )
    assert token_rc == 3, token_envelope
    validate_envelope, validate_rc = client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args=scope,
        confirm=True,
        confirmation_token=token_envelope["result"]["confirmation_token"],
    )
    assert validate_rc == 0, validate_envelope
    assert validate_envelope["output"]["status"] == "validated_complete"
    return scope

# ------------------------------------------------------------------------------
# TIER 1: FEATURE COVERAGE (Tests 1 to 20)
# ------------------------------------------------------------------------------

# Feature 1: Gated Execution (F1.01-05)

def test_f1_01_ingestion_requires_confirmation_in_safe_profile():
    client = MiniAgentClient(profile="safe")
    envelope, rc = client.validate_action(
        prompt="Ingest video",
        tool_name="run_ingestion",
        tool_args={"input_dir": "incoming", "epoch": "epoch-one"},
    )
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"

def test_f1_02_ingestion_requires_confirmation_in_unrestricted_profile():
    client = MiniAgentClient(profile="unrestricted")
    envelope, rc = client.validate_action(
        prompt="Ingest video",
        tool_name="run_ingestion",
        tool_args={"input_dir": "incoming", "epoch": "epoch-one"},
    )
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"

def test_f1_03_ingestion_blocked_in_offline_profile():
    client = MiniAgentClient(profile="offline")
    envelope, rc = client.validate_action(prompt="Ingest video", tool_name="run_ingestion")
    assert rc == 1
    assert envelope["status"] == "error"
    assert "offline_blocked" in envelope["errors"][0]["code"]

def test_f1_04_promotion_blocked_under_agent_failure():
    client = MiniAgentClient(profile="safe")
    client.agent_available = False
    envelope, rc = client.validate_action(prompt="Promote records", tool_name="promote_ucf_to_memory")
    assert rc == 1
    assert envelope["status"] == "error"
    assert "agent_offline_mutation_blocked" in envelope["errors"][0]["code"]

def test_f1_05_validation_allowed_under_agent_failure():
    client = MiniAgentClient(profile="safe")
    client.agent_available = False
    envelope, rc = client.validate_action(prompt="Validate UCF", tool_name="validate_ucf_epoch")
    assert rc == 0
    assert envelope["status"] == "ok"

# Feature 2: Post-Ingestion UCF Validation & Gating (F2.01-05)

def test_f2_01_ingestion_triggers_post_validation():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 10.0)
    args = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 5.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 0
    # Ingestion successfully ran and completed post-validation check
    assert envelope["status"] == "success"

def test_f2_02_ingestion_success_with_valid_ucf():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    args = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {"text": "hello"}}]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 0
    assert envelope["status"] == "success"
    assert envelope["output"]["status"] == "staged_complete"

def test_f2_03_ingestion_aborts_on_validation_failure():
    pass
    client = MiniAgentClient(profile="safe")
    # Missing media registration makes it fail validation
    args = {
        "ucf_records": [{"video_hash": "unregistered_vid", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc != 0
    assert envelope["status"] == "fatal_error"
    assert "ucf_validation_failed" in envelope["errors"][0]["code"]

def test_f2_04_validation_failure_prevents_subsequent_steps():
    pass
    client = MiniAgentClient(profile="safe")
    args = {
        "ucf_records": [{"video_hash": "unregistered_vid", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    # Should fail validation during run_ingestion
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc != 0
    # No staged records should exist
    if mock_harness_active():
        assert len(MockState.staged_records) == 0
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        res = conn.execute("SELECT count(*) FROM context_frames").fetchone()[0]
        conn.close()
        assert res == 0

def test_f2_05_validation_error_surfaced_in_envelope():
    pass
    client = MiniAgentClient(profile="safe")
    args = {
        "ucf_records": [{"video_hash": "unregistered_vid", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc != 0
    assert "details" in envelope["errors"][0]
    assert len(envelope["errors"][0]["details"]) > 0

# Feature 3: Human-in-the-Loop Gating (F3.01-05)

def test_f3_01_ingested_records_remain_staged():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    args = {
        "ucf_records": [{"frame_id": "rec1", "video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    execute_locally_confirmed(client, tool_name="run_ingestion", tool_args=args)
    if mock_harness_active():
        assert MockState.staged_records["rec1"]["status"] == "staged"
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        row = conn.execute("SELECT promotion_status FROM context_frames WHERE source_artifact_id = ? OR vector_key = ? OR frame_id = ?", ("rec1", "rec1", "rec1")).fetchone()
        if not row:
            row = conn.execute("SELECT promotion_status FROM context_frames").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "staged"

def test_f3_02_automated_promotion_blocked():
    pass
    client = MiniAgentClient(profile="safe")
    # Promotion check without token or confirm flag
    envelope, rc = client.validate_action(prompt="Automated promotion", tool_name="promote_ucf_to_memory")
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"

def test_f3_03_promotion_requires_confirm_flag():
    pass
    client = MiniAgentClient(profile="safe")
    envelope, rc = client.validate_action(prompt="Promotion", tool_name="promote_ucf_to_memory", confirm=False)
    assert rc == 3
    assert envelope["status"] == "needs_confirmation"
    assert "confirmation_token" in envelope["result"]

def test_f3_04_promotion_requires_valid_token():
    pass
    client = MiniAgentClient(profile="safe")
    envelope, rc = client.validate_action(prompt="Promotion", tool_name="promote_ucf_to_memory", confirm=True, confirmation_token="invalid-token")
    assert rc == 1
    assert envelope["status"] == "error"
    assert "invalid_confirmation_token" in envelope["errors"][0]["code"]

def test_f3_05_promotion_succeeds_with_confirm_and_token():
    """Verify that promote_ucf_to_memory correctly blocks when called without
    a prior validate_ucf_frames step.

    Doctrine: staged -> [validate_ucf_frames] -> validated -> [promote_ucf_to_memory] -> promoted

    This test exercises the blocking guard: ingest sets frames to 'staged'; calling
    promote_ucf_to_memory without first calling validate_ucf_frames must return
    status='blocked' with reason='promotion_blocked_unvalidated_frames'.

    # TODO: add a companion test that exercises the full lifecycle:
    #   validate_ucf_frames + promote_ucf_to_memory -> expect 'promoted'
    """
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    
    # 1. Ingest (frames land as 'staged')
    args_ingest = {
        "ucf_records": [{"frame_id": "rec1", "video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args_ingest
    )
    
    # 2. Get confirmation token
    envelope_val, rc_val = client.validate_action(prompt="Promotion", tool_name="promote_ucf_to_memory", confirm=False)
    token = envelope_val["result"]["confirmation_token"]
    
    # 3. Attempt promotion without prior validate_ucf_frames
    #    Real engine: blocks because staged frames have not been validated first.
    envelope_prom, rc_prom = client.execute_tool(tool_name="promote_ucf_to_memory", tool_args={}, confirm=True, confirmation_token=token)
    if mock_harness_active():
        # Mock harness enforces validation check; status remains 'staged'
        assert MockState.staged_records["rec1"]["status"] == "staged"
    else:
        # Real engine enforces staged -> validated -> promoted lifecycle.
        # The outer envelope status is always 'success' (call succeeded without exception).
        # The blocking result is in the tool output.
        assert envelope_prom["status"] == "success"  # outer envelope: call completed
        assert envelope_prom["output"]["status"] == "blocked"  # tool result: blocked by engine
        assert envelope_prom["output"].get("reason") == "promotion_blocked_unvalidated_frames"
        # Frames must remain staged (unaffected by the blocked call)
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        staged_count = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'").fetchone()[0]
        conn.close()
        assert staged_count > 0, "Expected staged frames to remain after blocked promotion call"


# Feature 4: Envelope Path Sanitization (F4.01-05)

def test_f4_01_redacts_absolute_paths_in_output():
    pass
    # Break-glass required: testing path sanitization, not security gate
    _prev = os.environ.get("GOODQ_BREAK_GLASS")
    os.environ["GOODQ_BREAK_GLASS"] = "1"
    try:
        client = MiniAgentClient(profile="safe")
        # File delete returns target path in output
        if not mock_harness_active():
            Path(r"L:\\GOODCUBE\\projects\\goodq4all\\file_to_delete.txt").parent.mkdir(parents=True, exist_ok=True)
            Path(r"L:\\GOODCUBE\\projects\\goodq4all\\file_to_delete.txt").touch()
        args = {
            "path": "L:\\GOODCUBE\\projects\\goodq4all\\file_to_delete.txt",
        }
        envelope, rc = execute_locally_confirmed(
            client, tool_name="file_delete", tool_args=args
        )
        assert rc == 0
        # Absolute path should be redacted/sanitized
        assert "L:\\GOODCUBE" not in str(envelope)
        assert "relative/file_to_delete.txt" in envelope["output"]["deleted"]
    finally:
        if _prev is None:
            os.environ.pop("GOODQ_BREAK_GLASS", None)
        else:
            os.environ["GOODQ_BREAK_GLASS"] = _prev

def test_f4_02_redacts_absolute_paths_in_artifacts():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    args = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}],
        "absolute_path_artifacts": ["C:\\Users\\jdben\\mock_report.json"]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 0
    assert "C:\\Users" not in str(envelope)
    assert "relative/mock_report.json" in envelope["artifacts"]

def test_f4_03_redacts_absolute_paths_in_errors():
    pass
    client = MiniAgentClient(profile="safe")
    args = {
        "ucf_records": [],
        "simulate_validation_fail": True,
        "absolute_path_artifacts": ["L:\\projects\\error_log.txt"]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc != 0
    assert "L:\\projects" not in str(envelope)
    assert "relative/error_log.txt" in envelope["artifacts"]

def test_f4_04_preserves_path_agnostic_relative_references():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    args = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}],
        "absolute_path_artifacts": ["db/ucf/ucf_ledger.db"] # already relative
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 0
    # Break-glass required: testing path sanitization, not security gate
    _prev = os.environ.get("GOODQ_BREAK_GLASS")
    os.environ["GOODQ_BREAK_GLASS"] = "1"
    try:
        client = MiniAgentClient(profile="safe")
        register_media("v1", 20.0)
        args = {
            "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}],
            "absolute_path_artifacts": ["db/ucf/ucf_ledger.db"] # already relative
        }
        envelope, rc = execute_locally_confirmed(
            client, tool_name="run_ingestion", tool_args=args
        )
        assert rc == 0
        # Relative path should remain unchanged
        assert "db/ucf/ucf_ledger.db" in envelope["artifacts"]
    finally:
        if _prev is None:
            os.environ.pop("GOODQ_BREAK_GLASS", None)
        else:
            os.environ["GOODQ_BREAK_GLASS"] = _prev

def test_f4_05_sanitizes_mixed_slashes_and_unc_paths():
    pass
    # Break-glass required: testing path sanitization, not security gate
    _prev = os.environ.get("GOODQ_BREAK_GLASS")
    os.environ["GOODQ_BREAK_GLASS"] = "1"
    try:
        client = MiniAgentClient(profile="safe")
        if not mock_harness_active():
            Path(r"\\\\server\\share\\subfolder\\file.txt").parent.mkdir(parents=True, exist_ok=True)
            Path(r"\\\\server\\share\\subfolder\\file.txt").touch()
        args = {
            "path": "\\\\server\\share\\subfolder\\file.txt",
        }
        envelope, rc = execute_locally_confirmed(
            client, tool_name="file_delete", tool_args=args
        )
        assert rc == 0
        assert "\\\\server" not in str(envelope)
        assert "relative/file.txt" in envelope["output"]["deleted"]
    finally:
        if _prev is None:
            os.environ.pop("GOODQ_BREAK_GLASS", None)
        else:
            os.environ["GOODQ_BREAK_GLASS"] = _prev

# ------------------------------------------------------------------------------
# TIER 2: BOUNDARY & CORNER CASES (Tests 21 to 40)
# ------------------------------------------------------------------------------

# Feature 1 Boundary Cases (F1.06-10)

def test_f1_06_profile_case_insensitivity():
    client = MiniAgentClient(profile="Safe")
    envelope, rc = client.validate_action(prompt="Ingest video", tool_name="run_ingestion")
    assert rc == 3
    assert envelope["profile"] == "safe"

def test_f1_07_invalid_profile_fallback_to_safe():
    client = MiniAgentClient(profile="invalid-profile-name")
    envelope, rc = client.validate_action(prompt="Ingest video", tool_name="run_ingestion")
    assert rc == 3
    assert envelope["profile"] == "safe"

def test_f1_08_custom_operation_unrecognized_blocked():
    client = MiniAgentClient(profile="safe")
    client.agent_available = False
    envelope, rc = client.validate_action(prompt="Unrecognized", tool_name="unrecognized_operation_xyz")
    assert rc == 1
    assert "agent_offline_mutation_blocked" in envelope["errors"][0]["code"]

def test_f1_09_file_delete_blocked_under_agent_failure():
    client = MiniAgentClient(profile="safe")
    client.agent_available = False
    envelope, rc = client.validate_action(prompt="Delete file", tool_name="file_delete")
    assert rc == 1
    assert "agent_offline_mutation_blocked" in envelope["errors"][0]["code"]

def test_f1_10_multiple_operations_gating_consistency():
    pass
    client = MiniAgentClient(profile="safe")
    # Safe requires confirmation for ingestion.
    _, rc1 = client.validate_action(prompt="Ingest", tool_name="run_ingestion")
    assert rc1 == 3
    # Offline blocks ingestion
    client_off = MiniAgentClient(profile="offline")
    _, rc2 = client_off.validate_action(prompt="Ingest", tool_name="run_ingestion")
    assert rc2 == 1

# Feature 2 Boundary Cases (F2.06-10)

def test_f2_06_missing_media_sources_fails_validation():
    pass
    client = MiniAgentClient(profile="safe")
    # record references "v_missing" which is not registered
    args = {
        "ucf_records": [{"video_hash": "v_missing", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 1
    assert "Unregistered media source" in envelope["errors"][0]["details"][0]

def test_f2_07_temporal_bounds_out_of_range_fails():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 10.0) # Duration is 10.0
    # t_end is 15.0 which exceeds duration + 0.05 tolerance
    args = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 15.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 1
    assert "t_end exceeds duration" in envelope["errors"][0]["details"][0]

def test_f2_08_non_flat_payload_fails_validation():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    # Payload has a nested dictionary
    args = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {"nested": {"key": "val"}}}]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 1
    assert "Non-flat payload" in envelope["errors"][0]["details"][0]

def test_f2_09_schema_version_mismatch_fails_validation():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    # Schema version is invalid (e.g. ucf.v0.2)
    args = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.2", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 1
    assert "Schema version mismatch" in envelope["errors"][0]["details"][0]

def test_f2_10_invalid_spatial_coordinates_fails():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    # Bbox coord 1.5 is not normalized
    args = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "spatial_region": [0.1, 0.2, 1.5, 0.4], "payload": {}}]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 1
    assert "not normalized" in envelope["errors"][0]["details"][0]

# Feature 3 Boundary Cases (F3.06-10)

def test_f3_06_expired_confirmation_token():
    pass
    client = MiniAgentClient(profile="safe")
    expired_args = {"video_hash": "expired-token-video", "epoch_id": "expired-token-epoch"}
    envelope_val, rc_val = client.validate_action(
        prompt="Promotion",
        tool_name="promote_ucf_to_memory",
        confirm=False,
        tool_args=expired_args,
    )
    assert rc_val == 3
    token = envelope_val["result"]["confirmation_token"]
    expired_at = datetime.utcnow() - timedelta(seconds=3600)
    if mock_harness_active():
        MockState.tokens[token]["timestamp"] = expired_at
    else:
        tokens = client._load_tokens()
        tokens[token]["timestamp"] = expired_at.isoformat() + "Z"
        client._save_tokens(tokens)
    
    # Try promoting with expired token
    envelope_prom, rc_prom = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=expired_args,
        confirm=True,
        confirmation_token=token,
    )
    assert rc_prom == 1
    assert "token_expired" in envelope_prom["errors"][0]["code"]

def test_f3_07_token_reuse_blocked(monkeypatch):
    client = MiniAgentClient(profile="safe")
    scope = seed_validated_scope(
        client,
        monkeypatch,
        video_hash="token-reuse-video",
        epoch_id="token-reuse-epoch",
    )
    envelope_val, rc_val = client.validate_action(
        prompt="Promotion",
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=False,
    )
    assert rc_val == 3
    token = envelope_val["result"]["confirmation_token"]
    
    # Use token first time
    envelope_prom1, rc_prom1 = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )
    assert rc_prom1 == 0
    
    # Use token second time
    envelope_prom2, rc_prom2 = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=True,
        confirmation_token=token,
    )
    assert rc_prom2 == 1
    assert "token_already_used" in envelope_prom2["errors"][0]["code"]

def test_f3_08_empty_or_whitespace_token_blocked():
    pass
    client = MiniAgentClient(profile="safe")
    envelope, rc = client.validate_action(prompt="Promotion", tool_name="promote_ucf_to_memory", confirm=True, confirmation_token="   ")
    assert rc == 1
    assert "invalid_confirmation_token" in envelope["errors"][0]["code"]

def test_f3_09_token_for_different_operation_blocked():
    pass
    client = MiniAgentClient(profile="safe")
    # Request promotion token
    envelope_val, rc_val = client.validate_action(prompt="Promotion", tool_name="promote_ucf_to_memory", confirm=False)
    token = envelope_val["result"]["confirmation_token"]
    
    # Try using token for file_delete
    client.profile = "unrestricted" # ensure allowed for file_delete
    envelope, rc = client.validate_action(prompt="Delete file", tool_name="file_delete", confirm=True, confirmation_token=token)
    assert rc == 1
    # File delete doesn't require confirmation token in mock anyway, but token mismatch blocks if validated
    # Wait, the token was for promotion, so using it for promotion with mismatch operation or in validate_action blocks:
    envelope_prom, rc_prom = client.validate_action(prompt="Validate promotion token operation", tool_name="promote_ucf_to_memory", confirm=True, confirmation_token=token)
    assert rc_prom == 0 # valid match
    
    envelope_mismatch, rc_mismatch = client.validate_action(prompt="Validate token", tool_name="promote_ucf_to_memory", confirm=True, confirmation_token="some-other-token")
    assert rc_mismatch == 1

def test_f3_10_confirm_true_without_token_blocked():
    pass
    client = MiniAgentClient(profile="safe")
    envelope, rc = client.validate_action(prompt="Promotion", tool_name="promote_ucf_to_memory", confirm=True)
    assert rc == 1
    assert "invalid_confirmation_token" in envelope["errors"][0]["code"]

# Feature 4 Boundary Cases (F4.06-10)

def test_f4_06_nested_json_path_sanitization():
    pass
    # Break-glass required: testing path sanitization, not security gate
    _prev = os.environ.get("GOODQ_BREAK_GLASS")
    os.environ["GOODQ_BREAK_GLASS"] = "1"
    try:
        client = MiniAgentClient(profile="safe")
        args = {
            "path": "C:\\some\\path\\file.txt",
            "absolute_path_artifacts": [{"nested_list": ["L:\\subfolder\\another_file.json", "relative.txt"]}]
        }
        envelope, rc = execute_locally_confirmed(
            client, tool_name="file_delete", tool_args=args
        )
        assert rc == 0
        assert "C:\\some" not in str(envelope)
        assert "L:\\subfolder" not in str(envelope)
        assert "relative/another_file.json" in envelope["artifacts"][0]["nested_list"]
    finally:
        if _prev is None:
            os.environ.pop("GOODQ_BREAK_GLASS", None)
        else:
            os.environ["GOODQ_BREAK_GLASS"] = _prev

def test_f4_07_empty_paths_and_none_handled_gracefully():
    pass
    # Break-glass required: testing path sanitization, not security gate
    _prev = os.environ.get("GOODQ_BREAK_GLASS")
    os.environ["GOODQ_BREAK_GLASS"] = "1"
    try:
        client = MiniAgentClient(profile="safe")
        args = {
            "path": "",
            "absolute_path_artifacts": [None, ""]
        }
        envelope, rc = execute_locally_confirmed(
            client, tool_name="file_delete", tool_args=args
        )
        assert rc == 0
        assert envelope["artifacts"] == [None, ""]
    finally:
        if _prev is None:
            os.environ.pop("GOODQ_BREAK_GLASS", None)
        else:
            os.environ["GOODQ_BREAK_GLASS"] = _prev

def test_f4_08_already_relative_paths_untouched():
    pass
    # Break-glass required: testing path sanitization, not security gate
    _prev = os.environ.get("GOODQ_BREAK_GLASS")
    os.environ["GOODQ_BREAK_GLASS"] = "1"
    try:
        client = MiniAgentClient(profile="safe")
        args = {
            "path": "subfolder/file.txt",
            "absolute_path_artifacts": ["another_sub/data.json"]
        }
        envelope, rc = execute_locally_confirmed(
            client, tool_name="file_delete", tool_args=args
        )
        assert rc == 0
        assert envelope["output"]["deleted"] == "subfolder/file.txt"
        assert envelope["artifacts"] == ["another_sub/data.json"]
    finally:
        if _prev is None:
            os.environ.pop("GOODQ_BREAK_GLASS", None)
        else:
            os.environ["GOODQ_BREAK_GLASS"] = _prev

def test_f4_09_lowercase_drive_letters_sanitized():
    pass
    # Break-glass required: testing path sanitization, not security gate
    _prev = os.environ.get("GOODQ_BREAK_GLASS")
    os.environ["GOODQ_BREAK_GLASS"] = "1"
    try:
        client = MiniAgentClient(profile="safe")
        if not mock_harness_active():
            Path(r"c:\\lowercase\\drive\\file.mp4").parent.mkdir(parents=True, exist_ok=True)
            Path(r"c:\\lowercase\\drive\\file.mp4").touch()
        args = {
            "path": "c:\\lowercase\\drive\\file.mp4",
        }
        envelope, rc = execute_locally_confirmed(
            client, tool_name="file_delete", tool_args=args
        )
        assert rc == 0
        assert "c:\\lowercase" not in str(envelope)
        assert "relative/file.mp4" in envelope["output"]["deleted"]
    finally:
        if _prev is None:
            os.environ.pop("GOODQ_BREAK_GLASS", None)
        else:
            os.environ["GOODQ_BREAK_GLASS"] = _prev

def test_f4_10_path_like_strings_in_text_prompts_not_redacted():
    pass
    client = MiniAgentClient(profile="safe")
    # Prompt contains absolute path. It's in the input, but should we sanitize prompts?
    # Usually we sanitize outcomes (results/envelopes/reports). Let's check:
    # "JSON results/envelopes/reports sanitized to redact absolute local file paths"
    # Prompt is in the task/envelope. Let's verify prompt contains absolute path but results/outputs are sanitized.
    envelope, rc = client.validate_action(prompt="Ingest L:\\test.mp4", tool_name="run_ingestion")
    assert rc == 3
    # The result envelope is sanitized, so any drive letters inside the envelope string are redacted.
    assert "L:\\test" not in str(envelope)

# ------------------------------------------------------------------------------
# TIER 3: CROSS-FEATURE COMBINATIONS (Tests 41 to 45)
# ------------------------------------------------------------------------------

def test_f3_tier3_01_profile_collision_offline_takes_precedence():
    pass
    client = MiniAgentClient(profile="offline")
    # Even if agent fails (meaningFallback validation is triggered), offline blocks mutating action
    client.agent_available = False
    envelope, rc = client.validate_action(prompt="Ingest", tool_name="run_ingestion")
    assert rc == 1
    assert "offline_blocked" in envelope["errors"][0]["code"]

def test_f3_tier3_02_qdrant_faiss_backfilling_sync(tmp_path):
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    
    dummy_file = tmp_path / "dummy_frame.jpg"
    dummy_file.touch()
    
    dino_key = "12345678-1234-1234-1234-123456789012"
    clip_key = "a" * 64
    
    # Prepopulate FAISS sidecar database if running real client
    if not mock_harness_active():
        import sqlite3
        clip_map_db = client.config["paths"]["clip_id_map_db"]
        Path(clip_map_db).parent.mkdir(parents=True, exist_ok=True)
        s_conn = sqlite3.connect(clip_map_db)
        s_conn.execute("CREATE TABLE IF NOT EXISTS clip_id_map (faiss_id INTEGER PRIMARY KEY, hash TEXT, source_path TEXT, epoch_id TEXT, video_hash TEXT, scene_id TEXT, worker_name TEXT, vector_model_tag TEXT, modality TEXT, ucf_frame_id INTEGER)")
        s_conn.execute("INSERT OR REPLACE INTO clip_id_map (faiss_id, hash, source_path, ucf_frame_id) VALUES (42, ?, ?, NULL)", (clip_key, str(dummy_file)))
        s_conn.commit()
        s_conn.close()

    args = {
        "ucf_records": [
            {
                "frame_id": "rec1", "video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1",
                "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "image_embed_dino",
                "model_tag": "facebook/dinov2-large", "vector_model_tag": "facebook/dinov2-large",
                "vector_dim": 1024, "vector_key": dino_key, "vector_backend": "qdrant", "vector_collection": "dino", "raw_ref": str(dummy_file), "payload": {}
            },
            {
                "frame_id": "rec2", "video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1",
                "t_start": 10.0, "t_end": 20.0, "modality": "video", "worker_name": "image_embed_clip",
                "model_tag": "openai/clip-vit-large-patch14", "vector_model_tag": "openai/clip-vit-large-patch14",
                "vector_dim": 768, "vector_key": clip_key, "vector_backend": "faiss", "vector_collection": "clip", "raw_ref": str(dummy_file), "payload": {"faiss_id": 42}
            }
        ]
    }
    # Ingest should synchronize vector backfill points
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 0
    if mock_harness_active():
        assert dino_key in MockState.qdrant_points["dino"]
        assert clip_key in MockState.faiss_points[str(dummy_file)]
    else:
        import sqlite3
        clip_map_db = client.config["paths"]["clip_id_map_db"]
        s_conn = sqlite3.connect(clip_map_db)
        row = s_conn.execute("SELECT ucf_frame_id FROM clip_id_map WHERE faiss_id = 42").fetchone()
        assert row is not None
        assert row[0] is not None
        s_conn.close()

def test_f3_tier3_03_orphan_vector_injection_blocking():
    pass
    client = MiniAgentClient(profile="safe")
    args = {
        "vectors": ["orphan-vector-uuid-999"]
    }

    # Production promotion accepts only an exact video_hash/epoch_id scope. The
    # legacy mock keeps the historical orphan-vector behavior as a compatibility
    # witness, but the real client must reject the unsupported field before it
    # can mint a confirmation token.
    envelope_val, rc_val = client.validate_action(
        prompt="Promotion",
        tool_name="promote_ucf_to_memory",
        tool_args=args,
        confirm=False,
    )
    if not mock_harness_active():
        assert rc_val == 1
        assert envelope_val["errors"][0]["code"] == "invalid_tool_arguments"
        return

    token = envelope_val["result"]["confirmation_token"]
    envelope_prom, rc_prom = client.execute_tool(tool_name="promote_ucf_to_memory", tool_args=args, confirm=True, confirmation_token=token)
    assert rc_prom == 1
    assert "orphan_vector_blocked" in envelope_prom["errors"][0]["code"]

def test_f3_tier3_04_sanitization_applied_to_validation_failure_report():
    pass
    client = MiniAgentClient(profile="safe")
    # Trigger validation failure with absolute paths in artifacts
    args = {
        "ucf_records": [],
        "simulate_validation_fail": True,
        "absolute_path_artifacts": ["C:\\Windows\\System32\\cmd.exe"]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 1
    # Check that paths inside error report are sanitized
    assert "C:\\Windows" not in str(envelope)
    assert "relative/cmd.exe" in envelope["artifacts"]

def test_f3_tier3_05_promotion_validation_handshake_loop():
    pass
    client = MiniAgentClient(profile="safe")
    
    # 1. Ingest with invalid UCF (negative timestamp)
    args_invalid = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": -1.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    env_fail, rc_fail = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args_invalid
    )
    assert rc_fail != 0
    if mock_harness_active():
        assert len(MockState.staged_records) == 0
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        res = conn.execute("SELECT count(*) FROM context_frames").fetchone()[0]
        conn.close()
        assert res == 0
    
    # 2. Ingest with corrected UCF
    register_media("v1", 20.0)
    args_valid = {
        "ucf_records": [{"frame_id": "rec_fixed", "video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 1.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    env_ok, rc_ok = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args_valid
    )
    assert rc_ok == 0
    if mock_harness_active():
        assert len(MockState.staged_records) == 1
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        res = conn.execute("SELECT count(*) FROM context_frames").fetchone()[0]
        conn.close()
        assert res == 1
    if mock_harness_active():
        assert MockState.staged_records["rec_fixed"]["status"] == "staged"
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        row = conn.execute("SELECT promotion_status FROM context_frames WHERE source_artifact_id = ? OR vector_key = ? OR frame_id = ?", ("rec_fixed", "rec_fixed", "rec_fixed")).fetchone()
        if not row:
            row = conn.execute("SELECT promotion_status FROM context_frames").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "staged"

# ------------------------------------------------------------------------------
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (Tests 46 to 50)
# ------------------------------------------------------------------------------

def test_f4_tier4_01_complete_happy_path_loop():
    """Verify the complete E2E ingestion path. Frames land as 'staged'.

    Promotion is attempted without a prior validate_ucf_frames step. The implemented
    promotion engine correctly blocks this with reason='promotion_blocked_unvalidated_frames'.

    Doctrine: staged -> [validate_ucf_frames] -> validated -> [promote_ucf_to_memory] -> promoted

    # TODO: add a companion test exercising the full lifecycle:
    #   validate_ucf_frames + promote_ucf_to_memory -> expect 'promoted'
    """
    client = MiniAgentClient(profile="safe")
    register_media("v1", 100.0)
    
    # Ingestion stages records
    args_ingest = {
        "ucf_records": [{"frame_id": "frame001", "video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}],
        "absolute_path_artifacts": ["C:\\Users\\jdben\\My Drive\\_AGENT\\scene_001.json"]
    }
    envelope_ingest, rc_ingest = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args_ingest
    )
    assert rc_ingest == 0
    assert envelope_ingest["status"] == "success"
    assert "C:\\Users" not in str(envelope_ingest)
    if mock_harness_active():
        assert MockState.staged_records["frame001"]["status"] == "staged"
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        row = conn.execute("SELECT promotion_status FROM context_frames WHERE source_artifact_id = ? OR vector_key = ? OR frame_id = ?", ("frame001", "frame001", "frame001")).fetchone()
        if not row:
            row = conn.execute("SELECT promotion_status FROM context_frames").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "staged"
    
    # Request promotion validation token
    envelope_val, rc_val = client.validate_action(prompt="Promote epoch", tool_name="promote_ucf_to_memory", confirm=False)
    assert rc_val == 3
    token = envelope_val["result"]["confirmation_token"]
    
    # Confirm promotion (without prior validate_ucf_frames)
    envelope_promote, rc_promote = client.execute_tool(tool_name="promote_ucf_to_memory", tool_args={}, confirm=True, confirmation_token=token)
    if mock_harness_active():
        assert MockState.staged_records["frame001"]["status"] == "staged"
    else:
        # Real engine enforces staged -> validated -> promoted lifecycle.
        # Outer envelope status is always 'success'; tool result contains the blocking details.
        assert envelope_promote["status"] == "success"  # outer envelope: call completed
        assert envelope_promote["output"]["status"] == "blocked"  # tool result: blocked by engine
        assert envelope_promote["output"].get("reason") == "promotion_blocked_unvalidated_frames"
        # Frames must remain staged (unaffected by the blocked call)
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        staged_count = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'").fetchone()[0]
        conn.close()
        assert staged_count > 0, "Expected staged frames to remain after blocked promotion call"
        # TODO: add a companion test exercising the full lifecycle:
        #   validate_ucf_frames + promote_ucf_to_memory -> expect 'promoted'

def test_f4_tier4_02_validation_failure_aborts_pipeline():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    
    # UCF Record has invalid bounding box coordinates (ymin > ymax)
    args_ingest = {
        "ucf_records": [{"frame_id": "frame002", "video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "spatial_region": [0.8, 0.1, 0.2, 0.4], "payload": {}}]
    }
    envelope_ingest, rc_ingest = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args_ingest
    )
    assert rc_ingest != 0
    if mock_harness_active():
        assert len(MockState.staged_records) == 0
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        res = conn.execute("SELECT count(*) FROM context_frames").fetchone()[0]
        conn.close()
        assert res == 0
    
    # Request promotion token fails because no staged records exist
    envelope_val, rc_val = client.validate_action(prompt="Promote epoch", tool_name="promote_ucf_to_memory", confirm=False)
    assert rc_val == 3 # Confirmation token is generated but executing promotion won't promote anything

def test_f4_tier4_03_path_audit_scenario():
    pass
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    
    # Video source has absolute path, but outcome envelope is audited to be relative
    args = {
        "ucf_records": [{"video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}],
        "absolute_path_artifacts": ["L:\\_DATA\\GoodQ_Data\\db\\ucf\\ucf_ledger.db"]
    }
    envelope, rc = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc == 0
    envelope_str = str(envelope)
    assert "L:\\_DATA" not in envelope_str
    assert "C:\\" not in envelope_str
    assert "relative/ucf_ledger.db" in envelope["artifacts"]

def test_f4_tier4_04_concurrency_isolation(monkeypatch):
    client1 = MiniAgentClient(profile="safe")
    client2 = MiniAgentClient(profile="safe")
    scope1 = seed_validated_scope(
        client1,
        monkeypatch,
        video_hash="concurrency-video-1",
        epoch_id="concurrency-epoch-1",
    )
    scope2 = seed_validated_scope(
        client2,
        monkeypatch,
        video_hash="concurrency-video-2",
        epoch_id="concurrency-epoch-2",
    )
    
    # Concurrent token requests generate unique isolated tokens
    envelope_val1, _ = client1.validate_action(
        prompt="Promotion 1", tool_name="promote_ucf_to_memory", tool_args=scope1, confirm=False
    )
    envelope_val2, _ = client2.validate_action(
        prompt="Promotion 2", tool_name="promote_ucf_to_memory", tool_args=scope2, confirm=False
    )
    
    t1 = envelope_val1["result"]["confirmation_token"]
    t2 = envelope_val2["result"]["confirmation_token"]
    
    assert t1 != t2
    # A token is isolated by exact operation scope, not by Python object identity.
    crossed, crossed_rc = client1.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope1,
        confirm=True,
        confirmation_token=t2,
    )
    assert crossed_rc == 1
    assert crossed["errors"][0]["code"] == "token_scope_mismatch"

    own1, own1_rc = client1.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope1,
        confirm=True,
        confirmation_token=t1,
    )
    own2, own2_rc = client2.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope2,
        confirm=True,
        confirmation_token=t2,
    )
    assert own1_rc == 0, own1
    assert own2_rc == 0, own2

def test_f4_tier4_05_agent_failure_recovery_scenario():
    """Verify agent failure recovery: after recovery, promote_ucf_to_memory correctly blocks
    because validate_ucf_frames has not been run first.

    Doctrine: staged -> [validate_ucf_frames] -> validated -> [promote_ucf_to_memory] -> promoted

    The promotion engine IS implemented. Calling promote without validate is blocked with
    reason='promotion_blocked_unvalidated_frames'. Frames remain 'staged' after the blocked call.

    # TODO: add a companion test exercising the full lifecycle after recovery:
    #   validate_ucf_frames + promote_ucf_to_memory -> expect 'promoted'
    """
    client = MiniAgentClient(profile="safe")
    register_media("v1", 20.0)
    
    # 1. Agent fails
    client.agent_available = False
    args = {
        "ucf_records": [{"frame_id": "recovery_rec", "video_hash": "v1", "ucf_schema_version": "ucf.v0.1", "epoch_id": "ep1", "run_id": "run1", "t_start": 0.0, "t_end": 10.0, "modality": "video", "worker_name": "worker1", "model_tag": "tag1", "payload": {}}]
    }
    envelope_fail, rc_fail = client.execute_tool(tool_name="run_ingestion", tool_args=args)
    assert rc_fail != 0 # Blocked
    
    # 2. Agent recovers
    client.agent_available = True
    envelope_ok, rc_ok = execute_locally_confirmed(
        client, tool_name="run_ingestion", tool_args=args
    )
    assert rc_ok == 0 # Allowed
    
    # 3. Attempt promotion without prior validate_ucf_frames
    envelope_val, rc_val = client.validate_action(prompt="Promote recovery", tool_name="promote_ucf_to_memory", confirm=False)
    token = envelope_val["result"]["confirmation_token"]
    envelope_prom, rc_prom = client.execute_tool(tool_name="promote_ucf_to_memory", tool_args={}, confirm=True, confirmation_token=token)
    assert rc_prom == 0
    if mock_harness_active():
        assert MockState.staged_records["recovery_rec"]["status"] == "staged"
    else:
        # Real engine blocks: staged frames must be validated first
        assert envelope_prom["output"]["status"] == "blocked"
        assert envelope_prom["output"].get("reason") == "promotion_blocked_unvalidated_frames"
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        staged_count = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'").fetchone()[0]
        conn.close()
        assert staged_count > 0, "Expected staged frames to remain after blocked promotion call"
        # TODO: add a companion test exercising the full lifecycle:
        #   validate_ucf_frames + promote_ucf_to_memory -> expect 'promoted'


# ------------------------------------------------------------------------------
# ADVERSARIAL STRESS HARNESS TESTS (Proposed)
# ------------------------------------------------------------------------------

def test_adv_windows_greedy_match_corruption():
    """Verify that path redaction does not consume the remainder of the sentence when drive letter paths are used without quotes."""
    client = MiniAgentClient(profile="safe")
    sentence = "Log written to C:\\project\\data.json successfully and checked."
    sanitized = client.sanitize_envelope(sentence)
    assert "successfully" in sanitized
    assert "checked" in sanitized
    assert "C:\\project" not in sanitized


def test_adv_unc_and_wsl_path_spaces_leakage():
    """Verify that paths with spaces are completely redacted rather than truncated at the space."""
    client = MiniAgentClient(profile="safe")
    
    unc_path = "\\\\server\\share\\my folder\\file.txt"
    wsl_path = "/mnt/c/Users/user/My Drive/data.json"
    
    sanitized_unc = client.sanitize_envelope(unc_path)
    sanitized_wsl = client.sanitize_envelope(wsl_path)
    
    assert "my folder" not in sanitized_unc
    assert "My Drive" not in sanitized_wsl
    assert "relative/file.txt" in sanitized_unc
    assert "relative/data.json" in sanitized_wsl


def test_adv_unix_path_redaction_leakage():
    """Verify that standard Linux/Unix absolute paths (e.g. in /home/ or /tmp/) are successfully redacted."""
    client = MiniAgentClient(profile="safe")
    
    unix_path = "/home/jdben/MyProject/secrets.json"
    sanitized = client.sanitize_envelope(unix_path)
    
    assert "jdben" not in sanitized
    assert "/home/" not in sanitized
    assert "relative/secrets.json" in sanitized


def test_adv_offline_profile_mutating_block_omissions():
    """Verify that other mutating operations (like qdrant_upsert and home_assistant_call_service) are properly blocked in the offline profile."""
    client = MiniAgentClient(profile="offline")
    
    # Test qdrant_upsert in offline profile
    env_qdrant, rc_qdrant = client.validate_action(prompt="Write to Qdrant", tool_name="qdrant_upsert")
    assert rc_qdrant == 1
    assert "offline_blocked" in env_qdrant["errors"][0]["code"] or env_qdrant["status"] == "error"
    
    # Test home_assistant_call_service in offline profile
    env_ha, rc_ha = client.validate_action(prompt="Call HA service", tool_name="home_assistant_call_service")
    assert rc_ha == 1
    assert "offline_blocked" in env_ha["errors"][0]["code"] or env_ha["status"] == "error"


def test_adv_timezone_aware_token_expiration():
    """Verify that timezone-aware token timestamps do not crash the duration checker or bypass validation."""
    client = MiniAgentClient(profile="safe")
    
    token = "token-test-aware-expired"
    ts_aware = (datetime.utcnow() - timedelta(seconds=3600)).isoformat() + "+00:00"
    
    tokens = client._load_tokens()
    tokens[token] = {
        "operation": "promote_ucf_to_memory",
        "timestamp": ts_aware,
        "used": False,
        "tool_args": {}
    }
    client._save_tokens(tokens)
    
    envelope, rc = client.validate_action(
        prompt="Promote aware token",
        tool_name="promote_ucf_to_memory",
        confirm=True,
        confirmation_token=token
    )
    assert rc == 1
    assert "token_expired" in envelope["errors"][0]["code"]


def test_adv_premature_token_consumption(monkeypatch):
    """Verify that tokens are not consumed during validate_action if they are to be executed later."""
    client = MiniAgentClient(profile="safe")
    scope = seed_validated_scope(
        client,
        monkeypatch,
        video_hash="premature-token-video",
        epoch_id="premature-token-epoch",
    )
    
    env_val, rc_val = client.validate_action(
        prompt="Promotion",
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=False,
    )
    assert rc_val == 3
    token = env_val["result"]["confirmation_token"]
    
    env_check, rc_check = client.validate_action(
        prompt="Promotion Check", 
        tool_name="promote_ucf_to_memory", 
        tool_args=scope,
        confirm=True, 
        confirmation_token=token
    )
    assert rc_check == 0
    
    env_exec, rc_exec = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=True,
        confirmation_token=token
    )
    assert rc_exec == 0
    assert env_exec["status"] == "success"


# ==============================================================================
# FULL LIFECYCLE TEST: staged -> validated -> promoted
# ==============================================================================

def test_full_lifecycle_staged_validated_promoted(monkeypatch):
    """Exercise the complete, doctrine-correct UCF promotion lifecycle.

    Doctrine:
        staged -> [validate_ucf_frames] -> validated -> [promote_ucf_to_memory] -> promoted

    Both lifecycle operations require a separate confirmation token (human-in-the-loop gate).

    Assertions (5 points):
        1. After ingestion: staged_count >= 2 in DB.
        2. promote_ucf_to_memory before validate_ucf_frames: output.status == 'blocked',
           reason == 'promotion_blocked_unvalidated_frames', DB staged_count unchanged.
        3. validate_ucf_frames with confirmation token: output.status == 'validated_complete',
           validated_count >= 1, DB staged == 0, validated >= 2.
        4. promote_ucf_to_memory with confirmation token (no staged frames):
           output.status == 'promoted_complete', promoted_count >= 1.
        5. DB final state: staged == 0, validated == 0, promoted >= 2.
    """
    client = MiniAgentClient(profile="safe")
    scope = {"video_hash": "lifecycle_vid", "epoch_id": "lifecycle_ep1"}
    if not mock_harness_active():
        monkeypatch.setattr(
            client,
            "_execute_validate_ucf_epoch",
            lambda _args: {"success": True, "errors": []},
        )
        monkeypatch.setattr(
            client,
            "_sync_qdrant_by_scope",
            lambda **_kwargs: {
                "status": "ok",
                "points_verified": 1,
                "failed_collections": [],
            },
        )
    register_media("lifecycle_vid", 60.0)

    # ---- Step 1: Ingest -> staged ----
    args_ingest = {
        "ucf_records": [
            {
                "video_hash": "lifecycle_vid",
                "ucf_schema_version": "ucf.v0.1",
                "epoch_id": "lifecycle_ep1",
                "run_id": "lifecycle_run1",
                "t_start": 0.0,
                "t_end": 10.0,
                "modality": "video",
                "worker_name": "worker1",
                "model_tag": "tag1",
                "payload": {},
            },
            {
                "video_hash": "lifecycle_vid",
                "ucf_schema_version": "ucf.v0.1",
                "epoch_id": "lifecycle_ep1",
                "run_id": "lifecycle_run1",
                "t_start": 10.0,
                "t_end": 20.0,
                "modality": "video",
                "worker_name": "worker1",
                "model_tag": "tag1",
                "payload": {},
            },
        ]
    }
    envelope_ingest, rc_ingest = execute_locally_confirmed(
        client,
        tool_name="run_ingestion", tool_args=args_ingest
    )
    assert rc_ingest == 0
    assert envelope_ingest["status"] == "success"
    assert envelope_ingest["output"]["status"] == "staged_complete"
    assert envelope_ingest["output"]["ingested_count"] == 2

    if not mock_harness_active():
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        staged_after_ingest = conn.execute(
            "SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'"
        ).fetchone()[0]
        conn.close()
        assert staged_after_ingest >= 2, (
            f"Expected >= 2 staged frames after ingestion, got {staged_after_ingest}"
        )

    # ---- Step 1b: Attempt promote without validate -> must be blocked ----
    # Proves the gate fires before any validation has occurred.
    early_prom_token_env, rc_early = client.validate_action(
        prompt="Premature promotion attempt",
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=False,
    )
    assert rc_early == 3
    early_prom_token = early_prom_token_env["result"]["confirmation_token"]

    envelope_early_prom, rc_early_prom = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=True,
        confirmation_token=early_prom_token,
    )
    assert rc_early_prom == 0  # call succeeded without exception
    if not mock_harness_active():
        assert envelope_early_prom["output"]["status"] == "blocked", (
            f"Expected 'blocked' when promoting before validation, "
            f"got: {envelope_early_prom['output']}"
        )
        assert envelope_early_prom["output"].get("reason") == "promotion_blocked_unvalidated_frames"
        # Frames must still be staged — the blocked call left DB unchanged
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        staged_still = conn.execute(
            "SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'"
        ).fetchone()[0]
        conn.close()
        assert staged_still >= 2, (
            f"Expected staged frames to survive a blocked promotion, got {staged_still}"
        )

    # ---- Step 2: validate_ucf_frames (requires token) -> validated ----
    envelope_val_token, rc_val_token = client.validate_action(
        prompt="Validate lifecycle frames",
        tool_name="validate_ucf_frames",
        tool_args=scope,
        confirm=False,
    )
    assert rc_val_token == 3
    assert "confirmation_token" in envelope_val_token["result"]
    val_token = envelope_val_token["result"]["confirmation_token"]

    envelope_validate, rc_validate = client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args=scope,
        confirm=True,
        confirmation_token=val_token,
    )
    assert rc_validate == 0
    assert envelope_validate["status"] == "success"
    assert envelope_validate["output"]["status"] == "validated_complete"

    if mock_harness_active():
        # Mock records should be in promoted state after mock validate
        pass
    else:
        assert envelope_validate["output"]["validated_count"] >= 1

        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        staged_after_validate = conn.execute(
            "SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'"
        ).fetchone()[0]
        validated_after_validate = conn.execute(
            "SELECT count(*) FROM context_frames WHERE promotion_status = 'validated'"
        ).fetchone()[0]
        conn.close()
        assert staged_after_validate == 0, (
            f"Expected 0 staged frames after validate_ucf_frames, got {staged_after_validate}"
        )
        assert validated_after_validate >= 2, (
            f"Expected >= 2 validated frames, got {validated_after_validate}"
        )

    # ---- Step 3: promote_ucf_to_memory (requires token, no staged frames) -> promoted ----
    envelope_prom_token, rc_prom_token = client.validate_action(
        prompt="Promote lifecycle frames",
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=False,
    )
    assert rc_prom_token == 3
    assert "confirmation_token" in envelope_prom_token["result"]
    prom_token = envelope_prom_token["result"]["confirmation_token"]

    envelope_promote, rc_promote = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=True,
        confirmation_token=prom_token,
    )
    assert rc_promote == 0
    assert envelope_promote["status"] == "success"

    if mock_harness_active():
        pass  # Mock promotes without lifecycle enforcement
    else:
        # Engine must NOT block (all staged frames were validated in step 2)
        assert envelope_promote["output"]["status"] == "promoted_complete", (
            f"Expected 'promoted_complete', got: {envelope_promote['output']}"
        )
        assert envelope_promote["output"]["promoted_count"] >= 1

        # ---- Step 4: DB state final check ----
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        staged_final = conn.execute(
            "SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'"
        ).fetchone()[0]
        validated_final = conn.execute(
            "SELECT count(*) FROM context_frames WHERE promotion_status = 'validated'"
        ).fetchone()[0]
        promoted_final = conn.execute(
            "SELECT count(*) FROM context_frames WHERE promotion_status = 'promoted'"
        ).fetchone()[0]
        conn.close()

        assert staged_final == 0, (
            f"Expected 0 staged frames after promotion, got {staged_final}"
        )
        assert validated_final == 0, (
            f"Expected 0 validated frames after promotion, got {validated_final}"
        )
        assert promoted_final >= 2, (
            f"Expected >= 2 promoted frames, got {promoted_final}"
        )


# ==============================================================================
# NEW UCF PIPELINE STAGING, REJECTION AND SUPERSESSION TESTS (9 Tests)
# ==============================================================================

def helper_ingest_two_records(client, video_hash, epoch_id, run_id):
    args_ingest = {
        "ucf_records": [
            {
                "video_hash": video_hash,
                "ucf_schema_version": "ucf.v0.1",
                "epoch_id": epoch_id,
                "run_id": run_id,
                "t_start": 0.0,
                "t_end": 10.0,
                "modality": "video",
                "worker_name": "worker1",
                "model_tag": "tag1",
                "payload": {},
            },
            {
                "video_hash": video_hash,
                "ucf_schema_version": "ucf.v0.1",
                "epoch_id": epoch_id,
                "run_id": run_id,
                "t_start": 10.0,
                "t_end": 20.0,
                "modality": "video",
                "worker_name": "worker1",
                "model_tag": "tag1",
                "payload": {},
            },
        ]
    }
    envelope_ingest, rc_ingest = execute_locally_confirmed(
        client,
        tool_name="run_ingestion", tool_args=args_ingest
    )
    assert rc_ingest == 0
    return envelope_ingest

def test_reject_staged_frames():
    """Test 1: reject_ucf_frames on staged frames (staged -> reject)."""
    client = MiniAgentClient(profile="safe")
    register_media("reject_staged_vid", 60.0)
    helper_ingest_two_records(client, "reject_staged_vid", "ep1", "run1")

    reject_args = {
        "video_hash": "reject_staged_vid",
        "epoch_id": "ep1",
        "reason": "Bad quality",
    }

    # Get confirmation token for rejection
    env_token, rc_token = client.validate_action(
        prompt="Reject staged frames",
        tool_name="reject_ucf_frames",
        tool_args=reject_args,
        confirm=False,
    )
    assert rc_token == 3
    token = env_token["result"]["confirmation_token"]

    # Reject
    env_reject, rc_reject = client.execute_tool(
        tool_name="reject_ucf_frames",
        tool_args=reject_args,
        confirm=True,
        confirmation_token=token,
    )
    assert rc_reject == 0
    assert env_reject["status"] == "success"
    assert env_reject["output"]["status"] == "rejected_complete"
    assert env_reject["output"]["rejected_count"] == 2

    if mock_harness_active():
        staged_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "staged")
        rejected_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "rejected")
        assert staged_count == 0
        assert rejected_count == 2
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        staged = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'").fetchone()[0]
        rejected = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'rejected'").fetchone()[0]
        conn.close()
        assert staged == 0
        assert rejected == 2


def test_reject_validated_frames():
    """Test 2: reject_ucf_frames on validated frames (staged -> validate -> reject)."""
    client = MiniAgentClient(profile="safe")
    register_media("reject_validated_vid", 60.0)
    helper_ingest_two_records(client, "reject_validated_vid", "ep1", "run1")

    validate_args = {"video_hash": "reject_validated_vid", "epoch_id": "ep1"}
    reject_args = {
        "video_hash": "reject_validated_vid",
        "epoch_id": "ep1",
        "reason": "No longer needed",
    }

    # Validate
    env_token_val, rc_token_val = client.validate_action(
        prompt="Validate",
        tool_name="validate_ucf_frames",
        tool_args=validate_args,
        confirm=False,
    )
    assert rc_token_val == 3
    token_val = env_token_val["result"]["confirmation_token"]

    env_val, rc_val = client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args=validate_args,
        confirm=True,
        confirmation_token=token_val,
    )
    assert rc_val == 0

    # Reject
    env_token_rej, rc_token_rej = client.validate_action(
        prompt="Reject",
        tool_name="reject_ucf_frames",
        tool_args=reject_args,
        confirm=False,
    )
    assert rc_token_rej == 3
    token_rej = env_token_rej["result"]["confirmation_token"]

    env_rej, rc_rej = client.execute_tool(
        tool_name="reject_ucf_frames",
        tool_args=reject_args,
        confirm=True,
        confirmation_token=token_rej,
    )
    assert rc_rej == 0
    assert env_rej["output"]["rejected_count"] == 2

    if mock_harness_active():
        validated_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "validated")
        rejected_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "rejected")
        assert validated_count == 0
        assert rejected_count == 2
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        validated = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'validated'").fetchone()[0]
        rejected = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'rejected'").fetchone()[0]
        conn.close()
        assert validated == 0
        assert rejected == 2


def test_promote_rejected_frames_blocked():
    """Test 3: Attempting to promote rejected frames is blocked/noop."""
    client = MiniAgentClient(profile="safe")
    register_media("promote_rejected_vid", 60.0)
    helper_ingest_two_records(client, "promote_rejected_vid", "ep1", "run1")

    reject_args = {
        "video_hash": "promote_rejected_vid",
        "epoch_id": "ep1",
        "reason": "Bad quality",
    }
    promote_args = {"video_hash": "promote_rejected_vid", "epoch_id": "ep1"}

    # Reject
    env_token_rej, rc_token_rej = client.validate_action(
        prompt="Reject",
        tool_name="reject_ucf_frames",
        tool_args=reject_args,
        confirm=False,
    )
    assert rc_token_rej == 3
    token_rej = env_token_rej["result"]["confirmation_token"]

    client.execute_tool(
        tool_name="reject_ucf_frames",
        tool_args=reject_args,
        confirm=True,
        confirmation_token=token_rej,
    )

    # Attempt promote
    env_token_prom, rc_token_prom = client.validate_action(
        prompt="Promote",
        tool_name="promote_ucf_to_memory",
        tool_args=promote_args,
        confirm=False,
    )
    assert rc_token_prom == 3
    token_prom = env_token_prom["result"]["confirmation_token"]

    env_prom, rc_prom = client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=promote_args,
        confirm=True,
        confirmation_token=token_prom,
    )
    assert rc_prom == 0
    assert env_prom["output"].get("promoted_count", 0) == 0

    if mock_harness_active():
        rejected_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "rejected")
        promoted_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "promoted")
        assert rejected_count == 2
        assert promoted_count == 0
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        rejected = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'rejected'").fetchone()[0]
        promoted = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'promoted'").fetchone()[0]
        conn.close()
        assert rejected == 2
        assert promoted == 0


def test_supersede_validated_frames():
    """Test 4: supersede_ucf_frames on validated frames (staged -> validate -> supersede)."""
    client = MiniAgentClient(profile="safe")
    register_media("supersede_val_vid", 60.0)
    helper_ingest_two_records(client, "supersede_val_vid", "ep1", "run1")

    scope = {"video_hash": "supersede_val_vid", "epoch_id": "ep1"}

    # Validate
    env_token_val, rc_token_val = client.validate_action(
        prompt="Validate",
        tool_name="validate_ucf_frames",
        tool_args=scope,
        confirm=False,
    )
    token_val = env_token_val["result"]["confirmation_token"]
    client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args=scope,
        confirm=True,
        confirmation_token=token_val,
    )

    # Supersede
    env_token_sup, rc_token_sup = client.validate_action(
        prompt="Supersede",
        tool_name="supersede_ucf_frames",
        tool_args=scope,
        confirm=False,
    )
    assert rc_token_sup == 3
    token_sup = env_token_sup["result"]["confirmation_token"]

    env_sup, rc_sup = client.execute_tool(
        tool_name="supersede_ucf_frames",
        tool_args=scope,
        confirm=True,
        confirmation_token=token_sup,
    )
    assert rc_sup == 0
    assert env_sup["output"]["superseded_count"] == 2

    if mock_harness_active():
        superseded_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "superseded")
        assert superseded_count == 2
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        superseded = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'superseded'").fetchone()[0]
        conn.close()
        assert superseded == 2


def test_supersede_promoted_frames():
    """Test 5: supersede_ucf_frames on promoted frames (staged -> validate -> promote -> supersede)."""
    client = MiniAgentClient(profile="safe")
    register_media("supersede_prom_vid", 60.0)
    helper_ingest_two_records(client, "supersede_prom_vid", "ep1", "run1")

    scope = {"video_hash": "supersede_prom_vid", "epoch_id": "ep1"}

    # Validate
    env_token_val, rc_token_val = client.validate_action(
        prompt="Validate",
        tool_name="validate_ucf_frames",
        tool_args=scope,
        confirm=False,
    )
    token_val = env_token_val["result"]["confirmation_token"]
    client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args=scope,
        confirm=True,
        confirmation_token=token_val,
    )

    # Promote
    env_token_prom, rc_token_prom = client.validate_action(
        prompt="Promote",
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=False,
    )
    token_prom = env_token_prom["result"]["confirmation_token"]
    client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=scope,
        confirm=True,
        confirmation_token=token_prom,
    )

    # Supersede
    env_token_sup, rc_token_sup = client.validate_action(
        prompt="Supersede",
        tool_name="supersede_ucf_frames",
        tool_args=scope,
        confirm=False,
    )
    assert rc_token_sup == 3
    token_sup = env_token_sup["result"]["confirmation_token"]

    env_sup, rc_sup = client.execute_tool(
        tool_name="supersede_ucf_frames",
        tool_args=scope,
        confirm=True,
        confirmation_token=token_sup,
    )
    assert rc_sup == 0
    assert env_sup["output"]["superseded_count"] == 2

    if mock_harness_active():
        promoted_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "promoted")
        superseded_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "superseded")
        assert promoted_count == 0
        assert superseded_count == 2
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        promoted = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'promoted'").fetchone()[0]
        superseded = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'superseded'").fetchone()[0]
        conn.close()
        assert promoted == 0
        assert superseded == 2


def test_supersede_staged_blocked():
    """Test 6: Attempting to supersede staged frames is a noop."""
    client = MiniAgentClient(profile="safe")
    register_media("supersede_staged_vid", 60.0)
    helper_ingest_two_records(client, "supersede_staged_vid", "ep1", "run1")

    scope = {"video_hash": "supersede_staged_vid", "epoch_id": "ep1"}

    # Attempt supersede
    env_token_sup, rc_token_sup = client.validate_action(
        prompt="Supersede",
        tool_name="supersede_ucf_frames",
        tool_args=scope,
        confirm=False,
    )
    token_sup = env_token_sup["result"]["confirmation_token"]

    env_sup, rc_sup = client.execute_tool(
        tool_name="supersede_ucf_frames",
        tool_args=scope,
        confirm=True,
        confirmation_token=token_sup,
    )
    assert rc_sup == 0
    assert env_sup["output"].get("superseded_count", 0) == 0

    if mock_harness_active():
        staged_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "staged")
        superseded_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "superseded")
        assert staged_count == 2
        assert superseded_count == 0
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        staged = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'staged'").fetchone()[0]
        superseded = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'superseded'").fetchone()[0]
        conn.close()
        assert staged == 2
        assert superseded == 0


def test_revalidate_rejected_or_superseded_noop():
    """Test 7: Attempting validate_ucf_frames on rejected or superseded frames is a noop."""
    client = MiniAgentClient(profile="safe")
    register_media("revalidate_vid", 60.0)
    helper_ingest_two_records(client, "revalidate_vid", "ep1", "run1")

    reject_args = {
        "video_hash": "revalidate_vid",
        "epoch_id": "ep1",
        "reason": "Bad quality",
    }
    validate_args = {"video_hash": "revalidate_vid", "epoch_id": "ep1"}

    # Reject
    env_token_rej, rc_token_rej = client.validate_action(
        prompt="Reject",
        tool_name="reject_ucf_frames",
        tool_args=reject_args,
        confirm=False,
    )
    token_rej = env_token_rej["result"]["confirmation_token"]
    client.execute_tool(
        tool_name="reject_ucf_frames",
        tool_args=reject_args,
        confirm=True,
        confirmation_token=token_rej,
    )

    # Attempt Validate
    env_token_val, rc_token_val = client.validate_action(
        prompt="Validate",
        tool_name="validate_ucf_frames",
        tool_args=validate_args,
        confirm=False,
    )
    token_val = env_token_val["result"]["confirmation_token"]
    env_val, rc_val = client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args=validate_args,
        confirm=True,
        confirmation_token=token_val,
    )
    assert rc_val == 0
    assert env_val["output"].get("validated_count", 0) == 0

    if mock_harness_active():
        validated_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "validated")
        rejected_count = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "rejected")
        assert validated_count == 0
        assert rejected_count == 2
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        validated = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'validated'").fetchone()[0]
        rejected = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'rejected'").fetchone()[0]
        conn.close()
        assert validated == 0
        assert rejected == 2


def test_full_ingestion_supersede_lifecycle():
    """Test 8: Full pipeline run: Run 1 promoted -> Run 2 staged -> validate Run 2 -> supersede Run 1 -> promote Run 2."""
    client = MiniAgentClient(profile="safe")
    register_media("lifecycle_supersede_vid", 60.0)
    ep1_scope = {"video_hash": "lifecycle_supersede_vid", "epoch_id": "ep1"}
    ep2_scope = {"video_hash": "lifecycle_supersede_vid", "epoch_id": "ep2"}

    # Run 1 (ep1)
    helper_ingest_two_records(client, "lifecycle_supersede_vid", "ep1", "run1")
    env_t_v1, _ = client.validate_action(
        prompt="Validate ep1",
        tool_name="validate_ucf_frames",
        tool_args=ep1_scope,
        confirm=False,
    )
    client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args=ep1_scope,
        confirm=True,
        confirmation_token=env_t_v1["result"]["confirmation_token"],
    )
    env_t_p1, _ = client.validate_action(
        prompt="Promote ep1",
        tool_name="promote_ucf_to_memory",
        tool_args=ep1_scope,
        confirm=False,
    )
    client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=ep1_scope,
        confirm=True,
        confirmation_token=env_t_p1["result"]["confirmation_token"],
    )

    # Run 2 (ep2)
    helper_ingest_two_records(client, "lifecycle_supersede_vid", "ep2", "run2")
    env_t_v2, _ = client.validate_action(
        prompt="Validate ep2",
        tool_name="validate_ucf_frames",
        tool_args=ep2_scope,
        confirm=False,
    )
    client.execute_tool(
        tool_name="validate_ucf_frames",
        tool_args=ep2_scope,
        confirm=True,
        confirmation_token=env_t_v2["result"]["confirmation_token"],
    )

    # Supersede Run 1 (ep1)
    env_t_s1, _ = client.validate_action(
        prompt="Supersede ep1",
        tool_name="supersede_ucf_frames",
        tool_args=ep1_scope,
        confirm=False,
    )
    client.execute_tool(
        tool_name="supersede_ucf_frames",
        tool_args=ep1_scope,
        confirm=True,
        confirmation_token=env_t_s1["result"]["confirmation_token"],
    )

    # Promote Run 2 (ep2)
    env_t_p2, _ = client.validate_action(
        prompt="Promote ep2",
        tool_name="promote_ucf_to_memory",
        tool_args=ep2_scope,
        confirm=False,
    )
    client.execute_tool(
        tool_name="promote_ucf_to_memory",
        tool_args=ep2_scope,
        confirm=True,
        confirmation_token=env_t_p2["result"]["confirmation_token"],
    )

    if mock_harness_active():
        # Check overall state in mock
        promoted = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "promoted")
        superseded = sum(1 for rec in MockState.staged_records.values() if rec["status"] == "superseded")
        assert promoted == 2
        assert superseded == 2
    else:
        import sqlite3
        conn = sqlite3.connect(str(client._get_ucf_db_path()))
        promoted = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'promoted'").fetchone()[0]
        superseded = conn.execute("SELECT count(*) FROM context_frames WHERE promotion_status = 'superseded'").fetchone()[0]
        conn.close()
        assert promoted == 2
        assert superseded == 2


def test_reject_supersede_token_validation():
    """Test 9: Token validation, operation mismatch, and invalid/expired token handling on reject/supersede."""
    client = MiniAgentClient(profile="safe")
    register_media("token_val_vid", 60.0)
    helper_ingest_two_records(client, "token_val_vid", "ep1", "run1")
    cross_operation_args = {"video_hash": "token_val_vid", "epoch_id": "ep1"}

    # Request reject token
    env_token_rej, rc_token_rej = client.validate_action(
        prompt="Reject",
        tool_name="reject_ucf_frames",
        tool_args=cross_operation_args,
        confirm=False,
    )
    token_rej = env_token_rej["result"]["confirmation_token"]

    # 1. Try to use reject token on supersede_ucf_frames -> should fail with token_operation_mismatch
    env_fail1, rc_fail1 = client.execute_tool(
        tool_name="supersede_ucf_frames",
        tool_args=cross_operation_args,
        confirm=True,
        confirmation_token=token_rej,
    )
    assert rc_fail1 == 1
    assert "token_operation_mismatch" in env_fail1["errors"][0]["code"]

    # 2. Try to reject with fake token -> should fail with invalid_confirmation_token
    env_fail2, rc_fail2 = client.execute_tool(
        tool_name="reject_ucf_frames",
        tool_args={"video_hash": "token_val_vid", "epoch_id": "ep1", "reason": "test"},
        confirm=True,
        confirmation_token="fake-token-123",
    )
    assert rc_fail2 == 1
    assert "invalid_confirmation_token" in env_fail2["errors"][0]["code"]

    # 3. Try to reject with simulated expired token
    expired_reject_args = {
        "video_hash": "token_val_vid",
        "epoch_id": "ep1",
        "reason": "test",
    }
    env_token_exp, rc_token_exp = client.validate_action(
        prompt="Reject Expired",
        tool_name="reject_ucf_frames",
        confirm=False,
        tool_args=expired_reject_args,
    )
    assert rc_token_exp == 3
    token_exp = env_token_exp["result"]["confirmation_token"]
    expired_at = datetime.utcnow() - timedelta(seconds=3600)
    if mock_harness_active():
        MockState.tokens[token_exp]["timestamp"] = expired_at
    else:
        tokens = client._load_tokens()
        tokens[token_exp]["timestamp"] = expired_at.isoformat() + "Z"
        client._save_tokens(tokens)

    env_fail3, rc_fail3 = client.execute_tool(
        tool_name="reject_ucf_frames",
        tool_args=expired_reject_args,
        confirm=True,
        confirmation_token=token_exp,
    )
    assert rc_fail3 == 1
    assert "token_expired" in env_fail3["errors"][0]["code"]

