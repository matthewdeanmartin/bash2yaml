"""Unit tests for the GitHubTarget adapter."""

from __future__ import annotations

import pytest

from bash2yaml.targets.github import GitHubTarget


@pytest.fixture
def target():
    return GitHubTarget()


# --- Identity ----------------------------------------------------------------


def test_name(target):
    assert target.name == "github"


def test_display_name(target):
    assert target.display_name == "GitHub Actions"


# --- script_key_paths --------------------------------------------------------


def test_script_key_paths_finds_run_in_steps(target):
    doc = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"name": "Build", "run": "./scripts/build.sh"},
                    {"name": "Test", "run": "npm test"},
                ],
            }
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 2
    assert sections[0].job_name == "build/Build"
    assert sections[0].script_key == "run"
    assert sections[0].lines == "./scripts/build.sh"
    assert sections[1].job_name == "build/Test"
    assert sections[1].lines == "npm test"


def test_script_key_paths_skips_uses_steps(target):
    doc = {
        "on": "push",
        "jobs": {
            "deploy": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-node@v3", "with": {"node-version": "18"}},
                ],
            }
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 0


def test_script_key_paths_no_jobs_key(target):
    doc = {"on": "push", "name": "Empty"}
    sections = target.script_key_paths(doc)
    assert len(sections) == 0


def test_script_key_paths_unnamed_step_uses_index(target):
    doc = {
        "on": "push",
        "jobs": {
            "lint": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"run": "echo hello"},
                ],
            }
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "lint/step[0]"


def test_script_key_paths_multiple_jobs(target):
    doc = {
        "on": "push",
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "steps": [{"name": "Compile", "run": "make"}],
            },
            "test": {
                "runs-on": "ubuntu-latest",
                "steps": [{"name": "Test", "run": "make test"}],
            },
        },
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 2
    job_names = {s.job_name for s in sections}
    assert "build/Compile" in job_names
    assert "test/Test" in job_names


# --- variables_key_paths -----------------------------------------------------


def test_variables_key_paths_finds_all_env_levels(target):
    doc = {
        "on": "push",
        "env": {"GLOBAL_VAR": "1"},
        "jobs": {
            "build": {
                "runs-on": "ubuntu-latest",
                "env": {"JOB_VAR": "2"},
                "steps": [
                    {"name": "Build", "run": "make", "env": {"STEP_VAR": "3"}},
                    {"uses": "actions/checkout@v4"},  # no env here
                ],
            }
        },
    }
    sections = target.variables_key_paths(doc)
    scopes = {s.scope for s in sections}
    assert "global" in scopes
    assert "build" in scopes
    assert "build/Build" in scopes
    assert len(sections) == 3


def test_variables_key_paths_empty_doc(target):
    doc = {"on": "push", "jobs": {"j": {"runs-on": "ubuntu-latest", "steps": []}}}
    sections = target.variables_key_paths(doc)
    assert len(sections) == 0


# --- variables_key_name / job_entries ----------------------------------------


def test_variables_key_name(target):
    assert target.variables_key_name() == "env"


def test_job_entries(target):
    doc = {
        "on": "push",
        "env": {"X": "1"},
        "jobs": {
            "build": {"runs-on": "ubuntu-latest", "steps": []},
            "test": {"runs-on": "ubuntu-latest", "steps": []},
        },
    }
    entries = target.job_entries(doc)
    names = {e[0] for e in entries}
    assert names == {"build", "test"}


def test_job_entries_no_jobs(target):
    doc = {"on": "push"}
    entries = target.job_entries(doc)
    assert entries == []


# --- Output conventions ------------------------------------------------------


def test_default_output_filename(target):
    assert target.default_output_filename() == "workflow.yml"


# --- Decompile support -------------------------------------------------------


def test_script_keys(target):
    assert target.script_keys() == ["run"]


def test_is_job_with_steps(target):
    assert target.is_job("build", {"runs-on": "ubuntu-latest", "steps": []}) is True


def test_is_job_reusable_workflow(target):
    assert target.is_job("call-workflow", {"uses": "org/repo/.github/workflows/build.yml@main"}) is True


def test_is_job_reserved_key(target):
    assert target.is_job("name", {"steps": []}) is False


def test_is_job_non_dict(target):
    assert target.is_job("build", "not a dict") is False


# --- Reserved keys -----------------------------------------------------------


def test_reserved_top_level_keys(target):
    keys = target.reserved_top_level_keys()
    assert "on" in keys
    assert "name" in keys
    assert "env" in keys
    assert "permissions" in keys
    assert "jobs" not in keys  # jobs is where actual jobs live


# --- Auto-detection ----------------------------------------------------------


def test_matches_filename_returns_false(target):
    # GitHub workflows don't have a single canonical filename
    assert target.matches_filename("workflow.yml") is False


def test_matches_directory_github_workflows(target, tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    assert target.matches_directory(workflows) is True


def test_matches_directory_parent_of_github(target, tmp_path):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    assert target.matches_directory(tmp_path) is True


def test_matches_directory_random_dir(target, tmp_path):
    assert target.matches_directory(tmp_path) is False


# --- Schema / validation ----------------------------------------------------


def test_schema_url(target):
    assert "schemastore" in target.schema_url()
    assert "github-workflow" in target.schema_url()


def test_fallback_schema_path(target):
    assert target.fallback_schema_path() == "schemas/github_workflow_schema.json"
