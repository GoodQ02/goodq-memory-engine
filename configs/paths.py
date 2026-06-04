"""
GoodQ Project Path Configuration
Compatibility helper derived from the canonical runtime config.
"""
from __future__ import annotations

from pathlib import Path
import os

from steps.common.config_loader import get_runtime_paths, load_configs


def drive_path(path_value: str) -> Path:
    """Return a filesystem path without introducing new root calculations."""
    return Path(path_value)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CFG = load_configs({})
_PATHS = get_runtime_paths(
    _CFG,
    "faiss_dir",
    "faiss_audio_path",
    "models_cache",
    "processed",
    "failed",
    "output_directory",
)

# Canonical data directories
DATA_ROOT = drive_path(_PATHS["data_root"])
DATABASE_DIR = Path(_PATHS["db_path"]).parent
MEMORY_DB = drive_path(_PATHS["db_path"])
KNOWLEDGE_GRAPH_DB = drive_path(_PATHS["knowledge_graph_db"])

# Cache
from steps.common.platform_config import PlatformHelper
CACHE_DIR = PlatformHelper.get_cache_root()
HF_CACHE = CACHE_DIR / "huggingface"
TORCH_CACHE = CACHE_DIR / "torch"

# FAISS
FAISS_DIR = drive_path(_PATHS["faiss_dir"])
FAISS_TEXT_DIR = FAISS_DIR / "text"
FAISS_AUDIO_DIR = FAISS_DIR / "audio"
FAISS_DINO_DIR = FAISS_DIR / "dino"
FAISS_CLIP_DIR = FAISS_DIR / "clip"

# Runtime directories
PROCESSING_DIR = drive_path(_PATHS["processing"])
COMPLETED_DIR = drive_path(_PATHS.get("processed") or str(DATA_ROOT / "completed"))
EXPORTS_DIR = drive_path(_PATHS.get("output_directory") or str(DATA_ROOT / "exports"))
LOGS_DIR = drive_path(_PATHS["log_dir"])
STEP_RUNS_LOG = LOGS_DIR / "step_runs.jsonl"
WATCHDOG_LOG = LOGS_DIR / "watchdog.log"
PIPELINE_LOG = LOGS_DIR / "pipeline.log"
IMPORT_INBOX = drive_path(_PATHS["import_inbox"])

# Project directories
CONFIGS_DIR = PROJECT_ROOT / "configs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
PIPELINES_DIR = PROJECT_ROOT / "pipelines"
STEPS_DIR = PROJECT_ROOT / "steps"
API_DIR = PROJECT_ROOT / "api"
DOCS_DIR = PROJECT_ROOT / "docs"
ENVS_DIR = PROJECT_ROOT / "envs"

# External directories
MODELS_DIR = drive_path(_PATHS["models_cache"])
TOOLS_DIR = Path(os.environ.get("GOODQ_TOOLS_DIR") or str(PROJECT_ROOT / "vendor"))
ARCHIVE_DIR = Path((_CFG.get("paths") or {}).get("nas_path") or str(DATA_ROOT / "archive"))


def ensure_directories() -> None:
    """Create required runtime directories if they do not exist."""
    dirs = [
        DATABASE_DIR,
        CACHE_DIR,
        HF_CACHE,
        TORCH_CACHE,
        FAISS_TEXT_DIR,
        FAISS_AUDIO_DIR,
        FAISS_DINO_DIR,
        FAISS_CLIP_DIR,
        PROCESSING_DIR,
        COMPLETED_DIR,
        EXPORTS_DIR,
        LOGS_DIR,
        IMPORT_INBOX,
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def get_processing_dir(video_name: str) -> Path:
    """Get the canonical processing directory for a specific video."""
    video_dir = PROCESSING_DIR / video_name
    (video_dir / "video").mkdir(parents=True, exist_ok=True)
    (video_dir / "audio").mkdir(exist_ok=True)
    (video_dir / "metadata").mkdir(exist_ok=True)
    return video_dir


def get_completed_dir(video_name: str) -> Path:
    """Get the completed directory for a specific video."""
    return COMPLETED_DIR / video_name


def set_environment_variables() -> None:
    """Set environment variables for caching and isolation."""
    os.environ["HF_HOME"] = str(HF_CACHE)
    os.environ["TORCH_HOME"] = str(TORCH_CACHE)
    os.environ["TRANSFORMERS_CACHE"] = str(HF_CACHE)
    os.environ["PYTHONNOUSERSITE"] = "1"
    os.environ["PIP_NO_CACHE_DIR"] = "1"
    os.environ["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"


LEGACY_PATHS = {
    "goodq4all": PROJECT_ROOT,
    "old_logs": ARCHIVE_DIR / "old_tests",
    "old_data": ARCHIVE_DIR / "old_data",
}


if __name__ == "__main__":
    print("=" * 70)
    print("GoodQ Project Paths Configuration")
    print("=" * 70)
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"DATA_ROOT:    {DATA_ROOT}")
    print(f"PROCESSING:   {PROCESSING_DIR}")
    print(f"LOGS:         {LOGS_DIR}")
    print(f"INBOX:        {IMPORT_INBOX}")
    print(f"MEMORY_DB:    {MEMORY_DB}")
    print(f"KG_DB:        {KNOWLEDGE_GRAPH_DB}")
    print(f"MODELS_DIR:   {MODELS_DIR}")
