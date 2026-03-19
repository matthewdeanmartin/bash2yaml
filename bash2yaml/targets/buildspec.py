"""AWS CodeBuild Buildspec target adapter.

Handles the structural differences between AWS CodeBuild Buildspec and GitLab CI:
- Scripts live in ``phases.<phase>.commands[]`` as arrays of strings
- Each phase can also have a ``finally.commands[]`` block
- Variables use ``env.variables`` (plaintext), ``env.parameter-store``, ``env.secrets-manager``
- No concept of "jobs" — single build context with named phases
- Standalone file: ``buildspec.yml`` (not a pipeline file per se)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bash2yaml.targets.base import BaseTarget, ScriptSection, VariablesSection

logger = logging.getLogger(__name__)

# AWS CodeBuild Buildspec reserved top-level keys (not phases).
BUILDSPEC_RESERVED_KEYS: set[str] = {
    "version",
    "env",
    "proxy",
    "batch",
    "reports",
    "artifacts",
    "cache",
}


class BuildspecTarget(BaseTarget):
    """Target adapter for AWS CodeBuild Buildspec (``buildspec.yml``)."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "buildspec"

    @property
    def display_name(self) -> str:
        return "AWS CodeBuild"

    # ------------------------------------------------------------------
    # Structure introspection
    # ------------------------------------------------------------------

    def script_key_paths(self, doc: dict) -> list[ScriptSection]:
        """Find all scriptable sections in an AWS CodeBuild Buildspec.

        Discovers ``commands:`` keys inside ``phases.<phase>`` and
        ``phases.<phase>.finally`` blocks.
        """
        sections: list[ScriptSection] = []

        phases = doc.get("phases", {})
        if not isinstance(phases, dict):
            return sections

        for phase_name, phase_data in phases.items():
            if not isinstance(phase_data, dict):
                continue

            # Main commands block
            if "commands" in phase_data and isinstance(phase_data["commands"], list):
                sections.append(
                    ScriptSection(
                        job_name=f"phases/{phase_name}",
                        script_key="commands",
                        lines=phase_data["commands"],
                        parent=phase_data,
                    )
                )

            # finally.commands block
            finally_block = phase_data.get("finally")
            if isinstance(finally_block, dict) and "commands" in finally_block:
                if isinstance(finally_block["commands"], list):
                    sections.append(
                        ScriptSection(
                            job_name=f"phases/{phase_name}/finally",
                            script_key="commands",
                            lines=finally_block["commands"],
                            parent=finally_block,
                        )
                    )

        return sections

    def variables_key_paths(self, doc: dict) -> list[VariablesSection]:
        """Find the ``env.variables`` section in an AWS CodeBuild Buildspec.

        Returns the plaintext variables dict under ``env.variables``.
        """
        sections: list[VariablesSection] = []

        env_dict = doc.get("env")
        if not isinstance(env_dict, dict):
            return sections

        env_vars = env_dict.get("variables")
        if isinstance(env_vars, dict):
            sections.append(
                VariablesSection(
                    scope="global",
                    variables=env_vars,
                    parent=env_dict,
                    key="variables",
                )
            )

        return sections

    # ------------------------------------------------------------------
    # Variable / job key names
    # ------------------------------------------------------------------

    def variables_key_name(self) -> str:
        return "variables"

    def job_entries(self, doc: dict) -> list[tuple[str, dict]]:
        """Return phases as if they were jobs, prefixed with ``phases/``."""
        phases = doc.get("phases", {})
        if not isinstance(phases, dict):
            return []
        return [(f"phases/{name}", data) for name, data in phases.items() if isinstance(data, dict)]

    # ------------------------------------------------------------------
    # Output conventions
    # ------------------------------------------------------------------

    def default_output_filename(self) -> str:
        return "buildspec.yml"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def schema_url(self) -> str | None:
        return "https://json.schemastore.org/buildspec.json"

    def fallback_schema_path(self) -> str | None:
        return "schemas/buildspec_schema.json"

    def validate(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate using JSON schema from SchemaStore.

        AWS CodeBuild has no official lint API — schema validation only.
        """
        from bash2yaml.utils.validate_pipeline_buildspec import BuildspecValidator

        validator = BuildspecValidator()
        return validator.validate_buildspec(yaml_content)

    # ------------------------------------------------------------------
    # Decompile support
    # ------------------------------------------------------------------

    def script_keys(self) -> list[str]:
        return ["commands"]

    def is_job(self, key: str, value: Any) -> bool:
        """In a Buildspec, a "job" is a phase entry that contains ``commands``.

        Used for decompile support — each phase with commands is treated as a job.
        """
        return isinstance(value, dict) and "commands" in value

    # ------------------------------------------------------------------
    # Reserved keys
    # ------------------------------------------------------------------

    def reserved_top_level_keys(self) -> set[str]:
        return BUILDSPEC_RESERVED_KEYS

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    def matches_filename(self, filename: str) -> bool:
        """Detect ``buildspec.yml`` or ``buildspec.yaml``."""
        return filename.lower() in ("buildspec.yml", "buildspec.yaml")

    def matches_directory(self, path: Path) -> bool:
        """Detect a directory containing ``buildspec.yml``."""
        path = Path(path)
        return (path / "buildspec.yml").exists()
