"""GitLab CI/CD component template (spec:inputs) scenario.

Covers Phase 1 acceptance: compile, decompile, and validate a component
template whose ``spec:`` header and ``$[[ inputs.x ]]`` interpolation must
survive byte-for-byte.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from test.temp_change_dir import chdir_to_file_dir

from bash2yaml.commands.compile_all import run_compile_all
from bash2yaml.commands.decompile_all import run_decompile_gitlab_file
from bash2yaml.utils.gitlab_components import split_component_template

SCENARIO = "scenario_gitlab_component"


def clean_scenario() -> None:
    base = Path(__file__).parent / SCENARIO
    shutil.rmtree(str(base / ".out"), ignore_errors=True)
    shutil.rmtree(str(base / ".decompiled"), ignore_errors=True)
    shutil.rmtree(str(base / "uncompiled/.bash2yaml"), ignore_errors=True)


def test_compile_component_template():
    with chdir_to_file_dir(__file__):
        clean_scenario()
        uncompiled = Path(f"{SCENARIO}/uncompiled")
        output_root = Path(f"{SCENARIO}/.out")

        run_compile_all(uncompiled, output_root)

        source_text = (uncompiled / "scanner/template.yml").read_text(encoding="utf-8")
        source = split_component_template(source_text)
        assert source is not None, "fixture must be a component template"

        compiled_text = (output_root / "scanner/template.yml").read_text(encoding="utf-8")

        # The spec header and its --- separator survive byte-identically.
        assert (source.header + source.separator) in compiled_text

        # Interpolation spans pass through verbatim — in the YAML body and
        # from the inlined script.
        assert '"$[[ inputs.job-prefix ]]-scan"' in compiled_text
        assert "stage: $[[ inputs.stage ]]" in compiled_text
        assert "$[[ inputs.stage ]] stage" in compiled_text

        # The script got inlined and the pragma directive was stripped.
        assert "scan complete" in compiled_text
        assert "gitlab-interpolation" not in compiled_text
        assert "./scripts/scan.sh" not in compiled_text


def test_compiled_component_passes_validation():
    """run_compile_all validates via GitLabCIValidator and raises on failure,
    so a separate explicit check guards against validation being skipped.
    """
    with chdir_to_file_dir(__file__):
        clean_scenario()
        uncompiled = Path(f"{SCENARIO}/uncompiled")
        output_root = Path(f"{SCENARIO}/.out")
        run_compile_all(uncompiled, output_root)

        from bash2yaml.utils.validate_pipeline import GitLabCIValidator

        compiled_text = (output_root / "scanner/template.yml").read_text(encoding="utf-8")
        ok, errors = GitLabCIValidator().validate_ci_config(compiled_text)
        assert ok, errors


def test_decompile_component_template_round_trip():
    with chdir_to_file_dir(__file__):
        clean_scenario()
        uncompiled = Path(f"{SCENARIO}/uncompiled")
        output_root = Path(f"{SCENARIO}/.out")
        run_compile_all(uncompiled, output_root)

        compiled_yaml = output_root / "scanner/template.yml"
        decompile_dir = Path(f"{SCENARIO}/.decompiled")

        jobs, created, out_yaml = run_decompile_gitlab_file(
            input_yaml_path=compiled_yaml.resolve(),
            output_dir=decompile_dir.resolve(),
        )
        assert jobs >= 1
        assert created >= 1

        decompiled_text = out_yaml.read_text(encoding="utf-8")
        compiled = split_component_template(compiled_yaml.read_text(encoding="utf-8"))
        assert compiled is not None

        # Header + separator written back byte-identically.
        assert (compiled.header + compiled.separator) in decompiled_text
        # Body now references a script file instead of inline bash.
        assert ".sh" in decompiled_text
        assert "scan complete" not in decompiled_text

        # The extracted script keeps interpolation and gains the pragma so
        # recompiling is warning-free.
        scripts = [p for p in out_yaml.parent.rglob("*.sh") if "variables" not in p.name and "mock_ci" not in p.name]
        assert scripts, "expected an extracted script"
        script_text = "".join(p.read_text(encoding="utf-8") for p in scripts)
        assert "$[[ inputs.stage ]]" in script_text
        assert "Pragma: gitlab-interpolation" in script_text
