# bash2yaml Roadmap

> **Status:** Approved direction, phased for handoff
> **Audience:** Any agent or contributor executing the work. Each phase is
> self-contained; do them in order unless a phase note says otherwise.
> **House rules for the executing bot:**
> - Run everything through `uv run` (e.g. `uv run pytest`). Never the system Python.
> - YAML is handled with `ruamel.yaml` to preserve comments/anchors/formatting.
>   Do not switch YAML libraries or lose round-trip fidelity.
> - New behavior gets tests under `test/`. Follow the existing scenario-folder
>   pattern in `test/test_commands/`.
> - Targets live in `bash2yaml/targets/`, commands in `bash2yaml/commands/`.
>   New platform behavior goes in the target adapter, not in command logic.
> - Update `CHANGELOG.md` per phase, and docs under `docs/` when user-facing
>   behavior changes.

---

## Phase 1 — GitLab CI/CD Components & `spec:inputs`

**What this is.** GitLab's component/templating system. The names to search docs
for: **"CI/CD components"**, **"spec:inputs"**, and **"inputs interpolation"**.
The syntax is GitLab's own (not Jinja/ytt):

```yaml
spec:
  inputs:
    stage:
      default: test
    job-prefix:
      type: string
---
"$[[ inputs.job-prefix ]]-scan":
  stage: $[[ inputs.stage ]]
  script:
    - ./scripts/scan.sh
```

Key structural facts the compiler must respect:

- A component template file is a **multi-document YAML file**: a `spec:` header
  document, a `---` separator, then the pipeline body. `ruamel.yaml` must load
  and dump it as multi-doc without mangling the separator.
- `$[[ inputs.x ]]` interpolation can appear in keys, values, and inside
  script strings. Interpolation supports functions (e.g.
  `$[[ inputs.x | expand_vars ]]`) — treat the whole `$[[ ... ]]` span as
  opaque; never split or re-quote across it.
- Components live in repos under `templates/<name>.yml` or
  `templates/<name>/template.yml` and are consumed via
  `include: component: gitlab.example.com/group/proj/name@1.0`.
- Inputs also work on plain `include:` files (`include: ... inputs: ...`),
  not just catalog components.

**Why bash2yaml cares.** The core user base maintains centralized template
repos (see README "Who is this for?"). Components are GitLab's blessed way to
do that, so component template files are exactly the files bash2yaml will be
asked to compile. Today `bash2yaml/targets/gitlab.py` has no awareness of
`spec:`, multi-doc files, or `$[[ ]]`.

### Work items

1. **Multi-document YAML support in the GitLab target.**
   - `targets/gitlab.py` (and any single-doc assumptions in
     `commands/compile_all.py` / `compile_bash_reader.py`): detect a leading
     `spec:` doc, pass it through untouched, compile only the body doc(s).
   - `is_job()` / `reserved_top_level_keys()` must not treat `spec` as a job.
   - Round-trip test: compile a component template; the `spec:` header and the
     `---` separator are byte-identical in output.
2. **Interpolation-safe inlining.**
   - When inlining a script into a `script:` block, any `$[[ ... ]]` already in
     the YAML must survive verbatim.
   - New (optional, pragma-gated) feature: allow `$[[ inputs.x ]]` inside a
     `.sh` source file, passed through to the compiled YAML untouched. Needs a
     pragma like `# Pragma: gitlab-interpolation` so shellcheck-unfriendly
     tokens are opt-in. Document the shellcheck interaction.
3. **Validation.**
   - GitLab's official schema does not accept the `spec:` doc as part of the
     pipeline schema. `validate()` in `targets/gitlab.py` must validate the
     body doc only, and validate the `spec:` doc against the inputs spec shape
     (keys: `default`, `description`, `type`, `options`, `regex`).
4. **Decompile support.**
   - `decompile_all.py`: extracting scripts from a component template must
     preserve the `spec:` header and write it back on recompile.
5. **`init` / `doctor` awareness.**
   - `init_project.py`: a `--component` flavor that scaffolds
     `templates/<name>/template.yml` + `scripts/`.
   - `doctor.py`: detect a components repo (presence of `templates/*.yml` with
     `spec:` headers) and report it.

**Acceptance:** an `examples/gitlab-component/` worked example exists; compile,
decompile, validate, and drift-detect all pass on it; existing GitLab tests
still pass.

---

## Phase 2 — Feature parity across forge CI dialects

