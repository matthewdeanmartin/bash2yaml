"""Tests for the out-of-tree state store (traceless mode, Phase 4)."""

from __future__ import annotations

from pathlib import Path

from bash2yaml.utils.state_store import (
    StateStore,
    default_state_root,
    find_repo_root,
    repo_fingerprint,
    resolve_state_dir,
    sha256_text,
)


def test_fingerprint_is_stable_and_short(tmp_path: Path):
    fp1 = repo_fingerprint(tmp_path)
    fp2 = repo_fingerprint(tmp_path)
    assert fp1 == fp2
    assert len(fp1) == 16
    assert all(c in "0123456789abcdef" for c in fp1)


def test_fingerprint_differs_per_checkout_path(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert repo_fingerprint(a) != repo_fingerprint(b)


def test_resolve_state_dir_explicit_override_wins(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BASH2YAML_STATE_DIR", str(tmp_path / "env_dir"))
    override = tmp_path / "explicit"
    assert resolve_state_dir(tmp_path, override) == override.resolve()


def test_resolve_state_dir_env_var(tmp_path: Path, monkeypatch):
    env_dir = tmp_path / "env_dir"
    monkeypatch.setenv("BASH2YAML_STATE_DIR", str(env_dir))
    assert resolve_state_dir(tmp_path) == env_dir.resolve()


def test_resolve_state_dir_default_is_fingerprinted(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("BASH2YAML_STATE_DIR", raising=False)
    result = resolve_state_dir(tmp_path)
    assert result.parent == default_state_root()
    assert result.name == repo_fingerprint(tmp_path)


def test_find_repo_root(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_repo_root(nested) == tmp_path.resolve()


def test_find_repo_root_none_when_no_git(tmp_path: Path):
    assert find_repo_root(tmp_path) is None


def test_state_store_hash_roundtrip(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    store.record_hash(".gitlab-ci.yml", "content one\n")
    store.save()

    fresh = StateStore(tmp_path / "state")
    assert fresh.get_hash(".gitlab-ci.yml") == sha256_text("content one\n")
    assert fresh.content_matches(".gitlab-ci.yml", "content one\n") is True
    assert fresh.content_matches(".gitlab-ci.yml", "tampered\n") is False
    assert fresh.content_matches("never-recorded.yml", "x") is None


def test_state_store_normalizes_path_separators(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    store.record_hash("ci\\nested\\file.yml", "abc")
    assert store.get_hash("ci/nested/file.yml") == sha256_text("abc")


def test_state_store_sources_roundtrip(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    store.record_source(".gitlab-ci.yml", {"uncompiled": "sources/.gitlab-ci.yml"})
    store.save()

    fresh = StateStore(tmp_path / "state")
    assert fresh.sources[".gitlab-ci.yml"]["uncompiled"] == "sources/.gitlab-ci.yml"


def test_state_store_shred(tmp_path: Path):
    store = StateStore(tmp_path / "state")
    store.record_hash("x.yml", "abc")
    store.save()
    assert store.exists()
    assert store.shred() is True
    assert not store.exists()
    assert store.shred() is False  # idempotent


def test_state_store_corrupt_json_treated_as_empty(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    (state / StateStore.HASHES_FILE).write_text("{not json", encoding="utf-8")
    store = StateStore(state)
    assert store.hashes == {}
