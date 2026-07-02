; GoodQ4All Hardened Offline Installer Script (NSIS)
; ---------------------------------------
; State-Machine driven installer for Windows 11.
; Allocates binaries to Program Files and mutable data/storage to ProgramData.

!include "MUI2.nsh"
!include "WinVer.nsh"
!include "FileFunc.nsh"

Name "GoodQ4All"
OutFile "..\..\GoodQ4All_Setup_2.5.8-rc5.exe"
InstallDir "$PROGRAMFILES64\GoodQ4All"
RequestExecutionLevel admin

; MUI Configuration
!define MUI_ABORTWARNING
!define MUI_ICON "..\..\branding\favicon.ico"
!define MUI_UNICON "..\..\branding\favicon.ico"
!define MUI_WELCOMEPAGE_TITLE "Welcome to the GoodQ4All v2.5.8-rc5 Offline Installer"
!define MUI_WELCOMEPAGE_TEXT "This installer will set up your local-first personal memory engine completely offline.\r\n\r\nIt configures a sandboxed Python runtime and imports selected local models."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; Component selection variables
Var AlwaysOnService
Var GpuEnhancedMode
Var WslStatus
Var GpuStatus
Var COMMONAPPDATA
Var WslTarPath

Function .onInit
  SetShellVarContext all
  StrCpy $AlwaysOnService 0
  StrCpy $GpuEnhancedMode 0
  StrCpy $WslStatus "skipped_wsl_unavailable"
  StrCpy $GpuStatus "skipped"
FunctionEnd

Section "Base Application (Required)" SecBase
  SectionIn RO
  SetShellVarContext all
  StrCpy $COMMONAPPDATA $APPDATA
  SetOutPath "$INSTDIR"

  ; --- STATE 1: preflight ---
  DetailPrint "Step 1/12: Running preflight system checks..."
  ; Verify Windows 11 / Windows 10
  ${IfNot} ${AtLeastWin10}
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: GoodQ4All requires Windows 10 or Windows 11."
    Abort
  ${EndIf}
  
  ; --- STATE 2: install runtime ---
  DetailPrint "Step 2/12: Installing sandboxed Python 3.10 runtime..."
  SetOutPath "$INSTDIR\runtime"
  File /r "staged\runtime\*.*"

  ; --- STATE 3: verify runtime ---
  DetailPrint "Step 3/12: Verifying isolated Python runtime..."
  IfFileExists "$INSTDIR\runtime\python.exe" runtime_ok runtime_fail
runtime_fail:
  IfSilent +2
  MessageBox MB_OK|MB_ICONSTOP "Error: Failed to verify embedded Python runtime."
  Abort
