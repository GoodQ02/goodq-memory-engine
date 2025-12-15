#!/bin/bash
# CUDA/cuDNN Environment Setup for GoodQ Audio Processing
# Source this script to properly configure CUDA libraries

# Add NVIDIA cuDNN libraries to LD_LIBRARY_PATH
CUDNN_LIB_PATH="$HOME/goodq_audio/venv/lib/python3.12/site-packages/nvidia/cudnn/lib"
CUBLAS_LIB_PATH="$HOME/goodq_audio/venv/lib/python3.12/site-packages/nvidia/cublas/lib"
CUDA_NVRTC_LIB_PATH="$HOME/goodq_audio/venv/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib"
CUDA_RUNTIME_LIB_PATH="$HOME/goodq_audio/venv/lib/python3.12/site-packages/nvidia/cuda_runtime/lib"

# Export LD_LIBRARY_PATH with all NVIDIA library paths
export LD_LIBRARY_PATH="$CUDNN_LIB_PATH:$CUBLAS_LIB_PATH:$CUDA_NVRTC_LIB_PATH:$CUDA_RUNTIME_LIB_PATH:${LD_LIBRARY_PATH:-}"

# Activate the virtual environment
source "$HOME/goodq_audio/venv/bin/activate"

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
