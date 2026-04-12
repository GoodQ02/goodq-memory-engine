"""
GoodQ4All WSL2 Audio Bridge
Simple interface to WSL2 audio processing
"""

import subprocess
import json
import time
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from scripts.wsl_audio_preflight import probe_wsl_audio_runtime
except Exception:  # noqa: BLE001
    from wsl_audio_preflight import probe_wsl_audio_runtime

_WORKSPACE_PREFLIGHT_TIMEOUTS = (5, 10)
_WORKSPACE_PREFLIGHT_RETRY_DELAY_SEC = 0.25


class WSL2AudioBridge:
    """Bridge to WSL2 audio processing"""
    _workspace_warning_keys: set[str] = set()
    
    def __init__(self):
        self.require_wsl_audio = self._is_truthy(os.environ.get("GOODQ_REQUIRE_WSL_AUDIO", ""))
        self.wsl_user = self._resolve_wsl_user()
        self.workspace = self._resolve_wsl_workspace()
        self.audio_workspace = self.workspace.rstrip("/")
        self.wsl_distro = os.environ.get("GOODQ_WSL_DISTRO", "Ubuntu")
        self._workspace_checked = False
        self._workspace_warned = False
        self._workspace_ready = False

    @staticmethod
    def _is_truthy(value):
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _workspace_warning_key(cls, *, distro: str, workspace: str, warning_kind: str) -> str:
        run_id = os.environ.get("GOODQ_RUN_ID")
        scope = f"run:{run_id}" if run_id else f"pid:{os.getpid()}"
        return f"{scope}|{distro}|{workspace}|{warning_kind}"

    def _warn_workspace_once(self, message: str, *, warning_kind: str) -> None:
        if self._workspace_warned:
            return
        key = self._workspace_warning_key(
            distro=self.wsl_distro,
            workspace=self.audio_workspace,
            warning_kind=warning_kind,
        )
        if key in self._workspace_warning_keys:
            self._workspace_warned = True
            return
        print(f"[WSL2AudioBridge][WARN] {message}")
        self._workspace_warning_keys.add(key)
        self._workspace_warned = True

    def _resolve_wsl_user(self):
        explicit = os.environ.get("GOODQ_WSL_USER")
        if explicit:
            return explicit
        if self.require_wsl_audio:
            raise RuntimeError(
                "GOODQ_REQUIRE_WSL_AUDIO=1 requires GOODQ_WSL_USER to be set explicitly."
            )
        for candidate in (os.environ.get("USER"), os.environ.get("USERNAME"), os.environ.get("LOGNAME")):
            if candidate:
                return candidate
        return "user"

    def _resolve_wsl_workspace(self):
        explicit = os.environ.get("GOODQ_WSL_WORKSPACE")
        if explicit:
            return explicit
        return f"/home/{self.wsl_user}/goodq_audio"

    def _ensure_workspace_ready(self):
        if self._workspace_checked and (self._workspace_ready or not self.require_wsl_audio):
            return self._workspace_ready

        check = None
        last_exception: Optional[Exception] = None
        for attempt_index, timeout_sec in enumerate(_WORKSPACE_PREFLIGHT_TIMEOUTS, start=1):
            try:
                check = subprocess.run(
                    [
                        "wsl",
                        "-d",
                        self.wsl_distro,
                        "--",
                        "bash",
                        "-lc",
                        (
                            f"test -d '{self.audio_workspace}' && "
                            f"test -f '{self.audio_workspace}/setup_cuda_env.sh' && "
                            f"test -f '{self.audio_workspace}/process_audio.py'"
                        ),
                    ],
                    capture_output=True,
                    timeout=timeout_sec,
                )
                self._workspace_ready = check.returncode == 0
                last_exception = None
                break
            except Exception as e:
                last_exception = e
                self._workspace_ready = False
                if attempt_index < len(_WORKSPACE_PREFLIGHT_TIMEOUTS):
                    time.sleep(_WORKSPACE_PREFLIGHT_RETRY_DELAY_SEC)
                    continue

        if last_exception is not None:
            self._workspace_ready = False
            message = (
                f"WSL workspace preflight failed for distro={self.wsl_distro}, "
                f"workspace={self.audio_workspace}: {last_exception}"
            )
            self._workspace_checked = True
            if self.require_wsl_audio:
                raise RuntimeError(message) from last_exception
            self._warn_workspace_once(message, warning_kind="preflight_failed")
            return False

        self._workspace_checked = True
        if not self._workspace_ready:
            message = (
                f"WSL workspace not found for distro={self.wsl_distro}, workspace={self.audio_workspace}. "
                "Set GOODQ_WSL_USER and GOODQ_WSL_WORKSPACE for deterministic host setup."
            )
            if self.require_wsl_audio:
                raise RuntimeError(message)
            self._warn_workspace_once(message, warning_kind="workspace_not_found")
        return self._workspace_ready
        
    def wsl_path(self, windows_path):
        """Convert Windows path to WSL path"""
        p = str(windows_path).replace("\\", "/")
        if len(p) > 1 and p[1] == ":":
            drive = p[0].lower()
            rest = p[2:].replace("\\", "/")
            return f"/mnt/{drive}{rest}"
        return p
        
    def windows_path(self, wsl_path):
        """Convert WSL path to Windows path"""
        if wsl_path.startswith("/mnt/"):
            parts = wsl_path[5:].split("/", 1)
            drive = parts[0].upper()
            rest = parts[1] if len(parts) > 1 else ""
            # Avoid backslashes inside f-string expressions (invalid syntax).
            rest_win = rest.replace("/", "\\")
            return f"{drive}:\\{rest_win}"
        return wsl_path
        
    def process_audio(self, audio_file, output_file=None, timeout=None, audio_duration=None):
        """
        Process audio file using WSL2
        
        Args:
            audio_file: Path to audio file on Windows
            output_file: Optional output path (auto-generated if None)
            timeout: Processing timeout in seconds (auto-calculated if None)
            audio_duration: Audio duration in seconds (for timeout calculation)
            
        Returns:
            dict: Processing results with transcription segments
        """
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        self._ensure_workspace_ready()
            
        # Calculate dynamic timeout based on audio duration
        # Formula: base_overhead + (duration * processing_factor)
        if timeout is None:
            if audio_duration:
                # 120s base + 4x duration (for transcription + diarization + emotion + embeddings)
                timeout = max(300, int(120 + (audio_duration * 4)))
            else:
                timeout = 1200  # Default 20min fallback
            
        # Convert to WSL path
        wsl_input = self.wsl_path(audio_path)
        
        # Output directory for results
        wsl_output = f"{self.audio_workspace}/output"
        
        request_uuid = str(uuid.uuid4())

        # Build command - use CUDA environment setup (includes venv + cuDNN paths)
        cmd = (
            f"source {self.audio_workspace}/setup_cuda_env.sh && "
            f"GOODQ_BRIDGE_REQUEST_UUID='{request_uuid}' "
            f"python3 {self.audio_workspace}/process_audio.py '{wsl_input}' '{wsl_output}'"
        )
        
        print(f"Processing: {audio_path.name}")
        process_started_epoch = time.time()
        requested_scene_file = Path(str(wsl_input).replace("\\", "/")).name

        def _stderr_warnings(stderr: str, max_lines: int = 50, max_chars: int = 300) -> list[str]:
            warnings: list[str] = []
            for line in (stderr or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                if len(line) > max_chars:
                    line = line[:max_chars] + "..."
                warnings.append(line)
                if len(warnings) >= max_lines:
                    break
            return warnings

        def _try_parse_json(text: str) -> dict | None:
            text = (text or "").strip()
            if not text:
                return None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None

        def _read_result_json_debug() -> dict | None:
            # Debug-only fallback: never authoritative for success.
            try:
                read_cmd = ["wsl", "-d", self.wsl_distro, "--", "cat", f"{wsl_output}/result.json"]
                read_result = subprocess.run(read_cmd, capture_output=True, text=True, timeout=10)
            except Exception:
                return None
            if read_result.returncode != 0:
                return None
            return _try_parse_json(read_result.stdout)

        def _result_json_mtime_epoch() -> tuple[Optional[float], Dict[str, Any]]:
            try:
                stat_cmd = [
                    "wsl",
                    "-d",
                    self.wsl_distro,
                    "--",
                    "bash",
                    "-c",
                    f"stat -c %Y '{wsl_output}/result.json'",
                ]
                stat_result = subprocess.run(stat_cmd, capture_output=True, text=True, timeout=10)
            except Exception as exc:
                return None, {
                    "probe": "result_json_mtime",
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                }
            if stat_result.returncode != 0:
                return None, {
                    "probe": "result_json_mtime",
                    "stat_returncode": stat_result.returncode,
                    "stat_stdout_tail": (stat_result.stdout or "")[-300:],
                    "stat_stderr_tail": (stat_result.stderr or "")[-300:],
                }
            raw_mtime = (stat_result.stdout or "").strip()
            try:
                return float(raw_mtime), {
                    "probe": "result_json_mtime",
                    "stat_returncode": stat_result.returncode,
                }
            except (TypeError, ValueError):
                return None, {
                    "probe": "result_json_mtime",
                    "stat_returncode": stat_result.returncode,
                    "stat_stdout_raw": raw_mtime[:300],
                }

        def _scene_file_name(path_value: Any) -> str:
            if not isinstance(path_value, str):
                return ""
            return Path(path_value.replace("\\", "/")).name

        def _build_error(
            reason: str,
            *,
            error_message: str,
            wsl_returncode: Optional[int],
            stderr_warnings: list[str],
            details: Optional[Dict[str, Any]] = None,
            returned_scene_file: Optional[str] = None,
            returned_request_uuid: Optional[str] = None,
            used_fallback_result_json: bool = False,
            env_warnings: Optional[list[str]] = None,
        ) -> Dict[str, Any]:
            payload: Dict[str, Any] = {
                "status": "error",
                "error": error_message,
                "bridge_error_reason": reason,
                "bridge_error_details": details or {},
                "wsl_returncode": wsl_returncode,
                "returncode": wsl_returncode,
                "requested_scene_file": requested_scene_file,
                "returned_scene_file": returned_scene_file,
                "requested_request_uuid": request_uuid,
                "returned_request_uuid": returned_request_uuid,
                "used_fallback_result_json": bool(used_fallback_result_json),
            }
            if stderr_warnings:
                payload["stderr_warnings"] = stderr_warnings
            if env_warnings:
                payload["bridge_env_warnings"] = env_warnings
            return payload

        # Execute in WSL2
        try:
            runtime_probe = probe_wsl_audio_runtime(self.wsl_distro, self.audio_workspace)
            if not bool(runtime_probe.get("runtime_ready")):
                return _build_error(
                    "wsl_env_runtime_unavailable",
                    error_message=str(runtime_probe.get("detail") or "WSL audio runtime preflight failed"),
                    wsl_returncode=None,
                    stderr_warnings=[],
                    details=runtime_probe,
                    used_fallback_result_json=False,
                )
            if not bool(runtime_probe.get("abi_ready")):
                return _build_error(
                    "wsl_env_abi_unavailable",
                    error_message=str(
                        runtime_probe.get("detail")
                        or "WSL audio runtime ABI preflight failed"
                    ),
                    wsl_returncode=None,
                    stderr_warnings=[],
                    details=runtime_probe,
                    used_fallback_result_json=False,
                )
            env_warnings: list[str] = []
            if "diarization_ready" in runtime_probe and not bool(runtime_probe.get("diarization_ready")):
                diarization_warning = str(
                    runtime_probe.get("diarization_detail")
                    or "diarization runtime unavailable"
                ).strip()
                if diarization_warning and diarization_warning not in env_warnings:
                    env_warnings.append(diarization_warning)
            result = subprocess.run(
                ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            stderr_warnings = _stderr_warnings(result.stderr)
            fallback_debug = None
            fallback_used = False

            output = _try_parse_json(result.stdout)
            if output is None:
                fallback_debug = _read_result_json_debug()
                fallback_used = isinstance(fallback_debug, dict)
                if fallback_debug is not None and result.returncode == 0:
                    stderr_warnings.append("stdout_json_parse_failed; result.json read for debug only")

            if result.returncode != 0:
                details = {
                    "stdout_json_parse_ok": isinstance(output, dict),
                    "stderr_tail": (result.stderr or "")[-600:],
                }
                processor_error = None
                if isinstance(fallback_debug, dict):
                    details["fallback_result_status"] = fallback_debug.get("status")
                    details["fallback_result_audio_file"] = fallback_debug.get("audio_file")
                    details["fallback_result_request_uuid"] = fallback_debug.get("request_uuid")
                    details["processor_transcription_status"] = fallback_debug.get("transcription_status")
                    details["processor_diarization_status"] = fallback_debug.get("diarization_status")
                    details["processor_emotion_status"] = fallback_debug.get("emotion_status")
                    details["processor_embeddings_status"] = fallback_debug.get("embeddings_status")
                    processor_error = str(fallback_debug.get("error") or "").strip() or None
                    if processor_error:
                        details["processor_error"] = processor_error
                    processor_traceback = str(fallback_debug.get("traceback") or "").strip()
                    if processor_traceback:
                        details["processor_traceback_tail"] = processor_traceback[-1200:]
                error_message = f"WSL audio processor exited with return code {result.returncode}"
                if processor_error:
                    error_message = f"{error_message}: {processor_error}"
                return _build_error(
                    "wsl_subprocess_nonzero",
                    error_message=error_message,
                    wsl_returncode=result.returncode,
                    stderr_warnings=stderr_warnings,
                    details=details,
                    returned_scene_file=_scene_file_name(
                        fallback_debug.get("audio_file") if isinstance(fallback_debug, dict) else None
                    )
                    or None,
                    returned_request_uuid=(
                        fallback_debug.get("request_uuid") if isinstance(fallback_debug, dict) else None
                    ),
                    used_fallback_result_json=fallback_used,
                    env_warnings=env_warnings,
                )

            if output is None:
                details = {
                    "stdout_json_parse_ok": False,
                    "stdout_prefix": (result.stdout or "").strip()[:400],
                }
                if isinstance(fallback_debug, dict):
                    details["fallback_result_status"] = fallback_debug.get("status")
                    details["fallback_result_audio_file"] = fallback_debug.get("audio_file")
                    details["fallback_result_request_uuid"] = fallback_debug.get("request_uuid")
                return _build_error(
                    "stdout_json_parse_failed",
                    error_message="No valid JSON output from WSL audio processor stdout",
                    wsl_returncode=result.returncode,
                    stderr_warnings=stderr_warnings,
                    details=details,
                    returned_scene_file=_scene_file_name(
                        fallback_debug.get("audio_file") if isinstance(fallback_debug, dict) else None
                    )
                    or None,
                    returned_request_uuid=(
                        fallback_debug.get("request_uuid") if isinstance(fallback_debug, dict) else None
                    ),
                    used_fallback_result_json=fallback_used,
                    env_warnings=env_warnings,
                )

            returned_request_uuid = output.get("request_uuid") if isinstance(output.get("request_uuid"), str) else None
            if not returned_request_uuid:
                return _build_error(
                    "request_uuid_missing",
                    error_message="WSL audio output missing request_uuid",
                    wsl_returncode=result.returncode,
                    stderr_warnings=stderr_warnings,
                    details={},
                    returned_scene_file=_scene_file_name(output.get("audio_file")) or None,
                    returned_request_uuid=None,
                    used_fallback_result_json=False,
                    env_warnings=env_warnings,
                )
            if returned_request_uuid != request_uuid:
                return _build_error(
                    "request_uuid_mismatch",
                    error_message="WSL audio output request_uuid mismatch",
                    wsl_returncode=result.returncode,
                    stderr_warnings=stderr_warnings,
                    details={
                        "requested_request_uuid": request_uuid,
                        "returned_request_uuid": returned_request_uuid,
                    },
                    returned_scene_file=_scene_file_name(output.get("audio_file")) or None,
                    returned_request_uuid=returned_request_uuid,
                    used_fallback_result_json=False,
                    env_warnings=env_warnings,
                )

            returned_scene_file = _scene_file_name(output.get("audio_file"))
            if not returned_scene_file or returned_scene_file.lower() != requested_scene_file.lower():
                details = {
                    "requested_audio_file": wsl_input,
                    "returned_audio_file": output.get("audio_file"),
                }
                return _build_error(
                    "stale_or_mismatched_result",
                    error_message="WSL audio output identity mismatch",
                    wsl_returncode=result.returncode,
                    stderr_warnings=stderr_warnings,
                    details=details,
                    returned_scene_file=returned_scene_file or None,
                    returned_request_uuid=returned_request_uuid,
                    used_fallback_result_json=False,
                    env_warnings=env_warnings,
                )

            result_json_mtime, freshness_probe = _result_json_mtime_epoch()
            if result_json_mtime is None:
                time.sleep(0.5)
                retried_result_json_mtime, freshness_retry_probe = _result_json_mtime_epoch()
                if retried_result_json_mtime is not None:
                    result_json_mtime = retried_result_json_mtime
                    stderr_warnings.append("result_json_freshness_probe_retried")
                else:
                    details = {
                        "freshness_probe_attempts": [
                            freshness_probe,
                            freshness_retry_probe,
                        ]
                    }
                    return _build_error(
                        "result_json_freshness_unavailable",
                        error_message="Unable to verify WSL result.json freshness",
                        wsl_returncode=result.returncode,
                        stderr_warnings=stderr_warnings,
                        details=details,
                        returned_scene_file=returned_scene_file or None,
                        returned_request_uuid=returned_request_uuid,
                        used_fallback_result_json=False,
                        env_warnings=env_warnings,
                    )
            if result_json_mtime < (process_started_epoch - 1.0):
                details = {
                    "result_json_mtime_epoch": result_json_mtime,
                    "process_started_epoch": process_started_epoch,
                    "freshness_probe": freshness_probe,
                }
                return _build_error(
                    "stale_or_mismatched_result",
                    error_message="WSL result.json is stale relative to process start",
                    wsl_returncode=result.returncode,
                    stderr_warnings=stderr_warnings,
                    details=details,
                    returned_scene_file=returned_scene_file or None,
                    returned_request_uuid=returned_request_uuid,
                    used_fallback_result_json=False,
                    env_warnings=env_warnings,
                )

            # Always attach warnings and explicit bridge metadata for observability.
            if stderr_warnings:
                output.setdefault("stderr_warnings", stderr_warnings)
            if env_warnings:
                output.setdefault("bridge_env_warnings", env_warnings)
            output.setdefault("returncode", result.returncode)
            output.setdefault("wsl_returncode", result.returncode)
            output.setdefault("requested_scene_file", requested_scene_file)
            output.setdefault("returned_scene_file", returned_scene_file)
            output.setdefault("requested_request_uuid", request_uuid)
            output.setdefault("returned_request_uuid", returned_request_uuid)
            output.setdefault("used_fallback_result_json", False)

            if output.get("status") == "success":
                return output

            details = {"output_status": output.get("status")}
            return _build_error(
                "wsl_processor_reported_error",
                error_message=str(output.get("error") or "Unknown error"),
                wsl_returncode=result.returncode,
                stderr_warnings=stderr_warnings,
                details=details,
                returned_scene_file=returned_scene_file or None,
                returned_request_uuid=returned_request_uuid,
                used_fallback_result_json=False,
                env_warnings=env_warnings,
            )

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": f"Processing timeout after {timeout}s",
                "bridge_error_reason": "wsl_timeout",
                "bridge_error_details": {"timeout_seconds": timeout},
                "wsl_returncode": None,
                "returncode": None,
                "requested_scene_file": requested_scene_file,
                "returned_scene_file": None,
                "requested_request_uuid": request_uuid,
                "returned_request_uuid": None,
                "used_fallback_result_json": False,
            }
            
    def check_status(self):
        """Check if WSL2 audio is ready"""
        self._ensure_workspace_ready()
        test_cmd = f"source {self.audio_workspace}/setup_cuda_env.sh && python3 -c 'import torch; print(torch.cuda.is_available())' 2>&1"
        result = subprocess.run(
            ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", test_cmd],
            capture_output=True,
            text=True
        )
        # Check if CUDA environment works
        return result.returncode == 0 and "True" in result.stdout
        
    def get_info(self):
        """Get WSL2 audio system info"""
        self._ensure_workspace_ready()
        info_cmd = f"source {self.audio_workspace}/setup_cuda_env.sh && python3 -c \"import torch; print(f'Device: {{\\\"cuda\\\" if torch.cuda.is_available() else \\\"cpu\\\"}}'); import sys; sys.stdout.flush(); print(f'GPU: {{torch.cuda.get_device_name(0)}}') if torch.cuda.is_available() else None; print(f'VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}}GB') if torch.cuda.is_available() else None\" 2>&1"
        
        result = subprocess.run(
            ["wsl", "-d", self.wsl_distro, "--", "bash", "-c", info_cmd],
            capture_output=True,
            text=True
        )
        return result.stdout if result.returncode == 0 else "Not available"

# Example usage
if __name__ == "__main__":
    bridge = WSL2AudioBridge()
    
    print("="*60)
    print("  GoodQ4All WSL2 Audio Bridge")
    print("="*60)
    print()
    print("Status:", "Ready" if bridge.check_status() else "Not Ready")
    print()
    print("System Info:")
    print(bridge.get_info())
    print()
    print("="*60)
    print()
    print("Usage:")
    print("  from wsl2_audio_bridge import WSL2AudioBridge")
    print("  bridge = WSL2AudioBridge()")
    print("  result = bridge.process_audio('path/to/audio.wav')")
    print("  print(result['segments'])")
