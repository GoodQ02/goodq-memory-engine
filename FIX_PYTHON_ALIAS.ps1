# Fix Windows Store Python Alias Interference
# This removes the annoying Microsoft Store app execution aliases

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "FIXING PYTHON WINDOWS STORE INTERFERENCE" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "🔍 THE PROBLEM:" -ForegroundColor Yellow
Write-Host "   Windows 10/11 includes 'app execution aliases' that redirect" -ForegroundColor White
Write-Host "   'python' and 'python3' commands to the Microsoft Store." -ForegroundColor White
Write-Host "   This interferes with your real Python installation!`n" -ForegroundColor White

Write-Host "🔧 THE FIX:" -ForegroundColor Green
Write-Host "   We need to disable these aliases in Windows Settings.`n" -ForegroundColor White

Write-Host "📋 MANUAL STEPS (takes 30 seconds):" -ForegroundColor Cyan
Write-Host "   1. Press Win+I to open Windows Settings" -ForegroundColor Yellow
Write-Host "   2. Go to: Apps > Apps & features (or Apps > Advanced app settings)" -ForegroundColor Yellow
Write-Host "   3. Click: 'App execution aliases'" -ForegroundColor Yellow
Write-Host "   4. Find 'python.exe' and 'python3.exe'" -ForegroundColor Yellow
Write-Host "   5. Toggle BOTH to OFF (disabled)`n" -ForegroundColor Yellow

Write-Host "⚡ QUICK SHORTCUT:" -ForegroundColor Magenta
Write-Host "   Run this command to open the settings directly:`n" -ForegroundColor White

Write-Host '   Start-Process "ms-settings:appsfeatures-app"' -ForegroundColor Cyan

Write-Host "`n   Then navigate to 'App execution aliases' on the left side.`n" -ForegroundColor White

Write-Host "🤔 OR - Use this automated approach:" -ForegroundColor Green
Write-Host "   We can try to disable via registry (may require admin)`n" -ForegroundColor White

$choice = Read-Host "Try automated fix? (Y/N)"

if ($choice -eq 'Y' -or $choice -eq 'y') {
    Write-Host "`n🔧 Attempting registry fix..." -ForegroundColor Cyan
    
    $aliasPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths"
    $aliasesPath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock"
    
    # Try to disable app execution aliases
    try {
        # Remove Windows Store Python aliases from registry
        $pythonAlias = "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"
        $python3Alias = "$env:LOCALAPPDATA\Microsoft\WindowsApps\python3.exe"
        
        if (Test-Path $pythonAlias) {
            Write-Host "  Found Windows Store python.exe alias at: $pythonAlias" -ForegroundColor Yellow
        }
        
        if (Test-Path $python3Alias) {
            Write-Host "  Found Windows Store python3.exe alias at: $python3Alias" -ForegroundColor Yellow
        }
        
        Write-Host "`n  ⚠️  Cannot automatically disable these aliases." -ForegroundColor Yellow
        Write-Host "      Please use the manual steps above.`n" -ForegroundColor Yellow
        
    } catch {
        Write-Host "  ❌ Error: $_" -ForegroundColor Red
    }
    
    # Open settings for user
    Write-Host "  Opening Windows Settings for you..." -ForegroundColor Cyan
    Start-Process "ms-settings:appsfeatures-app"
    Start-Sleep -Seconds 2
    
    Write-Host "`n  ✓ Settings opened! Navigate to 'App execution aliases' on the left." -ForegroundColor Green
    
} else {
    Write-Host "`n⏭️  Skipped automated fix. Use manual steps above when ready.`n" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "AFTER DISABLING THE ALIASES:" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "1️⃣  Close all terminal windows" -ForegroundColor White
Write-Host "2️⃣  Open a NEW PowerShell or CMD window" -ForegroundColor White
Write-Host "3️⃣  Test: python --version" -ForegroundColor White
Write-Host "    (Should show your Conda Python, not 'Python was not found')" -ForegroundColor DarkGray
Write-Host "4️⃣  Test: Double-click LAUNCH_WEB_INTERFACE.bat" -ForegroundColor White
Write-Host "    (Should work without errors!)`n" -ForegroundColor DarkGray

Write-Host "========================================`n" -ForegroundColor Cyan
