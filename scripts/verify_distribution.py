"""Verify that built distributions contain the project's source files."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from collections.abc import Iterable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "bash2yaml"
TEST_ROOT = PROJECT_ROOT / "test"


def source_files(root: Path, pattern: str = "*") -> set[str]:
    """Return archive-style paths for files below the project root."""
    return {
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in root.rglob(pattern)
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}
    }


def wheel_files(path: Path) -> set[str]:
    """Return the paths stored in a wheel."""
    with zipfile.ZipFile(path) as archive:
        return set(archive.namelist())


def sdist_files(path: Path) -> set[str]:
    """Return sdist paths with the archive's project directory removed."""
    with tarfile.open(path, mode="r:*") as archive:
        files = set()
        for member in archive.getmembers():
            if not member.isfile():
                continue
            parts = Path(member.name).parts
            if len(parts) > 1:
                files.add(Path(*parts[1:]).as_posix())
        return files


def require_files(artifact: Path, expected: Iterable[str], actual: set[str]) -> None:
    """Fail with a useful list when an artifact omits expected files."""
    missing = sorted(set(expected) - actual)
    if missing:
        formatted = "\n".join(f"  - {name}" for name in missing)
        raise RuntimeError(f"{artifact.name} is missing {len(missing)} required files:\n{formatted}")


def find_one(directory: Path, pattern: str) -> Path:
    """Find exactly one artifact matching a glob."""
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {pattern} in {directory}, found {len(matches)}")
    return matches[0]


def verify(directory: Path) -> None:
    """Verify the wheel's package and the sdist's package and tests."""
    wheel = find_one(directory, "*.whl")
    sdist = find_one(directory, "*.tar.gz")

    package_files = source_files(PACKAGE_ROOT)
    test_python_files = source_files(TEST_ROOT, "*.py")

    require_files(wheel, package_files, wheel_files(wheel))
    require_files(sdist, package_files | test_python_files, sdist_files(sdist))

    package_python_count = sum(name.endswith(".py") for name in package_files)
    print(
        f"Verified {wheel.name} and {sdist.name}: "
        f"{len(package_files)} package files ({package_python_count} Python) "
        f"and {len(test_python_files)} test modules."
    )


def main() -> None:
    """Run distribution verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory containing one wheel and one sdist")
    args = parser.parse_args()
    verify(args.directory.resolve())


if __name__ == "__main__":
    main()
