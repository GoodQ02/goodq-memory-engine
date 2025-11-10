"""Base agent class for GoodQ agents."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

# Add parent directory to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.python_paths import get_conda_run_command


class BaseAgent(ABC):
    """Base class for all GoodQ agents."""
    
    def __init__(self, name: str, conda_env: str):
        self.name = name
        self.conda_env = conda_env
        self.initialized = False
    
    @abstractmethod
    async def initialize(self):
        """Initialize the agent (load models, etc.)"""
        pass
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's main task"""
        pass
    
    async def run_in_conda(self, script_path: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a script in the agent's conda environment."""
        args_json = json.dumps(args)
        
        # Use centralized conda path configuration
        conda_cmd = get_conda_run_command(self.conda_env)
        cmd = conda_cmd + ["python", script_path, args_json]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "returncode": proc.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode()
        }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "name": self.name,
            "conda_env": self.conda_env,
            "initialized": self.initialized
        }
