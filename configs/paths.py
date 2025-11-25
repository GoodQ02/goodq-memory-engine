"""
GoodQ Project Path Configuration
Central source of truth for all project paths.
"""
from pathlib import Path
import os


def drive_path(win_path: str) -> Path:
    """
    Translate Windows-style paths (e.g., L:/foo) to platform-specific paths.
    - On Windows: return the given path unchanged.
    - On WSL/Linux: map drive letters to /mnt/<drive_letter>/...
    """
    if os.name == "nt":
        return Path(win_path)
    if len(win_path) >= 3 and win_path[1:3] == ":/":
        drive = win_path[0].lower()
        rest = win_path[3:]
        return Path(f"/mnt/{drive}") / rest
    return Path(win_path)

# ==============================================================================
# PROJECT ROOT
# ==============================================================================
PROJECT_ROOT = drive_path("L:/goodq4all")

# ==============================================================================
# DATA DIRECTORIES (Not in GitHub - local only)
# ==============================================================================
DATA_ROOT = drive_path("L:/_DATA/GoodQ_Data")

# Databases
DATABASE_DIR = DATA_ROOT / "databases"
MEMORY_DB = DATABASE_DIR / "memory.db"
KNOWLEDGE_GRAPH_DB = DATABASE_DIR / "knowledge_graph.db"

# Cache
CACHE_DIR = DATA_ROOT / "cache"
HF_CACHE = CACHE_DIR / "huggingface"
TORCH_CACHE = CACHE_DIR / "torch"

# FAISS Indices
FAISS_DIR = DATA_ROOT / "faiss_indices"
FAISS_TEXT_DIR = FAISS_DIR / "text"
FAISS_AUDIO_DIR = FAISS_DIR / "audio"
FAISS_DINO_DIR = FAISS_DIR / "dino"
FAISS_CLIP_DIR = FAISS_DIR / "clip"

# Processing directories
PROCESSING_DIR = DATA_ROOT / "processing"
COMPLETED_DIR = DATA_ROOT / "completed"
EXPORTS_DIR = DATA_ROOT / "exports"

# Logs
LOGS_DIR = DATA_ROOT / "logs"
STEP_RUNS_LOG = LOGS_DIR / "step_runs.jsonl"
WATCHDOG_LOG = LOGS_DIR / "watchdog.log"
PIPELINE_LOG = LOGS_DIR / "pipeline.log"

# ==============================================================================
# PROJECT DIRECTORIES (In GitHub repo)
# ==============================================================================
IMPORT_INBOX = PROJECT_ROOT / "import_inbox"
CONFIGS_DIR = PROJECT_ROOT / "configs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
PIPELINES_DIR = PROJECT_ROOT / "pipelines"
STEPS_DIR = PROJECT_ROOT / "steps"
API_DIR = PROJECT_ROOT / "api"
DOCS_DIR = PROJECT_ROOT / "docs"
ENVS_DIR = PROJECT_ROOT / "envs"

# ==============================================================================
# EXTERNAL DIRECTORIES
# ==============================================================================
MODELS_DIR = drive_path("L:/_DATA/models")
TOOLS_DIR = drive_path("L:/_TOOLS")
ARCHIVE_DIR = drive_path("L:/_ARCHIVE")

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def ensure_directories():
    """Create all required directories if they don't exist."""
    dirs = [
        DATABASE_DIR, CACHE_DIR, HF_CACHE, TORCH_CACHE,
        FAISS_TEXT_DIR, FAISS_AUDIO_DIR, FAISS_DINO_DIR, FAISS_CLIP_DIR,
        PROCESSING_DIR, COMPLETED_DIR, EXPORTS_DIR, LOGS_DIR
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)

def get_processing_dir(video_name: str) -> Path:
    """Get the processing directory for a specific video."""
    video_dir = PROCESSING_DIR / video_name
    video_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (video_dir / "frames").mkdir(exist_ok=True)
    (video_dir / "audio").mkdir(exist_ok=True)
    (video_dir / "metadata").mkdir(exist_ok=True)
    
    return video_dir

def get_completed_dir(video_name: str) -> Path:
    """Get the completed directory for a specific video."""
    return COMPLETED_DIR / video_name

def set_environment_variables():
    """Set environment variables for caching and isolation."""
    os.environ["HF_HOME"] = str(HF_CACHE)
    os.environ["TORCH_HOME"] = str(TORCH_CACHE)
    os.environ["TRANSFORMERS_CACHE"] = str(HF_CACHE)
    os.environ["PYTHONNOUSERSITE"] = "1"
    os.environ["PIP_NO_CACHE_DIR"] = "1"
    os.environ["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

# ==============================================================================
# LEGACY PATH MAPPING (for migration)
# ==============================================================================
LEGACY_PATHS = {
    "goodq4all": PROJECT_ROOT,
    "old_logs": ARCHIVE_DIR / "old_tests",
    "old_data": ARCHIVE_DIR / "old_data"
}

if __name__ == "__main__":
    # Test and display all paths
    print("=" * 70)
    print("GoodQ Project Paths Configuration")
    print("=" * 70)
    
    print("\n📁 PROJECT ROOT:")
    print(f"   {PROJECT_ROOT}")
    
    print("\n💾 DATA DIRECTORIES:")
    print(f"   Root:       {DATA_ROOT}")
    print(f"   Databases:  {DATABASE_DIR}")
    print(f"   Cache:      {CACHE_DIR}")
    print(f"   FAISS:      {FAISS_DIR}")
    print(f"   Processing: {PROCESSING_DIR}")
    print(f"   Completed:  {COMPLETED_DIR}")
    print(f"   Exports:    {EXPORTS_DIR}")
    print(f"   Logs:       {LOGS_DIR}")
    
    print("\n📋 KEY FILES:")
    print(f"   Memory DB:  {MEMORY_DB}")
    print(f"   Graph DB:   {KNOWLEDGE_GRAPH_DB}")
    print(f"   Step Log:   {STEP_RUNS_LOG}")
    
    print("\n🔧 EXTERNAL:")
    print(f"   Models:     {MODELS_DIR}")
    print(f"   Tools:      {TOOLS_DIR}")
    print(f"   Archive:    {ARCHIVE_DIR}")
    
    print("\n✓ Creating directories...")
    ensure_directories()
    print("✓ All directories ready!")
    
    print("\n✓ Setting environment variables...")
    set_environment_variables()
    print("✓ Environment configured!")
