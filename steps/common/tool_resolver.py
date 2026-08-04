import os
import sys
import shutil
from pathlib import Path
from typing import Dict, Any

class ToolResolver:
    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def resolve_tool(name: str) -> Dict[str, Any]:
        """
        Resolve standard tools like ffmpeg, tesseract, pdftotext, qdrant
        """
        hints = {
            "ffmpeg": {
                "required_for": "Video framing, scene detection, and audio formatting",
                "severity": "error",
                "win": "winget install --id Gyan.FFmpeg.Essentials or download from ffmpeg.org",
                "mac": "brew install ffmpeg",
                "linux": "sudo apt update && sudo apt install ffmpeg (Ubuntu/Debian) or sudo pacman -S ffmpeg (Arch)",
            },
            "tesseract": {
                "required_for": "OCR (Optical Character Recognition) on keyframes",
                "severity": "warning",
                "win": "winget install --id UB.TesseractOCR or download installer",
                "mac": "brew install tesseract tesseract-lang",
                "linux": "sudo apt install tesseract-ocr (Ubuntu/Debian) or sudo pacman -S tesseract (Arch)",
            },
            "pdftotext": {
                "required_for": "PDF text parsing",
                "severity": "warning",
                "win": "Install Poppler/pdftotext and add to PATH",
                "mac": "brew install poppler",
                "linux": "sudo apt install poppler-utils (Ubuntu/Debian) or sudo pacman -S poppler (Arch)",
            },
            "qdrant": {
                "required_for": "Vector search index database",
                "severity": "warning",
                "win": "Download qdrant.exe and place in vendor/qdrant/",
                "mac": "brew install qdrant or run docker container",
                "linux": "sudo apt install qdrant or docker run",
            }
        }
        
        hint_data = hints.get(name, {
            "required_for": "Helper utility",
            "severity": "info",
            "win": "Install native package",
            "mac": "Install native package",
            "linux": "Install native package"
        })

        if sys.platform == "win32":
            hint_msg = hint_data["win"]
        elif sys.platform == "darwin":
            hint_msg = hint_data["mac"]
        else:
            hint_msg = hint_data["linux"]

        # Check: Env override
        tools_root = os.environ.get("GOODQ_TOOLS_ROOT") or os.environ.get("GOODQ_TOOLS_DIR")
        if tools_root:
            tools_path = Path(tools_root)
            binary_name = f"{name}.exe" if sys.platform == "win32" else name
            candidates = [
                tools_path / binary_name,
                tools_path / name / "bin" / binary_name,
                tools_path / "qdrant" / binary_name,
            ]
            for c in candidates:
                if c.exists():
                    return {
                        "name": name,
                        "found": True,
                        "path": str(c.resolve()).replace("\\", "/"),
                        "install_hint": hint_msg,
                        "required_for": hint_data["required_for"],
                        "severity": hint_data["severity"]
                    }

        # Check: Bundled tools
        project_root = ToolResolver._project_root()
        bundled_binary = f"{name}.exe" if sys.platform == "win32" else name
        bundled_candidates = [
            project_root / "vendor" / bundled_binary,
            project_root / "vendor" / name / "bin" / bundled_binary,
            project_root / "vendor" / "qdrant" / bundled_binary,
        ]
        if name in {"ffmpeg", "ffprobe"}:
            bundled_candidates.append(project_root / "ffmpeg" / bundled_binary)
        for c in bundled_candidates:
            if c.exists():
                return {
                    "name": name,
                    "found": True,
                    "path": str(c.resolve()).replace("\\", "/"),
                    "install_hint": hint_msg,
                    "required_for": hint_data["required_for"],
                    "severity": hint_data["severity"]
                }

        # Check: PATH
        path_hit = shutil.which(name)
        if path_hit:
            return {
                "name": name,
                "found": True,
                "path": path_hit.replace("\\", "/"),
                "install_hint": hint_msg,
                "required_for": hint_data["required_for"],
                "severity": hint_data["severity"]
            }

        # Check: Platform standard locations
        typical_paths = []
        if sys.platform == "darwin":
            typical_paths = [
                Path("/opt/homebrew/bin") / name,
                Path("/usr/local/bin") / name,
            ]
        elif sys.platform != "win32":
            typical_paths = [
                Path("/usr/bin") / name,
                Path("/usr/local/bin") / name,
            ]
        else:
            program_files = os.environ.get("ProgramFiles", "C:/Program Files")
            windows_fallbacks = {
                "tesseract": [Path(program_files) / "Tesseract-OCR" / "tesseract.exe"],
                "pdftotext": [Path(program_files) / "Git" / "mingw64" / "bin" / "pdftotext.exe"],
            }
            typical_paths = windows_fallbacks.get(name, [])

        for p in typical_paths:
            if p.exists():
                return {
                    "name": name,
                    "found": True,
                    "path": str(p.resolve()).replace("\\", "/"),
                    "install_hint": hint_msg,
                    "required_for": hint_data["required_for"],
                    "severity": hint_data["severity"]
                }

        return {
            "name": name,
            "found": False,
            "path": None,
            "install_hint": hint_msg,
            "required_for": hint_data["required_for"],
            "severity": hint_data["severity"]
        }
