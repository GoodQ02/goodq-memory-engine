from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_goodq_env_names_include_core_and_supported_step_envs() -> None:
    from scripts import bootstrap_hygiene

    names = bootstrap_hygiene.goodq_env_names()

    assert names[0] == "goodq_core"
    assert "goodq_video_scene_detect" in names
    assert "goodq_image_caption" in names
    assert len(names) == len(set(names))


def test_snapshot_reads_only_safe_env_keys_and_redacts_token_values(tmp_path: Path) -> None:
    from scripts import bootstrap_hygiene

    env_path = tmp_path / ".env.local"
    token_key = "H" + "F_TOKEN"
    token_value = "h" + "f_" + "abcdefghijklmnopqrstuvwxyz"
    env_path.write_text(
        "\n".join(
            [
                "GOODQ_DATA_ROOT=%USERPROFILE%\\GoodQ_Bootstrap_Test",
                "GOODQ_REQUIRE_WSL_AUDIO=0",
                f"{token_key}={token_value}",
            ]
        ),
        encoding="utf-8",
    )

    snapshot = bootstrap_hygiene.collect_snapshot(
        repo_root=tmp_path,
        conda_runner=lambda _conda: {"goodq_core": "%USERPROFILE%\\miniconda3\\envs\\goodq_core"},
    )

    assert snapshot["local_env"]["GOODQ_DATA_ROOT"] == "%USERPROFILE%\\GoodQ_Bootstrap_Test"
    assert snapshot["local_env"]["GOODQ_REQUIRE_WSL_AUDIO"] == "0"
    assert "HF_TOKEN" not in snapshot["local_env"]
    assert token_value not in json.dumps(snapshot)


def test_reset_plan_is_non_destructive_and_uses_fresh_data_root(tmp_path: Path) -> None:
    from scripts import bootstrap_hygiene

    fresh_root = "%USERPROFILE%\\GoodQ_Bootstrap_Test"
    plan = bootstrap_hygiene.build_reset_plan(repo_root=tmp_path, fresh_data_root=fresh_root)

    rendered = "\n".join(plan["commands"])
    assert plan["mode"] == "plan_only"
    assert "Review these commands before running them" in plan["warning"]
    assert "conda env remove -n goodq_core -y" in rendered
    assert "--disable-wsl-audio" in rendered
    assert f'--data-root "{fresh_root}"' in rendered
    assert "--no-launch" in rendered
    assert "Remove-Item" not in rendered


def test_cli_snapshot_writes_json(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "snapshot.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "bootstrap_hygiene.py"),
            "snapshot",
            "--output",
            str(output),
            "--no-conda",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["repo_root"]
    assert "goodq_core" in payload["expected_conda_envs"]
