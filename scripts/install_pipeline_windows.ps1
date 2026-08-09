# GoodQ4All – 00Q Pipeline Installer (Windows)
# --------------------------------------------
# Creates/fixes all conda envs, pins CUDA 12.1 torch stacks, installs FAISS 1.9.0,
# and runs smoke tests (torch CUDA + FAISS). Idempotent; rerun anytime.

$ErrorActionPreference = "Stop"

# Locate conda
$CondaExe = Join-Path $env:USERPROFILE "miniconda3\Scripts\conda.exe"
if (-not (Test-Path $CondaExe)) { $CondaExe = "conda" }

function LogQ($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[00Q][$ts] $msg" -ForegroundColor Cyan
}

function EnvExists($name) {
    $list = & $CondaExe env list
    return $list -match "(\s|^)$name(\s|$)"
}

function EnsureEnv($name, $py) {
    if (EnvExists $name) {
        LogQ "Env present: $name"
        return
    }
    LogQ "Creating env $name (python=$py)"
    & $CondaExe create -y -n $name "python=$py" | Out-Null
}

function RunEnv($name, $cmd) {
    & $CondaExe run -n $name $cmd
}

function InstallReqs($name, $reqPath, $skipFaiss) {
    if (-not (Test-Path $reqPath)) {
        LogQ "Skip (missing reqs): $reqPath"
        return
    }
    LogQ "Installing requirements for $name from $reqPath"
    # Install without deps; torch/faiss handled separately.
    RunEnv $name "pip install --no-cache-dir --no-deps -r `"$reqPath`""
    if ($skipFaiss) {
        LogQ "Installing FAISS 1.9.0 for $name"
        RunEnv $name "pip install --no-cache-dir faiss-cpu==1.9.0"
    }
}

function InstallTorch($name) {
    LogQ "Installing CUDA 12.1 torch stack for $name"
    RunEnv $name "pip uninstall -y torch torchvision torchaudio"
    RunEnv $name "pip install --no-cache-dir torch==2.3.1+cu121 torchvision==0.18.1+cu121 torchaudio==2.3.1 --extra-index-url https://download.pytorch.org/whl/cu121"
    RunEnv $name "pip install --no-cache-dir numpy==2.2.6 pillow==12.0.0"
    # Smoke
    RunEnv $name "python - <<'PY'`nimport torch`nprint('torch', torch.__version__, 'cuda?', torch.cuda.is_available())`nPY"
}

function Smoke($name, $needsTorch, $needsFaiss) {
    LogQ "Smoke tests for $name"
    if ($needsTorch) {
        RunEnv $name "python - <<'PY'`nimport torch`nprint('torch', torch.__version__, 'cuda?', torch.cuda.is_available())`nPY"
        if ($name -eq "goodq_audio_embed") {
            RunEnv $name "python - <<'PY'`nimport torchaudio`nprint('torchaudio', torchaudio.__version__)`nPY"
        }
    }
    if ($needsFaiss) {
        RunEnv $name "python - <<'PY'`nimport faiss, numpy as np`nprint('faiss', faiss.__version__, 'numpy', np.__version__)`nPY"
    }
}

function EnsureCoreFallbackDependency() {
    $coreEnv = if ([string]::IsNullOrWhiteSpace($env:GOODQ_CONDA_ENV)) { "goodq_core" } else { $env:GOODQ_CONDA_ENV }
    if (-not (EnvExists $coreEnv)) {
        LogQ "Core env missing ($coreEnv); skipping faster-whisper fallback provisioning"
        return
    }
    LogQ "Ensuring faster-whisper for local BASELINE transcription fallback in $coreEnv"
    RunEnv $coreEnv "pip install --no-cache-dir faster-whisper==1.0.3"
    RunEnv $coreEnv "python - <<'PY'`nimport importlib.util as u`nprint('faster_whisper', u.find_spec('faster_whisper') is not None)`nPY"
}

# Env matrix
$envs = @(
    @{ name="goodq_video_scene_detect"; py="3.12"; req="envs/video_scene_detect/requirements.txt"; torch=$true; faiss=$false },
    @{ name="goodq_face_embed"; py="3.12"; req="envs/face_embed/requirements.txt"; torch=$true; faiss=$false },
    @{ name="goodq_image_caption"; py="3.12"; req="envs/image_caption/requirements.txt"; torch=$true; faiss=$true },
      @{ name="goodq_object_detect"; py="3.12"; req="envs/object_detect/requirements.txt"; torch=$false; faiss=$false },
    @{ name="goodq_object_track"; py="3.12"; req="envs/object_track_yolo/requirements.txt"; torch=$true; faiss=$false },
    @{ name="goodq_audio_diarize"; py="3.12"; req="envs/audio_diarize/requirements.txt"; torch=$true; faiss=$false },
    @{ name="goodq_audio_transcribe"; py="3.12"; req="envs/audio_transcribe/requirements.txt"; torch=$true; faiss=$false },
    @{ name="goodq_audio_emotion"; py="3.12"; req="envs/audio_emotion/requirements.txt"; torch=$true; faiss=$false },
    @{ name="goodq_audio_embed"; py="3.12"; req="envs/audio_embed/requirements.txt"; torch=$true; faiss=$true },
    @{ name="goodq_audio_metadata"; py="3.12"; req="envs/audio_metadata/requirements.txt"; torch=$false; faiss=$false },
    @{ name="goodq_text_embed"; py="3.12"; req="envs/text_embed/requirements.txt"; torch=$true; faiss=$true },
    @{ name="goodq_tagger"; py="3.12"; req="envs/tagger/requirements.txt"; torch=$true; faiss=$false },
    @{ name="goodq_sentiment"; py="3.12"; req="envs/sentiment/requirements.txt"; torch=$true; faiss=$false },
    @{ name="goodq_emotion_classify"; py="3.12"; req="envs/emotion_classify/requirements.txt"; torch=$true; faiss=$false },
    @{ name="goodq_llm_chat"; py="3.12"; req="envs/llm_chat/requirements.txt"; torch=$false; faiss=$false },
    @{ name="goodq_tts"; py="3.12"; req="envs/tts/requirements.txt"; torch=$false; faiss=$false },
    @{ name="goodq_ocr"; py="3.12"; req="envs/ocr/requirements.txt"; torch=$false; faiss=$false },
    @{ name="goodq_pdf_text"; py="3.12"; req="envs/pdf_text/requirements.txt"; torch=$false; faiss=$false },
    @{ name="goodq_system_metrics"; py="3.12"; req="envs/system_metrics/requirements.txt"; torch=$false; faiss=$false },
    @{ name="goodq_home_assistant_status"; py="3.12"; req="envs/home_assistant_status/requirements.txt"; torch=$false; faiss=$false }
)

LogQ "Starting 00Q Windows pipeline install"
foreach ($env in $envs) {
    $name = $env.name
    $py = $env.py
    $req = $env.req
    $needsTorch = [bool]$env.torch
    $needsFaiss = [bool]$env.faiss

    try {
        EnsureEnv $name $py
        InstallReqs $name $req $needsFaiss
        if ($needsTorch) { InstallTorch $name }
        Smoke $name $needsTorch $needsFaiss
        LogQ "✅ Complete: $name"
    } catch {
        LogQ "❌ $name failed: $_"
        continue
    }
}

EnsureCoreFallbackDependency

LogQ "All done. Rerun anytime for self-heal."
