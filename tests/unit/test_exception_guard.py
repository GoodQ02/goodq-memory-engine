import os
import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# Files that we strictly guard against silent exception swallowing
GUARDED_FILES = {
    "agents/control_agent.py",
    "agents/mini_agent_client.py",
    "steps/audio_diarize/vad_preprocessor.py",
    "steps/audio_transcribe/step.py",
    "steps/graph_builder/emotion_arc_analyzer.py",
    "steps/graph_builder/llm_enrichment.py",
    "steps/video_summarizer/step.py",
    "steps/tts/step.py",
    "steps/llm_chat/step.py",
    "steps/home_assistant_status/step.py",
}

# Allowlist: (relative_path_substring, try_or_handler_substring, reason)
ALLOWLIST = [
    # Explicit repairs / standard exceptions
    ("agents/mini_agent_client.py", "fd.close()", "Swallowing close exception is intentional when lock fails"),
    ("agents/mini_agent_client.py", "os.remove(temp_path_str)", "Swallowing file removal exception is safe as this is a temporary file cleanup attempt"),
    ("agents/mini_agent_client.py", "report_path", "Validation report load fails can pass through"),
    
    # Legacy/Existing codebase exceptions in guarded files
    ("agents/mini_agent_client.py", "datetime.fromisoformat", "Ignore timestamp parsing error for token expiration check"),
    ("agents/mini_agent_client.py", "SELECT file_path FROM media_sources", "Ignore sqlite query exception when retrieving source path from UCF"),
    ("agents/mini_agent_client.py", "meta.get(\"keyframe\"", "Ignore keyframe or audio metadata parsing failure"),
    ("agents/mini_agent_client.py", "props.get(\"video_path\")", "Ignore JSON parsing failure of video path properties in KG"),
    ("agents/mini_agent_client.py", "video_hash in str(props)", "Ignore parsing failure of properties for node deletion"),
    ("agents/mini_agent_client.py", "SELECT frame_id FROM context_frames", "Ignore sqlite connection/query failure on context frames"),
    ("agents/mini_agent_client.py", "ROLLBACK", "Ignore transaction rollback failure on materialization error"),
    ("steps/audio_transcribe/step.py", "os.remove(output_json_path)", "Ignore output json deletion error in faster-whisper helper"),
    ("steps/audio_transcribe/step.py", "model_ctx_holder[0].__exit__", "Ignore exit context cleanup error"),
    ("steps/audio_transcribe/step.py", "float(seg.get(\"end\"", "Ignore segment float end time parsing error"),
]

def is_silent_body(body):
    """
    Check if the block body contains only silent instructions (pass, return None, Constant).
    """
    if not body:
        return True
    
    # If any statement in the body is not pass/return None/Constant, it's not silent
    for node in body:
        if isinstance(node, ast.Pass):
            continue
        if isinstance(node, ast.Return):
            if node.value is None:
                continue
            if isinstance(node.value, ast.Constant) and node.value.value is None:
                continue
            if isinstance(node.value, ast.Name) and node.value.id == "None":
                continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        # If we reach here, it has some active statement (e.g. logging, raise, function call)
        return False
    return True

def check_file(file_path: Path):
    violations = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines()
        
        tree = ast.parse(content, filename=str(file_path))
    except Exception:
        # If a file fails to parse, it's not a swallowing violation per se
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                is_bare = handler.type is None
                is_silent = is_silent_body(handler.body)
                
                # Check for:
                # - Silent except Exception: pass / return None
                # - Silent except BaseException: pass / return None
                # - Silent except: pass
                # - Bare except:
                
                is_target_exception_type = False
                if is_bare:
                    is_target_exception_type = True
                elif isinstance(handler.type, ast.Name) and handler.type.id in ("Exception", "BaseException"):
                    is_target_exception_type = True
                
                if (is_bare) or (is_target_exception_type and is_silent):
                    rel_path = file_path.relative_to(REPO_ROOT).as_posix()
                    line_no = handler.lineno
                    
                    # Fetch code text of the Try block (from try: to the end of the handler)
                    start_line = max(0, node.lineno - 1)
                    end_line = min(len(lines), handler.end_lineno if handler.end_lineno is not None else handler.lineno + 1)
                    handler_lines = lines[start_line:end_line]
                    handler_text = "\n".join(handler_lines)
                    
                    # Check if the file is guarded. If not, treat as allowed (legacy codebase exception)
                    if rel_path not in GUARDED_FILES:
                        allowed = True
                    else:
                        allowed = False
                        for allowed_path, allowed_pattern, reason in ALLOWLIST:
                            if allowed_path in rel_path:
                                if allowed_pattern is None or any(allowed_pattern in line for line in handler_lines):
                                    allowed = True
                                    break
                    
                    if not allowed:
                        violations.append({
                            "file": rel_path,
                            "line": line_no,
                            "type": "bare" if is_bare else "silent",
                            "code": handler_text,
                        })
    return violations

def test_exception_swallowing_regression_guard():
    target_dirs = ["agents", "steps", "api", "lib", "cli", "pipelines", "scripts", "common"]
    all_violations = []
    
    for dir_name in target_dirs:
        dir_path = REPO_ROOT / dir_name
        if not dir_path.exists():
            continue
        for root, dirs, files in os.walk(dir_path):
            path_parts = Path(root).parts
            # Prune directory search to exclude vendor, archive, site-packages, Lib, go_compiler, staged or hidden paths
            if any(p.startswith(".") for p in path_parts):
                continue
            if any(p in ("vendor", "archive", "site-packages", "Lib", "go_compiler", "staged") for p in path_parts):
                continue
                
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    violations = check_file(file_path)
                    all_violations.extend(violations)
                    
    if all_violations:
        msg = f"Found {len(all_violations)} non-allowlisted exception swallowing violations:\n"
        for v in all_violations:
            msg += f"- {v['file']}:{v['line']} ({v['type']}):\n{v['code']}\n\n"
        assert False, msg
