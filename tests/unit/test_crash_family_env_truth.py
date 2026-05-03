from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

CRASH_FAMILY_ENVS = {
    "audio_embed": ("torch", "torchaudio"),
    "image_caption": ("torch", "torchvision", "torchaudio"),
    "object_detect": ("torch", "torchvision"),
}


def _pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        pins[name.strip().lower()] = version.strip()
    return pins


def _base_version(version: str) -> str:
    return version.split("+", 1)[0]


def test_crash_family_requirements_track_lock_torch_lane() -> None:
    for env_name, packages in CRASH_FAMILY_ENVS.items():
        requirements = _pins(REPO_ROOT / "envs" / env_name / "requirements.txt")
        locked = _pins(REPO_ROOT / "envs" / "locks" / f"{env_name}.lock.txt")

        for package in packages:
            assert package in locked, f"{env_name} lock missing {package}"
            assert package in requirements, f"{env_name} requirements missing {package}"
            assert _base_version(requirements[package]) == _base_version(locked[package])
