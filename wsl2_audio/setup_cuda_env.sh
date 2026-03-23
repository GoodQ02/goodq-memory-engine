#!/bin/bash
# CUDA/cuDNN Environment Setup for GoodQ Audio Processing
# Source this script to properly configure CUDA libraries

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.goodq_env"
VENV_DIR="$SCRIPT_DIR/venv"

if [ ! -f "$VENV_DIR/bin/activate" ] && [ -f "$SCRIPT_DIR/env/bin/activate" ]; then
    VENV_DIR="$SCRIPT_DIR/env"
fi

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "✗ Missing virtual environment activation script: $VENV_DIR/bin/activate" >&2
    return 1 2>/dev/null || exit 1
fi

# Activate the virtual environment
source "$VENV_DIR/bin/activate"

PYTHON_TAG="$(python -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
NVIDIA_LIB_ROOT="$VENV_DIR/lib/$PYTHON_TAG/site-packages/nvidia"

# Add NVIDIA libraries to LD_LIBRARY_PATH
CUDNN_LIB_PATH="$NVIDIA_LIB_ROOT/cudnn/lib"
CUBLAS_LIB_PATH="$NVIDIA_LIB_ROOT/cublas/lib"
CUDA_NVRTC_LIB_PATH="$NVIDIA_LIB_ROOT/cuda_nvrtc/lib"
CUDA_RUNTIME_LIB_PATH="$NVIDIA_LIB_ROOT/cuda_runtime/lib"

# Export LD_LIBRARY_PATH with all NVIDIA library paths
export LD_LIBRARY_PATH="$CUDNN_LIB_PATH:$CUBLAS_LIB_PATH:$CUDA_NVRTC_LIB_PATH:$CUDA_RUNTIME_LIB_PATH:${LD_LIBRARY_PATH:-}"

# Export HuggingFace token
# Priority: 1) Use existing HF_TOKEN, 2) Retrieve from HF cache
if [ -z "${HF_TOKEN:-}" ] && [ -z "${HUGGINGFACE_TOKEN:-}" ]; then
    # No token in environment, try to retrieve from HF cache
    if command -v python3 &> /dev/null; then
        RETRIEVED_TOKEN=$(python3 -c "from huggingface_hub import HfFolder; token = HfFolder.get_token(); print(token if token else '')" 2>/dev/null)
        if [ -n "$RETRIEVED_TOKEN" ]; then
            export HF_TOKEN="$RETRIEVED_TOKEN"
            export HUGGINGFACE_TOKEN="$RETRIEVED_TOKEN"
        fi
    fi
else
    # Token already in environment, ensure both vars are set
    if [ -n "${HF_TOKEN:-}" ] && [ -z "${HUGGINGFACE_TOKEN:-}" ]; then
        export HUGGINGFACE_TOKEN="$HF_TOKEN"
    elif [ -n "${HUGGINGFACE_TOKEN:-}" ] && [ -z "${HF_TOKEN:-}" ]; then
        export HF_TOKEN="$HUGGINGFACE_TOKEN"
    fi
fi

echo "✓ CUDA/cuDNN environment configured" >&2
echo "  - LD_LIBRARY_PATH set with NVIDIA libraries" >&2
echo "  - Virtual environment activated" >&2
echo "" >&2
echo "Test CUDA availability with:" >&2
echo "  python3 -c \"import torch; print(f'CUDA: {torch.cuda.is_available()}')\"" >&2
