# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- GitLab CI/CD component template support (`spec:inputs`). Compile, decompile,
  and validate now handle the multi-document layout: the `spec:` header
  round-trips byte-identically, the body is compiled and schema-validated on
  its own, and the header is validated against the `spec:inputs` shape.
- `$[[ inputs.x ]]` interpolation passes through compilation verbatim.
  Interpolation inside `.sh` source files is opt-in via
  `# Pragma: gitlab-interpolation` (the pragma line is stripped from compiled
  output; interpolation without the pragma warns). Decompile adds the pragma
  automatically when extracted script lines contain interpolation.
- `bash2yaml init --component NAME` non-interactively scaffolds a component
  repo (`src/NAME/template.yml` + `src/scripts/NAME.sh`, compiled to
  `templates/NAME/template.yml`).
- `bash2yaml doctor` reports GitLab component templates detected in the input
  directory.
- Worked example under `examples/gitlab-component/` and a docs page
  (`docs/usage/components.md`).

## [0.11.1] - 2026-04-15

### Fixed

- Gets schema from package resource when network not available.
- Documentation updates.

## [0.11.0] - 2025-03-16

### Changed

- Published under new name bash2yaml.

## [0.10.0] - 2025-03-15

### Changed

- Renamed bash2gitlab to bash2yaml. GitLab is a trademark subject to GitLab's trademark policies. The package will now be published as bash2yaml with support for GitHub Actions and other bash-in-yaml build scripts. bash2gitlab will remain on PyPI but receive no further updates.

## [0.9.10] - 2025-11-29

### Added

- Python 3.14 support.
- Pragma: inline-artifact support.
- `--totalhelp` switch to list all help text.

## [0.9.9] - 2025-09-29

### Added

- `autogit` command and associated switches.

### Fixed

- Included missing GitLab library dependency.

## [0.9.8] - 2025-09-04

### Added

- `check-pins` command to attempt to upgrade `include:` elements to the latest hash or git tag.

### Fixed

- Wrong bash return value for `detect-uncompiled`.
- Fixed other ad hoc return values.

## [0.9.7] - 2025-09-01

### Fixed

- Improved performance via lazy loading and rtoml.
- Fixed performance and caching logic for the update checker.

## [0.9.6] - 2025-09-01

### Fixed

- JSON schema now loaded from cache, then URL, then bundled resource.
- Prime cache before attempting to validate on multiple threads.

## [0.9.5] - 2025-08-28

### Fixed

- Restored backwards compatibility for Python 3.8 and earlier supported versions.

## [0.9.4] - 2025-08-28

### Added

- New `validate` command to validate YAML against JSON schema without requiring a compile step.

### Changed

- Added dependencies on orjson and urllib3 for speed, and tomli for backwards compatibility.

## [0.9.3] - 2025-08-27

### Fixed

- Detect drift failed on argument parse. Validated with more comprehensive basic_check.sh test.

## [0.9.2] - 2025-08-23

### Fixed

- Replaced Python exceptions in CLI code with sys.exit and numeric error codes for bash-style error handling.
- Improved error reporting when running gui/tui/interactive without installing `[all]` extras.

## [0.9.1] - 2025-08-22

### Fixed

- Core mode is less likely to fail due to import errors. Install help is now more compact.
- `doctor` command is now functional.

## [0.9.0] - 2025-08-22

### Added

- CLI option for `bash2gitlab run --in-file .gitlab-ci.yml` for best-effort local pipeline execution.

### Changed

- Installation split into `bash2gitlab` for core use on CI/build servers and `bash2gitlab[all]` for all commands on a local machine, reducing supply chain risk.

## [0.8.22] - 2025-08-21

### Added

- Best-effort local runner to execute a `.gitlab-ci.yml` without many CI features.

### Changed

- Map deploy writes to multiple folders.
- Map commit gathers from multiple folders but does not yet handle conflicts.

## [0.8.21] - 2025-08-20

### Added

- `# Pragma: do-not-validate-schema` for `!reference` code to skip schema validation before GitLab merges templates.

## [0.8.20] - 2025-08-20

### Added

- YAML validation against GitLab's JSON schema on every compile.

### Fixed

- Fixed regression where stages were serialized as string blocks instead of lists.

## [0.8.19] - 2025-08-19

### Added

