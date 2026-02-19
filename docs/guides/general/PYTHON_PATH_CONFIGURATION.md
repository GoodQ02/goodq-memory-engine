# Python Path Configuration - GoodQ4All

## Overview

The GoodQ4All system now uses a **centralized Python and Conda path configuration** system to eliminate path-related issues across all components.

## Location

- **Main Module**: <project_root>\config\python_paths.py
- **Test Script**: <project_root>\test_python_paths.py

## Key Features

### 1. **Single Source of Truth**
All Python and Conda paths are managed through one centralized module, eliminating:
- Hardcoded paths scattered across files
- Platform-specific path issues
- Conda executable not found errors
- Python path inconsistencies

### 2. **Automatic Detection**
The system automatically detects:
- Conda base installation directory
- Conda executable location (conda.exe or conda.bat)
- Python executables for all environments
- Platform-specific paths (Windows/Linux/Mac)

### 3. **Validation**
Built-in validation ensures:
- Conda installation is found
- Environments exist
- Python executables are accessible
- Paths are valid before use

## Usage

### Basic Usage

\\\python
from config.python_paths import (
    get_conda_exe,
    get_env_python,
    get_conda_run_command,
    validate_env
)

# Get conda executable path
conda_exe = get_conda_exe()
# Returns: Path('<conda_base>/Scripts/conda.exe')

# Get Python for specific environment
python_exe = get_env_python('goodq_core')
# Returns: Path('<conda_base>/envs/goodq_core/python.exe')

# Get conda run command for an environment
cmd = get_conda_run_command('goodq_core')
# Returns: ['<conda_base>\\Scripts\\conda.exe', 'run', '-n', 'goodq_core']

# Validate environment exists
is_valid = validate_env('goodq_core')
# Returns: True or False
\\\

### Advanced Usage

\\\python
from config.python_paths import get_config

# Get full configuration object
config = get_config()

# Get all environments
all_envs = config.get_all_envs()
# Returns: {'goodq_core': Path(...), 'goodq_video_scene_detect': Path(...), ...}

# Get configuration info
info = config.get_info_dict()
# Returns: {
#     'conda_base': '<conda_base>',
#     'conda_exe': '<conda_base>\\Scripts\\conda.exe',
#     'platform': 'Windows',
#     'environments': {...},
#     'initialized': True
# }
\\\

## Files Updated

The following files have been updated to use the centralized configuration:

1. **process_manager.py**
   - Now uses get_conda_exe() and get_env_python()
   - Removed hardcoded paths

2. **steps/common/tool_paths.py**
   - 
esolve_conda() now uses centralized config
   - Simplified implementation

3. **gents/base_agent.py**
   - 
un_in_conda() now uses get_conda_run_command()
   - Automatic path resolution

4. **cli/run_ingestion.py**
   - Already uses 
esolve_conda() (now improved)

## Testing

Run the test script to verify all paths are correctly configured:

\\\ash
conda activate goodq_core
python test_python_paths.py
\\\

Expected output:
\\\
✓ ALL TESTS PASSED
\\\

## How It Works

### 1. **Detection Priority**

The system searches for Conda installation in this order:

1. **Environment Variable**: CONDA_EXE (most reliable)
2. **PATH Search**: Uses shutil.which('conda')
3. **Common Locations**: Checks standard installation directories
   - Windows: <conda_base>, <alt_conda_base>, etc.
   - Linux/Mac: ~/miniconda3, /opt/miniconda3, etc.

### 2. **Caching**

Environment paths are cached on first access for performance:
- All environments scanned once
- Paths stored in memory
- Fast subsequent lookups

### 3. **Lazy Initialization**

Configuration initializes automatically on first use:
- No manual setup required
- Initialization happens on module import
- Can be explicitly triggered with initialize_paths()

## Migration Guide

### Old Pattern (Hardcoded)

\\\python
# DON'T DO THIS ANYMORE
conda_path = Path("<conda_base>")
python_exe = conda_path / "envs" / "goodq_core" / "python.exe"
cmd = ["conda", "run", "-n", "goodq_core"]
\\\

### New Pattern (Centralized)

\\\python
# DO THIS INSTEAD
from config.python_paths import get_env_python, get_conda_run_command

python_exe = get_env_python('goodq_core')
cmd = get_conda_run_command('goodq_core')
\\\

## Benefits

✓ **No more hardcoded paths** - Works on any system with Conda installed  
✓ **Automatic discovery** - Finds Conda regardless of installation location  
✓ **Cross-platform** - Works on Windows, Linux, and Mac  
✓ **Validated paths** - Ensures paths exist before use  
✓ **Centralized management** - One place to update if needed  
✓ **Better error messages** - Clear logging when paths aren't found  
✓ **Performance** - Caching prevents repeated file system checks  

## Troubleshooting

### Issue: "Could not locate conda installation"

**Solution**:
1. Verify Conda is installed: conda --version
2. Check CONDA_EXE environment variable: cho %CONDA_EXE%
3. Ensure Conda is in PATH
4. Run test script for detailed diagnostics

### Issue: Environment not found

**Solution**:
1. List all environments: conda env list
2. Create missing environment from YAML file
3. Verify environment name matches exactly

### Issue: Python executable not found

**Solution**:
1. Activate environment: conda activate <env_name>
2. Check Python exists: python --version
3. Reinstall environment if corrupted

## Support

For issues or questions, check:
- Test script output: python test_python_paths.py
- Configuration info: rom config.python_paths import get_config; print(get_config().get_info_dict())
- Logs in <project_root>\logs\process_manager.log

## Future Enhancements

Potential future improvements:
- Automatic environment creation if missing
- Support for virtual environments (venv)
- Docker container path resolution
- Network/remote Conda installations

