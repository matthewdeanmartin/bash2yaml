"""Regressions for the built-in runtime after removing extension hooks."""

import argparse
import subprocess
import sys
from types import SimpleNamespace

import pytest

from bash2yaml.__main__ import run_cli
from bash2yaml.commands import autogit


@pytest.mark.parametrize("without_extras", [False, True])
def test_runtime_does_not_import_pluggy(without_extras):
    code = f"without_extras = {without_extras!r}\n" + """
import sys
from importlib.abc import MetaPathFinder

class NoPluggy(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pluggy' or fullname.startswith('pluggy.'):
            raise AssertionError('Runtime attempted to load Pluggy')
        if without_extras and fullname == 'tomlkit':
            raise ModuleNotFoundError(fullname)

sys.meta_path.insert(0, NoPluggy())
import bash2yaml.__main__
from bash2yaml.targets import list_targets
assert list_targets() == ['bitbucket', 'buildspec', 'circleci', 'github', 'gitlab', 'semaphore']
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(("result", "enabled", "staged"), [(0, True, True), (1, True, False), (0, False, False)])
def test_cli_autogit_stages_only_after_success(tmp_path, monkeypatch, result, enabled, staged):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True).stdout

    git("init")
    source = tmp_path / "src"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    (source / "script.sh").write_text("echo hello\n", encoding="utf-8")
    (output / "ci.yml").write_text("job: {}\n", encoding="utf-8")
    monkeypatch.setattr(
        autogit,
        "config",
        SimpleNamespace(
            autogit_mode="stage",
            input_dir=str(source),
            output_dir=str(output),
        ),
    )
    args = argparse.Namespace(func=lambda _args: result, autogit=enabled)
    assert run_cli(args) == result
    assert bool(git("diff", "--cached", "--name-only").strip()) is staged
