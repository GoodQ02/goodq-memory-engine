#!/usr/bin/env python3
"""
GoodQ4All Unified Health Check with Self-Healing
Consolidates all health checks into single source of truth
Validates and auto-corrects dataset paths, cache locations, and environment
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Color codes for terminal output
class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

@dataclass
class HealthIssue:
    """Represents a health check issue with self-healing capability"""
    category: str
    severity: str  # critical, warning, info
    description: str
    current_state: str
    expected_state: str
    can_auto_heal: bool = False
    heal_action: Optional[str] = None
    fixed: bool = False

@dataclass
class HealthReport:
    """Complete health check report"""
    timestamp: str
    overall_status: str  # GREEN, YELLOW, RED
    issues: List[HealthIssue] = field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0
    auto_healed: int = 0
    
    def add_issue(self, issue: HealthIssue):
        self.issues.append(issue)
        if issue.severity == "critical":
            self.checks_failed += 1
        
    def summary(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status,
            "total_issues": len(self.issues),
            "critical": len([i for i in self.issues if i.severity == "critical"]),
            "warnings": len([i for i in self.issues if i.severity == "warning"]),
            "auto_healed": self.auto_healed,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed
        }


class UnifiedHealthChecker:
    """Unified health checker with self-healing capabilities"""
    
    # Single source of truth for paths
    CANONICAL_PATHS = {
        "HF_HOME": "L:/models",
        "TORCH_HOME": "L:/models",
        "HF_DATASETS_CACHE": "L:/models/hf/datasets",
        "TRANSFORMERS_CACHE": "L:/models/transformers",
        "HF_HUB_CACHE": "L:/models/hub",
    }
    
    FRAGMENTED_CACHE_LOCATIONS = [
        Path.home() / ".cache" / "huggingface",
        Path.home() / ".cache" / "torch",
        Path.home() / "AppData" / "Local" / "huggingface",
    ]
    
    def __init__(self, auto_heal: bool = False, verbose: bool = False):
        self.auto_heal = auto_heal
        self.verbose = verbose
        self.report = HealthReport(
            timestamp=self._timestamp(),
            overall_status="GREEN"
        )
        self.repo_root = Path(__file__).resolve().parents[1]
        
    def _timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _print(self, msg: str, color: str = ""):
        """Print with optional color"""
        if color:
            print(f"{color}{msg}{Color.END}")
        else:
            print(msg)
    
    def _check_header(self, title: str):
        """Print check section header"""
        self._print(f"\n{'='*70}", Color.CYAN)
        self._print(f"{title}", Color.BOLD + Color.CYAN)
        self._print(f"{'='*70}", Color.CYAN)
    
    def _ok(self, msg: str):
        """Print success message"""
        self._print(f"  ✓ {msg}", Color.GREEN)
        self.report.checks_passed += 1
    
    def _warn(self, msg: str):
        """Print warning message"""
        self._print(f"  ⚠ {msg}", Color.YELLOW)
    
    def _fail(self, msg: str):
        """Print failure message"""
        self._print(f"  ✗ {msg}", Color.RED)
        self.report.checks_failed += 1
    
    def _heal(self, msg: str):
        """Print healing action message"""
        self._print(f"  🔧 HEALING: {msg}", Color.CYAN)
        self.report.auto_healed += 1
    
    def check_environment_variables(self) -> List[HealthIssue]:
        """Check and validate environment variables"""
        self._check_header("Environment Variables")
        issues = []
        
        for var_name, expected_value in self.CANONICAL_PATHS.items():
            current_value = os.environ.get(var_name)
            
            if not current_value:
                issue = HealthIssue(
                    category="environment",
                    severity="warning",
                    description=f"{var_name} not set",
                    current_state="Not set",
                    expected_state=expected_value,
                    can_auto_heal=True,
                    heal_action=f"Set {var_name}={expected_value}"
                )
                issues.append(issue)
                self._warn(f"{var_name} not set (expected: {expected_value})")
                
                if self.auto_heal:
                    os.environ[var_name] = expected_value
                    issue.fixed = True
                    self._heal(f"Set {var_name}={expected_value}")
                    
            elif current_value != expected_value:
                # Normalize paths for comparison
                current_norm = Path(current_value).as_posix()
                expected_norm = Path(expected_value).as_posix()
                
                if current_norm != expected_norm:
                    issue = HealthIssue(
                        category="environment",
                        severity="warning",
                        description=f"{var_name} points to wrong location",
                        current_state=current_value,
                        expected_state=expected_value,
                        can_auto_heal=True,
                        heal_action=f"Update {var_name} to {expected_value}"
                    )
                    issues.append(issue)
                    self._warn(f"{var_name}={current_value} (expected: {expected_value})")
                    
                    if self.auto_heal:
                        os.environ[var_name] = expected_value
                        issue.fixed = True
                        self._heal(f"Updated {var_name}={expected_value}")
                else:
                    self._ok(f"{var_name}={current_value}")
            else:
                self._ok(f"{var_name}={current_value}")
        
        return issues
    
    def check_fragmented_caches(self) -> List[HealthIssue]:
        """Detect and optionally consolidate fragmented caches"""
        self._check_header("Fragmented Cache Detection")
        issues = []
        
        for cache_location in self.FRAGMENTED_CACHE_LOCATIONS:
            if cache_location.exists():
                try:
                    # Calculate size
                    total_size = sum(f.stat().st_size for f in cache_location.rglob('*') if f.is_file())
                    size_gb = total_size / (1024**3)
                    
                    if size_gb > 0.1:  # More than 100MB
                        issue = HealthIssue(
                            category="cache_fragmentation",
                            severity="warning",
                            description=f"Fragmented cache at {cache_location}",
                            current_state=f"{size_gb:.2f} GB",
                            expected_state="Consolidated in L:/models",
                            can_auto_heal=False,  # Manual intervention required
                            heal_action=f"Move to L:/models (requires manual confirmation)"
                        )
                        issues.append(issue)
                        self._warn(f"Found {size_gb:.2f} GB in {cache_location}")
                        self._warn(f"  → Should be consolidated to L:/models")
                    else:
                        self._ok(f"{cache_location} is empty or negligible")
                        
                except Exception as e:
                    self._warn(f"Could not analyze {cache_location}: {e}")
            else:
                self._ok(f"{cache_location} does not exist (good)")
        
        return issues
    
    def check_dataset_paths(self) -> List[HealthIssue]:
        """Verify dataset paths in configuration files"""
        self._check_header("Dataset Path Configuration")
        issues = []
        
        # Files to check
        files_to_check = [
            self.repo_root / "steps" / "common" / "conda_runner.py",
            self.repo_root / "scripts" / "download_datasets.py",
            self.repo_root / "scripts" / "system_readiness_check.py",
        ]
        
        correct_path = "L:/models/hf/datasets"
        incorrect_patterns = ["L:/models/datasets", "L:\\models\\datasets"]
        
        for file_path in files_to_check:
            if not file_path.exists():
                continue
                
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            found_incorrect = False
            for pattern in incorrect_patterns:
                if pattern in content and "HF_DATASETS_CACHE" in content:
                    found_incorrect = True
                    issue = HealthIssue(
                        category="configuration",
                        severity="critical",
                        description=f"Incorrect dataset path in {file_path.name}",
                        current_state=pattern,
                        expected_state=correct_path,
                        can_auto_heal=True,
                        heal_action=f"Replace {pattern} with {correct_path}"
                    )
                    issues.append(issue)
                    self._fail(f"{file_path.name}: uses {pattern} instead of {correct_path}")
                    
                    if self.auto_heal:
                        # Fix the file
                        new_content = content.replace(f'"{pattern}"', f'"{correct_path}"')
                        new_content = new_content.replace(f"'{pattern}'", f"'{correct_path}'")
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        issue.fixed = True
                        self._heal(f"Fixed {file_path.name}")
                    break
            
            if not found_incorrect:
                self._ok(f"{file_path.name}: dataset paths correct")
        
        return issues
    
    def check_cache_locations(self) -> List[HealthIssue]:
        """Verify actual cache directories exist and are accessible"""
        self._check_header("Cache Directory Verification")
        issues = []
        
        expected_dirs = [
            Path("L:/models/hf/datasets"),
            Path("L:/models/hub"),
            Path("L:/models/transformers"),
            Path("L:/models/checkpoints"),
        ]
        
        for dir_path in expected_dirs:
            if dir_path.exists():
                # Check if it has content
                try:
                    item_count = len(list(dir_path.iterdir()))
                    self._ok(f"{dir_path}: exists ({item_count} items)")
                except Exception as e:
                    self._warn(f"{dir_path}: exists but cannot read ({e})")
            else:
                issue = HealthIssue(
                    category="cache_directory",
                    severity="warning",
                    description=f"Cache directory missing: {dir_path}",
                    current_state="Does not exist",
                    expected_state="Should exist",
                    can_auto_heal=True,
                    heal_action=f"Create directory {dir_path}"
                )
                issues.append(issue)
                self._warn(f"{dir_path}: does not exist")
                
                if self.auto_heal:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    issue.fixed = True
                    self._heal(f"Created {dir_path}")
        
        return issues
    
    def check_conda_environments(self) -> List[HealthIssue]:
        """Verify required conda environments exist"""
        self._check_header("Conda Environments")
        issues = []
        
        try:
            result = subprocess.run(
                ["conda", "env", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            env_list = result.stdout
            
            required_envs = [
                "goodq_zenml",
                "goodq_text_embed",
                "goodq_image_caption",
                "goodq_object_detect",
                "goodq_audio_transcribe",
                "goodq_audio_diarize",
            ]
            
            for env_name in required_envs:
                if env_name in env_list:
                    self._ok(f"{env_name}: installed")
                else:
                    issue = HealthIssue(
                        category="conda_environment",
                        severity="critical",
                        description=f"Missing conda environment: {env_name}",
                        current_state="Not installed",
                        expected_state="Should be installed",
                        can_auto_heal=False,
                        heal_action=f"Run: pwsh scripts/prepare_step_envs.ps1 -EnvPrefix goodq"
                    )
                    issues.append(issue)
                    self._fail(f"{env_name}: not found")
                    
        except Exception as e:
            self._fail(f"Could not check conda environments: {e}")
        
        return issues
    
    def check_cuda_availability(self) -> List[HealthIssue]:
        """Check CUDA availability in GPU environments"""
        self._check_header("CUDA Availability")
        issues = []
        
        gpu_envs = [
            "goodq_image_caption",
            "goodq_object_detect", 
            "goodq_audio_transcribe",
            "goodq_audio_diarize",
            "goodq_audio_emotion",
        ]
        
        for env_name in gpu_envs:
            try:
                result = subprocess.run(
                    ["conda", "run", "-n", env_name, "python", "-c",
                     "import torch; print(torch.cuda.is_available())"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and "True" in result.stdout:
                    self._ok(f"{env_name}: CUDA available")
                else:
                    issue = HealthIssue(
                        category="cuda",
                        severity="critical",
                        description=f"CUDA not available in {env_name}",
                        current_state="CUDA unavailable",
                        expected_state="CUDA should be available",
                        can_auto_heal=False,
                        heal_action=f"Run: pwsh scripts/enable_cuda.ps1"
                    )
                    issues.append(issue)
                    self._fail(f"{env_name}: CUDA not available")
                    
            except Exception as e:
                self._warn(f"{env_name}: Could not check CUDA ({e})")
        
        return issues
    
    def check_critical_tools(self) -> List[HealthIssue]:
        """Verify critical external tools are accessible"""
        self._check_header("Critical Tools")
        issues = []
        
        tools = {
            "ffmpeg": "L:/Tools/ffmpeg/bin/ffmpeg.exe",
            "tesseract": "L:/Tools/tesseract/tesseract.exe",
            "whisper-cli": "L:/Tools/whisper/whisper-cli.exe",
        }
        
        for tool_name, tool_path in tools.items():
            if Path(tool_path).exists():
                self._ok(f"{tool_name}: {tool_path}")
            else:
                issue = HealthIssue(
                    category="tools",
                    severity="critical",
                    description=f"Missing tool: {tool_name}",
                    current_state="Not found",
                    expected_state=tool_path,
                    can_auto_heal=False,
                    heal_action=f"Install {tool_name} to {tool_path}"
                )
                issues.append(issue)
                self._fail(f"{tool_name}: not found at {tool_path}")
        
        return issues
    
    def run_all_checks(self) -> HealthReport:
        """Run all health checks"""
        self._print("\n" + "="*70, Color.BOLD + Color.CYAN)
        self._print("GoodQ4All Unified Health Check", Color.BOLD + Color.CYAN)
        self._print(f"Auto-heal: {self.auto_heal}", Color.CYAN)
        self._print("="*70 + "\n", Color.BOLD + Color.CYAN)
        
        # Run all checks
        all_issues = []
        all_issues.extend(self.check_environment_variables())
        all_issues.extend(self.check_dataset_paths())
        all_issues.extend(self.check_cache_locations())
        all_issues.extend(self.check_fragmented_caches())
        all_issues.extend(self.check_conda_environments())
        all_issues.extend(self.check_cuda_availability())
        all_issues.extend(self.check_critical_tools())
        
        # Add all issues to report
        for issue in all_issues:
            self.report.add_issue(issue)
        
        # Determine overall status
        critical_count = len([i for i in all_issues if i.severity == "critical"])
        warning_count = len([i for i in all_issues if i.severity == "warning"])
        
        if critical_count > 0:
            self.report.overall_status = "RED"
        elif warning_count > 0:
            self.report.overall_status = "YELLOW"
        else:
            self.report.overall_status = "GREEN"
        
        # Print summary
        self._print_summary()
        
        return self.report
    
    def _print_summary(self):
        """Print health check summary"""
        self._print("\n" + "="*70, Color.BOLD + Color.CYAN)
        self._print("Health Check Summary", Color.BOLD + Color.CYAN)
        self._print("="*70, Color.BOLD + Color.CYAN)
        
        status_color = {
            "GREEN": Color.GREEN,
            "YELLOW": Color.YELLOW,
            "RED": Color.RED
        }
        
        self._print(f"\nOverall Status: {self.report.overall_status}",
                   status_color.get(self.report.overall_status, ""))
        self._print(f"Checks Passed: {self.report.checks_passed}", Color.GREEN)
        self._print(f"Checks Failed: {self.report.checks_failed}", Color.RED)
        self._print(f"Issues Found: {len(self.report.issues)}", Color.YELLOW)
        self._print(f"Auto-Healed: {self.report.auto_healed}", Color.CYAN)
        
        # List unresolved critical issues
        critical_issues = [i for i in self.report.issues 
                          if i.severity == "critical" and not i.fixed]
        if critical_issues:
            self._print(f"\n{Color.RED}Critical Issues Requiring Attention:{Color.END}", Color.RED)
            for issue in critical_issues:
                self._print(f"  • {issue.description}", Color.RED)
                if issue.heal_action:
                    self._print(f"    Action: {issue.heal_action}", Color.YELLOW)
        
        # List warnings
        warnings = [i for i in self.report.issues 
                   if i.severity == "warning" and not i.fixed]
        if warnings:
            self._print(f"\n{Color.YELLOW}Warnings:{Color.END}", Color.YELLOW)
            for warning in warnings:
                self._print(f"  • {warning.description}", Color.YELLOW)
                if warning.heal_action:
                    self._print(f"    Suggestion: {warning.heal_action}", Color.CYAN)
        
        self._print("\n" + "="*70 + "\n", Color.CYAN)


def main():
    parser = argparse.ArgumentParser(
        description="GoodQ4All Unified Health Check with Self-Healing"
    )
    parser.add_argument(
        "--auto-heal",
        action="store_true",
        help="Automatically fix issues where possible"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    checker = UnifiedHealthChecker(auto_heal=args.auto_heal, verbose=args.verbose)
    report = checker.run_all_checks()
    
    if args.json:
        print(json.dumps(report.summary(), indent=2))
    
    # Exit with appropriate code
    if report.overall_status == "RED":
        sys.exit(1)
    elif report.overall_status == "YELLOW":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
