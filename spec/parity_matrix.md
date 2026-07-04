# Target parity matrix (Phase 2)

> **Status:** GitLab and GitHub columns audited (2026-07-04) by reading code
> and running the scenario tests / worked examples. The other four columns
> are **not yet audited** — cells marked `?` are guesses pending the same
> treatment. Fill a column only after running its scenario tests.

Legend: ✅ works · 🟡 partial · ❌ missing · N/A not applicable · ? not audited

| Capability | gitlab | github | circleci | bitbucket | buildspec | semaphore |
|---|---|---|---|---|---|---|
| compile | ✅ | ✅ | ? | ? | ? | ? |
| decompile | ✅ | ✅ | ? | ? | ? | ? |
| validate (online schema) | ✅ | ✅ | ? | ? | ? | ? |
| validate (offline fallback schema) | ✅ | ✅ | ? | ? | ? | ? |
| lint (hosted API) | ✅ GitLab CI Lint API | N/A — GitHub has no lint API; schema validation is the analog | N/A | N/A | N/A | N/A |
| drift detect | ✅ | ✅ | ? | ? | ? | ? |
| graph | ✅ | ? | ? | ? | ? | ? |
| pipeline docs | ✅ | ? | ? | ? | ? | ? |
| init scaffolding | ✅ (incl. `--component`) | ❌ — `init` scaffolds GitLab-shaped projects only | ❌ | ❌ | ❌ | ❌ |
| watch | ✅ | ? | ? | ? | ? | ? |
| template pin/upgrade | ✅ (`include:` pinning) | ❌ — `uses: @ref` pinning not implemented (`upgrade_pinned_templates.py` parses GitLab `include:` only) | ? | N/A (no include mechanism) | N/A | ? |
| trigger | ✅ (python-gitlab) | ❌ — no GitHub dispatch support (`pipeline_trigger.py` is GitLab-only) | ❌ | ❌ | ❌ | ❌ |
| parameterized reuse pass-through | ✅ `spec:inputs` + `$[[ ]]` (Phase 1) | ✅ `workflow_call` inputs + `${{ }}` (this phase) | ❌ `<< parameters.x >>` untested — hostile to naive YAML handling, needs explicit round-trip tests | ? anchors/`definitions:` | N/A (likely) | N/A (likely) |

## GitHub column — audit notes (2026-07-04)

- **compile / decompile / validate**: exercised by
  `test/test_commands/test_scenario_github1.py`,
  `test/test_commands/test_scenario_github_reusable.py`, and
  `test/test_commands_no_scenario/test_github_*.py`. Offline fallback schema
  ships at `bash2yaml/schemas/github_workflow_schema.json`.
- **drift detect**: hash-sidecar based, target-agnostic; verified against
  `examples/github-reusable/`.
- **reusable workflows**: `on: workflow_call: inputs:` passes through
  untouched (`on` is a reserved key and ruamel keeps it a string, not a YAML
  1.1 boolean). `${{ ... }}` expressions survive verbatim in `if:`, `env:`,
  `environment:`, and `run:` strings. Expressions inside `.sh` sources are
  opt-in via `# Pragma: github-expression` (stripped at compile; decompile
  adds it back automatically). See `docs/usage/github-reusable.md`.
- **known gaps** (each is a bot-sized task if wanted): `init --target github`
  scaffolding, `uses:` ref pinning/upgrading, `workflow_dispatch` triggering,
  graph/pipeline-docs over `needs:`.
