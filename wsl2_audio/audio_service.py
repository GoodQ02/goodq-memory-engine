#!/usr/bin/env python3
"""
GoodQ4All - WSL2 Audio Processing Service

This service runs in WSL2 and processes audio files using GPU acceleration.
It watches a queue directory for incoming jobs from the Windows side.
"""

import json
import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
import signal

import torch
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

try:
    from wsl2_audio import model_cache
except ImportError:  # Direct WSL worker execution from its workspace.
    import model_cache

# Profile semantics (fallback to canonical behavior when steps package is unavailable in WSL context)
try:
    from steps.common.profile_config import (
        log_runtime_profile_state,
        require_gpu,
        resolve_wsl_gpu_config,
    )
except Exception:
    def require_gpu() -> bool:  # type: ignore
        return os.getenv("GOODQ_REQUIRE_GPU", "").strip().lower() in {"1", "true", "yes", "on"}

    def resolve_wsl_gpu_config(gpu_cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:  # type: ignore
        return dict(gpu_cfg or {})

    def log_runtime_profile_state(*args, **kwargs) -> None:  # type: ignore
        return None

# Setup logging
log_dir = Path.home() / "goodq_audio" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / 'audio_service.log')
    ]
)
logger = logging.getLogger(__name__)


def _resolve_hf_cache_dir() -> Optional[str]:
    """Return the canonical HF cache path exported by bootstrap, when present."""
    cache_dir = os.getenv("HUGGINGFACE_HUB_CACHE") or os.getenv("HF_HUB_CACHE") or None
    if cache_dir:
        os.environ.setdefault("HF_HUB_CACHE", cache_dir)
        os.environ.setdefault("PYANNOTE_CACHE", cache_dir)
    return cache_dir


def _load_pyannote_pipeline(
    pipeline_cls: Any,
    model_name: str,
    token: str,
    cache_dir: Optional[str] = None,
    is_offline: bool = False,
):
    """Delegate PyAnnote compatibility handling to the shared cache authority."""
    return model_cache.load_pyannote_pipeline(
        pipeline_cls, model_name, token, cache_dir=cache_dir, is_offline=is_offline
    )


@dataclass
class GPUConfig:
    """GPU configuration"""
    device: str = "cuda"
    memory_fraction: float = 0.8
    compute_type: str = "float16"


@dataclass
class AudioJob:
    """Audio processing job"""
    job_id: str
    audio_path: str
    output_path: str
    task: str  # "transcribe", "diarize", "both"
    params: Dict[str, Any]
    run_id: Optional[str] = None


