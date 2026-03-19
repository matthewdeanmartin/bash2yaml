"""Semaphore CI target adapter.

Handles the structural differences between Semaphore and GitLab CI:
- Config lives at ``.semaphore/semaphore.yml``
- Blocks → tasks → jobs, with ``commands:`` at the job level (array of strings)
- ``task.prologue.commands`` and ``task.epilogue.*.commands`` for setup/teardown
- Variables: ``env_vars:`` as array of ``{name, value}`` objects (unique format)
- ``promotions`` section — skip (references to other pipeline files)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bash2yaml.targets.base import BaseTarget, ScriptSection, VariablesSection

logger = logging.getLogger(__name__)

# Semaphore CI reserved top-level keys (not pipeline sections).
SEMAPHORE_RESERVED_KEYS: set[str] = {
    "version",
    "name",
    "agent",
    "promotions",
    "queue",
    "fail_fast",
    "auto_cancel",
    "global_job_config",
}


class SemaphoreTarget(BaseTarget):
    """Target adapter for Semaphore CI (``.semaphore/semaphore.yml``)."""

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "semaphore"

    @property
    def display_name(self) -> str:
        return "Semaphore CI"

    # ------------------------------------------------------------------
    # Structure introspection
    # ------------------------------------------------------------------

    def script_key_paths(self, doc: dict) -> list[ScriptSection]:
        """Find all scriptable sections in a Semaphore CI config.

        Traverses ``blocks[].task.jobs[].commands``,
        ``blocks[].task.prologue.commands``, and
        ``blocks[].task.epilogue.{always,on_pass,on_fail}.commands``.
        """
        sections: list[ScriptSection] = []

        for idx, block in enumerate(doc.get("blocks", [])):
            if not isinstance(block, dict):
                continue

            block_name = block.get("name", f"block[{idx}]")
            task = block.get("task", {})
            if not isinstance(task, dict):
                continue

            # --- jobs ---
            jobs = task.get("jobs", [])
            if isinstance(jobs, list):
                for job_idx, job in enumerate(jobs):
                    if not isinstance(job, dict):
                        continue
                    job_name_str = job.get("name", f"job[{job_idx}]")
                    if "commands" in job and isinstance(job["commands"], list):
                        sections.append(
                            ScriptSection(
                                job_name=f"{block_name}/{job_name_str}",
                                script_key="commands",
                                lines=job["commands"],
                                parent=job,
                            )
                        )

            # --- prologue ---
            prologue = task.get("prologue", {})
            if isinstance(prologue, dict) and "commands" in prologue and isinstance(prologue["commands"], list):
                sections.append(
                    ScriptSection(
                        job_name=f"{block_name}/prologue",
                        script_key="commands",
                        lines=prologue["commands"],
                        parent=prologue,
                    )
                )

            # --- epilogue ---
            epilogue = task.get("epilogue", {})
            if isinstance(epilogue, dict):
                for sub_name in ("always", "on_pass", "on_fail"):
                    sub_dict = epilogue.get(sub_name, {})
                    if isinstance(sub_dict, dict) and "commands" in sub_dict and isinstance(sub_dict["commands"], list):
                        sections.append(
                            ScriptSection(
                                job_name=f"{block_name}/epilogue/{sub_name}",
                                script_key="commands",
                                lines=sub_dict["commands"],
                                parent=sub_dict,
                            )
                        )

        return sections

    def variables_key_paths(self, doc: dict) -> list[VariablesSection]:
        """Semaphore uses ``env_vars: [{name, value}]`` — not dict-based.

        Standard variable merging (dict-based) doesn't support this format.
        Return empty for now.
        """
        return []

    # ------------------------------------------------------------------
    # Variable / job key names
    # ------------------------------------------------------------------

    def variables_key_name(self) -> str:
        return "env_vars"

    def job_entries(self, doc: dict) -> list[tuple[str, dict]]:
        """Semaphore's block/task/job structure doesn't map to simple top-level job entries."""
        return []

    # ------------------------------------------------------------------
    # Output conventions
    # ------------------------------------------------------------------

    def default_output_filename(self) -> str:
        return ".semaphore/semaphore.yml"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def schema_url(self) -> str | None:
        return "https://raw.githubusercontent.com/semaphoreci/spec/main/schemas/pipeline.json"

    def fallback_schema_path(self) -> str | None:
        return "schemas/semaphore_schema.json"

    def validate(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate using JSON schema from Semaphore's spec repository."""
        from bash2yaml.utils.validate_pipeline_semaphore import SemaphoreValidator

        validator = SemaphoreValidator()
        return validator.validate_pipeline(yaml_content)

    # ------------------------------------------------------------------
    # Decompile support
    # ------------------------------------------------------------------

    def script_keys(self) -> list[str]:
        return ["commands"]

    def is_job(self, key: str, value: Any) -> bool:
        """In Semaphore CI, a "job" is a dict with a ``commands`` key."""
        return isinstance(value, dict) and "commands" in value

    # ------------------------------------------------------------------
    # Reserved keys
    # ------------------------------------------------------------------

    def reserved_top_level_keys(self) -> set[str]:
        return SEMAPHORE_RESERVED_KEYS

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    def matches_filename(self, filename: str) -> bool:
        """Detect ``semaphore.yml`` or ``semaphore.yaml``."""
        return filename.lower() in ("semaphore.yml", "semaphore.yaml")

    def matches_directory(self, path: Path) -> bool:
        """Detect a ``.semaphore`` directory or a directory containing one."""
        path = Path(path)
        if path.name == ".semaphore":
            return True
        if (path / ".semaphore").is_dir():
            return True
        if any(part == ".semaphore" for part in path.parts):
            return True
        return False
