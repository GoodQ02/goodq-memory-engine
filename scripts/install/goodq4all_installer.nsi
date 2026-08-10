; GoodQ4All Hardened Offline Installer Script (NSIS)
; ---------------------------------------
; State-Machine driven installer for Windows 11.
; Allocates binaries to Program Files and mutable data/storage to ProgramData.

!include "MUI2.nsh"
!include "WinVer.nsh"
!include "FileFunc.nsh"

Name "GoodQ4All"
!ifndef GOODQ_INSTALLER_OUTPUT_ROOT
!define GOODQ_INSTALLER_OUTPUT_ROOT "..\.."
!endif
!ifndef GOODQ_LAUNCHER_PATH
!define GOODQ_LAUNCHER_PATH "..\..\LAUNCH_GOODQ.exe"
!endif
!ifndef GOODQ_INSTALLER_PROFILE
!define GOODQ_INSTALLER_PROFILE "PUBLIC_CPU_BASELINE"
!endif
!if "${GOODQ_INSTALLER_PROFILE}" != "PUBLIC_CPU_BASELINE"
!if "${GOODQ_INSTALLER_PROFILE}" != "PUBLIC_GPU_ENHANCED"
!if "${GOODQ_INSTALLER_PROFILE}" != "PERSONAL_AIR_GAP"
!error "Unknown GOODQ_INSTALLER_PROFILE: ${GOODQ_INSTALLER_PROFILE}"
!endif
!endif
!endif
OutFile "${GOODQ_INSTALLER_OUTPUT_ROOT}\GoodQ4All_Setup_2.5.8.exe"
InstallDir "$PROGRAMFILES64\GoodQ4All"
RequestExecutionLevel admin

; MUI Configuration
!define MUI_ABORTWARNING
!define MUI_ICON "..\..\branding\favicon.ico"
!define MUI_UNICON "..\..\branding\favicon.ico"
!define MUI_WELCOMEPAGE_TITLE "Welcome to the GoodQ4All v2.5.8 Offline Installer"
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
Var WslStatus
Var GpuStatus
Var COMMONAPPDATA
Var InstallStage

Function .onInit
  SetShellVarContext all
  StrCpy $AlwaysOnService 0
  StrCpy $WslStatus "not_packaged"
  StrCpy $GpuStatus "not_packaged"
  StrCpy $COMMONAPPDATA $APPDATA
  StrCpy $InstallStage "initialization"

  ; A baseline install is intentionally a clean-target contract.  It must not
  ; overwrite the desktop's canonical data root or adopt its Qdrant service.
  ; A future upgrade workflow may make that migration explicit and evidenced.
  IfFileExists "$COMMONAPPDATA\GoodQ4All\GoodQ_Data\*.*" existing_canonical_install
  IfFileExists "$COMMONAPPDATA\GoodQ4All\runtime_config.json" existing_canonical_install
  nsExec::ExecToLog 'sc query "GoodQ_Qdrant"'
  Pop $0
  ${If} $0 == 0
    Goto existing_canonical_install
  ${EndIf}
  Goto clean_target_confirmed

existing_canonical_install:
  DetailPrint "Existing canonical GoodQ state detected. Baseline install aborted before changes."
  IfSilent +2
  MessageBox MB_OK|MB_ICONSTOP "Existing GoodQ data or service detected.$\r$\n$\r$\nThis baseline installer will not replace a canonical installation. Use a clean validation target or an explicit upgrade workflow."
  Abort

clean_target_confirmed:
FunctionEnd

