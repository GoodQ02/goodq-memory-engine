"""
GoodQ4All Package Setup
"""
from setuptools import setup, find_packages

setup(
    name="goodq4all",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        # Runtime CLI dependency (used by cli/run_ingestion and related entrypoints).
        "typer>=0.9,<1.0",
        # Portable FFmpeg binary fallback for environments without system ffmpeg.
        "imageio-ffmpeg>=0.6.0,<1.0",
    ],
    extras_require={
        # Optional local Windows fallback transcription dependency used by
        # run_ingestion when BASELINE selects the windows backend.
        "audio-transcribe-local": [
            "faster-whisper==1.0.3",
        ],
    },
)
