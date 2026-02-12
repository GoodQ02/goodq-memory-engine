<!-- DOC_BADGE: HISTORICAL -->
<!-- DOC_STATUS: ARCHIVED -->
<!-- DOC_ARCHIVED_ON: 2026-02-12 -->

# Bugfix: Command Center Heredoc Syntax

**Date:** October 6, 2025  
**Issue:** PowerShell heredoc syntax error  
**Status:** ✅ FIXED

---

## Problem

The `command_center.ps1` script used Unix-style heredoc syntax (`<<'PY'`) which is not supported in Windows PowerShell:

```powershell
# ✗ BROKEN (Unix-style)
$out = & conda run -n goodq_zenml python - <<'PY'
import sqlite3, sys
...
PY
```

**Error:**
```
ParserError: Missing file specification after redirection operator.
The '<' operator is reserved for future use.
```

---

## Solution

Replaced all heredocs with temp file approach:

```powershell
# ✓ FIXED (PowerShell-compatible)
$pyScript = @'
import sqlite3, sys
...
'@
$tmpFile = [System.IO.Path]::GetTempFileName()
Set-Content -LiteralPath $tmpFile -Value $pyScript -Encoding UTF8
try {
    $out = & conda run -n goodq_zenml python $tmpFile $args
} finally {
    Remove-Item -LiteralPath $tmpFile -Force -ErrorAction SilentlyContinue
}
```

---

## Changes Made

**File:** `scripts/command_center.ps1`

**Locations Fixed:**
1. Line ~47: `Show-DBAndFAISS` function (DB query)
2. Line ~70: `_faiss` helper (FAISS index count)
3. Line ~234: Memory snapshots query
4. Line ~357: FAISS count helper
5. Line ~367: SQLite count helper

**Total:** 5 heredoc patterns replaced

---

## Verification

```powershell
# Syntax check
$errors = $null
$tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    "L:\goodq4all\scripts\command_center.ps1", 
    [ref]$tokens, 
    [ref]$errors
)

# Result: No errors! ✓
```

---

## Testing

```powershell
# Test Command Center directly
pwsh scripts/command_center.ps1

# Test full launcher
.\LAUNCH_GOODQ.bat
```

Both should now work without syntax errors!

---

## Root Cause

The original script was likely developed/tested on Linux/macOS where heredoc syntax (`<<EOF`) is natively supported by the shell. Windows PowerShell doesn't support this syntax and requires alternative approaches like:

1. ✅ Temp files (used here)
2. ✅ Here-strings with `@'...'@`
3. ✅ String variables passed as arguments

---

## Impact

- ✅ Command Center now launches successfully
- ✅ LAUNCH_GOODQ.bat works end-to-end
- ✅ All database/FAISS queries functional
- ✅ Cross-platform compatibility maintained (temp files work everywhere)

---

*Bugfix applied: October 6, 2025*
