#!/usr/bin/env bash
# GoodQ4All - Native Unix Bootstrap Installer for macOS & Linux

set -e

# Parse arguments
CHECK_ONLY=0
SKIP_PREFETCH=0
SKIP_STEP_ENVS=0
NO_START=0

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --check-only) CHECK_ONLY=1 ;;
        --skip-model-prefetch) SKIP_PREFETCH=1 ;;
        --skip-step-envs) SKIP_STEP_ENVS=1 ;;
        --no-start) NO_START=1 ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Resolve project root robustly
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# OS Detection
OS_TYPE="$(uname -s | tr '[:upper:]' '[:lower:]')"
echo "[BOOTSTRAP] Sourced Platform: $OS_TYPE"

# 1. Dependency Check
echo "================================================================================"
echo "  [1/6] System Dependency Preflight Check"
echo "================================================================================"

check_dep() {
    local name="$1"
    local cmd="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "  [PASS] $name is available ($(command -v "$cmd"))"
        return 0
    else
        echo "  [FAIL] $name ($cmd) is missing!"
        return 1
    fi
}

DEPS_FAIL=0
check_dep "Conda" "conda" || DEPS_FAIL=1
check_dep "FFmpeg" "ffmpeg" || DEPS_FAIL=1
check_dep "Poppler (pdftotext)" "pdftotext" || DEPS_FAIL=1
check_dep "Tesseract OCR" "tesseract" || DEPS_FAIL=1

# Check for Qdrant either system-wide or in vendor/
if command -v qdrant >/dev/null 2>&1; then
    echo "  [PASS] Qdrant database is available in system PATH"
elif [ -f "$PROJECT_ROOT/vendor/qdrant/qdrant" ]; then
    echo "  [PASS] Qdrant database is available in vendor/ folder"
else
    echo "  [FAIL] Qdrant database is missing! Install via brew/apt or place in vendor/qdrant/"
    DEPS_FAIL=1
fi

# Go compiler is optional for launcher compile warning
GO_AVAILABLE=0
if command -v go >/dev/null 2>&1; then
    echo "  [PASS] Go compiler is available (optional)"
    GO_AVAILABLE=1
else
    echo "  [INFO] Go compiler is missing (optional; needed if compiling launcher from source)"
fi

if [ $DEPS_FAIL -eq 1 ]; then
    echo "[BOOTSTRAP] [ERROR] Some critical system dependencies are missing."
    if [ "$OS_TYPE" = "darwin" ]; then
        echo "Please run: brew install ffmpeg poppler tesseract qdrant"
    else
        echo "Please run: sudo apt install ffmpeg poppler-utils tesseract-ocr qdrant"
    fi
    exit 1
fi

if [ $CHECK_ONLY -eq 1 ]; then
    echo "[BOOTSTRAP] Check-only mode active. All dependencies verified. Exiting."
    exit 0
fi

# 2. PyTorch GPU Availability Check (Linux)
GPU_AVAILABLE=0
if [ "$OS_TYPE" = "linux" ]; then
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
        echo "[BOOTSTRAP] NVIDIA GPU detected via nvidia-smi."
        GPU_AVAILABLE=1
    else
        echo "[BOOTSTRAP] No NVIDIA GPU detected. Using CPU-only configuration."
    fi
fi

# 3. Create/Update Core Conda Environment (goodq_core)
echo ""
echo "================================================================================"
echo "  [2/6] Provisioning Core Conda Environment (goodq_core)"
echo "================================================================================"

ENV_EXISTS=$(conda env list | grep -w "goodq_core" || true)

if [ "$OS_TYPE" = "darwin" ]; then
    echo "[BOOTSTRAP] Creating goodq_core for macOS (Apple Silicon/MPS)..."
    if [ -z "$ENV_EXISTS" ]; then
        conda create -y -n goodq_core python=3.10
    fi
    # Install dependencies without cpuonly, install torch stack natively
    conda run -n goodq_core pip install numpy pandas pyyaml python-dotenv requests fastapi uvicorn typer pytest imageio-ffmpeg transformers sentence-transformers qdrant-client faster-whisper faiss-cpu
    conda run -n goodq_core pip install torch torchvision torchaudio
    conda run -n goodq_core pip install -e .
else
    # Linux
    if [ $GPU_AVAILABLE -eq 1 ]; then
        echo "[BOOTSTRAP] Creating goodq_core for Linux with GPU..."
        if [ -z "$ENV_EXISTS" ]; then
            conda env create -f environment.gpu.yml
        else
            conda env update -f environment.gpu.yml
        fi
    else
        echo "[BOOTSTRAP] Creating goodq_core for Linux with CPU..."
        if [ -z "$ENV_EXISTS" ]; then
            conda env create -f environment.yml
        else
            conda env update -f environment.yml
        fi
    fi
fi
echo "[BOOTSTRAP] Core environment goodq_core is ready."

