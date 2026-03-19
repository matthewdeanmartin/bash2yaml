# Adding a New Target

This guide walks through everything you need to do to add support for a new CI/CD platform to bash2yaml. Follow these
tasks in order — each one builds on the previous.

---

## Prerequisites

Before you start, make sure you understand:

- The YAML structure of your target CI/CD platform (where jobs, scripts, and variables live)
- The `BaseTarget` interface in `bash2yaml/targets/base.py`
- How the existing `GitLabTarget` or `GitHubTarget` implementations work (read them as reference)

---

## Task 1: Research Your Platform

Before writing any code, answer these questions about your target platform:

| Question                                      | Example (GitHub Actions)                |
|:----------------------------------------------|:----------------------------------------|
| What is the config filename / path?            | `.github/workflows/*.yml`               |
| Where do jobs live in the YAML structure?      | Under `jobs:` key                       |
| What keys hold script content?                 | `run:` in `steps[]`                     |
| Is script content an array or a string?        | Multiline string                        |
| Where do variables live?                       | `env:` at workflow/job/step levels      |
| Are there reusable components to skip?         | `uses:` steps                           |
| Is there a JSON schema available?              | SchemaStore `github-workflow.json`      |
| Is there a lint API or CLI tool?               | No (schema only)                        |
| What are the reserved (non-job) top-level keys?| `name`, `on`, `env`, `permissions`, ... |

Document your answers — they'll guide every implementation decision.

---

## Task 2: Create the Target Class

Create a new file at `bash2yaml/targets/<platform>.py`. Your class must extend `BaseTarget` and implement all abstract
methods.

### Required methods

```python
from bash2yaml.targets.base import BaseTarget, ScriptSection, VariablesSection

class MyPlatformTarget(BaseTarget):
    @property
    def name(self) -> str:
        """Short identifier, e.g. 'circleci'. Used in --target flag."""

    @property
    def display_name(self) -> str:
        """Human-readable name, e.g. 'CircleCI'."""

    def script_key_paths(self, doc: dict) -> list[ScriptSection]:
        """Find all script sections in the parsed YAML.
        Return a ScriptSection for each scriptable block."""

    def variables_key_paths(self, doc: dict) -> list[VariablesSection]:
        """Find all variable sections in the parsed YAML."""

    def default_output_filename(self) -> str:
        """E.g. 'config.yml', 'buildspec.yml'."""

    def schema_url(self) -> str | None:
        """URL to fetch the JSON schema. Return None if unavailable."""

    def fallback_schema_path(self) -> str | None:
        """Package-relative path to a bundled fallback schema."""

    def validate(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate compiled YAML. Return (is_valid, error_messages)."""

    def script_keys(self) -> list[str]:
        """YAML keys that hold script content, e.g. ['run'] or ['script', 'before_script']."""

    def is_job(self, key: str, value: Any) -> bool:
        """Return True if (key, value) represents a CI job (not a metadata key)."""

    def reserved_top_level_keys(self) -> set[str]:
        """Top-level YAML keys that are NOT jobs."""
```

### Methods you may need to override

```python
def variables_key_name(self) -> str:
    """Default returns 'variables'. Override if your platform uses
    a different key (e.g. 'env', 'environment', 'env_vars')."""

def job_entries(self, doc: dict) -> list[tuple[str, dict]]:
    """Default returns all non-reserved top-level dict entries.
    Override if jobs are nested (e.g. under a 'jobs:' key)."""

def matches_filename(self, filename: str) -> bool:
    """Return True if this filename is a strong signal for your platform.
    Used for auto-detection."""

def matches_directory(self, path: Path) -> bool:
    """Return True if the directory structure matches your platform.
    Used for auto-detection."""
```

### Tips

- Look at `GitLabTarget` for a platform with array-style scripts and top-level jobs.
- Look at `GitHubTarget` for a platform with string-style scripts, nested jobs, and step-based structure.
- Use `ScriptSection.parent` to give callers a way to write back processed results.
- For platforms with steps (like GitHub), your `script_key_paths()` needs to iterate into steps within each job.

---

## Task 3: Create the Validator

Create `bash2yaml/utils/validate_pipeline_<platform>.py`. Follow the pattern established by the existing validators:

```python
class MyPlatformValidator:
    def validate_workflow(self, yaml_content: str) -> tuple[bool, list[str]]:
        # 1. Check for pragma: do-not-validate-schema
        # 2. Parse YAML
        # 3. Validate against JSON schema
        # 4. Return (is_valid, errors)
```

Schema fetching follows the pattern: **cache → URL → bundled fallback**.

- Cache directory: `~/.cache/bash2yaml/schemas/` (7-day expiry)
- URL: from your target's `schema_url()`
- Fallback: a minimal schema bundled at `bash2yaml/schemas/<platform>_schema.json`

---

## Task 4: Create a Fallback Schema

