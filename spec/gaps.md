# GitHub target gaps — follow-up work items

> **Status:** Backlog, one bot-sized task per section. Written 2026-07-04
> after the Phase 2 GitHub audit (see `spec/parity_matrix.md` for the full
> capability matrix and `spec/fable_says_road_map.md` for house rules:
> `uv run` everything, ruamel round-trip fidelity, tests under `test/`,
> scenario-folder pattern, CHANGELOG + docs per change).
>
> These are the ❌ cells in the GitHub column. Compile, decompile, validate,
> drift-detect, and `workflow_call`/`${{ }}` pass-through are already green
> and tested — do not redo them. Do the items below in any order; they are
> independent of each other.

---

## Gap 1 — `init` has no GitHub scaffold

**The problem.** `bash2yaml init` (`bash2yaml/commands/init_project.py`) only
produces GitLab-shaped projects. `run_init` interactively writes a
`.bash2yaml.toml` plus a GitLab-style `uncompiled/` layout, and the
non-interactive `run_init_component` flavor scaffolds specifically a GitLab
CI/CD component repo (`spec:inputs` header template + script). A user who
develops on GitHub — the tool's second-best-supported forge — gets no
onboarding path at all: there is nothing that lays down
`src/ + .github/workflows/` with a working workflow, script, and config.
`doctor` will happily diagnose a GitHub repo, but `init` can't create one.

**What can be done.** Mirror what Phase 1 did for GitLab components:

1. Add a `run_init_github` (or generalize `run_init` with a `--target github`
   flag — prefer the flag; a per-forge function per target won't scale to six
   targets) that scaffolds:
   - `src/ci.yml` — a minimal workflow (checkout + one `run: ./scripts/build.sh`
     step), and optionally `src/deploy.yml` as a reusable workflow with
     `on: workflow_call: inputs:` (crib from
     `test/test_commands/scenario_github_reusable/uncompiled/`).
   - `src/scripts/build.sh` — real bash with shebang and `set -euo pipefail`.
   - `.bash2yaml.toml` with `target = "github"`, `input = "src"`,
     `output = ".github/workflows"`.
2. Wire the flag in `__main__.py` next to the existing `--component` handling
   (~line 302) and keep `--component` GitLab-only (it is a GitLab concept).
3. Reuse the scaffold-string pattern at the top of `init_project.py`
   (`COMPONENT_TEMPLATE_SCAFFOLD` / `COMPONENT_SCRIPT_SCAFFOLD`).

**Acceptance.** `bash2yaml init --target github` in an empty temp dir followed
by `bash2yaml compile --in src --out .github/workflows --target github`
produces a workflow that passes `validate --target github`, with no manual
edits in between. Test lives beside the existing init tests; follow their
non-interactive style (the interactive prompts must not fire when the flag is
given).

---

## Gap 2 — `check-pins` only understands GitLab `include:` (no `uses: @ref` pinning)

**The problem.** `bash2yaml check-pins`
(`bash2yaml/commands/upgrade_pinned_templates.py`) exists to answer "are my
external template references pinned to something immutable, and is a newer
version available?" It does this exclusively for GitLab: `_normalize_includes`
parses the `include:` block of a `.gitlab-ci.yml`, and `GitLabClient` hits the
GitLab REST API to classify each ref (branch/tag/sha) and suggest a pin.

GitHub Actions has the *same* problem with higher stakes — every
`uses: owner/repo@ref` step is an external, mutable dependency, and
`@main` / `@v4` (a movable tag) vs a full commit SHA is a well-known
supply-chain concern that GitHub's own hardening guide tells you to pin.
bash2yaml currently says nothing about a workflow full of `uses: foo@master`.

**What can be done.** A GitHub analog of the existing pipeline, reusing its
dataclass shapes (`IncludeSpec` → a `UsesSpec`, `Suggestion`,
`IncludeAnalysis`) so the report/JSON output layer
(`analyses_to_table` / `analyses_to_json`) keeps working:

