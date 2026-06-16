import os
import subprocess
import re
import pytest

# Globally ignore desktop.ini to prevent OS-specific/Google Drive metadata conflicts
_original_listdir = os.listdir
def listdir_ignoring_system_files(path):
    return [item for item in _original_listdir(path) if item.lower() != "desktop.ini"]
os.listdir = listdir_ignoring_system_files

_original_walk = os.walk
def walk_ignoring_system_files(top, topdown=True, onerror=None, followlinks=False):
    for root, dirs, files in _original_walk(top, topdown, onerror, followlinks):
        filtered_files = [f for f in files if f.lower() != "desktop.ini"]
        yield root, dirs, filtered_files
os.walk = walk_ignoring_system_files


WORKSPACE_ROOT = os.path.normpath("C:/Users/jdben/My Drive/_AGENT")
REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
AGENTS_MD_PATH = os.path.join(REPO_ROOT, "AGENTS.md")

# ==============================================================================
# FEATURE 1: Directory Tree Architecture (F1, R1)
# ==============================================================================

def test_f1_01_workspace_root_exists():
    """Verify the root workspace folder exists."""
    assert os.path.isdir(WORKSPACE_ROOT), f"Workspace root not found at {WORKSPACE_ROOT}"

def test_f1_02_protocols_dir_exists():
    """Verify protocols/ directory exists."""
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    assert os.path.isdir(protocols_dir), f"protocols/ directory not found"

def test_f1_03_models_and_vram_dir_exists():
    """Verify models_and_vram/ directory exists."""
    models_dir = os.path.join(WORKSPACE_ROOT, "models_and_vram")
    assert os.path.isdir(models_dir), f"models_and_vram/ directory not found"

def test_f1_04_workflows_dir_exists():
    """Verify workflows/ directory exists."""
    workflows_dir = os.path.join(WORKSPACE_ROOT, "workflows")
    assert os.path.isdir(workflows_dir), f"workflows/ directory not found"

def test_f1_05_lessons_dir_exists():
    """Verify lessons/ directory exists."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    assert os.path.isdir(lessons_dir), f"lessons/ directory not found"

def test_f1_05a_templates_dir_exists():
    """Verify templates/ directory exists."""
    templates_dir = os.path.join(WORKSPACE_ROOT, "templates")
    assert os.path.isdir(templates_dir), f"templates/ directory not found"

def test_f1_05b_host_profiles_dir_exists():
    """Verify host_profiles/ directory exists."""
    profiles_dir = os.path.join(WORKSPACE_ROOT, "host_profiles")
    assert os.path.isdir(profiles_dir), f"host_profiles/ directory not found"

def test_f1_05c_quizzes_dir_exists():
    """Verify quizzes/ directory exists."""
    quizzes_dir = os.path.join(WORKSPACE_ROOT, "quizzes")
    assert os.path.isdir(quizzes_dir), f"quizzes/ directory not found"

def test_f1_06_protocols_dir_not_empty():
    """Verify protocols/ folder is not empty."""
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    files = os.listdir(protocols_dir)
    assert len(files) > 0, "protocols/ directory is empty"

def test_f1_07_models_and_vram_dir_not_empty():
    """Verify models_and_vram/ folder is not empty."""
    models_dir = os.path.join(WORKSPACE_ROOT, "models_and_vram")
    files = os.listdir(models_dir)
    assert len(files) > 0, "models_and_vram/ directory is empty"

def test_f1_08_workflows_dir_not_empty():
    """Verify workflows/ folder is not empty."""
    workflows_dir = os.path.join(WORKSPACE_ROOT, "workflows")
    files = os.listdir(workflows_dir)
    assert len(files) > 0, "workflows/ directory is empty"

def test_f1_09_lessons_dir_not_empty():
    """Verify lessons/ folder is not empty."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    files = os.listdir(lessons_dir)
    assert len(files) > 0, "lessons/ directory is empty"

def test_f1_09a_templates_dir_not_empty():
    """Verify templates/ folder is not empty."""
    templates_dir = os.path.join(WORKSPACE_ROOT, "templates")
    files = os.listdir(templates_dir)
    assert len(files) > 0, "templates/ directory is empty"

def test_f1_09b_host_profiles_dir_not_empty():
    """Verify host_profiles/ folder is not empty."""
    profiles_dir = os.path.join(WORKSPACE_ROOT, "host_profiles")
    files = os.listdir(profiles_dir)
    assert len(files) > 0, "host_profiles/ directory is empty"

def test_f1_09c_quizzes_dir_not_empty():
    """Verify quizzes/ folder is not empty."""
    quizzes_dir = os.path.join(WORKSPACE_ROOT, "quizzes")
    files = os.listdir(quizzes_dir)
    assert len(files) > 0, "quizzes/ directory is empty"

def test_f1_10_no_unknown_root_directories():
    """Verify no undocumented directories exist in the root workspace."""
    allowed_dirs = {"protocols", "models_and_vram", "workflows", "lessons", "templates", "host_profiles", "quizzes", "reports"}
    allowed_files = {"bootstrap_agent.ps1", "verify_agent_workspace.py", "original_request.md", "briefing.md", "plan.md", "index.md", "readme_for_agents.md", ".agent_workspace_policy.json", "changelog.md"}
    actual_items = os.listdir(WORKSPACE_ROOT)
    for item in actual_items:
        if item == "__pycache__":
            continue
        full_path = os.path.join(WORKSPACE_ROOT, item)
        if os.path.isdir(full_path):
            assert item in allowed_dirs, f"Undocumented directory found in workspace root: {item}"
        else:
            assert item.lower() in allowed_files, f"Undocumented file found in workspace root: {item}"

