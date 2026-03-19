"""Tests for GitHub Actions validator."""

from __future__ import annotations

import pytest

from bash2yaml.targets.github import GitHubTarget


@pytest.fixture
def target():
    return GitHubTarget()


def test_validate_valid_workflow(target):
    yaml_content = """\
name: Test
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build
        run: echo hello
"""
    is_valid, errors = target.validate(yaml_content)
    assert is_valid is True
    assert errors == []


def test_validate_pragma_skips_validation(target):
    yaml_content = """\
# Pragma: do-not-validate-schema
name: Test
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hello
      - bad_key: should_not_matter
"""
    is_valid, errors = target.validate(yaml_content)
    assert is_valid is True


def test_validate_invalid_yaml(target):
    yaml_content = ":::not yaml at all:::"
    is_valid, errors = target.validate(yaml_content)
    assert is_valid is False
    assert len(errors) > 0


def test_validate_missing_required_keys(target):
    yaml_content = """\
name: Missing Jobs
"""
    is_valid, errors = target.validate(yaml_content)
    assert is_valid is False
    assert any("required" in e.lower() or "on" in e.lower() or "jobs" in e.lower() for e in errors)
