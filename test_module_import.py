"""
Quick diagnostic to check if goodq4all module is accessible in conda environments.
"""
import subprocess
import json

envs_to_check = [
    'goodq_zenml',
    'goodq_video_scene_detect', 
    'goodq_face_embed',
    'goodq_image_caption'
]

print("=" * 80)
print("Checking goodq4all module accessibility")
print("=" * 80)

for env in envs_to_check:
    print(f"\n[{env}]")
    try:
        result = subprocess.run(
            ['conda', 'run', '-n', env, 'python', '-c', 
             'import sys; import os; sys.path.insert(0, "L:/goodq4all"); import goodq4all; print("✓ goodq4all module found")'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print(f"  ✓ SUCCESS: {result.stdout.strip()}")
        else:
            print(f"  ✗ FAILED:")
            if result.stderr:
                # Show only the relevant error
                for line in result.stderr.split('\n'):
                    if 'ModuleNotFoundError' in line or 'ImportError' in line or 'Error' in line:
                        print(f"    {line}")
    except Exception as e:
        print(f"  ✗ ERROR: {e}")

print("\n" + "=" * 80)
print("Diagnostic complete")
print("=" * 80)