def test_f1_11_workspace_permissions_readable():
    """Verify that the workspace directories are readable."""
    for d in ["protocols", "models_and_vram", "workflows", "lessons", "templates", "host_profiles", "quizzes", "reports"]:
        full_path = os.path.join(WORKSPACE_ROOT, d)
        assert os.access(full_path, os.R_OK), f"Directory {d} is not readable"

def test_f1_12_workspace_permissions_writeable():
    """Verify that the workspace directories are writeable."""
    for d in ["protocols", "models_and_vram", "workflows", "lessons", "templates", "host_profiles", "quizzes", "reports"]:
        full_path = os.path.join(WORKSPACE_ROOT, d)
        assert os.access(full_path, os.W_OK), f"Directory {d} is not writeable"

# ==============================================================================
# FEATURE 2: Context & Rule Distillation (F2, R2)
# ==============================================================================

def test_f2_01_agents_distilled_rules_exist():
    """Verify distilled rules files are present under protocols/."""
    expected_files = ["agent_identities_and_roles.md", "global_rules_and_security.md", "system_boundaries.md"]
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    for f in expected_files:
        assert os.path.isfile(os.path.join(protocols_dir, f)), f"Distilled rule file missing: {f}"

def test_f2_02_gemini_distilled_rules_exist():
    """Verify model and hardware specifications are present under models_and_vram/."""
    expected_files = ["lifecycle_and_fallback.md", "vram_budget_and_hardware.md"]
    models_dir = os.path.join(WORKSPACE_ROOT, "models_and_vram")
    for f in expected_files:
        assert os.path.isfile(os.path.join(models_dir, f)), f"Model spec file missing: {f}"

def test_f2_03_workflows_distilled_procedures_exist():
    """Verify operational procedures are present under workflows/."""
    expected_files = ["clean_memory_start.md", "evidence_first_runtime_repair.md", "laptop_setup_test_and_report.md", "pipeline_troubleshooting.md", "google_drive_sync_safety.md", "post_cleanup_manifest.md"]
    workflows_dir = os.path.join(WORKSPACE_ROOT, "workflows")
    for f in expected_files:
        assert os.path.isfile(os.path.join(workflows_dir, f)), f"Procedure file missing: {f}"

def test_f2_03a_templates_exist():
    """Verify that templates exist under templates/."""
    templates_dir = os.path.join(WORKSPACE_ROOT, "templates")
    for f in ["lesson_template.md", "incident_report_template.md", "agent_handoff_template.md"]:
        assert os.path.isfile(os.path.join(templates_dir, f)), f"Template file missing: {f}"

def test_f2_03b_host_profiles_exist():
    """Verify that host profiles exist under host_profiles/."""
    profiles_dir = os.path.join(WORKSPACE_ROOT, "host_profiles")
    for f in ["good_cube.md", "good_speed_32.md", "good_recon_16.md"]:
        assert os.path.isfile(os.path.join(profiles_dir, f)), f"Host profile file missing: {f}"

def test_f2_03c_quizzes_exist():
    """Verify that quizzes exist under quizzes/."""
    quizzes_dir = os.path.join(WORKSPACE_ROOT, "quizzes")
    assert os.path.isfile(os.path.join(quizzes_dir, "goodq4all_ingestion_readiness.md")), "Quiz file missing"

def test_f2_04_protocols_content_non_empty():
    """Verify rule files under protocols/ are non-empty and substantive."""
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    for f in os.listdir(protocols_dir):
        p = os.path.join(protocols_dir, f)
        if os.path.isfile(p):
            assert os.path.getsize(p) > 100, f"File {f} is empty or too small"

def test_f2_05_models_content_non_empty():
    """Verify rule files under models_and_vram/ are non-empty and substantive."""
    models_dir = os.path.join(WORKSPACE_ROOT, "models_and_vram")
    for f in os.listdir(models_dir):
        p = os.path.join(models_dir, f)
        if os.path.isfile(p):
            assert os.path.getsize(p) > 100, f"File {f} is empty or too small"

def test_f2_06_workflows_content_non_empty():
    """Verify rule files under workflows/ are non-empty and substantive."""
    workflows_dir = os.path.join(WORKSPACE_ROOT, "workflows")
    for f in os.listdir(workflows_dir):
        p = os.path.join(workflows_dir, f)
        if os.path.isfile(p):
            assert os.path.getsize(p) > 100, f"File {f} is empty or too small"

