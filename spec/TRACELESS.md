# TRACELESS — bash2yaml without footprints

> **Status:** Draft proposal
> **Audience:** bash2yaml maintainers, contributors evaluating adoption strategy

## Problem statement

bash2yaml's value prop ("write your CI bash in `.sh` files, get IDE/shellcheck/tests")
is high. Its **adoption cost** is also high, because the default workflow leaves a
visible compilation pipeline in the repo:

- `# DO NOT EDIT — compiled with bash2yaml` headers on generated YAML
- `# >>> BEGIN inline: build.sh` / `# <<< END inline` fence comments
- Sidecar `.hash` files next to every generated file
- An `uncompiled.gitlab-ci.yml` (or `src/`) tree shipping alongside the real one
- A `.bash2yaml.toml` in the repo root
- Pre-commit hooks that gate every commit on `bash2yaml compile`

That's fine when the team has bought in. It's a **showstopper** in two cases:

1. **Probationary use.** A developer wants to try bash2yaml on a real repo to see
   if it pays for itself. The team hasn't agreed to anything yet. The dev
   needs to deliver a normal-looking PR that any teammate can read, edit, and
   merge without learning a new tool first.
2. **Foreign-repo contributions.** A bash2yaml power-user contributes to repos
   they don't own (open-source, partner teams, customer repos). The host repo
   has its own conventions and won't accept bash2yaml artifacts at all. The
   user still wants their own lint/format/test loop locally.

In both cases the user is **allowed** to lint and format their bash — repos
welcome cleaner shell. They are **not allowed** to check in evidence of how
the bash was authored.

This document proposes **traceless mode**: a workflow and supporting CLI in
which bash2yaml runs entirely outside the working tree, leaves no markers in
checked-in files, and produces YAML that is byte-indistinguishable from what
a human would have written.

## Design goals

In priority order:

1. **No checked-in artifacts.** No `.hash` files, no `bash2yaml.toml`, no
   `uncompiled.*.yml`, no `scripts/` directory, no fence comments, no
   "DO NOT EDIT" headers. A reviewer running `git diff` should see only
   normal YAML changes.
2. **Reversible at any moment.** A traceless user can stop using bash2yaml
   tomorrow with no cleanup PR. Conversely, a team can promote a traceless
   workflow to a normal bash2yaml workflow without rewriting history.
3. **Output equivalence with hand-edited YAML.** Compiled output must round-trip
   through normal YAML formatters and human edits without bash2yaml losing
   the thread on the next compile.
4. **Quiet by default.** No log lines mentioning bash2yaml in the generated
   files. No commit messages auto-tagged. No git config touched.
5. **Local-only state.** Anything bash2yaml needs to remember (mappings,
   hashes, source paths) lives outside the working tree, ideally under
   the user's home or under a gitignored sidecar.

Non-goals:

- Hiding bash2yaml from teammates who *opt in* — the normal workflow is fine
  for them, traceless is for the other case.
- Defeating forensic discovery — a determined reviewer comparing bash blocks
  across two PRs could still infer a tool was used. The goal is no
  *gratuitous* signal in the diff.

## The traceless contract

A repo is "traceless-clean" with respect to bash2yaml if all of the following
hold after a compile:

| Surface | Constraint |
|---|---|
| Generated YAML files | No bash2yaml-attributed header. No `BEGIN inline` / `END inline` markers. No `auto-generated` notice unless the user opts in. |
| Repo root | No `.bash2yaml.toml`, no `bash2yaml.toml`. |
| Output dir | No `*.hash` siblings. No `.bash2yaml/` subdirectory. |
| Source tree | No `uncompiled.*.yml`. No tracked `scripts/` directory created by bash2yaml's `init`. (User-authored `scripts/` is fine.) |
| Git config | Untouched. |
| Pre-commit | Either none, or a hook that runs entirely from a non-tracked location. |
| `.gitignore` | bash2yaml may *suggest* additions, but only adds them if the user explicitly opts in via `--gitignore`. |

A `bash2yaml traceless verify` command (see below) checks all of these
and exits non-zero on any violation, suitable for CI on the host repo.

## State storage

bash2yaml currently keeps `.hash` files next to generated files. Traceless
mode needs the same integrity guarantees without on-tree state. The proposal:

