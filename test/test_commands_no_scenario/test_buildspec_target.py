"""Unit tests for the BuildspecTarget adapter."""

from __future__ import annotations

import pytest

from bash2yaml.targets.buildspec import BuildspecTarget


@pytest.fixture
def target():
    return BuildspecTarget()


# --- Identity ----------------------------------------------------------------


def test_name(target):
    assert target.name == "buildspec"


def test_display_name(target):
    assert target.display_name == "AWS CodeBuild"


# --- script_key_paths --------------------------------------------------------


def test_script_key_paths_finds_phases(target):
    doc = {
        "version": 0.2,
        "phases": {
            "install": {
                "commands": ["npm install"],
            },
            "build": {
                "commands": ["npm run build", "npm test"],
            },
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 2
    job_names = {s.job_name for s in sections}
    assert "phases/install" in job_names
    assert "phases/build" in job_names
    install_section = next(s for s in sections if s.job_name == "phases/install")
    assert install_section.script_key == "commands"
    assert install_section.lines == ["npm install"]


def test_script_key_paths_finds_finally(target):
    doc = {
        "version": 0.2,
        "phases": {
            "build": {
                "commands": ["npm run build"],
                "finally": {
                    "commands": ["echo cleanup"],
                },
            },
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 2
    job_names = {s.job_name for s in sections}
    assert "phases/build" in job_names
    assert "phases/build/finally" in job_names
    finally_section = next(s for s in sections if s.job_name == "phases/build/finally")
    assert finally_section.script_key == "commands"
    assert finally_section.lines == ["echo cleanup"]


def test_script_key_paths_no_phases(target):
    doc = {"version": 0.2}
    sections = target.script_key_paths(doc)
    assert len(sections) == 0


# --- variables_key_paths -----------------------------------------------------


def test_variables_key_paths_env_variables(target):
    doc = {
        "version": 0.2,
        "env": {
            "variables": {
                "NODE_ENV": "ci",
                "BUILD_OUTPUT": "dist",
            }
        },
    }
    sections = target.variables_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].scope == "global"
    assert sections[0].key == "variables"
    assert sections[0].variables == {"NODE_ENV": "ci", "BUILD_OUTPUT": "dist"}
    assert sections[0].parent is doc["env"]


def test_variables_key_paths_empty(target):
    doc = {"version": 0.2}
    sections = target.variables_key_paths(doc)
    assert len(sections) == 0


# --- variables_key_name / job_entries ----------------------------------------


def test_variables_key_name(target):
    assert target.variables_key_name() == "variables"


def test_job_entries(target):
    doc = {
        "version": 0.2,
        "phases": {
            "install": {"commands": ["npm install"]},
            "build": {"commands": ["npm run build"]},
            "post_build": {"commands": ["echo done"]},
        },
    }
    entries = target.job_entries(doc)
    names = {e[0] for e in entries}
    assert names == {"phases/install", "phases/build", "phases/post_build"}


# --- Output conventions ------------------------------------------------------


def test_default_output_filename(target):
    assert target.default_output_filename() == "buildspec.yml"


# --- Decompile support -------------------------------------------------------


def test_script_keys(target):
    assert target.script_keys() == ["commands"]


def test_is_job_with_commands(target):
    assert target.is_job("build", {"commands": ["npm run build"]}) is True


def test_is_job_without_commands(target):
    assert target.is_job("artifacts", {"files": ["**/*"]}) is False


# --- Auto-detection ----------------------------------------------------------


def test_matches_filename_buildspec_yml(target):
    assert target.matches_filename("buildspec.yml") is True
    assert target.matches_filename("buildspec.yaml") is True
    assert target.matches_filename("BUILDSPEC.YML") is True


def test_matches_filename_other(target):
    assert target.matches_filename(".gitlab-ci.yml") is False
    assert target.matches_filename("workflow.yml") is False


def test_matches_directory_with_buildspec(target, tmp_path):
    (tmp_path / "buildspec.yml").write_text("version: 0.2\n")
    assert target.matches_directory(tmp_path) is True


def test_matches_directory_without(target, tmp_path):
    assert target.matches_directory(tmp_path) is False


# --- Schema / validation ----------------------------------------------------


def test_schema_url(target):
    assert "schemastore" in target.schema_url()
    assert "buildspec" in target.schema_url()


def test_fallback_schema_path(target):
    assert target.fallback_schema_path() == "schemas/buildspec_schema.json"
