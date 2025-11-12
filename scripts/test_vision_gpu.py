"""Test Vision GPU Setup"""
import torch
import sys

def test_gpu():
    print(f"PyTorch Version: {torch.__version__}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Device Count: {torch.cuda.device_count()}")
        
        # Test tensor on GPU
        try:
            x = torch.rand(3, 3).cuda()
            print(f"✓ GPU tensor creation successful")
            print(f"  Device: {x.device}")
            return 0
        except Exception as e:
            print(f"✗ GPU tensor creation failed: {e}")
            return 1
    else:
        print("✗ CUDA not available")
        return 1

if __name__ == "__main__":
    sys.exit(test_gpu())
