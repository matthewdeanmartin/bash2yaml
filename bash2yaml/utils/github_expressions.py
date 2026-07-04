"""Support for GitHub Actions expressions (``${{ ... }}``) in bash sources.

GitHub Actions substitutes ``${{ ... }}`` expressions (contexts like
``inputs``, ``github``, ``secrets``, functions like ``contains()``) before a
``run:`` step executes. Reusable workflows (``on: workflow_call: inputs:``)
lean on these heavily — ``${{ inputs.x }}`` is the GitHub analog of GitLab's
``$[[ inputs.x ]]`` component interpolation.

bash2yaml never evaluates expressions. Inside YAML they are ordinary string
content and round-trip through ruamel untouched. Inside a ``.sh`` source file
they are a problem: bash treats ``${{ x }}`` as a bad substitution and
shellcheck rejects it, so their presence should be deliberate. The
``# Pragma: github-expression`` directive is that opt-in — mirroring
``# Pragma: gitlab-interpolation`` from ``gitlab_components``.

This module must not import from the ``commands`` package (it imports us).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

__all__ = [
    "EXPRESSION_REGEX",
    "EXPRESSION_PRAGMA_REGEX",
    "contains_expression",
    "strip_expression_pragma_lines",
]

# A `${{ ... }}` expression span. Treated as opaque: never split, re-quoted,
# or evaluated. Non-greedy so two expressions on one line match separately.
EXPRESSION_REGEX = re.compile(r"\$\{\{.+?\}\}")

# Opt-in pragma allowing `${{ }}` expressions inside a .sh source file.
# The pragma line itself is stripped from compiled output.
EXPRESSION_PRAGMA_REGEX = re.compile(r"#\s*Pragma:\s*github-expression\b", re.IGNORECASE)


def contains_expression(text: str) -> bool:
    """Return True if *text* contains a ``${{ ... }}`` expression span."""
    return bool(EXPRESSION_REGEX.search(text))


def strip_expression_pragma_lines(content: str, origin: str) -> str:
    """Strip ``# Pragma: github-expression`` lines from script content.

    The pragma is a compiler directive, not script content, so it never
    reaches compiled YAML. When expressions appear *without* the pragma,
    the content passes through unchanged but a warning points the user at
    the pragma (bash treats ``${{ }}`` as a bad substitution and shellcheck
    rejects it, so usage should be deliberate).
    """
    has_pragma = bool(EXPRESSION_PRAGMA_REGEX.search(content))
    has_expression = contains_expression(content)

    if has_expression and not has_pragma:
        logger.warning(
            "Script '%s' contains GitHub Actions '${{ ... }}' expressions but no '# Pragma: github-expression'. The expressions are passed through verbatim; add the pragma to confirm this is intentional and silence this warning.",
            origin,
        )

    if not has_pragma:
        return content

    kept = [line for line in content.splitlines(keepends=True) if not EXPRESSION_PRAGMA_REGEX.search(line)]
    return "".join(kept)