class AudioService:
    """WSL2 Audio Processing Service"""
    
    def __init__(self, config_path: str = "~/goodq_audio/config.json"):
        # === Q-BRANCH SELF-ANCHORING ===
        # Anchor base_dir to the location of this file, not $HOME, not CWD.
        self.base_dir = Path(__file__).resolve().parent
        
        # Config path within repo
        self.config_path = self.base_dir / "config.json"

        # Validate/load JSON
        self.config = self._load_config_safely()
        self.config["gpu"] = resolve_wsl_gpu_config(self.config.get("gpu", {}))

        # Auto-create expected directories (failsafe)
        self.queue_dir = self.base_dir / self.config.get("queue_dir", "queue_in")
        self.output_dir = self.base_dir / self.config.get("output_dir", "queue_out")
        self.logs_dir = self.base_dir / self.config.get("logs_dir", "logs")

        for d in [self.queue_dir, self.output_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Log environment variables
        sys.path.insert(0, str(self.base_dir))
        model_cache.log_env_summary(logger)

        self.running = True
        self.processing_lock = threading.Lock()

        gpu_cfg = self.config.get("gpu", {}) or {}
        requested_device = str(gpu_cfg.get("device", "cuda")).lower()
        gpu_enabled = requested_device == "cuda" and torch.cuda.is_available()
        log_runtime_profile_state(
            logger=logger,
            context="wsl2_audio.audio_service",
            gpu_enabled=gpu_enabled,
            wsl_enabled=True,
        )
        
        # GPU setup
        self._setup_gpu()
        
        # Load models
        self.whisper_model = None
        self.diarization_pipeline = None
        self.vad_model = None
        self._load_models()
        
        logger.info("Audio service initialized")
    
    def _load_config_safely(self):
        """
        Loads config.json with failsafe behavior:
        - Validates JSON
        - Guarantees a dict
        - Fixes double-object / merge errors
        """

        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")

        text = self.config_path.read_text().strip()

        # If config accidentally has multiple JSON objects, split and take first valid
        if text.count("{") > 1:
            # Try to extract the first valid object
            candidate = text.split("}{")[0] + "}"
            try:
                return json.loads(candidate)
            except Exception:
                pass  # fall through to normal load

        # Normal JSON load
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in {self.config_path}: {e}")

    @staticmethod
    def _resolve_secret(raw_value: Any, env_key: Optional[str] = None) -> Optional[str]:
        """Resolve a secret value from env-first config references."""
        if isinstance(env_key, str) and env_key.strip():
            env_value = os.getenv(env_key.strip())
            if env_value:
                return env_value

        if isinstance(raw_value, str):
            value = raw_value.strip()
            if value.startswith("${") and value.endswith("}"):
                ref = value[2:-1].strip()
                if ref:
                    return os.getenv(ref)
            return value or None
        return None
    
    def _setup_gpu(self):
        """Configure GPU"""
        gpu_config = self.config.get('gpu', {})
        configured_device = str(gpu_config.get('device', 'cuda')).lower()
        wants_cuda = configured_device == "cuda"
        cuda_available = torch.cuda.is_available()

        if wants_cuda and cuda_available:
            device_name = torch.cuda.get_device_name(0)
            memory_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            
            logger.info(f"GPU: {device_name}")
            logger.info(f"VRAM: {memory_total:.1f} GB")
            logger.info(f"CUDA: {torch.version.cuda}")
            
            # Set memory fraction
            memory_fraction = gpu_config.get('memory_fraction', 0.8)
            torch.cuda.set_per_process_memory_fraction(memory_fraction, 0)
            
            # Enable optimizations
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            
            logger.info(f"GPU memory fraction: {memory_fraction*100:.0f}%")
        else:
            if require_gpu():
                if not wants_cuda:
                    raise RuntimeError("GOODQ_REQUIRE_GPU=1 but profile/config resolved WSL audio device to CPU")
                raise RuntimeError("GOODQ_REQUIRE_GPU=1 but CUDA is not available in WSL audio service")
            if wants_cuda:
                logger.warning("CUDA not available, will use CPU (slow!)")
            else:
                logger.info("WSL audio running in CPU mode by profile/config")
    
    def _load_models(self):
        """Load AI models"""
        models_config = self.config.get('models', {})
        gpu_config = self.config.get('gpu', {})
        
        if hasattr(self, 'base_dir') and self.base_dir:
            sys.path.insert(0, str(self.base_dir))
            
        is_offline = model_cache.is_offline_mode()
        
        # Load Whisper
        try:
            whisper_model = models_config.get('whisper', 'large-v3')
            device = str(gpu_config.get('device', 'cuda')).lower()
            compute_type = str(gpu_config.get('compute_type', 'float16')).lower()
            if device == "cuda" and not torch.cuda.is_available():
                if require_gpu():
                    raise RuntimeError("GOODQ_REQUIRE_GPU=1 but CUDA is unavailable for Whisper load")
            
            if is_offline and not model_cache.check_whisper_cache(whisper_model):
                raise OSError(
                    f"Offline mode: Faster-Whisper model '{whisper_model}' is missing from local cache.\n"
                    "Status: Non-gated.\n"
                    "Requirements: No Hugging Face token or license terms required.\n"
                    "Approved Provisioning Command: python3 scripts/install_pipeline_wsl.py --download-whisper"
                )
                
            logger.info(f"Loading Whisper model: {whisper_model}")
            self.whisper_model = WhisperModel(
                whisper_model,
                device=device,
                compute_type=compute_type,
                num_workers=4,
                local_files_only=is_offline
            )
            logger.info("[SYMBOL] Whisper model loaded")
        except Exception as e:
            redacted_error = model_cache.redact_sensitive_info(str(e))
            logger.error(f"Failed to load Whisper: {redacted_error}")
            if is_offline:
                raise

        # Load Silero VAD
        try:
            logger.info("Loading Silero VAD...")
            self.vad_model, vad_utils = model_cache.load_silero_vad(offline=is_offline)
            self.vad_get_speech_timestamps = vad_utils[0]
            self.vad_collect_chunks = vad_utils[4]
            logger.info("[SYMBOL] Silero VAD loaded")
        except Exception as e:
            redacted_error = model_cache.redact_sensitive_info(str(e))
            logger.error(f"Failed to load VAD: {redacted_error}")
            if is_offline:
                raise

        # Load PyAnnote diarization
        try:
            from pyannote.audio import Pipeline
            
            diarization_model = models_config.get('diarization', 'pyannote/speaker-diarization-3.1')
            hf_token = self._resolve_secret(
                self.config.get('huggingface_token'),
                self.config.get('huggingface_token_env', 'PYANNOTE_TOKEN'),
            )
            
            if is_offline and not model_cache.check_pyannote_cache(diarization_model):
                raise OSError(
                    f"Offline mode: PyAnnote diarization model '{diarization_model}' is missing from local cache.\n"
                    "Status: Gated.\n"
                    "Requirements: Requires Hugging Face account licensing approval and access token (HF_TOKEN or PYANNOTE_TOKEN).\n"
                    "Approved Provisioning Command: python3 scripts/install_pipeline_wsl.py --download-pyannote"
                )
                
            if hf_token or is_offline:
                logger.info(f"Loading diarization model: {diarization_model}")
                self.diarization_pipeline = _load_pyannote_pipeline(
                    Pipeline,
                    diarization_model,
                    hf_token or "",
                    cache_dir=_resolve_hf_cache_dir(),
                    is_offline=is_offline,
                )
                if self.diarization_pipeline and str(gpu_config.get("device", "cuda")).lower() == "cuda" and torch.cuda.is_available():
                    self.diarization_pipeline.to(torch.device("cuda"))
                logger.info("[SYMBOL] Diarization pipeline loaded")
            else:
                logger.warning("No HuggingFace token provided, diarization unavailable")
        except Exception as e:
            redacted_error = model_cache.redact_sensitive_info(str(e))
            logger.error(f"Failed to load diarization: {redacted_error}")
            if is_offline:
                raise
    
    def apply_vad(self, audio_path: str) -> Optional[str]:
        """Apply VAD to extract speech segments"""
        if not self.vad_model:
            logger.warning("VAD model not loaded, skipping VAD")
            return audio_path
        
        try:
            logger.info(f"Applying VAD to {audio_path}")
            
            # Load audio
            wav, sr = sf.read(audio_path)
            
            # Convert to mono if stereo
            if len(wav.shape) > 1:
                wav = wav.mean(axis=1)
            
            # Resample to 16kHz if needed
            if sr != 16000:
                import librosa
                wav = librosa.resample(wav, orig_sr=sr, target_sr=16000)
                sr = 16000
            
            # Convert to tensor
            wav_tensor = torch.FloatTensor(wav)
            
            # Get speech timestamps
            processing_config = self.config.get('processing', {})
            speech_timestamps = self.vad_get_speech_timestamps(
                wav_tensor,
                self.vad_model,
                sampling_rate=sr,
                threshold=processing_config.get('vad_threshold', 0.5),
                min_speech_duration_ms=processing_config.get('min_speech_duration_ms', 250),
                min_silence_duration_ms=processing_config.get('min_silence_duration_ms', 100)
            )
            
            if not speech_timestamps:
                logger.warning("No speech detected by VAD")
                return audio_path
            
            # Collect speech chunks
            speech_chunks = self.vad_collect_chunks(speech_timestamps, wav_tensor)
            speech_audio = torch.cat(speech_chunks, dim=0).numpy()
            
            # Save VAD-filtered audio
            vad_output = audio_path.replace('.wav', '_vad.wav')
            sf.write(vad_output, speech_audio, sr)
            
            original_duration = len(wav) / sr
            filtered_duration = len(speech_audio) / sr
            reduction = (1 - filtered_duration / original_duration) * 100
            
            logger.info(f"VAD complete: {original_duration:.1f}s → {filtered_duration:.1f}s ({reduction:.0f}% reduction)")
            
            return vad_output
            
        except Exception as e:
            redacted_error = model_cache.redact_sensitive_info(str(e))
            logger.error(f"VAD failed: {redacted_error}")
            traceback.print_exc()
            return audio_path
    
    def transcribe_audio(self, audio_path: str, job: AudioJob) -> Dict:
        """Transcribe audio using Whisper"""
        if not self.whisper_model:
            raise RuntimeError("Whisper model not loaded")
        
        start_time = time.time()
        
        # Apply VAD first
        vad_audio = self.apply_vad(audio_path)
        
        logger.info(f"Transcribing: {vad_audio}")
        
        # Transcribe
        segments, info = self.whisper_model.transcribe(
            vad_audio,
            language=job.params.get('language'),
            task=job.params.get('task', 'transcribe'),
            beam_size=job.params.get('beam_size', 5),
            vad_filter=False,  # Already applied
            word_timestamps=True
        )
        
        # Collect results
        transcription = []
        full_text = []
        
        for segment in segments:
            seg_dict = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "words": []
            }
            
            if hasattr(segment, 'words') and segment.words:
                for word in segment.words:
                    seg_dict["words"].append({
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "probability": word.probability
                    })
            
            transcription.append(seg_dict)
            full_text.append(segment.text.strip())
        
        elapsed = time.time() - start_time
        audio_duration = info.duration
        rtf = elapsed / audio_duration if audio_duration > 0 else 0
        
        result = {
            "job_id": job.job_id,
            "run_id": job.run_id,
            "status": "success",
            "transcription": transcription,
            "full_text": " ".join(full_text),
            "info": {
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "processing_time": elapsed,
                "rtf": rtf
            }
        }
        
        logger.info(f"Transcription complete: {audio_duration:.1f}s audio in {elapsed:.1f}s (RTF: {rtf:.2f}x)")
        
        return result
    
    def diarize_audio(self, audio_path: str, job: AudioJob) -> Dict:
        """Perform speaker diarization"""
        if not self.diarization_pipeline:
            raise RuntimeError("Diarization pipeline not loaded")
        
        start_time = time.time()
        
        # Apply VAD first
        vad_audio = self.apply_vad(audio_path)
        
        logger.info(f"Diarizing: {vad_audio}")
        
        # Run diarization
        diarization = self.diarization_pipeline(vad_audio)
        
        # Extract segments
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "speaker": speaker,
                "start": turn.start,
                "end": turn.end,
                "duration": turn.end - turn.start
            })
        
        elapsed = time.time() - start_time
        
        result = {
            "job_id": job.job_id,
            "run_id": job.run_id,
            "status": "success",
            "diarization": segments,
            "speaker_count": len(set(s['speaker'] for s in segments)),
            "processing_time": elapsed
        }
        
        logger.info(f"Diarization complete: {len(segments)} segments, {result['speaker_count']} speakers in {elapsed:.1f}s")
        
        return result
    
    def process_job(self, job: AudioJob) -> Dict:
        """Process an audio job"""
        try:
            if job.run_id:
                logger.info(f"Processing job {job.job_id} (run_id={job.run_id}): {job.task}")
            else:
                logger.info(f"Processing job {job.job_id}: {job.task}")
            
            if job.task == "transcribe":
                result = self.transcribe_audio(job.audio_path, job)
            elif job.task == "diarize":
                result = self.diarize_audio(job.audio_path, job)
            elif job.task == "both":
                # Do both transcription and diarization
                trans_result = self.transcribe_audio(job.audio_path, job)
                diar_result = self.diarize_audio(job.audio_path, job)
                result = {
                    "job_id": job.job_id,
                    "run_id": job.run_id,
                    "status": "success",
                    "transcription": trans_result["transcription"],
                    "full_text": trans_result["full_text"],
                    "diarization": diar_result["diarization"],
                    "speaker_count": diar_result["speaker_count"],
                    "info": trans_result["info"]
                }
            else:
                raise ValueError(f"Unknown task: {job.task}")
            
            # Save result
            output_file = self.output_dir / f"{job.job_id}_result.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            logger.info(f"Job {job.job_id} complete, saved to {output_file}")
            
            return result
            
        except Exception as e:
            redacted_error = model_cache.redact_sensitive_info(str(e))
            logger.error(f"Job {job.job_id} failed: {redacted_error}")
            traceback.print_exc()
            
            error_result = {
                "job_id": job.job_id,
                "run_id": job.run_id,
                "status": "error",
                "error": redacted_error
            }
            
            # Save error
            output_file = self.output_dir / f"{job.job_id}_error.json"
            with open(output_file, 'w') as f:
                json.dump(error_result, f, indent=2)
            
            return error_result
    
    def watch_queue(self):
        """Watch queue directory for new jobs"""
        logger.info("Starting queue watcher...")
        
        pending_dir = self.queue_dir / "pending"
        processing_dir = self.queue_dir / "processing"
        completed_dir = self.queue_dir / "completed"
        failed_dir = self.queue_dir / "failed"
        
        while self.running:
            try:
                # Find pending jobs
                job_files = list(pending_dir.glob("*.json"))
                
                if job_files:
                    logger.info(f"Found {len(job_files)} pending job(s)")
                
                for job_file in job_files:
                    if not self.running:
                        break
                    
                    try:
                        # Move to processing
                        processing_file = processing_dir / job_file.name
                        job_file.rename(processing_file)
                        
                        # Load job
                        with open(processing_file, 'r') as f:
                            job_data = json.load(f)
                        
                        job = AudioJob(
                            job_id=job_data['job_id'],
                            run_id=job_data.get('run_id'),
                            audio_path=job_data['audio_path'],
                            output_path=job_data['output_path'],
                            task=job_data.get('task', 'both'),
                            params=job_data.get('params', {})
                        )
                        
                        # Process
                        result = self.process_job(job)
                        
                        # Move to completed or failed
                        if result['status'] == 'success':
                            final_file = completed_dir / job_file.name
                        else:
                            final_file = failed_dir / job_file.name
                        
                        processing_file.rename(final_file)
                        
                    except Exception as e:
                        redacted_error = model_cache.redact_sensitive_info(str(e))
                        logger.error(f"Failed to process job file {job_file}: {redacted_error}")
                        traceback.print_exc()
                
                # Sleep before next check
                time.sleep(2)
                
            except Exception as e:
                redacted_error = model_cache.redact_sensitive_info(str(e))
                logger.error(f"Queue watcher error: {redacted_error}")
                traceback.print_exc()
                time.sleep(5)
        
        logger.info("Queue watcher stopped")
    
    def start(self):
        """Start the service"""
        logger.info("="*80)
        logger.info("  GoodQ4All WSL2 Audio Service")
        logger.info("="*80)
        logger.info(f"Queue dir: {self.queue_dir}")
        logger.info(f"Output dir: {self.output_dir}")
        logger.info("="*80)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Start queue watcher
        self.watch_queue()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def stop(self):
        """Stop the service"""
        self.running = False


def main():
    """Main entry point"""
    service = AudioService()
    service.start()


if __name__ == '__main__':
    main()
