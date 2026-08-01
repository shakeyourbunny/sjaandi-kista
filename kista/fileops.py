# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Atomic write pattern from litcollect's mirror.py (same author,
# same license), including the mergerfs EXDEV lesson.

from __future__ import annotations

import errno
import logging
import os
import shutil
import tempfile
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

logger = logging.getLogger(__name__)


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


def stamp_http_mtime(path: str | Path, last_modified: str) -> datetime | None:
    """Stamp a file's mtime from an HTTP Last-Modified header value.

    Empty or unparseable headers are a logged no-op, not an error - a
    download must not fail because a server sends a broken date.
    """
    if not last_modified:
        return None
    try:
        stamp = parsedate_to_datetime(last_modified)
    except (ValueError, TypeError) as e:
        logger.warning("Unparseable Last-Modified %r for %s: %s", last_modified, path, e)
        return None
    seconds = stamp.timestamp()
    os.utime(path, (seconds, seconds))
    return stamp


def list_files(root: str | Path, exclude_top: tuple[str, ...] = ()) -> list[str]:
    """Sorted relative paths of files and symlinks below root.

    Directories are not listed. Dangling symlinks are - the caller's
    cleanup pass decides what happens to them. exclude_top skips
    whole top-level subtrees by name.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"not a directory: {root}")
    found = []
    for entry in root.rglob("*"):
        if not (entry.is_file() or entry.is_symlink()):
            continue
        rel = entry.relative_to(root)
        if rel.parts[0] in exclude_top:
            continue
        found.append(str(rel))
    return sorted(found)


def prune_candidates(
    directory: str | Path,
    pattern: str = "*",
    max_age_days: float | None = None,
    keep_newest: int | None = None,
) -> list[Path]:
    """Select files due for retention pruning; never deletes anything.

    The caller decides what happens to the returned paths - delete,
    archive, report. Age and keep-N criteria combine with OR.
    Adapted from AmberChatLite's cleanup_old_files, split into
    policy (here) and action (caller).
    """
    if max_age_days is None and keep_newest is None:
        raise ValueError("at least one of max_age_days or keep_newest is required")
    directory = Path(directory)
    if not directory.is_dir():
        return []

    files = [p for p in directory.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    cutoff = None
    if max_age_days is not None:
        cutoff = datetime.now(UTC).timestamp() - max_age_days * 86400

    selected = []
    for index, path in enumerate(files):
        too_old = cutoff is not None and path.stat().st_mtime < cutoff
        overflow = keep_newest is not None and index >= keep_newest
        if too_old or overflow:
            selected.append(path)
    return selected


def available_name(path: str | Path) -> Path:
    """First non-existing variant of path: name.ext, name_1.ext, ..."""
    path = Path(path)
    if not path.exists():
        return path
    for counter in range(1, 10000):
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"no available name variant for {path}")


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
