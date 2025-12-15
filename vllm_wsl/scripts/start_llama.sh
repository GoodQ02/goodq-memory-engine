#!/bin/bash
# Start vLLM server with Llama 3.2 3B Instruct
# NOTE: Requires HF token and model download first

echo "═══════════════════════════════════════════════════════════════"
echo "⚠️  Llama 3.2 3B not downloaded"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "This model requires:"
echo "1. HuggingFace account with license acceptance"
echo "2. HF_TOKEN environment variable set"
echo ""
echo "To download:"
echo "  export HF_TOKEN='your_token'"
echo "  python3 -c 'from huggingface_hub import snapshot_download; \\"
echo "    snapshot_download(\"meta-llama/Llama-3.2-3B-Instruct\", \\"
echo "    local_dir=\"/mnt/l/_DATA/models/llm/huggingface/Llama-3.2-3B-Instruct\")'"
echo ""
echo "License: https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct"
echo "═══════════════════════════════════════════════════════════════"
