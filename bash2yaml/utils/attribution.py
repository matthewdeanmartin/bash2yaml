"""Quiet-attribution support: keep the tool's name out of its own output.

``--quiet-attribution`` (or ``BASH2YAML_QUIET_ATTRIBUTION=1``) suppresses any
mention of the tool by name in logs, console output, and generated files. This
is distinct from ``-q/--quiet``: it doesn't reduce output volume, it removes
self-references — for screen-sharing, pair-programming, and traceless mode.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, TextIO

__all__ = [
    "QUIET_ATTRIBUTION_ENV_VAR",
    "enable_quiet_attribution",
    "quiet_attribution_enabled",
    "scrub_attribution",
]

QUIET_ATTRIBUTION_ENV_VAR = "BASH2YAML_QUIET_ATTRIBUTION"

# The tool name plus an optional joiner, so "the bash2yaml compiler" -> "the compiler"
# and "compiled with bash2yaml" -> "compiled". Case-insensitive.
_NAME_WITH_TRAILING_JOINER = re.compile(r"bash2yaml[ \t_./-]", re.IGNORECASE)
_NAME_WITH_LEADING_JOINER = re.compile(r"[ \t_./-]bash2yaml", re.IGNORECASE)
_BARE_NAME = re.compile(r"bash2yaml", re.IGNORECASE)


def quiet_attribution_enabled() -> bool:
    """True when attribution scrubbing is on (set via flag-driven env var)."""
    return os.environ.get(QUIET_ATTRIBUTION_ENV_VAR, "").lower() in ("1", "true", "yes")


def enable_quiet_attribution() -> None:
    """Turn on scrubbing for this process and its children (workers inherit env)."""
    os.environ[QUIET_ATTRIBUTION_ENV_VAR] = "1"
    install_stream_scrubbers()


def scrub_attribution(text: str) -> str:
    """Remove mentions of the tool name from *text*."""
    text = _NAME_WITH_TRAILING_JOINER.sub("", text)
    text = _NAME_WITH_LEADING_JOINER.sub("", text)
    return _BARE_NAME.sub("", text)


class _ScrubbingStream:
    """TextIO wrapper that scrubs attribution from everything written through it."""

    def __init__(self, wrapped: TextIO):
        self._wrapped = wrapped

    def write(self, text: str) -> int:
        return self._wrapped.write(scrub_attribution(text))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


def install_stream_scrubbers() -> None:
    """Wrap stdout/stderr so even bare ``print`` calls are scrubbed. Idempotent."""
    if not isinstance(sys.stdout, _ScrubbingStream):
        sys.stdout = _ScrubbingStream(sys.stdout)  # type: ignore[assignment]
    if not isinstance(sys.stderr, _ScrubbingStream):
        sys.stderr = _ScrubbingStream(sys.stderr)  # type: ignore[assignment]
