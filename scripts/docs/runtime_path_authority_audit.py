from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "docs" / "archive" / "reports" / "RUNTIME_PATH_AUTHORITY_REPORT.md"


CANONICAL_FILES = [
    Path("steps/common/config_loader.py"),
    Path("configs/config.yaml"),
]

SECONDARY_FILES = [
    Path("configs/paths.py"),
]

ACTIVE_RUNTIME_FILES = [
    Path("LAUNCH_GOODQ.ps1"),
    Path("cli/run_ingestion.py"),
    Path("cli/watchdog.py"),
    Path("cli/graph_query.py"),
    Path("cli/monitor_ingestion.py"),
    Path("cli/system_status.py"),
    Path("steps/video/scene_visual_embeddings.py"),
    Path("steps/video/cross_modal_harmonizer.py"),
    Path("steps/audio_emotion/step.py"),
    Path("steps/audio_transcribe/step.py"),
    Path("steps/audio_diarize/step.py"),
    Path("steps/image_caption/step.py"),
    Path("steps/object_detect/step.py"),
    Path("steps/sentiment/step.py"),
    Path("steps/sentiment/step_fixed.py"),
    Path("steps/common/conda_runner.py"),
    Path("steps/common/memory_writer.py"),
    Path("scripts/qdrant/START_QDRANT.bat"),
    Path("scripts/qdrant/INSTALL_QDRANT_SERVICE.bat"),
    Path("scripts/analytics_cli.py"),
    Path("scripts/analytics_dashboard.py"),
    Path("scripts/analytics_query.py"),
    Path("scripts/build_knowledge_graph_from_db.py"),
    Path("scripts/build_kg_standalone.py"),
    Path("scripts/build_unified_kg.py"),
    Path("scripts/monitor_ingestion.py"),
    Path("scripts/monitor_ingestion_realtime.py"),
    Path("scripts/monitor_ingestion_progress.py"),
    Path("scripts/utils/check_watchdog_status.py"),
]

# Filter out non-existent files (e.g. archived legacy steps)
ACTIVE_RUNTIME_FILES = [f for f in ACTIVE_RUNTIME_FILES if (REPO_ROOT / f).exists()]