runtime_ok:
  DetailPrint "Isolated runtime verified successfully."

  ; --- STATE 4: install app ---
  DetailPrint "Step 4/12: Copying application binaries and codefiles..."
  SetOutPath "$INSTDIR"
  File "..\..\LAUNCH_GOODQ.exe"
  File "..\..\goodq_version.py"
  File "..\..\requirements-baseline-lock.txt"
  
  SetOutPath "$INSTDIR\qdrant"
  File "staged\qdrant\qdrant.exe"

  SetOutPath "$INSTDIR\scripts"
  File /r /x "go_compiler" /x "nsis_compiler" /x "nssm_bin" /x "staged" /x "go_bin" /x "dev_private_key.hex" "..\..\scripts\*.*"

  SetOutPath "$INSTDIR\configs"
  File /r /x "config.local.yaml" "..\..\configs\*.*"

  SetOutPath "$INSTDIR\api"
  File /r "..\..\api\*.*"

  SetOutPath "$INSTDIR\cli"
  File /r "..\..\cli\*.*"

  SetOutPath "$INSTDIR\steps"
  File /r "..\..\steps\*.*"

  SetOutPath "$INSTDIR\ui"
  File /r "..\..\ui\*.*"

  SetOutPath "$INSTDIR\agents"
  File /r "..\..\agents\*.*"

  SetOutPath "$INSTDIR\lib"
  File /r "..\..\lib\*.*"

  SetOutPath "$INSTDIR\common"
  File /r "..\..\common\*.*"

  SetOutPath "$INSTDIR\retrieval"
  File /r "..\..\retrieval\*.*"

  SetOutPath "$INSTDIR\pipelines"
  File /r "..\..\pipelines\*.*"

  SetOutPath "$INSTDIR\vendor"
  File /r "staged\vendor\*.*"

  SetOutPath "$INSTDIR\branding"
  File /r "..\..\branding\*.*"

  ; Create data directories under ProgramData
  CreateDirectory "$COMMONAPPDATA\GoodQ4All"
  CreateDirectory "$COMMONAPPDATA\GoodQ4All\logs"
  CreateDirectory "$COMMONAPPDATA\GoodQ4All\qdrant\storage"
  CreateDirectory "$COMMONAPPDATA\GoodQ4All\qdrant\logs"
  CreateDirectory "$COMMONAPPDATA\GoodQ4All\qdrant\config"
  CreateDirectory "$COMMONAPPDATA\GoodQ4All\models"
  CreateDirectory "$COMMONAPPDATA\GoodQ4All\GoodQ_Data"
  CreateDirectory "$COMMONAPPDATA\GoodQ4All\GoodQ_Data\import_inbox"
  CreateDirectory "$COMMONAPPDATA\GoodQ4All\GoodQ_Data\processed"
  CreateDirectory "$COMMONAPPDATA\GoodQ4All\GoodQ_Data\failed"

  ; Write default config to ProgramData
  SetOutPath "$COMMONAPPDATA\GoodQ4All\qdrant\config"
  File "staged\qdrant\config\qdrant_config.yaml"

  ; Grant modify permissions on ProgramData folder to standard users
  DetailPrint "Configuring folder permissions for standard users..."
  nsExec::ExecToLog 'icacls "$COMMONAPPDATA\GoodQ4All" /grant *S-1-5-32-545:(OI)(CI)M /T /C'

  ; --- STATE 5: install VC++ Redistributable ---
  DetailPrint "Step 5/12: Installing VC++ Runtime prerequisites..."
  SetOutPath "$INSTDIR\binaries"
  File "staged\binaries\vc_redist.x64.exe"
  File "staged\binaries\tesseract_setup.exe"
  nsExec::ExecToLog '"$INSTDIR\binaries\vc_redist.x64.exe" /q /norestart'
  Pop $0
  DetailPrint "VC++ Redistributable setup completed. exit code = $0"
  ${If} $0 != 0
  ${AndIf} $0 != 3010
  ${AndIf} $0 != 1638
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: VC++ Redistributable installation failed. Code $0"
    Abort
  ${EndIf}

  ; --- STATE 6: copy local wheelhouse & install offline ---
  DetailPrint "Step 6/12: Staging wheelhouse and installing Python packages..."
  SetOutPath "$INSTDIR\wheels"
  File /r "staged\wheels\*.*"
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" -m pip install --upgrade --force-reinstall --no-index --find-links="$INSTDIR\wheels" -r "$INSTDIR\requirements-baseline-lock.txt"'
  Pop $0
  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Offline Python package installation failed. Code $0"
    Abort
  ${EndIf}

  ; --- STATE 7: configure background service if requested ---
  DetailPrint "Step 7/12: Configuring service registrations..."
  ${If} $AlwaysOnService == 1
    SetOutPath "$INSTDIR\nssm"
    File "staged\nssm\nssm.exe"
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" install GoodQ_Qdrant "$INSTDIR\qdrant\qdrant.exe" "--config-path $COMMONAPPDATA\GoodQ4All\qdrant\config\qdrant_config.yaml"'
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" set GoodQ_Qdrant AppDirectory "$INSTDIR\qdrant"'
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" set GoodQ_Qdrant AppStdout "$COMMONAPPDATA\GoodQ4All\qdrant\logs\service_stdout.log"'
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" set GoodQ_Qdrant AppStderr "$COMMONAPPDATA\GoodQ4All\qdrant\logs\service_stderr.log"'
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" start GoodQ_Qdrant'
  ${Else}
    DetailPrint "Personal Mode selected. Qdrant will start on-demand under LAUNCH_GOODQ.exe."
  ${EndIf}

  ; --- STATE 8: WSL pre-baked distro import ---
  DetailPrint "Step 8/12: Configuring WSL2 audio compute environment..."
  ; Stage wsl distro folder
  SetOutPath "$INSTDIR\wsl"
  IfFileExists "staged\wsl\goodq_audio_wsl.tar" 0 wsl_tar_staged_skip
  File /nonfatal "staged\wsl\goodq_audio_wsl.tar"