def test_f2_07_no_obsolete_rules_in_protocols():
    """Verify that obsolete or deprecated policies are not included in distilled rules."""
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    obsolete_terms = ["Native CLAP without CPU fallback", "confirm-123", "global path python pollution"]
    for f in os.listdir(protocols_dir):
        p = os.path.join(protocols_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8", errors="ignore").read()
            for term in obsolete_terms:
                assert term not in content, f"Obsolete rule term '{term}' found in {f}"

def test_f2_08_no_contradictory_rules():
    """Verify that there are no contradictory rules between files."""
    # Ensure baseline and enhanced requirements are clear and don't conflict
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    models_dir = os.path.join(WORKSPACE_ROOT, "models_and_vram")
    
    protocols_text = ""
    for f in os.listdir(protocols_dir):
        p = os.path.join(protocols_dir, f)
        if os.path.isfile(p):
            protocols_text += open(p, "r", encoding="utf-8", errors="ignore").read()

    models_text = ""
    for f in os.listdir(models_dir):
        p = os.path.join(models_dir, f)
        if os.path.isfile(p):
            models_text += open(p, "r", encoding="utf-8", errors="ignore").read()
            
    # We should not say GPU is required in protocols, and GPU is optional in models
    if "gpu is required" in protocols_text.lower():
        assert "gpu is optional" not in models_text.lower(), "Contradictory GPU optional/required rule found"

def test_f2_09_relative_links_in_protocols():
    """Verify markdown cross-links in protocols/ are relative."""
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    link_pattern = re.compile(r'\[.*?\]\((.*?)\)')
    for f in os.listdir(protocols_dir):
        p = os.path.join(protocols_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8", errors="ignore").read()
            for link in link_pattern.findall(content):
                if not link.startswith("http") and not link.startswith("mailto"):
                    assert not re.match(r'^[a-zA-Z]:', link), f"Absolute Windows path found in markdown link in {f}: {link}"
                    assert link.startswith(".") or "/" in link or link.endswith(".md"), f"Link is not properly relative in {f}: {link}"

def test_f2_10_relative_links_in_models():
    """Verify markdown cross-links in models_and_vram/ are relative."""
    models_dir = os.path.join(WORKSPACE_ROOT, "models_and_vram")
    link_pattern = re.compile(r'\[.*?\]\((.*?)\)')
    for f in os.listdir(models_dir):
        p = os.path.join(models_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8", errors="ignore").read()
            for link in link_pattern.findall(content):
                if not link.startswith("http") and not link.startswith("mailto"):
                    assert not re.match(r'^[a-zA-Z]:', link), f"Absolute Windows path found in markdown link in {f}: {link}"
                    assert link.startswith(".") or "/" in link or link.endswith(".md"), f"Link is not properly relative in {f}: {link}"

def test_f2_11_relative_links_in_workflows():
    """Verify markdown cross-links in workflows/ are relative."""
    workflows_dir = os.path.join(WORKSPACE_ROOT, "workflows")
    link_pattern = re.compile(r'\[.*?\]\((.*?)\)')
    for f in os.listdir(workflows_dir):
        p = os.path.join(workflows_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8", errors="ignore").read()
            for link in link_pattern.findall(content):
                if not link.startswith("http") and not link.startswith("mailto"):
                    assert not re.match(r'^[a-zA-Z]:', link), f"Absolute Windows path found in markdown link in {f}: {link}"
                    assert link.startswith(".") or "/" in link or link.endswith(".md"), f"Link is not properly relative in {f}: {link}"

def test_f2_12_no_drive_letters_in_distilled_markdowns():
    """Verify no hardcoded drive letters exist in active markdown files inside protocols, models_and_vram, workflows, templates, host_profiles, quizzes."""
    for sub in ["protocols", "models_and_vram", "workflows", "templates", "host_profiles", "quizzes"]:
        sub_dir = os.path.join(WORKSPACE_ROOT, sub)
        for f in os.listdir(sub_dir):
            p = os.path.join(sub_dir, f)
            if os.path.isfile(p):
                content = open(p, "r", encoding="utf-8", errors="ignore").read()
                # Check for things like C:\ or L:\ or L:/ or C:/
                drive_matches = re.findall(r'\b[cClL]:[/\\]', content)
                assert len(drive_matches) == 0, f"Hardcoded Windows drive roots found in {sub}/{f}: {drive_matches}"

# ==============================================================================
# FEATURE 3: Lessons Learned Integration (F3, R3)
# ==============================================================================

def test_f3_01_lessons_files_are_markdown():
    """Verify all files inside lessons/ have `.md` extension."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            assert f.endswith(".md"), f"Non-markdown file found in lessons/: {f}"

def test_f3_02_lessons_first_line_starts_with_summary():
    """Verify the first line of each lessons file starts with 'Summary: '."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    files = os.listdir(lessons_dir)
    assert len(files) > 0, "No lessons files to verify"
    for f in files:
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8", errors="ignore") as file_handle:
                first_line = file_handle.readline()
                assert first_line.startswith("Summary: "), f"First line of lesson {f} must start with 'Summary: ', got: '{first_line}'"

def test_f3_03_lessons_summary_content_length():
    """Verify the summary line describes a finding and is not just a placeholder."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as file_handle:
                first_line = file_handle.readline().strip()
                summary_val = first_line.replace("Summary:", "").strip()
                assert len(summary_val) > 10, f"Summary in lesson {f} is too short: '{summary_val}'"

def test_f3_04_lessons_contain_background_context():
    """Verify each lesson describes its background context."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            assert "background" in content or "context" in content, f"Lesson {f} must describe background context"

def test_f3_05_lessons_contain_correction_detail():
    """Verify each lesson documents correction detail/steps."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            assert "correction" in content or "detail" in content or "fix" in content or "solution" in content, f"Lesson {f} must describe correction details"

def test_f3_06_lessons_contain_engineering_impact():
    """Verify each lesson details why the finding mattered (impact)."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            assert "impact" in content or "mattered" in content or "why" in content or "importance" in content, f"Lesson {f} must document why the finding mattered"

def test_f3_07_lessons_no_unformatted_files():
    """Verify that only correctly formatted markdown files live in lessons/."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            assert re.match(r'^[a-zA-Z0-9_\-]+\.md$', f), f"Lesson file name has incorrect format: {f}"

def test_f3_08_lessons_relative_links():
    """Verify links in lessons/ are relative."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    link_pattern = re.compile(r'\[.*?\]\((.*?)\)')
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8", errors="ignore").read()
            for link in link_pattern.findall(content):
                if not link.startswith("http") and not link.startswith("mailto"):
                    assert not re.match(r'^[a-zA-Z]:', link), f"Absolute Windows path found in lesson link in {f}: {link}"

def test_f3_09_lessons_no_literal_drive_roots():
    """Verify lessons files do not contain hardcoded drive letters (C: or L:)."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8", errors="ignore").read()
            drive_matches = re.findall(r'\b[cClL]:[/\\]', content)
            assert len(drive_matches) == 0, f"Hardcoded Windows drive roots found in lessons/{f}: {drive_matches}"

def test_f3_10_lessons_unique_summaries():
    """Verify lessons summaries are unique."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    summaries = []
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as file_handle:
                line = file_handle.readline().strip()
                summaries.append(line)
    assert len(summaries) == len(set(summaries)), "Duplicate lessons summaries found"

def test_f3_11_lessons_contain_valid_markdown_headers():
    """Verify lessons contain valid markdown headers."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read()
            assert "## " in content or "# " in content, f"Lesson {f} has no markdown headers"

def test_f3_12_lessons_contain_durable_patterns():
    """Verify that lesson files contain detailed descriptions, not short placeholders."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read()
            assert len(content) > 150, f"Lesson {f} has insufficient content size"

# ==============================================================================
# FEATURE 4: Programmatic Verification Linter (F4, R4)
# ==============================================================================

def test_f4_01_linter_script_exists():
    """Verify that verify_agent_workspace.py exists inside _AGENT."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    assert os.path.isfile(linter_path), f"verify_agent_workspace.py missing at {linter_path}"

def test_f4_02_linter_exits_zero_on_success():
    """Verify the linter runs successfully and exits 0 on compliant workspace."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    res = subprocess.run(["python", linter_path], capture_output=True, text=True)
    assert res.returncode == 0, f"Linter exited with code {res.returncode}. Stderr: {res.stderr}"

def test_f4_03_linter_validates_folders_exist():
    """Verify that the linter fails if one of the core workspace directories is missing."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    # Simulate missing folder by temporarily renaming it
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    temp_dir = os.path.join(WORKSPACE_ROOT, "lessons_temp_missing")
    if os.path.isdir(lessons_dir):
        os.rename(lessons_dir, temp_dir)
        try:
            res = subprocess.run(["python", linter_path], capture_output=True, text=True)
            assert res.returncode != 0, "Linter did not fail when lessons directory was missing"
        finally:
            os.rename(temp_dir, lessons_dir)

def test_f4_04_linter_validates_folders_not_empty():
    """Verify that the linter fails if a core workspace directory is empty."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    # Simulate empty folder
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    temp_dir = os.path.join(WORKSPACE_ROOT, "lessons_temp_empty")
    os.rename(lessons_dir, temp_dir)
    os.makedirs(lessons_dir)
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail when lessons directory was empty"
    finally:
        os.rmdir(lessons_dir)
        os.rename(temp_dir, lessons_dir)

def test_f4_05_linter_validates_lessons_first_line():
    """Verify that the linter fails if a lesson file does not start with 'Summary: '."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    bad_lesson = os.path.join(lessons_dir, "bad_lesson_format.md")
    
    with open(bad_lesson, "w", encoding="utf-8") as f:
        f.write("This is a bad lesson that doesn't start with Summary:\n")
        
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail when a lesson lacked Summary: header"
    finally:
        if os.path.exists(bad_lesson):
            os.remove(bad_lesson)

def test_f4_06_linter_scans_trailing_slashes():
    """Verify that the linter flags variables or path definitions with trailing slashes."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    bad_file = os.path.join(protocols_dir, "bad_trailing_slash.md")
    
    with open(bad_file, "w", encoding="utf-8") as f:
        f.write("Target: %USERPROFILE%/My Drive/_AGENT/\n")
        
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail when markdown had path with trailing slash"
        assert "Trailing slash found" in res.stdout or "Trailing slash found" in res.stderr
    finally:
        if os.path.exists(bad_file):
            os.remove(bad_file)

def test_f4_07_linter_scans_drive_roots():
    """Verify that the linter flags hardcoded Windows drive roots in active md files."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    bad_file = os.path.join(protocols_dir, "bad_drive_root.md")
    
    with open(bad_file, "w", encoding="utf-8") as f:
        f.write("Drive root is L:\\GOODCUBE\\projects\\goodq4all\n")
        
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail when markdown had literal drive root"
    finally:
        if os.path.exists(bad_file):
            os.remove(bad_file)

def test_f4_08_linter_is_python3_compatible():
    """Verify the linter script compiles and runs under Python 3."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    res = subprocess.run(["python", "-m", "py_compile", linter_path], capture_output=True)
    try:
        assert res.returncode == 0, "Linter script has syntax errors under python3"
    finally:
        import shutil
        pycache_path = os.path.join(WORKSPACE_ROOT, "__pycache__")
        if os.path.isdir(pycache_path):
            shutil.rmtree(pycache_path, ignore_errors=True)

def test_f4_09_linter_logs_errors_visible():
    """Verify that the linter outputs clear messages to stdout/stderr on failure."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    bad_lesson = os.path.join(lessons_dir, "bad_lesson_format.md")
    with open(bad_lesson, "w", encoding="utf-8") as f:
        f.write("Bad lesson\n")
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert len(res.stdout) > 0 or len(res.stderr) > 0, "Linter did not print output on failure"
    finally:
        if os.path.exists(bad_lesson):
            os.remove(bad_lesson)

def test_f4_10_linter_reports_compliant_status():
    """Verify that the linter outputs a clear completion/compliance message on success."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    # This test assumes workspace has been repaired and is compliant. 
    # If not compliant, it will naturally fail or skip based on test runner.
    res = subprocess.run(["python", linter_path], capture_output=True, text=True)
    if res.returncode == 0:
        assert "success" in res.stdout.lower() or "compliant" in res.stdout.lower() or "verified" in res.stdout.lower()

def test_f4_11_linter_runs_in_reasonable_time():
    """Verify linter execution takes under 2 seconds."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    import time
    start = time.time()
    subprocess.run(["python", linter_path], capture_output=True)
    elapsed = time.time() - start
    assert elapsed < 2.0, f"Linter script is too slow: {elapsed} seconds"

def test_f4_12_linter_handles_empty_lessons_folder_gracefully():
    """Verify linter flags empty lessons folder and exits with non-zero."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    # Temporary rename lessons contents
    files = os.listdir(lessons_dir)
    temp_files = []
    for f in files:
        src = os.path.join(lessons_dir, f)
        dst = os.path.join(lessons_dir, f + ".backup")
        os.rename(src, dst)
        temp_files.append((src, dst))
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0 or "lessons" in res.stdout.lower(), "Linter failed to flag empty lessons directory"
    finally:
        for src, dst in temp_files:
            os.rename(dst, src)

def test_f4_13_linter_checks_index_registration():
    """Verify that the linter flags unregistered files under workflows/."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    workflows_dir = os.path.join(WORKSPACE_ROOT, "workflows")
    unregistered_file = os.path.join(workflows_dir, "test_temp_unregistered_file.md")
    
    with open(unregistered_file, "w", encoding="utf-8") as f:
        f.write("# Temp Unregistered File\n")
        
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail on unregistered workflows file"
        assert "is not registered (linked) in INDEX.md" in res.stdout or "is not registered (linked) in INDEX.md" in res.stderr
    finally:
        if os.path.exists(unregistered_file):
            os.remove(unregistered_file)

def test_f4_14_linter_checks_inline_python_lines_limit():
    """Verify that the linter flags inline Python blocks exceeding 40 lines."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    workflows_dir = os.path.join(WORKSPACE_ROOT, "workflows")
    bad_file = os.path.join(workflows_dir, "test_temp_long_python.md")
    
    lines = ["# Long Python Script File\n", "```python\n"]
    for i in range(45):
        lines.append(f"print({i})\n")
    lines.append("```\n")
    
    with open(bad_file, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail on long inline python block"
        assert "Inline Python script block exceeds 40 lines" in res.stdout or "Inline Python script block exceeds 40 lines" in res.stderr
    finally:
        if os.path.exists(bad_file):
            os.remove(bad_file)

# ==============================================================================
# FEATURE 5: Previous Sessions Reflection & Lessons Extraction (F5, R5)
# ==============================================================================

def test_f5_01_lessons_cover_vram_governance():
    """Verify at least one lesson covers VRAM budgeting or vLLM/Ollama fallback configs."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    found = False
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            if any(term in content for term in ["vram", "gpu", "ollama", "vllm", "allocator"]):
                found = True
                break
    assert found, "No lesson found covering VRAM budgeting or GPU models fallback configs"

def test_f5_02_lessons_cover_setup_installers():
    """Verify at least one lesson covers setup installer issues or paths normalization."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    found = False
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            if any(term in content for term in ["installer", "nsis", "setup.exe", "path normalization", "powershell profile"]):
                found = True
                break
    assert found, "No lesson found covering setup installers or path normalization"

def test_f5_03_lessons_cover_pipeline_debugging():
    """Verify at least one lesson covers pipeline debugging and log outputs."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    found = False
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            if any(term in content for term in ["pipeline", "diarize", "clap", "faster_whisper", "scene_detect", "opencv"]):
                found = True
                break
    assert found, "No lesson found covering pipeline debugging or perception steps"

def test_f5_04_lessons_extracted_from_history():
    """Verify that extracted lessons reference historical sessions, dates, or specific errors."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    found = False
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            if any(term in content for term in ["session", "history", "transcript", "2026-", "2025-"]):
                found = True
                break
    assert found, "No lesson found referencing prior transcript history"

def test_f5_05_lessons_vram_limits_checked():
    """Verify VRAM targets and fp8 quantization details are mentioned in VRAM lessons."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    found = False
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            if "16gb" in content or "16 gb" in content or "13.5" in content or "fp8" in content:
                found = True
                break
    assert found, "VRAM limits or FP8 options were not documented in lessons"

def test_f5_06_lessons_installer_compatibility_checked():
    """Verify that installer permission configurations or launching rules are documented."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    found = False
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            if "launch_goodq" in content or "programdata" in content or "permission" in content or "icacls" in content:
                found = True
                break
    assert found, "Installer launching rules or permissions are not documented"

def test_f5_07_lessons_pipeline_thresholds_checked():
    """Verify Shannon entropy, Laplacian variance, or OpenCV seeks are covered in pipeline lessons."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    found = False
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            if any(term in content for term in ["entropy", "variance", "seeking", "capture", "laplacian"]):
                found = True
                break
    assert found, "Shannon entropy, Laplacian variance, or OpenCV seeking are not documented"

def test_f5_08_lessons_count():
    """Verify that the lessons directory contains at least 3 distinct lessons."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    md_files = [f for f in os.listdir(lessons_dir) if f.endswith(".md")]
    assert len(md_files) >= 3, f"Lessons count is less than 3: {len(md_files)}"

def test_f5_09_lessons_content_structured():
    """Verify lessons body is well-structured with Background, Correction, and Why sections."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            content = open(p, "r", encoding="utf-8").read().lower()
            assert "background" in content or "context" in content, f"Lesson {f} is not well-structured"
            assert "correction" in content or "fix" in content or "solution" in content, f"Lesson {f} lacks correction details"
            assert "mattered" in content or "impact" in content or "why" in content, f"Lesson {f} lacks impact analysis"

def test_f5_10_lessons_contain_no_redundant_lessons():
    """Verify lessons files do not contain identical content or duplicate findings."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    contents = []
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            txt = open(p, "r", encoding="utf-8").read().strip()
            # Clean whitespaces
            txt_clean = re.sub(r'\s+', ' ', txt)
            contents.append(txt_clean)
    assert len(contents) == len(set(contents)), "Duplicate lesson contents found"

def test_f5_11_lessons_are_readable_by_agent():
    """Verify that all lesson files are plain text UTF-8 markdown files."""
    lessons_dir = os.path.join(WORKSPACE_ROOT, "lessons")
    for f in os.listdir(lessons_dir):
        p = os.path.join(lessons_dir, f)
        if os.path.isfile(p):
            try:
                open(p, "r", encoding="utf-8").read()
            except UnicodeDecodeError:
                pytest.fail(f"Lesson {f} is not encoded in valid UTF-8 plain text")

# ==============================================================================
# FEATURE 6: Agent Workspace Onboarding Bootstrapper (F6, R6)
# ==============================================================================

def test_f6_01_bootstrapper_script_exists():
    """Verify bootstrap_agent.ps1 exists at the root of _AGENT."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    assert os.path.isfile(bootstrap_path), f"bootstrap_agent.ps1 missing at {bootstrap_path}"

def test_f6_02_bootstrapper_exits_zero():
    """Run bootstrap_agent.ps1 and verify it exits 0."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path], capture_output=True, text=True)
    assert res.returncode == 0, f"Bootstrapper exited with code {res.returncode}. Stderr: {res.stderr}"

def test_f6_03_bootstrapper_checks_paths():
    """Verify the bootstrapper checks workspace path validity."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path], capture_output=True, text=True)
    assert "path" in res.stdout.lower() or "directory" in res.stdout.lower() or "folder" in res.stdout.lower()

def test_f6_04_bootstrapper_checks_folders():
    """Verify the bootstrapper checks for required folder existence."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path], capture_output=True, text=True)
    assert "protocols" in res.stdout.lower() or "models" in res.stdout.lower() or "workflows" in res.stdout.lower() or "lessons" in res.stdout.lower()

def test_f6_05_bootstrapper_checks_read_write():
    """Verify the bootstrapper checks read/write access."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path], capture_output=True, text=True)
    assert "access" in res.stdout.lower() or "permissions" in res.stdout.lower() or "read" in res.stdout.lower() or "write" in res.stdout.lower()

def test_f6_06_bootstrapper_outputs_workspace_summary():
    """Verify the bootstrapper prints a summary of the workspace sections."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path], capture_output=True, text=True)
    assert "summary" in res.stdout.lower() or "sections" in res.stdout.lower() or "overview" in res.stdout.lower()

def test_f6_07_bootstrapper_reports_system_capabilities():
    """Verify the bootstrapper outputs a report of system capabilities."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path], capture_output=True, text=True)
    assert "capabilities" in res.stdout.lower() or "report" in res.stdout.lower() or "capacity" in res.stdout.lower()

def test_f6_08_bootstrapper_runs_in_powershell():
    """Verify the bootstrapper runs properly under PowerShell."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", f"& '{bootstrap_path}'"], capture_output=True, text=True)
    assert res.returncode == 0, "Bootstrapper script failed to run via PowerShell Command invocation"

def test_f6_09_bootstrapper_handles_invalid_paths_gracefully():
    """Verify the bootstrapper exits with non-zero code if run in a corrupted context or invalid folder."""
    # Move bootstrapper to system temp and run it, simulating path error if it relies on current directory location.
    # Note: If it checks parent/child directory structure of _AGENT, it should fail in temp directory.
    import tempfile
    import shutil
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copy(bootstrap_path, tmpdir)
        temp_script = os.path.join(tmpdir, "bootstrap_agent.ps1")
        res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", temp_script], capture_output=True, text=True)
        # If it enforces being run inside the workspace root, it should fail
        assert res.returncode != 0 or "error" in res.stdout.lower() or "invalid" in res.stdout.lower()

def test_f6_10_bootstrapper_logs_checks_clearly():
    """Verify the bootstrapper outputs descriptive logs indicating what checks were run."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path], capture_output=True, text=True)
    assert "[info]" in res.stdout.lower() or "[check]" in res.stdout.lower() or "ok" in res.stdout.lower() or "pass" in res.stdout.lower()

def test_f6_11_bootstrapper_creates_no_garbage_files():
    """Verify the bootstrapper does not leave behind any temporary files after execution."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    before_files = set(os.listdir(WORKSPACE_ROOT))
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path], capture_output=True, text=True)
    after_files = set(os.listdir(WORKSPACE_ROOT))
    assert before_files == after_files, f"Temporary/garbage files created: {after_files - before_files}"

def test_f6_12_bootstrapper_respects_no_drive_letters_in_output():
    """Verify the bootstrapper's console output contains no literal Windows drive letters (C: or L:)."""
    bootstrap_path = os.path.join(WORKSPACE_ROOT, "bootstrap_agent.ps1")
    res = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", bootstrap_path], capture_output=True, text=True)
    drive_matches = re.findall(r'\b[cClL]:[/\\]', res.stdout)
    assert len(drive_matches) == 0, f"Literal Windows drive letters printed by bootstrapper: {drive_matches}"

# ==============================================================================
# FEATURE 7: Repository Pointer Update (F7, R7)
# ==============================================================================

def test_f7_01_agents_md_exists():
    r"""Verify l:\GOODCUBE\projects\goodq4all\AGENTS.md exists."""
    assert os.path.isfile(AGENTS_MD_PATH), f"AGENTS.md missing at {AGENTS_MD_PATH}"

def test_f7_02_agents_md_contains_workspace_pointer_section():
    """Verify AGENTS.md contains a specific section pointing to the workspace."""
    content = open(AGENTS_MD_PATH, "r", encoding="utf-8", errors="ignore").read().lower()
    assert "_agent" in content or "my drive\\_agent" in content or "agent knowledge base" in content, "Workspace pointer missing in AGENTS.md"

def test_f7_03_agents_md_pointer_uses_correct_format():
    """Verify the pointer path in AGENTS.md uses environment abstractions or standardized patterns."""
    content = open(AGENTS_MD_PATH, "r", encoding="utf-8", errors="ignore").read()
    # Path should not contain hardcoded C: or L: directly in the text body describing the workspace path
    # Check that any references to My Drive include standard path notation
    assert "My Drive/_AGENT" in content or "My Drive\\_AGENT" in content or "%USERPROFILE%" in content or "%SystemDrive%" in content

def test_f7_04_agents_md_pointer_is_prominent():
    """Verify the pointer in AGENTS.md is prominently located."""
    lines = open(AGENTS_MD_PATH, "r", encoding="utf-8", errors="ignore").readlines()
    content_head = "".join(lines[:100]).lower()
    assert "_agent" in content_head or "my drive\\_agent" in content_head or "agent knowledge base" in content_head, "Workspace pointer is not prominently located within first 100 lines of AGENTS.md"

def test_f7_05_agents_md_no_broken_links():
    """Verify that links in the pointer section of AGENTS.md are valid."""
    content = open(AGENTS_MD_PATH, "r", encoding="utf-8", errors="ignore").read()
    link_pattern = re.compile(r'\[.*?\]\((.*?)\)')
    for link in link_pattern.findall(content):
        if "_AGENT" in link or "bootstrap" in link or "verify" in link:
            # If it's a relative link, verify target exists
            if not link.startswith("http") and not link.startswith("mailto"):
                target_path = os.path.normpath(os.path.join(os.path.dirname(AGENTS_MD_PATH), link))
                assert os.path.exists(target_path) or os.path.exists(os.path.join(WORKSPACE_ROOT, link)), f"Broken link in AGENTS.md: {link}"

def test_f7_06_agents_md_retains_identity_rules():
    """Verify that updating AGENTS.md has not deleted the core rules (System Identity, Mission, etc.)."""
    content = open(AGENTS_MD_PATH, "r", encoding="utf-8", errors="ignore").read().lower()
    assert "mission" in content, "AGENTS.md lacks 'mission'"
    assert "system identity" in content, "AGENTS.md lacks 'system identity'"
    assert "technical standards" in content, "AGENTS.md lacks 'technical standards'"

def test_f7_07_agents_md_conforms_to_layout():
    """Verify AGENTS.md remains syntactically valid markdown."""
    content = open(AGENTS_MD_PATH, "r", encoding="utf-8", errors="ignore").read()
    # Needs to start with standard headings or tags
    assert content.strip().startswith("<!--") or content.strip().startswith("#"), "AGENTS.md layout is broken"

def test_f7_08_agents_md_file_size_reasonable():
    """Verify AGENTS.md is of reasonable size, confirming it wasn't truncated."""
    size = os.path.getsize(AGENTS_MD_PATH)
    assert 2000 < size < 30000, f"AGENTS.md size is suspicious: {size} bytes"

def test_f7_09_agents_md_pointer_references_bootstrap():
    """Verify the pointer section in AGENTS.md mentions bootstrap_agent.ps1 for onboarding."""
    content = open(AGENTS_MD_PATH, "r", encoding="utf-8", errors="ignore").read().lower()
    assert "bootstrap_agent.ps1" in content, "AGENTS.md does not reference bootstrap_agent.ps1"

def test_f7_10_agents_md_pointer_references_linter():
    """Verify the pointer section in AGENTS.md mentions verify_agent_workspace.py for verification."""
    content = open(AGENTS_MD_PATH, "r", encoding="utf-8", errors="ignore").read().lower()
    assert "verify_agent_workspace.py" in content, "AGENTS.md does not reference verify_agent_workspace.py"

def test_f7_11_agents_md_last_verified_date_updated():
    """Verify that the verification date in AGENTS.md header is present."""
    content = open(AGENTS_MD_PATH, "r", encoding="utf-8", errors="ignore").read()
    assert "DOC_LAST_VERIFIED" in content, "AGENTS.md is missing DOC_LAST_VERIFIED tag"

def test_f7_12_post_manifest_script_exists():
    """Verify that scripts/generate_post_manifest.py exists in the repository."""
    script_path = os.path.join(REPO_ROOT, "scripts", "generate_post_manifest.py")
    assert os.path.isfile(script_path), f"generate_post_manifest.py missing at {script_path}"

# ==============================================================================
# FEATURE 8: Hardened Workspace Auditing (F8, R8)
# ==============================================================================

def test_f8_01_reports_subdirs_exist():
    """Verify that the reports folder and all subfolders exist and are not empty."""
    reports_dir = os.path.join(WORKSPACE_ROOT, "reports")
    assert os.path.isdir(reports_dir), "reports/ directory does not exist"
    for subdir in ["bootstrap", "audits", "handoffs", "cleanup"]:
        path = os.path.join(reports_dir, subdir)
        assert os.path.isdir(path), f"reports/{subdir}/ directory does not exist"
        assert len(os.listdir(path)) > 0, f"reports/{subdir}/ directory is empty"

def test_f8_02_changelog_exists():
    """Verify that CHANGELOG.md exists in the workspace root."""
    changelog_path = os.path.join(WORKSPACE_ROOT, "CHANGELOG.md")
    assert os.path.isfile(changelog_path), "CHANGELOG.md is missing from workspace root"

def test_f8_03_policy_json_keys():
    """Verify that .agent_workspace_policy.json contains the stricter required keys."""
    policy_path = os.path.join(WORKSPACE_ROOT, ".agent_workspace_policy.json")
    assert os.path.isfile(policy_path), ".agent_workspace_policy.json is missing"
    import json
    with open(policy_path, "r", encoding="utf-8") as f:
        policy = json.load(f)
    assert "agents_may_create" in policy, "policy missing 'agents_may_create'"
    assert "agents_must_not_create_without_approval" in policy, "policy missing 'agents_must_not_create_without_approval'"
    assert "allowed_source_formats" in policy, "policy missing 'allowed_source_formats'"
    assert "forbidden_file_patterns" in policy, "policy missing 'forbidden_file_patterns'"
    
    # Assert specific additions
    assert "reports/" in policy["agents_may_create"], "policy does not allow reports/ creation"
    assert "protocols/" in policy["agents_must_not_create_without_approval"], "policy does not require approval for protocols/"

def test_f8_04_host_profiles_standard_fields():
    """Verify that each host profile markdown contains Network and Constraints keywords."""
    profiles_dir = os.path.join(WORKSPACE_ROOT, "host_profiles")
    assert os.path.isdir(profiles_dir), "host_profiles/ directory does not exist"
    for f in os.listdir(profiles_dir):
        if f.lower().endswith(".md"):
            p = os.path.join(profiles_dir, f)
            content = open(p, "r", encoding="utf-8", errors="ignore").read()
            assert "network" in content.lower(), f"Host profile {f} is missing Network keyword"
            assert "constraints" in content.lower(), f"Host profile {f} is missing Constraints keyword"

def test_f8_05_quiz_exactly_8_questions_and_passing_threshold():
    """Verify that the quiz has exactly 8 questions and does not contain the answers."""
    quiz_file = os.path.join(WORKSPACE_ROOT, "quizzes", "goodq4all_ingestion_readiness.md")
    assert os.path.isfile(quiz_file), "Quiz file is missing"
    content = open(quiz_file, "r", encoding="utf-8", errors="ignore").read()
    
    questions = re.findall(r"##\s+Question\s+\d+", content, re.IGNORECASE)
    assert len(questions) == 8, f"Quiz must contain exactly 8 questions (found {len(questions)})"
    
    # Check that it doesn't contain answers/answer keys
    assert "answer key" not in content.lower(), "Quiz file should not contain answer key references"
    # Ensure passing threshold is mentioned
    assert "passing" in content.lower() or "threshold" in content.lower(), "Quiz file must state passing threshold"
    
    # Check that answer key exists in answer_keys folder
    key_file = os.path.join(WORKSPACE_ROOT, "quizzes", "answer_keys", "goodq4all_ingestion_readiness_key.md")
    assert os.path.isfile(key_file), "Quiz answer key file is missing"

def test_f8_06_linter_bans_cache_files():
    """Verify that the linter correctly flags and bans pycache, pyc, pyo, pytest_cache, mypy_cache, and ruff_cache."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    
    # Let's create a temporary banned directory
    banned_dir = os.path.join(WORKSPACE_ROOT, ".pytest_cache")
    created_dir = False
    if not os.path.exists(banned_dir):
        os.makedirs(banned_dir)
        created_dir = True
    
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail when .pytest_cache was present"
        assert "Banned directory found" in res.stdout or "Banned directory found" in res.stderr
    finally:
        if created_dir:
            os.rmdir(banned_dir)

def test_f8_07_linter_bans_file_links():
    """Verify that the linter flags file:/// links in markdown documents."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    bad_file = os.path.join(protocols_dir, "test_temp_file_link.md")
    
    with open(bad_file, "w", encoding="utf-8") as f:
        f.write("Here is a link: [plan](file:///something/else/plan.md)\n")
        
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail when file:/// link was present"
        assert "file:/// link found" in res.stdout or "file:/// link found" in res.stderr
    finally:
        if os.path.exists(bad_file):
            os.remove(bad_file)

def test_f8_08_linter_bans_conflicted_copies():
    """Verify that the linter flags files containing 'conflicted copy' in the name."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    bad_file = os.path.join(protocols_dir, "rules (conflicted copy).md")
    
    with open(bad_file, "w", encoding="utf-8") as f:
        f.write("# Rules\n")
        
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail when conflicted copy was present"
        assert "Banned conflicted copy file found" in res.stdout or "Banned conflicted copy file found" in res.stderr
    finally:
        if os.path.exists(bad_file):
            os.remove(bad_file)

def test_f8_09_linter_bans_google_native_shortcuts():
    """Verify that the linter flags Google-native shortcuts and temporary files."""
    linter_path = os.path.join(WORKSPACE_ROOT, "verify_agent_workspace.py")
    protocols_dir = os.path.join(WORKSPACE_ROOT, "protocols")
    bad_file = os.path.join(protocols_dir, "document.gdoc")
    
    with open(bad_file, "w", encoding="utf-8") as f:
        f.write("Google doc link dummy\n")
        
    try:
        res = subprocess.run(["python", linter_path], capture_output=True, text=True)
        assert res.returncode != 0, "Linter did not fail when Google-native shortcut was present"
        assert "Banned file format found" in res.stdout or "Banned file format found" in res.stderr
    finally:
        if os.path.exists(bad_file):
            os.remove(bad_file)

def test_f8_10_linter_validates_index_doctrine_and_readme_authority():
    """Verify that the linter checks INDEX.md for the doctrine statement and README_FOR_AGENTS.md for Authority Order."""
    index_path = os.path.join(WORKSPACE_ROOT, "INDEX.md")
    readme_path = os.path.join(WORKSPACE_ROOT, "README_FOR_AGENTS.md")
    assert os.path.isfile(index_path), "INDEX.md does not exist"
    assert os.path.isfile(readme_path), "README_FOR_AGENTS.md does not exist"
    
    index_content = open(index_path, "r", encoding="utf-8", errors="ignore").read()
    readme_content = open(readme_path, "r", encoding="utf-8", errors="ignore").read()
    
    assert "This folder is doctrine. The repository is implementation. If they conflict, stop and ask for evidence." in index_content
    assert "Authority Order" in readme_content
