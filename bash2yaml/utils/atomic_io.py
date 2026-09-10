"""Atomic publication and process-safe locks using only the standard library."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def atomic_write_text(path: Path, content: str) -> None:
    """Replace a complete UTF-8 file; failed writes leave the old file intact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=".bash2yaml-write-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def file_lock(path: Path, timeout: float = 30.0) -> Iterator[None]:
    """Lock a persistent file; the OS releases it if the process exits or crashes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        # Windows byte-range locking needs a byte to lock.
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if sys.platform == "win32":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for another writer: {path}") from None
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
