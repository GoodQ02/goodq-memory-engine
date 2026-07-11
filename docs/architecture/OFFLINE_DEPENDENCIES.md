<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_RELEASE_REFERENCE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Offline Dependencies & Wheelhouse Checksums

This document lists the official SHA256 checksums and verification commands for the offline installation wheelhouses, host tools packages, and environment manifests required for air-gapped installation of GoodQ4All.

---

## 1. Offline Release Assets

### Host Tools Package (Windows x64)
* **File Name**: `goodq4all-0.1.1-host-tools-windows-x86_64.zip`
* **Relative Path**: `scratch/release_assets/goodq4all-0.1.1-host-tools-windows-x86_64.zip`
* **Size**: 741,956,588 bytes (~707 MB)
* **SHA256 Checksum**: `fb764714af96e3e8dcd64af0603134ad60fd501b3e2dd70130efea897f0fe603`
* **Contents**: Bundled binaries for local service runtimes, including:
  - `ffmpeg.exe` (Windows transcoding utility)
  - `ffprobe.exe` (Media inspector)
  - Qdrant Vector database binaries

---

## 2. Pip Wheelhouse Manifests

The offline pip wheelhouse dependencies are tracked by three local manifest JSON files in the offline bundle.

| Manifest File | Relative Path | Size (Bytes) | SHA256 Checksum |
| :--- | :--- | :--- | :--- |
| **Main Manifest** | `scratch/offline_bundle/current/manifests/windows_pip_wheelhouse_manifest.json` | 1,122 | `9a5cd383642fe246a8c6a57c220c09cefa2a6eb591fd2e73d442005b97d4551c` |
| **Files List** | `scratch/offline_bundle/current/manifests/windows_pip_wheelhouse_files.json` | 27,821 | `7a2ddcb86366ca95a3ce15aa6899532508e94339d384ab3fc687d0598c0e91fe` |
| **No-Index Verification** | `scratch/offline_bundle/current/manifests/pip_wheelhouse_no_index_verify.json` | 20,238 | `d182ddc56c5e9c4c0f68a382e686c2b296c61ad3a605ca766f5729febd92bd30` |

---

## 3. Local Verification Commands

To verify that your offline download package matches the canonical build output, run the corresponding command for your shell:

### PowerShell (Windows Host)
```powershell
# Verify Host Tools Zip
Get-FileHash -Algorithm SHA256 "%GOODQ_REPO_ROOT%\scratch\release_assets\goodq4all-0.1.1-host-tools-windows-x86_64.zip"

# Verify Manifests
Get-FileHash -Algorithm SHA256 "%GOODQ_REPO_ROOT%\scratch\offline_bundle\current\manifests\windows_pip_wheelhouse_manifest.json"
Get-FileHash -Algorithm SHA256 "%GOODQ_REPO_ROOT%\scratch\offline_bundle\current\manifests\windows_pip_wheelhouse_files.json"
```

### Bash (WSL2 / Linux Environment)
```bash
# Verify Host Tools Zip
sha256sum $GOODQ_REPO_ROOT/scratch/release_assets/goodq4all-0.1.1-host-tools-windows-x86_64.zip

# Verify Manifests
sha256sum $GOODQ_REPO_ROOT/scratch/offline_bundle/current/manifests/windows_pip_wheelhouse_manifest.json
```
