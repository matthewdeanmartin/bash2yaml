"""GitLab CI target adapter.

Extracts the existing GitLab-specific logic from compile_all, decompile_all,
and validate_pipeline into a single target adapter.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bash2yaml.targets.base import BaseTarget, ScriptSection, VariablesSection

logger = logging.getLogger(__name__)

# Keys that hold scripts inside a GitLab CI job definition.
GITLAB_SCRIPT_KEYS = ["script", "before_script", "after_script", "pre_get_sources_script"]

# Top-level YAML keys that are NOT jobs — the compiler must skip these.
GITLAB_RESERVED_KEYS: set[str] = {
    "stages",
    "variables",
    "include",
    "rules",
    "image",
    "services",
    "cache",
    "true",
    "false",
    "nil",
    "workflow",
    "default",
    "pages",
}


class GitLabTarget(BaseTarget):
    """Target adapter for GitLab CI (``.gitlab-ci.yml``)."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "gitlab"

    @property
    def display_name(self) -> str:
        return "GitLab CI"

    # ------------------------------------------------------------------
    # Structure introspection
    # ------------------------------------------------------------------

    def script_key_paths(self, doc: dict) -> list[ScriptSection]:
        """Find all scriptable sections in a GitLab CI YAML document.

        Handles:
        - Top-level ``before_script`` / ``after_script`` (deprecated but supported)
        - Per-job ``script``, ``before_script``, ``after_script``, ``pre_get_sources_script``
        - ``hooks.pre_get_sources_script`` inside jobs
        - ``run[].script`` inside jobs
        - Top-level lists (commonly used as YAML anchor script templates)
        """
        sections: list[ScriptSection] = []

        for key, value in doc.items():
            # Top-level before_script / after_script (deprecated)
            if key in ("before_script", "after_script") and not isinstance(value, dict):
                sections.append(
                    ScriptSection(
                        job_name="(top-level)",
                        script_key=key,
                        lines=value,
                        parent=doc,
                    )
                )
                continue

            if key in self.reserved_top_level_keys():
                continue

            # Skip tagged/anchored nodes unless pragma:must-inline
            if hasattr(value, "tag") and value.tag.value:
                continue
            if hasattr(value, "anchor") and value.anchor.value:
                if not self._has_must_inline_pragma(value):
                    continue

            # Top-level list (anchor script template)
            if isinstance(value, list):
                sections.append(
                    ScriptSection(
                        job_name=key,
                        script_key=key,
                        lines=value,
                        parent=doc,
                    )
                )
                continue

            if not isinstance(value, dict):
                continue

            # Regular job dict — look for script keys
            for sk in GITLAB_SCRIPT_KEYS:
                if sk in value:
                    sections.append(
                        ScriptSection(
                            job_name=key,
                            script_key=sk,
                            lines=value[sk],
                            parent=value,
                        )
                    )

            # hooks.pre_get_sources_script
            if "hooks" in value and isinstance(value["hooks"], dict):
                hooks = value["hooks"]
                if "pre_get_sources_script" in hooks:
                    sections.append(
                        ScriptSection(
                            job_name=key,
                            script_key="pre_get_sources_script",
                            lines=hooks["pre_get_sources_script"],
                            parent=hooks,
                        )
                    )

            # run[].script
            if "run" in value and isinstance(value["run"], list):
                for idx, item in enumerate(value["run"]):
                    if isinstance(item, dict) and "script" in item:
                        sections.append(
                            ScriptSection(
                                job_name=f"{key}/run[{idx}]",
                                script_key="script",
                                lines=item["script"],
                                parent=item,
                            )
                        )

        return sections

    def variables_key_paths(self, doc: dict) -> list[VariablesSection]:
        """Find all variable sections in a GitLab CI YAML document.

        Returns global ``variables:`` and per-job ``variables:`` sections.
        """
        sections: list[VariablesSection] = []

        # Global variables
        if "variables" in doc and isinstance(doc["variables"], dict):
            sections.append(
                VariablesSection(
                    scope="global",
                    variables=doc["variables"],
                    parent=doc,
                    key="variables",
                )
            )

        # Per-job variables
        for key, value in doc.items():
            if key in self.reserved_top_level_keys():
                continue
            if isinstance(value, dict) and "variables" in value and isinstance(value["variables"], dict):
                sections.append(
                    VariablesSection(
                        scope=key,
                        variables=value["variables"],
                        parent=value,
                        key="variables",
                    )
                )

        return sections

    # ------------------------------------------------------------------
    # Output conventions
    # ------------------------------------------------------------------

    def default_output_filename(self) -> str:
        return ".gitlab-ci.yml"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def schema_url(self) -> str | None:
        return "https://gitlab.com/gitlab-org/gitlab/-/raw/master/app/assets/javascripts/editor/schema/ci.json"

    def fallback_schema_path(self) -> str | None:
        return "schemas/gitlab_ci_schema.json"

    def validate(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate using the existing GitLabCIValidator."""
        from bash2yaml.utils.validate_pipeline import GitLabCIValidator

        validator = GitLabCIValidator()
        return validator.validate_ci_config(yaml_content)

    # ------------------------------------------------------------------
    # Decompile support
    # ------------------------------------------------------------------

    def script_keys(self) -> list[str]:
        return list(GITLAB_SCRIPT_KEYS)

    def is_job(self, key: str, value: Any) -> bool:
        """A GitLab job is a dict with a ``script`` key (or related keys)."""
        if key in self.reserved_top_level_keys():
            return False
        if not isinstance(value, dict):
            return False
        return any(sk in value for sk in GITLAB_SCRIPT_KEYS)

    # ------------------------------------------------------------------
    # Reserved keys
    # ------------------------------------------------------------------

    def reserved_top_level_keys(self) -> set[str]:
        return GITLAB_RESERVED_KEYS

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    def matches_filename(self, filename: str) -> bool:
        lower = filename.lower()
        return lower == ".gitlab-ci.yml" or lower == ".gitlab-ci.yaml"

    def matches_directory(self, path: Path) -> bool:
        """GitLab CI uses a single file, not a directory convention."""
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_must_inline_pragma(job_data: Any) -> bool:
        """Check if job data contains ``pragma:must-inline`` comment directive."""
        if isinstance(job_data, list):
            for item_id, _item in enumerate(job_data):
                if hasattr(job_data, "ca"):
                    comment = job_data.ca.items.get(item_id)
                    if comment:
                        comment_value = comment[0].value
                        if "pragma" in comment_value.lower() and "must-inline" in comment_value.lower():
                            return True
            for item in job_data:
                if isinstance(item, str) and "pragma" in item.lower() and "must-inline" in item.lower():
                    return True
        if isinstance(job_data, str):
            if "pragma" in job_data.lower() and "must-inline" in job_data.lower():
                return True
        elif isinstance(job_data, dict):
            for _key, value in job_data.items():
                if "pragma" in str(value).lower() and "must-inline" in str(value).lower():
                    return True
        return False
