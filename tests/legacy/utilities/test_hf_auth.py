"""
Test HuggingFace authentication and model downloading
"""
import os
import sys
from pathlib import Path

def model_cache_root() -> Path:
    explicit = os.environ.get("GOODQ_MODEL_CACHE_ROOT") or os.environ.get("HF_HOME")
    if explicit:
        return Path(explicit)
    data_root = os.environ.get("GOODQ_DATA_ROOT")
    if data_root:
        return Path(data_root) / "models"
    return Path.home() / ".goodq" / "models"

print("="*80)
print("[SYMBOL] HUGGINGFACE AUTHENTICATION & MODEL LOADING TEST")
print("="*80)

# Set cache directories
_model_cache = model_cache_root()
os.environ["HF_HOME"] = str(_model_cache)
os.environ["TORCH_HOME"] = str(_model_cache)
os.environ["TRANSFORMERS_CACHE"] = str(_model_cache / "transformers")

print(f"\n[DIR] Cache Directories:")
print(f"   HF_HOME: {os.environ.get('HF_HOME')}")
print(f"   TORCH_HOME: {os.environ.get('TORCH_HOME')}")
print(f"   TRANSFORMERS_CACHE: {os.environ.get('TRANSFORMERS_CACHE')}")

# Check if directories exist
for dir_path in [os.environ["HF_HOME"], os.environ["TRANSFORMERS_CACHE"]]:
    if not os.path.exists(dir_path):
        print(f"   Creating: {dir_path}")
        os.makedirs(dir_path, exist_ok=True)

print(f"\n[SYMBOL] Authentication Status:")

try:
    from huggingface_hub import HfApi, login
    from huggingface_hub.utils import HfFolder
    
    # Check for token
    token = HfFolder.get_token()
    if token:
        print(f"   [OK] Token found (length: {len(token)})")
    else:
        print(f"   [WARN]  No token found")
        print(f"   Looking in: {HfFolder.path_token}")
    
    # Try to get user info
    try:
        api = HfApi()
        user = api.whoami(token=token)
        print(f"   [OK] Authenticated as: {user.get('name', 'Unknown')}")
    except Exception as e:
        print(f"   [FAIL] Authentication failed: {type(e).__name__}: {str(e)}")
        
except ImportError as e:
    print(f"   [FAIL] huggingface_hub not installed: {e}")
except Exception as e:
    print(f"   [FAIL] Error checking auth: {type(e).__name__}: {str(e)}")

print(f"\n[SYMBOL] Package Versions:")
try:
    import transformers
    print(f"   transformers: {transformers.__version__}")
except ImportError:
    print(f"   [FAIL] transformers not installed")

try:
    import torch
    print(f"   torch: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA device: {torch.cuda.get_device_name(0)}")
except ImportError:
    print(f"   [FAIL] torch not installed")

print(f"\n[SYMBOL] Test 1: Download Small Model (with timeout)")
print("   Model: prajjwal1/bert-tiny (18MB)")

try:
    import torch
    from transformers import AutoTokenizer, AutoModel
    import threading
    import time
    
    download_success = {"status": False, "error": None}
    
    def download_model():
        try:
            print(f"   Downloading tokenizer...")
            tokenizer = AutoTokenizer.from_pretrained(
                "prajjwal1/bert-tiny",
                cache_dir=os.environ["TRANSFORMERS_CACHE"],
                resume_download=True
            )
            print(f"   [OK] Tokenizer downloaded")
            
            print(f"   Downloading model...")
            model = AutoModel.from_pretrained(
                "prajjwal1/bert-tiny",
                cache_dir=os.environ["TRANSFORMERS_CACHE"],
                resume_download=True
            )
            print(f"   [OK] Model downloaded")
            
            download_success["status"] = True
        except Exception as e:
            download_success["error"] = f"{type(e).__name__}: {str(e)}"
    
    # Run with timeout
    download_thread = threading.Thread(target=download_model, daemon=True)
    download_thread.start()
    download_thread.join(timeout=120)  # 2 minute timeout
    
    if download_thread.is_alive():
        print(f"   [FAIL] TIMEOUT: Download took > 120 seconds")
        print(f"   This is the problem! Model downloading hangs.")
    elif download_success["status"]:
        print(f"   [OK] SUCCESS: Model downloaded and loaded")
    else:
        print(f"   [FAIL] ERROR: {download_success['error']}")
        
except Exception as e:
    print(f"   [FAIL] Test failed: {type(e).__name__}: {str(e)}")

print(f"\n[SYMBOL] Test 2: Load Cached Model (if exists)")
print("   Model: distilbert-base-uncased-finetuned-sst-2-english")

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    
    # Try local_files_only first
    print(f"   Attempting local load (no download)...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            "distilbert-base-uncased-finetuned-sst-2-english",
            cache_dir=os.environ["TRANSFORMERS_CACHE"],
            local_files_only=True
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            "distilbert-base-uncased-finetuned-sst-2-english",
            cache_dir=os.environ["TRANSFORMERS_CACHE"],
            local_files_only=True
        )
        print(f"   [OK] Model loaded from cache")
        
        # Test inference
        inputs = tokenizer("This is a test", return_tensors="pt")
        outputs = model(**inputs)
        print(f"   [OK] Inference works")
        
    except Exception as e:
        print(f"   [WARN]  Not in cache: {type(e).__name__}")
        print(f"   Would need to download from HuggingFace Hub")
        
except Exception as e:
    print(f"   [FAIL] Test failed: {type(e).__name__}: {str(e)}")

print(f"\n[SYMBOL] Test 3: Check Network Connectivity")

try:
    import requests
    
    print(f"   Testing huggingface.co...")
    response = requests.get("https://huggingface.co", timeout=10)
    if response.status_code == 200:
        print(f"   [OK] Can reach huggingface.co")
    else:
        print(f"   [WARN]  Unexpected status: {response.status_code}")
        
except requests.exceptions.Timeout:
    print(f"   [FAIL] TIMEOUT: Cannot reach huggingface.co")
    print(f"   This could be the network issue causing hangs!")
except Exception as e:
    print(f"   [FAIL] Network test failed: {type(e).__name__}: {str(e)}")

print(f"\n[CONFIG] Recommendations:")
print("="*80)

# Check cache size
cache_dir = Path(os.environ["TRANSFORMERS_CACHE"])
if cache_dir.exists():
    total_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
    print(f"[STATS] Cache size: {total_size / (1024**3):.2f} GB")
    
    # Check for model files
    model_files = list(cache_dir.rglob("pytorch_model.bin"))
    print(f"[SYMBOL] Cached models: {len(model_files)}")
    for mf in model_files[:5]:
        print(f"   • {mf.parent.name}: {mf.stat().st_size / (1024**2):.1f} MB")

print("\n" + "="*80)
