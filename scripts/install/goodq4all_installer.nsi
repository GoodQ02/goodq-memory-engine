; GoodQ4All Unified Installer Script (NSIS)
; ---------------------------------------
; State-Machine driven installer for Windows 11.
; Allocates binaries to Program Files and mutable data/storage to ProgramData.

!include "MUI2.nsh"
!include "WinVer.nsh"
!include "FileFunc.nsh"

Name "GoodQ4All"
OutFile "..\..\GoodQ4All_Setup_1.0.0.exe"
InstallDir "$PROGRAMFILES64\GoodQ4All"
RequestExecutionLevel admin

; MUI Configuration
!define MUI_ABORTWARNING
!define MUI_ICON "..\..\branding\favicon.ico"
!define MUI_UNICON "..\..\branding\favicon.ico"
!define MUI_WELCOMEPAGE_TITLE "Welcome to the GoodQ4All v1.0.0 Installer"
!define MUI_WELCOMEPAGE_TEXT "This installer will set up your local-first personal memory engine.\r\n\r\nIt will configure a sandboxed runtime environment (No Conda required) and download selected model weights."

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

Section "Base Application (Required)" SecBase
  SectionIn RO
  SetShellVarContext all
  SetOutPath "$INSTDIR"

  ; --- STATE 1: preflight ---
  DetailPrint "Step 1/10: Running preflight system checks..."
  ; Verify Windows 11 / Windows 10
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONSTOP "Error: GoodQ4All requires Windows 10 or Windows 11."
    Abort
  ${EndIf}
  
  ; --- STATE 2: install runtime ---
  DetailPrint "Step 2/10: Installing sandboxed Python 3.10 runtime..."
  SetOutPath "$INSTDIR\runtime"
  ; (During build_installer.bat, python-3.10-embed-amd64.zip is staged here)
  File "staged\python-3.10-embed-amd64.zip"
  ; Expand the zip using a lightweight utility or built-in cmd
  ; For safety, build_installer.bat pre-extracts it into a folder, or we bundle unzip.exe
  File /r "staged\runtime\*.*"

  ; --- STATE 3: verify runtime ---
  DetailPrint "Step 3/10: Verifying isolated Python runtime..."
  IfFileExists "$INSTDIR\runtime\python.exe" runtime_ok runtime_fail
runtime_fail:
  MessageBox MB_OK|MB_ICONSTOP "Error: Failed to verify embedded Python runtime."
  Abort
