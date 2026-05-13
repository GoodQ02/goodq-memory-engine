# GoodQ4All GPU Configuration
# This file is read by pipeline steps to configure GPU usage

import os

# GPU Device Selection
os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Use first GPU only

# GPU Memory Fractions per Environment
GPU_MEMORY_LIMITS = {
    "goodq_audio_diarize": 0.25,  # Audio diarization (reduced for vision)
    "goodq_audio_transcribe": 0.20,  # Whisper transcription
    "goodq_emotion_classify": 0.18,  # Emotion classification
    "goodq_face_embed": 0.20,  # Face embeddings
    "goodq_image_caption": 0.20,  # BLIP captioning / shared image env
    "goodq_object_detect": 0.25,  # Object detection (YOLO)
    "goodq_ocr": 0.20,  # OCR
    "goodq_text_embed": 0.15,  # Text embeddings
}

STEP_MEMORY_LIMITS = {
    "image_caption": 0.20,  # BLIP or fallback image captioning
    "image_embed_clip": 0.25,  # CLIP ViT
    "image_embed_dino": 0.25,  # DINOv2
}

# Apply memory limit for current environment
def configure_gpu_memory():
    '''Call this at the start of each step to configure GPU memory'''
    import torch
    env_name = os.environ.get('CONDA_DEFAULT_ENV', 'unknown')
    
    if env_name in GPU_MEMORY_LIMITS:
        fraction = GPU_MEMORY_LIMITS[env_name]
        torch.cuda.set_per_process_memory_fraction(fraction, 0)
        print(f"[GPU] Configured {env_name} to use {fraction*100:.0f}% of GPU memory")
    
    # Enable memory growth
    torch.backends.cudnn.benchmark = True
    
    # Verify CUDA is available
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        total_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"[GPU] Using {device_name} ({total_memory:.1f} GB total memory)")
        return True
    else:
        print("[GPU] WARNING: CUDA not available, falling back to CPU")
        return False

def setup_step_gpu(step_name):
    '''Setup GPU configuration for a specific step'''
    import torch
    
    # Map step names to environment names
    step_to_env = {
        "audio_diarize": "goodq_audio_diarize",
        "audio_transcribe": "goodq_audio_transcribe",
        "emotion_classify": "goodq_emotion_classify",
        "face_embed": "goodq_face_embed",
        "image_caption": "goodq_image_caption",
        "image_embed_clip": "goodq_image_caption",
        "image_embed_dino": "goodq_image_caption",
        "object_detect": "goodq_object_detect",
        "ocr": "goodq_ocr",
        "text_embed": "goodq_text_embed",
    }
    
    env_name = step_to_env.get(step_name, os.environ.get('CONDA_DEFAULT_ENV', 'unknown'))
    fraction = STEP_MEMORY_LIMITS.get(step_name, GPU_MEMORY_LIMITS.get(env_name, 0.15))
    
    # Determine device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Configure memory if using GPU
    if device == "cuda":
        try:
            torch.cuda.set_per_process_memory_fraction(fraction, 0)
            torch.backends.cudnn.benchmark = True
        except Exception as e:
            print(f"[GPU] WARNING: Failed to configure GPU memory: {e}")
    
    return {
        "device": device,
        "step_name": step_name,
        "memory_fraction": fraction,
        "env_name": env_name
    }

class GPUManager:
    '''Centralized GPU management utilities'''
    
    @staticmethod
    def clear_cache():
        '''Clear GPU cache to free memory'''
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception:
            pass
    
    @staticmethod
    def get_memory_info():
        '''Get current GPU memory usage'''
        try:
            import torch
            if not torch.cuda.is_available():
                return {"available": False}
            
            allocated = torch.cuda.memory_allocated(0) / 1024**3
            reserved = torch.cuda.memory_reserved(0) / 1024**3
            total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            
            return {
                "available": True,
                "allocated_gb": allocated,
                "reserved_gb": reserved,
                "total_gb": total,
                "free_gb": total - allocated
            }
        except Exception:
            return {"available": False}
    
    @staticmethod
    def reset_peak_stats():
        '''Reset peak memory statistics'''
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats(0)
        except Exception:
            pass
