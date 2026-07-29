"""
GoodQ4All WSL2 Audio Bridge
Simple interface to WSL2 audio processing
"""

import sys
import subprocess
import json
import time
import os
import uuid
import hashlib
import shlex
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from scripts.wsl_audio_preflight import probe_wsl_audio_runtime
except Exception:  # noqa: BLE001
    from wsl_audio_preflight import probe_wsl_audio_runtime

def _read_timeout_sequence(env_name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    raw_value = os.environ.get(env_name, "").strip()
    if not raw_value:
        return default
    values: list[int] = []
    for part in raw_value.split(","):
        try:
            value = int(part.strip())
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return tuple(values) or default


_WORKSPACE_PREFLIGHT_TIMEOUTS = _read_timeout_sequence("GOODQ_WSL_WORKSPACE_PREFLIGHT_TIMEOUTS", (30, 90))
_WORKSPACE_PREFLIGHT_RETRY_DELAY_SEC = 0.25


def _compact_runtime_probe(probe: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(probe, dict):
        return {}
    black_box = probe.get("runtime_black_box") if isinstance(probe.get("runtime_black_box"), dict) else {}
    torchcodec = black_box.get("torchcodec") if isinstance(black_box.get("torchcodec"), dict) else {}
    ffmpeg = black_box.get("ffmpeg") if isinstance(black_box.get("ffmpeg"), dict) else {}
    ffmpeg_libraries = (
        black_box.get("ffmpeg_libraries")
        if isinstance(black_box.get("ffmpeg_libraries"), dict)
        else {}
    )
    package_versions = (
        black_box.get("package_versions")
        if isinstance(black_box.get("package_versions"), dict)
        else probe.get("detected_versions")
    )
    return {
        "source": "wsl_audio_preflight",
        "runtime_ready": bool(probe.get("runtime_ready")),
        "abi_ready": bool(probe.get("abi_ready")),
        "diarization_ready": bool(probe.get("diarization_ready")),
        "wav2vec_enrichment_ready": bool(probe.get("wav2vec_enrichment_ready")),
        "torch_lane_status": probe.get("torch_lane_status"),
        "expected_torch_lane": probe.get("expected_torch_lane"),
        "package_versions": package_versions or {},
        "active_env_kind": black_box.get("active_env_kind"),
        "python_version": black_box.get("python_version"),
        "torchcodec_ready": probe.get("torchcodec_ready"),
        "torchcodec_detail": probe.get("torchcodec_detail"),
        "torchcodec_error_families": torchcodec.get("error_families") or [],
        "ffmpeg_available": ffmpeg.get("available"),
        "ffmpeg_version_first_line": ffmpeg.get("version_first_line"),
        "ffmpeg_libraries": ffmpeg_libraries.get("libraries") or [],
        "runtime_warnings": probe.get("runtime_warnings") or [],
    }


class AudioRunner:
    def process_audio(self, audio_file: str, output_file: Optional[str] = None, timeout: Optional[int] = None, audio_duration: Optional[float] = None) -> dict:
        raise NotImplementedError()

    def check_status(self) -> bool:
        raise NotImplementedError()

    def get_info(self) -> str:
        raise NotImplementedError()


def normalize_huggingface_cache_refs(cache_dir: Path) -> None:
    """Normalize CRLF line endings in Hugging Face cache ref files to prevent local_files_only errors in WSL/Linux."""
    if not cache_dir.exists():
        return
    try:
        # Search for all ref files in the cache directory (typically under hub/models--*/refs/*)
        for ref_path in cache_dir.glob("hub/models--*/refs/*"):
            if ref_path.is_file():
                try:
                    content = ref_path.read_bytes()
                    # Strip any trailing carriage return (\r) or newline (\n) or whitespace
                    cleaned = content.strip()
                    if cleaned != content:
                        ref_path.write_bytes(cleaned)
                        print(f"[WSL2AudioBridge][INFO] Normalized CRLF line endings in HF ref: {ref_path.name}")
                except Exception as e:
                    print(f"[WSL2AudioBridge][WARN] Failed to normalize HF ref {ref_path}: {e}")
    except Exception as e:
        print(f"[WSL2AudioBridge][WARN] Failed to scan HF cache directory for normalization: {e}")


class WindowsWSL2AudioRunner(AudioRunner):
    """Bridge to WSL2 audio processing on Windows"""
    _workspace_warning_keys: set[str] = set()
    
    def __init__(self):
        self.require_wsl_audio = self._is_truthy(os.environ.get("GOODQ_REQUIRE_WSL_AUDIO", ""))
        
        # Load unified configuration
        REPO_ROOT = Path(__file__).resolve().parents[1]
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        try:
            from steps.common.config_loader import load_configs
            cfg = load_configs()
        except Exception:
            cfg = {}
        self._config = cfg
        host_cfg = cfg.get('host', {})
        
        config_user = host_cfg.get('wsl_user')
        if config_user == "auto":
            config_user = None
        self.wsl_user = os.environ.get("GOODQ_WSL_USER") or config_user or self._resolve_wsl_user()
        if self.wsl_user:
            self.wsl_user = self.wsl_user.replace("\r", "").strip()
        
        config_workspace = host_cfg.get('wsl_workspace')
        if config_workspace == "auto":
            config_workspace = None
        self.workspace = os.environ.get("GOODQ_WSL_WORKSPACE") or config_workspace or self._resolve_wsl_workspace()
        if self.workspace:
            self.workspace = self.workspace.replace("\r", "").strip()
        self.audio_workspace = self.workspace.rstrip("/")
        
        config_distro = host_cfg.get('wsl_distro')
        if config_distro == "auto":
            config_distro = None
        self.wsl_distro = os.environ.get("GOODQ_WSL_DISTRO") or config_distro or "Ubuntu"
        if self.wsl_distro:
            self.wsl_distro = self.wsl_distro.replace("\r", "").strip()
        
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

        # Normalize carriage returns in HF refs if models directory exists
        try:
            from bootstrap_models import resolve_models_root
        except ImportError:
            try:
                from scripts.bootstrap_models import resolve_models_root
            except ImportError:
                resolve_models_root = None
        if resolve_models_root:
            try:
                models_root = resolve_models_root()
                if models_root:
                    normalize_huggingface_cache_refs(models_root)
            except Exception as e:
                print(f"[WSL2AudioBridge][WARN] Failed to resolve models root for HF ref normalization: {e}")

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

        mismatches = self._workspace_worker_mismatches()
        if mismatches:
            self._workspace_ready = False
            message = (
                "WSL worker deployment is stale or incomplete: "
                + ", ".join(mismatches)
                + ". Synchronize the worker before processing audio."
            )
            if self.require_wsl_audio:
                raise RuntimeError(message)
            self._warn_workspace_once(message, warning_kind="worker_mismatch")
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

    def _wsl_model_cache_exports(self) -> Dict[str, str]:
        """Return the canonical cache authority for a managed WSL audio run.

        WSL does not inherit the Windows process environment.  Passing these
        variables in the bridge command prevents Hugging Face from silently
        creating or consuming a per-user fallback cache on GPU-managed hosts.
        """
        paths_cfg = self._config.get("paths", {}) if isinstance(self._config, dict) else {}
        raw_root = (
            os.environ.get("GOODQ_MODEL_CACHE_ROOT")
            or os.environ.get("HF_HOME")
            or paths_cfg.get("models_cache")
        )
        if not raw_root:
            if self.require_wsl_audio:
                raise RuntimeError(
                    "GOODQ_REQUIRE_WSL_AUDIO=1 requires a configured canonical models_cache; "
                    "refusing the per-user Hugging Face cache fallback."
                )
            return {}

        root = self.wsl_path(Path(str(raw_root)))
        hub = f"{root.rstrip('/')}/hub"
        return {
            "GOODQ_MODEL_CACHE_ROOT": root,
            "HF_HOME": root,
            "TORCH_HOME": root,
            "HUGGINGFACE_HUB_CACHE": hub,
            "HF_HUB_CACHE": hub,
            "PYANNOTE_CACHE": hub,
        }

    @staticmethod
    def _worker_file_names() -> tuple[str, ...]:
        return ("setup_cuda_env.sh", "process_audio.py", "model_cache.py")

    def _expected_worker_hashes(self) -> Dict[str, str]:
        source_root = Path(__file__).resolve().parents[1] / "wsl2_audio"
        return {
            name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
            for name in self._worker_file_names()
        }

    def _workspace_worker_mismatches(self) -> list[str]:
        """Return stale or unreadable deployed worker filenames without mutating WSL."""
        expected = self._expected_worker_hashes()
        paths = " ".join(
            shlex.quote(f"{self.audio_workspace}/{name}")
            for name in self._worker_file_names()
        )
        result = subprocess.run(
            ["wsl", "-d", self.wsl_distro, "--", "bash", "-lc", f"sha256sum {paths}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return list(expected)
        actual = [line.split(maxsplit=1)[0].lower() for line in result.stdout.splitlines() if line.strip()]
        mismatches = [
            name
            for name, actual_hash in zip(self._worker_file_names(), actual)
            if actual_hash != expected[name]
        ]
        return mismatches + list(self._worker_file_names()[len(actual):])
        
    def process_audio(self, audio_file, output_file=None, timeout=None, audio_duration=None):
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        self._ensure_workspace_ready()
            
        # Calculate dynamic timeout based on audio duration
        if timeout is None:
            if audio_duration:
                timeout = max(300, int(120 + (audio_duration * 4)))
            else:
                timeout = 1200
            
        wsl_input = self.wsl_path(audio_path)
        
        # Verify if input file is accessible inside WSL distribution
        file_check = subprocess.run(
            ["wsl", "-d", self.wsl_distro, "--", "test", "-f", wsl_input],
            capture_output=True
        )
        if file_check.returncode != 0:
            drive_letter = audio_path.drive
            mount_point = f"/mnt/{drive_letter[0].lower()}" if drive_letter else ""
            mount_check = subprocess.run(
                ["wsl", "-d", self.wsl_distro, "--", "test", "-d", mount_point],
                capture_output=True
            )
            if mount_check.returncode != 0:
                raise FileNotFoundError(
                    f"WSL cannot access the path '{wsl_input}'. "
                    f"The mount point '{mount_point}' is not mounted or accessible in WSL distro '{self.wsl_distro}'."
                )
            else:
                raise FileNotFoundError(
                    f"WSL cannot find the file at '{wsl_input}'. "
                    "Ensure the file has been successfully written and has appropriate read permissions."
                )

        wsl_output = f"{self.audio_workspace}/output"
        request_uuid = str(uuid.uuid4())

        setup_script = f"{self.audio_workspace}/setup_cuda_env.sh"
        processor = f"{self.audio_workspace}/process_audio.py"
        
        print(f"Processing: {audio_path.name}")
        process_started_epoch = time.time()
        requested_scene_file = Path(str(wsl_input).replace("\\", "/")).name
        runtime_probe: Optional[Dict[str, Any]] = None

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

        def _get_windows_result_json_path() -> Optional[str]:
            if os.name != "nt":
                return None
            try:
                if self.audio_workspace.startswith("/mnt/"):
                    win_workspace = self.windows_path(self.audio_workspace)
                    return os.path.join(win_workspace, "output", "result.json")
                
                wsl_path_part = self.audio_workspace.replace('/', '\\')
                if not wsl_path_part.startswith("\\"):
                    wsl_path_part = "\\" + wsl_path_part
                unc_path = f"\\\\wsl.localhost\\{self.wsl_distro}{wsl_path_part}\\output\\result.json"
                return unc_path
            except Exception:
                return None

        def _read_result_json_debug() -> dict | None:
            win_path = _get_windows_result_json_path()
            if win_path:
                try:
                    if os.path.exists(win_path):
                        with open(win_path, "r", encoding="utf-8", errors="ignore") as f:
                            return _try_parse_json(f.read())
                except Exception:
                    pass
            try:
                read_cmd = ["wsl", "-d", self.wsl_distro, "--", "cat", f"{wsl_output}/result.json"]
                read_result = subprocess.run(read_cmd, capture_output=True, text=True, timeout=10)
            except Exception:
                return None
            if read_result.returncode != 0:
                return None
            return _try_parse_json(read_result.stdout)

        def _result_json_mtime_epoch() -> tuple[Optional[float], Dict[str, Any]]:
            win_path = _get_windows_result_json_path()
            if win_path:
                try:
                    if os.path.exists(win_path):
                        mtime = os.path.getmtime(win_path)
                        return mtime, {
                            "probe": "result_json_mtime_unc",
                            "status": "success",
                            "path": win_path
                        }
                except Exception as exc:
                    pass
            try:
                stat_cmd = [
                    "wsl",
                    "-d",
                    self.wsl_distro,
                    "--",
                    "stat",
                    "-c",
                    "%Y",
                    f"{wsl_output}/result.json",
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
            compact_probe = _compact_runtime_probe(runtime_probe)
            if compact_probe:
                payload["bridge_runtime_probe"] = compact_probe
            return payload

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
            cache_exports = self._wsl_model_cache_exports()
            cache_export_script = "".join(
                f"export {key}={shlex.quote(value)}; "
                for key, value in cache_exports.items()
            )
            bridge_script = (
                f'set -euo pipefail; '
                f'{cache_export_script}'
                f'source {shlex.quote(setup_script)}; '
                f'export GOODQ_BRIDGE_REQUEST_UUID={shlex.quote(request_uuid)}; '
                f'exec python3 {shlex.quote(processor)} {shlex.quote(wsl_input)} {shlex.quote(wsl_output)}'
            )
            result = subprocess.run(
                [
                    "wsl",
                    "-d",
                    self.wsl_distro,
                    "--",
                    "bash",
                    "-lc",
                    bridge_script,
                ],
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

            if stderr_warnings:
                output.setdefault("stderr_warnings", stderr_warnings)
            if env_warnings:
                output.setdefault("bridge_env_warnings", env_warnings)
            compact_probe = _compact_runtime_probe(runtime_probe)
            if compact_probe:
                output.setdefault("bridge_runtime_probe", compact_probe)
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
                "bridge_runtime_probe": _compact_runtime_probe(runtime_probe),
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


class NativeAudioRunner(AudioRunner):
    """Bridge to native local audio processing for macOS (Apple Silicon) and Linux"""
    def __init__(self):
        self.audio_workspace = str(Path(__file__).resolve().parent.parent / "wsl2_audio")
        self.output_dir = f"{self.audio_workspace}/output"

    def process_audio(self, audio_file, output_file=None, timeout=None, audio_duration=None):
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        if timeout is None:
            if audio_duration:
                timeout = max(300, int(120 + (audio_duration * 4)))
            else:
                timeout = 1200

        import sys
        import uuid
        request_uuid = str(uuid.uuid4())
        
        # Ensure output directory exists
        out_path = Path(self.output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            sys.executable,
            str(Path(self.audio_workspace) / "process_audio.py"),
            str(audio_path.resolve()),
            str(out_path.resolve())
        ]
        
        env = os.environ.copy()
        env["GOODQ_BRIDGE_REQUEST_UUID"] = request_uuid
        
        # Audio device logic: macOS defaults to CPU for Diarization unless overridden
        device_override = os.environ.get("GOODQ_AUDIO_DEVICE")
        if device_override:
            env["GOODQ_DEVICE"] = device_override.lower()
        else:
            if sys.platform == "darwin":
                env["GOODQ_DEVICE"] = "mps"
                env["GOODQ_MPS_DIARIZATION"] = "0"
            elif sys.platform.startswith("linux"):
                import torch
                env["GOODQ_DEVICE"] = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"Processing: {audio_path.name}")
        requested_scene_file = audio_path.name

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            output = None
            if result.returncode == 0:
                try:
                    output = json.loads(result.stdout)
                except json.JSONDecodeError:
                    pass

            if output is None:
                result_json_file = out_path / "result.json"
                if result_json_file.exists():
                    try:
                        output = json.loads(result_json_file.read_text())
                    except json.JSONDecodeError:
                        pass

            if output is None:
                error_msg = result.stderr or "No valid JSON output from audio processor"
                return {
                    "status": "error",
                    "error": error_msg,
                    "bridge_error_reason": "stdout_json_parse_failed",
                    "returncode": result.returncode,
                    "requested_scene_file": requested_scene_file
                }

            output.setdefault("returncode", result.returncode)
            output.setdefault("requested_scene_file", requested_scene_file)
            output.setdefault("returned_scene_file", Path(output.get("audio_file", "")).name)
            output.setdefault("requested_request_uuid", request_uuid)
            output.setdefault("returned_request_uuid", output.get("request_uuid", request_uuid))
            output.setdefault("used_fallback_result_json", result.returncode != 0)
            return output

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": f"Processing timeout after {timeout}s",
                "bridge_error_reason": "native_timeout",
                "returncode": None,
                "requested_scene_file": requested_scene_file
            }

    def check_status(self) -> bool:
        try:
            import torch
            return True
        except ImportError:
            return False

    def get_info(self) -> str:
        try:
            import torch
            device_kind = "cpu"
            if torch.cuda.is_available():
                device_kind = f"cuda ({torch.cuda.get_device_name(0)})"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device_kind = "mps"
            return f"Device: {device_kind}\nPython: {sys.version}"
        except ImportError:
            return "Not available"


class WSL2AudioBridge(AudioRunner):
    """Polymorphic entry point proxying Windows-WSL2 and native macOS/Linux audio runners"""
    def __init__(self):
        self.native_mode = sys.platform != "win32" or os.environ.get("GOODQ_NATIVE_AUDIO") == "1"
        if self.native_mode:
            self.runner = NativeAudioRunner()
        else:
            self.runner = WindowsWSL2AudioRunner()

    def process_audio(self, audio_file, output_file=None, timeout=None, audio_duration=None):
        return self.runner.process_audio(audio_file, output_file, timeout, audio_duration)

    def check_status(self):
        return self.runner.check_status()

    def get_info(self):
        return self.runner.get_info()

    def __getattr__(self, name):
        return getattr(self.runner, name)

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
