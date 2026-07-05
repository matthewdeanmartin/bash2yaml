"""Support for GitLab CI/CD component templates (``spec:inputs``).

A GitLab component template is a *multi-document* YAML file: a ``spec:``
header document, a ``---`` separator, then the pipeline body. Example::

    spec:
      inputs:
        stage:
          default: test
    ---
    "$[[ inputs.job-prefix ]]-scan":
      stage: $[[ inputs.stage ]]
      script:
        - ./scripts/scan.sh

bash2yaml never evaluates ``$[[ inputs.x ]]`` interpolation — GitLab does
that at include time. The compiler's job is to leave the header and every
interpolation span byte-for-byte intact while inlining scripts into the body.

This module is the single place that knows how to split a component template
into (header, body), validate the ``spec:`` header shape, and detect
interpolation tokens. It must not import from ``validate_pipeline`` or the
``commands`` package (they import us).
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

logger = logging.getLogger(__name__)

__all__ = [
    "ComponentTemplate",
    "split_component_template",
    "is_component_template",
    "validate_spec_header",
    "contains_interpolation",
    "INTERPOLATION_REGEX",
    "INTERPOLATION_PRAGMA_REGEX",
    "strip_interpolation_pragma_lines",
    "find_component_templates",
]

# A `$[[ inputs.x ]]` interpolation span, possibly with functions
# (e.g. `$[[ inputs.x | expand_vars ]]`). Treated as opaque: never split,
# re-quoted, or evaluated.
INTERPOLATION_REGEX = re.compile(r"\$\[\[.+?\]\]")

# Opt-in pragma allowing `$[[ ]]` tokens inside a .sh source file.
# The pragma line itself is stripped from compiled output.
INTERPOLATION_PRAGMA_REGEX = re.compile(r"#\s*Pragma:\s*gitlab-interpolation\b", re.IGNORECASE)

# Keys GitLab allows for a single input definition under `spec.inputs.<name>`.
ALLOWED_INPUT_OPTION_KEYS = {"default", "description", "type", "options", "regex"}

# Values GitLab allows for `spec.inputs.<name>.type`.
ALLOWED_INPUT_TYPES = {"string", "number", "boolean", "array"}

# Keys GitLab allows at the top of the `spec:` mapping.
ALLOWED_SPEC_KEYS = {"inputs"}


@dataclass
class ComponentTemplate:
    """A component template split into byte-preserving pieces.

    ``header`` is the exact text of the ``spec:`` document (no separator),
    ``separator`` is the exact ``---`` line including its newline, and
    ``body`` is the exact text of the pipeline document(s) after it.
    ``header + separator + body`` reproduces the original file exactly.
    """

    header: str
    separator: str
    body: str

    def reassemble(self, new_body: str | None = None) -> str:
        """Rebuild the full file text, optionally with a replaced body."""
        body = self.body if new_body is None else new_body
        return self.header + self.separator + body


def _parse_header(header_text: str) -> dict | None:
    """Parse candidate header text; return the mapping if it has a ``spec`` key."""
    yaml = YAML(typ="rt")
    try:
        data = yaml.load(io.StringIO(header_text))
    except YAMLError:
        return None
    if isinstance(data, dict) and "spec" in data:
        return dict(data)
    return None


def split_component_template(text: str) -> ComponentTemplate | None:
    """Split a component template into header/separator/body at the text level.

    Splitting on raw text (rather than ruamel multi-doc load/dump) guarantees
    the ``spec:`` header round-trips byte-identically through compile and
    decompile.

    Returns ``None`` when *text* is not a component template (no ``---``
    document separator after content, or the first document has no top-level
    ``spec`` key).
    """
    # Cheap rejection before any line scanning.
    if "spec" not in text or "---" not in text:
        return None

    offset = 0
    seen_content = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        # Separator must start at column 0; an indented `---` is content
        # (e.g. inside a block scalar), not a document boundary.
        is_separator = line.startswith("---") and (stripped == "---" or line.startswith("--- "))
        if is_separator and seen_content:
            header = text[:offset]
            separator = line
            body = text[offset + len(line) :]
            if _parse_header(header) is None:
                return None
            return ComponentTemplate(header=header, separator=separator, body=body)
        if is_separator and not seen_content:
            # Explicit document start (`---` before any content) — the spec
            # doc hasn't begun yet; keep scanning for the *next* separator.
            seen_content = False
        elif stripped and not stripped.startswith("#"):
            seen_content = True
        offset += len(line)
    return None


def is_component_template(text: str) -> bool:
    """Return True if *text* is a GitLab component template (``spec:`` + ``---``)."""
    return split_component_template(text) is not None


def validate_spec_header(header_text: str) -> tuple[bool, list[str]]:
    """Validate the shape of a ``spec:`` header document.

    Checks the structure GitLab documents for ``spec:inputs``: each input is
    ``None`` (no options) or a mapping using only ``default``, ``description``,
    ``type``, ``options``, ``regex``. Unknown keys are errors so typos fail at
    compile time instead of at include time on the GitLab server.
    """
    errors: list[str] = []
    yaml = YAML(typ="rt")
    try:
        data = yaml.load(io.StringIO(header_text))
    except YAMLError as e:
        return False, [f"spec header: YAML parsing error: {e}"]

    if not isinstance(data, dict) or "spec" not in data:
        return False, ["spec header: expected a mapping with a top-level 'spec' key"]

    extra_top = set(data.keys()) - {"spec"}
    if extra_top:
        errors.append(f"spec header: unexpected top-level keys besides 'spec': {sorted(extra_top)}")

    spec = data["spec"]
    if spec is None:
        return len(errors) == 0, errors
    if not isinstance(spec, dict):
        return False, ["spec header: 'spec' must be a mapping"]

    unknown_spec_keys = set(spec.keys()) - ALLOWED_SPEC_KEYS
    if unknown_spec_keys:
        errors.append(f"spec header: unknown keys under 'spec': {sorted(unknown_spec_keys)}")

    inputs = spec.get("inputs")
    if inputs is None:
        return len(errors) == 0, errors
    if not isinstance(inputs, dict):
        return False, ["spec header: 'spec.inputs' must be a mapping of input names"]

    for input_name, options in inputs.items():
        if options is None:
            continue
        if not isinstance(options, dict):
            errors.append(f"spec header: input '{input_name}' must be empty or a mapping of options")
            continue
        unknown = set(options.keys()) - ALLOWED_INPUT_OPTION_KEYS
        if unknown:
            errors.append(
                f"spec header: input '{input_name}' has unknown option(s) {sorted(unknown)}; allowed: {sorted(ALLOWED_INPUT_OPTION_KEYS)}"
            )
        input_type = options.get("type")
        if input_type is not None and input_type not in ALLOWED_INPUT_TYPES:
            errors.append(
                f"spec header: input '{input_name}' has invalid type '{input_type}'; allowed: {sorted(ALLOWED_INPUT_TYPES)}"
            )
        options_list = options.get("options")
        if options_list is not None and not isinstance(options_list, list):
            errors.append(f"spec header: input '{input_name}': 'options' must be a list")
        regex = options.get("regex")
        if regex is not None and not isinstance(regex, str):
            errors.append(f"spec header: input '{input_name}': 'regex' must be a string")

    return len(errors) == 0, errors


def contains_interpolation(text: str) -> bool:
    """Return True if *text* contains a ``$[[ ... ]]`` interpolation span."""
    return bool(INTERPOLATION_REGEX.search(text))


def strip_interpolation_pragma_lines(content: str, origin: str) -> str:
    """Strip ``# Pragma: gitlab-interpolation`` lines from script content.

    The pragma is a compiler directive, not script content, so it never
    reaches compiled YAML. When interpolation appears *without* the pragma,
    the content passes through unchanged but a warning points the user at
    the pragma (shellcheck and bash will both choke on ``$[[ ]]``, so usage
    should be deliberate).
    """
    has_pragma = bool(INTERPOLATION_PRAGMA_REGEX.search(content))
    has_interpolation = contains_interpolation(content)

    if has_interpolation and not has_pragma:
        logger.warning(
            "Script '%s' contains GitLab '$[[ ... ]]' interpolation but no '# Pragma: gitlab-interpolation'. The tokens are passed through verbatim; add the pragma to confirm this is intentional and silence this warning.",
            origin,
        )

    if not has_pragma:
        return content

    kept = [line for line in content.splitlines(keepends=True) if not INTERPOLATION_PRAGMA_REGEX.search(line)]
    return "".join(kept)


def find_component_templates(root: Path) -> list[Path]:
    """Find component template files (``spec:`` + ``---``) under *root*.

    Used by ``doctor`` to report that a project is a components repo.
    """
    found: list[Path] = []
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*.yml")) + sorted(root.rglob("*.yaml")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if is_component_template(text):
            found.append(path)
    return found
