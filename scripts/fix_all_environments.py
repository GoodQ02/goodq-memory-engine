"""
Comprehensive fix for all environment naming and path issues
"""
import os
import re
from pathlib import Path

# Environment name mapping
ENV_MAPPING = {
    'audio_diarize': 'goodq_audio_diarize',
    'audio_transcribe': 'goodq_audio_transcribe',
    'emotion_classify': 'goodq_emotion_classify',
    'face_embed': 'goodq_face_embed',
    'text_embed': 'goodq_text_embed',
    'audio_embed': 'goodq_audio_embed',
    'video_scene_detect': 'goodq_video_scene_detect',
    'object_detect': 'goodq_object_detect',
    'object_track': 'goodq_object_track',
    'image_caption': 'goodq_image_caption',
    'ocr': 'goodq_ocr',
    'sentiment': 'goodq_sentiment',
    'agents': 'goodq_agents',
    'llm_chat': 'goodq_llm_chat',
    'tts': 'goodq_tts',
    'zenml': 'goodq_zenml'
}

def fix_file(file_path, dry_run=False):
    """Fix environment names in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes = []
        
        # Fix environment names in various contexts
        for old_name, new_name in ENV_MAPPING.items():
            # Pattern 1: conda activate env_name
            pattern1 = rf'conda activate {old_name}\b'
            if re.search(pattern1, content):
                content = re.sub(pattern1, f'conda activate {new_name}', content)
                changes.append(f"  - Fixed 'conda activate {old_name}' -> '{new_name}'")
            
            # Pattern 2: environment: env_name
            pattern2 = rf"environment:\s*['\"]?{old_name}['\"]?\b"
            if re.search(pattern2, content):
                content = re.sub(pattern2, f"environment: {new_name}", content)
                changes.append(f"  - Fixed 'environment: {old_name}' -> '{new_name}'")
            
            # Pattern 3: env_name in paths
            pattern3 = rf'envs[/\\]{old_name}\b'
            if re.search(pattern3, content):
                content = re.sub(pattern3, f'envs/{new_name}', content)
                changes.append(f"  - Fixed path 'envs/{old_name}' -> 'envs/{new_name}'")
        
        if content != original_content:
            if not dry_run:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            return True, changes
        
        return False, []
        
    except Exception as e:
        return False, [f"  ERROR: {str(e)}"]


def main():
    print("="*80)
    print("  GoodQ4All - Environment Name Fix")
    print("="*80)
    print()
    
    project_root = Path(__file__).parent.parent
    
    # Files to check and fix
    patterns_to_check = [
        'scripts/**/*.py',
        'scripts/**/*.ps1',
        'scripts/**/*.bat',
        'steps/**/*.py',
        'pipelines/**/*.py',
        '*.py',
        '*.bat',
        '*.ps1'
    ]
    
    files_to_fix = []
    for pattern in patterns_to_check:
        files_to_fix.extend(project_root.glob(pattern))
    
    # Remove duplicates
    files_to_fix = list(set(files_to_fix))
    
    print(f"Found {len(files_to_fix)} files to check")
    print()
    
    fixed_count = 0
    
    for file_path in sorted(files_to_fix):
        if file_path.is_file():
            modified, changes = fix_file(file_path, dry_run=False)
            if modified:
                print(f"✓ Fixed: {file_path.relative_to(project_root)}")
                for change in changes:
                    print(change)
                print()
                fixed_count += 1
    
    print("="*80)
    print(f"  Fixed {fixed_count} files")
    print("="*80)
    print()
    
    # Create environment validation report
    print("Validating environments...")
    print()
    
    import subprocess
    result = subprocess.run(['conda', 'env', 'list'], capture_output=True, text=True, shell=True)
    env_list = result.stdout
    
    print("Available environments:")
    for env_name in ENV_MAPPING.values():
        if env_name in env_list:
            print(f"  ✓ {env_name}")
        else:
            print(f"  ✗ {env_name} - MISSING!")
    
    print()
    print("="*80)
    print("  Fix complete!")
    print("="*80)


if __name__ == '__main__':
    main()
