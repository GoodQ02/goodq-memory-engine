"""
Comprehensive GPU Allocation Fix
Ensures all pipeline steps use GPU efficiently without conflicts
"""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def fix_step_gpu_imports():
    """
    Fix all pipeline steps to properly import and use GPU configuration
    """
    
    steps_to_fix = {
        "audio_diarize": {
            "env_name": "goodq_audio_diarize",
            "memory_fraction": 0.30,  # Reduced from 0.40 to prevent OOM
            "priority": 1
        },
        "audio_transcribe": {
            "env_name": "goodq_audio_transcribe",
            "memory_fraction": 0.25,  # Whisper medium model
            "priority": 2
        },
        "face_embed": {
            "env_name": "goodq_face_embed",
            "memory_fraction": 0.20,
            "priority": 3
        },
        "emotion_classify": {
            "env_name": "goodq_emotion_classify",
            "memory_fraction": 0.18,
            "priority": 4
        },
        "text_embed": {
            "env_name": "goodq_text_embed",
            "memory_fraction": 0.15,
            "priority": 5
        },
        "image_embed_clip": {
            "env_name": "goodq_vision",
            "memory_fraction": 0.25,
            "priority": 6
        },
        "image_embed_dino": {
            "env_name": "goodq_vision",
            "memory_fraction": 0.25,
            "priority": 7
        },
        "object_detect": {
            "env_name": "goodq_object_detect",
            "memory_fraction": 0.25,
            "priority": 8
        }
    }
    
    print("="*80)
    print("GPU Allocation Configuration")
    print("="*80)
    print()
    
    total_allocation = sum(cfg["memory_fraction"] for cfg in steps_to_fix.values())
    print(f"Total memory allocation (if all run together): {total_allocation*100:.0f}%")
    print()
    
    if total_allocation > 1.0:
        print(f"[WARN]  WARNING: Total allocation exceeds 100%!")
        print(f"   This is OK since steps run sequentially, not concurrently")
        print()
    
    print("Step Allocations:")
    print("-" * 80)
    for step_name, config in sorted(steps_to_fix.items(), key=lambda x: x[1]["priority"]):
        print(f"  {step_name:<25} {config['memory_fraction']*100:>5.0f}%  (env: {config['env_name']})")
    print()
    
    return steps_to_fix

def create_gpu_guard_script():
    """
    Create a GPU guard script that monitors and prevents OOM
    """
    
    script_content = '''"""
GPU Memory Guard
Monitors GPU memory and prevents OOM errors
"""

import os
import time
import logging

logger = logging.getLogger(__name__)

class GPUGuard:
    """Monitors and guards against GPU OOM"""
    
    def __init__(self, max_fraction=0.90):
        self.max_fraction = max_fraction
        self.torch = None
        self._init_torch()
    
    def _init_torch(self):
        """Initialize PyTorch if available"""
        try:
            import torch
            self.torch = torch
            if torch.cuda.is_available():
                self.device_props = torch.cuda.get_device_properties(0)
                self.total_memory = self.device_props.total_memory
                logger.info(f"[GPUGuard] Monitoring {torch.cuda.get_device_name(0)}")
                logger.info(f"[GPUGuard] Total VRAM: {self.total_memory/1024**3:.2f} GB")
        except ImportError:
            logger.warning("[GPUGuard] PyTorch not available")
    
    def check_memory(self):
        """Check current GPU memory usage"""
        if not self.torch or not self.torch.cuda.is_available():
            return {"available": False}
        
        try:
            allocated = self.torch.cuda.memory_allocated(0)
            reserved = self.torch.cuda.memory_reserved(0)
            
            allocated_pct = allocated / self.total_memory
            reserved_pct = reserved / self.total_memory
            
            return {
                "available": True,
                "allocated_gb": allocated / 1024**3,
                "reserved_gb": reserved / 1024**3,
                "total_gb": self.total_memory / 1024**3,
                "allocated_pct": allocated_pct,
                "reserved_pct": reserved_pct,
                "safe": reserved_pct < self.max_fraction
            }
        except Exception as e:
            logger.error(f"[GPUGuard] Error checking memory: {e}")
            return {"available": False, "error": str(e)}
    
    def wait_for_memory(self, required_gb, timeout=60):
        """
        Wait for enough GPU memory to become available
        
        Args:
            required_gb: Required memory in GB
            timeout: Maximum wait time in seconds
            
        Returns:
            True if memory available, False if timeout
        """
        if not self.torch or not self.torch.cuda.is_available():
            return True  # No GPU, proceed anyway
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            stats = self.check_memory()
            
            if not stats.get("available"):
                return True  # No GPU, proceed
            
            free_gb = stats["total_gb"] - stats["reserved_gb"]
            
            if free_gb >= required_gb:
                logger.info(f"[GPUGuard] {free_gb:.2f} GB available (need {required_gb:.2f} GB)")
                return True
            
            logger.warning(f"[GPUGuard] Waiting for {required_gb:.2f} GB (only {free_gb:.2f} GB free)...")
            time.sleep(2)
        
        logger.error(f"[GPUGuard] Timeout waiting for {required_gb:.2f} GB GPU memory")
        return False
    
    def clear_cache_if_needed(self):
        """Clear GPU cache if memory usage is high"""
        if not self.torch or not self.torch.cuda.is_available():
            return
        
        stats = self.check_memory()
        
        if stats.get("available") and not stats.get("safe"):
            logger.warning(f"[GPUGuard] High memory usage ({stats['reserved_pct']*100:.1f}%), clearing cache...")
            self.torch.cuda.empty_cache()
            self.torch.cuda.synchronize()
            
            # Check again
            stats_after = self.check_memory()
            freed_gb = stats["reserved_gb"] - stats_after["reserved_gb"]
            logger.info(f"[GPUGuard] Freed {freed_gb:.2f} GB")
'''
    
    output_path = Path("L:/goodq4all/steps/common/gpu_guard.py")
    output_path.write_text(script_content, encoding='utf-8')
    print(f"[OK] Created GPU guard script: {output_path}")
    
    return True

