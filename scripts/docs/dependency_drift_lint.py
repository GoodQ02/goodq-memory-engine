#!/usr/bin/env python3
"""Lint dependency drift across setup.py, environment.yml, and lockfiles.

Checks:
1. setup.py install_requires must be present in environment.yml (under conda or pip).
2. All packages in environment.yml must be locked in environment-baseline-lock.yml
   and requirements-baseline-lock.txt (excluding conda-only packages like cpuonly/pip/python).
3. Locked versions in lockfiles must satisfy constraints in setup.py and environment.yml.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
import yaml
from packaging.requirements import Requirement
from packaging.version import Version

# Conda-only packages or metadata flags that are not locked in pip requirements.txt
CONDA_ONLY_PACKAGES = {"cpuonly", "python", "pip"}

# Core packages that must be checked for locking
CONDA_META_PACKAGES = {"python", "pip", "cpuonly"}

# Mapping from conda package name to pip package name
PACKAGE_NAME_MAPPING = {
    "pytorch": "torch"
}

def parse_setup_py(setup_py_path: Path) -> tuple[list[str], dict[str, list[str]]]:
    """Extract install_requires and extras_require from setup.py."""
    if not setup_py_path.exists():
        return [], {}
    
    with open(setup_py_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(setup_py_path))
    
    install_requires = []
    extras_require = {}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "setup":
            for kw in node.keywords:
                if kw.arg == "install_requires" and isinstance(kw.value, ast.List):
                    for elt in kw.value.elts:
                        if isinstance(elt, ast.Constant):
                            install_requires.append(elt.value)
                elif kw.arg == "extras_require" and isinstance(kw.value, ast.Dict):
                    for k, v in zip(kw.value.keys, kw.value.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.List):
                            reqs = []
                            for elt in v.elts:
                                if isinstance(elt, ast.Constant):
                                    reqs.append(elt.value)
                            extras_require[k.value] = reqs
    return install_requires, extras_require

def parse_environment_yml(env_path: Path) -> tuple[list[str], list[str]]:
    """Extract conda and pip dependencies from environment.yml."""
    if not env_path.exists():
        return [], []
    
    with open(env_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    conda_deps = []
    pip_deps = []
    
    for dep in data.get("dependencies", []):
        if isinstance(dep, str):
            conda_deps.append(dep)
        elif isinstance(dep, dict) and "pip" in dep:
            for pip_dep in dep["pip"]:
                if isinstance(pip_dep, str):
                    pip_deps.append(pip_dep)
    return conda_deps, pip_deps

def parse_requirements_txt(req_path: Path) -> list[str]:
    """Extract requirements from requirements-baseline-lock.txt."""
    if not req_path.exists():
        return []
    
    reqs = []
    with open(req_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            reqs.append(line)
    return reqs

def normalize_to_pip_spec(dep_str: str) -> str:
    """Normalize conda spec (e.g. fastapi=0.135.2 or python=3.10) to pip format."""
    dep_str = dep_str.strip()
    if dep_str.startswith("-e"):
        return dep_str
    
    # Replace single '=' with '==' if it's not part of >=, <=, !=, or ==
    if "=" in dep_str and not any(op in dep_str for op in [">=", "<=", "!=", "=="]):
        parts = dep_str.split("=", 1)
        name = parts[0].strip()
        version = parts[1].strip()
        # If version has format X.Y (two components), treat as X.Y.* wildcards
        if re.match(r"^\d+\.\d+$", version):
            return f"{name}=={version}.*"
        return f"{name}=={version}"
    return dep_str

def get_pkg_name(req_str: str) -> str:
    """Get lowercase package name from a requirement string, mapped to canonical pip name."""
    req_str = normalize_to_pip_spec(req_str)
    if req_str.startswith("-e"):
        return "-e"
    try:
        raw_name = Requirement(req_str).name.lower()
    except Exception:
        # Fallback to simple regex if packaging fails
        m = re.match(r"^([a-zA-Z0-9_\-]+)", req_str)
        raw_name = m.group(1).lower() if m else req_str.lower()
    
    # Map conda-specific package names to canonical pip names
    return PACKAGE_NAME_MAPPING.get(raw_name, raw_name)

def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    
    setup_py = repo_root / "setup.py"
    env_yml = repo_root / "environment.yml"
    lock_yml = repo_root / "environment-baseline-lock.yml"
    lock_txt = repo_root / "requirements-baseline-lock.txt"
    
    failures = []
    
    # 1. Parse all files
    try:
        setup_install, setup_extras = parse_setup_py(setup_py)
        env_conda, env_pip = parse_environment_yml(env_yml)
        lock_conda, lock_pip = parse_environment_yml(lock_yml)
        lock_txt_lines = parse_requirements_txt(lock_txt)
    except Exception as e:
        print(f"FAIL: Error parsing dependency files: {e}")
        return 1

    # Normalize environment packages
    env_packages = {}
    for dep in env_conda + env_pip:
        pkg_name = get_pkg_name(dep)
        if pkg_name and pkg_name != "-e":
            env_packages[pkg_name] = dep

    # Normalize locked packages
    locked_packages_yml = {}
    for dep in lock_conda + lock_pip:
        pkg_name = get_pkg_name(dep)
        if pkg_name and pkg_name != "-e":
            locked_packages_yml[pkg_name] = dep

    locked_packages_txt = {}
    for dep in lock_txt_lines:
        pkg_name = get_pkg_name(dep)
        if pkg_name:
            locked_packages_txt[pkg_name] = dep

    # --- CHECK 1: setup.py install_requires must be present in environment.yml ---
    for req_str in setup_install:
        pkg_name = get_pkg_name(req_str)
        if pkg_name not in env_packages:
            failures.append(f"FAIL: setup.py declares '{pkg_name}', but environment.yml does not.")

    # --- CHECK 2: All environment.yml packages must be in the lockfiles ---
    for pkg_name, env_spec in env_packages.items():
        if pkg_name in CONDA_META_PACKAGES:
            continue
        
        # Check environment-baseline-lock.yml
        if pkg_name not in locked_packages_yml:
            failures.append(f"FAIL: '{pkg_name}' is declared in environment.yml, but missing from environment-baseline-lock.yml.")
        
        # Check requirements-baseline-lock.txt (conda-only packages are excluded)
        if pkg_name not in CONDA_ONLY_PACKAGES and pkg_name not in locked_packages_txt:
            failures.append(f"FAIL: '{pkg_name}' is declared in environment.yml, but missing from requirements-baseline-lock.txt.")

    # --- CHECK 3: Locked versions must satisfy constraints in setup.py and environment.yml ---
    specifiers_to_check: list[tuple[str, str, Requirement]] = []
    
    # Add specs from setup.py
    for req_str in setup_install:
        try:
            req = Requirement(normalize_to_pip_spec(req_str))
            # Map name if needed
            mapped_name = PACKAGE_NAME_MAPPING.get(req.name.lower(), req.name.lower())
            specifiers_to_check.append(("setup.py", mapped_name, req))
        except Exception:
            pass
            
    # Add specs from environment.yml
    for dep in env_conda + env_pip:
        pkg_name = get_pkg_name(dep)
        if pkg_name == "-e":
            continue
        try:
            req = Requirement(normalize_to_pip_spec(dep))
            # Map name if needed
            mapped_name = PACKAGE_NAME_MAPPING.get(pkg_name, pkg_name)
            specifiers_to_check.append(("environment.yml", mapped_name, req))
        except Exception:
            pass

    for source, pkg_name, req in specifiers_to_check:
        # Check in environment-baseline-lock.yml
        if pkg_name in locked_packages_yml:
            locked_spec = locked_packages_yml[pkg_name]
            try:
                lock_req = Requirement(normalize_to_pip_spec(locked_spec))
                version_str = None
                for spec in lock_req.specifier:
                    if spec.operator in ("==", "="):
                        version_str = spec.version
                        break
                
                if version_str:
                    ver = Version(version_str)
                    if ver not in req.specifier:
                        failures.append(
                            f"FAIL: {source} requires '{req}', but environment-baseline-lock.yml locks '{pkg_name}' to version '{version_str}' which violates this constraint."
                        )
            except Exception:
                pass

        # Check in requirements-baseline-lock.txt
        if pkg_name in locked_packages_txt:
            locked_spec = locked_packages_txt[pkg_name]
            try:
                lock_req = Requirement(normalize_to_pip_spec(locked_spec))
                version_str = None
                for spec in lock_req.specifier:
                    if spec.operator in ("==", "="):
                        version_str = spec.version
                        break
                
                if version_str:
                    ver = Version(version_str)
                    if ver not in req.specifier:
                        failures.append(
                            f"FAIL: {source} requires '{req}', but requirements-baseline-lock.txt locks '{pkg_name}' to version '{version_str}' which violates this constraint."
                        )
            except Exception:
                pass

    # 5. Output results
    if failures:
        print("\n".join(failures))
        print(f"\nDependency drift lint failed: {len(failures)} error(s) found.")
        return 1
    
    print("OK: Dependency drift lint passed. setup.py, environment.yml, and lockfiles are in sync.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
