import os
import sys
from pathlib import Path

class PlatformHelper:
    @property
    def is_windows(self) -> bool:
        return sys.platform == "win32"

    @property
    def is_mac(self) -> bool:
        return sys.platform == "darwin"

    @property
    def is_linux(self) -> bool:
        return sys.platform.startswith("linux")

    @property
    def is_wsl(self) -> bool:
        if sys.platform != "linux":
            return False
        try:
            uname_rel = os.uname().release.lower()
            return "wsl" in uname_rel or "microsoft" in uname_rel or "WSL_DISTRO_NAME" in os.environ
        except AttributeError:
            return "WSL_DISTRO_NAME" in os.environ

    @classmethod
    def get_data_root(cls) -> Path:
        override = os.environ.get("GOODQ_DATA_ROOT")
        if override:
            return Path(override)
        if sys.platform == "win32":
            return Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "GoodQ4All"
        elif sys.platform == "darwin":
            return Path.home() / "Library/Application Support/GoodQ4All"
        else:
            xdg_data = os.environ.get("XDG_DATA_HOME")
            if xdg_data:
                return Path(xdg_data) / "goodq4all"
            return Path.home() / ".local/share/goodq4all"

    @classmethod
    def get_config_root(cls) -> Path:
        override = os.environ.get("GOODQ_CONFIG_ROOT")
        if override:
            return Path(override)
        if sys.platform == "win32":
            return cls.get_data_root() / "config"
        elif sys.platform == "darwin":
            return Path.home() / "Library/Preferences/GoodQ4All"
        else:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                return Path(xdg_config) / "goodq4all"
            return Path.home() / ".config/goodq4all"

    @classmethod
    def get_cache_root(cls) -> Path:
        override = os.environ.get("GOODQ_CACHE_ROOT")
        if override:
            return Path(override)
        if sys.platform == "win32":
            return cls.get_data_root() / "cache"
        elif sys.platform == "darwin":
            return Path.home() / "Library/Caches/GoodQ4All"
        else:
            xdg_cache = os.environ.get("XDG_CACHE_HOME")
            if xdg_cache:
                return Path(xdg_cache) / "goodq4all"
            return Path.home() / ".cache/goodq4all"

    @classmethod
    def get_logs_root(cls) -> Path:
        override = os.environ.get("GOODQ_LOGS_ROOT")
        if override:
            return Path(override)
        if sys.platform == "win32":
            return cls.get_data_root() / "logs"
        elif sys.platform == "darwin":
            return Path.home() / "Library/Logs/GoodQ4All"
        else:
            xdg_state = os.environ.get("XDG_STATE_HOME")
            if xdg_state:
                return Path(xdg_state) / "goodq4all/logs"
            return Path.home() / ".local/state/goodq4all/logs"

    @classmethod
    def get_models_root(cls) -> Path:
        override = os.environ.get("GOODQ_MODELS_ROOT")
        if override:
            return Path(override)
        if sys.platform == "win32":
            return cls.get_data_root() / "models"
        else:
            return cls.get_cache_root() / "models"

    @classmethod
    def get_temp_root(cls) -> Path:
        override = os.environ.get("GOODQ_TEMP_ROOT")
        if override:
            return Path(override)
        if sys.platform == "win32":
            return cls.get_data_root() / "processing"
        else:
            return cls.get_cache_root() / "processing"

    @classmethod
    def get_binary_name(cls, base_name: str) -> str:
        if sys.platform == "win32":
            return f"{base_name}.exe"
        return base_name