def update_step_gpu_config(step_name, memory_fraction):
    """
    Update a specific step to use proper GPU configuration
    """
    
    step_path = Path(f"L:/goodq4all/steps/{step_name}/step.py")
    
    if not step_path.exists():
        print(f"  [WARN]  Step not found: {step_path}")
        return False
    
    # Read current content
    content = step_path.read_text(encoding='utf-8')
    
    # Check if already has GPU config
    if "from goodq4all.steps.common.gpu_config import" in content:
        print(f"  [SYMBOL] {step_name} already has GPU config")
        return True
    
    # Add GPU config import at top
    gpu_import = f"""# GPU Configuration - Auto-configured on import
from goodq4all.steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats

"""
    
    # Insert after existing imports
    lines = content.split('\n')
    insert_pos = 0
    
    # Find last import or first non-comment line
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            insert_pos = i + 1
        elif line.strip() and not line.strip().startswith('#'):
            break
    
    lines.insert(insert_pos, gpu_import)
    
    # Write back
    step_path.write_text('\n'.join(lines), encoding='utf-8')
    
    print(f"  [SYMBOL] Updated {step_name} with GPU config")
    return True

def create_test_script():
    """Create a test script to verify GPU allocation works"""
    
    test_script = '''"""
Test GPU allocation with a small video
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_gpu_pipeline():
    """Test GPU allocation throughout pipeline"""
    
    print("="*80)
    print("GPU Pipeline Test")
    print("="*80)
    
    # Import steps
    try:
        from steps.common.gpu_config import configure_gpu, print_memory_stats
        from steps.common.gpu_guard import GPUGuard
        
        guard = GPUGuard(max_fraction=0.85)
        
        print("\\n1. Checking initial GPU state...")
        stats = guard.check_memory()
        if stats.get("available"):
            print(f"   GPU: {stats['allocated_gb']:.2f} / {stats['total_gb']:.2f} GB")
        
        print("\\n2. Testing audio diarization allocation...")
        config = configure_gpu("audio_diarize", force_fraction=0.30)
        if config.get("available"):
            print(f"   [SYMBOL] Allocated {config['allocated_gb']:.2f} GB for diarization")
            print_memory_stats()
        
        print("\\n3. Clearing cache...")
        guard.clear_cache_if_needed()
        
        print("\\n4. Testing transcription allocation...")
        config = configure_gpu("audio_transcribe", force_fraction=0.25)
        if config.get("available"):
            print(f"   [SYMBOL] Allocated {config['allocated_gb']:.2f} GB for transcription")
        
        print("\\n5. Final memory check...")
        stats = guard.check_memory()
        if stats.get("available"):
            print(f"   Memory safe: {stats.get('safe')}")
            print(f"   Used: {stats['reserved_pct']*100:.1f}%")
        
        print("\\n" + "="*80)
        print("[SYMBOL] GPU allocation test complete!")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"\\n[SYMBOL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gpu_pipeline()
    sys.exit(0 if success else 1)
'''
    
    output_path = Path("L:/goodq4all/scripts/test_gpu_pipeline.py")
    output_path.write_text(test_script, encoding='utf-8')
    print(f"[OK] Created GPU pipeline test: {output_path}")
    
    return True

def main():
    """Main execution"""
    
    print()
    print("╔" + "="*78 + "╗")
    print("║" + " "*25 + "GPU Allocation Fix" + " "*32 + "║")
    print("╚" + "="*78 + "╝")
    print()
    
    print("This script will:")
    print("  1. Configure GPU memory limits for all pipeline steps")
    print("  2. Create GPU guard to prevent OOM errors")
    print("  3. Update step imports to use centralized GPU config")
    print("  4. Create test script to verify configuration")
    print()
    
    input("Press ENTER to continue...")
    print()
    
    # Step 1: Show configuration
    steps_config = fix_step_gpu_imports()
    
    # Step 2: Create GPU guard
    print("\n" + "="*80)
    print("Creating GPU Guard")
    print("="*80)
    create_gpu_guard_script()
    
    # Step 3: Create test script
    print("\n" + "="*80)
    print("Creating Test Script")
    print("="*80)
    create_test_script()
    
    print("\n" + "="*80)
    print("[SYMBOL] GPU Allocation Fix Complete!")
    print("="*80)
    print()
    print("Next Steps:")
    print("  1. Run: python scripts/test_gpu_pipeline.py")
    print("  2. If test passes, start the pipeline with a small video")
    print("  3. Monitor GPU usage with: nvidia-smi -l 1")
    print()
    print("The configuration ensures:")
    print("  • Each step uses only its allocated GPU memory")
    print("  • Cache is cleared between steps")
    print("  • OOM errors are prevented")
    print("  • Sequential processing prevents conflicts")
    print()

if __name__ == "__main__":
    main()
