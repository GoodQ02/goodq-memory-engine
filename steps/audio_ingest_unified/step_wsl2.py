"""
Unified WSL2 Audio Processing Step

Uses the upgraded WSL2 audio pipeline to get transcription, diarization,
emotion, embeddings, and features in a single unified JSON output.
"""
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path

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
    
    # Convert Windows path to WSL path
    audio_path_win = Path(audio_path).resolve()
    audio_path_wsl = subprocess.check_output(
        ['wsl', 'wslpath', '-a', str(audio_path_win)],
        text=True
    ).strip()
    
    # Create temporary output directory in WSL
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_win = Path(temp_dir).resolve()
        temp_dir_wsl = subprocess.check_output(
            ['wsl', 'wslpath', '-a', str(temp_dir_win)],
            text=True
        ).strip()
        
        # Call WSL2 audio processing script
        cmd = [
            'wsl', 'bash', '-lc',
            f'source ~/goodq_audio/setup_cuda_env.sh 2>/dev/null && '
            f'cd ~/goodq_audio && '
            f'python3 ~/goodq_audio/scripts/process_audio.py "{audio_path_wsl}" "{temp_dir_wsl}"'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout for long audio
            )
            
            if result.returncode != 0:
                logger.error(f"WSL2 audio processing failed: {result.stderr}")
                return {
                    'status': 'error',
                    'error': f'Processing failed',
                    'stderr': result.stderr[:1000]  # First 1000 chars
                }
            
            # Parse JSON output from stdout
            try:
                audio_result = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse WSL2 audio JSON: {e}")
                logger.error(f"STDOUT: {result.stdout[:500]}")
                return {
                    'status': 'error',
                    'error': 'Invalid JSON output',
                    'raw_output': result.stdout[:500]
                }
            
            # Write compatibility artifacts for legacy code
            if 'transcription' in audio_result:
                transcript_path = audio_path_win.parent / 'transcript.json'
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'text': audio_result.get('transcription', ''),
                        'word_timestamps': audio_result.get('word_timestamps', []),
                        'language': audio_result.get('language', 'en'),
                        'language_probability': audio_result.get('language_probability', 0.0)
                    }, f, indent=2)
            
            if 'diarization' in audio_result:
                diarization_path = audio_path_win.parent / 'diarization.json'
                with open(diarization_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        'speakers': audio_result.get('speakers', []),
                        'speaker_count': audio_result.get('speaker_count', 0),
                        'segments': audio_result.get('diarization', [])
                    }, f, indent=2)
            
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
            
        except subprocess.TimeoutExpired:
            logger.error(f"WSL2 audio processing timed out after 1 hour")
            return {
                'status': 'error',
                'error': 'Processing timeout'
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
