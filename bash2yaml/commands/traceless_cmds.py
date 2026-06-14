"""Traceless mode: run bash2yaml with zero footprint in the working tree.

See ``spec/TRACELESS.md`` for the full design. The short version: sources and
state live out-of-tree under a per-repo state directory; compiled YAML carries
no headers, fences, or hash sidecars; a reviewer sees only normal YAML changes.

Subcommands:

- ``adopt``   — decompile existing YAML into the state dir, verify the round
  trip, leave the working tree untouched.
- ``compile`` — recompile adopted files in place from state-dir sources.
- ``verify``  — assert the traceless contract holds (exit 0 clean / 1
  violation / 2 setup error).
- ``shred``   — remove all out-of-tree state for this repo.
"""

from __future__ import annotations

import logging
import subprocess  # nosec
from pathlib import Path
from typing import Any

from bash2yaml.commands.compile_all import (
    CompileOptions,
    inline_gitlab_scripts,
    write_compiled_file_no_sidecar,
)
from bash2yaml.commands.decompile_all import run_decompile_traceless
from bash2yaml.errors.exceptions import Bash2YamlError, NotFound
from bash2yaml.targets.base import BaseTarget
from bash2yaml.utils import diff_helpers
from bash2yaml.utils.dotenv import parse_env_file
from bash2yaml.utils.state_store import StateStore, find_repo_root
from bash2yaml.utils.utils import remove_leading_blank_lines, short_path

logger = logging.getLogger(__name__)

__all__ = [
    "run_traceless_adopt",
    "run_traceless_compile",
    "run_traceless_shred",
    "run_traceless_verify",
]

# Marker strings whose presence in checked-in YAML violates the contract.
FORBIDDEN_MARKERS = ("compiled with bash2yaml", "BEGIN inline:", "END inline")
# Sentinel we would use if we ever auto-added .gitignore entries. Hand-written
# "# bash2yaml" comments are the user's business; this exact line is ours.
GITIGNORE_AUTO_SENTINEL = "# bash2yaml (auto-added)"

VERIFY_OK = 0
VERIFY_VIOLATION = 1
VERIFY_SETUP_ERROR = 2


def _require_repo_root(start: Path | None = None) -> Path:
    repo_root = find_repo_root(start)
    if repo_root is None:
        raise NotFound(Path.cwd())
    return repo_root


def _compile_state_source(
    store: StateStore,
    rel: str,
    target: BaseTarget | None,
) -> str:
    """Compile one adopted file from its state-dir sources; return the YAML text."""
    info = store.sources.get(rel)
    if not info:
        raise Bash2YamlError(f"'{rel}' is not adopted; run `traceless adopt --in-file {rel}` first.")
    uncompiled_path = store.state_dir / info["uncompiled"]
    if not uncompiled_path.is_file():
        raise Bash2YamlError(
            f"State-dir source for '{rel}' is missing ({uncompiled_path}). Re-run `traceless adopt`."
        )

    input_dir = uncompiled_path.parent
    raw_text = uncompiled_path.read_text(encoding="utf-8")

    global_vars: dict[str, str] = {}
    global_vars_path = input_dir / "global_variables.sh"
    if global_vars_path.is_file():
        global_vars = parse_env_file(global_vars_path.read_text(encoding="utf-8"))

    inlined, compiled_text = inline_gitlab_scripts(
        raw_text, input_dir, global_vars, input_dir, target=target, emit_fences=False
    )
    content = compiled_text if inlined > 0 else raw_text
    return remove_leading_blank_lines(content)


# ---------------------------------------------------------------------------
# adopt
# ---------------------------------------------------------------------------


def run_traceless_adopt(
    in_file: Path,
    state_dir: str | Path | None = None,
    target: BaseTarget | None = None,
    dry_run: bool = False,
) -> int:
    """One-shot adoption: decompile *in_file* into the state dir, then recompile
    and compare against the original to verify the round trip.

    The working tree is left exactly as it was. Returns 0 on success.
    """
    in_file = in_file.resolve()
    if not in_file.is_file():
        raise NotFound(in_file)

    repo_root = _require_repo_root(in_file.parent)
    store = StateStore.for_repo(repo_root, state_dir)
    original_text = in_file.read_text(encoding="utf-8")

    jobs, created, dest_dir = run_decompile_traceless(
        input_yaml_path=in_file,
        state_dir=state_dir,
        dry_run=dry_run,
        target=target,
        rewrite_yaml=True,
    )
    if dry_run:
        print(f"[DRY RUN] Would adopt {short_path(in_file)}: {jobs} job(s), {created} extracted file(s).")
        return 0

    rel = str(in_file.relative_to(repo_root)).replace("\\", "/")
    print(f"Adopted {rel}: {jobs} job(s), {created} file(s) extracted to {dest_dir}")

    # Round-trip check: recompiling the extracted sources should reproduce the file.
    recompiled = _compile_state_source(store, rel, target)
    byte_identical = recompiled == original_text
    info = store.sources.get(rel, {})
    info["byte_identical"] = byte_identical
    store.record_source(rel, info)
    store.save()

    if byte_identical:
        print("Round trip verified: recompiling reproduces the file byte-for-byte.")
    else:
        diff_text = diff_helpers.unified_diff(original_text, recompiled, in_file, "original", "recompiled")
        stats = diff_helpers.diff_stats(diff_text)
        print(
            "Note: recompiling normalizes formatting "
            f"({stats.changed} line(s) will change on the first compile: "
            f"+{stats.insertions}, -{stats.deletions})."
        )
        print("The working tree was NOT modified. The first `traceless compile` will apply the normalization.")
    print(f"State directory: {store.state_dir}")
    return 0


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------


