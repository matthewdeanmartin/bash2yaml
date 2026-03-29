"""Abstract base class for CI/CD platform target adapters.

Each target adapter knows:
1. Which YAML keys contain script lines (e.g. ``script:``, ``run:``, ``commands:``)
2. Where variables live
3. Which JSON schema to validate against
4. What the default output filename is

The compilation pipeline stays generic. A target adapter plugs in at the
"find script lines" and "validate output" stages.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ScriptSection:
    """A single scriptable section found in the YAML document.

    Attributes:
        job_name: Name of the job (or top-level key) containing the script.
        script_key: The YAML key name (e.g. "script", "before_script", "run").
        lines: The script content — a list of strings, a single string, or any
            YAML node that the compiler should process.
        parent: The dict-like node that owns ``script_key``, so callers can
            write back processed results via ``parent[script_key] = ...``.
    """

    job_name: str
    script_key: str
    lines: Any
    parent: dict


@dataclass
class VariablesSection:
    """A single variables section found in the YAML document.

    Attributes:
        scope: Human-readable scope (e.g. "global", job name, step name).
        variables: The dict-like mapping of variable names to values.
        parent: The dict-like node that owns the variables key, so callers
            can write back merged results.
        key: The key name under ``parent`` (e.g. "variables", "env").
    """

    scope: str
    variables: dict
    parent: dict
    key: str


class BaseTarget(abc.ABC):
    """Abstract base for a CI/CD platform target adapter."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier for this target (e.g. ``"gitlab"``, ``"github"``)."""

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g. ``"GitLab CI"``, ``"GitHub Actions"``)."""

    # ------------------------------------------------------------------
    # Structure introspection
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def script_key_paths(self, doc: dict) -> list[ScriptSection]:
        """Yield all scriptable sections in the parsed YAML document.

        The compiler iterates over these to inline script references.

        Args:
            doc: Parsed YAML document (a ``dict``-like ruamel node).

        Returns:
            List of :class:`ScriptSection` descriptors.
        """

    @abc.abstractmethod
    def variables_key_paths(self, doc: dict) -> list[VariablesSection]:
        """Yield all variable sections in the parsed YAML document.

        Used by the compiler to merge ``global_variables.sh`` and
        ``job_variables.sh`` into the correct YAML locations.

        Args:
            doc: Parsed YAML document.

        Returns:
            List of :class:`VariablesSection` descriptors.
        """

    # ------------------------------------------------------------------
    # Variable / job key names
    # ------------------------------------------------------------------

    def variables_key_name(self) -> str:
        """Return the YAML key name used for variables (e.g. ``"variables"``, ``"env"``)."""
        return "variables"

    def job_entries(self, doc: dict) -> list[tuple[str, dict]]:
        """Return a list of ``(job_name, job_data)`` pairs from the document.

        Override for platforms where jobs aren't top-level keys (e.g. GitHub's
        ``jobs:`` container).  The default implementation returns all top-level
        dict entries that aren't reserved keys.
        """
        reserved = self.reserved_top_level_keys()
        return [(k, v) for k, v in doc.items() if k not in reserved and isinstance(v, dict)]

    # ------------------------------------------------------------------
    # Output conventions
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def default_output_filename(self) -> str:
        """Return the conventional output filename for this platform.

        Examples: ``".gitlab-ci.yml"``, ``"buildspec.yml"``.
        """

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def schema_url(self) -> str | None:
        """Return the URL to fetch the JSON schema for this platform.

        Return ``None`` if no remote schema is available.
        """

    @abc.abstractmethod
    def fallback_schema_path(self) -> str | None:
        """Return the package-relative path to a bundled fallback schema.

        Return ``None`` if no bundled schema is shipped.
        """

    @abc.abstractmethod
    def validate(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate compiled YAML against this platform's schema.

        Args:
            yaml_content: The full YAML text to validate.

        Returns:
            Tuple of ``(is_valid, list_of_error_messages)``.
        """

    # ------------------------------------------------------------------
    # Decompile support
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def script_keys(self) -> list[str]:
        """Return the YAML key names that hold script content in a job.

        Used by the decompiler to know which keys to extract.
        For GitLab: ``["script", "before_script", "after_script", "pre_get_sources_script"]``.
        """

    @abc.abstractmethod
    def is_job(self, key: str, value: Any) -> bool:
        """Return True if the top-level ``(key, value)`` pair represents a CI job.

        Used to distinguish jobs from metadata keys like ``stages:``, ``include:``, etc.
        """

    # ------------------------------------------------------------------
    # Reserved / non-job top-level keys
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def reserved_top_level_keys(self) -> set[str]:
        """Return top-level YAML keys that are NOT jobs.

        Used by the compiler to skip keys like ``stages``, ``variables``,
        ``include``, etc.
        """

    # ------------------------------------------------------------------
    # Optional: auto-detection helpers
    # ------------------------------------------------------------------

    def matches_filename(self, filename: str) -> bool:
        """Return True if ``filename`` is a conventional name for this target.

        Used for auto-detection when ``--target`` is not specified.
        The default implementation returns ``False``.
        """
        # Keep extension-point parameter names stable; pluggy-style integrations
        # match provided arguments by name rather than position.
        _ = filename
        return False

    def matches_directory(self, path: Path) -> bool:
        """Return True if the directory structure matches this target.

        Used for auto-detection. The default implementation returns ``False``.
        """
        # Keep extension-point parameter names stable; pluggy-style integrations
        # match provided arguments by name rather than position.
        _ = path
        return False
