# Scripts Directory Organization

## Structure

```
scripts/
├── setup/              # Installation & environment setup scripts
│   ├── setup_conda_envs.py
│   ├── setup_qdrant.py
│   └── verify_gpu.py
│
├── utils/              # Utility & validation scripts
│   ├── check_*.py
│   ├── verify_*.py
│   └── validate_*.py
│
└── maintenance/        # Database & index maintenance
    └── rebuild_indices.py
```

## Moved to CLI

- `watchdog.py` → `cli/watchdog.py` (now invoked as `python -m cli.watchdog`)

## Archived (deprecated_2025_12_07/scripts/)

- Legacy test scripts (test_audio_*, test_clip_*)
- Deprecated processors (audio_scene_processor.py)
- Old batch tools (batch_process_videos.py)
- Standalone search demos

## Usage

### Setup
```bash
python scripts/setup/setup_conda_envs.py
python scripts/setup/verify_gpu.py
```

### Validation
```bash
python scripts/utils/validate_config.py
```

### Maintenance
```bash
python scripts/maintenance/rebuild_indices.py
```