# 4. Provision Step Environments
if [ $SKIP_STEP_ENVS -eq 0 ]; then
    echo ""
    echo "================================================================================"
    echo "  [3/6] Provisioning Isolated Step Environments"
    echo "================================================================================"

    STEP_ENVS=(
        "goodq_video_scene_detect:video_scene_detect:1"
        "goodq_image_caption:image_caption:1"
        "goodq_object_detect:object_detect:1"
        "goodq_face_embed:face_embed:1"
        "goodq_text_embed:text_embed:1"
        "goodq_audio_metadata:audio_metadata:0"
        "goodq_audio_transcribe:audio_transcribe:1"
        "goodq_audio_diarize:audio_diarize:1"
        "goodq_audio_emotion:audio_emotion:1"
        "goodq_audio_embed:audio_embed:1"
        "goodq_tagger:tagger:1"
        "goodq_sentiment:sentiment:1"
        "goodq_emotion_classify:emotion_classify:1"
        "goodq_llm_chat:llm_chat:0"
    )

    for step_spec in "${STEP_ENVS[@]}"; do
        IFS=":" read -r env_name folder_name needs_torch <<< "$step_spec"
        echo "[BOOTSTRAP] Ensuring env $env_name..."
        
        STEP_ENV_EXISTS=$(conda env list | grep -w "$env_name" || true)
        if [ -z "$STEP_ENV_EXISTS" ]; then
            conda create -y -n "$env_name" python=3.10
        fi

        # Install dependencies
        REQ_PATH="envs/$folder_name/requirements.txt"
        LOCK_PATH="envs/locks/$folder_name.lock.txt"
        
        # Determine the source surface: use lock file if available, otherwise requirements
        INSTALL_SOURCE="$REQ_PATH"
        if [ -f "$LOCK_PATH" ]; then
            # Filter out torch/numpy pins from lock file on macOS to prevent CUDA wheel pull attempts
            if [ "$OS_TYPE" = "darwin" ]; then
                INSTALL_SOURCE="envs/locks/${folder_name}_filtered.lock.txt"
                grep -vE "^(torch|torchvision|torchaudio)" "$LOCK_PATH" > "$INSTALL_SOURCE"
            else
                INSTALL_SOURCE="$LOCK_PATH"
            fi
        fi

        # Install base requirements
        if [ -f "$INSTALL_SOURCE" ]; then
            # Vision/audio/NLP dependencies can have conflicting sub-dependencies, install cleanly
            conda run -n "$env_name" pip install --no-cache-dir -r "$INSTALL_SOURCE"
            if [ "$OS_TYPE" = "darwin" ] && [ -f "envs/locks/${folder_name}_filtered.lock.txt" ]; then
                rm -f "envs/locks/${folder_name}_filtered.lock.txt"
            fi
        fi

        # Install specialized torch stack if needed
        if [ "$needs_torch" -eq 1 ]; then
            if [ "$OS_TYPE" = "darwin" ]; then
                conda run -n "$env_name" pip install torch torchvision torchaudio
            else
                if [ $GPU_AVAILABLE -eq 1 ]; then
                    conda run -n "$env_name" pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
                else
                    conda run -n "$env_name" pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
                fi
            fi
        fi
        
        # Fix numpy compatibility issue for faiss/clip dependencies
        if [[ "$env_name" =~ (image_caption|audio_embed|text_embed) ]]; then
            conda run -n "$env_name" pip install faiss-cpu==1.9.0
        fi
        
        echo "[BOOTSTRAP] Step env $env_name is ready."
    done
else
    echo "[BOOTSTRAP] Skipping step environments provisioning."
fi

# 5. Prefetch model weights
if [ $SKIP_PREFETCH -eq 0 ]; then
    echo ""
    echo "================================================================================"
    echo "  [4/6] Prefetching Model Cache Weights"
    echo "================================================================================"
    conda run -n goodq_core python scripts/bootstrap_models.py
else
    echo "[BOOTSTRAP] Skipping model prefetch as requested."
fi

# 6. Go Launcher compilation
echo ""
echo "================================================================================"
echo "  [5/6] Building Go Launcher Supervisor"
echo "================================================================================"
if [ $GO_AVAILABLE -eq 1 ]; then
    echo "[BOOTSTRAP] Compiling Go launcher supervisor..."
    go build -o LAUNCH_GOODQ scripts/install/LAUNCH_GOODQ.go scripts/install/launcher_unix.go
    echo "[BOOTSTRAP] [OK] LAUNCH_GOODQ compiled successfully."
else
    echo "[BOOTSTRAP] [WARN] 'go' compiler not found. Skipping compilation of LAUNCH_GOODQ."
    echo "[BOOTSTRAP] [WARN] You can compile it manually later using:"
    echo "  go build -o LAUNCH_GOODQ scripts/install/LAUNCH_GOODQ.go scripts/install/launcher_unix.go"
fi

# 7. Preflight verification
echo ""
echo "================================================================================"
echo "  [6/6] Running Bootstrap Verification Checks"
echo "================================================================================"
conda run -n goodq_core python scripts/bootstrap_verify.py --profile desktop

echo ""
echo "================================================================================"
echo "  Bootstrap Complete! GoodQ4All is ready on your Unix platform."
echo "================================================================================"
echo "To start services:"
echo "  ./dev_on.sh"
echo "To stop services:"
echo "  ./dev_off.sh"
echo ""