**Problem.** GitLab is the first-class citizen; the other five targets
(`github.py`, `circleci.py`, `buildspec.py`, `bitbucket.py`, `semaphore.py`)
were added later and support an unaudited subset of features. Commands like
drift detection, pipeline docs, template pinning/upgrading
(`upgrade_pinned_templates.py`), and trigger (`pipeline_trigger.py`) may be
GitLab-only in practice.

### Work items

1. **Parity audit (do this first; it scopes everything else).**
   - Produce `spec/parity_matrix.md`: rows = capabilities (compile, decompile,
     validate online, validate offline/fallback schema, lint, drift detect,
     graph, pipeline docs, init scaffolding, watch, template pin/upgrade,
     trigger), columns = the six targets. Fill it by reading code and running
     the existing example/scenario tests per target — not from memory.
   - Mark each cell: works / partial / missing / not-applicable (some cells
     are legitimately N/A, e.g. `include:`-style pinning on buildspec).
2. **Close the "must work everywhere" row first:** compile, decompile,
   validate, lint, drift-detect must be green for all six targets. Each gap is
   one bot-sized task: fix the target adapter, add a scenario test mirroring
   the GitLab one.
3. **Per-forge analog of Phase 1** (parameterized/reusable pipeline units).
   Same pass-through rule as `$[[ ]]`: bash2yaml never evaluates these, it
   must just not break them:
   - GitHub Actions: reusable workflows (`on: workflow_call: inputs:`) and
     `${{ inputs.x }}` / `${{ ... }}` expressions inside `run:` strings.
   - CircleCI: pipeline/job `parameters:` and `<< parameters.x >>` /
     `<< pipeline.x >>` syntax. The `<< >>` tokens are hostile to naive YAML
     handling — needs explicit round-trip tests.
   - Bitbucket: YAML anchors-based reuse and `definitions:` blocks.
   - Buildspec / Semaphore: confirm N/A or document what exists.