ACTIVE_EXPECTATIONS = {
    Path("cli/run_ingestion.py"): {
        "required": [
            "get_runtime_paths",
            "Path(runtime_paths[\"import_inbox\"])",
            "Path(runtime_paths[\"output_directory\"]) / \"scene_ingest_results.json\"",
            "processing_dir / 'video' / 'frames'",
            "audio_artifact_dir / 'chunks'",
        ],
        "forbidden": [
            "Path('import_inbox')",
            "Path('logs/scene_ingest_results.json')",
            "Path('logs/scene_ingest')",
            "video_workspace / 'temporal_index.json'",
            "GOODQ_DATA_ROOT",
            "cfg.get('data_dir', 'data')",
        ],
    },
    Path("cli/watchdog.py"): {
        "required": [
            "get_runtime_paths",
            "_resolve_watchdog_paths",
            "\"watchdog_lock_file\"",
            "\"watchdog_state_file\"",
        ],
        "forbidden": [
            "GOODQ_DATA_ROOT",
            "_default_processing_root",
            "WATCH_DIR = REPO_ROOT",
            "STATE_FILE = REPO_ROOT",
            "from configs.paths import LOGS_DIR",
        ],
    },
    Path("LAUNCH_GOODQ.ps1"): {
        "required": [
            "Load-ConfigSnapshot",
            "Canonical config snapshot is missing one or more required runtime paths.",
            "qdrant_storage",
            "GOODQ_QDRANT_STORAGE",
        ],
        "forbidden": [
            "if ($env:GOODQ_DB_PATH)",
            "if ($env:GOODQ_KG_DB_PATH)",
            "if ($env:GOODQ_PROCESSING_ROOT)",
            "if ($env:GOODQ_QDRANT_URL)",
        ],
    },
    Path("steps/video/scene_visual_embeddings.py"): {
        "required": ["get_runtime_paths"],
        "forbidden": ["GOODQ_DATA_ROOT", "Path.cwd() / \"processing\""],
    },
    Path("steps/video/cross_modal_harmonizer.py"): {
        "required": ["get_runtime_paths"],
        "forbidden": ["GOODQ_DATA_ROOT", "Path.cwd() / \"processing\""],
    },
    Path("steps/common/conda_runner.py"): {
        "required": ["get_runtime_paths(load_configs({}), \"models_cache\")"],
        "forbidden": ["GOODQ_DATA_ROOT", "Path.cwd() / \"models\""],
    },
    Path("steps/audio_emotion/step.py"): {
        "required": ["get_runtime_paths(load_configs({}), \"models_cache\")"],
        "forbidden": ["GOODQ_DATA_ROOT", "Path.cwd() / \"models\""],
    },
    Path("steps/audio_transcribe/step.py"): {
        "required": ["get_runtime_paths(load_configs({}), \"models_cache\")"],
        "forbidden": ["GOODQ_DATA_ROOT", "os.getcwd(), \"models\""],
    },
    Path("steps/image_caption/step.py"): {
        "required": ["get_runtime_paths(load_configs({}), \"models_cache\")"],
        "forbidden": ["GOODQ_DATA_ROOT", "Path.cwd() / \"models\""],
    },
    Path("steps/object_detect/step.py"): {
        "required": ["get_runtime_paths(load_configs({}), \"models_cache\")"],
        "forbidden": ["GOODQ_DATA_ROOT", "Path.cwd() / \"models\""],
    },
    Path("steps/sentiment/step.py"): {
        "required": ["get_runtime_paths(load_configs({}), \"models_cache\")"],
        "forbidden": ["GOODQ_DATA_ROOT", "Path.cwd() / \"models\""],
    },
    Path("steps/sentiment/step_fixed.py"): {
        "required": ["get_runtime_paths(load_configs({}), \"models_cache\")"],
        "forbidden": ["GOODQ_DATA_ROOT", "Path.cwd() / \"models\""],
    },
    Path("scripts/qdrant/START_QDRANT.bat"): {
        "required": ["qdrant_storage", "steps.common.config_loader", "GOODQ_LOG_DIR"],
        "forbidden": ["GOODQ_DATA_ROOT=%REPO_DRIVE%\\_DATA", "QDRANT_STORAGE_PATH=%GOODQ_DATA_ROOT%"],
    },
    Path("scripts/qdrant/INSTALL_QDRANT_SERVICE.bat"): {
        "required": ["qdrant_storage", "GOODQ_LOG_DIR", "steps.common.config_loader"],
        "forbidden": ["GOODQ_DATA_ROOT=%REPO_DRIVE%\\_DATA", "QDRANT_STORAGE_PATH=%GOODQ_DATA_ROOT%"],
    },
}


LEGACY_SCAN_TOKENS = [
    "L:/_DATA",
    "L:\\_DATA",
    "L:/goodq4all/config.yaml",
    "with open('config.yaml'",
    'with open("config.yaml"',
    "GOODQ_DATA_ROOT",
]


@dataclass
class Finding:
    severity: str
    area: str
    file: str
    detail: str


def _read_text(rel_path: Path) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")


def _format_file_list(paths: Iterable[Path]) -> str:
    lines = []
    for path in paths:
        lines.append(f"- `{path.as_posix()}`")
    return "\n".join(lines)


def _evaluate_active_checks() -> list[Finding]:
    findings: list[Finding] = []
    for rel_path, expectations in ACTIVE_EXPECTATIONS.items():
        if not (REPO_ROOT / rel_path).exists():
            continue
        text = _read_text(rel_path)
        for token in expectations.get("required", []):
            if token not in text:
                findings.append(
                    Finding(
                        severity="HIGH",
                        area="active_runtime",
                        file=rel_path.as_posix(),
                        detail=f"missing required token: {token}",
                    )
                )
        for token in expectations.get("forbidden", []):
            if token in text:
                findings.append(
                    Finding(
                        severity="HIGH",
                        area="active_runtime",
                        file=rel_path.as_posix(),
                        detail=f"forbidden token still present: {token}",
                    )
                )
    return findings