Function .onInstFailed
  ; Silent installs otherwise return only NSIS exit code 2. Preserve the last
  ; owned state so a remote or unattended validation can report the cause.
  CreateDirectory "$COMMONAPPDATA\GoodQ4All"
  WriteINIStr "$COMMONAPPDATA\GoodQ4All\install_failure.ini" "installation" "stage" "$InstallStage"
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
  StrCpy $InstallStage "runtime_verify"
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
  File "${GOODQ_LAUNCHER_PATH}"
  File "..\..\goodq_version.py"
  File "staged\requirements-lock.txt"
  File "verify_offline_suite.ps1"
  
  SetOutPath "$INSTDIR\qdrant"
  File "staged\qdrant\qdrant.exe"

  SetOutPath "$INSTDIR\ffmpeg"
  File /r "staged\ffmpeg\*.*"

  SetOutPath "$INSTDIR\poppler"
  File /r "staged\poppler\*.*"

  SetOutPath "$INSTDIR\scripts"
  File /r /x "go_compiler" /x "nsis_compiler" /x "nssm_bin" /x "staged" /x "staged_cache" /x "go_bin" /x "dev_private_key.hex" "..\..\scripts\*.*"

  SetOutPath "$INSTDIR\configs"
  File /r /x "config.local.yaml" /x "model_download_manifest.json" /x "model_download_manifest.json.sig" "..\..\configs\*.*"
  File "staged\configs\model_download_manifest.json"
  File "staged\configs\model_download_manifest.json.sig"
  File "staged\configs\selected_capabilities.json"
  File "staged\configs\selected_capabilities.json.sig"
  File "staged\configs\installer_profile.txt"

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

  ; Large, sealed runtime payloads are intentionally not embedded in this
  ; NSIS bootstrap.  They remain as signed ZIP packs beside Setup.exe and are
  ; verified before extraction below.  This keeps the bootstrap inside NSIS's
  ; supported data-block boundary without reducing the offline CPU profile.

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

  ; Verify the signed external payload manifest, then extract every bounded
  ; local pack.  This is intentionally before wheel installation and model
  ; verification so a partial or moved release bundle fails at its boundary.
  DetailPrint "Step 5/12: Verifying and extracting signed offline payload packs..."
  StrCpy $InstallStage "payload_pack_verify"
  nsExec::ExecToLog '"$INSTDIR\LAUNCH_GOODQ.exe" --verify-release-payload "$EXEDIR"'
  Pop $0
  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Signed offline payload verification failed. Keep every release asset together and retry. Code $0"
    Abort
  ${EndIf}
  StrCpy $InstallStage "payload_pack_extract"
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" "$INSTDIR\scripts\install\release_payload_packs.py" apply --bundle-root "$EXEDIR" --install-dir "$INSTDIR" --data-dir "$COMMONAPPDATA\GoodQ4All"'
  Pop $0
  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Signed offline payload extraction failed. Code $0"
    Abort
  ${EndIf}

  ; Write default config to ProgramData
  SetOutPath "$COMMONAPPDATA\GoodQ4All\qdrant\config"
  File "staged\qdrant\config\qdrant_config.yaml"

  ; Grant modify permissions on ProgramData folder to standard users
  DetailPrint "Configuring folder permissions for standard users..."
  nsExec::ExecToLog 'icacls "$COMMONAPPDATA\GoodQ4All" /grant *S-1-5-32-545:(OI)(CI)M /T /C'

  ; --- STATE 6: install VC++ Redistributable ---
  DetailPrint "Step 6/12: Installing VC++ Runtime prerequisites..."
  StrCpy $InstallStage "vc_runtime_stage"
  SetOutPath "$INSTDIR\binaries"
  File "staged\binaries\vc_redist.x64.exe"
  File "staged\binaries\tesseract_setup.exe"
  ; The VC runtime is machine-wide. Reuse a healthy x64 runtime so a follower
  ; repair does not relaunch a GUI bootstrapper during an unattended install.
  SetRegView 64
  ReadRegDWORD $0 HKLM "SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" "Installed"
  ${If} $0 == 1
    Goto vcredist_verify
  ${EndIf}
vcredist_install:
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
vcredist_verify:
  StrCpy $InstallStage "vc_runtime_verify"
  ; A 32-bit NSIS process may be redirected between System32 and SysWOW64.
  ; Verify the same authoritative x64 runtime marker used for reuse instead.
  SetRegView 64
  ReadRegDWORD $1 HKLM "SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" "Installed"
  ${If} $1 != 1
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: VC++ Redistributable runtime verification failed."
    Abort
  ${EndIf}

  ; The engine is machine-wide. Reuse a working prior install so a repair or
  ; upgrade does not relaunch its nested NSIS setup and block unattended work.
  StrCpy $InstallStage "tesseract_stage"
  IfFileExists "$PROGRAMFILES64\Tesseract-OCR\tesseract.exe" tesseract_verify tesseract_install
tesseract_install:
  DetailPrint "Installing bundled Tesseract OCR prerequisite..."
  nsExec::ExecToLog '"$INSTDIR\binaries\tesseract_setup.exe" /S'
  Pop $0
  DetailPrint "Tesseract OCR setup completed. exit code = $0"
  ${If} $0 != 0
  ${AndIf} $0 != 2
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Tesseract OCR installation failed. Code $0"
    Abort
  ${EndIf}
tesseract_verify:
  StrCpy $InstallStage "tesseract_verify"
  IfFileExists "$PROGRAMFILES64\Tesseract-OCR\tesseract.exe" tesseract_command_verify tesseract_missing
tesseract_missing:
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Tesseract OCR executable was not installed."
    Abort
