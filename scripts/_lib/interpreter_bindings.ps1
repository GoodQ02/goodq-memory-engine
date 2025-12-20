# Shared interpreter binding helpers for GoodQ4All scripts.
# Keeps launcher behavior deterministic across PATH / shell-state drift.

function Get-GoodQWslDistro {
    $distro = $env:GOODQ_WSL_DISTRO
    if ([string]::IsNullOrWhiteSpace($distro)) {
        return "Ubuntu"
    }
    return $distro
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
