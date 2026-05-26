# GoodQ4All Uninstall Guide

Use this guide when you want to remove GoodQ4All, its environments, database services, and stored data from your Windows 11 host.

## 1. Remove Conda Environments

Run this in your terminal to delete the main orchestration environment:

```powershell
conda env remove -n goodq_core
```

## 2. Remove the Qdrant Database Service

To stop and uninstall the Windows background Qdrant service:

1. Open an **Administrator** Command Prompt or PowerShell.
2. Run the uninstaller batch script located in the repository:
   ```powershell
   .\scripts\qdrant\UNINSTALL_QDRANT_SERVICE.bat
   ```

## 3. Delete Local Data and Artifacts

Delete the directory where all media files, manifests, processing data, and databases are stored. The default location is:

```text
%USERPROFILE%\GoodQ_Data\
```

If you configured a custom `GOODQ_DATA_ROOT` during bootstrap or inside `.env.local`, delete that directory instead.
