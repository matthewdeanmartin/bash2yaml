# Traceless mode example

This directory plays the role of **someone else's repo**: it has a normal,
hand-written `.gitlab-ci.yml` and has never heard of bash2yaml. The walkthrough
below edits its CI bash with full shell tooling while leaving zero tool
footprint in the tree — no headers, no fence comments, no `.hash` sidecars,
no config files.

Full docs: `docs/usage/traceless.md`. Design: `spec/TRACELESS.md`.

## Walkthrough

```bash
./walkthrough.sh
```

or step by step (run from this directory; it must be inside a git repo — the
bash2yaml repo itself works fine):

```bash
# Keep the example self-contained: put state in a local temp dir instead of
# your real per-user state home. Omit this in real use.
export BASH2YAML_STATE_DIR="$(mktemp -d)"

# 1. Adopt: extract the bash out of the YAML into private state.
#    The working tree is NOT modified.
bash2yaml traceless adopt --in-file .gitlab-ci.yml
git status --porcelain .        # -> clean

# 2. Edit the extracted scripts with real shell tooling.
ls "$BASH2YAML_STATE_DIR/sources"     # build_job.sh, test_job.sh, ...
shellcheck "$BASH2YAML_STATE_DIR"/sources/*.sh
sed -i 's/make test/make test VERBOSE=1/' "$BASH2YAML_STATE_DIR/sources/test_job.sh"

# 3. Compile back in place. The diff is an ordinary YAML edit.
bash2yaml traceless compile
git diff .gitlab-ci.yml

# 4. Prove there is no tool footprint anywhere in the repo.
bash2yaml traceless verify --strict   # exit 0

# 5. Done? Remove all state. The repo keeps your compiled changes.
bash2yaml traceless shred
```

## What to notice

- After `adopt`, `git status` is clean — adoption is read-only.
- The compiled YAML has no `# DO NOT EDIT` banner, no
  `# >>> BEGIN inline:` fences, and no `.hash` sibling. It is
  indistinguishable from a hand edit (the first compile normalizes
  formatting, e.g. multi-line `script:` lists become a `|-` literal block;
  `adopt` reports exactly how many lines that will touch).
- If you hand-edit `.gitlab-ci.yml` after adopting, the next
  `traceless compile` refuses to overwrite it (use `--force` to discard the
  hand edit, or fold it into the state-dir sources).
- `traceless verify --strict` is the command a cautious user puts in a
  pre-push hook.