- **State directory:** `$XDG_STATE_HOME/bash2yaml/<repo-fingerprint>/`
  (Windows: `%LOCALAPPDATA%\bash2yaml\state\<repo-fingerprint>\`).
  Fingerprint is `sha256(git config --get remote.origin.url || repo abspath)`,
  truncated to 16 hex chars.
- **Contents:** `hashes.json` (a single JSON map of `relpath → sha256`),
  `sources.json` (mapping compiled YAML files to their source `.sh` paths),
  `config.toml` (the equivalent of `.bash2yaml.toml`).
- **Worktree fallback:** if `--state-dir` is passed or `BASH2YAML_STATE_DIR`
  is set, that path wins. If the user prefers gitignored in-tree state,
  they can point it at `.bash2yaml/` and add that to `.gitignore` — but the
  default keeps state out of the repo entirely.
- **Multi-developer caveat:** state is per-machine. Two developers using
  traceless mode on the same repo each have their own hashes. This is fine
  because traceless's drift-detection is for the *single user's* sanity
  ("did I edit the compiled file by mistake?"), not for team-wide enforcement.

## CLI surface

Traceless is a **mode**, not a separate program. Existing commands grow flags;
new commands are added only where existing ones don't cleanly fit.

### New: `bash2yaml traceless`

A subcommand group that bundles the traceless workflow. Subcommands:

| Subcommand | Purpose |
|---|---|
| `traceless init` | Like `init`, but writes state to `$XDG_STATE_HOME` instead of the repo. Does not create a tracked `scripts/` directory. Does not write `.bash2yaml.toml`. |
| `traceless adopt` | One-shot: decompile existing YAML into externally-stored sources, immediately recompile to verify byte-equivalence, then leave the working tree exactly as it was. After this, the user can edit the externally-stored `.sh` files and recompile in place. |
| `traceless compile` | Equivalent to `compile --traceless` (see below). |
| `traceless shred` | Inverse of adopt. Removes all out-of-tree state for the current repo. The working tree is unchanged. |
| `traceless verify` | Checks the traceless contract above. Suitable for the host repo's CI as `bash2yaml traceless verify --strict`. |
| `traceless status` | Shows what bash2yaml *would* do: which YAML files it tracks, where their sources live, whether they're in sync. |
| `traceless edit <yamlfile>` | Opens the externally-stored source `.sh` files for a given compiled YAML in `$EDITOR`. Saves you from remembering the state path. |

### New flags on existing commands

| Command | Flag | Effect |
|---|---|---|
| `compile` | `--traceless` | Implies `--no-header`, `--no-fences`, `--no-hash`, `--state-dir=<auto>`. Reads sources from the state dir, not the working tree. |
| `compile` | `--no-header` | Suppress the `# DO NOT EDIT` header entirely. |
| `compile` | `--no-fences` | Suppress `# >>> BEGIN inline: build.sh` / `# <<< END inline` markers. The inlined bash appears with no attribution. |
| `compile` | `--no-hash` | Don't write `.hash` sidecar files. |
| `compile` | `--header-text <str\|@file>` | Replace the default header with a custom one. `@file` reads from a path. Empty string = same as `--no-header`. |
| `compile` | `--state-dir <path>` | Override where state is stored. |
| `compile` | `--in-place` | Source `.sh` files live outside the tree (state dir); the YAML in the working tree is overwritten in place. No sibling `uncompiled.yml`. |
| `decompile` | `--traceless` | Writes extracted `.sh` files to the state dir, not the working tree. The original YAML is left untouched. |
| `decompile` | `--no-rewrite` | Decompile without modifying the input YAML to point at `.sh` files. (Pairs with `--traceless`.) |
| `init` | `--traceless` | Writes config and directory layout to the state dir. |
| `clean` | `--include-state` | Also clean the state dir (default off — clean is normally a working-tree operation). |
| `detect-drift` | `--traceless` | Reads hashes from the state dir. |
| `install-precommit` | `--traceless` | Installs a hook in `.git/hooks/pre-commit` (which is **not tracked**) rather than configuring `.pre-commit-config.yaml` (which is). |

### New top-level flag: `--quiet-attribution`

Suppresses any text in *any* output (logs, generated files, pre-commit
messages, error reports) that mentions "bash2yaml" by name. The tool still
works; it just doesn't introduce its own brand into the user's terminal or
files. Useful when screen-sharing or pair-programming with a teammate who
doesn't know about the tool yet.

This is distinct from `-q/--quiet`, which suppresses log volume.
`--quiet-attribution` doesn't reduce volume, just removes self-references.

## Settings

### New TOML keys (in state-dir config)

```toml
[traceless]
enabled = true
state_dir = "auto"          # "auto" | absolute path
header = "none"             # "none" | "default" | "custom:<text>" | "file:<path>"
fences = false              # emit BEGIN/END inline markers
write_hashes = false        # write .hash sidecars
quiet_attribution = true    # never print "bash2yaml" in output
gitignore_suggest = false   # suggest .gitignore additions
in_place = true             # overwrite YAML in place rather than emit to out_dir
```

### Environment variables

| Var | Purpose |
|---|---|
| `BASH2YAML_TRACELESS` | `1` to force traceless mode for all commands. |
| `BASH2YAML_STATE_DIR` | Override state directory location. |
| `BASH2YAML_QUIET_ATTRIBUTION` | `1` to never emit "bash2yaml" in output. |
| `BASH2YAML_NO_HEADER` | `1` to suppress headers (a narrower escape hatch than full traceless). |

## Workflows

### Workflow A — Probationary use ("prove value before committing the team")

```bash
# Day 0: grab the existing CI file out into private state.
bash2yaml traceless adopt --in-file .gitlab-ci.yml

# Day 1..N: edit the externally-stored .sh files with full IDE support.
bash2yaml traceless edit .gitlab-ci.yml      # opens build.sh, test.sh in $EDITOR
shellcheck ~/.local/state/bash2yaml/<fp>/scripts/*.sh

# Compile in place. The diff in git is just normal YAML changes.
bash2yaml traceless compile

git diff .gitlab-ci.yml                       # looks like a normal edit
git commit -m "Improve build script error handling"

# At any time, prove cleanliness:
bash2yaml traceless verify --strict
# exit 0 → repo has zero bash2yaml footprint
```

If the team eventually adopts bash2yaml properly, the user runs
`bash2yaml traceless promote` (a future addition) to copy the
externally-stored sources into the repo and switch to the standard workflow.

### Workflow B — Foreign-repo contribution

```bash
# Clone someone else's repo. They've never heard of bash2yaml.
git clone https://github.com/their-org/their-repo
cd their-repo

# One-shot: pull their YAML's bash into a private workspace.
bash2yaml traceless adopt --in-file .github/workflows/ci.yml

# Edit, lint, test the bash with full tooling.
bash2yaml traceless edit .github/workflows/ci.yml

# Compile straight back in. No new files, no marker comments.
bash2yaml traceless compile

# Verify and submit a clean PR.
bash2yaml traceless verify --strict
git diff                                      # only the YAML you intended to change
gh pr create
```

### Workflow C — "Shred-and-go" for a one-line fix

When the user just needs to tweak one bash line in a foreign repo and doesn't
want any persistent state:

```bash
bash2yaml traceless adopt --in-file ci.yml --ephemeral
$EDITOR $(bash2yaml traceless where ci.yml --script build.sh)
bash2yaml traceless compile
bash2yaml traceless shred                     # state dir gone, working tree clean
```

`--ephemeral` marks the state dir for cleanup at the next `shred` (or on
process exit, if the OS supports it). `where` prints the source path of a
named script for shell expansion.

## What changes in compile output

Concrete before/after on the existing `examples/compile` fixture.

**Today:**

```yaml
# DO NOT EDIT
# This is a compiled file, compiled with bash2yaml
# Recompile instead of editing this file.
#
# Compiled with the command:
#     bash2yaml.exe compile --in src --out out

build_cobol_program:
  stage: build
  script: |-
    # >>> BEGIN inline: build.sh
    # The -x flag creates an executable.
    cobc -x -o "${EXECUTABLE_NAME}" "${PROGRAM_NAME}".cbl
    echo "Compilation successful."
    # <<< END inline
```

**With `--traceless`:**

```yaml
build_cobol_program:
  stage: build
  script: |-
    # The -x flag creates an executable.
    cobc -x -o "${EXECUTABLE_NAME}" "${PROGRAM_NAME}".cbl
    echo "Compilation successful."
```

Identical to what a human would have written and committed. The `.hash` file
that would have lived at `out/.gitlab-ci.yml.hash` instead lives at
`$XDG_STATE_HOME/bash2yaml/<fp>/hashes.json`.

## Drift detection without sidecar hashes

Today, `detect-drift` reads `<file>.hash` next to the file. In traceless mode,
it consults the state dir's `hashes.json`. Two implications:

1. **Drift is per-user.** If a teammate edits the compiled YAML by hand, *my*
   bash2yaml will see drift on my next compile but their machine has no
   record. That's fine — traceless explicitly opts out of team-wide
   enforcement.
2. **First compile after a manual edit.** If the user edits the compiled YAML
   directly (e.g., a quick fix during incident response) and then runs
   `traceless compile`, bash2yaml notices the drift and refuses to overwrite
   without `--force` or a prior `traceless reconcile` step. `reconcile`
   re-extracts bash from the on-disk YAML back into the state-dir source
   files, so manual edits aren't lost.

## How `traceless verify` works

`bash2yaml traceless verify [--strict]` walks the working tree and the
configured output paths and asserts:

1. No `.hash` files anywhere in the configured output dir (or, in `--in-place`
   mode, anywhere in the repo).
2. No `bash2yaml.toml` or `.bash2yaml.toml` tracked by git. (Untracked is
   fine.)
3. No `uncompiled.*.yml` tracked by git.
4. No file in the configured output dir contains the strings
   `"compiled with bash2yaml"`, `"BEGIN inline:"`, or `"END inline"` —
   unless `--allow-markers` is passed.
5. `.gitignore` does not contain `# bash2yaml` comments unless the user added
   them by hand (we look for our own auto-added sentinel).
6. `--strict` additionally checks `git ls-files` to make sure none of the
   above are *staged* even if the working tree is clean.

Exit codes: 0 = clean, 1 = violation, 2 = setup error (no state dir found,
nothing to verify against).

This is the command a paranoid user runs in their pre-push hook, and that
the host repo's CI could run as a courtesy check ("we didn't ask, but if
you're using bash2yaml, please use it tracelessly").

## What about precommit?

The current `install-precommit` writes a `.pre-commit-config.yaml` entry,
which is tracked. Traceless can't do that. Instead, `install-precommit
--traceless` writes directly to `.git/hooks/pre-commit` (untracked, per-clone).
The hook content:

```sh
#!/usr/bin/env sh
exec bash2yaml traceless compile --check
```

`--check` mode compiles to a tempdir and diffs against the working tree,
failing the commit if they differ. It does not write to the working tree
during a hook — the user is expected to run `traceless compile` themselves
to update.

## Open questions

- **Promotion path.** Spec includes `traceless promote` as a future
  addition; do we cut it from v1 and ship traceless as one-way? Probably
  yes — promotion is its own design problem (config translation, hash
  format conversion, scripts directory layout choice).
- **Multi-repo state collisions.** Fingerprinting on remote URL collides
  for forks. Should the fingerprint also include the user's checkout path?
  Leaning yes for v1, with `--state-dir` as the escape hatch.
- **Windows path length.** State dir paths can get long on Windows. Should
  we hash the full state subdir name to a short fixed-width directory? Yes
  — fingerprint is already 16 hex chars; flat is fine.
- **Editor integration.** `traceless edit` opens scripts in `$EDITOR`. Do we
  want a long-running watch mode (`traceless watch`) that recompiles on save
  *of the externally-stored sources*? Probably yes; trivial extension of
  the existing `compile --watch`.
- **Discoverability.** A user who only knows the regular `bash2yaml`
  command won't find traceless. Add a top-level mention in `--help` and
  in `bash2yaml doctor`'s "are you in a traceless-friendly repo?" check.

## Scope checklist for v1

Minimum to ship:

- [ ] `compile --traceless` (and the `--no-header`, `--no-fences`,
      `--no-hash`, `--in-place`, `--state-dir` flags it composes from)
- [ ] `decompile --traceless --no-rewrite`
- [ ] `traceless adopt`
- [ ] `traceless compile`
- [ ] `traceless verify`
- [ ] `traceless shred`
- [ ] State-dir storage with `hashes.json` + `sources.json` + `config.toml`
- [ ] `--quiet-attribution` on all commands
- [ ] Docs page (`docs/usage/traceless.md`) and a worked example under
      `examples/traceless/`

Deferred to v2:

- [ ] `traceless promote` (traceless → standard)
- [ ] `traceless watch`
- [ ] `traceless edit` (nice-to-have; users can `cd $(traceless where)` in v1)
- [ ] Pre-commit hook installer with `--traceless`
- [ ] Host-repo CI integration helper (`bash2yaml traceless verify` shipped
      as a GitHub Action / GitLab include)
