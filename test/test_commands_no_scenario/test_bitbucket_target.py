"""Unit tests for the BitbucketTarget adapter."""

from __future__ import annotations

import pytest

from bash2yaml.targets.bitbucket import BitbucketTarget


@pytest.fixture
def target():
    return BitbucketTarget()


# --- Identity ----------------------------------------------------------------


def test_name(target):
    assert target.name == "bitbucket"


def test_display_name(target):
    assert target.display_name == "Bitbucket Pipelines"


# --- script_key_paths --------------------------------------------------------


def test_script_key_paths_default_pipeline(target):
    """Default pipeline list of step-groups is traversed."""
    doc = {
        "pipelines": {
            "default": [
                {
                    "step": {
                        "name": "Build",
                        "script": ["./scripts/build.sh"],
                        "after-script": ["./scripts/cleanup.sh"],
                    }
                }
            ]
        }
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 2
    script_section = next(s for s in sections if s.script_key == "script")
    after_section = next(s for s in sections if s.script_key == "after-script")
    assert script_section.job_name == "pipelines/default/Build"
    assert script_section.lines == ["./scripts/build.sh"]
    assert after_section.job_name == "pipelines/default/Build"
    assert after_section.lines == ["./scripts/cleanup.sh"]


def test_script_key_paths_default_uses_index_when_no_name(target):
    """Default pipeline step without a name uses step[idx] as job name."""
    doc = {
        "pipelines": {
            "default": [
                {
                    "step": {
                        "script": ["echo hello"],
                    }
                }
            ]
        }
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "pipelines/default/step[0]"


def test_script_key_paths_branches_pipeline(target):
    """Branches pipeline dict of pattern → step list is traversed."""
    doc = {
        "pipelines": {
            "branches": {
                "main": [
                    {
                        "step": {
                            "name": "Deploy to production",
                            "script": ["./scripts/deploy.sh"],
                        }
                    }
                ]
            }
        }
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "pipelines/branches/main/Deploy to production"
    assert sections[0].script_key == "script"
    assert sections[0].lines == ["./scripts/deploy.sh"]


def test_script_key_paths_custom_pipeline(target):
    """Custom pipeline is traversed by name."""
    doc = {
        "pipelines": {
            "custom": {
                "run-tests": [
                    {
                        "step": {
                            "name": "Run tests",
                            "script": ["./scripts/test.sh"],
                        }
                    }
                ]
            }
        }
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "pipelines/custom/run-tests/Run tests"


def test_script_key_paths_parallel_steps(target):
    """Parallel step entries are traversed and each step is extracted."""
    doc = {
        "pipelines": {
            "default": [
                {
                    "parallel": [
                        {
                            "step": {
                                "name": "Unit tests",
                                "script": ["npm test"],
                            }
                        },
                        {
                            "step": {
                                "name": "Lint",
                                "script": ["npm run lint"],
                            }
                        },
                    ]
                }
            ]
        }
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 2
    job_names = {s.job_name for s in sections}
    assert "pipelines/default/parallel[0]/Unit tests" in job_names
    assert "pipelines/default/parallel[0]/Lint" in job_names


def test_script_key_paths_no_pipelines_key(target):
    """Document without a ``pipelines`` key returns no sections."""
    doc = {"image": "atlassian/default-image:4"}
    sections = target.script_key_paths(doc)
    assert sections == []


def test_script_key_paths_skips_steps_without_script(target):
    """Steps that lack a ``script`` key are skipped."""
    doc = {
        "pipelines": {
            "default": [
                {
                    "step": {
                        "name": "No script here",
                    }
                }
            ]
        }
    }
    sections = target.script_key_paths(doc)
    assert sections == []


def test_script_key_paths_after_script_only_when_present(target):
    """``after-script`` section is only added when the key exists on the step."""
    doc = {
        "pipelines": {
            "default": [
                {
                    "step": {
                        "name": "Build",
                        "script": ["npm run build"],
                    }
                }
            ]
        }
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].script_key == "script"


def test_script_key_paths_multiple_triggers(target):
    """Sections are collected from all triggers."""
    doc = {
        "pipelines": {
            "default": [{"step": {"name": "Default", "script": ["echo default"]}}],
            "branches": {"main": [{"step": {"name": "Main branch", "script": ["echo main"]}}]},
            "tags": {"v*": [{"step": {"name": "Tag release", "script": ["echo release"]}}]},
        }
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 3
    job_names = {s.job_name for s in sections}
    assert "pipelines/default/Default" in job_names
    assert "pipelines/branches/main/Main branch" in job_names
    assert "pipelines/tags/v*/Tag release" in job_names


def test_script_key_paths_parent_is_step_dict(target):
    """The ``parent`` of the ScriptSection is the step dict itself."""
    step_dict = {"name": "Build", "script": ["./build.sh"]}
    doc = {"pipelines": {"default": [{"step": step_dict}]}}
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].parent is step_dict


# --- variables_key_paths -----------------------------------------------------


def test_variables_key_paths_returns_empty(target):
    """Bitbucket variables are not used for YAML-level merging — always empty."""
    doc = {
        "pipelines": {
            "default": [
                {
                    "step": {
                        "name": "Build",
                        "script": ["echo hi"],
                    }
                }
            ]
        }
    }
    sections = target.variables_key_paths(doc)
    assert sections == []


def test_variables_key_paths_empty_doc(target):
    doc = {}
    sections = target.variables_key_paths(doc)
    assert sections == []


# --- variables_key_name / job_entries ----------------------------------------


def test_variables_key_name(target):
    assert target.variables_key_name() == "variables"


def test_job_entries_returns_empty(target):
    doc = {"pipelines": {"default": [{"step": {"name": "Build", "script": ["echo build"]}}]}}
    entries = target.job_entries(doc)
    assert entries == []


def test_job_entries_empty_doc(target):
    assert target.job_entries({}) == []


# --- Output conventions ------------------------------------------------------


def test_default_output_filename(target):
    assert target.default_output_filename() == "bitbucket-pipelines.yml"


# --- Decompile support -------------------------------------------------------


def test_script_keys(target):
    assert target.script_keys() == ["script", "after-script"]


def test_is_job_with_script_key(target):
    assert target.is_job("build", {"name": "Build", "script": ["echo hi"]}) is True


def test_is_job_without_script_key(target):
    assert target.is_job("image", {"name": "atlassian/default-image:4"}) is False


def test_is_job_non_dict(target):
    assert target.is_job("image", "atlassian/default-image:4") is False


# --- Reserved keys -----------------------------------------------------------


def test_reserved_top_level_keys(target):
    keys = target.reserved_top_level_keys()
    assert "image" in keys
    assert "options" in keys
    assert "definitions" in keys
    assert "clone" in keys


# --- Auto-detection ----------------------------------------------------------


def test_matches_filename_yml(target):
    assert target.matches_filename("bitbucket-pipelines.yml") is True


def test_matches_filename_yaml(target):
    assert target.matches_filename("bitbucket-pipelines.yaml") is True


def test_matches_filename_case_insensitive(target):
    assert target.matches_filename("Bitbucket-Pipelines.YML") is True


def test_matches_filename_other(target):
    assert target.matches_filename(".gitlab-ci.yml") is False
    assert target.matches_filename("buildspec.yml") is False
    assert target.matches_filename("config.yml") is False


def test_matches_directory_with_file(target, tmp_path):
    (tmp_path / "bitbucket-pipelines.yml").write_text("pipelines:\n  default: []\n")
    assert target.matches_directory(tmp_path) is True


def test_matches_directory_without_file(target, tmp_path):
    assert target.matches_directory(tmp_path) is False


# --- Schema / validation ----------------------------------------------------


def test_schema_url_contains_schemastore(target):
    assert "schemastore" in target.schema_url()


def test_schema_url_contains_bitbucket(target):
    assert "bitbucket" in target.schema_url()


def test_fallback_schema_path(target):
    assert target.fallback_schema_path() == "schemas/bitbucket_pipelines_schema.json"
