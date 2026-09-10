"""Shared path policy for compiler inputs."""

from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath

from bash2yaml.errors.exceptions import Bash2YamlError
from bash2yaml.utils.state_store import find_repo_root


class SourceSecurityError(Bash2YamlError):
    """An input resolves outside its allowed source tree."""


def _canonical_namespace(path: Path) -> Path:
    """Compare Windows extended and ordinary paths in the same namespace."""
    text = str(path)
    if os.name == "nt" and text.startswith("\\\\?\\"):
        if text[4:8].upper() == "UNC\\":
            return Path("\\\\" + text[8:])
        if len(text) >= 7 and text[5:7] == ":\\":
            return Path(text[4:])
    return path


def source_root(scripts_root: Path) -> Path:
    """Use the enclosing repository, or the supplied source directory outside Git."""
    root = scripts_root.resolve()
    return find_repo_root(root) or root


def resolve_source(base: Path, value: str | Path, allowed_root: Path, *, bypass: bool = False) -> Path:
    """Preserve path meaning, resolve symlinks, and enforce the allowed boundary."""
    text = str(_canonical_namespace(Path(str(value).strip().strip('"').strip("'"))))
    windows = PureWindowsPath(text)
    if windows.drive and (os.name != "nt" or not windows.is_absolute()):
        raise SourceSecurityError(f"Unsupported drive-qualified source path: {text}")
    root = _canonical_namespace(allowed_root.resolve())
    enforce = not bypass and not os.environ.get("BASH2YAML_SKIP_ROOT_CHECKS")
    unresolved = base / text.replace("\\", "/")
    # abspath collapses '..' without contacting a foreign drive or UNC server.
    lexical = _canonical_namespace(Path(os.path.abspath(unresolved)))
    lexical_root = _canonical_namespace(Path(os.path.abspath(allowed_root)))
    if enforce and not (lexical.is_relative_to(lexical_root) or lexical.is_relative_to(root)):
        raise SourceSecurityError(f"Refusing to read '{value}': escapes allowed root '{root}'.")
    # Windows may retain the extended prefix if a parent appears during resolve.
    candidate = _canonical_namespace(unresolved.resolve())
    if enforce and not candidate.is_relative_to(root):
        raise SourceSecurityError(f"Refusing to read '{value}': escapes allowed root '{root}'.")
    return candidate
