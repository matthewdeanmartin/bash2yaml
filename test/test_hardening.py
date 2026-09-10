"""Regression tests for compilation boundaries, publication, and selection."""

import argparse
import base64
import json
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

from bash2yaml.__main__ import run_cli
from bash2yaml.commands.compile_all import process_script_list, run_compile_all
from bash2yaml.commands.compile_artifacts import maybe_inline_artifact
from bash2yaml.commands.compile_bash_reader import read_bash_script
from bash2yaml.commands.hash_path_helpers import get_output_hash_path
from bash2yaml.commands.input_change_detector import needs_compilation
from bash2yaml.config import config
from bash2yaml.errors.exceptions import ConfigInvalid, ValidationFailed
from bash2yaml.targets import detect_target, get_target, resolve_target
from bash2yaml.utils.atomic_io import atomic_write_text
from bash2yaml.utils.source_paths import SourceSecurityError, resolve_source
from bash2yaml.utils.state_store import StateStore, sha256_text

PRAGMA = "# Pragma: do-not-validate-schema\n"
TEMPLATES = {
    "gitlab": "job:\n  script: ['./hello.sh']\n",
    "github": "jobs:\n  job:\n    runs-on: ubuntu-latest\n    steps:\n      - run: ./hello.sh\n",
    "circleci": "version: 2.1\njobs:\n  job:\n    steps:\n      - run: ./hello.sh\n",
    "buildspec": "version: 0.2\nphases:\n  build:\n    commands: ['./hello.sh']\n",
    "bitbucket": "pipelines:\n  default:\n    - step:\n        script: ['./hello.sh']\n",
    "semaphore": "version: v1.0\nblocks:\n  - name: build\n    task:\n      jobs:\n        - name: job\n          commands: ['./hello.sh']\n",
}


@pytest.mark.skipif(os.name != "nt", reason="Windows extended path namespace")
def test_extended_windows_paths_share_containment_boundary(tmp_path):
    root = tmp_path / "sources"
    root.mkdir()
    script = root / "hello.py"
    script.write_text("print('hello')", encoding="utf-8")
    extended = Path("\\\\?\\" + str(script))
    extended_root = Path("\\\\?\\" + str(root))
    assert resolve_source(root, extended, root) == script
    assert resolve_source(root, script, extended_root) == script
    with pytest.raises(SourceSecurityError):
        resolve_source(root, Path("\\\\?\\" + str(tmp_path / "outside.py")), root)


@pytest.mark.parametrize("platform", TEMPLATES)
@pytest.mark.timeout(60)
def test_spawn_matches_sequential_for_each_target(tmp_path, monkeypatch, platform):
    source = tmp_path / "src"
    source.mkdir()
    (source / "hello.sh").write_text("echo worker-output\n", encoding="utf-8")
    for number in range(5):
        (source / f"ci{number}.yml").write_text(PRAGMA + TEMPLATES[platform], encoding="utf-8")
    # This configuration exists only in the parent, not in a config file on disk.
    monkeypatch.setattr(config, "file_config", {"custom_header": "# configured in the parent"})
    monkeypatch.setattr(config, "env_config", {})
    outputs = []
    reports = []
    for workers in (1, 2):
        destination = tmp_path / f"out{workers}"
        stats = {}
        assert (
            run_compile_all(
                source, destination, parallelism=workers, force=True, target=get_target(platform), stats=stats
            )
            == 5
        )
        outputs.append({path.name: path.read_bytes() for path in destination.glob("*.yml")})
        reports.append(stats)
        assert not needs_compilation(source)
    assert outputs[0] == outputs[1]
    assert reports[0] == reports[1]
    assert all(
        b"echo worker-output" in content and b"configured in the parent" in content for content in outputs[1].values()
    )


@pytest.mark.parametrize("platform", TEMPLATES)
@pytest.mark.timeout(60)
def test_validation_failures_propagate_from_workers(tmp_path, monkeypatch, platform):
    source = tmp_path / "src"
    source.mkdir()
    (source / "hello.sh").write_text("echo invalid-header-test\n", encoding="utf-8")
    for number in range(5):
        (source / f"ci{number}.yml").write_text(TEMPLATES[platform], encoding="utf-8")
    monkeypatch.setattr(config, "file_config", {"custom_header": "invalid: ["})
    monkeypatch.setattr(config, "env_config", {})
    for workers in (1, 2):
        destination = tmp_path / f"out{workers}"
        with pytest.raises(ValidationFailed):
            run_compile_all(source, destination, force=True, parallelism=workers, target=get_target(platform))
        assert not list(destination.glob("*.yml"))
        assert needs_compilation(source)


