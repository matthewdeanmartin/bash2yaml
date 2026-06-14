"""End-to-end tests for traceless mode (Phase 4: adopt / compile / verify / shred)."""

from __future__ import annotations

import subprocess  # nosec
from pathlib import Path

import pytest

from bash2yaml.commands.compile_all import CompileOptions, run_compile_all
from bash2yaml.commands.decompile_all import run_decompile_traceless
from bash2yaml.commands.traceless_cmds import (
    run_traceless_adopt,
    run_traceless_compile,
    run_traceless_shred,
    run_traceless_verify,
)
from bash2yaml.errors.exceptions import Bash2YamlError, CompileError
from bash2yaml.utils.state_store import StateStore

SIMPLE_CI = """stages:
  - build

build_job:
  stage: build
  script:
    - echo "building"
    - make all
    - echo "done"
"""


@pytest.fixture
def git_repo(tmp_path: Path, monkeypatch) -> Path:
    """A scratch git repo with one CI file, cwd inside it, state dir isolated."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)  # nosec
    (repo / ".gitlab-ci.yml").write_text(SIMPLE_CI, encoding="utf-8")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("BASH2YAML_STATE_DIR", str(tmp_path / "state"))
    return repo


def state_store(tmp_path: Path) -> StateStore:
    return StateStore(tmp_path / "state")


def test_adopt_extracts_sources_and_leaves_tree_untouched(git_repo: Path, tmp_path: Path):
    before = (git_repo / ".gitlab-ci.yml").read_text(encoding="utf-8")

    rc = run_traceless_adopt(git_repo / ".gitlab-ci.yml")

    assert rc == 0
    assert (git_repo / ".gitlab-ci.yml").read_text(encoding="utf-8") == before
    store = state_store(tmp_path)
    assert ".gitlab-ci.yml" in store.sources
    assert (store.sources_dir / "build_job.sh").is_file()
    # No state landed in the repo itself
    assert not list(git_repo.rglob("*.hash"))
    assert not (git_repo / ".bash2yaml").exists()


def test_compile_after_adopt_writes_clean_yaml(git_repo: Path, tmp_path: Path, capsys):
    run_traceless_adopt(git_repo / ".gitlab-ci.yml")
    store = state_store(tmp_path)
    script = store.sources_dir / "build_job.sh"
    script.write_text(script.read_text(encoding="utf-8").replace('echo "done"', 'echo "all done"'), encoding="utf-8")

    rc = run_traceless_compile()

    assert rc == 0
    content = (git_repo / ".gitlab-ci.yml").read_text(encoding="utf-8")
    assert 'echo "all done"' in content
    # The traceless contract: no headers, no fences, no tool name.
    assert "DO NOT EDIT" not in content
    assert "BEGIN inline" not in content
    assert "bash2yaml" not in content
    assert content.endswith("\n")
    assert not list(git_repo.rglob("*.hash"))


def test_compile_check_mode_reports_out_of_date(git_repo: Path, tmp_path: Path):
    run_traceless_adopt(git_repo / ".gitlab-ci.yml")
    store = state_store(tmp_path)
    script = store.sources_dir / "build_job.sh"
    script.write_text(script.read_text(encoding="utf-8") + 'echo "extra"\n', encoding="utf-8")

    assert run_traceless_compile(check=True) == 1
    assert run_traceless_compile() == 0
    assert run_traceless_compile(check=True) == 0


def test_compile_refuses_to_clobber_manual_edit_without_force(git_repo: Path, tmp_path: Path):
    run_traceless_adopt(git_repo / ".gitlab-ci.yml")
    run_traceless_compile()  # normalize + record hash

    # Teammate (or incident response) edits the compiled YAML directly.
    ci = git_repo / ".gitlab-ci.yml"
    ci.write_text(ci.read_text(encoding="utf-8").replace("make all", "make hotfix"), encoding="utf-8")
    # And the state-dir source changes too, so a compile would overwrite.
    store = state_store(tmp_path)
    script = store.sources_dir / "build_job.sh"
    script.write_text(script.read_text(encoding="utf-8") + 'echo "extra"\n', encoding="utf-8")

    with pytest.raises(CompileError, match="Manual edit detected"):
        run_traceless_compile()
    assert "make hotfix" in ci.read_text(encoding="utf-8")  # nothing lost

    rc = run_traceless_compile(force=True)
    assert rc == 0
    assert "make hotfix" not in ci.read_text(encoding="utf-8")


def test_compile_without_adopt_is_a_friendly_error(git_repo: Path):
    with pytest.raises(Bash2YamlError, match="adopt"):
        run_traceless_compile()


def test_verify_clean_repo(git_repo: Path):
    assert run_traceless_verify() == 0


def test_verify_flags_hash_sidecars(git_repo: Path):
    (git_repo / ".gitlab-ci.yml.hash").write_text("abc", encoding="utf-8")
    assert run_traceless_verify() == 1


def test_verify_flags_attribution_markers(git_repo: Path):
    ci = git_repo / ".gitlab-ci.yml"
    ci.write_text(ci.read_text(encoding="utf-8") + "# compiled with bash2yaml\n", encoding="utf-8")
    assert run_traceless_verify() == 1
    assert run_traceless_verify(allow_markers=True) == 0


def test_verify_flags_state_dir_in_tree(git_repo: Path):
    (git_repo / ".bash2yaml").mkdir()
    assert run_traceless_verify() == 1


def test_verify_flags_tracked_config(git_repo: Path):
    (git_repo / ".bash2yaml.toml").write_text("[compile]\n", encoding="utf-8")
    # Untracked is allowed...
    assert run_traceless_verify() == 0
    subprocess.run(["git", "add", ".bash2yaml.toml"], cwd=str(git_repo), check=True)  # nosec
    # ...tracked is a violation.
    assert run_traceless_verify() == 1


def test_verify_setup_error_outside_repo(tmp_path: Path, monkeypatch):
    no_repo = tmp_path / "plain"
    no_repo.mkdir()
    monkeypatch.chdir(no_repo)
    assert run_traceless_verify() == 2


def test_shred_removes_state_and_only_state(git_repo: Path, tmp_path: Path):
    run_traceless_adopt(git_repo / ".gitlab-ci.yml")
    assert state_store(tmp_path).exists()

    assert run_traceless_shred() == 0
    assert not state_store(tmp_path).exists()
    assert (git_repo / ".gitlab-ci.yml").is_file()
    # Second shred is a no-op, not an error.
    assert run_traceless_shred() == 0


def test_decompile_traceless_no_rewrite_extracts_only_scripts(git_repo: Path, tmp_path: Path):
    before = (git_repo / ".gitlab-ci.yml").read_text(encoding="utf-8")

    jobs, created, dest = run_decompile_traceless(
        input_yaml_path=git_repo / ".gitlab-ci.yml",
        rewrite_yaml=False,
    )

    assert jobs == 1
    assert (git_repo / ".gitlab-ci.yml").read_text(encoding="utf-8") == before
    assert (dest / "build_job.sh").is_file()
    # --no-rewrite: no modified YAML is produced, not even in the state dir.
    assert not (dest / ".gitlab-ci.yml").exists()


def test_compile_traceless_options_macro():
    opts = CompileOptions.traceless(state_dir="/x", force=True)
    assert not opts.emit_header
    assert not opts.emit_fences
    assert not opts.write_hashes
    assert opts.in_place
    assert opts.force
    assert opts.state_dir == "/x"


def test_run_compile_all_with_no_footprint_flags(tmp_path: Path, monkeypatch):
    """Compile --no-header --no-fences --no-hash on a normal input tree."""
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "src"
    out = tmp_path / "out"
    src.mkdir()
    (src / "ci.yml").write_text(
        'job_one:\n  stage: build\n  script:\n    - ./build.sh\n',
        encoding="utf-8",
    )
    (src / "build.sh").write_text('#!/bin/bash\necho "step one"\necho "step two"\n', encoding="utf-8")

    options = CompileOptions(emit_header=False, emit_fences=False, write_hashes=False)
    run_compile_all(src, out, force=True, options=options)

    content = (out / "ci.yml").read_text(encoding="utf-8")
    assert "step one" in content
    assert "DO NOT EDIT" not in content
    assert "BEGIN inline" not in content
    assert "bash2yaml" not in content
    assert not list(out.rglob("*.hash"))
    assert not (out / ".bash2yaml").exists()
