# Hardening plan

This review follows the Python 3.11 baseline change and removal of the application plugin system. Items **1, 3, 4, and 6 are implemented**. Items 2, 5, and 7 are intentionally deferred at the owner's request. The findings and acceptance criteria below retain the rationale for each item. Prioritize correctness and preservation of user files before additional features.

## 1. Preserve target behavior in parallel compilation (P1)

**Evidence:** `bash2yaml/commands/compile_all.py`, `run_compile_all`, explicitly passes `None` for the target in multiprocessing arguments. Its comment assumes only GitLab exists, but the package now supports six platforms. The parallel branch activates with at least five files and requested parallelism on a machine with multiple CPUs.

**Work:** Pass the built-in target name to each worker and resolve its adapter in the worker. Carry all effective compile settings explicitly across the process boundary. Avoid relying on inherited global configuration, especially with Windows process spawning.

**Acceptance:** For each platform, compile at least five fixtures sequentially and with two workers. Compare output bytes, validation outcomes, exit status, and dependency tracking. Run this on Windows and Linux.

## 2. Prevent decompilation from overwriting distinct scripts (P1)

**Evidence:** `bash2yaml/commands/decompile_all.py`, `create_script_filename`, lowercases job names and replaces punctuation with hyphens. Names such as `Build` and `build`, or `a:b` and `a-b`, produce the same filename. `extract_script_block` writes the resulting path directly.

**Work:** Allocate filenames for the entire operation before writing. Detect collisions across jobs, script sections, and input YAML files; either fail with both source locations or apply a stable suffix. Check existing user files before replacement.

**Acceptance:** Collision fixtures retain both distinct script bodies; repeated decompilation uses stable names; preexisting unrelated files remain untouched; dry-run reports the same decisions without writing.

## 3. Apply one path boundary to all inliners (P1)

**Evidence:** Bash inlining passes an `allowed_root` to `read_bash_script`. `bash2yaml/commands/compile_not_bash.py`, `resolve_interpreter_target`, instead strips leading characters with `lstrip("./")` and joins the result to the scripts root. This can silently reinterpret paths and does not enforce a resolved containment boundary before reading, including symlink targets.

**Work:** Define the allowed project/source root once and pass it to Bash, interpreter, and artifact readers. Resolve paths, preserve their meaning, then enforce containment. Separate unsupported commands from missing or disallowed file references, with a documented strict policy for CI.

**Acceptance:** Cover parent traversal, absolute paths, Windows drives/UNC paths, symlinks, spaces, Unicode, nested sources, and traceless source roots. Disallowed references must not expose file contents in generated YAML or diagnostics.

## 4. Make output and state updates recoverable (P1)

**Evidence:** `compile_all.py` writes output and hash files separately with `write_text`. `bash2yaml/utils/state_store.py`, `_save_json`, writes directly to the destination, and `save` writes the two state manifests separately. `_load_json` accepts any valid JSON value despite callers expecting a mapping.

**Work:** Render and validate before publication. Write temporary files beside their destinations and replace atomically. Publish success hashes only after output publication. Add a state format version, shape validation, and a clear recovery strategy for interrupted multi-file operations. Serialize concurrent state writers or use a transactional store.

**Acceptance:** Inject write failures and interruptions between publication steps; existing output remains readable, no failed build is marked current, and the next run repairs incomplete state. Exercise malformed JSON, valid non-object JSON, invalid record types, and concurrent writers.

## 5. Make watch mode converge on the final edit (P2)

**Evidence:** `bash2yaml/watch_files.py`, `_RecompileHandler.on_any_event`, drops events inside the debounce window without scheduling a trailing rebuild. Its extension list omits supported interpreter files such as `.py` and `.js`. It also handles arbitrary event types, including filesystem reads on platforms that emit them.

**Work:** Queue a trailing rebuild after a quiet period; retain a dirty flag when edits arrive during compilation. Filter to relevant mutations and account for atomic-save move destinations. Watch supported source dependencies and configuration, and exclude generated output/state.

**Acceptance:** Burst edits, atomic editor saves, source deletion/rename, interpreter edits, and edits during a slow compile all result in output matching the last source state. Reading sources does not trigger an endless rebuild cycle.

## 6. Make platform selection and errors deterministic (P2)

**Evidence:** `bash2yaml/targets/__init__.py`, `detect_target`, appends filename and directory matches separately. A single adapter matching both can be reported as ambiguous: `semaphore.yml` with directory `.semaphore` reproduces this. The preserved automatic Git operation logs failures while the main command can still return success.

**Work:** Deduplicate target matches by name and fail clearly on genuine ambiguity rather than silently choosing the GitLab fallback. Decide and document whether requested automatic Git failures fail the command. Audit broad exception handlers for cases that turn incomplete work into successful exit codes.

**Acceptance:** Matching filename and directory select one target; conflicting platforms produce an actionable diagnostic; invalid configuration and failed requested actions have documented nonzero statuses. Exercise CLI, GUI, and TUI dispatch consistently.

## 7. Make quality gates reproducible and representative (P2)

**Evidence:** `Makefile` refreshes unpinned schemas during `check`, suppresses download failures, and invokes formatting through its lint prerequisites. Despite contributor instructions, `check` does not depend on the pre-commit target. Tests rewrite at least the tracked stress-scenario output fixture. The coverage threshold permits approximately half the package to remain uncovered.

**Work:** Separate read-only checks from formatting and schema refresh. Pin schema provenance and review updates separately. Make pre-commit an explicit gate. Move every mutable scenario into `tmp_path`. Add core-only installed-wheel tests without development dependencies, alongside extras tests and the Python 3.11/3.13/3.14 matrix. Raise coverage by targeting failure paths and round-trip behavior, rather than a blanket percentage increase.

**Acceptance:** A complete check succeeds offline after dependency installation and leaves `git status` unchanged. Broken subprocesses fail the gate. Installed core and extras distributions compile representative fixtures for all six targets. Property tests preserve YAML tags, anchors, expressions, multiline shell semantics, and compile/decompile idempotence.

## Suggested sequence

1. Fix parallel target propagation and decompile filename collisions, each with reproducing tests.
1. Standardize path handling and atomic publication/state recovery.
1. Repair watcher convergence and clarify selection/error behavior.
1. Make checks read-only and add the cross-platform, installed-distribution, and round-trip coverage above.

For each step, ship a focused change with regression tests and run the complete quality gate plus the supported-version matrix. Reassess remaining risks after the first two steps rather than expanding the feature surface.