@pytest.mark.parametrize(
    "command", ["./../secret.sh", "python ../secret.py", "# Pragma: inline-artifact ../secret.txt"]
)
def test_all_inliners_reject_parent_escape(tmp_path, command):
    source = tmp_path / "src"
    source.mkdir()
    for suffix in ("sh", "py", "txt"):
        (tmp_path / f"secret.{suffix}").write_text("DO_NOT_EMBED", encoding="utf-8")
    with pytest.raises(SourceSecurityError) as error:
        process_script_list([command], source, allowed_root=source)
    assert "DO_NOT_EMBED" not in str(error.value)


def test_parent_path_is_preserved_inside_allowed_tree(tmp_path):
    nested = tmp_path / "src"
    nested.mkdir()
    (tmp_path / "hello.py").write_text("print('correct file')", encoding="utf-8")
    (nested / "hello.py").write_text("print('wrong file')", encoding="utf-8")
    output = process_script_list(["python ../hello.py"], nested, allowed_root=tmp_path)
    assert "correct file" in str(output)
    assert "wrong file" not in str(output)


def test_quoted_unicode_paths_and_nested_sources(tmp_path):
    (tmp_path / "café script.py").write_text("print('unicode')", encoding="utf-8")
    assert "unicode" in str(process_script_list(['python "café script.py"'], tmp_path))
    (tmp_path / "inner script.sh").write_text("echo nested\n", encoding="utf-8")
    script = tmp_path / "main.sh"
    script.write_text('source "inner script.sh"\n', encoding="utf-8")
    assert "echo nested" in read_bash_script(script, allowed_root=tmp_path)


def test_artifact_quotes_runtime_output_path(tmp_path):
    (tmp_path / "source file.txt").write_text("data", encoding="utf-8")
    lines, _ = maybe_inline_artifact('# Pragma: inline-artifact "source file.txt" --output="/tmp/output dir"', tmp_path)
    assert "mkdir -p '/tmp/output dir'" in lines


@pytest.mark.parametrize("value", ["C:relative.py", "Z:\\outside\\secret.py", "\\\\other-server\\share\\secret.py"])
def test_drive_and_unc_paths_are_not_reinterpreted(tmp_path, value):
    with pytest.raises(SourceSecurityError):
        resolve_source(tmp_path, value, tmp_path)


def test_absolute_paths_require_containment(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    assert resolve_source(source, source / "ok.py", source) == source / "ok.py"
    with pytest.raises(SourceSecurityError):
        resolve_source(source, tmp_path / "outside.py", source)


@pytest.mark.parametrize("kind", ["bash", "python", "artifact"])
def test_symlink_escape_is_blocked(tmp_path, kind):
    source = tmp_path / "src"
    source.mkdir()
    secret = tmp_path / "secret.py"
    secret.write_text("DO_NOT_EMBED", encoding="utf-8")
    bundle = source / "bundle"
    bundle.mkdir()
    link = bundle / ("link.sh" if kind == "bash" else "link.py")
    try:
        link.symlink_to(secret)
    except OSError as error:
        pytest.skip(f"Symlinks unavailable: {error}")
    command = {
        "bash": "./bundle/link.sh",
        "python": "python bundle/link.py",
        "artifact": "# Pragma: inline-artifact bundle",
    }[kind]
    with pytest.raises(SourceSecurityError):
        process_script_list([command], source, allowed_root=source)


def test_atomic_write_failure_preserves_old_file(tmp_path):
    output = tmp_path / "existing.yml"
    output.write_text("old content", encoding="utf-8")
    with pytest.raises(UnicodeEncodeError):
        atomic_write_text(output, "invalid UTF-8: \ud800")
    assert output.read_text(encoding="utf-8") == "old content"
    assert list(tmp_path.iterdir()) == [output]


def test_retry_repairs_output_after_integrity_write_failure(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "hello.sh").write_text("echo recovery\n", encoding="utf-8")
    (source / "ci.yml").write_text(PRAGMA + TEMPLATES["gitlab"], encoding="utf-8")
    destination = tmp_path / "out"
    hash_path = get_output_hash_path(destination / "ci.yml", destination)
    hash_path.mkdir(parents=True)  # Real write failure, after output publication.
    with pytest.raises(OSError):
        run_compile_all(source, destination)
    assert (source / ".bash2yaml/compilation.pending").exists()
    published = (destination / "ci.yml").read_text(encoding="utf-8")
    assert "echo recovery" in published
    # Simulate a temporary file abandoned by a killed writer.
    abandoned = destination / ".bash2yaml-write-interrupted.tmp"
    abandoned.write_text("incomplete publication", encoding="utf-8")
    hash_path.rmdir()
    run_compile_all(source, destination)
    assert base64.b64decode(hash_path.read_text()).decode() == published
    assert not needs_compilation(source)


@pytest.mark.parametrize(
    "bad",
    [
        [],
        None,
        {"version": 99},
        {"version": 1, "hashes": [], "sources": {}},
        {"version": 1, "hashes": {"ci.yml": "bad"}, "sources": {}},
        {"version": 1, "hashes": {}, "sources": {"ci.yml": {"uncompiled": "../escape.yml"}}},
    ],
)
def test_bad_state_is_rejected_without_overwriting(tmp_path, bad):
    path = tmp_path / "state.json"
    text = json.dumps(bad)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigInvalid):
        StateStore(tmp_path).record_hash("ci.yml", "new")
    assert path.read_text(encoding="utf-8") == text


