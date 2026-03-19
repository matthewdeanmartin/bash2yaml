"""Unit tests for the CircleCITarget adapter."""

from __future__ import annotations

import pytest

from bash2yaml.targets.circleci import CircleCITarget


@pytest.fixture
def target():
    return CircleCITarget()


# --- Identity ----------------------------------------------------------------


def test_name(target):
    assert target.name == "circleci"


def test_display_name(target):
    assert target.display_name == "CircleCI"


# --- script_key_paths --------------------------------------------------------


def test_script_key_paths_string_run(target):
    """Shorthand ``run: "command"`` form is found and parent is the step dict."""
    doc = {
        "version": 2.1,
        "jobs": {
            "build": {
                "docker": [{"image": "cimg/node:20.0"}],
                "steps": [
                    "checkout",
                    {"run": "./scripts/build.sh"},
                ],
            }
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].script_key == "run"
    assert sections[0].lines == "./scripts/build.sh"
    assert sections[0].parent is doc["jobs"]["build"]["steps"][1]
    assert sections[0].job_name == "build/step[1]"


def test_script_key_paths_dict_run(target):
    """Object form ``run:\n  command: |`` — parent is the run dict, key is ``command``."""
    doc = {
        "version": 2.1,
        "jobs": {
            "install": {
                "docker": [{"image": "cimg/node:20.0"}],
                "steps": [
                    "checkout",
                    {
                        "run": {
                            "name": "Install dependencies",
                            "command": "./scripts/install.sh",
                        }
                    },
                ],
            }
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].script_key == "command"
    assert sections[0].lines == "./scripts/install.sh"
    assert sections[0].parent is doc["jobs"]["install"]["steps"][1]["run"]
    assert sections[0].job_name == "install/Install dependencies"


def test_script_key_paths_dict_run_no_name_uses_index(target):
    """Object form without ``name:`` falls back to ``step[{idx}]``."""
    doc = {
        "version": 2.1,
        "jobs": {
            "build": {
                "docker": [{"image": "cimg/base:2023.06"}],
                "steps": [
                    {
                        "run": {
                            "command": "echo hello",
                        }
                    },
                ],
            }
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "build/step[0]"


def test_script_key_paths_skips_non_run_steps(target):
    """Non-run steps (checkout, restore_cache, orb commands) are skipped."""
    doc = {
        "version": 2.1,
        "jobs": {
            "build": {
                "docker": [{"image": "cimg/node:20.0"}],
                "steps": [
                    "checkout",
                    {"restore_cache": {"keys": ['v1-{{ checksum "package.json" }}']}},
                    {"save_cache": {"key": 'v1-{{ checksum "package.json" }}', "paths": ["node_modules"]}},
                    {"store_artifacts": {"path": "dist"}},
                    {"node/install-packages": {}},
                ],
            }
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 0


def test_script_key_paths_no_jobs(target):
    """Empty document returns no sections."""
    doc = {"version": 2.1}
    sections = target.script_key_paths(doc)
    assert len(sections) == 0


def test_script_key_paths_multiple_jobs(target):
    """Sections are collected from all jobs."""
    doc = {
        "version": 2.1,
        "jobs": {
            "install": {
                "docker": [{"image": "cimg/node:20.0"}],
                "steps": [
                    "checkout",
                    {"run": {"name": "Install", "command": "./scripts/install.sh"}},
                ],
            },
            "build": {
                "docker": [{"image": "cimg/node:20.0"}],
                "steps": [
                    "checkout",
                    {"run": "./scripts/build.sh"},
                ],
            },
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 2
    job_names = {s.job_name for s in sections}
    assert "install/Install" in job_names
    assert "build/step[1]" in job_names


# --- variables_key_paths -----------------------------------------------------


def test_variables_key_paths_job_level(target):
    """``environment:`` at the job level is discovered."""
    doc = {
        "version": 2.1,
        "jobs": {
            "install": {
                "docker": [{"image": "cimg/node:20.0"}],
                "environment": {"NODE_ENV": "ci"},
                "steps": ["checkout"],
            },
            "build": {
                "docker": [{"image": "cimg/node:20.0"}],
                "steps": ["checkout"],
            },
        },
    }
    sections = target.variables_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].scope == "install"
    assert sections[0].key == "environment"
    assert sections[0].variables == {"NODE_ENV": "ci"}


def test_variables_key_paths_no_environment(target):
    """Jobs without ``environment:`` produce no sections."""
    doc = {
        "version": 2.1,
        "jobs": {
            "build": {
                "docker": [{"image": "cimg/node:20.0"}],
                "steps": ["checkout"],
            }
        },
    }
    sections = target.variables_key_paths(doc)
    assert len(sections) == 0


def test_variables_key_paths_no_jobs(target):
    doc = {"version": 2.1}
    sections = target.variables_key_paths(doc)
    assert len(sections) == 0


# --- variables_key_name / job_entries ----------------------------------------


def test_variables_key_name(target):
    assert target.variables_key_name() == "environment"


def test_job_entries(target):
    doc = {
        "version": 2.1,
        "jobs": {
            "install": {"docker": [{"image": "cimg/node:20.0"}], "steps": []},
            "build": {"docker": [{"image": "cimg/node:20.0"}], "steps": []},
        },
    }
    entries = target.job_entries(doc)
    names = {e[0] for e in entries}
    assert names == {"install", "build"}


def test_job_entries_no_jobs(target):
    doc = {"version": 2.1}
    entries = target.job_entries(doc)
    assert entries == []


# --- Output conventions ------------------------------------------------------


def test_default_output_filename(target):
    assert target.default_output_filename() == ".circleci/config.yml"


# --- Decompile support -------------------------------------------------------


def test_script_keys(target):
    assert target.script_keys() == ["run"]


def test_is_job_with_steps(target):
    assert target.is_job("build", {"docker": [{"image": "cimg/node:20.0"}], "steps": []}) is True


def test_is_job_reserved_key(target):
    assert target.is_job("workflows", {"main": {"jobs": ["build"]}}) is False
    assert target.is_job("version", 2.1) is False
    assert target.is_job("orbs", {"node": "circleci/node@5"}) is False


def test_is_job_no_steps(target):
    assert target.is_job("build", {"docker": [{"image": "cimg/node:20.0"}]}) is False


def test_is_job_non_dict(target):
    assert target.is_job("build", "not a dict") is False


# --- Auto-detection ----------------------------------------------------------


def test_matches_filename_false(target):
    # CircleCI filename alone is ambiguous — always False
    assert target.matches_filename("config.yml") is False
    assert target.matches_filename(".circleci/config.yml") is False


def test_matches_directory_circleci(target, tmp_path):
    circleci_dir = tmp_path / ".circleci"
    circleci_dir.mkdir()
    assert target.matches_directory(circleci_dir) is True


def test_matches_directory_parent_of_circleci(target, tmp_path):
    circleci_dir = tmp_path / ".circleci"
    circleci_dir.mkdir()
    assert target.matches_directory(tmp_path) is True


def test_matches_directory_random_dir(target, tmp_path):
    assert target.matches_directory(tmp_path) is False


# --- Schema / validation ----------------------------------------------------


def test_schema_url(target):
    assert "schemastore" in target.schema_url()
    assert "circleci" in target.schema_url()


def test_fallback_schema_path(target):
    assert target.fallback_schema_path() == "schemas/circleci_schema.json"
