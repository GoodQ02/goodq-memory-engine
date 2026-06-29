import json
import os
import re

# Resolve paths
script_dir = os.path.dirname(os.path.abspath(__file__))
version_py_path = os.path.join(script_dir, "..", "..", "goodq_version.py")
nsi_path = os.path.join(script_dir, "goodq4all_installer.nsi")
version_json_path = os.path.join(script_dir, "versioninfo.json")

# 1. Read canonical version
with open(version_py_path, "r", encoding="utf-8") as f:
    version_py = f.read()

version_match = re.search(r'GOODQ_VERSION\s*=\s*\"([^\"]+)\"', version_py)
if not version_match:
    raise ValueError("Could not find GOODQ_VERSION in goodq_version.py")

v = version_match.group(1)
# Handle optional 'v' prefix if present
clean_v = v.lstrip('v')
p = clean_v.split('.')
major = int(p[0])
minor = int(p[1])
patch_part = p[2] if len(p) > 2 else "0"
patch_match = re.match(r'^(\d+)', patch_part)
patch = int(patch_match.group(1)) if patch_match else 0

print(f"Canonical version resolved: {v} (Clean: {clean_v}, Major: {major}, Minor: {minor}, Patch: {patch})")

# 2. Update goodq4all_installer.nsi
if os.path.exists(nsi_path):
    with open(nsi_path, "r", encoding="utf-8") as f:
        nsi_content = f.read()
    
    # Replace OutFile "..\..\GoodQ4All_Setup_*.exe"
    nsi_content = re.sub(
        r'OutFile\s+\"..\\[^\"]+GoodQ4All_Setup_[^\"]+\.exe\"', 
        f'OutFile "..\\..\\GoodQ4All_Setup_{v}.exe"'.replace('\\', '\\\\'), 
        nsi_content
    )
    
    # Replace MUI_WELCOMEPAGE_TITLE
    nsi_content = re.sub(
        r'!define\s+MUI_WELCOMEPAGE_TITLE\s+\"[^\"]+Offline Installer\"', 
        f'!define MUI_WELCOMEPAGE_TITLE "Welcome to the GoodQ4All v{v} Offline Installer"'.replace('\\', '\\\\'), 
        nsi_content
    )
    
    # Replace DisplayVersion
    nsi_content = re.sub(
        r'\"DisplayVersion\"\s+\"[0-9\.]+\"', 
        f'"DisplayVersion" "{v}"'.replace('\\', '\\\\'), 
        nsi_content
    )
    
    with open(nsi_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(nsi_content)
    print("[OK] goodq4all_installer.nsi version synced successfully.")
else:
    print("[WARN] goodq4all_installer.nsi not found.")

# 3. Update versioninfo.json
if os.path.exists(version_json_path):
    with open(version_json_path, "r", encoding="utf-8") as f:
        vi = json.load(f)
    
    vi['FixedFileInfo']['FileVersion'].update({
        'Major': major,
        'Minor': minor,
        'Patch': patch,
        'Build': 0
    })
    vi['FixedFileInfo']['ProductVersion'].update({
        'Major': major,
        'Minor': minor,
        'Patch': patch,
        'Build': 0
    })
    vi['StringFileInfo']['FileVersion'] = f"{v}.0"
    vi['StringFileInfo']['ProductVersion'] = f"{v}.0"
    
    with open(version_json_path, "w", encoding="utf-8") as f:
        json.dump(vi, f, indent=2)
    print("[OK] versioninfo.json version synced successfully.")
else:
    print("[WARN] versioninfo.json not found.")
