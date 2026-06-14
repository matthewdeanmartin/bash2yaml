# Traceless mode

Traceless mode runs bash2yaml with **zero footprint in the working tree**.
Sources, hashes, and config live in a per-repo state directory under your home
directory; compiled YAML carries no headers, no `BEGIN/END inline` fences, and
no `.hash` sidecars. A teammate reviewing your PR sees only normal,
hand-written-looking YAML.

It is an **optional workflow** — it does not replace the standard compile
workflow. It exists for two situations:

1. **Probationary use.** You want to try bash2yaml on a real repo before the
   team has agreed to adopt it. Your PRs must look like ordinary YAML edits.
2. **Foreign-repo contributions.** You contribute to repos you don't own.
   The host repo has its own conventions and won't accept tool artifacts, but
   nobody objects to cleaner bash.

The full design is in `spec/TRACELESS.md`.

## Quick start

```bash
# One-shot: pull the existing CI file's bash into private, out-of-tree state.
bash2yaml traceless adopt --in-file .gitlab-ci.yml
# -> reports the state directory and whether the round trip is byte-identical

# Edit the extracted .sh files with full IDE/shellcheck support.
# adopt prints the state directory; the scripts live under <state-dir>/sources/
shellcheck ~/.local/state/bash2yaml/<fingerprint>/sources/*.sh

# Compile back in place. The git diff is just a normal YAML change.
bash2yaml traceless compile
git diff .gitlab-ci.yml

# Prove the repo is clean of any tool footprint:
bash2yaml traceless verify --strict   # exit 0 = clean

# Done experimenting? Remove all state. The repo is untouched.
bash2yaml traceless shred
```

## Where state lives

| Platform | Default location |
|---|---|
| Linux / macOS | `$XDG_STATE_HOME/bash2yaml/<fingerprint>/` (default `~/.local/state/bash2yaml/<fingerprint>/`) |
| Windows | `%LOCALAPPDATA%\bash2yaml\state\<fingerprint>\` |

The fingerprint is a 16-hex-char hash of the repo's `remote.origin.url` plus
the checkout path, so forks and multiple clones don't collide. Override the
location with `--state-dir` or `BASH2YAML_STATE_DIR`.

Inside the state directory:

- `hashes.json` — repo-relative path → sha256 of the last compiled content
  (replaces `.hash` sidecars)
- `sources.json` — which YAML files are adopted and where their sources live
- `sources/` — the uncompiled YAML and extracted `.sh` files
- `config.toml` — optional, the equivalent of `.bash2yaml.toml`

State is **per-machine and per-user**. Drift detection in traceless mode is
for your own sanity ("did I edit the compiled file by mistake?"), not
team-wide enforcement.

## Subcommands

| Command | Purpose |
|---|---|
| `traceless adopt --in-file F` | Decompile `F` into the state dir, recompile, and report whether the round trip is byte-identical. The working tree is never modified. |
| `traceless compile` | Recompile every adopted file in place from state-dir sources. Refuses to clobber a manually edited file unless `--force`. `--check` compiles to memory and exits 1 if anything is out of date (pre-commit friendly). |
| `traceless verify` | Assert the traceless contract: no `.hash` files, no `.bash2yaml/` dirs, no tracked `bash2yaml.toml` / `uncompiled.*.yml`, no attribution markers in YAML. Exit codes: 0 clean, 1 violation, 2 setup error. `--strict` also checks files tracked in git. |
| `traceless shred` | Remove all out-of-tree state for this repo. Working tree unchanged. |

## Composable compile flags

`--traceless` on `compile` is a macro for individually available flags:

| Flag | Effect |
|---|---|
| `--no-header` | No `# DO NOT EDIT` banner. (`BASH2YAML_NO_HEADER=1` also works.) |
| `--no-fences` | No `# >>> BEGIN inline:` / `# <<< END inline` markers. |
| `--no-hash` | No `.hash` sidecars. Integrity tracking moves to the state dir when one is configured; without one it is skipped (with a warning). |
| `--in-place` | The output directory is a live tree: skip the stray-file halt. |
| `--state-dir P` | Where out-of-tree state lives. |

`decompile --traceless` extracts `.sh` sources into the state dir without
touching the repo; add `--no-rewrite` to skip producing a rewritten YAML
entirely.

## Quiet attribution

`--quiet-attribution` (any command, or `BASH2YAML_QUIET_ATTRIBUTION=1`)
removes every mention of the tool's name from logs, console output, and
generated headers — useful when screen-sharing with someone who hasn't met
the tool yet. This is orthogonal to `-q/--quiet`, which reduces volume.

## Drift and manual edits

If you (or a teammate) edit a compiled YAML file directly, the next
`traceless compile` notices that the file no longer matches its recorded
hash and **refuses to overwrite** it. Your options:

- fold the manual change into the state-dir source scripts, re-adopt, or
- discard the manual change with `traceless compile --force`.

## What's deferred to v2

`traceless promote` (convert to the standard workflow), `traceless watch`,
`traceless edit`, a `--traceless` pre-commit installer, and a host-CI verify
helper. See the scope checklist in `spec/TRACELESS.md`.

## Worked example

See `examples/traceless/` for a copy-paste walkthrough on a tiny repo.
