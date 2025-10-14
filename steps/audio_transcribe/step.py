from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import json as _json
import math
import os
import subprocess
import tempfile


_FW_CACHE: Dict[Tuple[str, str, str], Any] = {}  # (model_id, device, compute_type) -> model


def _load_fw_model(model_id: str, device: str, compute_type: str) -> Any:
    key = (model_id, device, compute_type)
    if key in _FW_CACHE:
        return _FW_CACHE[key]
    try:
        from faster_whisper import WhisperModel  # type: ignore

        model = WhisperModel(model_id, device=device, compute_type=compute_type)
    except Exception as e:
        model = None
    _FW_CACHE[key] = model
    return model


def _audio_duration(path: str) -> Optional[float]:
    try:
        import soundfile as sf  # type: ignore

        info = sf.info(path)
        if getattr(info, "duration", None):
            return float(info.duration)
        if getattr(info, "frames", None) and getattr(info, "samplerate", None):
            return float(info.frames) / float(info.samplerate)
    except Exception as e:
        print(f'[ERROR] Exception in step.py line 37: {str(e)}')
        pass
    try:
        import librosa  # type: ignore

        return float(librosa.get_duration(filename=path))
    except Exception as e:
        print(f'[WARN] _audio_duration returning None')
        return None


def _split_range(start: float, end: float, chunk_seconds: float, speaker: Optional[str]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    if not math.isfinite(start) or not math.isfinite(end):
        return segments
    if end <= start:
        return segments
    if chunk_seconds <= 0:
        segments.append({"start": start, "end": end, "speaker": speaker})
        return segments
    cur = start
    while cur < end:
        nxt = min(end, cur + chunk_seconds)
        if nxt - cur <= 0:
            break
        segments.append({"start": cur, "end": nxt, "speaker": speaker})
        cur = nxt
    return segments


def _build_chunks(item: Dict[str, Any], cfg: Dict[str, Any], duration: Optional[float], chunk_seconds: float) -> List[Dict[str, Any]]:
    diarization = item.get("diarization")
    chunks: List[Dict[str, Any]] = []
    if isinstance(diarization, list) and diarization:
        for seg in diarization:
            try:
                start = float(seg.get("start", 0.0) or 0.0)
                end = float(seg.get("end", start) or start)
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 76: {str(e)}')
                continue
            speaker = seg.get("speaker")
            chunks.extend(_split_range(max(0.0, start), max(start, end), chunk_seconds, speaker))
    else:
        if duration is None:
            return []
        chunks.extend(_split_range(0.0, max(0.1, duration), chunk_seconds, None))
    filtered = [c for c in chunks if c["end"] - c["start"] >= 0.2]
    return filtered or chunks


def _slice_to_wav(src_path: str, start: float, end: float, ffmpeg_path: Optional[str]) -> Optional[str]:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_path = tmp.name
    tmp.close()
    duration = max(0.1, end - start)
    try:
        import soundfile as sf  # type: ignore

        with sf.SoundFile(src_path) as fh:
            sr = fh.samplerate
            start_frame = max(0, int(start * sr))
            end_frame = max(start_frame + 1, int((start + duration) * sr))
            fh.seek(start_frame)
            data = fh.read(end_frame - start_frame)
        if data.size == 0:
            raise ValueError("empty slice")
        sf.write(tmp_path, data, sr)
        return tmp_path
    except Exception as e:
        if ffmpeg_path is None:
            try:
                os.remove(tmp_path)
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 111: {str(e)}')
                pass
            print(f'[WARN] _slice_to_wav returning None')
            return None
        try:
            cmd = [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{max(0.0, start):.3f}",
                "-t",
                f"{duration:.3f}",
                "-i",
                src_path,
                tmp_path,
            ]
            subprocess.run(cmd, check=True)
            return tmp_path
        except Exception as e:
            try:
                os.remove(tmp_path)
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 136: {str(e)}')
                pass
            print(f'[WARN] _slice_to_wav returning None')
            return None


def _transcribe_chunk_whisper_cli(chunk_path: str, offset: float, whisper_cli: str, whisper_model: str) -> Optional[Dict[str, Any]]:
    try:
        out_prefix = tempfile.NamedTemporaryFile(delete=False).name
        cmd = [
            whisper_cli,
            "-m",
            whisper_model,
            "-f",
            chunk_path,
            "-oj",
            "-of",
            out_prefix,
            "-pp",
        ]
        subprocess.run(cmd, check=True)
        json_path = out_prefix + ".json"
        txt_path = out_prefix + ".txt"
        transcript = None
        segments: List[Dict[str, Any]] = []
        if os.path.isfile(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                iterable = data if isinstance(data, list) else data.get("segments") or []
                for seg in iterable:
                    start = float(seg.get("start", 0.0) or 0.0) + offset
                    end = float(seg.get("end", 0.0) or 0.0) + offset
                    text = seg.get("text", "") or ""
                    segments.append({"start": start, "end": end, "text": text})
                transcript = " ".join(s.get("text", "").strip() for s in segments if s.get("text")) or None
            except Exception as e:
                segments = []
        if transcript is None and os.path.isfile(txt_path):
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    transcript = f.read().strip() or None
            except Exception as e:
                transcript = None
        return {
            "transcript": transcript,
            "segments": segments,
            "engine": "whisper.cpp",
        }
    except Exception as e:
        print(f'[WARN] _transcribe_chunk_whisper_cli returning None')
        return None
    finally:
        for ext in (".json", ".txt", ".srt", ".tsv"):
            try:
                os.remove(out_prefix + ext)
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 193: {str(e)}')
                pass


def _transcribe_chunk_fw(chunk_path: str, offset: float, model: Any) -> Optional[Dict[str, Any]]:
    if model is None:
        print(f'[WARN] _transcribe_chunk_fw returning None')
        return None
    try:
        # Optimized Whisper settings for better transcription quality
        # - beam_size=5: balanced quality/speed
        # - vad_filter=True: removes silence
        # - vad_parameters: tuned for home videos with background noise
        # - word_timestamps=True: enables word-level timing
        # - condition_on_previous_text=True: better context for long audio
        segments, info = model.transcribe(
            chunk_path,
            beam_size=5,
            vad_filter=True,
            vad_parameters={
                "threshold": 0.4,  # Lower threshold for quiet speech
                "min_speech_duration_ms": 250,  # Catch short utterances
                "max_speech_duration_s": float('inf'),  # Allow long segments
                "min_silence_duration_ms": 500,  # Shorter silence = more captures
                "speech_pad_ms": 400  # Padding around speech
            },
            word_timestamps=True,
            condition_on_previous_text=True,
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],  # Fallback temperatures
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6
        )
        seg_list: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        for seg in segments:
            start = float(getattr(seg, "start", 0.0) or 0.0) + offset
            end = float(getattr(seg, "end", 0.0) or 0.0) + offset
            text = getattr(seg, "text", "") or ""
            seg_list.append({
                "start": start,
                "end": end,
                "text": text,
                "words": [
                    {
                        "start": float(getattr(w, "start", 0.0) or 0.0) + offset,
                        "end": float(getattr(w, "end", 0.0) or 0.0) + offset,
                        "word": getattr(w, "word", "") or "",
                        "prob": float(getattr(w, "probability", 0.0) or 0.0),
                    }
                    for w in (getattr(seg, "words", None) or [])
                ],
            })
            if text:
                text_parts.append(text.strip())
        transcript = " ".join(tp for tp in text_parts if tp) or None
        meta = {
            "transcript": transcript,
            "segments": seg_list,
            "engine": "faster-whisper",
            "language": getattr(info, "language", None),
            "duration": float(getattr(info, "duration", 0.0) or 0.0),
        }
        return meta
    except Exception as e:
        print(f"[WARN] Whisper transcription error: {str(e)}")
        return None


def audio_transcribe(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"transcript": None, "transcript_meta": {"status": "no_file"}}

    cfg_audio = (cfg.get("audio", {}) or {})
    tx_cfg = (cfg_audio.get("transcribe", {}) or {})
    chunk_seconds = float(tx_cfg.get("chunk_seconds") or 10)
    chunk_seconds = max(1.0, chunk_seconds)

    from goodq4all.steps.common.tool_paths import resolve_ffmpeg

    ffmpeg_path = resolve_ffmpeg(cfg) or "ffmpeg"

    duration = _audio_duration(path)
    chunks = _build_chunks(item, cfg, duration, chunk_seconds)
    if not chunks:
        return {"transcript": None, "transcript_meta": {"status": "no_chunks"}}

    tools_cfg = ((cfg.get("config", {}) or {}).get("tools", {}) or {})
    whisper_cli = tools_cfg.get("whisper_cli")
    whisper_model_path = tools_cfg.get("whisper_ggml_model")

    try:
        import torch  # type: ignore

        use_cuda = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
    except Exception as e:
        use_cuda = False
    device = "cuda" if use_cuda else "cpu"
    model_id = str(tx_cfg.get("model") or "medium")
    compute_type = "float16" if device == "cuda" else "int8"

    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault("HF_HOME", os.environ.get("HF_HOME") or "L:/models")
    os.environ.setdefault("TORCH_HOME", os.environ.get("TORCH_HOME") or "L:/models")

    fw_model = _load_fw_model(model_id, device, compute_type)

    if not (whisper_cli and whisper_model_path and os.path.isfile(str(whisper_cli)) and os.path.isfile(str(whisper_model_path))):
        whisper_cli = None

    full_text_parts: List[str] = []
    chunk_reports: List[Dict[str, Any]] = []
    flat_segments: List[Dict[str, Any]] = []

    for chunk in chunks:
        start = float(chunk["start"])
        end = float(chunk["end"])
        speaker = chunk.get("speaker")
        tmp_chunk = _slice_to_wav(path, start, end, ffmpeg_path)
        if not tmp_chunk:
            chunk_reports.append({
                "start": start,
                "end": end,
                "speaker": speaker,
                "status": "error",
                "error": "slice_failed",
            })
            continue
        try:
            result = None
            if whisper_cli:
                result = _transcribe_chunk_whisper_cli(tmp_chunk, start, whisper_cli, whisper_model_path)
            if result is None:
                result = _transcribe_chunk_fw(tmp_chunk, start, fw_model)
            if result is None:
                chunk_reports.append({
                    "start": start,
                    "end": end,
                    "speaker": speaker,
                    "status": "error",
                    "error": "transcribe_failed",
                })
                continue
            transcript = result.get("transcript")
            if isinstance(transcript, str):
                transcript = transcript.strip()
            elif transcript is not None:
                transcript = str(transcript).strip()
            if transcript:
                full_text_parts.append(transcript)
            else:
                transcript = None

            raw_segments = result.get("segments") if isinstance(result, dict) else None
            seg_list: List[Dict[str, Any]] = []
            if isinstance(raw_segments, list):
                for seg in raw_segments:
                    if not isinstance(seg, dict):
                        continue
                    seg_copy = dict(seg)
                    try:
                        seg_copy["start"] = float(seg_copy.get("start", start) or start)
                    except Exception as e:
                        seg_copy["start"] = start
                    try:
                        seg_copy["end"] = float(seg_copy.get("end", end) or end)
                    except Exception as e:
                        seg_copy["end"] = end
                    text_val = seg_copy.get("text")
                    seg_copy["text"] = str(text_val).strip() if text_val is not None else (transcript or "")
                    if not seg_copy["text"]:
                        seg_copy["text"] = transcript or ""
                    if seg_copy["text"]:
                        seg_copy["text"] = seg_copy["text"].strip()
                    speaker_val = seg_copy.get("speaker") or speaker
                    if speaker_val is not None:
                        seg_copy["speaker"] = speaker_val
                    words = seg_copy.get("words")
                    if isinstance(words, list):
                        norm_words = []
                        for w in words:
                            if not isinstance(w, dict):
                                continue
                            w_copy = dict(w)
                            try:
                                w_copy["start"] = float(w_copy.get("start", seg_copy["start"]) or seg_copy["start"])
                            except Exception as e:
                                w_copy["start"] = seg_copy["start"]
                            try:
                                w_copy["end"] = float(w_copy.get("end", seg_copy["end"]) or seg_copy["end"])
                            except Exception as e:
                                w_copy["end"] = seg_copy["end"]
                            if "word" in w_copy and w_copy["word"] is not None:
                                w_copy["word"] = str(w_copy["word"])
                            norm_words.append(w_copy)
                        seg_copy["words"] = norm_words
                    seg_list.append(seg_copy)
                flat_segments.extend(seg_list)
            elif transcript:
                seg_list = [{
                    "start": start,
                    "end": end,
                    "text": transcript,
                    "speaker": speaker,
                }]
                flat_segments.extend(seg_list)

            chunk_entry = {
                "start": start,
                "end": end,
                "speaker": speaker,
                "status": "ok" if transcript else "failed",
                "engine": result.get("engine"),
                "text": transcript,
                "segments": seg_list,
            }
            chunk_reports.append(chunk_entry)
        finally:
            try:
                os.remove(tmp_chunk)
            except Exception as e:
                print(f'[ERROR] Exception in step.py line 415: {str(e)}')
                pass

    normalized_segments: List[Dict[str, Any]] = []
    seen_segments = set()
    for seg in flat_segments:
        if not isinstance(seg, dict):
            continue
        try:
            start_val = float(seg.get("start", 0.0) or 0.0)
        except Exception as e:
            start_val = 0.0
        try:
            end_val = float(seg.get("end", start_val) or start_val)
        except Exception as e:
            end_val = start_val
        text_val = seg.get("text")
        text_str = str(text_val).strip() if text_val is not None else ""
        speaker_val = seg.get("speaker")
        key = (round(start_val, 3), round(end_val, 3), text_str, str(speaker_val) if speaker_val is not None else "")
        if key in seen_segments:
            continue
        seen_segments.add(key)
        seg_obj: Dict[str, Any] = {
            "start": start_val,
            "end": end_val,
            "text": text_str,
        }
        if speaker_val is not None:
            seg_obj["speaker"] = speaker_val
        words_val = seg.get("words")
        if isinstance(words_val, list) and words_val:
            seg_obj["words"] = words_val
        normalized_segments.append(seg_obj)
    if not normalized_segments:
        for report in chunk_reports:
            text_val = report.get("text")
            if not text_val:
                continue
            try:
                start_val = float(report.get("start") or 0.0)
            except Exception as e:
                start_val = 0.0
            try:
                end_val = float(report.get("end") or start_val)
            except Exception as e:
                end_val = start_val
            seg_obj = {
                "start": start_val,
                "end": end_val,
                "text": str(text_val).strip(),
            }
            speaker_val = report.get("speaker")
            if speaker_val is not None:
                seg_obj["speaker"] = speaker_val
            normalized_segments.append(seg_obj)
    normalized_segments.sort(key=lambda s: float(s.get("start") or 0.0))
    flat_segments = normalized_segments

    full_text = " ".join(part.strip() for part in full_text_parts if part)
    status = "ok" if full_text else "failed"
    if all(c.get("status") == "error" for c in chunk_reports):
        status = "error"
    elif all(c.get("status") in ("failed", "error", "empty") for c in chunk_reports):
        status = "failed"
    elif all(c.get("status") in ("failed", "error", "empty") for c in chunk_reports):
        status = "failed"

    meta = {
        "status": status,
        "engine": "hybrid_whisper",
        "chunks": chunk_reports,
        "chunk_seconds": chunk_seconds,
        "duration": duration,
        "used_cli": bool(whisper_cli),
        "device": device,
    }
    if flat_segments:
        meta["segments"] = flat_segments
        meta["segment_count"] = len(flat_segments)
        speakers = sorted({str(seg.get("speaker")) for seg in flat_segments if seg.get("speaker")})
        if speakers:
            meta["speakers"] = speakers
    return {"transcript": full_text or None, "transcript_meta": meta}



