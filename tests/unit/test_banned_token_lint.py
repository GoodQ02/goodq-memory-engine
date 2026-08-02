from pathlib import Path

from scripts.docs.banned_token_lint import is_excluded


def test_banned_token_lint_excludes_sibling_worktrees() -> None:
    repo_root = Path("C:/repo")

    assert is_excluded(
        repo_root / ".worktrees" / "release-candidate" / "docs" / "note.md",
        repo_root,
    )
