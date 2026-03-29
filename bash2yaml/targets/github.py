"""GitHub Actions target adapter.

Handles the structural differences between GitHub Actions and GitLab CI:
- Scripts live in ``steps[].run:`` as multiline string blocks
- Variables use ``env:`` at workflow, job, and step levels
- ``uses:`` steps are reusable actions — left untouched
- No ``before_script`` / ``after_script`` — modeled as separate steps
- Multiple workflow files live in ``.github/workflows/``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bash2yaml.targets.base import BaseTarget, ScriptSection, VariablesSection

logger = logging.getLogger(__name__)

# GitHub Actions reserved top-level keys (not jobs).
GITHUB_RESERVED_KEYS: set[str] = {
    "name",
    "on",
    "true",
    "false",
    "permissions",
    "env",
    "defaults",
    "concurrency",
    "run-name",
}


class GitHubTarget(BaseTarget):
    """Target adapter for GitHub Actions (``.github/workflows/*.yml``)."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "github"

    @property
    def display_name(self) -> str:
        return "GitHub Actions"

    # ------------------------------------------------------------------
    # Structure introspection
    # ------------------------------------------------------------------

    def script_key_paths(self, doc: dict) -> list[ScriptSection]:
        """Find all scriptable sections in a GitHub Actions workflow.

        Discovers ``run:`` keys inside ``jobs.<job>.steps[]``.
        Steps with ``uses:`` are skipped (reusable actions, not scripts).
        """
        sections: list[ScriptSection] = []

        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            return sections

        for job_name, job_data in jobs.items():
            if not isinstance(job_data, dict):
                continue

            steps = job_data.get("steps")
            if not isinstance(steps, list):
                continue

            for idx, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue

                # Skip reusable action steps — they have ``uses:`` instead of ``run:``
                if "uses" in step:
                    continue

                if "run" in step:
                    step_name = step.get("name", f"step[{idx}]")
                    sections.append(
                        ScriptSection(
                            job_name=f"{job_name}/{step_name}",
                            script_key="run",
                            lines=step["run"],
                            parent=step,
                        )
                    )

        return sections

    def variables_key_paths(self, doc: dict) -> list[VariablesSection]:
        """Find all variable (``env:``) sections in a GitHub Actions workflow.

        Returns workflow-level, job-level, and step-level ``env:`` sections.
        """
        sections: list[VariablesSection] = []

        # Workflow-level env
        if "env" in doc and isinstance(doc["env"], dict):
            sections.append(
                VariablesSection(
                    scope="global",
                    variables=doc["env"],
                    parent=doc,
                    key="env",
                )
            )

        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            return sections

        for job_name, job_data in jobs.items():
            if not isinstance(job_data, dict):
                continue

            # Job-level env
            if "env" in job_data and isinstance(job_data["env"], dict):
                sections.append(
                    VariablesSection(
                        scope=job_name,
                        variables=job_data["env"],
                        parent=job_data,
                        key="env",
                    )
                )

            # Step-level env
            steps = job_data.get("steps")
            if not isinstance(steps, list):
                continue

            for idx, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                if "env" in step and isinstance(step["env"], dict):
                    step_name = step.get("name", f"step[{idx}]")
                    sections.append(
                        VariablesSection(
                            scope=f"{job_name}/{step_name}",
                            variables=step["env"],
                            parent=step,
                            key="env",
                        )
                    )

        return sections

    # ------------------------------------------------------------------
    # Variable / job key names
    # ------------------------------------------------------------------

    def variables_key_name(self) -> str:
        return "env"

    def job_entries(self, doc: dict) -> list[tuple[str, dict]]:
        """GitHub jobs live under the ``jobs:`` key, not at the top level."""
        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            return []
        return [(k, v) for k, v in jobs.items() if isinstance(v, dict)]

    # ------------------------------------------------------------------
    # Output conventions
    # ------------------------------------------------------------------

    def default_output_filename(self) -> str:
        return "workflow.yml"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def schema_url(self) -> str | None:
        return "https://json.schemastore.org/github-workflow.json"

    def fallback_schema_path(self) -> str | None:
        return "schemas/github_workflow_schema.json"

    def validate(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate using JSON schema from SchemaStore.

        GitHub Actions has no official lint API — schema validation only.
        """
        from bash2yaml.utils.validate_pipeline_github import GitHubActionsValidator

        validator = GitHubActionsValidator()
        return validator.validate_workflow(yaml_content)

    # ------------------------------------------------------------------
    # Decompile support
    # ------------------------------------------------------------------

    def script_keys(self) -> list[str]:
        return ["run"]

    def is_job(self, key: str, value: Any) -> bool:
        """In GitHub Actions, jobs live under the ``jobs:`` key.

        At top level, only the ``jobs`` key itself is relevant.
        Within ``jobs:``, each child dict is a job.
        """
        if key in self.reserved_top_level_keys():
            return False
        if not isinstance(value, dict):
            return False
        # A GitHub job has ``steps`` or ``uses`` (reusable workflow)
        return "steps" in value or "uses" in value

    # ------------------------------------------------------------------
    # Reserved keys
    # ------------------------------------------------------------------

    def reserved_top_level_keys(self) -> set[str]:
        return GITHUB_RESERVED_KEYS

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    def matches_filename(self, filename: str) -> bool:
        # GitHub workflows don't have a single canonical filename,
        # but they live in .github/workflows/
        # Keep the hook-style parameter name intact for plugin compatibility.
        _ = filename
        return False

    def matches_directory(self, path: Path) -> bool:
        """Detect ``.github/workflows/`` directory structure."""
        path = Path(path)
        # Check if path itself is .github/workflows or contains it
        if path.name == "workflows":
            parent = path.parent
            if parent.name == ".github":
                return True
        # Check if .github/workflows exists within path
        candidate = path / ".github" / "workflows"
        if candidate.is_dir():
            return True
        # Check if path is inside a .github/workflows tree
        parts = path.parts
        for i, part in enumerate(parts):
            if part == ".github" and i + 1 < len(parts) and parts[i + 1] == "workflows":
                return True
        return False
