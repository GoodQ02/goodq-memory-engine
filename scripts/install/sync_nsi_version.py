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
    nsi_content, count1 = re.subn(
        r'OutFile\s+"[^"]+GoodQ4All_Setup_[^"]+\.exe"', 
        lambda m: f'OutFile "..\\..\\GoodQ4All_Setup_{v}.exe"', 
        nsi_content
    )
    if count1 == 0:
        print("[ERROR] OutFile pattern not found or replaced.")
        import sys
        sys.exit(2)
    
    # Replace MUI_WELCOMEPAGE_TITLE
    nsi_content, count2 = re.subn(
        r'!define\s+MUI_WELCOMEPAGE_TITLE\s+"[^"]+Offline Installer"', 
        f'!define MUI_WELCOMEPAGE_TITLE "Welcome to the GoodQ4All v{v} Offline Installer"', 
        nsi_content
    )
    if count2 == 0:
        print("[ERROR] MUI_WELCOMEPAGE_TITLE pattern not found or replaced.")
        import sys
        sys.exit(2)
    
    # Replace DisplayVersion
    nsi_content, count3 = re.subn(
        r'"DisplayVersion"\s+"[^"]+"', 
        f'"DisplayVersion" "{v}"', 
        nsi_content
    )
    if count3 == 0:
        print("[ERROR] DisplayVersion pattern not found or replaced.")
        import sys
        sys.exit(2)
    
    try:
        with open(nsi_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(nsi_content)
        print("[OK] goodq4all_installer.nsi version synced successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to write nsi file: {e}")
        import sys
        sys.exit(2)
else:
    print("[ERROR] goodq4all_installer.nsi not found.")
    import sys
    sys.exit(2)

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
    print("[ERROR] versioninfo.json not found.")
    import sys
    sys.exit(2)
