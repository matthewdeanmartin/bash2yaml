"""Integration test: compile an AWS CodeBuild Buildspec with the BuildspecTarget."""

from __future__ import annotations

import shutil
from pathlib import Path
from test.temp_change_dir import chdir_to_file_dir

from ruamel.yaml import YAML

from bash2yaml.commands.compile_all import run_compile_all
from bash2yaml.targets.buildspec import BuildspecTarget


def test_buildspec_compile_inlines_scripts():
    """Compile a Buildspec and verify scripts were inlined into phase commands."""
    with chdir_to_file_dir(__file__):
        uncompiled = Path("scenario_buildspec1/uncompiled")
        output_root = Path("scenario_buildspec1/.out")
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/.out"), ignore_errors=True)
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/uncompiled/.bash2yaml"), ignore_errors=True)

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


def test_buildspec_compile_phases_structure():
    """Compiled Buildspec should preserve phase structure."""
    with chdir_to_file_dir(__file__):
        uncompiled = Path("scenario_buildspec1/uncompiled")
        output_root = Path("scenario_buildspec1/.out")
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/.out"), ignore_errors=True)
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/uncompiled/.bash2yaml"), ignore_errors=True)

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


def test_buildspec_compile_finally_block_inlined():
    """The finally block commands should also be inlined."""
    with chdir_to_file_dir(__file__):
        uncompiled = Path("scenario_buildspec1/uncompiled")
        output_root = Path("scenario_buildspec1/.out")
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/.out"), ignore_errors=True)
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/uncompiled/.bash2yaml"), ignore_errors=True)

        target = BuildspecTarget()
        run_compile_all(uncompiled, output_root, target=target)

        output_file = output_root / "buildspec.yml"
        output_text = output_file.read_text(encoding="utf-8")

        # cleanup.sh (from finally block) should be inlined
        assert "Cleaning up temporary files" in output_text
        assert "rm -rf /tmp/build-cache" in output_text


def test_buildspec_compile_preserves_artifacts():
    """The artifacts section should be preserved in the compiled output."""
    with chdir_to_file_dir(__file__):
        uncompiled = Path("scenario_buildspec1/uncompiled")
        output_root = Path("scenario_buildspec1/.out")
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/.out"), ignore_errors=True)
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/uncompiled/.bash2yaml"), ignore_errors=True)

        target = BuildspecTarget()
        run_compile_all(uncompiled, output_root, target=target)

        output_file = output_root / "buildspec.yml"
        yaml = YAML()
        data = yaml.load(output_file)

        artifacts = data.get("artifacts", {})
        assert "files" in artifacts
        assert "base-directory" in artifacts
        assert artifacts["base-directory"] == "dist"


def test_buildspec_compile_preserves_runtime_versions():
    """The runtime-versions section inside install phase should be preserved."""
    with chdir_to_file_dir(__file__):
        uncompiled = Path("scenario_buildspec1/uncompiled")
        output_root = Path("scenario_buildspec1/.out")
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/.out"), ignore_errors=True)
        shutil.rmtree(str(Path(__file__).parent / "scenario_buildspec1/uncompiled/.bash2yaml"), ignore_errors=True)

        target = BuildspecTarget()
        run_compile_all(uncompiled, output_root, target=target)

        output_file = output_root / "buildspec.yml"
        yaml = YAML()
        data = yaml.load(output_file)

        install_phase = data["phases"]["install"]
        assert "runtime-versions" in install_phase
        assert install_phase["runtime-versions"].get("nodejs") == 20
