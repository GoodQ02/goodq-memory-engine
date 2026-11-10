import json
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("case", ["face-labels", "voice-clips", "filter-and-empty-reload", "reference-review",
                                  "unidentified-faces", "unidentified-voices", "select-and-hold", "preview-only",
                                  "apply-cancel", "apply-confirm", "preview-error", "draft-restore",
                                  "legacy-completed", "stale-draft", "no-reuse", "review-only", "corrupt-draft", "stale-preview",
                                  "reassign", "applied-correction"])
def test_review_uses_original_evidence_without_assigning_identity(case):
    source = Path("ui/identity_workbench/static/js/matches.js").read_text(encoding="utf-8")
    result = subprocess.run(["node", "tests/unit/identity_matching_review.cjs"],
                            input=json.dumps({"source": source, "case": case}),
                            text=True, encoding="utf-8", capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr or result.stdout
