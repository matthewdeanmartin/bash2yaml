"""CircleCI target adapter.

Handles the structural differences between CircleCI and GitLab CI:
- Config lives at ``.circleci/config.yml``
- Scripts live in ``jobs.<name>.steps[]`` under ``run:`` keys
- ``run:`` can be a plain string (shorthand) or a dict with ``command:`` key
- Variables use ``environment:`` at the job level
- Non-run steps (``checkout``, ``restore_cache``, etc.) are skipped
- Orb references like ``orb-name/command-name`` appear as step dicts but have no ``run:``
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bash2yaml.targets.base import BaseTarget, ScriptSection, VariablesSection

logger = logging.getLogger(__name__)

# CircleCI reserved top-level keys (not jobs).
CIRCLECI_RESERVED_KEYS: set[str] = {
    "version",
    "orbs",
    "executors",
    "commands",
    "parameters",
    "workflows",
    "setup",
}


class CircleCITarget(BaseTarget):
    """Target adapter for CircleCI (``.circleci/config.yml``)."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "circleci"

    @property
    def display_name(self) -> str:
        return "CircleCI"

    # ------------------------------------------------------------------
    # Structure introspection
    # ------------------------------------------------------------------

    def script_key_paths(self, doc: dict) -> list[ScriptSection]:
        """Find all scriptable sections in a CircleCI config.

        Discovers ``run:`` keys inside ``jobs.<job>.steps[]``.
        Steps without a ``run:`` key are skipped (e.g. ``checkout``,
        ``restore_cache``, orb commands).

        Handles two forms of ``run:``:
        - String shorthand: ``run: "command"``
        - Object form: ``run:\n  command: |`` (with optional ``name:``)
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
                # String steps (e.g. ``- checkout``) have no run key — skip.
                if not isinstance(step, dict):
                    continue

                # Only process steps that have a ``run`` key.
                if "run" not in step:
                    continue

                run_value = step["run"]

                if isinstance(run_value, str):
                    # Shorthand form: ``run: "single line command"``
                    sections.append(
                        ScriptSection(
                            job_name=f"{job_name}/step[{idx}]",
                            script_key="run",
                            lines=run_value,
                            parent=step,
                        )
                    )
                elif isinstance(run_value, dict) and "command" in run_value:
                    # Object form: ``run:\n  name: "..."\n  command: |``
                    step_name = run_value.get("name", f"step[{idx}]")
                    sections.append(
                        ScriptSection(
                            job_name=f"{job_name}/{step_name}",
                            script_key="command",
                            lines=run_value["command"],
                            parent=run_value,
                        )
                    )
                # Dicts without ``command`` (malformed or future extensions) — skip.

        return sections

    def variables_key_paths(self, doc: dict) -> list[VariablesSection]:
        """Find all variable (``environment:``) sections in a CircleCI config.

        Returns job-level ``environment:`` sections.
        Executor-level ``environment:`` sections are skipped.
        """
        sections: list[VariablesSection] = []

        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            return sections

        for job_name, job_data in jobs.items():
            if not isinstance(job_data, dict):
                continue

            if "environment" in job_data and isinstance(job_data["environment"], dict):
                sections.append(
                    VariablesSection(
                        scope=job_name,
                        variables=job_data["environment"],
                        parent=job_data,
                        key="environment",
                    )
                )

        return sections

    # ------------------------------------------------------------------
    # Variable / job key names
    # ------------------------------------------------------------------

    def variables_key_name(self) -> str:
        return "environment"

    def job_entries(self, doc: dict) -> list[tuple[str, dict]]:
        """CircleCI jobs live under the ``jobs:`` key."""
        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            return []
        return [(k, v) for k, v in jobs.items() if isinstance(v, dict)]

    # ------------------------------------------------------------------
    # Output conventions
    # ------------------------------------------------------------------

    def default_output_filename(self) -> str:
        return ".circleci/config.yml"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def schema_url(self) -> str | None:
        return "https://json.schemastore.org/circleciconfig.json"

    def fallback_schema_path(self) -> str | None:
        return "schemas/circleci_schema.json"

    def validate(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate using JSON schema from SchemaStore.

        CircleCI has no official lint API — schema validation only.
        """
        from bash2yaml.utils.validate_pipeline_circleci import CircleCIValidator

        validator = CircleCIValidator()
        return validator.validate_config(yaml_content)

    # ------------------------------------------------------------------
    # Decompile support
    # ------------------------------------------------------------------

    def script_keys(self) -> list[str]:
        return ["run"]

    def is_job(self, key: str, value: Any) -> bool:
        """In CircleCI, jobs live under the ``jobs:`` key.

        Within ``jobs:``, each child dict with a ``steps`` key is a job.
        """
        if key in self.reserved_top_level_keys():
            return False
        if not isinstance(value, dict):
            return False
        return "steps" in value

    # ------------------------------------------------------------------
    # Reserved keys
    # ------------------------------------------------------------------

    def reserved_top_level_keys(self) -> set[str]:
        return CIRCLECI_RESERVED_KEYS

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    def matches_filename(self, filename: str) -> bool:
        # CircleCI config is always ``config.yml`` inside ``.circleci/``,
        # but the filename alone is ambiguous — rely on directory detection.
        return False

    def matches_directory(self, path: Path) -> bool:
        """Detect ``.circleci/`` directory structure."""
        path = Path(path)
        # Check if path itself is .circleci
        if path.name == ".circleci":
            return True
        # Check if .circleci exists within path
        candidate = path / ".circleci"
        if candidate.is_dir():
            return True
        # Check if path is inside a .circleci tree
        parts = path.parts
        for part in parts:
            if part == ".circleci":
                return True
        return False
