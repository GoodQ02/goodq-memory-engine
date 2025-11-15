#!/usr/bin/env python3
"""
GoodQ4All WSL2 Audio Processor
Runs inside WSL2 to process audio with GPU acceleration
"""

import sys
import json
import torch
from pathlib import Path

def main():
    """Main processing function"""
    
    # Check CUDA availability
    if not torch.cuda.is_available():
        print(json.dumps({
            "error": "CUDA not available",
            "cuda_available": False
        }))
        sys.exit(1)
    
    # Print system info
    info = {
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_count": torch.cuda.device_count(),
        "status": "ready"
    }
    
    print(json.dumps(info, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
