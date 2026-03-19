"""Target registry for CI/CD platform adapters.

Provides:
- :func:`get_target` — look up a target by name
- :func:`detect_target` — auto-detect target from filename / directory
- :func:`list_targets` — list all registered target names
- :func:`register_target` — register a third-party target adapter
"""

from __future__ import annotations

import logging
from pathlib import Path

from bash2yaml.targets.base import BaseTarget

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: dict[str, BaseTarget] = {}


def _ensure_builtins() -> None:
    """Lazily register built-in targets on first access."""
    if _registry:
        return
    from bash2yaml.targets.bitbucket import BitbucketTarget
    from bash2yaml.targets.buildspec import BuildspecTarget
    from bash2yaml.targets.circleci import CircleCITarget
    from bash2yaml.targets.github import GitHubTarget
    from bash2yaml.targets.gitlab import GitLabTarget
    from bash2yaml.targets.semaphore import SemaphoreTarget

    for cls in (GitLabTarget, GitHubTarget, CircleCITarget, BuildspecTarget, BitbucketTarget, SemaphoreTarget):
        _instance = cls()
        _registry[_instance.name] = _instance


def register_target(target: BaseTarget) -> None:
    """Register a target adapter (built-in or third-party plugin).

    If a target with the same ``name`` already exists it is replaced.
    """
    _registry[target.name] = target
    logger.debug("Registered target: %s (%s)", target.name, target.display_name)


def get_target(name: str) -> BaseTarget:
    """Return the target adapter for *name*.

    Raises:
        ValueError: If no target with that name is registered.
    """
    _ensure_builtins()
    target = _registry.get(name)
    if target is None:
        available = ", ".join(sorted(_registry))
        raise ValueError(f"Unknown target '{name}'. Available targets: {available}")
    return target


def list_targets() -> list[str]:
    """Return sorted list of all registered target names."""
    _ensure_builtins()
    return sorted(_registry)


def detect_target(filename: str | None = None, directory: Path | None = None) -> BaseTarget | None:
    """Auto-detect the target from a filename or directory structure.

    Args:
        filename: The input YAML filename (e.g. ``.gitlab-ci.yml``).
        directory: The input directory to inspect.

    Returns:
        The matching :class:`BaseTarget`, or ``None`` if detection is ambiguous
        or no match is found.
    """
    _ensure_builtins()
    matches: list[BaseTarget] = []

    for target in _registry.values():
        if filename and target.matches_filename(filename):
            matches.append(target)
        if directory and target.matches_directory(directory):
            matches.append(target)

    if len(matches) == 1:
        logger.info("Auto-detected target: %s", matches[0].display_name)
        return matches[0]

    if len(matches) > 1:
        names = ", ".join(t.name for t in matches)
        logger.warning("Ambiguous target detection (matched: %s). Use --target to specify.", names)

    return None


def resolve_target(
    cli_target: str | None = None,
    config_target: str | None = None,
    filename: str | None = None,
    directory: Path | None = None,
) -> BaseTarget:
    """Resolve the target from CLI flag, config, or auto-detection.

    Priority: CLI flag > config key > auto-detection > default (gitlab).

    Args:
        cli_target: Value of ``--target`` CLI flag.
        config_target: Value of ``target`` config key.
        filename: Input filename for auto-detection.
        directory: Input directory for auto-detection.

    Returns:
        The resolved :class:`BaseTarget`.

    Raises:
        ValueError: If an explicitly specified target name is unknown.
    """
    # Explicit target name (CLI or config)
    explicit = cli_target or config_target
    if explicit:
        return get_target(explicit)

    # Auto-detection
    detected = detect_target(filename=filename, directory=directory)
    if detected is not None:
        return detected

    # Default to gitlab (preserves existing behaviour)
    logger.debug("No target detected; defaulting to gitlab.")
    return get_target("gitlab")