def _scan_legacy_scripts() -> list[Finding]:
    findings: list[Finding] = []
    active_set = {path.as_posix() for path in ACTIVE_RUNTIME_FILES}
    protected = active_set | {path.as_posix() for path in CANONICAL_FILES + SECONDARY_FILES}
    protected.add("scripts/docs/runtime_path_authority_audit.py")

    for file_path in sorted((REPO_ROOT / "scripts").rglob("*")):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(REPO_ROOT).as_posix()
        if "__pycache__" in rel_path or file_path.suffix == ".pyc":
            continue
        if rel_path.startswith("scripts/archive/"):
            continue
        if rel_path in protected:
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        matches = [token for token in LEGACY_SCAN_TOKENS if token in text]
        if matches:
            findings.append(
                Finding(
                    severity="MEDIUM",
                    area="legacy_or_diagnostic",
                    file=rel_path,
                    detail=", ".join(matches[:3]),
                )
            )
    return findings


def _scan_test_and_docs() -> list[Finding]:
    findings: list[Finding] = []
    for root_name, severity in (("tests", "LOW"), ("docs", "LOW")):
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for file_path in sorted(root.rglob("*")):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(REPO_ROOT).as_posix()
            if "__pycache__" in rel_path or file_path.suffix == ".pyc":
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            matches = [token for token in LEGACY_SCAN_TOKENS if token in text]
            if matches:
                findings.append(
                    Finding(
                        severity=severity,
                        area=root_name,
                        file=rel_path,
                        detail=", ".join(matches[:3]),
                    )
                )
    return findings


def _check_config_contract() -> list[Finding]:
    findings: list[Finding] = []
    config_text = _read_text(Path("configs/config.yaml"))
    required_keys = [
        "data_root:",
        "import_inbox:",
        "processing:",
        "log_dir:",
        "db_path:",
        "knowledge_graph_db:",
        "qdrant_storage:",
        "watchdog_state_file:",
        "watchdog_lock_file:",
        "processed:",
        "failed:",
    ]
    for key in required_keys:
        if key not in config_text:
            findings.append(
                Finding(
                    severity="HIGH",
                    area="config_contract",
                    file="configs/config.yaml",
                    detail=f"missing config key: {key}",
                )
            )
    return findings