wsl_tar_staged_skip:

  ${If} $GpuEnhancedMode == 0
    ; Baseline mode - check if tar file is absent to print a warning, but do not abort
    StrCpy $WslTarPath "$EXEDIR\goodq_audio_wsl.tar"
    IfFileExists "$WslTarPath" wsl_baseline_tar_ok 0
    StrCpy $WslTarPath "$INSTDIR\wsl\goodq_audio_wsl.tar"
    IfFileExists "$WslTarPath" wsl_baseline_tar_ok 0
    DetailPrint "Warning: Pre-baked WSL2 audio container (goodq_audio_wsl.tar) is absent."
wsl_baseline_tar_ok:
    StrCpy $WslStatus "skipped_wsl_unavailable"
    Goto wsl_done
  ${EndIf}

  ; GPU mode ($GpuEnhancedMode == 1)
  ; Check if GoodQ_Audio_Distro is already registered
  DetailPrint "Checking if GoodQ_Audio_Distro is already registered..."
  nsExec::ExecToLog 'wsl -d GoodQ_Audio_Distro -- true'
  Pop $0
  ${If} $0 == 0
    DetailPrint "GoodQ_Audio_Distro is already registered. Reusing the existing registration."
    StrCpy $WslStatus "reused"
    Goto wsl_done
  ${EndIf}

  ; Not registered: Check if the pre-baked tar file is present
  StrCpy $WslTarPath "$EXEDIR\goodq_audio_wsl.tar"
  IfFileExists "$WslTarPath" wsl_tar_found 0
  StrCpy $WslTarPath "$INSTDIR\wsl\goodq_audio_wsl.tar"
  IfFileExists "$WslTarPath" wsl_tar_found wsl_tar_missing

wsl_tar_missing:
  IfSilent +2
  MessageBox MB_OK|MB_ICONSTOP "Error: Pre-baked WSL2 audio container (goodq_audio_wsl.tar) is required for GPU-Accelerated mode but was not found."
  Abort

wsl_tar_found:
  DetailPrint "Importing pre-baked WSL2 Linux container..."
  nsExec::ExecToLog 'wsl --import GoodQ_Audio_Distro "$COMMONAPPDATA\GoodQ4All\wsl_runtime" "$WslTarPath"'
  Pop $0
  ${If} $0 != 0
    DetailPrint "Error: Failed to import WSL2 audio compute container. Code: $0. Cleaning up registration..."
    nsExec::ExecToLog 'wsl --unregister GoodQ_Audio_Distro'
    Pop $1
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Failed to import WSL2 audio compute container. Code: $0"
    Abort
  ${EndIf}

  ; Usability verification
  DetailPrint "Verifying usability of imported WSL2 container..."
  nsExec::ExecToLog 'wsl -d GoodQ_Audio_Distro -- true'
  Pop $0
  ${If} $0 != 0
    DetailPrint "Error: Imported WSL2 container failed usability check. Code: $0. Cleaning up registration..."
    nsExec::ExecToLog 'wsl --unregister GoodQ_Audio_Distro'
    Pop $1
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Imported WSL2 container failed usability check. Code: $0"
    Abort
  ${EndIf}

  DetailPrint "WSL2 audio compute container imported and verified successfully."
  StrCpy $WslStatus "imported"

wsl_done:

  ; --- STATE 9: merge and verify model zips (non-fatal) ---
  DetailPrint "Step 9/12: Extracting and registering pre-staged model packs..."
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" "$INSTDIR\scripts\install\sandbox_env_setup.py" --packs core_memory --data-dir "$COMMONAPPDATA\GoodQ4All" --cache-dir "$EXEDIR"'
  Pop $0
  ${If} $0 != 0
    DetailPrint "Model pack setup returned code $0. Models will be downloaded on first launch."
    IfSilent model_pack_skip
    MessageBox MB_OK|MB_ICONINFORMATION "Model packs were not found alongside the installer.$\r$\n$\r$\nThe application will download required models (~830 MB) on first launch via LAUNCH_GOODQ.exe.$\r$\n$\r$\nYou can also place model pack files next to the installer and re-run to install offline."
    model_pack_skip:
  ${EndIf}

  ; --- STATE 10: run health check ---
  /*
  DetailPrint "Step 10/12: Running system readiness verification..."
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" "$INSTDIR\scripts\system_readiness_check.py" --data-dir "$COMMONAPPDATA\GoodQ4All"'
  Pop $0
  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: System readiness check failed. Code $0"
    Abort
  ${EndIf}
  DetailPrint "System health readiness test completed with code $0."
  */

  ; --- STATE 11: write install receipt ---
  DetailPrint "Step 11/12: Writing installation receipt..."
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" "$INSTDIR\scripts\install\sandbox_env_setup.py" --write-receipt --install-dir "$INSTDIR" --data-dir "$COMMONAPPDATA\GoodQ4All" --service-mode "$AlwaysOnService" --wsl-status "$WslStatus" --baseline-status "ok" --gpu-enhanced-status "$GpuStatus"'

  ; --- STATE 12: shortcuts & uninstaller ---
  DetailPrint "Step 12/12: Completing installation shortcuts..."
  SetOutPath "$INSTDIR"
  CreateDirectory "$SMPROGRAMS\GoodQ4All"
  CreateShortcut "$SMPROGRAMS\GoodQ4All\GoodQ4All.lnk" "$INSTDIR\LAUNCH_GOODQ.exe" "" "$INSTDIR\branding\favicon.ico" 0
  CreateShortcut "$DESKTOP\GoodQ4All.lnk" "$INSTDIR\LAUNCH_GOODQ.exe" "" "$INSTDIR\branding\favicon.ico" 0

  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Write Add/Remove Programs Registry Keys
  SetRegView 64
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "DisplayName" "GoodQ4All"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "DisplayVersion" "2.5.8-rc5"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "Publisher" "GoodQ4All Team"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "DisplayIcon" '"$INSTDIR\branding\favicon.ico"'
SectionEnd

