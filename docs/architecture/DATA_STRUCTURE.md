# GoodQ4All Unified Data Configuration
# Generated: 2025-10-10 22:53:07

## Directory Structure

### Project Root: <project_root>
- Source code, scripts, configs
- Small working data
- Git-tracked files

### System Data Root: <GOODQ_DATA_ROOT>
- Large databases
- FAISS indices
- Processing logs
- Export bundles
- Historical data

### Models Root: <GOODQ_DATA_ROOT>\models (See LEGACY_PATHS_DEPRECATED.md)
- HuggingFace models (HF_HOME)
- PyTorch models (TORCH_HOME)
- Model checkpoints
- Datasets cache

### Tools: <project_root>\tools
- External utilities
- Piper TTS
- LibreOffice
- Other tools

### Archives: <GOODQ_DATA_ROOT>\archive
- Old versions
- Deprecated scripts
- Legacy data

## Single Source of Truth

All batch files are in: <project_root>\*.bat
All active scripts are in: <project_root>\scripts\
All data is in: <GOODQ_DATA_ROOT>\GoodQ_Data\
All models are in: <GOODQ_DATA_ROOT>\models (See LEGACY_PATHS_DEPRECATED.md)\

## No Duplicates Policy

- No batch files in <project_root>\ root
- No duplicate scripts
- No scattered data directories
- Single configuration source