tesseract_command_verify:
  nsExec::ExecToLog '"$PROGRAMFILES64\Tesseract-OCR\tesseract.exe" --version'
  Pop $0
  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Tesseract OCR verification failed. Code $0"
    Abort
  ${EndIf}

  ; --- STATE 7: install local wheelhouse ---
  DetailPrint "Step 7/12: Installing Python packages from signed offline payload..."
  StrCpy $InstallStage "wheelhouse_stage"
  SetOutPath "$INSTDIR"
  File "staged\wheelhouse-sbom.json"
  IfFileExists "$INSTDIR\wheels\pytesseract-0.3.10-py3-none-any.whl" wheelhouse_ready wheelhouse_missing
wheelhouse_missing:
  IfSilent +2
  MessageBox MB_OK|MB_ICONSTOP "Error: Required offline wheelhouse artifact is missing."
  Abort
wheelhouse_ready:
  StrCpy $InstallStage "wheelhouse_install"
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" -m pip install --upgrade --force-reinstall --no-index --find-links="file:///$INSTDIR/wheels" -r "$INSTDIR\requirements-lock.txt"'
  Pop $0
  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Offline Python package installation failed. Code $0"
    Abort
  ${EndIf}
!if "${GOODQ_INSTALLER_PROFILE}" != "PUBLIC_CPU_BASELINE"
  StrCpy $InstallStage "cuda_runtime_verify"
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" -c "import torch; assert torch.version.cuda; assert torch.cuda.is_available(); assert torch.cuda.device_count() >= 1; print(torch.__version__, torch.version.cuda, torch.cuda.device_count())"'
  Pop $0
  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: GPU Enhanced runtime did not detect a usable CUDA device. Code $0"
    Abort
  ${EndIf}
!endif
  StrCpy $InstallStage "ocr_binding_verify"
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" -c "import pytesseract; print(pytesseract.__version__)"'
  Pop $0
  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Installed Python OCR binding verification failed. Code $0"
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

  ; Optional WSL/GPU packaging is intentionally excluded from the public BASELINE.
  !if 0
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
  !endif

  ; --- STATE 8: sealed object-detection capability packs ---
  DetailPrint "Step 8/11: Sealed NanoDet baseline payload and YOLOX GPU capability staged."

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

  ; --- STATE 10: write install receipt ---
  DetailPrint "Step 10/11: Writing installation receipt..."
  StrCpy $InstallStage "install_receipt"
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" "$INSTDIR\scripts\install\sandbox_env_setup.py" --write-receipt --install-dir "$INSTDIR" --data-dir "$COMMONAPPDATA\GoodQ4All" --service-mode "$AlwaysOnService" --wsl-status "$WslStatus" --baseline-status "ok" --gpu-enhanced-status "$GpuStatus"'
  Pop $0
  ${If} $0 != 0
    IfSilent +2
    MessageBox MB_OK|MB_ICONSTOP "Error: Failed to write installation receipt. Code $0"
    Abort
  ${EndIf}

  ; --- STATE 11: shortcuts & uninstaller ---
  DetailPrint "Step 11/11: Completing installation shortcuts..."
  SetOutPath "$INSTDIR"
  CreateDirectory "$SMPROGRAMS\GoodQ4All"
  CreateShortcut "$SMPROGRAMS\GoodQ4All\GoodQ4All.lnk" "$INSTDIR\LAUNCH_GOODQ.exe" "" "$INSTDIR\branding\favicon.ico" 0
  CreateShortcut "$SMPROGRAMS\GoodQ4All\Install Audio Standard.lnk" "$INSTDIR\scripts\install\INSTALL_AUDIO_STANDARD.bat"
  CreateShortcut "$DESKTOP\GoodQ4All.lnk" "$INSTDIR\LAUNCH_GOODQ.exe" "" "$INSTDIR\branding\favicon.ico" 0

  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Write Add/Remove Programs Registry Keys
  SetRegView 64
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "DisplayName" "GoodQ4All"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "DisplayVersion" "2.5.8"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "Publisher" "GoodQ4All Team"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "DisplayIcon" '"$INSTDIR\branding\favicon.ico"'
SectionEnd

Section /o "Always-On Background Service" SecService
  StrCpy $AlwaysOnService 1
SectionEnd

!if 0
Section /o "GPU-Accelerated WSL2 Audio" SecGpu
  StrCpy $GpuEnhancedMode 1
  StrCpy $GpuStatus "ok"
SectionEnd
!endif

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
  Delete "$INSTDIR\scripts\install\INSTALL_AUDIO_STANDARD.bat"
  Delete "$INSTDIR\goodq_version.py"
  Delete "$INSTDIR\requirements-lock.txt"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\qdrant"
  RMDir /r "$INSTDIR\ffmpeg"
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
  RMDir /r "$INSTDIR\nssm"
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
