"""Host-local integration for do_i_need_to_upgrade."""

from __future__ import annotations

import argparse
import sys
from typing import Any

HAS_UPGRADE_SUPPORT = False

if sys.version_info >= (3, 9):  # noqa: UP036 - py38 intentionally skips importing this optional dependency
    try:
        from do_i_need_to_upgrade import add_check_command, add_upgrade_command, run_if_upgrade_command
        from do_i_need_to_upgrade.api import check_for_updates
        from do_i_need_to_upgrade.report import Report
        from do_i_need_to_upgrade.settings import Settings

        HAS_UPGRADE_SUPPORT = True
    except ImportError:
        Report = Any  # type: ignore[assignment,misc]
        Settings = Any  # type: ignore[assignment,misc]
else:
    Report = Any  # type: ignore[assignment,misc]
    Settings = Any  # type: ignore[assignment,misc]

DIST_NAME = "bash2yaml"


def settings() -> Settings:
    """Return the host app's default updater settings."""
    if not HAS_UPGRADE_SUPPORT:
        raise RuntimeError("upgrade support is unavailable on this Python runtime")
    return Settings(dist_name=DIST_NAME, position="start", notify="return-only")


def add_commands(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register integrated updater subcommands."""
    if not HAS_UPGRADE_SUPPORT:
        return
    active_settings = settings()
    add_upgrade_command(subparsers, DIST_NAME, command="upgrade", settings=active_settings)
    add_check_command(subparsers, DIST_NAME, command="check-updates", settings=active_settings)


def run_command(args: argparse.Namespace) -> int | None:
    """Dispatch updater subcommands when selected."""
    if not HAS_UPGRADE_SUPPORT:
        return None
    return run_if_upgrade_command(args)


def startup_report() -> Report | None:
    """Kick off the cached startup check and background refresh."""
    if not HAS_UPGRADE_SUPPORT:
        return None
    report = check_for_updates(settings=settings())
    return report if not report.is_empty else None


def exit_report() -> Report | None:
    """Re-read the cache at shutdown without a blocking network call."""
    if not HAS_UPGRADE_SUPPORT:
        return None
    report = check_for_updates(settings=settings().replace(allow_network=False, notify="return-only"))
    return report if not report.is_empty else None


def render_notice(report: Report | None) -> str | None:
    """Convert a report into user-visible text."""
    if report is None:
        return None
    text = report.render_text()
    return text if text else None