def test_split_state_migrates_without_losing_records(tmp_path):
    (tmp_path / "hashes.json").write_text(json.dumps({"old.yml": sha256_text("old")}), encoding="utf-8")
    (tmp_path / "sources.json").write_text(json.dumps({"old.yml": {"uncompiled": "sources/old.yml"}}), encoding="utf-8")
    store = StateStore(tmp_path)
    store.record_hash("new.yml", "new")
    store.save()
    fresh = StateStore(tmp_path)
    assert fresh.content_matches("old.yml", "old")
    assert fresh.content_matches("new.yml", "new")
    assert fresh.sources["old.yml"]["uncompiled"] == "sources/old.yml"
    assert json.loads(fresh.state_path.read_text())["version"] == 1


def _save_record(arguments):
    path, number = arguments
    store = StateStore(Path(path))
    store.record_hash(f"file{number}.yml", str(number))
    store.record_source(f"file{number}.yml", {"uncompiled": f"sources/file{number}.yml"})
    store.save()


@pytest.mark.timeout(60)
def test_parallel_state_writers_keep_all_records(tmp_path):
    with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn")) as pool:
        list(pool.map(_save_record, [(str(tmp_path), number) for number in range(10)]))
    store = StateStore(tmp_path)
    assert len(store.hashes) == len(store.sources) == 10
    assert all(store.content_matches(f"file{number}.yml", str(number)) for number in range(10))


def test_same_platform_matching_twice_is_unambiguous(tmp_path):
    semaphore = tmp_path / ".semaphore"
    semaphore.mkdir()
    assert detect_target("semaphore.yml", semaphore).name == "semaphore"


def test_conflicting_platforms_require_explicit_selection(tmp_path):
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".circleci").mkdir()
    with pytest.raises(ConfigInvalid, match="--target"):
        resolve_target(directory=tmp_path)
    assert resolve_target(cli_target="github", directory=tmp_path).name == "github"


def test_requested_autogit_failure_is_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        config, "file_config", {"autogit": {"mode": "stage"}, "input_dir": str(tmp_path), "output_dir": str(tmp_path)}
    )
    monkeypatch.setattr(config, "env_config", {})
    args = argparse.Namespace(func=lambda _: 0, autogit=True)
    assert run_cli(args) != 0  # tmp_path is deliberately not a Git repository.
    assert "--autogit action failed" in capsys.readouterr().err


def test_runtime_interpreter_reference_can_opt_out(tmp_path):
    command = "python runtime.py # Pragma: do-not-inline"
    assert process_script_list([command], tmp_path) == [command]


def test_yaml_formatting_does_not_leak_between_operations():
    from bash2yaml.utils.yaml_factory import get_yaml

    customized = get_yaml()
    customized.indent(mapping=2, sequence=4, offset=2)
    fresh = get_yaml()
    assert fresh is not customized
    assert fresh.block_seq_indent != customized.block_seq_indent
