"""
Centralized Python and Conda Path Configuration for GoodQ4All
"""

import os
import platform
import shutil
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class PythonPathConfig:
    def __init__(self):
        self._conda_base = None
        self._conda_exe = None
        self._env_pythons = {}
        self._initialized = False
        import sys
        self.is_sandboxed = os.environ.get("GOODQ_SANDBOXED") == "1" or "Program Files" in sys.executable or "runtime" in sys.executable
        
    def initialize(self) -> bool:
        if self._initialized:
            return True
            
        if self.is_sandboxed:
            logger.info("Running in sandboxed/standalone mode (no conda needed)")
            self._conda_base = None
            self._conda_exe = None
            self._initialized = True
            return True

        try:
            self._conda_base = self._find_conda_base()
            if not self._conda_base:
                logger.error("Could not locate conda installation")
                return False
                
            if platform.system() == 'Windows':
                self._conda_exe = self._conda_base / 'Scripts' / 'conda.exe'
                if not self._conda_exe.exists():
                    self._conda_exe = self._conda_base / 'Scripts' / 'conda.bat'
            else:
                self._conda_exe = self._conda_base / 'bin' / 'conda'
                if not self._conda_exe.exists():
                    # WSL using Windows conda under /mnt/c
                    self._conda_exe = self._conda_base / 'Scripts' / 'conda.exe'
                if not self._conda_exe.exists():
                    self._conda_exe = self._conda_base / 'condabin' / 'conda.bat'
                
            if not self._conda_exe.exists():
                logger.error(f"Conda executable not found at {self._conda_exe}")
                return False
                
            self._cache_env_pythons()
            
            self._initialized = True
            logger.info(f"[SYMBOL] Python paths initialized (conda: {self._conda_base})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Python paths: {e}")
            return False
    
    def _find_conda_base(self) -> Optional[Path]:
        conda_exe = os.environ.get('CONDA_EXE')
        if conda_exe:
            conda_path = Path(conda_exe)
            if conda_path.exists():
                if platform.system() == 'Windows':
                    return conda_path.parent.parent
                else:
                    return conda_path.parent.parent
        
        conda_in_path = shutil.which('conda')
        if conda_in_path:
            conda_path = Path(conda_in_path)
            if platform.system() == 'Windows':
                return conda_path.parent.parent
            else:
                return conda_path.parent.parent
        
        if platform.system() == 'Windows':
            user_home = Path.home()
            common_paths = [
                user_home / 'miniconda3',
                user_home / 'anaconda3',
                Path('C:/ProgramData/miniconda3'),
                Path('C:/ProgramData/anaconda3'),
            ]
        else:
            common_paths = [
                Path.home() / 'miniconda3',
                Path.home() / 'anaconda3',
                Path('/opt/miniconda3'),
                Path('/opt/anaconda3'),
            ]

        # WSL-specific: look for Windows miniconda under /mnt/c
        if platform.system() == 'Linux' and ('WSL' in platform.release() or os.environ.get('WSL_DISTRO_NAME')):
            users_root = Path('/mnt/c/Users')
            if users_root.exists() and users_root.is_dir():
                for user_dir in users_root.iterdir():
                    if user_dir.is_dir():
                        common_paths.append(user_dir / 'miniconda3')
                        common_paths.append(user_dir / 'anaconda3')
            common_paths.extend([
                Path('/mnt/c/ProgramData/miniconda3'),
                Path('/mnt/c/ProgramData/anaconda3'),
            ])
        
        for path in common_paths:
            if path.exists() and path.is_dir():
                if platform.system() == 'Windows':
                    conda_exe = path / 'Scripts' / 'conda.exe'
                    if not conda_exe.exists():
                        conda_exe = path / 'Scripts' / 'conda.bat'
                else:
                    # WSL/Unix: try standard bin/conda, otherwise Windows-style Scripts/conda.exe under /mnt/c
                    conda_exe = path / 'bin' / 'conda'
                    if not conda_exe.exists():
                        conda_exe = path / 'Scripts' / 'conda.exe'
                    if not conda_exe.exists():
                        conda_exe = path / 'condabin' / 'conda.bat'
                    
                if conda_exe.exists():
                    return path
        
        return None
    
    def _cache_env_pythons(self):
        if not self._conda_base:
            return
            
        envs_dir = self._conda_base / 'envs'
        if not envs_dir.exists():
            return
            
        for env_dir in envs_dir.iterdir():
            if env_dir.is_dir():
                env_name = env_dir.name
                if platform.system() == 'Windows':
                    python_exe = env_dir / 'python.exe'
                else:
                    python_exe = env_dir / 'bin' / 'python'
                    
                if python_exe.exists():
                    self._env_pythons[env_name] = python_exe
    
    @property
    def conda_base(self) -> Optional[Path]:
        if not self._initialized:
            self.initialize()
        return self._conda_base
    
    @property
    def conda_exe(self) -> Optional[Path]:
        if not self._initialized:
            self.initialize()
        return self._conda_exe
    
    def get_env_python(self, env_name: str) -> Optional[Path]:
        if not self._initialized:
            self.initialize()
            
        if self.is_sandboxed or not self._conda_base:
            import sys
            return Path(sys.executable)
            
        if env_name in self._env_pythons:
            return self._env_pythons[env_name]
        
        envs_dir = self._conda_base / 'envs' / env_name
        if platform.system() == 'Windows':
            python_exe = envs_dir / 'python.exe'
        else:
            python_exe = envs_dir / 'bin' / 'python'
            
        if python_exe.exists():
            self._env_pythons[env_name] = python_exe
            return python_exe
            
        logger.warning(f"Python executable not found for environment: {env_name}")
        return None
    
    def get_all_envs(self) -> Dict[str, Path]:
        if not self._initialized:
            self.initialize()
        return self._env_pythons.copy()
    
    def validate_env(self, env_name: str) -> bool:
        python_exe = self.get_env_python(env_name)
        return python_exe is not None and python_exe.exists()
    
    def get_conda_run_command(self, env_name: str) -> list:
        if not self._initialized:
            self.initialize()
            
        if not self._conda_exe:
            if self.is_sandboxed:
                import sys
                # Return a python script wrapper that ignores the first 'python' argument to run_in_conda
                return [sys.executable, "-c", "import sys, subprocess; subprocess.run([sys.executable] + sys.argv[2:])"]
            raise RuntimeError("Conda executable not found")
            
        return [str(self._conda_exe), 'run', '-n', env_name]
    
    def get_info_dict(self) -> Dict:
        if not self._initialized:
            self.initialize()
            
        return {
            'conda_base': str(self._conda_base) if self._conda_base else None,
            'conda_exe': str(self._conda_exe) if self._conda_exe else None,
            'platform': platform.system(),
            'environments': {name: str(path) for name, path in self._env_pythons.items()},
            'initialized': self._initialized
        }


_config = PythonPathConfig()

def get_config() -> PythonPathConfig:
    return _config

def initialize_paths() -> bool:
    return _config.initialize()

def get_conda_exe() -> Optional[Path]:
    return _config.conda_exe

def get_env_python(env_name: str) -> Optional[Path]:
    return _config.get_env_python(env_name)

def get_conda_run_command(env_name: str) -> list:
    return _config.get_conda_run_command(env_name)

def validate_env(env_name: str) -> bool:
    return _config.validate_env(env_name)

initialize_paths()
