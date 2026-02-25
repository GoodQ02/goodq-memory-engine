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
    ],
)