- Compile now skips unchanged files when no source files in the input folder have changed since last compile.

### Fixed

- Fixed regression where scripts were serialized as quoted lists again. Added comprehensive unit tests.

## [0.8.18] - 2025-08-19

### Fixed

- Fixed variable lists being serialized as string blocks and `!reference` tags being flattened into plain lists.

## [0.8.17] - 2025-08-17

### Fixed

- Graph command failed to retry other renderers on error.
- Graph command failed on UTF-8 encoding error.
- Removed color logging from GUI/TUI Popen calls where it is not useful.
- Lint command now correctly reads `gitlab_url` from config.
- Fixed Pragma feature behavior.
- Fixed tkinter tab switching when a command is run.

## [0.8.16] - 2025-08-17

### Changed

- Updated documentation, docstrings, and help text.
- `init` command now covers all configuration options.

## [0.8.15] - 2025-08-16

### Added

- Interactive mode via `bash2gitlab-interactive` command.
- GUI via `bash2gitlab-gui` command.
- Pragma commands for inline control: `do-not-inline`, `do-not-inline-next-line`, `start-do-not-inline`, `end-do-not-inline`, and `allow-outside-root`.

### Changed

- `shred` command renamed to `decompile`.
- Config updated to support storing nearly all command options in the config file.

## [0.8.14] - 2025-08-16

### Added

- Basic Textual TUI to mirror the CLI interface.
- Makefile generation for the decompile command.

## [0.8.13] - 2025-08-15

### Changed

- `graph` command now attempts alternate graphing styles when Graphviz is not available.

### Fixed

- Fixed incorrect CLI argument validation in the decompile command.

## [0.8.12] - 2025-08-14

### Added

- `graph` command to generate a graph of inline relationships.
- `doctor` command for environment diagnostics.
- `show-config` command to display resolved cascading configuration.

### Fixed

- `decompile` now writes output to a folder.
- `decompile` accepts either `--in-file` or `--in-folder`.
- `decompile` records `!reference [.job, key]` as a bash comment.
- `decompile` now logs with relative paths.
- `decompile` now resolves paths relative to the YAML file rather than cwd.
- Fixed leading `.` being stripped from output file names.

## [0.8.11] - 2025-08-14

### Added

- Install and uninstall commands for git pre-commit hooks to compile before every commit.
- Pluggy support for plugins.

### Changed

- Inline support extended to a much larger set of script languages using variations on `interpreter -c "..."`.

## [0.8.10] - 2025-08-11

### Fixed

- Minimized all "script as YAML lists" serialization because it is incompatible with line continuation characters. No version of bash2gitlab before 0.8.10 should be used.

## [0.8.9] - 2025-08-11

### Fixed

- Fixed loss of all newlines in compiled scripts.

## [0.8.8] - 2025-08-11

### Added

- Support for inlining scripts in other languages such as Python using `python -c`.

### Fixed

- Force a trailing newline at the end of any compiled script.
- Minimize bash written in `- code` list format to reduce quoting problems.
- Quote strings more aggressively to avoid YAML serialization issues.

## [0.8.7] - 2025-08-10

### Added

- `clean` command to remove only unmodified files from the output folder.
- Check for stray files in the output folder before compiling.
- `lint` command (beta).

### Changed

- File invocations followed by a comment are now detected.
- Removed the separate concept of script folder and template folder in favor of input folder and output folder.

### Removed

- Global variable file feature removed; it was broken and needs a redesign.

### Fixed

- Output files are no longer rewritten when there are no changes.

## [0.8.6] - 2025-08-09

### Added

- Map commit CLI command.
- Suggestions displayed on incorrect CLI command.

### Changed

- Map deploy and map commit are now restricted to `.sh`, `.ps1`, and `.y[a]ml` files.

## [0.8.5] - 2025-08-08

### Added

- Map deploy command started.

### Changed

- Discourage excessive quoting in generated output.

### Fixed

- Gracefully degrade when generated YAML has been manually changed to invalid YAML.

## [0.8.4] - 2025-08-06

### Added

- Shows the command used to generate output in the file header.
- `detect-drift` command to complement drift detection that runs at compile time.

### Fixed

- Fixed bug that stringified certain complex values in YAML maps.

## [0.8.3] - 2025-08-05

### Added

