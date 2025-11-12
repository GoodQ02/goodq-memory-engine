# GoodQ4All GPU Configuration
# This file is read by pipeline steps to configure GPU usage

import os

# GPU Device Selection
os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # Use first GPU only

# GPU Memory Fractions per Environment
GPU_MEMORY_LIMITS = {
    "goodq_audio_diarize": 0.3,  # Audio diarization (speaker detection)
    "goodq_audio_transcribe": 0.25,  # Whisper transcription
    "goodq_emotion_classify": 0.15,  # Emotion classification
    "goodq_face_embed": 0.15,  # Face embeddings
    "goodq_text_embed": 0.15,  # Text embeddings
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
