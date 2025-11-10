"""
Test HuggingFace authentication and model downloading
"""
import os
import sys
from pathlib import Path

print("="*80)
print("🤗 HUGGINGFACE AUTHENTICATION & MODEL LOADING TEST")
print("="*80)

# Set cache directories
os.environ["HF_HOME"] = "L:/models"
os.environ["TORCH_HOME"] = "L:/models"
os.environ["TRANSFORMERS_CACHE"] = "L:/models/transformers"

print(f"\n📁 Cache Directories:")
print(f"   HF_HOME: {os.environ.get('HF_HOME')}")
print(f"   TORCH_HOME: {os.environ.get('TORCH_HOME')}")
print(f"   TRANSFORMERS_CACHE: {os.environ.get('TRANSFORMERS_CACHE')}")

# Check if directories exist
for dir_path in [os.environ["HF_HOME"], os.environ["TRANSFORMERS_CACHE"]]:
    if not os.path.exists(dir_path):
        print(f"   Creating: {dir_path}")
        os.makedirs(dir_path, exist_ok=True)

print(f"\n🔐 Authentication Status:")

try:
    from huggingface_hub import HfApi, login
    from huggingface_hub.utils import HfFolder
    
    # Check for token
    token = HfFolder.get_token()
    if token:
        print(f"   ✅ Token found (length: {len(token)})")
    else:
        print(f"   ⚠️  No token found")
        print(f"   Looking in: {HfFolder.path_token}")
    
    # Try to get user info
    try:
        api = HfApi()
        user = api.whoami(token=token)
        print(f"   ✅ Authenticated as: {user.get('name', 'Unknown')}")
    except Exception as e:
        print(f"   ❌ Authentication failed: {type(e).__name__}: {str(e)}")
        
except ImportError as e:
    print(f"   ❌ huggingface_hub not installed: {e}")
except Exception as e:
    print(f"   ❌ Error checking auth: {type(e).__name__}: {str(e)}")

print(f"\n📦 Package Versions:")
try:
    import transformers
    print(f"   transformers: {transformers.__version__}")
except ImportError:
    print(f"   ❌ transformers not installed")

try:
    import torch
    print(f"   torch: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA device: {torch.cuda.get_device_name(0)}")
except ImportError:
    print(f"   ❌ torch not installed")

print(f"\n🧪 Test 1: Download Small Model (with timeout)")
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
            print(f"   ✅ Tokenizer downloaded")
            
            print(f"   Downloading model...")
            model = AutoModel.from_pretrained(
                "prajjwal1/bert-tiny",
                cache_dir=os.environ["TRANSFORMERS_CACHE"],
                resume_download=True
            )
            print(f"   ✅ Model downloaded")
            
            download_success["status"] = True
        except Exception as e:
            download_success["error"] = f"{type(e).__name__}: {str(e)}"
    
    # Run with timeout
    download_thread = threading.Thread(target=download_model, daemon=True)
    download_thread.start()
    download_thread.join(timeout=120)  # 2 minute timeout
    
    if download_thread.is_alive():
        print(f"   ❌ TIMEOUT: Download took > 120 seconds")
        print(f"   This is the problem! Model downloading hangs.")
    elif download_success["status"]:
        print(f"   ✅ SUCCESS: Model downloaded and loaded")
    else:
        print(f"   ❌ ERROR: {download_success['error']}")
        
except Exception as e:
    print(f"   ❌ Test failed: {type(e).__name__}: {str(e)}")

print(f"\n🧪 Test 2: Load Cached Model (if exists)")
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
        print(f"   ✅ Model loaded from cache")
        
        # Test inference
        inputs = tokenizer("This is a test", return_tensors="pt")
        outputs = model(**inputs)
        print(f"   ✅ Inference works")
        
    except Exception as e:
        print(f"   ⚠️  Not in cache: {type(e).__name__}")
        print(f"   Would need to download from HuggingFace Hub")
        
except Exception as e:
    print(f"   ❌ Test failed: {type(e).__name__}: {str(e)}")

print(f"\n🧪 Test 3: Check Network Connectivity")

try:
    import requests
    
    print(f"   Testing huggingface.co...")
    response = requests.get("https://huggingface.co", timeout=10)
    if response.status_code == 200:
        print(f"   ✅ Can reach huggingface.co")
    else:
        print(f"   ⚠️  Unexpected status: {response.status_code}")
        
except requests.exceptions.Timeout:
    print(f"   ❌ TIMEOUT: Cannot reach huggingface.co")
    print(f"   This could be the network issue causing hangs!")
except Exception as e:
    print(f"   ❌ Network test failed: {type(e).__name__}: {str(e)}")

print(f"\n🔧 Recommendations:")
print("="*80)

# Check cache size
cache_dir = Path(os.environ["TRANSFORMERS_CACHE"])
if cache_dir.exists():
    total_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
    print(f"📊 Cache size: {total_size / (1024**3):.2f} GB")
    
    # Check for model files
    model_files = list(cache_dir.rglob("pytorch_model.bin"))
    print(f"📦 Cached models: {len(model_files)}")
    for mf in model_files[:5]:
        print(f"   • {mf.parent.name}: {mf.stat().st_size / (1024**2):.1f} MB")

print("\n" + "="*80)
