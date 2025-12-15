#!/bin/bash
# vLLM Server Environment Activation Script

# Get the directory where this script is located
VLLM_SERVER_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate Python virtual environment
if [ -f "$VLLM_SERVER_DIR/venv/bin/activate" ]; then
    source "$VLLM_SERVER_DIR/venv/bin/activate"
    echo "✅ Virtual environment activated"
else
    echo "❌ ERROR: Virtual environment not found at $VLLM_SERVER_DIR/venv"
    return 1
fi

# Set environment variables
export VLLM_SERVER_DIR="$VLLM_SERVER_DIR"
export VLLM_MODELS_DIR="$VLLM_SERVER_DIR/models"
export VLLM_CONFIGS_DIR="$VLLM_SERVER_DIR/configs"
export VLLM_LOGS_DIR="$VLLM_SERVER_DIR/logs"

# CUDA and GPU settings
export CUDA_VISIBLE_DEVICES=0
export VLLM_WORKER_MULTIPROC_METHOD=spawn

# Set cuDNN library path (if needed)
CUDNN_LIB_PATH="$VIRTUAL_ENV/lib/python3.12/site-packages/nvidia/cudnn/lib"
if [ -d "$CUDNN_LIB_PATH" ]; then
    export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$CUDNN_LIB_PATH"
fi

# HuggingFace settings (optional)
# export HF_HOME="$VLLM_SERVER_DIR/.cache/huggingface"
# export HF_TOKEN="your_token_here"  # Set this if you need private models

echo "Environment variables set:"
echo "  VLLM_SERVER_DIR=$VLLM_SERVER_DIR"
echo "  VLLM_MODELS_DIR=$VLLM_MODELS_DIR"
echo "  CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
echo ""
echo "vLLM Server environment ready!"
echo "Python: $(python --version)"
echo "vLLM: $(python -c 'import vllm; print(vllm.__version__)' 2>/dev/null || echo 'Not found')"
echo ""
echo "Quick commands:"
echo "  vllm serve <model>           - Start vLLM server"
echo "  python scripts/start.py      - Start with config file"
echo "  deactivate                   - Exit virtual environment"
