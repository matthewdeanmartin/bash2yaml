"""Tests for decompiling GitHub Actions workflows."""

from __future__ import annotations

import pytest
from ruamel.yaml import YAML

from bash2yaml.commands.decompile_all import run_decompile_gitlab_file
from bash2yaml.targets.github import GitHubTarget


@pytest.fixture
def target():
    return GitHubTarget()


@pytest.fixture
def compiled_workflow(tmp_path):
    """Create a compiled GitHub Actions workflow for decompilation."""
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """\
# Pragma: do-not-validate-schema
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: |
          echo "Building..."
          npm run build
          echo "Done."
      - name: Test
        run: |
          echo "Testing..."
          npm test
""",
        encoding="utf-8",
    )
    return workflow


def test_decompile_github_extracts_run_blocks(compiled_workflow, tmp_path, target):
    """Decompile should extract run: blocks into .sh files."""
    output_dir = tmp_path / "decompiled"

    jobs, files_created, output_yaml = run_decompile_gitlab_file(
        input_yaml_path=compiled_workflow,
        output_dir=output_dir,
        target=target,
    )

    assert jobs > 0
    assert files_created > 0

    # Check that .sh files were created
    sh_files = list(output_dir.rglob("*.sh"))
    assert len(sh_files) >= 2, f"Expected at least 2 .sh files, got {len(sh_files)}"

    # Check that the output YAML references .sh files instead of inline scripts
    yaml = YAML()
    data = yaml.load(output_yaml)
    build_steps = data["jobs"]["build"]["steps"]

    # uses: steps should be untouched
    assert build_steps[0].get("uses") == "actions/checkout@v4"

    # run: steps should now reference .sh files
    for step in build_steps[1:]:
        if "run" in step:
            run_val = str(step["run"])
            assert run_val.strip().endswith(".sh"), f"Expected .sh reference, got: {run_val}"


def test_decompile_github_preserves_uses_steps(compiled_workflow, tmp_path, target):
    """uses: steps should not be decompiled."""
    output_dir = tmp_path / "decompiled"

    run_decompile_gitlab_file(
        input_yaml_path=compiled_workflow,
        output_dir=output_dir,
        target=target,
    )

    yaml = YAML()
    output_yaml = output_dir / "workflow.yml"
    data = yaml.load(output_yaml)

    checkout_step = data["jobs"]["build"]["steps"][0]
    assert "uses" in checkout_step
    assert checkout_step["uses"] == "actions/checkout@v4"
    assert "run" not in checkout_step
