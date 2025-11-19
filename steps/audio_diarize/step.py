from __future__ import annotations
# GPU Configuration - Auto-configured on import
from goodq4all.steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats
# Audio-specific GPU optimization
from goodq4all.steps.common.audio_gpu_optimizer import get_audio_gpu_optimizer


from typing import Any, Dict, List, Optional, Tuple
import os
import tempfile
import subprocess
import math
import time


_PIPELINES: Dict[Tuple[str, str], Any] = {}
_SPEAKER_EMBEDDINGS: Dict[str, Any] = {}  # Cache for speaker embeddings
_MODEL_WARMED_UP: bool = False  # Track if model has been warmed up


def _resolve_device() -> str:
    try:
        import torch  # type: ignore
        return "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
    except Exception as e:
        return "cpu"


def _load_pipeline(model_id: str, device: str, auth_token: Optional[str], duration_minutes: float = None):
    """Load and cache PyAnnote pipeline with GPU optimization and warmup"""
    global _MODEL_WARMED_UP
    
    key = (model_id, device)
    if key in _PIPELINES:
        return _PIPELINES[key]
    
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except Exception as e:
        _PIPELINES[key] = None
        print(f'[WARN] _load_pipeline returning None - PyAnnote not available')
        return None
    
    try:
        # Initialize audio GPU optimizer
        optimizer = get_audio_gpu_optimizer()
        
        # Configure GPU for diarization workload
        if device == "cuda":
            gpu_config = optimizer.configure_for_diarization(duration_minutes)
            print(f"[DIARIZE] GPU configured: {gpu_config.memory_fraction*100:.0f}% VRAM allocation")
            
            # Warmup GPU kernels
            if not _MODEL_WARMED_UP:
                optimizer.warmup_gpu()
        
        print(f"[DIARIZE] Loading model {model_id} on {device}...")
        start_load = time.time()
        
        pipeline = Pipeline.from_pretrained(model_id, use_auth_token=auth_token)
        
        if device == "cuda":
            try:
                pipeline.to(torch.device("cuda"))
                load_time = time.time() - start_load
                print(f"[DIARIZE] Model loaded on GPU in {load_time:.1f}s")
                optimizer.print_memory_stats()
            except Exception as e:
                print(f'[ERROR] Failed to move model to GPU: {str(e)}')
                device = "cpu"
                pass
        else:
            load_time = time.time() - start_load
            print(f"[DIARIZE] Model loaded on CPU in {load_time:.1f}s")
        
        # Warmup: Run on small dummy audio to initialize CUDA kernels
        if device == "cuda" and not _MODEL_WARMED_UP:
            try:
                print("[DIARIZE] Warming up model (first run)...")
                import numpy as np
                import soundfile as sf
                import tempfile
                
                warmup_start = time.time()
                
                # Create 1-second silent audio
                warmup_audio = np.zeros((16000,), dtype=np.float32)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                sf.write(tmp.name, warmup_audio, 16000)
                tmp.close()
                
                try:
                    _ = pipeline(tmp.name)
                    warmup_time = time.time() - warmup_start
                    print(f"[DIARIZE] Model warmup complete in {warmup_time:.1f}s")
                    _MODEL_WARMED_UP = True
                except:
                    pass
                
                try:
                    os.remove(tmp.name)
                except:
                    pass
            except Exception as warmup_exc:
                print(f"[WARN] Model warmup failed: {str(warmup_exc)}")
        
        _PIPELINES[key] = pipeline
        
    except Exception as e:
        print(f"[ERROR] Failed to load pipeline: {str(e)}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        _PIPELINES[key] = None
    
    return _PIPELINES[key]


def _get_audio_duration(path: str) -> Optional[float]:
    """Get audio duration using soundfile or librosa"""
    try:
        import soundfile as sf
        info = sf.info(path)
        if getattr(info, "duration", None):
            return float(info.duration)
        if getattr(info, "frames", None) and getattr(info, "samplerate", None):
            return float(info.frames) / float(info.samplerate)
    except:
        pass
    
    try:
        import librosa
        return float(librosa.get_duration(filename=path))
    except:
        pass
    
    return None


def _extract_audio_chunk(src_path: str, start: float, duration: float, ffmpeg_path: str) -> Optional[str]:
    """Extract a chunk of audio to temp file"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_path = tmp.name
    tmp.close()
    
    try:
        cmd = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-ss", f"{max(0.0, start):.3f}",
            "-t", f"{duration:.3f}",
            "-i", src_path,
            "-ac", "1",  # Mono for diarization
            "-ar", "16000",  # 16kHz sample rate
            tmp_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        if not os.path.isfile(tmp_path) or os.path.getsize(tmp_path) == 0:
            raise ValueError("Empty chunk file")
            
        return tmp_path
    except Exception as e:
        print(f"[ERROR] Failed to extract audio chunk: {str(e)}")
        try:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
        except:
            pass
        return None


def _merge_speaker_segments(chunks: List[Dict[str, Any]], threshold: float = 0.5) -> List[Dict[str, Any]]:
    """
    Merge speaker segments from multiple chunks, resolving speaker IDs across chunks.
    Uses simple overlap and proximity heuristics.
    """
    if not chunks:
        return []
    
    # Collect all segments with chunk info
    all_segments = []
    for chunk_idx, chunk_data in enumerate(chunks):
        for seg in chunk_data.get("segments", []):
            seg_copy = dict(seg)
            seg_copy["chunk_idx"] = chunk_idx
            all_segments.append(seg_copy)
    
    # Sort by time
    all_segments.sort(key=lambda s: s.get("start", 0.0))
    
    if not all_segments:
        return []
    
    # Build speaker mapping across chunks
    # This is simplified - just renumber speakers sequentially
    speaker_map = {}
    next_speaker_id = 0
    
    merged = []
    for seg in all_segments:
        original_speaker = seg.get("speaker", "")
        chunk_idx = seg.get("chunk_idx", 0)
        key = f"{chunk_idx}_{original_speaker}"
        
        # Check if we've seen this speaker in this chunk
        if key not in speaker_map:
            # Check if there's a nearby speaker we can merge with
            found_match = False
            for prev_seg in reversed(merged[-5:]):  # Check last 5 segments
                if abs(prev_seg["end"] - seg["start"]) < 10.0:  # Within 10 seconds
                    speaker_map[key] = prev_seg["speaker"]
                    found_match = True
                    break
            
            if not found_match:
                speaker_map[key] = f"SPEAKER_{next_speaker_id:02d}"
                next_speaker_id += 1
        
        merged.append({
            "start": seg["start"],
            "end": seg["end"],
            "speaker": speaker_map[key],
        })
    
    return merged


def _format_segments(diarization, offset: float = 0.0, overlap_regions=None) -> List[Dict[str, Any]]:
    """Format diarization segments with time offset and overlap flags"""
    segments: List[Dict[str, Any]] = []
    if diarization is None:
        return segments
    try:
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            start = float(getattr(turn, "start", 0.0) or 0.0) + offset
            end = float(getattr(turn, "end", 0.0) or 0.0) + offset
            
            # Check if segment has overlapped speech
            has_overlap = False
            if overlap_regions:
                for overlap in overlap_regions:
                    overlap_start = float(getattr(overlap, "start", 0.0) or 0.0)
                    overlap_end = float(getattr(overlap, "end", 0.0) or 0.0)
                    # Check if overlap intersects with this segment
                    if (overlap_start <= start < overlap_end or 
                        overlap_start < end <= overlap_end or
                        (start <= overlap_start and overlap_end <= end)):
                        has_overlap = True
                        break
            
            segments.append({
                "start": max(0.0, start),
                "end": max(start, end),
                "speaker": str(speaker),
                "has_overlap": has_overlap,  # NEW: Flag for overlapped speech
            })
    except Exception as e:
        return []
    segments.sort(key=lambda s: s.get("start", 0.0))
    return segments


def audio_diarize(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Speaker diarization via PyAnnote pipeline with VAD preprocessing and GPU optimization.
    
    Uses Silero VAD to filter out silence and non-speech content before diarization.
    This dramatically reduces processing time and improves accuracy.
    
    For long audio files (>10 minutes), splits into chunks to prevent hanging.
    Merges speaker labels across chunks for consistent speaker IDs.
    Optimizes GPU usage based on file duration and available VRAM.
    """
    import time
    
    # Import progress tracker
    try:
        from steps.common.progress_tracker import get_tracker
        tracker = get_tracker()
    except:
        tracker = None
    
    # Initialize GPU optimizer
    optimizer = get_audio_gpu_optimizer()
    
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"diarization": None, "diarize_meta": {"status": "no_file"}}

    # Check if diarization is enabled
    cfg_audio = (cfg.get("audio", {}) or {})
    dz_cfg = (cfg_audio.get("diarization", {}) or {})
    
    if not dz_cfg.get("enabled", True):
        print("[INFO] Diarization disabled in config, skipping")
        return {"diarization": None, "diarize_meta": {"status": "disabled"}}
    
    token_env = str(dz_cfg.get("token_env") or "PYANNOTE_TOKEN")
    model_id = str(dz_cfg.get("model") or "pyannote/speaker-diarization@2.1")

    auth_token = os.getenv(token_env) or os.getenv("PYANNOTE_AUDIO_AUTH") or os.getenv("HF_TOKEN")
    if not auth_token:
        print("[WARN] No PyAnnote auth token found, skipping diarization")
        return {"diarization": None, "diarize_meta": {"status": "unavailable", "engine": "pyannote", "reason": "no_auth"}}

    device = _resolve_device()
    
    # VAD Configuration
    vad_enabled = dz_cfg.get("vad_enabled", True)  # Enable by default
    vad_threshold = float(dz_cfg.get("vad_threshold", 0.5))  # 0.5 is balanced, 0.6-0.7 for stricter
    vad_min_speech_ms = int(dz_cfg.get("vad_min_speech_ms", 400))
    vad_min_silence_ms = int(dz_cfg.get("vad_min_silence_ms", 200))
    vad_merge_gap = float(dz_cfg.get("vad_merge_gap_seconds", 1.0))
    
    # Get FFmpeg path
    ffmpeg_path = None
    try:
        from steps.common.tool_paths import resolve_ffmpeg
        ffmpeg_path = resolve_ffmpeg(cfg)
    except:
        pass
    
    if not ffmpeg_path:
        # Try config.tools.ffmpeg
        tools_cfg = ((cfg.get("config", {}) or {}).get("tools", {}) or {})
        ffmpeg_path = tools_cfg.get("ffmpeg")
    
    if not ffmpeg_path:
        # Fallback to known location
        fallback_path = "L:/Tools/ffmpeg/bin/ffmpeg.exe"
        if os.path.exists(fallback_path):
            ffmpeg_path = fallback_path
        else:
            ffmpeg_path = "ffmpeg"  # Hope it's in PATH
    
    print(f"[DIARIZE] Using ffmpeg: {ffmpeg_path}")

    try:
        # Check if input is a video file - if so, extract audio first
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm'}
        file_ext = os.path.splitext(path)[1].lower()
        audio_path = path
        temp_audio_file = None
        
        if file_ext in video_extensions:
            print(f"[DIARIZE] Input is video file, extracting audio track...")
            # Create temp audio file
            temp_audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", prefix="goodq_audio_")
            temp_audio_path = temp_audio_file.name
            temp_audio_file.close()
            
            # Extract audio with ffmpeg
            extract_cmd = [
                ffmpeg_path, '-i', path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # PCM 16-bit
                '-ar', '16000',  # 16kHz for diarization
                '-ac', '1',  # Mono
                temp_audio_path, '-y'  # Overwrite
            ]
            
            try:
                result = subprocess.run(extract_cmd, capture_output=True, text=True, timeout=300)
                if result.returncode != 0:
                    print(f"[ERROR] Audio extraction failed: {result.stderr}")
                    return {"diarization": None, "diarize_meta": {"status": "extraction_failed"}}
                
                if not os.path.exists(temp_audio_path) or os.path.getsize(temp_audio_path) == 0:
                    print(f"[ERROR] Audio extraction produced empty file")
                    return {"diarization": None, "diarize_meta": {"status": "extraction_failed"}}
                
                audio_path = temp_audio_path
                print(f"[DIARIZE] ✓ Audio extracted to: {os.path.basename(audio_path)}")
            except Exception as e:
                print(f"[ERROR] Audio extraction exception: {str(e)}")
                if temp_audio_file and os.path.exists(temp_audio_path):
                    try:
                        os.remove(temp_audio_path)
                    except:
                        pass
                return {"diarization": None, "diarize_meta": {"status": "extraction_failed"}}
        
        # Get audio duration (from extracted audio or original audio file)
        duration = _get_audio_duration(audio_path)
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        duration_minutes = (duration / 60.0) if duration else None
        
        # VAD Preprocessing (if enabled)
        vad_audio_path = None
        vad_segments = None
        vad_savings = None
        
        if vad_enabled:
            try:
                from steps.audio_diarize.vad_preprocessor import preprocess_audio_with_vad, calculate_time_savings
                
                print("[DIARIZE] Running VAD preprocessing to filter silence and noise...")
                if tracker:
                    tracker.update_step("audio_diarize", 3, {"details": "Running voice activity detection..."})
                
                vad_start = time.time()
                vad_audio_path, vad_segments = preprocess_audio_with_vad(
                    audio_path,  # Use extracted audio path
                    threshold=vad_threshold,
                    min_speech_duration_ms=vad_min_speech_ms,
                    min_silence_duration_ms=vad_min_silence_ms,
                    merge_gap_seconds=vad_merge_gap,
                    extract_to_file=True,
                )
                vad_elapsed = time.time() - vad_start
                
                if vad_audio_path and vad_segments:
                    # Calculate time savings
                    vad_savings = calculate_time_savings(duration, vad_segments)
                    print(f"[DIARIZE] VAD complete in {vad_elapsed:.1f}s")
                    print(f"[DIARIZE] Reduced audio from {duration/60:.1f}min to {vad_savings['speech_duration']/60:.1f}min ({vad_savings['reduction_percent']:.1f}% reduction)")
                    print(f"[DIARIZE] Estimated time savings: {vad_savings['time_saved']/60*1.5:.1f}-{vad_savings['time_saved']/60*2:.1f} minutes")
                    
                    # Use VAD-filtered audio for diarization
                    audio_path = vad_audio_path  # Update audio_path
                    duration = vad_savings['speech_duration']
                    duration_minutes = duration / 60.0
                else:
                    print("[DIARIZE] VAD preprocessing did not produce output, using extracted audio")
                    
            except Exception as vad_exc:
                print(f"[DIARIZE] WARN: VAD preprocessing failed: {str(vad_exc)}")
                print("[DIARIZE] Continuing with original audio (no VAD filtering)")
                import traceback
                print(traceback.format_exc())
        
        # OSD: Overlapped Speech Detection (NEW!)
        overlap_regions = None
        osd_enabled = dz_cfg.get("osd_enabled", True)
        
        if osd_enabled and device == "cuda":  # OSD works best on GPU
            try:
                from pyannote.audio.pipelines import OverlappedSpeechDetection
                
                print("[DIARIZE] Running overlapped speech detection...")
                if tracker:
                    tracker.update_step("audio_diarize", 4, {"details": "Detecting overlapped speech..."})
                
                osd_start = time.time()
                
                # Initialize OSD pipeline
                osd = OverlappedSpeechDetection(segmentation="pyannote/segmentation-3.0")
                osd_pipeline = osd.instantiate({
                    "onset": float(dz_cfg.get("osd_onset", 0.5)),
                    "offset": float(dz_cfg.get("osd_offset", 0.5)),
                    "min_duration_on": float(dz_cfg.get("osd_min_duration", 0.1)),
                    "min_duration_off": 0.1,
                })
                
                # Move to GPU
                import torch
                osd_pipeline.to(torch.device("cuda"))
                
                # Detect overlaps
                overlap_regions = osd_pipeline(audio_path)
                
                # Convert to list for easier processing
                overlap_list = list(overlap_regions)
                osd_elapsed = time.time() - osd_start
                
                total_overlap_duration = sum(
                    (overlap.end - overlap.start) for overlap in overlap_list
                )
                
                print(f"[DIARIZE] OSD complete in {osd_elapsed:.1f}s")
                print(f"[DIARIZE] Detected {len(overlap_list)} overlapped speech regions ({total_overlap_duration:.1f}s total)")
                
                if len(overlap_list) > 0:
                    print(f"[DIARIZE] This indicates multi-speaker conversation with cross-talk")
                
            except ImportError as import_exc:
                print(f"[DIARIZE] WARN: OSD not available - pyannote.audio may need update: {str(import_exc)}")
                overlap_regions = None
            except Exception as osd_exc:
                print(f"[DIARIZE] WARN: OSD failed: {str(osd_exc)}")
                print("[DIARIZE] Continuing without overlap detection")
                import traceback
                print(traceback.format_exc())
                overlap_regions = None
        elif osd_enabled and device == "cpu":
            print("[DIARIZE] OSD skipped (requires GPU for performance)")
        
        # Load pipeline with duration hint for optimal GPU configuration
        pipeline = _load_pipeline(model_id, device, auth_token, duration_minutes)
        if pipeline is None:
            print("[WARN] Failed to load PyAnnote pipeline, skipping diarization")
            return {"diarization": None, "diarize_meta": {"status": "unavailable", "engine": "pyannote"}}
        
        # Dynamic chunking strategy based on file duration
        # Shorter chunks for very long files reduce memory pressure
        # Longer chunks for medium files reduce merge overhead
        if duration:
            if duration < 20 * 60:  # Less than 20 minutes
                chunk_size_minutes = 20.0  # Process whole file
            elif duration < 40 * 60:  # 20-40 minutes
                chunk_size_minutes = 20.0  # 20-minute chunks
            else:  # Over 40 minutes
                chunk_size_minutes = 15.0  # 15-minute chunks for memory safety
        else:
            chunk_size_minutes = float(dz_cfg.get("chunk_size_minutes", 15.0))
        
        chunk_size_seconds = chunk_size_minutes * 60.0
        use_chunking = duration and duration > chunk_size_seconds
        
        if use_chunking:
            num_chunks = int(math.ceil(duration / chunk_size_seconds))
            print(f"[DIARIZE] Long audio ({duration/60:.1f}min) - splitting into {num_chunks} chunks of {chunk_size_minutes:.0f}min each")
            print(f"[DIARIZE] Estimated processing time: {(duration/60)*1.5:.1f}-{(duration/60)*2:.1f} minutes")
        else:
            num_chunks = 1
            print(f"[DIARIZE] Starting diarization for {os.path.basename(path)} ({file_size_mb:.1f}MB, {duration/60 if duration else 0:.1f}min) on {device}")
            if duration:
                print(f"[DIARIZE] Estimated processing time: {(duration/60)*1.5:.1f}-{(duration/60)*2:.1f} minutes")
        
        # Update progress
        if tracker:
            tracker.update_step("audio_diarize", 5, {
                "details": f"Analyzing speakers ({file_size_mb:.1f}MB, {num_chunks if use_chunking else 1} chunks)"
            })
        
        # Print GPU stats before processing
        if device == "cuda":
            optimizer.print_memory_stats()
        
        start_time = time.time()
        
        if use_chunking:
            # Process in chunks
            chunk_results = []
            temp_files = []
            
            for chunk_idx in range(num_chunks):
                chunk_start = chunk_idx * chunk_size_seconds
                chunk_duration = min(chunk_size_seconds, duration - chunk_start)
                chunk_end = chunk_start + chunk_duration
                
                print(f"[DIARIZE] Chunk {chunk_idx+1}/{num_chunks}: {chunk_start/60:.1f}-{chunk_end/60:.1f}min ({chunk_duration/60:.1f}min)")
                
                # Update progress with sub-progress
                if tracker:
                    sub_progress = (chunk_idx / num_chunks) * 100  # 0-100% within this step
                    tracker.update_step("audio_diarize", sub_progress, {
                        "details": f"Processing chunk {chunk_idx+1}/{num_chunks} ({chunk_start/60:.1f}-{chunk_end/60:.1f}min)"
                    })
                
                # Extract chunk from audio_path (which may be extracted or VAD-filtered audio)
                chunk_path = _extract_audio_chunk(audio_path, chunk_start, chunk_duration, ffmpeg_path)
                if not chunk_path:
                    print(f"[WARN] Failed to extract chunk {chunk_idx+1}, skipping")
                    continue
                
                temp_files.append(chunk_path)
                
                try:
                    # Clear GPU cache between chunks
                    if device == "cuda":
                        optimizer.clear_cache()
                    
                    # Run diarization on chunk with timing
                    chunk_start_time = time.time()
                    chunk_diarization = pipeline(chunk_path)
                    chunk_elapsed = time.time() - chunk_start_time
                    chunk_segments = _format_segments(chunk_diarization, offset=chunk_start, overlap_regions=overlap_regions)
                    
                    chunk_results.append({
                        "chunk_idx": chunk_idx,
                        "start": chunk_start,
                        "duration": chunk_duration,
                        "segments": chunk_segments,
                        "processing_time": chunk_elapsed,
                    })
                    
                    # Calculate speed metrics
                    realtime_factor = chunk_duration / chunk_elapsed if chunk_elapsed > 0 else 0
                    print(f"[DIARIZE] Chunk {chunk_idx+1} complete: {len(chunk_segments)} segments in {chunk_elapsed:.1f}s ({realtime_factor:.2f}x realtime)")
                    
                    # Record performance for optimization
                    if device == "cuda":
                        optimizer.record_performance("diarize_chunk", chunk_elapsed, chunk_duration)
                    
                except Exception as chunk_exc:
                    print(f"[WARN] Chunk {chunk_idx+1} failed: {str(chunk_exc)}")
                    import traceback
                    print(f"[WARN] Traceback: {traceback.format_exc()}")
                    continue
            
            # Clean up temp files
            for tmp in temp_files:
                try:
                    if os.path.isfile(tmp):
                        os.remove(tmp)
                except:
                    pass
            
            # Clean up VAD temp file if it exists
            if vad_audio_path and os.path.isfile(vad_audio_path):
                try:
                    os.remove(vad_audio_path)
                except:
                    pass
            
            # Merge chunks
            if tracker:
                tracker.update_step("audio_diarize", 90, {"details": f"Merging {len(chunk_results)} chunks..."})
            
            print(f"[DIARIZE] Merging {len(chunk_results)} chunks...")
            merge_start = time.time()
            segments = _merge_speaker_segments(chunk_results)
            merge_elapsed = time.time() - merge_start
            print(f"[DIARIZE] Merge complete in {merge_elapsed:.1f}s")
            
        else:
            # Process entire file (audio_path may be extracted or VAD-filtered)
            diarization = pipeline(audio_path)
            
            # Resegmentation: Refine boundaries (NEW!)
            if device == "cuda" and dz_cfg.get("resegment_enabled", True):
                try:
                    from pyannote.audio.pipelines import Resegmentation
                    
                    print("[DIARIZE] Refining speaker boundaries with resegmentation...")
                    reseg_start = time.time()
                    
                    reseg = Resegmentation(
                        segmentation="pyannote/segmentation-3.0",
                        device=torch.device("cuda")
                    )
                    diarization = reseg(audio_path, diarization)
                    
                    reseg_elapsed = time.time() - reseg_start
                    print(f"[DIARIZE] Resegmentation complete in {reseg_elapsed:.1f}s")
                    
                except ImportError as import_exc:
                    print(f"[DIARIZE] WARN: Resegmentation not available: {str(import_exc)}")
                except Exception as reseg_exc:
                    print(f"[DIARIZE] WARN: Resegmentation failed: {str(reseg_exc)}, using original")
            
            segments = _format_segments(diarization, overlap_regions=overlap_regions)
        
        elapsed = time.time() - start_time
        
        # Record performance for optimization
        if device == "cuda" and duration:
            optimizer.record_performance("diarize_full", elapsed, duration)
        
        # Performance metrics
        realtime_factor = (duration / elapsed) if (duration and elapsed > 0) else 0
        avg_speed = f"{realtime_factor:.2f}x realtime" if realtime_factor > 0 else "N/A"
        
        print(f"[DIARIZE] ✓ Completed in {elapsed:.1f}s ({elapsed/60:.1f}min) - {avg_speed}")
        
        # Print final GPU stats
        if device == "cuda":
            optimizer.print_memory_stats()
            
            # Get optimization suggestions
            suggestions = optimizer.optimize_for_next_run()
            if suggestions.get("recommendation"):
                print(f"[DIARIZE] GPU optimization suggestion: {suggestions['recommendation']}")
        
        if not segments:
            print("[DIARIZE] No speakers detected")
            if tracker:
                tracker.add_warning("No speakers detected in audio", "audio_diarize")
            return {"diarization": None, "diarize_meta": {"status": "empty", "engine": "pyannote"}}
        
        print(f"[DIARIZE] Found {len(segments)} speaker segments")
        
        # Count unique speakers
        unique_speakers = len(set(seg.get("speaker", "") for seg in segments))
        print(f"[DIARIZE] Detected {unique_speakers} unique speakers")
        
        # Calculate average segment duration
        if segments:
            avg_segment_duration = sum(seg.get("end", 0) - seg.get("start", 0) for seg in segments) / len(segments)
            print(f"[DIARIZE] Average segment duration: {avg_segment_duration:.1f}s")
        
        # Update progress with results
        if tracker:
            tracker.complete_step("audio_diarize", {
                "segment_count": len(segments),
                "speaker_count": unique_speakers,
                "processing_time": f"{elapsed:.1f}s ({elapsed/60:.1f}min)",
                "speed": avg_speed,
                "chunked": use_chunking,
                "device": device,
            })
        
        # Get GPU memory stats for metadata
        gpu_stats = optimizer.get_memory_stats() if device == "cuda" else {}
        
        # Count overlapped segments (NEW)
        overlap_count = sum(1 for seg in segments if seg.get("has_overlap", False))
        total_overlap_duration = sum(
            (seg["end"] - seg["start"]) for seg in segments if seg.get("has_overlap", False)
        )
        
        if overlap_count > 0:
            print(f"[DIARIZE] ⚠️  {overlap_count} segments have overlapped speech ({total_overlap_duration:.1f}s total)")
        
        meta = {
            "status": "ok",
            "engine": "pyannote",
            "model": model_id,
            "device": device,
            "segment_count": len(segments),
            "speaker_count": unique_speakers,
            "processing_time": elapsed,
            "realtime_factor": realtime_factor,
            "chunked": use_chunking,
            "chunk_count": num_chunks if use_chunking else 1,
            "chunk_size_minutes": chunk_size_minutes if use_chunking else None,
            "gpu_memory_peak_gb": gpu_stats.get("allocated_gb"),
            "gpu_utilization": gpu_stats.get("utilization"),
            "vad_enabled": vad_enabled and vad_savings is not None,
            "vad_savings": vad_savings,
            "osd_enabled": osd_enabled,  # NEW
            "overlap_detected": overlap_count > 0,  # NEW  
            "overlap_segment_count": overlap_count,  # NEW
            "overlap_duration_seconds": round(total_overlap_duration, 2),  # NEW
            "resegment_enabled": dz_cfg.get("resegment_enabled", True),  # NEW
        }
        # Cleanup temp audio file if we created one
        if temp_audio_file and os.path.exists(temp_audio_file.name):
            try:
                os.remove(temp_audio_file.name)
                print(f"[DIARIZE] Cleaned up temp audio file")
            except:
                pass
        
        return {"diarization": segments, "diarize_meta": meta}
        
    except Exception as exc:
        import traceback
        print(f"[ERROR] Diarization failed: {type(exc).__name__}: {str(exc)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        
        # Cleanup temp audio file on error
        if temp_audio_file and os.path.exists(temp_audio_file.name):
            try:
                os.remove(temp_audio_file.name)
            except:
                pass
        
        if tracker:
            tracker.add_error(f"Diarization failed: {str(exc)}", "audio_diarize")
        return {"diarization": None, "diarize_meta": {"status": "error", "engine": "pyannote", "error": str(exc)}}
