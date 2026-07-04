# GitHub Actions Reusable Workflows (`workflow_call`)

GitHub's [reusable workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
are the GitHub analog of GitLab components: a workflow declares typed inputs
under `on: workflow_call: inputs:`, consumers call it via
`jobs.<id>.uses: org/repo/.github/workflows/name.yml@ref`, and GitHub
substitutes `${{ inputs.x }}` expressions before each step runs.

bash2yaml compiles reusable workflows the same way it compiles any other
GitHub Actions workflow (`--target github`), with two guarantees:

1. **The `workflow_call` block is untouched.** `on:` is a reserved key — the
   trigger, its `inputs:`, and its `secrets:` pass through compilation
   unchanged (and `on` never degrades into a YAML boolean).
2. **Expressions are opaque.** `${{ ... }}` (any context or function:
   `inputs`, `github`, `secrets`, `contains()`, …) is never split, re-quoted,
   or evaluated, whether it appears in `if:`, `env:` values, or `run:` lines.

## Example

`src/deploy.yml`:

```yaml
name: Reusable deploy

on:
  workflow_call:
    inputs:
      environment:
        type: string
        required: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        run: ./scripts/deploy.sh
```

Run `bash2yaml compile --in src --out .github/workflows --target github` and
the compiled workflow keeps the `workflow_call` block and every expression
intact, with `deploy.sh` inlined into the `run:` block.

## Expressions inside bash scripts

`${{ }}` is a bad substitution in real bash (and shellcheck rejects it), so
using GitHub expressions inside a `.sh` source file is opt-in via a pragma:

```bash
#!/usr/bin/env bash
# Pragma: github-expression
set -euo pipefail

echo "Deploying to the ${{ inputs.environment }} environment"
```

The pragma line is a compiler directive: it is stripped from the compiled
YAML. If a script contains `${{ }}` without the pragma, the expressions still
pass through verbatim, but compilation logs a warning so accidental usage is
caught.

Note that shellcheck will flag the `${{ }}` lines themselves; disable the
relevant checks per-line (`# shellcheck disable=SC1083`) or keep expressions
in the workflow YAML (e.g. pass them in via `env:`) and reference plain
environment variables from the script — the `env:` route is the more
idiomatic GitHub Actions style and keeps scripts runnable locally.

## Decompiling

`bash2yaml decompile --target github` on a workflow whose `run:` blocks
contain `${{ }}` extracts the bash into `.sh` files and adds
`# Pragma: github-expression` automatically, so an immediate recompile is
warning-free and round-trips.

## Worked example

See [`examples/github-reusable/`](https://github.com/matthewdeanmartin/bash2yaml/tree/main/examples/github-reusable)
for a compile-ready reusable workflow with a `workflow_call` trigger, typed
inputs, secrets, and expressions in `if:`, `environment:`, `env:`, and the
inlined script.
