# Python Path Configuration

## Overview

GoodQ4All resolves Conda and interpreter paths through shared helper surfaces
instead of hardcoded machine paths. This keeps Python entrypoints consistent
across desktop, laptop, and shell-driven automation.

## Canonical Surfaces

- Main module: `<project_root>\configs\python_paths.py`
- Python runtime helper: `<project_root>\steps\common\tool_paths.py`
- Shell helpers: `<project_root>\scripts\_lib\interpreter_bindings.ps1` and `.bat`
- Validation test: `<project_root>\tests\test_python_paths.py`

## What This Controls

- Conda executable discovery
- Per-environment Python executable resolution
- `conda run -n <env>` command construction
- Cross-host fallback behavior when PATH or shell state drifts

## Python Usage

```python
from configs.python_paths import (
    get_conda_exe,
    get_conda_run_command,
    get_env_python,
    validate_env,
)

conda_exe = get_conda_exe()
python_exe = get_env_python("goodq_core")
cmd = get_conda_run_command("goodq_core")
is_valid = validate_env("goodq_core")
```

## Shell Usage

PowerShell and batch entrypoints should use the shared interpreter binding
helpers instead of assuming `conda` is already activated:

```powershell
. (Join-Path $PSScriptRoot "_lib\interpreter_bindings.ps1")
$condaExe = Get-GoodQCondaExe
$envName = Get-GoodQCondaEnv
& $condaExe run -n $envName python --version
```

## Detection Priority

The Python helper resolves Conda in this order:

1. `CONDA_EXE`
2. `conda` on `PATH`
3. common local Conda install locations
4. WSL-accessible Windows Conda locations when running under Linux/WSL

The shell helpers follow the same contract for PowerShell and batch launchers.

## Current Consumers

- `configs/python_paths.py`
- `steps/common/tool_paths.py`
- `agents/base_agent.py`
- `scripts/_lib/interpreter_bindings.ps1`
- `scripts/_lib/interpreter_bindings.bat`

## Testing

Run the validation test inside `goodq_core`:

```bash
conda activate goodq_core
python tests/test_python_paths.py
```

Expected result:

```text
[OK] all tests passed
```

## Migration Rule

Do not hardcode interpreter paths like this:

```python
conda_path = Path("<conda_base>")
python_exe = conda_path / "envs" / "goodq_core" / "python.exe"
cmd = ["conda", "run", "-n", "goodq_core"]
```

Use the shared helpers instead:

```python
from configs.python_paths import get_conda_run_command, get_env_python

python_exe = get_env_python("goodq_core")
cmd = get_conda_run_command("goodq_core")
```

## Troubleshooting

If interpreter binding fails:

1. Verify Conda is installed: `conda --version`
2. Run `python tests/test_python_paths.py`
3. Check `from configs.python_paths import get_config; print(get_config().get_info_dict())`
4. For shell launchers, use `scripts/diagnostics/quick_laptop_test.ps1`

## Notes

- `BASELINE` must remain safe without manual Conda activation.
- WSL is a compute extension only; Windows launchers remain canonical.
- This guide covers interpreter discovery only, not environment creation.
