"""GitHub Actions reusable workflow (``on: workflow_call: inputs:``) scenario.

Phase 2 analog of the GitLab component scenario: compile, validate, and
decompile a reusable workflow whose ``workflow_call`` block and
``${{ ... }}`` expressions must survive byte-for-byte.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from bash2yaml.commands.compile_all import run_compile_all
from bash2yaml.commands.decompile_all import run_decompile_gitlab_file
from bash2yaml.targets.github import GitHubTarget

SCENARIO = "scenario_github_reusable"


@pytest.fixture
def scenario_setup(tmp_path, monkeypatch):
    """Copy the scenario to a temp directory so tests never dirty the fixture."""
    monkeypatch.setenv("BASH2YAML_SKIP_ROOT_CHECKS", "True")

    src = Path(__file__).parent / SCENARIO
    dest = tmp_path / SCENARIO
    shutil.copytree(src, dest)

    uncompiled = dest / "uncompiled"
    output_root = dest / ".out"
    shutil.rmtree(str(output_root), ignore_errors=True)
    shutil.rmtree(str(uncompiled / ".bash2yaml"), ignore_errors=True)
    return uncompiled, output_root


def test_compile_reusable_workflow(scenario_setup):
    uncompiled, output_root = scenario_setup

    result = run_compile_all(uncompiled, output_root, target=GitHubTarget())
    assert result > 0, "Expected at least one inlined section"

    compiled_text = (output_root / "deploy.yml").read_text(encoding="utf-8")

    # The workflow_call trigger and its inputs survive verbatim —
    # including `on:` not degrading into a YAML 1.1 boolean.
    assert "on:" in compiled_text
    assert "True:" not in compiled_text
    assert "workflow_call:" in compiled_text
    assert "required: true" in compiled_text

    # Expressions pass through verbatim: in `if:`, `environment:`, `env:`
    # values, and inside the inlined script.
    assert "${{ !inputs.dry-run || inputs.environment != 'prod' }}" in compiled_text
    assert "environment: ${{ inputs.environment }}" in compiled_text
    assert "DEPLOY_TOKEN: ${{ secrets.deploy-token }}" in compiled_text
    assert "${{ inputs.environment }} environment" in compiled_text

    # The script got inlined and the pragma directive was stripped.
    assert "deploy complete" in compiled_text
    assert "github-expression" not in compiled_text
    assert "./scripts/deploy.sh" not in compiled_text

    # The `uses:` step is untouched.
    assert "actions/checkout@v4" in compiled_text


def test_compiled_reusable_workflow_passes_validation(scenario_setup):
    uncompiled, output_root = scenario_setup
    run_compile_all(uncompiled, output_root, target=GitHubTarget())

    from bash2yaml.utils.validate_pipeline_github import GitHubActionsValidator

    compiled_text = (output_root / "deploy.yml").read_text(encoding="utf-8")
    ok, errors = GitHubActionsValidator().validate_workflow(compiled_text)
    assert ok, errors


def test_decompile_reusable_workflow_round_trip(scenario_setup, tmp_path):
    uncompiled, output_root = scenario_setup
    run_compile_all(uncompiled, output_root, target=GitHubTarget())

    decompile_dir = tmp_path / "decompiled"
    jobs, created, out_yaml = run_decompile_gitlab_file(
        input_yaml_path=(output_root / "deploy.yml").resolve(),
        output_dir=decompile_dir.resolve(),
        target=GitHubTarget(),
    )
    assert jobs >= 1
    assert created >= 1

    decompiled_text = out_yaml.read_text(encoding="utf-8")

    # The workflow_call block and expressions outside run: are untouched.
    yaml = YAML()
    data = yaml.load(decompiled_text)
    assert "workflow_call" in data["on"]
    assert data["jobs"]["deploy"]["environment"] == "${{ inputs.environment }}"

    # Body now references a script file instead of inline bash.
    assert ".sh" in decompiled_text
    assert "deploy complete" not in decompiled_text

    # The extracted script keeps expressions and gains the pragma so
    # recompiling is warning-free.
    scripts = [p for p in out_yaml.parent.rglob("*.sh") if "variables" not in p.name and "mock_ci" not in p.name]
    assert scripts, "expected an extracted script"
    script_text = "".join(p.read_text(encoding="utf-8") for p in scripts)
    assert "${{ inputs.environment }}" in script_text
    assert "Pragma: github-expression" in script_text