Section /o "Always-On Background Service" SecService
  StrCpy $AlwaysOnService 1
SectionEnd

Section /o "GPU-Accelerated WSL2 Audio" SecGpu
  StrCpy $GpuEnhancedMode 1
  StrCpy $GpuStatus "ok"
SectionEnd

; Uninstaller Section
Section "Uninstall"
  SetShellVarContext all
  StrCpy $COMMONAPPDATA $APPDATA
  
  ; Stop and delete Windows service if registered
  IfFileExists "$INSTDIR\nssm\nssm.exe" stop_service skip_service_cleanup
stop_service:
  nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" stop GoodQ_Qdrant'
  nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" remove GoodQ_Qdrant confirm'
skip_service_cleanup:

  ; Preserve the optional WSL2 audio distro by default. It can be a large
  ; user-provisioned offline backend that may not be embedded in the installer.
  IfSilent preserve_wsl_distro
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Would you like to delete the GoodQ4All WSL2 audio backend (GoodQ_Audio_Distro)? Choose No to preserve offline audio acceleration." IDNO preserve_wsl_distro
  nsExec::ExecToLog 'wsl --unregister GoodQ_Audio_Distro'
preserve_wsl_distro:

  ; Delete Program Files directories
  Delete "$INSTDIR\LAUNCH_GOODQ.exe"
  Delete "$INSTDIR\goodq_version.py"
  Delete "$INSTDIR\requirements-baseline-lock.txt"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\qdrant"
  RMDir /r "$INSTDIR\scripts"
  RMDir /r "$INSTDIR\configs"
  RMDir /r "$INSTDIR\api"
  RMDir /r "$INSTDIR\cli"
  RMDir /r "$INSTDIR\steps"
  RMDir /r "$INSTDIR\ui"
  RMDir /r "$INSTDIR\agents"
  RMDir /r "$INSTDIR\lib"
  RMDir /r "$INSTDIR\common"
  RMDir /r "$INSTDIR\retrieval"
  RMDir /r "$INSTDIR\pipelines"
  RMDir /r "$INSTDIR\vendor"
  RMDir /r "$INSTDIR\wheels"
  RMDir /r "$INSTDIR\binaries"
  RMDir /r "$INSTDIR\wsl"
  RMDir /r "$INSTDIR\branding"
  RMDir "$INSTDIR"

  ; Delete shortcuts
  Delete "$SMPROGRAMS\GoodQ4All\GoodQ4All.lnk"
  RMDir "$SMPROGRAMS\GoodQ4All"
  Delete "$DESKTOP\GoodQ4All.lnk"

  ; Prompt user to delete user data. Silent uninstall preserves data by default.
  IfSilent preserve_data
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Would you like to delete your personal GoodQ4All memory database and downloaded model packs? (Warning: This will destroy all ingested memory and cannot be undone.)" IDNO preserve_data
  
  RMDir /r "$COMMONAPPDATA\GoodQ4All"
  Goto end_uninstall
  
preserve_data:
  Delete "$COMMONAPPDATA\GoodQ4All\install_receipt.json"

end_uninstall:
  SetRegView 64
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All"
SectionEnd