runtime_ok:
  DetailPrint "Isolated runtime verified successfully."

  ; --- STATE 4: install app ---
  DetailPrint "Step 4/10: Copying application binaries and codefiles..."
  SetOutPath "$INSTDIR"
  File "..\..\LAUNCH_GOODQ.exe"
  File "..\..\goodq_version.py"
  
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
  File /r "..\..\vendor\*.*"

  SetOutPath "$INSTDIR\branding"
  File /r "..\..\branding\*.*"

  ; Create data directories under ProgramData
  CreateDirectory "$APPDATA\GoodQ4All"
  CreateDirectory "$APPDATA\GoodQ4All\qdrant\storage"
  CreateDirectory "$APPDATA\GoodQ4All\qdrant\logs"
  CreateDirectory "$APPDATA\GoodQ4All\qdrant\config"
  CreateDirectory "$APPDATA\GoodQ4All\models"
  CreateDirectory "$APPDATA\GoodQ4All\GoodQ_Data"
  CreateDirectory "$APPDATA\GoodQ4All\GoodQ_Data\import_inbox"
  CreateDirectory "$APPDATA\GoodQ4All\GoodQ_Data\processed"
  CreateDirectory "$APPDATA\GoodQ4All\GoodQ_Data\failed"

  ; Write default config to ProgramData
  SetOutPath "$APPDATA\GoodQ4All\qdrant\config"
  File "staged\qdrant\config\qdrant_config.yaml"

  ; --- STATE 5: configure service ---
  DetailPrint "Step 5/10: Configuring service registrations..."
  ${If} $AlwaysOnService == 1
    SetOutPath "$INSTDIR\nssm"
    File "staged\nssm\nssm.exe"
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" install GoodQ_Qdrant "$INSTDIR\qdrant\qdrant.exe" "--config-path $APPDATA\GoodQ4All\qdrant\config\qdrant_config.yaml"'
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" set GoodQ_Qdrant AppDirectory "$INSTDIR\qdrant"'
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" set GoodQ_Qdrant AppStdout "$APPDATA\GoodQ4All\qdrant\logs\service_stdout.log"'
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" set GoodQ_Qdrant AppStderr "$APPDATA\GoodQ4All\qdrant\logs\service_stderr.log"'
    nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" start GoodQ_Qdrant'
  ${Else}
    DetailPrint "Personal Mode selected. Qdrant will start on-demand under LAUNCH_GOODQ.exe."
  ${EndIf}

  ; --- STATE 6: download selected model packs ---
  DetailPrint "Step 6/10: Hydrating sandboxed runtime and downloading model packs..."
  ; Note: Core Memory Pack is downloaded by default. Other selected components trigger additional flags.
  DetailPrint "Executing environment setup and downloading Core Memory Pack..."
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" "$INSTDIR\scripts\install\sandbox_env_setup.py" --packs core_memory --data-dir "$APPDATA\GoodQ4All" --cache-dir "$EXEDIR"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "Error: Hydration or Core Model Pack download failed. Code $0"
    Abort
  ${EndIf}

  ; --- STATE 7: verify assets ---
  DetailPrint "Step 7/10: Running asset checksum verification..."
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" "$INSTDIR\scripts\install\sandbox_env_setup.py" --verify-only --data-dir "$APPDATA\GoodQ4All"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_OK|MB_ICONSTOP "Error: Asset verification failed. One or more model checksums are invalid."
    Abort
  ${EndIf}

  ; --- STATE 8: run health check ---
  DetailPrint "Step 8/10: Executing startup health checks..."
  ; Run python preflight diagnostics check inside sandbox
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" "$INSTDIR\scripts\system_readiness_check.py" --data-dir "$APPDATA\GoodQ4All"'
  Pop $0
  DetailPrint "System health readiness test completed with code $0."

  ; --- STATE 9: write install receipt ---
  DetailPrint "Step 9/10: Writing installation receipt..."
  nsExec::ExecToLog '"$INSTDIR\runtime\python.exe" "$INSTDIR\scripts\install\sandbox_env_setup.py" --write-receipt --install-dir "$INSTDIR" --data-dir "$APPDATA\GoodQ4All" --service-mode "$AlwaysOnService"'

  ; --- STATE 10: enable launch ---
  DetailPrint "Step 10/10: Creating shortcuts and enabling launcher..."
  SetOutPath "$INSTDIR"
  CreateDirectory "$SMPROGRAMS\GoodQ4All"
  CreateShortcut "$SMPROGRAMS\GoodQ4All\GoodQ4All.lnk" "$INSTDIR\LAUNCH_GOODQ.exe" "" "$INSTDIR\branding\favicon.ico" 0
  CreateShortcut "$DESKTOP\GoodQ4All.lnk" "$INSTDIR\LAUNCH_GOODQ.exe" "" "$INSTDIR\branding\favicon.ico" 0

  ; Write Uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Write uninstall keys to Windows Registry for Add/Remove Programs
  SetRegView 64
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "DisplayName" "GoodQ4All"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "DisplayVersion" "1.0.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "Publisher" "GoodQ4All Team"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All" "DisplayIcon" '"$INSTDIR\branding\favicon.ico"'
SectionEnd

Section "Always-On Background Service" SecService
  StrCpy $AlwaysOnService 1
SectionEnd

; Uninstaller Section
Section "Uninstall"
  SetShellVarContext all
  ; Stop and delete Windows service if registered
  IfFileExists "$INSTDIR\nssm\nssm.exe" stop_service skip_service_cleanup
stop_service:
  nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" stop GoodQ_Qdrant'
  nsExec::ExecToLog '"$INSTDIR\nssm\nssm.exe" remove GoodQ_Qdrant confirm'
skip_service_cleanup:

  ; Delete binaries and application directories from Program Files
  Delete "$INSTDIR\LAUNCH_GOODQ.exe"
  Delete "$INSTDIR\goodq_version.py"
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
  RMDir /r "$INSTDIR\branding"
  RMDir "$INSTDIR"

  ; Delete shortcuts
  Delete "$SMPROGRAMS\GoodQ4All\GoodQ4All.lnk"
  RMDir "$SMPROGRAMS\GoodQ4All"
  Delete "$DESKTOP\GoodQ4All.lnk"

  ; Prompt user to delete ProgramData user databases (default is preserve)
  MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Would you like to delete your personal GoodQ4All memory database and downloaded model packs? (Warning: This will destroy all ingested memory and cannot be undone.)" IDNO preserve_data
  
  ; If YES, delete everything under ProgramData
  RMDir /r "$APPDATA\GoodQ4All"
  Goto end_uninstall

preserve_data:
  ; Only delete temporary install receipts but preserve models & databases
  Delete "$APPDATA\GoodQ4All\install_receipt.json"

end_uninstall:
  ; Remove uninstall keys from registry
  SetRegView 64
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\GoodQ4All"
SectionEnd
