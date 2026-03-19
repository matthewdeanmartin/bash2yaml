# Supported Targets

bash2yaml supports multiple CI/CD platforms through its **target** system. Each target is a platform adapter that
understands the YAML structure of a specific CI/CD system — where scripts live, how variables are defined, and how to
validate the output.

## Currently Supported

| Target           | `--target` value | Default Output File | Script Keys                                     | Variables Key  |
|:-----------------|:-----------------|:--------------------|:------------------------------------------------|:---------------|
| GitLab CI        | `gitlab`         | `.gitlab-ci.yml`    | `script`, `before_script`, `after_script`       | `variables:`   |
| GitHub Actions   | `github`         | `workflow.yml`      | `run` (in steps)                                | `env:`         |

More targets (CircleCI, AWS CodeBuild, Bitbucket Pipelines, Semaphore) are planned. See the
[roadmap](https://github.com/matthewdeanmartin/bash2yaml/blob/main/ROAD2BASH2YAML.md) for details.

---

## Specifying a Target

### CLI Flag

```bash
bash2yaml compile --in src/ --out dist/ --target github
bash2yaml compile --in src/ --out dist/ --target gitlab
```

### Configuration

In `.bash2yaml.toml` or `pyproject.toml`:

```toml
[tool.bash2yaml]
target = "github"
```

### Auto-Detection

If you don't specify a target, bash2yaml will try to detect it automatically:

- **GitLab CI**: Detected when the input file is named `.gitlab-ci.yml` or matches common GitLab CI patterns.
- **GitHub Actions**: Detected when the input directory is (or contains) `.github/workflows/`.

If auto-detection is ambiguous or fails, bash2yaml defaults to `gitlab` for backward compatibility.

---

## GitLab CI

The original and default target. GitLab CI jobs have `script:`, `before_script:`, and `after_script:` keys that contain
arrays of shell commands or script references.

### Structure

```yaml
# .gitlab-ci.yml
variables:
  APP_NAME: myapp

build-job:
  stage: build
  variables:
    BUILD_TYPE: release
  script:
    - ./scripts/build.sh
```

### Key behaviors

- **Script inlining**: Lines like `./scripts/build.sh` in `script:` arrays are replaced with the file's contents.
- **Variable merging**: `global_variables.sh` merges into the top-level `variables:` block. `jobname_variables.sh`
  merges into that job's `variables:` block.
- **Validation**: Schema validation against GitLab's official schema, plus optional lint via the GitLab API
  (`bash2yaml lint`).
- **Reserved keys**: `stages`, `variables`, `include`, `default`, `workflow`, `image`, `services`, `cache`,
  `before_script`, `after_script`, and others are recognized as non-job keys.

---

## GitHub Actions

GitHub Actions workflows live in `.github/workflows/` and use a different structure from GitLab. Jobs are nested
under a `jobs:` key, and scripts live in `steps[].run:` as multiline strings rather than arrays.

### Structure

```yaml
# .github/workflows/ci.yml
name: CI
on: push

env:
  NODE_ENV: production

jobs:
  build:
    runs-on: ubuntu-latest
    env:
      BUILD_TYPE: release
    steps:
      - uses: actions/checkout@v4
      - name: Build project
        run: ./scripts/build.sh
        env:
          OPTIMIZATION: high
```

### Key behaviors

- **Script inlining**: The entire `run:` value is treated as a single script reference
  (e.g. `run: ./scripts/build.sh`). The referenced file's contents replace the whole `run:` value as a literal
  block scalar (`run: |-`).
- **`uses:` steps are untouched**: Steps with `uses:` (reusable actions) are never modified by the compiler.
- **Variable merging**: `global_variables.sh` merges into the workflow-level `env:` block. `jobname_variables.sh`
  merges into that job's `env:` block. GitHub supports `env:` at three levels — workflow, job, and step — and
  bash2yaml preserves all of them.
- **Validation**: Schema validation against the SchemaStore GitHub Actions schema. No API-based lint is available
  for GitHub Actions.
- **Multiple workflow files**: When pointing at a `.github/workflows/` directory, bash2yaml processes all `.yml`
  files within it.
- **Decompile**: The decompiler extracts `run:` blocks into `.sh` files. Step names are used to derive filenames.
  Steps without names use their index (e.g. `step[0]`).

### Differences from GitLab at a glance

| Concept                | GitLab CI                     | GitHub Actions                      |
|:-----------------------|:------------------------------|:------------------------------------|
| Jobs location          | Top-level keys                | Nested under `jobs:`                |
| Script format          | Array of strings (`script:`)  | Multiline string (`run: \|`)        |
| Variables key          | `variables:`                  | `env:`                              |
| Variable scopes        | Global + job                  | Workflow + job + step               |
| Reusable actions       | `include:`                    | `uses:` (left untouched)            |
| before/after scripts   | `before_script:`/`after_script:` | Modeled as separate steps        |
| Lint API               | GitLab CI Lint API            | Schema validation only              |

---

## Third-Party Targets via Plugins

bash2yaml uses [pluggy](https://pluggy.readthedocs.io/) for extensibility. You can create a target for any CI/CD
platform and register it as a plugin — no changes to bash2yaml itself are needed.

See [Adding a New Target](NEW_TARGET_TASKS.md) for a step-by-step guide.
