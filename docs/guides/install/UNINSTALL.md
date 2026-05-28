# GoodQ4All Uninstallation Guide

Use this guide when you want to remove GoodQ4All, its environments, database services, and stored data from your Windows 11 host.

---

## Method A: Standard Windows Uninstallation (Recommended)

If you installed GoodQ4All using the Sandboxed Windows Installer setup:

1. **Open Windows Settings**: Navigate to **Settings** > **Apps** > **Installed Apps** (or search for **Add or Remove Programs** from the Start Menu).
2. **Uninstall GoodQ4All**: Locate **GoodQ4All** in the list, click the three dots, and choose **Uninstall**.
   * Alternatively, run the uninstaller binary directly:
     ```text
     C:\Program Files\GoodQ4All\Uninstall.exe
     ```
3. **Preservation of User Database**: The uninstaller will delete all binaries, registry keys, shortcuts, and sandboxed python configurations. By default, it **preserves** your local media data, manifests, and database files stored in `C:\ProgramData\GoodQ4All` and `%USERPROFILE%\GoodQ_Data`.
4. **Complete Cleanup**: If you wish to delete all user data and local memory files as well, manually delete the following directories after the uninstaller completes:
   * `C:\ProgramData\GoodQ4All\`
   * `%USERPROFILE%\GoodQ_Data\`

---

## Method B: Developer Workspace Manual Cleanup (Advanced)

If you are running the project from source code and need to manually clean up your workspace:

### 1. Remove Conda Environments
Run this in your terminal to delete the main orchestration environment:
```powershell
conda env remove -n goodq_core
```

### 2. Remove the Qdrant Database Service
If you installed Qdrant as a Windows service:
1. Open an **Administrator** PowerShell or Command Prompt.
2. Run the uninstaller batch script located in the repository:
   ```powershell
   .\scripts\qdrant\UNINSTALL_QDRANT_SERVICE.bat
   ```

### 3. Delete Local Data and Artifacts
Delete the directory where all media files, manifests, processing data, and databases are stored. The default location is:
```text
%USERPROFILE%\GoodQ_Data\
```
If you configured a custom `GOODQ_DATA_ROOT` during bootstrap or inside `.env.local`, delete that directory instead.
