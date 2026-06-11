"""Live parity audit: run compile/validate/decompile per target against scenario fixtures."""

from __future__ import annotations

import os
import shutil
import tempfile
import traceback
from pathlib import Path

os.environ["BASH2YAML_SKIP_ROOT_CHECKS"] = "True"

from bash2yaml.commands.compile_all import run_compile_all
from bash2yaml.commands.decompile_all import run_decompile_gitlab_file
from bash2yaml.targets import get_target

ROOT = Path(__file__).resolve().parent.parent / "test" / "test_commands"

FIXTURES = {
    "gitlab": ("scenario1", ".gitlab-ci.yml"),
    "github": ("scenario_github1", "ci.yml"),
    "circleci": ("scenario_circleci1", "ci.yml"),
    "buildspec": ("scenario_buildspec1", "buildspec.yml"),
    "bitbucket": ("scenario_bitbucket1", "bitbucket-pipelines.yml"),
    "semaphore": ("scenario_semaphore1", "semaphore.yml"),
}

for name, (scenario, main_yaml) in FIXTURES.items():
    target = get_target(name)
    print(f"\n=== {name} ({scenario}) ===")
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / scenario
        shutil.copytree(ROOT / scenario, dest)
        uncompiled = dest / "uncompiled"
        out = dest / ".out"
        shutil.rmtree(out, ignore_errors=True)
        shutil.rmtree(uncompiled / ".bash2yaml", ignore_errors=True)
        shutil.rmtree(uncompiled / ".bash2gitlab", ignore_errors=True)
        cwd = os.getcwd()
        os.chdir(dest)
        try:
            # --- compile ---
            try:
                n = run_compile_all(uncompiled, out, target=target)
                compiled = out / main_yaml
                print(f"compile: OK inlined={n} output_exists={compiled.exists()}")
            except Exception as e:
                print(f"compile: FAIL {type(e).__name__}: {e}")
                traceback.print_exc(limit=2)
                continue

            # --- validate compiled output ---
            try:
                text = compiled.read_text(encoding="utf-8")
                ok, errors = target.validate(text)
                print(f"validate: {'OK' if ok else 'FAIL'} {errors[:2] if errors else ''}")
            except Exception as e:
                print(f"validate: FAIL {type(e).__name__}: {e}")

            # --- decompile compiled output ---
            try:
                dec = dest / ".decompiled"
                jobs, created, out_yaml = run_decompile_gitlab_file(
                    input_yaml_path=compiled.resolve(), output_dir=dec.resolve(), target=target
                )
                sh_files = [p.name for p in dec.rglob("*.sh") if "mock_ci" not in p.name]
                print(f"decompile: jobs={jobs} created={created} scripts={sh_files}")
            except Exception as e:
                print(f"decompile: FAIL {type(e).__name__}: {e}")
                traceback.print_exc(limit=2)
        finally:
            os.chdir(cwd)
