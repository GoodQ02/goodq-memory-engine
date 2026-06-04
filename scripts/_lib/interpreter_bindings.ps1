# Shared interpreter binding helpers for GoodQ4All scripts.
# Keeps launcher behavior deterministic across PATH / shell-state drift.

function Get-GoodQWslDistro {
    $distro = $env:GOODQ_WSL_DISTRO
    if ([string]::IsNullOrWhiteSpace($distro)) {
        return "Ubuntu"
    }
    return $distro
}

function Get-GoodQCondaEnv {
    $envName = $env:GOODQ_CONDA_ENV
    if ([string]::IsNullOrWhiteSpace($envName)) {
        return "goodq_core"
    }
    return $envName
}

function Get-GoodQCondaExe {
    # Prefer CONDA_EXE if present (set by conda/conda init).
    $candidates = @()

    if ($env:CONDA_EXE) { $candidates += $env:CONDA_EXE }
    if ($env:CONDA_ROOT) { $candidates += (Join-Path $env:CONDA_ROOT "Scripts\\conda.exe") }
    if ($env:CONDA_ROOT) { $candidates += (Join-Path $env:CONDA_ROOT "Scripts\\conda.bat") }

    $userHome = [Environment]::GetFolderPath('UserProfile')
    if ($userHome) {
        $candidates += (Join-Path $userHome "miniconda3\\Scripts\\conda.exe")
        $candidates += (Join-Path $userHome "miniconda3\\Scripts\\conda.bat")
        $candidates += (Join-Path $userHome "anaconda3\\Scripts\\conda.exe")
        $candidates += (Join-Path $userHome "anaconda3\\Scripts\\conda.bat")
    }

    $candidates += "C:\\ProgramData\\miniconda3\\Scripts\\conda.exe"
    $candidates += "C:\\ProgramData\\miniconda3\\Scripts\\conda.bat"
    $candidates += "C:\\ProgramData\\anaconda3\\Scripts\\conda.exe"
    $candidates += "C:\\ProgramData\\anaconda3\\Scripts\\conda.bat"

    foreach ($path in $candidates) {
        if ([string]::IsNullOrWhiteSpace($path)) { continue }
        if (Test-Path $path) { return $path }
    }

    $cmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }

    return "conda"
}

function Get-GoodQPythonExe {
    $envName = Get-GoodQCondaEnv
    
    # 1. Check if CONDA_PREFIX is already the active env we want
    if ($env:CONDA_PREFIX -and (Split-Path $env:CONDA_PREFIX -Leaf) -eq $envName) {
        $pyPath = [System.IO.Path]::GetFullPath((Join-Path $env:CONDA_PREFIX "python.exe"))
        if (Test-Path $pyPath) { return $pyPath }
    }
    
    # 2. Derive from CondaExe
    $condaExe = Get-GoodQCondaExe
    if (Test-Path $condaExe) {
        $condaDir = Split-Path $condaExe -Parent
        if ($condaDir -match '\\(Scripts|condabin|bin)$') {
            $condaRoot = Split-Path $condaDir -Parent
        } else {
            $condaRoot = $condaDir
        }
        $pyPath = [System.IO.Path]::GetFullPath((Join-Path $condaRoot "envs\$envName\python.exe"))
        if (Test-Path $pyPath) { return $pyPath }
    }
    
    # 3. Fallback candidates in standard locations
    $userHome = [Environment]::GetFolderPath('UserProfile')
    $candidates = @()
    if ($userHome) {
        $candidates += (Join-Path $userHome "miniconda3\envs\$envName\python.exe")
        $candidates += (Join-Path $userHome "anaconda3\envs\$envName\python.exe")
    }
    $candidates += "C:\ProgramData\miniconda3\envs\$envName\python.exe"
    $candidates += "C:\ProgramData\anaconda3\envs\$envName\python.exe"
    
    foreach ($path in $candidates) {
        $normalized = [System.IO.Path]::GetFullPath($path)
        if (Test-Path $normalized) { return $normalized }
    }
    
    # 4. Fallback to just "python" if nothing else matches
    return "python"
}