Add a minimal JSON schema at `bash2yaml/schemas/<platform>_schema.json`. This is used when the remote schema can't be
fetched. It doesn't need to be exhaustive — just enough to catch obvious structural errors (missing required keys,
wrong types).

Look at `bash2yaml/schemas/github_workflow_schema.json` for a good example of a minimal fallback.

---

## Task 5: Register the Target

Add your target to the built-in registry in `bash2yaml/targets/__init__.py`:

```python
def _ensure_builtins() -> None:
    if _registry:
        return
    from bash2yaml.targets.github import GitHubTarget
    from bash2yaml.targets.gitlab import GitLabTarget
    from bash2yaml.targets.myplatform import MyPlatformTarget  # <-- add

    for cls in (GitLabTarget, GitHubTarget, MyPlatformTarget):  # <-- add
        _instance = cls()
        _registry[_instance.name] = _instance
```

After this step, `--target myplatform` will work in the CLI.

---

## Task 6: Handle Compile/Decompile Differences

The compile and decompile pipelines are generic, but they need to handle structural differences between platforms.
The key decision points are:

### If your platform uses steps (like GitHub Actions)

The decompiler in `decompile_all.py` has a branch for step-based platforms. If your job data contains a `steps` list,
the decompiler will iterate through steps and decompile script keys within each step. Make sure your `is_job()` and
`job_entries()` methods return the right structure.

### If your platform nests jobs (like GitHub's `jobs:` key)

Override `job_entries()` to return jobs from the correct nesting level. The default implementation assumes jobs are
top-level keys.

### If your platform uses a different variables key

Override `variables_key_name()` to return the correct key (e.g. `"env"`, `"environment"`, `"env_vars"`). The compiler
and decompiler use this to find and merge variables.

---

## Task 7: Write Tests

### Unit tests (`test/test_commands_no_scenario/`)

Create `test_<platform>_target.py` with tests for:

- `name` and `display_name` properties
- `script_key_paths()` — finds scripts, skips non-script sections
- `variables_key_paths()` — finds variables at all supported scopes
- `job_entries()` — returns correct jobs
- `is_job()` — distinguishes jobs from metadata
- `reserved_top_level_keys()` — expected keys are present
- `default_output_filename()`
- `script_keys()`
- Auto-detection (`matches_filename()`, `matches_directory()`)
- Schema URL and fallback path

Create `test_<platform>_validator.py` with tests for:

- Valid YAML passes
- Pragma skips validation
- Invalid YAML fails
- Missing required keys fails

### Integration tests (`test/test_commands/`)

Create a scenario directory: `test/test_commands/scenario_<platform>/`

```
scenario_myplatform/
├── uncompiled/
│   ├── config.yml              # your platform's YAML with script refs
│   ├── scripts/
│   │   ├── build.sh
│   │   └── test.sh
│   ├── global_variables.sh     # optional
│   └── build_variables.sh      # optional
└── .out/                       # generated by tests, gitignored
```

Create `test_scenario_<platform>.py` that tests the full compile round-trip:

- Scripts are inlined
- Variables are merged (global and job-level)
- Platform-specific structures are preserved (e.g. `uses:` steps untouched)
- Output is valid YAML

### Decompile tests

Add decompile tests in `test/test_commands_no_scenario/test_<platform>_decompile.py`:

- Scripts are extracted to `.sh` files
- Non-script sections are preserved
- Output YAML references `.sh` files

---

## Task 8: Update Documentation

1. Add your platform to `docs/targets/supported_targets.md` — add a row to the table and a new section with
   structure examples and key behaviors.
2. Update `docs/overview/README.md` and `docs/usage/usage.md` if they reference GitLab-specific concepts that now
   apply to your platform too.

---

## Task 9: Alternative — Register as a Plugin

If you're building a target outside of the bash2yaml repository, you can register it as a pluggy plugin instead of
modifying `__init__.py`. Create a package that implements the `register_targets` hookspec:

```python
# In your package's plugin module
import bash2yaml.hookspecs

class MyPlugin:
    @bash2yaml.hookspecs.hookimpl
    def register_targets(self, registry):
        from my_package.target import MyPlatformTarget
        registry.register(MyPlatformTarget())
```

Register the plugin via a `setuptools` entry point or by calling `pluggy` directly. The target will then be available
via `--target myplatform` without any changes to bash2yaml itself.

---

## Checklist

- [ ] Research platform YAML structure
- [ ] Create `bash2yaml/targets/<platform>.py` with target class
- [ ] Create `bash2yaml/utils/validate_pipeline_<platform>.py`
- [ ] Add fallback schema at `bash2yaml/schemas/<platform>_schema.json`
- [ ] Register target in `bash2yaml/targets/__init__.py`
- [ ] Verify compile works (script inlining, variable merging)
- [ ] Verify decompile works (script extraction)
- [ ] Write unit tests for the target class
- [ ] Write unit tests for the validator
- [ ] Write integration tests with a scenario directory
- [ ] Write decompile tests
- [ ] Update documentation
- [ ] Run full test suite — all existing tests must still pass
