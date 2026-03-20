#!/usr/bin/env python3
"""Wrapper to test the segment text storage fix."""

import sys
sys.path.insert(0, 'L:/goodq4all')

import subprocess
from pathlib import Path

# Run the ingestion command
cmd = [
    sys.executable,
    '-c',
    """
import sys
sys.path.insert(0, 'L:/goodq4all')

# Modify imports in cli.run_ingestion to be relative
import importlib.util
spec = importlib.util.spec_from_file_location("run_ingestion", "L:/goodq4all/cli/run_ingestion.py")
module = importlib.util.module_from_spec(spec)

# Fix imports
import steps.common.config_loader
import steps.common.memory
import steps.common.tag_utils
import steps.common.tool_paths
import steps.common.step_logger
import lib.knowledge_graph

sys.modules['goodq4all.steps.common.config_loader'] = steps.common.config_loader
sys.modules['goodq4all.steps.common.memory'] = steps.common.memory
sys.modules['goodq4all.steps.common.tag_utils'] = steps.common.tag_utils
sys.modules['goodq4all.steps.common.tool_paths'] = steps.common.tool_paths  
sys.modules['goodq4all.steps.common.step_logger'] = steps.common.step_logger
sys.modules['goodq4all'] = sys.modules['__main__']
sys.modules['lib.knowledge_graph'] = lib.knowledge_graph

spec.loader.exec_module(module)

# Run the command
import typer.testing
runner = typer.testing.CliRunner()
result = runner.invoke(module.APP, ['run', '--input-dir', 'import_inbox', '--max-videos', '1', '--max-scenes', '3', '--verbose'])
print(result.stdout)
if result.exit_code != 0:
    print(f"Exit code: {result.exit_code}", file=sys.stderr)
    if result.exception:
        raise result.exception
"""
]

result = subprocess.run(cmd, cwd='L:/goodq4all', capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
print(f"\nExit code: {result.returncode}")
