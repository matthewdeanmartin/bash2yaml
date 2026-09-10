"""Out-of-tree state storage for traceless mode.

Traceless mode keeps everything bash2yaml needs to remember (content hashes,
source mappings, config) outside the working tree, under a per-repo state
directory keyed by a repo fingerprint:

- Linux/macOS: ``$XDG_STATE_HOME/bash2yaml/<fingerprint>/``
  (``~/.local/state/bash2yaml/<fingerprint>/`` when ``XDG_STATE_HOME`` is unset)
- Windows: ``%LOCALAPPDATA%\\bash2yaml\\state\\<fingerprint>\\``

The fingerprint is ``sha256(remote.origin.url + "\\n" + abspath)`` truncated to
16 hex chars, so forks checked out to different paths do not collide.

``BASH2YAML_STATE_DIR`` (or an explicit ``--state-dir``) overrides the location
entirely.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess  # nosec
import sys
from copy import deepcopy
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, cast

from bash2yaml.errors.exceptions import ConfigInvalid
from bash2yaml.utils.atomic_io import atomic_write_text, file_lock

logger = logging.getLogger(__name__)

__all__ = [
    "StateStore",
    "default_state_root",
    "find_repo_root",
    "get_remote_url",
    "repo_fingerprint",
    "resolve_state_dir",
    "sha256_text",
]

STATE_DIR_ENV_VAR = "BASH2YAML_STATE_DIR"


def sha256_text(content: str) -> str:
    """Hex sha256 of text content (utf-8)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def find_repo_root(start: Path | None = None) -> Path | None:
    """Walk upward from *start* (default cwd) to the nearest directory containing ``.git``."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def get_remote_url(repo_root: Path) -> str | None:
    """Return ``remote.origin.url`` for the repo, or None when unavailable."""
    try:
        result = subprocess.run(  # nosec
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("Could not read remote.origin.url: %s", e)
        return None
    url = result.stdout.strip()
    return url or None


def repo_fingerprint(repo_root: Path) -> str:
    """16-hex-char fingerprint of remote URL + checkout path.

    Including the checkout path keeps two clones of the same remote (or two
    forks with the same URL after a rename) from sharing state.
    """
    remote = get_remote_url(repo_root) or ""
    basis = f"{remote}\n{repo_root.resolve()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def default_state_root() -> Path:
    """Platform-appropriate root under which per-repo state dirs live."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "bash2yaml" / "state"
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg_state) if xdg_state else Path.home() / ".local" / "state"
    return base / "bash2yaml"


def resolve_state_dir(repo_root: Path, override: str | Path | None = None) -> Path:
    """Resolve the state directory: explicit override > env var > default per-repo dir."""
    if override:
        return Path(override).resolve()
    env_override = os.environ.get(STATE_DIR_ENV_VAR)
    if env_override:
        return Path(env_override).resolve()
    return default_state_root() / repo_fingerprint(repo_root)


