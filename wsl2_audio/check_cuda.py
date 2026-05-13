#!/usr/bin/env python3
"""
CUDA/cuDNN Diagnostic Script for GoodQ Audio Processing
Run this to verify CUDA, cuDNN, and all audio processing libraries are working correctly.
"""

import sys
import os

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def check_cuda():
    print_header("CUDA & cuDNN Status")
    try:
        import torch
        print(f"✓ PyTorch version: {torch.__version__}")
        print(f"✓ CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"✓ CUDA version: {torch.version.cuda}")
            print(f"✓ cuDNN version: {torch.backends.cudnn.version()}")
            print(f"✓ cuDNN enabled: {torch.backends.cudnn.enabled}")
            print(f"✓ GPU count: {torch.cuda.device_count()}")
            print(f"✓ Current device: {torch.cuda.current_device()}")
            print(f"✓ Device name: {torch.cuda.get_device_name(0)}")
            
            # Test CUDA operation
            x = torch.randn(10, 10).cuda()
            y = x @ x.T
            print(f"✓ CUDA tensor operation: SUCCESS")
            
            # Test cuDNN operation
            conv = torch.nn.Conv2d(3, 64, 3).cuda()
            x = torch.randn(1, 3, 224, 224).cuda()
            y = conv(x)
            print(f"✓ cuDNN convolution: SUCCESS")
        else:
            print("✗ CUDA not available")
            return False
    except Exception as e:
        print(f"✗ CUDA check failed: {e}")
        return False
    return True

def check_libraries():
    print_header("Audio Processing Libraries")
    
    libraries = [
        ("torchaudio", "torchaudio"),
        ("faster-whisper", "faster_whisper"),
        ("pyannote.audio", "pyannote.audio"),
        ("transformers", "transformers"),
        ("librosa", "librosa"),
        ("soundfile", "soundfile"),
    ]
    
    all_ok = True
    for name, module in libraries:
        try:
            mod = __import__(module)
            version = getattr(mod, '__version__', 'unknown')
            print(f"✓ {name}: {version}")
        except ImportError as e:
            print(f"✗ {name}: NOT INSTALLED")
            all_ok = False
        except Exception as e:
            print(f"✗ {name}: ERROR - {e}")
            all_ok = False
    
    return all_ok

def check_environment():
    print_header("Environment Variables")
    
    ld_lib_path = os.environ.get('LD_LIBRARY_PATH', 'Not set')
    print(f"LD_LIBRARY_PATH:")
    if ld_lib_path != 'Not set':
        for path in ld_lib_path.split(':'):
            if path:
                print(f"  - {path}")
    else:
        print(f"  {ld_lib_path}")
    
    print(f"\nVIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'Not set')}")

def check_cudnn_libraries():
    print_header("cuDNN Library Files")
    
    import torch
    venv_path = os.environ.get('VIRTUAL_ENV', '')
    if venv_path:
        cudnn_lib_path = os.path.join(venv_path, 'lib/python3.12/site-packages/nvidia/cudnn/lib')
        if os.path.exists(cudnn_lib_path):
            libs = [f for f in os.listdir(cudnn_lib_path) if f.startswith('libcudnn')]
            print(f"Found {len(libs)} cuDNN libraries in:")
            print(f"  {cudnn_lib_path}")
            for lib in sorted(libs):
                print(f"  - {lib}")
        else:
            print(f"✗ cuDNN library directory not found: {cudnn_lib_path}")
    else:
        print("✗ VIRTUAL_ENV not set")

def main():
    print(f"\n{'#'*60}")
    print(f"  GoodQ Audio Processing - CUDA/cuDNN Diagnostic")
    print(f"{'#'*60}")
    
    cuda_ok = check_cuda()
    libs_ok = check_libraries()
    check_environment()
    check_cudnn_libraries()
    
    print_header("Summary")
    if cuda_ok and libs_ok:
        print("✓ All checks passed! Your environment is ready for audio processing.")
        return 0
    else:
        print("✗ Some checks failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
