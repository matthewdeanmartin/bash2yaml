"""Integration test: compile a GitHub Actions workflow with the GitHubTarget."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from bash2yaml.commands.compile_all import run_compile_all
from bash2yaml.targets.github import GitHubTarget


@pytest.fixture
def scenario_setup(tmp_path, monkeypatch):
    """Copy the scenario to a temporary directory for each test to avoid race conditions."""
    # Allow sourcing files from the temporary directory
    monkeypatch.setenv("BASH2YAML_SKIP_ROOT_CHECKS", "True")

    scenario_name = "scenario_github1"
    src = Path(__file__).parent / scenario_name
    dest = tmp_path / scenario_name
    shutil.copytree(src, dest)

    uncompiled = dest / "uncompiled"
    output_root = dest / ".out"

    # Ensure any previous state is cleared in the temp copy
    shutil.rmtree(str(output_root), ignore_errors=True)
    shutil.rmtree(str(uncompiled / ".bash2yaml"), ignore_errors=True)

    return uncompiled, output_root


def test_github_compile_inlines_scripts(scenario_setup):
    """Compile a GitHub Actions workflow and verify scripts were inlined."""
    uncompiled, output_root = scenario_setup

    target = GitHubTarget()
    result = run_compile_all(uncompiled, output_root, target=target)

    # At least some scripts should have been inlined
    assert result > 0, "Expected at least one inlined section"

    # Check the output file
    output_file = output_root / "ci.yml"
    assert output_file.exists(), "Output file should exist"

    output_text = output_file.read_text(encoding="utf-8")

    # The banner should be present (indicates scripts were inlined)
    assert "bash2yaml" in output_text

    # Inline markers should be present
    assert ">>> BEGIN inline" in output_text

    # Script references should be replaced
    assert "./scripts/install.sh" not in output_text
    assert "./scripts/build.sh" not in output_text
    assert "./scripts/test.sh" not in output_text

    # Inlined content should be present
    assert "npm ci" in output_text
    assert "npm run build" in output_text
    assert "npm test" in output_text

    # uses: steps should be preserved
    assert "actions/checkout@v4" in output_text


def test_github_compile_merges_global_env(scenario_setup):
    """Global variables from global_variables.sh should merge into workflow env:."""
    uncompiled, output_root = scenario_setup

    target = GitHubTarget()
    run_compile_all(uncompiled, output_root, target=target)

    output_file = output_root / "ci.yml"
    yaml = YAML()
    data = yaml.load(output_file)

    # Global env should contain merged variables
    env = data.get("env", {})
    assert env.get("CI_TOOL") == "bash2yaml", "global_variables.sh should merge into env:"
    assert env.get("VERSION") == "1.0.0"
    # Original YAML-defined env should still be there
    assert env.get("NODE_ENV") == "production"


def test_github_compile_merges_job_env(scenario_setup):
    """Job-specific variables from build_variables.sh should merge into job env:."""
    uncompiled, output_root = scenario_setup

    target = GitHubTarget()
    run_compile_all(uncompiled, output_root, target=target)

    output_file = output_root / "ci.yml"
    yaml = YAML()
    data = yaml.load(output_file)

    build_env = data["jobs"]["build"].get("env", {})
    assert build_env.get("BUILD_TARGET") == "dist", "build_variables.sh should merge into job env:"
    # Original job env should still be there
    assert build_env.get("BUILD_TYPE") == "release"


def test_github_compile_preserves_uses_steps(scenario_setup):
    """Steps with uses: should be left completely untouched."""
    uncompiled, output_root = scenario_setup

    target = GitHubTarget()
    run_compile_all(uncompiled, output_root, target=target)

    output_file = output_root / "ci.yml"
    yaml = YAML()
    data = yaml.load(output_file)

    # The checkout step should be preserved
    build_steps = data["jobs"]["build"]["steps"]
    checkout_step = build_steps[0]
    assert "uses" in checkout_step
    assert checkout_step["uses"] == "actions/checkout@v4"
    # Should not have run: key
    assert "run" not in checkout_step


def test_github_compile_preserves_step_env(scenario_setup):
    """Step-level env: should be preserved after inlining."""
    uncompiled, output_root = scenario_setup

    target = GitHubTarget()
    run_compile_all(uncompiled, output_root, target=target)

    output_file = output_root / "ci.yml"
    yaml = YAML()
    data = yaml.load(output_file)

    # Find the build step (3rd step, index 2: checkout, install, build)
    build_steps = data["jobs"]["build"]["steps"]
    build_step = build_steps[2]
    assert build_step.get("name") == "Build project"
    assert build_step.get("env", {}).get("OPTIMIZATION") == "high"
