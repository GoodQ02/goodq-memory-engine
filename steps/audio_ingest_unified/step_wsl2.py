"""
Unified WSL2 audio compatibility step.

This legacy step surface now delegates to the canonical unified WSL bridge
instead of invoking ``process_audio.py`` directly.
"""
import json
import logging
import os
from pathlib import Path

from steps.common.atomic_io import atomic_write_json
from scripts.wsl2_audio_bridge import WSL2AudioBridge

logger = logging.getLogger(__name__)


def run(item: dict, config: dict) -> dict:
    """
    Run unified WSL2 audio processing.
    
    Args:
        item: Contains 'audio_path' or audio file to process
        config: Configuration dict
        
    Returns:
        dict: Unified audio results with all modalities
    """
    audio_path = item.get('audio_path')
    if not audio_path or not os.path.exists(audio_path):
        return {
            'status': 'error',
            'error': f'Audio file not found: {audio_path}'
        }

    audio_path_win = Path(audio_path).resolve()
    bridge = WSL2AudioBridge()

    try:
        audio_result = bridge.process_audio(audio_path, timeout=3600)

        if audio_result.get('status') != 'success':
            return {
                'status': 'error',
                'error': audio_result.get('error', 'Processing failed'),
                'stderr': '\n'.join(audio_result.get('stderr_warnings', [])[:20]),
            }

        # Write compatibility artifacts for legacy code
        if 'transcription' in audio_result:
            transcript_path = audio_path_win.parent / 'transcript.json'
            atomic_write_json(
                transcript_path,
                {
                    'text': audio_result.get('transcription', ''),
                    'word_timestamps': audio_result.get('word_timestamps', []),
                    'language': audio_result.get('language', 'en'),
                    'language_probability': audio_result.get('language_probability', 0.0),
                },
            )

        if 'diarization' in audio_result:
            diarization_path = audio_path_win.parent / 'diarization.json'
            atomic_write_json(
                diarization_path,
                {
                    'speakers': audio_result.get('speakers', []),
                    'speaker_count': audio_result.get('speaker_count', 0),
                    'segments': audio_result.get('diarization', []),
                },
            )

        if 'energy' in audio_result or 'duration_seconds' in audio_result:
            features_path = audio_path_win.parent / 'audio_features.json'
            with open(features_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'energy': audio_result.get('energy', 0.0),
                    'duration_seconds': audio_result.get('duration_seconds', 0.0),
                    'sample_rate': audio_result.get('sample_rate', 16000),
                    'channels': audio_result.get('channels', 1)
                }, f, indent=2)

        return {
            'status': 'success',
            **audio_result
        }

    except Exception as e:
        logger.error(f"WSL2 audio processing exception: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


# Self-test
if __name__ == '__main__':
    # Test with a dummy audio file if available
    test_item = {'audio_path': 'test.wav'}
    result = run(test_item, {})
    print(json.dumps(result, indent=2))
