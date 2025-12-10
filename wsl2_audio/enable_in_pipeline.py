"""
Script to enable WSL2 audio processing in the pipeline

This updates the pipeline configuration to use WSL2-accelerated
audio steps instead of the Windows-native versions.
"""

import os
import sys
from pathlib import Path
import shutil

def main():
    print("="*80)
    print("  GoodQ4All - Enable WSL2 Audio in Pipeline")
    print("="*80)
    print()
    
    # Get paths
    project_root = Path(__file__).parent.parent
    pipeline_file = project_root / "pipelines" / "ingest_multimodal_conda.py"
    backup_file = pipeline_file.with_suffix(".py.backup_before_wsl2")
    
    if not pipeline_file.exists():
        print(f"ERROR: Pipeline file not found: {pipeline_file}")
        return 1
    
    # Read current pipeline
    with open(pipeline_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already enabled
    if 'step_wsl2' in content:
        print("[SYMBOL] WSL2 audio steps already enabled in pipeline")
        print()
        return 0
    
    # Create backup
    print(f"[1/2] Creating backup: {backup_file.name}")
    shutil.copy2(pipeline_file, backup_file)
    print("[SYMBOL] Backup created")
    print()
    
    # Apply changes
    print("[2/2] Updating pipeline to use WSL2 audio steps...")
    
    # Replace audio_transcribe with step_wsl2 version
    content = content.replace(
        'run_conda_step("goodq_audio_transcribe", "audio_transcribe"',
        'run_conda_step("goodq_audio_transcribe", "audio_transcribe.step_wsl2"'
    )
    
    # Note: We don't have a separate diarize step in the current pipeline
    # It's handled by audio_speaker_merge which we'll also update
    content = content.replace(
        'run_conda_step("goodq_audio_diarize", "audio_diarize"',
        'run_conda_step("goodq_audio_diarize", "audio_diarize.step_wsl2"'
    )
    
    # Write updated pipeline
    with open(pipeline_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("[SYMBOL] Pipeline updated")
    print()
    
    print("="*80)
    print("  WSL2 Audio Enabled!")
    print("="*80)
    print()
    print("The pipeline will now use WSL2-accelerated audio processing.")
    print()
    print("To revert:")
    print(f"  copy {backup_file} {pipeline_file}")
    print()
    print("Next steps:")
    print("  1. Ensure WSL2 service is running:")
    print("     wsl2_audio\\start_wsl2_service.bat")
    print()
    print("  2. Start the pipeline:")
    print("     launch_goodq.bat")
    print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