- Basic PowerShell (.ps1) file support.

### Fixed

- Fixed bug with copy2local.

## [0.8.2] - 2025-08-05

### Added

- Checks for an updated package on PyPI.

### Changed

- `copy2local` now copies the contents of the source folder directly to the destination folder to reduce nesting.

## [0.8.1] - 2025-08-05

### Added

- Improved logging output.

## [0.8.0] - 2025-08-04

### Added

- Inlines bash scripts using the same logic as YAML inlining. Detects `source script.sh` and inlines the referenced file.

### Changed

- `clone2local` renamed to `copy2local`, now using archive and copy commands to bring part of a remote repo into a dependent repo for testing.

### Fixed

- Multiple scripts in a script list were all being overwritten by the last script.

## [0.7.0] - 2025-08-02

### Added

- Started work on a `copy2local` feature to get scripts into dependent repos for testing.

### Removed

- Removed the `--format` option. All major YAML formatting tools are in various states of unsupported behavior that cause failures unrelated to bash2yaml output. Use your preferred orchestration tool (make, just, etc.) to invoke a YAML formatter of your choice.

## [0.6.0] - 2025-07-30

### Changed

- Hash is now a base64 encode of the whole YAML document so reformats involving more than whitespace changes are detected correctly.

### Fixed

- Loosely detect anchors (assumes all hashes with a list value and `./script.sh` pattern are script anchors).
- Detect jobs that contain only `before_script` or `after_script`.

## [0.5.1] - 2025-07-30

### Fixed

- Preserve long lines in compiled output.
- Remove leading blank lines from scripts to avoid indentation indicators such as `|2-`.

## [0.5.0] - 2025-07-29

### Added

- Started a feature to detect modification of generated files; currently warns but does not stop compilation.

### Fixed

- Subfolders containing YAML files are now processed.

## [0.4.1] - 2025-07-27

### Fixed

- Command-line aliases are now `bash2gitlab` and `b2gl`. Previously contained copy-paste errors.

## [0.4.0] - 2025-07-27

### Added

- Watch mode (`--watch`) to recompile on file changes.
- `decompile` supports job-level variables.
- `decompile` automatically generates an if-block to include job-level and global variables.
- `decompile` generates a mock CI variables file.
- `init` command to generate a config file.

## [0.3.0] - 2025-07-27

### Added

- Support for TOML config file or environment variable config as an alternative to CLI switches.

### Fixed

- Python 3.14 support fixed.

## [0.2.0] - 2025-07-27

### Added

- `decompile` command to turn pre-existing bash-in-yaml pipeline templates into shell files and YAML.

## [0.1.0] - 2025-07-26

### Added

- `compile` command.
- Verbose and quiet logging modes.
- CLI interface.
- Support for simple input/output project structure.
- Support for organizing scripts and templates into a scripts or templates folder.

[0.11.1]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.10...v0.10.0
[0.9.10]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.9...v0.9.10
[0.9.9]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.8...v0.9.9
[0.9.8]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.7...v0.9.8
[0.9.7]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.6...v0.9.7
[0.9.6]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.5...v0.9.6
[0.9.5]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.4...v0.9.5
[0.9.4]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.3...v0.9.4
[0.9.3]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.22...v0.9.0
[0.8.22]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.21...v0.8.22
[0.8.21]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.20...v0.8.21
[0.8.20]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.19...v0.8.20
[0.8.19]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.18...v0.8.19
[0.8.18]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.17...v0.8.18
[0.8.17]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.16...v0.8.17
[0.8.16]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.15...v0.8.16
[0.8.15]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.14...v0.8.15
[0.8.14]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.13...v0.8.14
[0.8.13]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.12...v0.8.13
[0.8.12]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.11...v0.8.12
[0.8.11]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.10...v0.8.11
[0.8.10]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.9...v0.8.10
[0.8.9]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.8...v0.8.9
[0.8.8]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.7...v0.8.8
[0.8.7]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.6...v0.8.7
[0.8.6]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.5...v0.8.6
[0.8.5]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.4...v0.8.5
[0.8.4]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.3...v0.8.4
[0.8.3]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.2...v0.8.3
[0.8.2]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/matthewdeanmartin/bash2yaml/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/matthewdeanmartin/bash2yaml/releases/tag/v0.1.0
