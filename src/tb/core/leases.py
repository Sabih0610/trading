"""Provider-neutral OS-held single-writer lease."""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO


class WriterBusy(RuntimeError):
    """Another process owns the persistent workspace."""


@contextmanager
def writer_lease(path: Path) -> Iterator[BinaryIO]:
    """OS-held process lock releases on interruption; no stale PID file bypass."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl = importlib.import_module("fcntl")
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise WriterBusy("Another process holds this workspace") from None
        try:
            yield handle
        finally:
            if handle.closed:
                pass
            elif os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
