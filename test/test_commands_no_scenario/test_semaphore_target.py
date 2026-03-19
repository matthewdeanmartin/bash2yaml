"""Unit tests for the SemaphoreTarget adapter."""

from __future__ import annotations


import pytest

from bash2yaml.targets.semaphore import SemaphoreTarget


@pytest.fixture
def target():
    return SemaphoreTarget()


# --- Identity ----------------------------------------------------------------


def test_name(target):
    assert target.name == "semaphore"


def test_display_name(target):
    assert target.display_name == "Semaphore CI"


# --- script_key_paths --------------------------------------------------------


def test_script_key_paths_basic_job_commands(target):
    """Basic block with a job that has commands is discovered."""
    doc = {
        "blocks": [
            {
                "name": "Build",
                "task": {
                    "jobs": [
                        {
                            "name": "Build App",
                            "commands": ["./scripts/build.sh"],
                        }
                    ]
                },
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "Build/Build App"
    assert sections[0].script_key == "commands"
    assert sections[0].lines == ["./scripts/build.sh"]


def test_script_key_paths_prologue_commands(target):
    """Prologue commands in a task are discovered."""
    doc = {
        "blocks": [
            {
                "name": "Build",
                "task": {
                    "prologue": {
                        "commands": ["./scripts/setup.sh"],
                    },
                    "jobs": [],
                },
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "Build/prologue"
    assert sections[0].script_key == "commands"
    assert sections[0].lines == ["./scripts/setup.sh"]


def test_script_key_paths_epilogue_always(target):
    """Epilogue always commands are discovered."""
    doc = {
        "blocks": [
            {
                "name": "Test",
                "task": {
                    "jobs": [],
                    "epilogue": {
                        "always": {"commands": ["./scripts/cleanup.sh"]},
                    },
                },
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "Test/epilogue/always"
    assert sections[0].lines == ["./scripts/cleanup.sh"]


def test_script_key_paths_epilogue_on_pass(target):
    """Epilogue on_pass commands are discovered."""
    doc = {
        "blocks": [
            {
                "name": "Test",
                "task": {
                    "jobs": [],
                    "epilogue": {
                        "on_pass": {"commands": ["./scripts/notify_success.sh"]},
                    },
                },
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "Test/epilogue/on_pass"
    assert sections[0].lines == ["./scripts/notify_success.sh"]


def test_script_key_paths_epilogue_on_fail(target):
    """Epilogue on_fail commands are discovered."""
    doc = {
        "blocks": [
            {
                "name": "Test",
                "task": {
                    "jobs": [],
                    "epilogue": {
                        "on_fail": {"commands": ["./scripts/notify_failure.sh"]},
                    },
                },
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "Test/epilogue/on_fail"
    assert sections[0].lines == ["./scripts/notify_failure.sh"]


def test_script_key_paths_multiple_blocks_and_jobs(target):
    """Multiple blocks and multiple jobs all produce sections."""
    doc = {
        "blocks": [
            {
                "name": "Build",
                "task": {
                    "jobs": [
                        {"name": "Build App", "commands": ["./scripts/build.sh"]},
                        {"name": "Build Docs", "commands": ["./scripts/build_docs.sh"]},
                    ]
                },
            },
            {
                "name": "Test",
                "task": {
                    "jobs": [
                        {"name": "Unit Tests", "commands": ["./scripts/test.sh"]},
                    ]
                },
            },
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 3
    job_names = {s.job_name for s in sections}
    assert "Build/Build App" in job_names
    assert "Build/Build Docs" in job_names
    assert "Test/Unit Tests" in job_names


def test_script_key_paths_empty_blocks(target):
    """Document with no blocks returns no sections."""
    doc = {"version": "v1.0", "name": "CI"}
    sections = target.script_key_paths(doc)
    assert sections == []


def test_script_key_paths_empty_blocks_list(target):
    """Document with empty blocks list returns no sections."""
    doc = {"blocks": []}
    sections = target.script_key_paths(doc)
    assert sections == []


def test_script_key_paths_skips_jobs_without_commands(target):
    """Jobs that lack a ``commands`` key are skipped."""
    doc = {
        "blocks": [
            {
                "name": "Build",
                "task": {
                    "jobs": [
                        {"name": "No commands here"},
                    ]
                },
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert sections == []


def test_script_key_paths_block_without_name_uses_index(target):
    """Block without a name uses block[idx] as the prefix."""
    doc = {
        "blocks": [
            {
                "task": {
                    "jobs": [
                        {"name": "Build App", "commands": ["./scripts/build.sh"]},
                    ]
                }
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "block[0]/Build App"


def test_script_key_paths_job_without_name_uses_index(target):
    """Job without a name uses job[idx] as the suffix."""
    doc = {
        "blocks": [
            {
                "name": "Build",
                "task": {
                    "jobs": [
                        {"commands": ["./scripts/build.sh"]},
                    ]
                },
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].job_name == "Build/job[0]"


def test_script_key_paths_parent_is_job_dict(target):
    """The ``parent`` of the ScriptSection for a job is the job dict itself."""
    job_dict = {"name": "Build App", "commands": ["./scripts/build.sh"]}
    doc = {
        "blocks": [
            {
                "name": "Build",
                "task": {"jobs": [job_dict]},
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].parent is job_dict


def test_script_key_paths_parent_is_prologue_dict(target):
    """The ``parent`` of the ScriptSection for prologue is the prologue dict."""
    prologue_dict = {"commands": ["./scripts/setup.sh"]}
    doc = {
        "blocks": [
            {
                "name": "Build",
                "task": {"prologue": prologue_dict, "jobs": []},
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 1
    assert sections[0].parent is prologue_dict


def test_script_key_paths_all_epilogue_subsections(target):
    """All three epilogue sub-sections are discovered when present."""
    doc = {
        "blocks": [
            {
                "name": "Test",
                "task": {
                    "jobs": [],
                    "epilogue": {
                        "always": {"commands": ["./scripts/cleanup.sh"]},
                        "on_pass": {"commands": ["./scripts/notify_success.sh"]},
                        "on_fail": {"commands": ["./scripts/notify_failure.sh"]},
                    },
                },
            }
        ]
    }
    sections = target.script_key_paths(doc)
    assert len(sections) == 3
    job_names = {s.job_name for s in sections}
    assert "Test/epilogue/always" in job_names
    assert "Test/epilogue/on_pass" in job_names
    assert "Test/epilogue/on_fail" in job_names


# --- variables_key_paths -----------------------------------------------------


def test_variables_key_paths_returns_empty(target):
    """Semaphore env_vars format is object-array — always returns empty."""
    doc = {
        "blocks": [
            {
                "name": "Build",
                "task": {
                    "env_vars": [
                        {"name": "NODE_ENV", "value": "ci"},
                    ],
                    "jobs": [],
                },
            }
        ]
    }
    sections = target.variables_key_paths(doc)
    assert sections == []


def test_variables_key_paths_empty_doc(target):
    doc = {}
    sections = target.variables_key_paths(doc)
    assert sections == []


# --- variables_key_name / job_entries ----------------------------------------


def test_variables_key_name(target):
    assert target.variables_key_name() == "env_vars"


def test_job_entries_returns_empty(target):
    doc = {
        "blocks": [
            {
                "name": "Build",
                "task": {"jobs": [{"name": "Build App", "commands": ["./scripts/build.sh"]}]},
            }
        ]
    }
    entries = target.job_entries(doc)
    assert entries == []


def test_job_entries_empty_doc(target):
    assert target.job_entries({}) == []


# --- Output conventions ------------------------------------------------------


def test_default_output_filename(target):
    assert target.default_output_filename() == ".semaphore/semaphore.yml"


# --- Decompile support -------------------------------------------------------


def test_script_keys(target):
    assert target.script_keys() == ["commands"]


def test_is_job_with_commands_key(target):
    assert target.is_job("build", {"name": "Build App", "commands": ["./build.sh"]}) is True


def test_is_job_without_commands_key(target):
    assert target.is_job("env", {"name": "NODE_ENV", "value": "ci"}) is False


def test_is_job_non_dict(target):
    assert target.is_job("version", "v1.0") is False


# --- Reserved keys -----------------------------------------------------------


def test_reserved_top_level_keys(target):
    keys = target.reserved_top_level_keys()
    assert "version" in keys
    assert "name" in keys
    assert "agent" in keys
    assert "promotions" in keys


def test_reserved_top_level_keys_includes_queue_and_fail_fast(target):
    keys = target.reserved_top_level_keys()
    assert "queue" in keys
    assert "fail_fast" in keys
    assert "auto_cancel" in keys
    assert "global_job_config" in keys


# --- Auto-detection ----------------------------------------------------------


def test_matches_filename_yml(target):
    assert target.matches_filename("semaphore.yml") is True


def test_matches_filename_yaml(target):
    assert target.matches_filename("semaphore.yaml") is True


def test_matches_filename_case_insensitive(target):
    assert target.matches_filename("Semaphore.YML") is True


def test_matches_filename_other(target):
    assert target.matches_filename(".gitlab-ci.yml") is False
    assert target.matches_filename("buildspec.yml") is False
    assert target.matches_filename("config.yml") is False


def test_matches_directory_with_semaphore_subdir(target, tmp_path):
    (tmp_path / ".semaphore").mkdir()
    assert target.matches_directory(tmp_path) is True


def test_matches_directory_when_path_is_semaphore_dir(target, tmp_path):
    semaphore_dir = tmp_path / ".semaphore"
    semaphore_dir.mkdir()
    assert target.matches_directory(semaphore_dir) is True


def test_matches_directory_when_semaphore_in_path_parts(target, tmp_path):
    nested = tmp_path / ".semaphore" / "subdir"
    nested.mkdir(parents=True)
    assert target.matches_directory(nested) is True


def test_matches_directory_false_for_random_dir(target, tmp_path):
    assert target.matches_directory(tmp_path) is False


# --- Schema / validation ----------------------------------------------------


def test_schema_url_contains_semaphoreci(target):
    assert "semaphoreci" in target.schema_url()


def test_schema_url_contains_semaphore(target):
    url = target.schema_url()
    assert "semaphore" in url.lower()


def test_fallback_schema_path(target):
    assert target.fallback_schema_path() == "schemas/semaphore_schema.json"