class StateStore:
    """JSON-backed state for one repo: content hashes, source mappings, config.

    Layout inside the state directory:

    - ``state.json`` — version 1; hashes and source mappings published atomically
    - ``hashes.json`` / ``sources.json`` — legacy input, migrated on the first save
    - ``config.toml``  — equivalent of ``.bash2yaml.toml`` (optional, user-managed)
    - ``sources/``     — the uncompiled YAML + extracted ``.sh`` files
    """

    STATE_FILE = "state.json"
    HASHES_FILE = "hashes.json"
    SOURCES_FILE = "sources.json"
    CONFIG_FILE = "config.toml"
    SOURCES_DIR = "sources"

    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self._hashes: dict[str, str] | None = None
        self._sources: dict[str, Any] | None = None
        self._hash_updates: dict[str, str] = {}
        self._source_updates: dict[str, Any] = {}

    @classmethod
    def for_repo(cls, repo_root: Path, override: str | Path | None = None) -> StateStore:
        return cls(resolve_state_dir(repo_root, override))

    # --- paths ---------------------------------------------------------------

    @property
    def hashes_path(self) -> Path:
        return self.state_dir / self.HASHES_FILE

    @property
    def sources_path(self) -> Path:
        return self.state_dir / self.SOURCES_FILE

    @property
    def config_path(self) -> Path:
        return self.state_dir / self.CONFIG_FILE

    @property
    def sources_dir(self) -> Path:
        return self.state_dir / self.SOURCES_DIR

    def exists(self) -> bool:
        return self.state_dir.is_dir()

    @property
    def state_path(self) -> Path:
        return self.state_dir / self.STATE_FILE

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConfigInvalid(f"Cannot read state file {path}; restore it from backup: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigInvalid(f"State file {path} must contain a JSON object.")
        return data

    @staticmethod
    def _validate(hashes: Any, sources: Any) -> None:
        if not isinstance(hashes, dict) or not isinstance(sources, dict):
            raise ConfigInvalid("State hashes and sources must be objects.")
        for key, digest in hashes.items():
            StateStore._normalize(key)
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ConfigInvalid(f"Invalid content hash for {key!r} in state.")
        for key, info in sources.items():
            StateStore._normalize(key)
            if not isinstance(info, dict) or not isinstance(info.get("uncompiled"), str):
                raise ConfigInvalid(f"Invalid source record for {key!r} in state.")
            path = StateStore._normalize(info["uncompiled"])
            if not path.startswith("sources/"):
                raise ConfigInvalid(f"Source record for {key!r} must be inside sources/.")
            for flag in ("rewrite_yaml", "byte_identical"):
                if flag in info and not isinstance(info[flag], bool):
                    raise ConfigInvalid(f"Invalid {flag} in source record for {key!r}.")

    def _read_state(self) -> tuple[dict[str, str], dict[str, Any]]:
        if self.state_path.exists():
            data = self._load_json(self.state_path)
            version = data.get("version")
            if not isinstance(version, int) or isinstance(version, bool) or version != 1:
                raise ConfigInvalid(f"Unsupported state format in {self.state_path}.")
            hashes, sources = data.get("hashes"), data.get("sources")
        else:
            # Read the old split format until the first successful atomic save.
            hashes = self._load_json(self.hashes_path)
            sources = self._load_json(self.sources_path)
        self._validate(hashes, sources)
        return cast(dict[str, str], hashes), cast(dict[str, Any], sources)

    @property
    def hashes(self) -> dict[str, str]:
        if self._hashes is None:
            self._hashes, self._sources = self._read_state()
        return self._hashes

    def get_hash(self, relpath: str) -> str | None:
        return self.hashes.get(self._normalize(relpath))

    def record_hash(self, relpath: str, content: str) -> None:
        key = self._normalize(relpath)
        digest = sha256_text(content)
        self.hashes[key] = digest
        self._hash_updates[key] = digest

    def content_matches(self, relpath: str, content: str) -> bool | None:
        """True/False if a record exists, None when this path was never recorded."""
        recorded = self.get_hash(relpath)
        return None if recorded is None else recorded == sha256_text(content)

    @property
    def sources(self) -> dict[str, Any]:
        if self._sources is None:
            self._hashes, self._sources = self._read_state()
        return self._sources

    def record_source(self, yaml_relpath: str, info: dict[str, Any]) -> None:
        key = self._normalize(yaml_relpath)
        self._validate({}, {key: info})
        self.sources[key] = deepcopy(info)
        self._source_updates[key] = deepcopy(info)

    def save_hashes(self) -> None:
        self._save(include_sources=False)

    def save_sources(self) -> None:
        self._save(include_hashes=False)

    def save(self) -> None:
        self._save()

    def _save(self, *, include_hashes: bool = True, include_sources: bool = True) -> None:
        with file_lock(self.state_dir / "state.lock"):
            hashes, sources = self._read_state()
            if include_hashes:
                hashes.update(self._hash_updates)
            if include_sources:
                sources.update(self._source_updates)
            self._validate(hashes, sources)
            data = {"version": 1, "hashes": hashes, "sources": sources}
            atomic_write_text(self.state_path, json.dumps(data, indent=2, sort_keys=True) + "\n")
            if include_hashes:
                self._hash_updates.clear()
            if include_sources:
                self._source_updates.clear()
            self._hashes = {**hashes, **self._hash_updates}
            self._sources = {**sources, **self._source_updates}

    # --- lifecycle ---------------------------------------------------------------

    def shred(self) -> bool:
        """Remove the entire state directory. Returns True when something was removed."""
        if not self.state_dir.exists():
            return False
        shutil.rmtree(self.state_dir)
        self._hashes = None
        self._sources = None
        self._hash_updates.clear()
        self._source_updates.clear()
        return True

    @staticmethod
    def _normalize(relpath: str) -> str:
        """Keys are posix-style relative paths so state files are portable."""
        if not isinstance(relpath, str) or not relpath:
            raise ConfigInvalid("State paths must be nonempty relative strings.")
        value = relpath.replace("\\", "/")
        path = PurePosixPath(value)
        if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts or not path.parts:
            raise ConfigInvalid(f"Invalid relative state path: {relpath!r}")
        return path.as_posix()
