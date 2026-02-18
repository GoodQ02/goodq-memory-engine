"""
GoodQ Project Path Configuration
Central source of truth for all project paths.
"""
from pathlib import Path
import os
import re


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


def _normalize_win_style(path_value: str) -> str:
    if not path_value:
        return path_value
    return path_value.replace("\\", "/")


_ENV_REF_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


def _resolve_env_ref(value: str) -> str:
    if not isinstance(value, str):
        return value

    def _replace(match: re.Match[str]) -> str:
        env_name = match.group(1)
        default_value = match.group(2)
        env_value = os.environ.get(env_name)
        if default_value is not None:
            return env_value if env_value not in (None, "") else default_value
        return env_value if env_value is not None else match.group(0)

    return _ENV_REF_PATTERN.sub(_replace, value)


def _read_host_data_root_from_config() -> str | None:
    config_path = Path(__file__).resolve().parent / "config.yaml"
    if not config_path.exists():
        return None

    in_host_block = False
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if not line.startswith(" ") and stripped.endswith(":"):
            in_host_block = stripped == "host:"
            continue

        if in_host_block and line.startswith("  ") and stripped.startswith("data_root:"):
            value = stripped.split(":", 1)[1].strip().strip("'\"")
            return value or None

    return None


def _resolve_authoritative_data_root() -> str:
    host_data_root = _read_host_data_root_from_config()
    if host_data_root:
        return _normalize_win_style(_resolve_env_ref(host_data_root)).rstrip("/")
    return _normalize_win_style(os.environ.get("GOODQ_DATA_ROOT", "L:" + "/_DATA")).rstrip("/")


def _drive_prefix(path_value: str) -> str:
    normalized = _normalize_win_style(path_value)
    if len(normalized) >= 2 and normalized[1] == ":":
        return normalized[:2]
    return ""

# ==============================================================================
# PROJECT ROOT
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ==============================================================================
# DATA DIRECTORIES (Not in GitHub - local only)
# ==============================================================================
_GOODQ_DATA_ROOT = _resolve_authoritative_data_root()
_DRIVE_PREFIX = _drive_prefix(_GOODQ_DATA_ROOT)
DATA_ROOT = drive_path(f"{_GOODQ_DATA_ROOT}/GoodQ_Data")

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
IMPORT_INBOX = DATA_ROOT / "import_inbox"  # Fixed: moved to DATA_ROOT (was PROJECT_ROOT)
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
MODELS_DIR = drive_path(f"{_GOODQ_DATA_ROOT}/models")
TOOLS_DIR = drive_path(f"{_DRIVE_PREFIX}/_TOOLS" if _DRIVE_PREFIX else "_TOOLS")
ARCHIVE_DIR = drive_path(f"{_DRIVE_PREFIX}/_ARCHIVE" if _DRIVE_PREFIX else "_ARCHIVE")

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
    
    print("\n[DIR] PROJECT ROOT:")
    print(f"   {PROJECT_ROOT}")
    
    print("\n[SAVE] DATA DIRECTORIES:")
    print(f"   Root:       {DATA_ROOT}")
    print(f"   Databases:  {DATABASE_DIR}")
    print(f"   Cache:      {CACHE_DIR}")
    print(f"   FAISS:      {FAISS_DIR}")
    print(f"   Processing: {PROCESSING_DIR}")
    print(f"   Completed:  {COMPLETED_DIR}")
    print(f"   Exports:    {EXPORTS_DIR}")
    print(f"   Logs:       {LOGS_DIR}")
    
    print("\n[LOG] KEY FILES:")
    print(f"   Memory DB:  {MEMORY_DB}")
    print(f"   Graph DB:   {KNOWLEDGE_GRAPH_DB}")
    print(f"   Step Log:   {STEP_RUNS_LOG}")
    
    print("\n[CONFIG] EXTERNAL:")
    print(f"   Models:     {MODELS_DIR}")
    print(f"   Tools:      {TOOLS_DIR}")
    print(f"   Archive:    {ARCHIVE_DIR}")
    
    print("\n[SYMBOL] Creating directories...")
    ensure_directories()
    print("[SYMBOL] All directories ready!")
    
    print("\n[SYMBOL] Setting environment variables...")
    set_environment_variables()
    print("[SYMBOL] Environment configured!")
