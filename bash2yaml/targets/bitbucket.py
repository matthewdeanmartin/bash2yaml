"""Bitbucket Pipelines target adapter.

Handles the structural differences between Bitbucket Pipelines and GitLab CI:
- Config lives at ``bitbucket-pipelines.yml``
- Scripts live in ``pipelines.<trigger>`` sections
- ``default`` is a list of step-groups directly
- ``branches``, ``tags``, ``pull-requests``, ``custom`` are dicts mapping
  pattern/name → list of step-groups
- Each step has ``script: [...]`` and optionally ``after-script: [...]``
- Parallel entries contain a list of steps
- No YAML-level variable merging (Bitbucket ``variables:`` is for manual triggers only)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bash2yaml.targets.base import BaseTarget, ScriptSection, VariablesSection

logger = logging.getLogger(__name__)

# Bitbucket Pipelines reserved top-level keys (not pipeline sections).
BITBUCKET_RESERVED_KEYS: set[str] = {
    "image",
    "options",
    "definitions",
    "clone",
}

# Trigger keys that map pattern/name → list of step-groups (dict-style).
_DICT_TRIGGERS = ("branches", "tags", "pull-requests", "custom")


def _sections_from_step(
    step_data: dict,
    job_name: str,
) -> list[ScriptSection]:
    """Extract ScriptSection entries from a single step dict."""
    sections: list[ScriptSection] = []

    if "script" not in step_data:
        return sections

    sections.append(
        ScriptSection(
            job_name=job_name,
            script_key="script",
            lines=step_data["script"],
            parent=step_data,
        )
    )

    if "after-script" in step_data and isinstance(step_data["after-script"], list):
        sections.append(
            ScriptSection(
                job_name=job_name,
                script_key="after-script",
                lines=step_data["after-script"],
                parent=step_data,
            )
        )

    return sections


def _sections_from_step_group(
    entry: Any,
    prefix: str,
    step_idx: int,
) -> list[ScriptSection]:
    """Extract ScriptSection entries from a step-group entry.

    A step-group entry is either:
    - ``{"step": {...}}``
    - ``{"parallel": [{"step": {...}}, ...]}``
    """
    sections: list[ScriptSection] = []

    if not isinstance(entry, dict):
        return sections

    if "step" in entry:
        step_data = entry["step"]
        if not isinstance(step_data, dict):
            return sections
        step_name = step_data.get("name", f"step[{step_idx}]")
        job_name = f"{prefix}/{step_name}"
        sections.extend(_sections_from_step(step_data, job_name))

    elif "parallel" in entry:
        parallel_list = entry["parallel"]
        if not isinstance(parallel_list, list):
            return sections
        parallel_prefix = f"{prefix}/parallel[{step_idx}]"
        for p_idx, p_entry in enumerate(parallel_list):
            if not isinstance(p_entry, dict) or "step" not in p_entry:
                continue
            step_data = p_entry["step"]
            if not isinstance(step_data, dict):
                continue
            step_name = step_data.get("name", f"step[{p_idx}]")
            job_name = f"{parallel_prefix}/{step_name}"
            sections.extend(_sections_from_step(step_data, job_name))

    return sections


class BitbucketTarget(BaseTarget):
    """Target adapter for Bitbucket Pipelines (``bitbucket-pipelines.yml``)."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "bitbucket"

    @property
    def display_name(self) -> str:
        return "Bitbucket Pipelines"

    # ------------------------------------------------------------------
    # Structure introspection
    # ------------------------------------------------------------------

    def script_key_paths(self, doc: dict) -> list[ScriptSection]:
        """Find all scriptable sections in a Bitbucket Pipelines config.

        Traverses ``pipelines.default`` (list) and
        ``pipelines.branches/tags/pull-requests/custom`` (dicts).
        Extracts ``script`` and ``after-script`` from each step.
        """
        sections: list[ScriptSection] = []

        pipelines = doc.get("pipelines")
        if not isinstance(pipelines, dict):
            return sections

        # --- default: list of step-groups ---
        default_list = pipelines.get("default")
        if isinstance(default_list, list):
            prefix = "pipelines/default"
            for idx, entry in enumerate(default_list):
                sections.extend(_sections_from_step_group(entry, prefix, idx))

        # --- branches, tags, pull-requests, custom: dict of pattern → list ---
        for trigger in _DICT_TRIGGERS:
            trigger_dict = pipelines.get(trigger)
            if not isinstance(trigger_dict, dict):
                continue
            for pattern, step_group_list in trigger_dict.items():
                if not isinstance(step_group_list, list):
                    continue
                prefix = f"pipelines/{trigger}/{pattern}"
                for idx, entry in enumerate(step_group_list):
                    sections.extend(_sections_from_step_group(entry, prefix, idx))

        return sections

    def variables_key_paths(self, doc: dict) -> list[VariablesSection]:
        """Bitbucket ``variables:`` is only for manual trigger inputs — skip."""
        return []

    # ------------------------------------------------------------------
    # Variable / job key names
    # ------------------------------------------------------------------

    def variables_key_name(self) -> str:
        return "variables"

    def job_entries(self, doc: dict) -> list[tuple[str, dict]]:
        """Bitbucket's structure doesn't map to simple job entries."""
        return []

    # ------------------------------------------------------------------
    # Output conventions
    # ------------------------------------------------------------------

    def default_output_filename(self) -> str:
        return "bitbucket-pipelines.yml"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def schema_url(self) -> str | None:
        return "https://json.schemastore.org/bitbucket-pipelines.json"

    def fallback_schema_path(self) -> str | None:
        return "schemas/bitbucket_pipelines_schema.json"

    def validate(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate using JSON schema from SchemaStore."""
        from bash2yaml.utils.validate_pipeline_bitbucket import BitbucketValidator

        validator = BitbucketValidator()
        return validator.validate_pipeline(yaml_content)

    # ------------------------------------------------------------------
    # Decompile support
    # ------------------------------------------------------------------

    def script_keys(self) -> list[str]:
        return ["script", "after-script"]

    def is_job(self, key: str, value: Any) -> bool:
        """In Bitbucket Pipelines, a "job" is a step dict with a ``script`` key."""
        return isinstance(value, dict) and "script" in value

    # ------------------------------------------------------------------
    # Reserved keys
    # ------------------------------------------------------------------

    def reserved_top_level_keys(self) -> set[str]:
        return BITBUCKET_RESERVED_KEYS

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    def matches_filename(self, filename: str) -> bool:
        """Detect ``bitbucket-pipelines.yml`` or ``bitbucket-pipelines.yaml``."""
        return filename.lower() in ("bitbucket-pipelines.yml", "bitbucket-pipelines.yaml")

    def matches_directory(self, path: Path) -> bool:
        """Detect a directory containing ``bitbucket-pipelines.yml``."""
        path = Path(path)
        return (path / "bitbucket-pipelines.yml").exists()
