# GoodQ4All Project Structure

## Directory Organization

### Root Level
- `INSTALL.bat` - Main installation script
- `LAUNCH_GOODQ.bat` - Main application launcher
- `setup.py` - Python package setup
- `README.md` - Project overview
- `LICENSE` - Project license

### `/api/`
FastAPI server implementation
- REST endpoints for web UI
- WebSocket connections
- Data serving layer

### `/cli/`
Command-line interface tools
- Interactive CLI for pipeline control
- Batch processing utilities

### `/common/`
Shared utilities and helpers
- Database connections
- Logging utilities
- Common data models

### `/configs/`
All configuration files (merged from config/)
- `config.yaml` - Main configuration
- `gpu_config.yaml` - GPU settings
- `paths.yaml` - Path configurations
- `entities.yaml` - Entity definitions
- `model_registry.yaml` - Model versions

### `/data/`
Runtime data storage
- SQLite databases
- Processing caches
- Temporary files

### `/docs/`
Project documentation
- `/audits/` - System audit reports
- `/phases/` - Development phase completions
- `/releases/` - Release notes and summaries
- `/wsl2/` - WSL2 integration docs

### `/envs/`
Conda environment definitions
- Step-specific environments
- Dependency specifications

### `/lib/`
Core library code
- Pipeline orchestration
- Step implementations
- Data models

### `/pipelines/`
legacy orchestration pipeline definitions
- Audio processing pipelines
- Vision processing pipelines
- Knowledge graph pipelines

### `/scripts/`
Utility and test scripts (consolidated)
- Installation helpers
- Diagnostic tools
- Testing utilities
- Monitoring scripts

### `/steps/`
legacy orchestration step implementations
- Audio processing steps
- Vision processing steps
- NLP/LLM steps
- Knowledge graph steps

### `/tests/`
Test suite
- Unit tests
- Integration tests
- End-to-end tests

### `/web/`
Web UI implementation
- Vue.js frontend
- Static assets
- UI components

### `/workflows/`
GitHub Actions and automation
- CI/CD pipelines
- Automated testing

### `/wsl2_audio/`
WSL2 audio processing bridge
- GPU-accelerated transcription
- Speaker diarization
- Audio analysis

## Recent Changes (2025-11-15)

### Consolidated Directories
- Merged `config/` into `configs/`
- Moved root Python scripts to `scripts/`
- Moved BAT files to `scripts/`
- Organized documentation into subdirectories

### File Movements
- **To scripts/**: All Python utilities, BAT files, test scripts
- **To docs/audits/**: Audit and test reports
- **To docs/phases/**: Phase completion documents
- **To docs/releases/**: Release notes and summaries
- **To docs/wsl2/**: WSL2 integration documentation

## Best Practices

1. **No Duplicates**: Each file has one home
2. **Clear Separation**: Code vs. docs vs. config
3. **Logical Grouping**: Related files together
4. **Standard Structure**: Follows Python project conventions
5. **Easy Navigation**: Predictable file locations