def _write_report(active: list[Finding], config_findings: list[Finding], legacy: list[Finding], docs_tests: list[Finding]) -> None:
    high_findings = [f for f in active + config_findings if f.severity == "HIGH"]
    medium_findings = [f for f in legacy if f.severity == "MEDIUM"]
    low_findings = [f for f in docs_tests if f.severity == "LOW"]

    report_lines = [
        "# Runtime Path Authority Report",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        "- Canonical authority: `steps.common.config_loader.load_configs()` -> `configs/config.yaml`",
        f"- Active runtime HIGH findings: {len(high_findings)}",
        f"- Legacy/diagnostic MEDIUM findings: {len(medium_findings)}",
        f"- Test/docs LOW findings: {len(low_findings)}",
        "",
        "## Runtime Path Authority Map",
        "",
        "### Category: Canonical",
        _format_file_list(CANONICAL_FILES),
        "",
        "### Category: Secondary",
        _format_file_list(SECONDARY_FILES),
        "",
        "### Category: Active Runtime Surfaces",
        _format_file_list(ACTIVE_RUNTIME_FILES),
        "",
        "## Active Runtime Verification",
        "",
        "| Status | Area | File | Detail |",
        "|---|---|---|---|",
    ]

    if high_findings:
        for finding in high_findings:
            report_lines.append(
                f"| FAIL | {finding.area} | `{finding.file}` | {finding.detail} |"
            )
    else:
        report_lines.append("| PASS | active_runtime | `core runtime surfaces` | No forbidden fallback tokens detected in audited active runtime files. |")
        report_lines.append("| PASS | config_contract | `configs/config.yaml` | Canonical runtime path keys are present, including Qdrant and watchdog path bindings. |")

    report_lines.extend(
        [
            "",
            "## Conflict Table",
            "",
            "| Conflict Class | Status | Notes |",
            "|---|---|---|",
            f"| Multiple runtime root definitions in active entrypoints | {'CLEAR' if not high_findings else 'OPEN'} | Active entrypoints now resolve through canonical config helpers. |",
            f"| Repo-relative inbox/log/workspace defaults | {'CLEAR' if not high_findings else 'OPEN'} | `run_ingestion` and `watchdog` defaults were moved behind canonical config resolution. |",
            f"| Artifact duplication across workspace vs processing | {'CLEAR' if not any('temporal_index' in f.detail for f in high_findings) else 'OPEN'} | Final scene manifests and temporal index now persist under `paths.processing`. |",
            f"| Qdrant storage outside config authority | {'CLEAR' if not any('qdrant' in f.detail.lower() for f in high_findings) else 'OPEN'} | Qdrant startup scripts resolve storage via canonical config. |",
            "",
            "## Risk Assessment",
            "",
            "| Risk Level | Issue | Example Files | Runtime Impact |",
            "|---|---|---|---|",
        ]
    )

    if high_findings:
        for finding in high_findings:
            report_lines.append(
                f"| HIGH | Active runtime authority drift | `{finding.file}` | {finding.detail} |"
            )
    else:
        report_lines.append("| LOW | Active runtime authority | `cli/run_ingestion.py`, `cli/watchdog.py`, `LAUNCH_GOODQ.ps1` | Canonical config authority is consistent across audited runtime surfaces. |")

    if medium_findings:
        example_files = ", ".join(f"`{finding.file}`" for finding in medium_findings[:5])
        report_lines.append(
            f"| MEDIUM | Legacy and diagnostic scripts still contain historical path references | {example_files} | No primary runtime impact, but ad hoc operator runs could still observe old roots. |"
        )
    else:
        report_lines.append("| LOW | Legacy utility drift | `scripts/*` | No medium-risk legacy path authorities detected outside active runtime surfaces. |")

    if low_findings:
        example_files = ", ".join(f"`{finding.file}`" for finding in low_findings[:5])
        report_lines.append(
            f"| LOW | Tests and docs still contain historical path references | {example_files} | Audit noise only; no production runtime impact. |"
        )
    else:
        report_lines.append("| LOW | Tests/docs drift | `tests/*`, `docs/*` | No residual test/doc path references detected by this audit. |")

    report_lines.extend(
        [
            "",
            "## Recommended Canonical Runtime Authority",
            "",
            "The current safest runtime authority is `steps.common.config_loader.load_configs()` backed by `configs/config.yaml`. The active runtime entrypoints and helper modules audited here now derive data root, inbox, processing, logs, databases, watchdog paths, Qdrant storage, and final scene artifacts from that authority rather than from repo-relative or environment-derived root defaults.",
            "",
            "## Residual Legacy Examples",
            "",
        ]
    )

    if medium_findings:
        for finding in medium_findings[:20]:
            report_lines.append(f"- `{finding.file}`: {finding.detail}")
    else:
        report_lines.append("- No medium-risk legacy script path authorities detected by this audit.")

    report_lines.extend(["", "## Test / Docs Examples", ""])
    if low_findings:
        for finding in low_findings[:20]:
            report_lines.append(f"- `{finding.file}`: {finding.detail}")
    else:
        report_lines.append("- No low-risk test/doc drift detected by this audit.")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    config_findings = _check_config_contract()
    active_findings = _evaluate_active_checks()
    legacy_findings = _scan_legacy_scripts()
    docs_tests_findings = _scan_test_and_docs()
    _write_report(active_findings, config_findings, legacy_findings, docs_tests_findings)
    return 1 if any(f.severity == "HIGH" for f in active_findings + config_findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
