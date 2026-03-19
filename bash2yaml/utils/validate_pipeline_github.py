"""GitHub Actions workflow validation against SchemaStore JSON schema.

GitHub Actions has no official lint API — validation is schema-only.
Schema source: ``https://json.schemastore.org/github-workflow.json``
"""

from __future__ import annotations

import logging
import sys
import tempfile
import time
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
import orjson as json
import ruamel.yaml

logger = logging.getLogger(__name__)

# Import compatibility for Python 3.8+
if sys.version_info >= (3, 9):  # noqa: UP036
    from importlib.resources import files
else:
    try:
        from importlib_resources import files
    except ImportError:
        files = None

# Python 3.9+ cache support
try:
    from functools import cache as _py_cache

    cache = _py_cache
except ImportError:

    def cache(func):
        return lru_cache(maxsize=None)(func)


class GitHubActionsValidator:
    """Validates GitHub Actions workflow YAML files against the SchemaStore schema."""

    def __init__(self, cache_dir: str | None = None):
        self.schema_url = "https://json.schemastore.org/github-workflow.json"
        self.cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir())
        self.cache_file = self.cache_dir / "github_workflow_schema.json"
        self.fallback_schema_path = "schemas/github_workflow_schema.json"
        self.yaml = ruamel.yaml.YAML(typ="rt")

    def _fetch_schema_from_url(self) -> dict[str, Any] | None:
        try:
            with urllib.request.urlopen(self.schema_url, timeout=5) as response:  # nosec
                schema_data = response.read().decode("utf-8")
                return json.loads(schema_data)
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to fetch GitHub Actions schema from URL: %s", e)
            return None

    def _load_schema_from_cache(self) -> dict[str, Any] | None:
        try:
            if self.cache_file.exists():
                mtime = self.cache_file.stat().st_mtime
                age_seconds = time.time() - mtime
                seven_days = 7 * 24 * 60 * 60
                if age_seconds > seven_days:
                    logger.debug("Cache file is older than 7 days, ignoring.")
                    return None

                with open(self.cache_file, encoding="utf-8") as f:
                    return json.loads(f.read())
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Failed to load schema from cache: %s", e)
        return None

    def _save_schema_to_cache(self, schema: dict[str, Any]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(schema).decode())
        except OSError as e:
            logger.warning("Failed to save schema to cache: %s", e)

    def _load_fallback_schema(self) -> dict[str, Any] | None:
        try:
            if files is not None:
                try:
                    package_files = files(__package__.rsplit(".", 1)[0] if __package__ else "bash2yaml")
                    schema_file = package_files / self.fallback_schema_path
                    if schema_file.is_file():
                        schema_data = schema_file.read_text(encoding="utf-8")
                        return json.loads(schema_data)
                except (FileNotFoundError, AttributeError, TypeError):
                    pass

            try:
                current_dir = Path(__file__).parent.parent if "__file__" in globals() else Path.cwd()
                fallback_file = current_dir / self.fallback_schema_path
                if fallback_file.exists():
                    with open(fallback_file, encoding="utf-8") as f:
                        return json.loads(f.read())
            except (OSError, FileNotFoundError):
                pass

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to load GitHub Actions schema from package resource: %s", e)

        return None

    @cache  # noqa: B019
    def get_schema(self) -> dict[str, Any]:
        """Get the GitHub Actions schema: cache -> URL -> fallback."""
        schema = self._load_schema_from_cache()
        if schema:
            logger.debug("Using cached GitHub Actions schema")
            return schema

        schema = self._fetch_schema_from_url()
        if schema:
            logger.debug("Using schema from URL")
            self._save_schema_to_cache(schema)
            return schema

        schema = self._load_fallback_schema()
        if schema:
            logger.debug("Using GitHub Actions schema from package")
            return schema

        raise RuntimeError("Could not load GitHub Actions schema from URL, cache, or fallback resource")

    def validate_workflow(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate GitHub Actions workflow YAML against the schema.

        Returns:
            tuple of ``(is_valid, list_of_error_messages)``.
        """
        if "pragma" in yaml_content.lower() and "do-not-validate-schema" in yaml_content.lower():
            logger.debug("Skipping validation: found do-not-validate-schema pragma")
            return True, []

        try:
            config_dict = self.yaml.load(yaml_content)

            schema = self.get_schema()

            validator = jsonschema.Draft7Validator(schema)
            errors = []

            for error in validator.iter_errors(config_dict):
                error_path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
                error_msg = f"Path '{error_path}': {error.message}"
                errors.append(error_msg)

            return len(errors) == 0, errors

        except ruamel.yaml.YAMLError as e:
            return False, [f"YAML parsing error: {str(e)}"]
        except Exception as e:
            return False, [f"Validation error: {str(e)}"]
