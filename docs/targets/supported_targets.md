# Supported Targets

bash2yaml supports multiple CI/CD platforms through its **target** system. Each target is a platform adapter that
understands the YAML structure of a specific CI/CD system — where scripts live, how variables are defined, and how to
validate the output.

## Currently Supported

| Target                | `--target` value | Default Output File          | Script Keys                                     | Variables Key  |
|:----------------------|:-----------------|:-----------------------------|:------------------------------------------------|:---------------|
| GitLab CI             | `gitlab`         | `.gitlab-ci.yml`             | `script`, `before_script`, `after_script`       | `variables:`   |
| GitHub Actions        | `github`         | `workflow.yml`               | `run` (in steps)                                | `env:`         |
| CircleCI              | `circleci`       | `config.yml`                 | `command` (in run steps)                        | `environment:` |
| AWS CodeBuild         | `buildspec`      | `buildspec.yml`              | `commands` (in phases)                          | `variables:`   |
| Bitbucket Pipelines   | `bitbucket`      | `bitbucket-pipelines.yml`    | `script`, `after-script`                        | *(none)*       |
| Semaphore CI          | `semaphore`      | `.semaphore/semaphore.yml`   | `commands`                                      | *(none)*       |

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
- **CircleCI**: Detected when the input directory is (or contains) `.circleci/`.
- **AWS CodeBuild**: Detected when the input file is named `buildspec.yml` or `buildspec.yaml`.
- **Bitbucket Pipelines**: Detected when the input file is named `bitbucket-pipelines.yml`.
- **Semaphore CI**: Detected when the input directory is (or contains) `.semaphore/`.

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

## CircleCI

CircleCI configs live at `.circleci/config.yml` and use an orbs + jobs + workflows structure. Scripts live in `steps`
as `run:` entries, where the `command:` key holds the shell content.

### Structure

```yaml
# .circleci/config.yml
version: 2.1

jobs:
  build:
    docker:
      - image: cimg/python:3.12
    environment:
      APP_ENV: production
    steps:
      - checkout
      - run:
          name: Build project
          command: ./scripts/build.sh
```

### Key behaviors

- **Script inlining**: `command:` values that reference a single shell file are replaced with the file's contents,
  wrapped in a `|-` block scalar.
- **`uses:` / checkout steps are untouched**: Steps without a `command:` key (e.g., `checkout`, orb steps) are
  left unmodified.
- **Variable merging**: `global_variables.sh` merges into the top-level `environment:` of a job.
  `jobname_variables.sh` merges into that job's `environment:` block.
- **Validation**: Schema validation against the SchemaStore CircleCI schema. No API-based lint.
- **Reserved keys**: `version`, `orbs`, `workflows`, `executors`, `commands`, `parameters`, `jobs`.

---

## AWS CodeBuild

AWS CodeBuild uses `buildspec.yml` (or `buildspec.yaml`) with a phases-based structure. Scripts live in
`phases.<phase>.commands` arrays. The file typically sits at the repo root.

### Structure

```yaml
# buildspec.yml
version: 0.2

env:
  variables:
    APP_NAME: myapp
  exported-variables:
    - APP_NAME

phases:
  install:
    commands:
      - ./scripts/install.sh
  build:
    commands:
      - ./scripts/build.sh
  post_build:
    commands:
      - ./scripts/cleanup.sh
```

### Key behaviors

- **Script inlining**: Lines in `phases.<phase>.commands` arrays that reference a single shell file are replaced
  with the file's contents.
- **Variable merging**: `global_variables.sh` merges into `env.variables`. Job-level variables (keyed by phase name)
  merge into that phase's commands context.
- **Validation**: Schema validation using a bundled fallback schema (no official JSON schema URL available).
- **Reserved keys**: `version`, `env`, `phases`, `artifacts`, `cache`, `reports`, `proxy`.

---

## Bitbucket Pipelines

Bitbucket Pipelines uses `bitbucket-pipelines.yml` at the repo root. Scripts live inside `step` blocks under various
pipeline triggers (`default`, `branches`, `tags`, `pull-requests`, `custom`). Each step can have both a `script:` and
an `after-script:` array.

### Structure

```yaml
# bitbucket-pipelines.yml
image: atlassian/default-image:3

pipelines:
  default:
    - step:
        name: Build
        script:
          - ./scripts/build.sh
        after-script:
          - ./scripts/cleanup.sh

  branches:
    main:
      - step:
          name: Deploy to production
          script:
            - ./scripts/deploy.sh

  custom:
    run-tests:
      - step:
          name: Run tests
          script:
            - ./scripts/test.sh
```

### Key behaviors

- **Script inlining**: Lines in `script:` and `after-script:` arrays that reference a single shell file are inlined.
- **Parallel steps**: Steps inside `parallel:` groups are fully traversed and inlined.
- **Variable merging**: Not supported — Bitbucket's `variables:` block is for manual pipeline trigger inputs only,
  not environment variables defined in YAML. Use the Bitbucket repository/workspace settings UI instead.
- **Validation**: Schema validation against the SchemaStore Bitbucket Pipelines schema.
- **Reserved keys**: `image`, `options`, `definitions`, `clone`.

### Pipeline trigger structure

| Trigger          | YAML key         | Shape                                    |
|:-----------------|:-----------------|:-----------------------------------------|
| Default          | `default`        | List of step-groups                      |
| Branch patterns  | `branches`       | Dict of `pattern` → list of step-groups  |
| Tag patterns     | `tags`           | Dict of `pattern` → list of step-groups  |
| Pull requests    | `pull-requests`  | Dict of `pattern` → list of step-groups  |
| Manual pipelines | `custom`         | Dict of `name` → list of step-groups     |

---

## Semaphore CI

Semaphore CI configs live at `.semaphore/semaphore.yml`. The structure is blocks-based: each block has a `task` with
`jobs`, an optional `prologue`, and an optional `epilogue`. Scripts live in `commands` arrays throughout.

### Structure

```yaml
# .semaphore/semaphore.yml
version: v1.0
name: My Pipeline

agent:
  machine:
    type: e1-standard-2
    os_image: ubuntu2004

blocks:
  - name: Build
    task:
      prologue:
        commands:
          - ./scripts/setup.sh
      jobs:
        - name: Build project
          commands:
            - ./scripts/build.sh
      epilogue:
        always:
          commands:
            - ./scripts/cleanup.sh
```

### Key behaviors

- **Script inlining**: Lines in `commands` arrays (in jobs, prologue, and epilogue sub-sections) that reference a
  single shell file are inlined.
- **Prologue / epilogue**: Both `task.prologue.commands` and `task.epilogue.{always,on_pass,on_fail}.commands` are
  traversed and inlined.
- **Variable merging**: Not supported — Semaphore uses an object-array format for `env_vars`
  (`[{name: KEY, value: VALUE}]`) that is incompatible with the dict-based variable merging used by other targets.
  Manage secrets and variables via the Semaphore UI or `sem` CLI.
- **Validation**: Schema validation using a bundled fallback schema.
- **Reserved keys**: `version`, `name`, `agent`, `promotions`, `queue`, `fail_fast`, `auto_cancel`,
  `global_job_config`.

---

## Third-Party Targets via Plugins

bash2yaml uses [pluggy](https://pluggy.readthedocs.io/) for extensibility. You can create a target for any CI/CD
platform and register it as a plugin — no changes to bash2yaml itself are needed.

See [Adding a New Target](NEW_TARGET_TASKS.md) for a step-by-step guide.
