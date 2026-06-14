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
import shutil
import subprocess  # nosec
import sys
from pathlib import Path
from typing import Any

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

    - ``hashes.json``  — map of repo-relative path -> sha256 of last written content
    - ``sources.json`` — map of repo-relative YAML path -> source info (uncompiled
      YAML path relative to the state dir, extracted scripts, adoption metadata)
    - ``config.toml``  — equivalent of ``.bash2yaml.toml`` (optional, user-managed)
    - ``sources/``     — the uncompiled YAML + extracted ``.sh`` files
    """

    HASHES_FILE = "hashes.json"
    SOURCES_FILE = "sources.json"
    CONFIG_FILE = "config.toml"
    SOURCES_DIR = "sources"

    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self._hashes: dict[str, str] | None = None
        self._sources: dict[str, Any] | None = None

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

    # --- json plumbing ---------------------------------------------------------

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not read state file %s: %s. Treating as empty.", path, e)
            return {}

    @staticmethod
    def _save_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # --- hashes ----------------------------------------------------------------

    @property
    def hashes(self) -> dict[str, str]:
        if self._hashes is None:
            self._hashes = self._load_json(self.hashes_path)
        return self._hashes

    def get_hash(self, relpath: str) -> str | None:
        return self.hashes.get(self._normalize(relpath))

    def record_hash(self, relpath: str, content: str) -> None:
        self.hashes[self._normalize(relpath)] = sha256_text(content)

    def content_matches(self, relpath: str, content: str) -> bool | None:
        """True/False if a record exists, None when this path was never recorded."""
        recorded = self.get_hash(relpath)
        if recorded is None:
            return None
        return recorded == sha256_text(content)

    def save_hashes(self) -> None:
        if self._hashes is not None:
            self._save_json(self.hashes_path, self._hashes)

    # --- sources ---------------------------------------------------------------

    @property
    def sources(self) -> dict[str, Any]:
        if self._sources is None:
            self._sources = self._load_json(self.sources_path)
        return self._sources

    def record_source(self, yaml_relpath: str, info: dict[str, Any]) -> None:
        self.sources[self._normalize(yaml_relpath)] = info

    def save_sources(self) -> None:
        if self._sources is not None:
            self._save_json(self.sources_path, self._sources)

    def save(self) -> None:
        self.save_hashes()
        self.save_sources()

    # --- lifecycle ---------------------------------------------------------------

    def shred(self) -> bool:
        """Remove the entire state directory. Returns True when something was removed."""
        if not self.state_dir.exists():
            return False
        shutil.rmtree(self.state_dir)
        self._hashes = None
        self._sources = None
        return True

    @staticmethod
    def _normalize(relpath: str) -> str:
        """Keys are posix-style relative paths so state files are portable."""
        return str(relpath).replace("\\", "/")
