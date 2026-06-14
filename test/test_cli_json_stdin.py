"""CLI tests for Phase 3 ergonomics: --json output, piped stdin, quiet attribution."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

SIMPLE_CI = """build_job:
  stage: build
  script:
    - ./build.sh
"""

BUILD_SH = '#!/bin/bash\necho "step one"\necho "step two"\n'


@pytest.fixture(autouse=True)
def cli_env(monkeypatch):
    """Neutralize update checks / argcomplete, keep logging configurable."""
    import bash2yaml.__main__ as m

    if m.argcomplete:
        monkeypatch.setattr(m.argcomplete, "autocomplete", lambda *a, **k: None)
    monkeypatch.setattr(m, "start_background_update_check", lambda *a, **k: None)
    monkeypatch.setattr(m.logging.config, "dictConfig", lambda cfg: None)
    # enable_quiet_attribution sets this for child processes. setenv (not
    # delenv) registers an undo even when the var was absent, so the flag set
    # by the code under test cannot leak into other tests. Empty string is
    # falsy for every consumer.
    for var in (
        "BASH2YAML_QUIET_ATTRIBUTION",
        "BASH2YAML_TRACELESS",
        "BASH2YAML_STATE_DIR",
        "BASH2YAML_NO_HEADER",
    ):
        monkeypatch.setenv(var, "")
    yield


def run_main(monkeypatch, argv: list[str]) -> int:
    import bash2yaml.__main__ as m

    monkeypatch.setattr(sys, "argv", ["bash2yaml", *argv])
    try:
        return int(m.main())
    except SystemExit as e:
        return int(e.code or 0)


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "ci.yml").write_text(SIMPLE_CI, encoding="utf-8")
    (src / "build.sh").write_text(BUILD_SH, encoding="utf-8")
    return tmp_path


def test_compile_json_reports_stats(project: Path, monkeypatch, capsys):
    rc = run_main(monkeypatch, ["compile", "--in", "src", "--out", "out", "--force", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["command"] == "compile"
    assert payload["files_written"] == 1
    assert payload["inlined_sections"] >= 1


def test_validate_json_reports_results(project: Path, monkeypatch, capsys):
    rc = run_main(monkeypatch, ["validate", "--in", "src", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["command"] == "validate"
    assert payload["summary"]["total_files"] == 1
    assert payload["summary"]["invalid_files"] == 0


def test_validate_without_out_does_not_crash(project: Path, monkeypatch, capsys):
    # Phase 3 pain point: `validate` without --out used to be a raw traceback.
    rc = run_main(monkeypatch, ["validate", "--in", "src"])
    assert rc == 0


def test_detect_drift_json(project: Path, monkeypatch, capsys):
    run_main(monkeypatch, ["compile", "--in", "src", "--out", "out", "--force"])
    capsys.readouterr()

    rc = run_main(monkeypatch, ["detect-drift", "--out", "out", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["command"] == "detect-drift"
    assert payload["drifted_files"] == []

    # Introduce drift and confirm both the exit code and the report change.
    out_file = project / "out" / "ci.yml"
    out_file.write_text(out_file.read_text(encoding="utf-8") + "# manual edit\n", encoding="utf-8")
    rc = run_main(monkeypatch, ["detect-drift", "--out", "out", "--json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert len(payload["drifted_files"]) == 1


def test_detect_drift_exit_code_propagates(project: Path, monkeypatch, capsys):
    # Phase 3 pain point: handler return codes were swallowed (always exit 0).
    run_main(monkeypatch, ["compile", "--in", "src", "--out", "out", "--force"])
    out_file = project / "out" / "ci.yml"
    out_file.write_text(out_file.read_text(encoding="utf-8") + "# manual edit\n", encoding="utf-8")
    assert run_main(monkeypatch, ["detect-drift", "--out", "out"]) == 1


def test_compile_stdin_to_stdout(project: Path, monkeypatch, capsys):
    monkeypatch.chdir(project / "src")
    monkeypatch.setattr(sys, "stdin", io.StringIO(SIMPLE_CI))
    rc = run_main(monkeypatch, ["compile", "--in", "-"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "step one" in out
    assert "./build.sh" not in out.replace("BEGIN inline: build.sh", "")
    # stdin mode writes nothing to disk
    assert not (project / "src" / "ci.yml.hash").exists()


def test_validate_stdin(project: Path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("job:\n  script:\n    - echo hi\n"))
    rc = run_main(monkeypatch, ["validate", "--in", "-", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["file"] == "<stdin>"
    assert payload["is_valid"] is True


def test_missing_script_error_suggests_pragma(project: Path, monkeypatch, capsys):
    (project / "src" / "ci.yml").write_text(
        "build_job:\n  stage: build\n  script:\n    - ./missing.sh\n", encoding="utf-8"
    )
    rc = run_main(monkeypatch, ["compile", "--in", "src", "--out", "out", "--force"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "do-not-inline" in err


def test_compile_quiet_attribution_banner(project: Path, monkeypatch, capsys):
    rc = run_main(
        monkeypatch,
        ["compile", "--in", "src", "--out", "out", "--force", "--quiet-attribution"],
    )
    assert rc == 0
    content = (project / "out" / "ci.yml").read_text(encoding="utf-8")
    assert "bash2yaml" not in content
    assert "DO NOT EDIT" in content  # header is still there, just unattributed


def test_scrub_attribution_text():
    from bash2yaml.utils.attribution import scrub_attribution

    assert "bash2yaml" not in scrub_attribution("compiled with bash2yaml")
    assert "bash2yaml" not in scrub_attribution("Starting bash2yaml compiler...")
    assert "bash2yaml" not in scrub_attribution("BASH2YAML rocks")
    assert scrub_attribution("nothing to see") == "nothing to see"
