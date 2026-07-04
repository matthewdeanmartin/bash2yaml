# GitHub Actions reusable workflow example

This example shows bash2yaml compiling a **reusable workflow** — a workflow
triggered by `on: workflow_call:` with typed `inputs:`, consumed from other
workflows via `jobs.<id>.uses:`. Inputs surface in the workflow body as
`${{ inputs.x }}` expressions.

bash2yaml never evaluates `${{ ... }}` (GitHub does that before a step runs).
It inlines your `.sh` files into `run:` blocks while leaving the
`workflow_call` block and every `${{ ... }}` span byte-for-byte intact.

## Layout

```
src/
  deploy.yml             # uncompiled reusable workflow (workflow_call inputs)
  scripts/deploy.sh      # real bash, with IDE/shellcheck support
.github/workflows/
  deploy.yml             # compiled output — where GitHub requires workflows to live
```

## Expressions inside bash

`src/scripts/deploy.sh` uses `${{ inputs.environment }}` inside the script.
Because `${{ }}` is a bad substitution in real bash (and shellcheck rejects
it), that usage must be opted into with a pragma:

```bash
# Pragma: github-expression
```

The pragma line is stripped from the compiled YAML. Without it, compilation
still passes the expressions through but logs a warning.

## Try it

```bash
./compile.sh
```

Then diff `.github/workflows/deploy.yml` against `src/deploy.yml`: the
`on: workflow_call:` block is untouched and the `run:` block now contains the
inlined bash.

A consumer calls the compiled workflow like any reusable workflow:

```yaml
jobs:
  deploy-staging:
    uses: your-org/your-repo/.github/workflows/deploy.yml@main
    with:
      environment: staging
    secrets:
      deploy-token: ${{ secrets.DEPLOY_TOKEN }}
```
