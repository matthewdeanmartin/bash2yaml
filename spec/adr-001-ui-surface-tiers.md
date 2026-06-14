# ADR-001: UI surface support tiers

> **Status:** Accepted (2026-06-10)
> **Context:** Roadmap Phase 3, item 4 ("surface triage")

## Context

bash2yaml has five user-facing surfaces: the CLI (`bash2yaml` / `b2y`), the
Rich-based interactive Q&A (`bash2yaml-interactive`), the Textual TUI
(`bash2yaml-tui`), the tkinter GUI (`bash2yaml-gui`), and a web UI (`web/`).
Per `docs_todo/pain_points.md`, the interactive CLI, GUI, and TUI lag behind
the main app, and silently maintaining five half-finished UIs misleads users
and burns maintenance time on every new command.

## Decision

| Tier | Surface | Commitment |
|------|---------|-----------|
| 1 | **CLI** | Full support. Every command, flag, and exit-code contract lands here first. |
| 1 | **Interactive** (`bash2yaml-interactive`) | Full support. Menu coverage is kept in sync with the CLI command list; a missing command is a bug. |
| 2 | **GUI** (tkinter, `bash2yaml-gui`) | Supported but allowed to lag. New commands appear on a best-effort basis. Known issues stay tracked, not silently shipped. |
| 3 | **TUI** (`bash2yaml-tui`) and **web** (`web/`) | Experimental. Clearly labeled as such in their startup output and docs. No coverage guarantees; may be demoted/removed without a deprecation cycle. |

## Consequences

- New CLI commands must be added to the interactive menu in the same change
  (Phase 4's `traceless` group is the first instance of this rule).
- TUI and web banners/docs say "experimental" so users are not surprised by
  missing commands.
- GUI gets no catch-up work in Phase 3 (explicit roadmap decision); its gaps
  are acceptable for tier 2.
- Bug reports against tier-3 surfaces can be triaged as "experimental,
  contributions welcome" without guilt.