4. **Document the matrix** in `docs/` as a user-facing support table, and make
   `bash2yaml doctor` honest about per-target capability (no implying a
   command works on a target where it's "missing" in the matrix).

**Acceptance:** parity matrix exists and is enforced by a test that
parameterizes the core five capabilities over all six targets via scenario
fixtures.

---

## Phase 3 — UI/UX ergonomics

**Problem.** There are five surfaces — CLI, `interactive.py`, `tui.py`,
`gui.py`, and `web/` — and per `docs_todo/pain_points.md` the interactive
CLI/GUI/TUI lag behind the main app. Plus known CLI ergonomics debt from
`docs_todo/TODO.md`.

### Work items (each independent; good cheap-bot fodder)

1. **CLI exit codes and errors.** Only `__main__` returns exit codes; all
   other layers raise typed exceptions (`bash2yaml/errors/`). Map common
   failures to distinct codes. Kill raw stack traces for user errors:
   - missing script file on compile → friendly error + suggestion
   - inlining a `.sh` inside a `.sh` → suggest `# Pragma: do-not-inline`
   - `validate` without `--out` → real message, not a crash
2. **`--json` output flag** on compile/validate/lint/drift for scripting, and
   piped-stdin single-file mode.
3. **Silent-failure fixes.** `detect_drift.py`: dry-run prints output but the
   real run prints nothing — make non-dry-run report what it did.
4. **Surface triage.** Decide (one short ADR in `spec/`): which of
   interactive/TUI/GUI/web are supported vs. demoted to experimental. Bring
   the supported ones up to current command coverage; mark the rest clearly
   in `--help` and docs. Don't silently maintain five half-UIs.
5. **Hash sidecar cleanup** (also a UX issue — "clutter! ugly!"): migrate
   per-file `.hash` sidecars to a single `.bash2yaml/hashes.json` (or similar)
   with a migration shim that reads old sidecars once and deletes them on next
   compile. **Note:** coordinate with Phase 4 — traceless mode needs hashes in
   a state dir anyway; build one hash-store abstraction, two backends
   (in-repo file, traceless state dir).

**Acceptance:** no command exits via unhandled traceback for foreseeable user
errors; `--json` works on the four core commands; ADR merged; hash store
unified.

---

## Phase 4 — Traceless mode ("invisible mode")

**Status: spec complete, implementation not started.** The full design is in
`spec/TRACELESS.md` — read it before writing any code; it is the source of
truth and already contains the v1 scope checklist. Summary: bash2yaml runs
entirely outside the working tree (state under the user's home, keyed by repo
fingerprint), emits YAML with no headers/fences/hash sidecars, so a teammate
sees only normal hand-written-looking YAML.

### Work items (mirrors the TRACELESS.md v1 checklist)

1. Composable flags on compile: `--no-header`, `--no-fences`, `--no-hash`,
   `--in-place`, `--state-dir`; `--traceless` as the macro flag.
2. State-dir storage: `hashes.json`, `sources.json`, `config.toml` under a
   fingerprinted dir (fingerprint = remote URL + checkout path, hashed to 16
   hex chars per the spec's open-questions resolutions).
3. `decompile --traceless --no-rewrite` (extract sources to state dir without
   touching the repo).
4. `traceless` subcommand group: `adopt`, `compile`, `verify`, `shred`.
   `verify` exit codes per spec: 0 clean / 1 violation / 2 setup error.
5. `--quiet-attribution` on all commands (no bash2yaml mentions in any output
   file or log line destined for the repo).
6. Docs page `docs/usage/traceless.md` + worked example
   `examples/traceless/`.

Deferred to v2 (do **not** build now): `traceless promote`, `traceless watch`,
`traceless edit`, traceless pre-commit installer, host-CI verify helper.

**Dependency note:** item 2 should reuse the hash-store abstraction from
Phase 3 item 5. If Phase 3 was skipped, build the abstraction here and
backfill.

**Acceptance:** the v1 scope checklist in `spec/TRACELESS.md` is fully checked;
`traceless verify` passes on the worked example after a compile; a `git status`
in the example repo shows only the compiled YAML changed.

---

## Phase 5 — Tech debt: one codebase, one voice

**Problem.** Different parts of the app read like different authors heading in
different directions: inconsistent error handling, inconsistent parallelism,
config options that exist in env vars but not the TOML file, a deprecated
"best effort runner," and concurrency questions in the update checker.

This phase is deliberately last: Phases 1–4 will touch most of these files
anyway, and their tests make refactoring safer. The executing bot should treat
each item as a separate PR.

### Work items

1. **Error-handling sweep.** Finish what Phase 3 item 1 started: audit every
   module in `commands/` for bare `print`/`sys.exit`/raw exceptions; route
   everything through `bash2yaml/errors/` types. One consistent
   logging/output style (pick the dominant existing one; don't invent).
2. **Parallelism consistency.** compile/validate/lint are parallelized; apply
   the same pattern to the remaining commands or document why a command is
   inherently serial.
3. **Config unification.** Every env-var-only setting gets a `.bash2yaml.toml`
   counterpart via `config.py`'s hierarchy; generate the config reference doc
   from the config schema so it can't drift.
4. **Remove the best-effort runner** (`best_effort_runner.py`) per
   `docs_todo/pain_points.md` — or, if anything depends on it, fold the useful
   part into `doctor` and delete the rest. It also "doesn't stop on tools
   failing," so it's currently misleading.
5. **Update-checker concurrency bug.** Reproduce via `TestConcurrency` /
   `exercise_update_checker.py`, fix, delete the exercise script if redundant.
6. **Repo hygiene.** Root directory carries scratch artifacts
   (`dependency-graph-*`, `tmp/`, `what/`, `docs_bip/`, `coverage.xml`,
   `junit.xml`, `htmlcov/`). Gitignore or delete the generated ones; promote
   or remove the scratch dirs. Fold the still-true parts of
   `docs_todo/` and `ROAD2BASH2YAML.md` into real docs and delete the rest —
   stale planning docs are exactly the "different people, different
   directions" smell this phase exists to fix.

**Acceptance:** `docs_todo/` is empty (contents either done or promoted into
tracked issues/docs); one error-handling pattern repo-wide; config reference
generated, not hand-maintained.

---

## Sequencing summary

| Phase | Theme | Depends on |
|-------|-------|-----------|
| 1 | GitLab components / `spec:inputs` | — |
| 2 | Forge parity (audit first) | 1 (defines the parity bar for "inputs-like" features) |
| 3 | UX ergonomics | — (parallelizable with 1–2) |
| 4 | Traceless v1 | 3.5 (hash-store abstraction), `spec/TRACELESS.md` |
| 5 | Tech debt sweep | best after 1–4; items 5.5–5.6 can start anytime |