1. **Extraction.** Walk a workflow's `jobs.<id>.steps[].uses` and
   `jobs.<id>.uses` (reusable-workflow calls) and parse
   `owner/repo[/path]@ref`. Skip `./local-action` and `docker://` forms.
   Use the ruamel-loaded document so line/context info is available; never
   rewrite the YAML in this task (report-only, like the GitLab side's default).
2. **Classification.** A small `GitHubClient` mirroring `GitLabClient`, stdlib
   `urllib` only (house style — the GitLab client already avoids extra deps):
   - `GET /repos/{owner}/{repo}/git/matching-refs/tags/{ref}` and
     `/branches/{ref}` to classify branch vs tag vs SHA,
   - `GET /repos/{owner}/{repo}/tags` to find the latest semver tag,
   - token from `GITHUB_TOKEN` env var (optional; unauthenticated works at
     60 req/h, so cache aggressively and batch by repo).
3. **Suggestions.** branch ref → "pin to tag or SHA"; tag ref → "newer tag
   vX available" and optionally "pin to the tag's SHA with a `# vX` trailing
   comment" (the ecosystem convention, e.g. what dependabot writes).
4. Wire `--target github` through the `check-pins` CLI path in `__main__.py`;
   GitLab remains the default.

**Acceptance.** A scenario fixture with a workflow containing `uses:` pinned
to a branch, a tag, and a SHA; the command (with the HTTP client mocked —
follow whatever mocking pattern the existing check-pins tests use) reports
one suggestion for the branch, an upgrade hint for the stale tag, and
"pinned" for the SHA. `--json` output round-trips through `json.loads`.

---

## Gap 3 — `trigger` is python-gitlab only (no `workflow_dispatch`)

**The problem.** `bash2yaml trigger`
(`bash2yaml/commands/pipeline_trigger.py`) triggers pipelines and polls them
to completion, but it is hard-wired to python-gitlab: `get_gitlab_client`,
`trigger_pipelines`, `poll_pipelines_until_complete` all speak GitLab's API
and status vocabulary. On GitHub the equivalent exists —
`POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` for
workflows with a `workflow_dispatch:` trigger, then polling
`/actions/runs` — but bash2yaml can't do it, so the "compile, push, kick the
pipeline, watch it" loop the GitLab side supports is impossible on GitHub.

**What can be done.** Decide first whether this is worth owning at all:
`gh workflow run` + `gh run watch` already do this well, and a thin shell-out
to `gh` (if present) may honestly serve users better than a second HTTP
client. Two acceptable shapes — pick one, don't build both:

- **Option A (recommended): shell out to `gh`.** Detect `gh` on PATH, run
  `gh workflow run <file> --ref <ref> [-f key=val ...]` and
  `gh run watch <id> --exit-status`, map exit codes into the existing
  `TriggerResult` / `PollResult` dataclasses. No new auth story (gh handles
  it), ~100 lines. If `gh` is missing, fail with a friendly install hint
  (there is precedent: `bash2yaml/install_help.py`).
- **Option B: native API client.** stdlib `urllib` against the dispatches +
  runs endpoints, `GITHUB_TOKEN` auth. More code, more polling/status mapping
  (GitHub's `status`/`conclusion` pair vs GitLab's single `status`), and a
  known wart to handle: the dispatch endpoint returns 204 with no run id, so
  you must correlate the run by `created>=timestamp` + branch + workflow.

Either way: wire `--target github` through the `trigger` CLI path, map
statuses into the existing result dataclasses so polling/reporting code is
shared, and honor `--quiet-attribution` (no bash2yaml mentions in dispatched
inputs or logs destined for the repo).

**Caveat for the executing bot.** A `workflow_dispatch` trigger must already
exist in the target workflow — dispatching a workflow without it is a 422.
`doctor`/error output should say exactly that ("add `workflow_dispatch:` to
`on:`"), not surface a raw HTTP error.

**Acceptance.** Unit tests with the `gh` subprocess (or HTTP layer) mocked:
success, failure conclusion, missing-`workflow_dispatch` error path each map
to the right exit code. A manual smoke test against this repo (it is
developed on GitHub — add a trivial dispatchable workflow under
`.github/workflows/` if none exists) is worth doing once but must not run in
CI unconditionally.

---

## Explicitly out of scope (don't drift into these)

- **graph / pipeline docs / watch for GitHub** — the matrix marks these `?`
  (unaudited), not `❌`. Audit them first before building anything; they may
  already work since `needs:` parsing is structural.
- **CircleCI `<< parameters.x >>`** — the next parity target after GitHub,
  but its `<< >>` tokens are hostile to YAML parsing and need their own
  round-trip design pass. Separate task.
- **Rewriting `uses:` refs in place** (auto-upgrade). Gap 2 is report-only;
  in-place rewriting has the same manual-edit-safety questions as compile
  output and should reuse that machinery if ever built.
