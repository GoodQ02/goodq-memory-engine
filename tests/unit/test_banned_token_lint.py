from pathlib import Path

from scripts.docs.banned_token_lint import is_excluded


def test_scan_filters_non_targets_before_accessing_inaccessible_links(tmp_path, monkeypatch, capsys):
    from scripts.docs import banned_token_lint

    monkeypatch.setattr(banned_token_lint, "__file__", str(tmp_path / "scripts/docs/banned_token_lint.py"))
    binary_link = tmp_path / "model.ckpt"
    excluded_link = tmp_path / "tests/fixture.py"
    witness_link = tmp_path / "tmp/witness/speaker_model/custom.py"
    active_source = tmp_path / "active.py"
    active_source.write_text(banned_token_lint.BANNED_TOKEN, encoding="utf-8")
    monkeypatch.setattr(Path, "rglob", lambda *_args: iter([binary_link, excluded_link, witness_link, active_source]))
    real_is_file = Path.is_file

    def guarded_is_file(path):
        if path in {binary_link, excluded_link, witness_link}:
            raise OSError("inaccessible WSL model link")
        return real_is_file(path)

    monkeypatch.setattr(Path, "is_file", guarded_is_file)
    assert banned_token_lint.main() == 1
    assert "active.py:1:" in capsys.readouterr().out
    assert not is_excluded(tmp_path / "scripts/tmp/active.py", tmp_path)


def test_banned_token_lint_excludes_sibling_worktrees() -> None:
    repo_root = Path("C:/repo")

    assert is_excluded(
        repo_root / ".worktrees" / "release-candidate" / "docs" / "note.md",
        repo_root,
    )