def run_traceless_compile(
    state_dir: str | Path | None = None,
    target_resolver: Any = None,
    check: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    """Recompile every adopted file from state-dir sources, in place.

    Args:
        state_dir: Optional state dir override.
        target_resolver: Callable ``(filename: str) -> BaseTarget | None`` used to
            pick the platform adapter per file (None = legacy GitLab handling).
        check: Compile to memory and diff against the working tree instead of
            writing; non-zero exit when any file is out of date (pre-commit use).
        force: Overwrite even when the on-disk file drifted from the last record.
        dry_run: Report what would be written without writing.

    Returns 0 on success; 1 when ``--check`` found differences.
    """
    repo_root = _require_repo_root()
    store = StateStore.for_repo(repo_root, state_dir)
    if not store.sources:
        raise Bash2YamlError(
            f"No adopted files found in state directory ({store.state_dir}). Run `traceless adopt` first."
        )

    options = CompileOptions.traceless(state_dir=str(store.state_dir), force=force)
    out_of_date = 0
    written = 0

    for rel in sorted(store.sources):
        target = target_resolver(Path(rel).name) if target_resolver else None
        compiled = _compile_state_source(store, rel, target)
        out_path = repo_root / rel

        if check or dry_run:
            current = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
            if current != compiled:
                out_of_date += 1
                label = "[DRY RUN] Would rewrite" if dry_run else "Out of date:"
                print(f"{label} {rel}")
            continue

        if write_compiled_file_no_sidecar(out_path, compiled, repo_root, target, options):
            written += 1
            print(f"Compiled {rel}")
        else:
            logger.info("Up to date: %s", rel)

    if check:
        if out_of_date:
            print(f"{out_of_date} file(s) differ from their compiled sources.")
            return 1
        print("All adopted files are up to date.")
        return 0
    if not dry_run:
        print(f"Done. {written} file(s) written, {len(store.sources) - written} already up to date.")
    return 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def _git_ls_files(repo_root: Path) -> list[str] | None:
    try:
        result = subprocess.run(  # nosec
            ["git", "ls-files"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("git ls-files failed: %s", e)
        return None
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _iter_worktree_files(repo_root: Path):
    for path in repo_root.rglob("*"):
        if ".git" in path.parts:
            continue
        yield path


def run_traceless_verify(
    repo_root: Path | None = None,
    strict: bool = False,
    allow_markers: bool = False,
) -> int:
    """Check the traceless contract; print violations.

    Returns 0 when clean, 1 on any violation, 2 on setup error (not a git repo).
    """
    root = repo_root.resolve() if repo_root else find_repo_root()
    if root is None or not root.is_dir():
        print("Setup error: not inside a git repository (nothing to verify against).")
        return VERIFY_SETUP_ERROR

    violations: list[str] = []

    # 1 & contract table: no .hash sidecars, no .bash2yaml/ state dirs in the tree.
    for path in _iter_worktree_files(root):
        rel = str(path.relative_to(root)).replace("\\", "/")
        if path.is_dir():
            if path.name == ".bash2yaml":
                violations.append(f"state directory in working tree: {rel}/")
            continue
        if path.name.endswith(".hash"):
            violations.append(f"hash sidecar in working tree: {rel}")
        elif not allow_markers and path.suffix in (".yml", ".yaml"):
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for marker in FORBIDDEN_MARKERS:
                if marker in content:
                    violations.append(f"attribution marker {marker!r} in {rel}")

    # 2 & 3: config files / uncompiled trees must not be *tracked* (untracked is fine).
    tracked = _git_ls_files(root)
    if tracked is None:
        print("Setup error: `git ls-files` failed; cannot check tracked files.")
        return VERIFY_SETUP_ERROR
    for tracked_file in tracked:
        name = Path(tracked_file).name
        if name in ("bash2yaml.toml", ".bash2yaml.toml"):
            violations.append(f"tracked config file: {tracked_file}")
        elif name.startswith("uncompiled.") and name.endswith((".yml", ".yaml")):
            violations.append(f"tracked uncompiled source: {tracked_file}")
        elif strict and (name.endswith(".hash") or ".bash2yaml/" in tracked_file.replace("\\", "/")):
            # Strict: staged/tracked artifacts count even if the worktree copy is gone.
            violations.append(f"tracked bash2yaml artifact: {tracked_file}")

    # 5: .gitignore should not carry our auto-added sentinel.
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        try:
            if GITIGNORE_AUTO_SENTINEL in gitignore.read_text(encoding="utf-8"):
                violations.append(f".gitignore contains auto-added entries ({GITIGNORE_AUTO_SENTINEL!r})")
        except (OSError, UnicodeDecodeError):
            pass

    if violations:
        print(f"Traceless contract violated ({len(violations)} finding(s)):")
        for v in violations:
            print(f"  - {v}")
        return VERIFY_VIOLATION

    print("Traceless contract holds: no compilation footprint found in the working tree.")
    return VERIFY_OK


# ---------------------------------------------------------------------------
# shred
# ---------------------------------------------------------------------------


def run_traceless_shred(state_dir: str | Path | None = None, dry_run: bool = False) -> int:
    """Remove all out-of-tree state for the current repo. The working tree is unchanged."""
    repo_root = _require_repo_root()
    store = StateStore.for_repo(repo_root, state_dir)
    if not store.exists():
        print(f"No state directory found at {store.state_dir}; nothing to shred.")
        return 0
    if dry_run:
        print(f"[DRY RUN] Would remove state directory: {store.state_dir}")
        return 0
    store.shred()
    print(f"Removed state directory: {store.state_dir}")
    print("The working tree was not touched.")
    return 0
