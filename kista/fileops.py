# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Atomic write pattern from litcollect's mirror.py (same author,
# same license), including the mergerfs EXDEV lesson.

from __future__ import annotations

import errno
import os
import shutil
import tempfile
from pathlib import Path


def write_atomic(path: str | Path, data: bytes, mode: int = 0o644) -> None:
    """Write via temp file in the same directory plus rename; a crash
    mid-write never leaves a truncated file at the target path."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"data must be bytes, got {type(data).__name__}")
    path = Path(path)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        # mkstemp creates 0600; the caller decides the real mode
        os.chmod(tmp_name, mode)
        try:
            os.replace(tmp_name, path)
        except OSError as e:
            # Layered filesystems (mergerfs) can raise EXDEV for a
            # rename inside one directory; copy+delete sidesteps it.
            if e.errno != errno.EXDEV:
                raise
            if path.exists():
                path.unlink()
            shutil.copy2(tmp_name, path)
            os.unlink(tmp_name)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def copy_preserving(src: str | Path, dst: str | Path) -> None:
    """Copy with metadata; timestamp preservation is the point."""
    src, dst = Path(src), Path(dst)
    if not src.is_file():
        raise FileNotFoundError(f"source is not a file: {src}")
    shutil.copy2(src, dst)


def move_preserving(src: str | Path, dst: str | Path) -> None:
    """Move that survives filesystem boundaries and verifies the
    timestamp landed before the source is removed. Refuses to
    overwrite an existing target."""
    src, dst = Path(src), Path(dst)
    if not src.is_file():
        raise FileNotFoundError(f"source is not a file: {src}")
    if dst.exists():
        raise FileExistsError(f"target already exists: {dst}")
    try:
        os.rename(src, dst)
        return
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise
    shutil.copy2(src, dst)
    if int(dst.stat().st_mtime) != int(src.stat().st_mtime):
        dst.unlink()
        raise OSError(f"mtime not preserved copying {src} -> {dst}")
    src.unlink()
