"""Integration test: compile an AWS CodeBuild Buildspec with the BuildspecTarget."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from bash2yaml.commands.compile_all import run_compile_all
from bash2yaml.targets.buildspec import BuildspecTarget


@pytest.fixture
def scenario_setup(tmp_path, monkeypatch):
    """Copy the scenario to a temporary directory for each test to avoid race conditions."""
    # Allow sourcing files from the temporary directory
    monkeypatch.setenv("BASH2YAML_SKIP_ROOT_CHECKS", "True")

    scenario_name = "scenario_buildspec1"
    src = Path(__file__).parent / scenario_name
    dest = tmp_path / scenario_name
    shutil.copytree(src, dest)

    uncompiled = dest / "uncompiled"
    output_root = dest / ".out"

    # Ensure any previous state is cleared in the temp copy
    shutil.rmtree(str(output_root), ignore_errors=True)
    shutil.rmtree(str(uncompiled / ".bash2yaml"), ignore_errors=True)

    return uncompiled, output_root


def test_buildspec_compile_inlines_scripts(scenario_setup):
    """Compile a Buildspec and verify scripts were inlined into phase commands."""
    uncompiled, output_root = scenario_setup

    target = BuildspecTarget()
    result = run_compile_all(uncompiled, output_root, target=target)

    # At least some scripts should have been inlined
    assert result > 0, "Expected at least one inlined section"

    # Check the output file
    output_file = output_root / "buildspec.yml"
    assert output_file.exists(), "Output file buildspec.yml should exist"

    output_text = output_file.read_text(encoding="utf-8")

    # The banner should be present (indicates scripts were inlined)
    assert "bash2yaml" in output_text

    # Inline markers should be present
    assert ">>> BEGIN inline" in output_text

    # Script references should be replaced
    assert "./scripts/setup.sh" not in output_text
    assert "./scripts/pre_build.sh" not in output_text
    assert "./scripts/build.sh" not in output_text
    assert "./scripts/cleanup.sh" not in output_text
    assert "./scripts/post_build.sh" not in output_text

    # Inlined content should be present
    assert "npm install -g @aws/aws-sdk" in output_text
    assert "npm ci" in output_text
    assert "npm run build" in output_text
    assert "rm -rf /tmp/build-cache" in output_text
    assert "aws s3 sync dist/" in output_text


def test_buildspec_compile_phases_structure(scenario_setup):
    """Compiled Buildspec should preserve phase structure."""
    uncompiled, output_root = scenario_setup

    target = BuildspecTarget()
    run_compile_all(uncompiled, output_root, target=target)

    output_file = output_root / "buildspec.yml"
    yaml = YAML()
    data = yaml.load(output_file)

    # All phases should be present
    phases = data.get("phases", {})
    assert "install" in phases
    assert "pre_build" in phases
    assert "build" in phases
    assert "post_build" in phases

    # Build phase should have a finally block
    build_phase = phases["build"]
    assert "finally" in build_phase
    assert "commands" in build_phase["finally"]


def test_buildspec_compile_finally_block_inlined(scenario_setup):
    """The finally block commands should also be inlined."""
    uncompiled, output_root = scenario_setup

    target = BuildspecTarget()
    run_compile_all(uncompiled, output_root, target=target)

    output_file = output_root / "buildspec.yml"
    output_text = output_file.read_text(encoding="utf-8")

    # cleanup.sh (from finally block) should be inlined
    assert "Cleaning up temporary files" in output_text
    assert "rm -rf /tmp/build-cache" in output_text


def test_buildspec_compile_preserves_artifacts(scenario_setup):
    """The artifacts section should be preserved in the compiled output."""
    uncompiled, output_root = scenario_setup

    target = BuildspecTarget()
    run_compile_all(uncompiled, output_root, target=target)

    output_file = output_root / "buildspec.yml"
    yaml = YAML()
    data = yaml.load(output_file)

    artifacts = data.get("artifacts", {})
    assert "files" in artifacts
    assert "base-directory" in artifacts
    assert artifacts["base-directory"] == "dist"


def test_buildspec_compile_preserves_runtime_versions(scenario_setup):
    """The runtime-versions section inside install phase should be preserved."""
    uncompiled, output_root = scenario_setup

    target = BuildspecTarget()
    run_compile_all(uncompiled, output_root, target=target)

    output_file = output_root / "buildspec.yml"
    yaml = YAML()
    data = yaml.load(output_file)

    install_phase = data["phases"]["install"]
    assert "runtime-versions" in install_phase
    assert install_phase["runtime-versions"].get("nodejs") == 20
