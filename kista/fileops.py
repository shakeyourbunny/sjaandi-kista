# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Atomic write pattern from litcollect's mirror.py (same author,
# same license), including the mergerfs EXDEV lesson.

from __future__ import annotations

import errno
import logging
import os
import platform
import re
import shutil
import tempfile
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_SETTLE_FS_TYPES = frozenset({"cifs", "smb", "smbfs", "fuse.mergerfs", "mergerfs"})
_SETTLE_DELAY_DEFAULT = 2.0

# Mount table: parsed once from /proc/mounts at import, cached for the
# process lifetime. Maps resolved mountpoint string to filesystem type.
# Sorted longest-first so the first prefix match is the deepest mount.
_mount_table: list[tuple[str, str]] = []

def _unescape_mount(s: str) -> str:
    """Unescape octal sequences in /proc/mounts (spaces as \\040 etc.)."""
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), s)


if platform.system() == "Linux":
    try:
        _raw: dict[str, str] = {}
        with open("/proc/mounts", encoding="utf-8") as _f:
            for _line in _f:
                _parts = _line.split()
                if len(_parts) >= 3:
                    _raw[_unescape_mount(_parts[1])] = _parts[2]
        _mount_table = sorted(_raw.items(), key=lambda kv: len(kv[0]), reverse=True)
    except OSError:
        pass

_settle_cache: dict[str, bool] = {}
_SETTLE_CACHE_MAX = 256


def _needs_settle(path: Path) -> bool:
    """True when path lives on a filesystem where writes may be delayed."""
    resolved = str(path.resolve())
    if resolved in _settle_cache:
        return _settle_cache[resolved]
    result = False
    for mountpoint, fstype in _mount_table:
        if resolved == mountpoint or resolved.startswith(mountpoint.rstrip("/") + "/"):
            result = fstype in _SETTLE_FS_TYPES
            break
    if len(_settle_cache) >= _SETTLE_CACHE_MAX:
        _settle_cache.clear()
    _settle_cache[resolved] = result
    return result


def write_atomic(path: str | Path, data: bytes, mode: int = 0o644) -> None:
    """Write via temp file in the same directory plus rename. On mergerfs
    the EXDEV fallback is not atomic and not crash-safe."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"data must be bytes, got {type(data).__name__}")
    path = Path(path)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    exdev_copy_failed = False
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_name, mode)
        try:
            os.replace(tmp_name, path)
        except OSError as e:
            if e.errno != errno.EXDEV:
                raise
            # mergerfs can raise EXDEV inside one directory.
            if os.path.lexists(path):
                os.unlink(path)
            try:
                shutil.copy2(tmp_name, path)
            except BaseException:
                exdev_copy_failed = True
                if os.path.lexists(path):
                    os.unlink(path)
                logger.error("EXDEV copy failed; payload kept at %s", tmp_name)
                raise
            os.unlink(tmp_name)
    finally:
        if not exdev_copy_failed and os.path.exists(tmp_name):
            os.unlink(tmp_name)
    if _needs_settle(path):
        time.sleep(_SETTLE_DELAY_DEFAULT)


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
    # RFC 2616: all HTTP dates are UTC; non-compliant servers may omit tz
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
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
    if max_age_days is not None and max_age_days < 0:
        raise ValueError(f"max_age_days must not be negative: {max_age_days}")
    if keep_newest is not None and keep_newest < 0:
        raise ValueError(f"keep_newest must not be negative: {keep_newest}")
    directory = Path(directory)
    if not directory.is_dir():
        return []

    entries = []
    for p in directory.glob(pattern):
        if p.is_file():
            entries.append((p, p.stat().st_mtime))
    entries.sort(key=lambda e: e[1], reverse=True)

    cutoff = None
    if max_age_days is not None:
        cutoff = datetime.now(UTC).timestamp() - max_age_days * 86400

    selected = []
    for index, (path, mtime) in enumerate(entries):
        too_old = cutoff is not None and mtime < cutoff
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
    """Copy with metadata; timestamp preservation is the point.

    On CIFS or mergerfs targets, pauses after writing to let delayed
    writes settle before the caller proceeds to verify or delete.
    """
    src, dst = Path(src), Path(dst)
    if not src.is_file():
        raise FileNotFoundError(f"source is not a file: {src}")
    shutil.copy2(src, dst)
    if _needs_settle(dst):
        time.sleep(_SETTLE_DELAY_DEFAULT)


def move_preserving(src: str | Path, dst: str | Path) -> None:
    """Move that survives filesystem boundaries and verifies the
    timestamp landed before the source is removed. Refuses to
    overwrite an existing target.

    On CIFS or mergerfs targets, pauses after cross-device copy
    before verifying size and mtime.
    """
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
    try:
        shutil.copy2(src, dst)
    except BaseException:
        if dst.exists():
            dst.unlink()
        raise
    if _needs_settle(dst):
        time.sleep(_SETTLE_DELAY_DEFAULT)
    if int(dst.stat().st_mtime) != int(src.stat().st_mtime):
        dst.unlink()
        raise OSError(f"mtime not preserved copying {src} -> {dst}")
    if dst.stat().st_size != src.stat().st_size:
        dst.unlink()
        raise OSError(f"size mismatch after copy: {src} -> {dst}")
    src.unlink()


from kista.dt import utc_now  # re-export for backwards compatibility

__all__ = [
    "available_name",
    "copy_preserving",
    "list_files",
    "move_preserving",
    "prune_candidates",
    "remove_tree",
    "stamp_http_mtime",
    "utc_now",
    "write_atomic",
]


def _fsync_dir(dirpath: Path) -> None:
    fd = os.open(dirpath, os.O_RDONLY)
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _dev(path) -> int:
    """Single choke point so the device-boundary logic stays testable."""
    return os.lstat(path).st_dev


def _assert_single_fs(directory: Path, root_dev: int) -> None:
    """Under one mergerfs pool every branch shares st_dev, so this only trips
    on a genuinely nested mount."""
    with os.scandir(directory) as it:
        for e in it:
            if e.is_symlink():
                continue
            if e.is_dir(follow_symlinks=False):
                if _dev(e.path) != root_dev:
                    raise ValueError(
                        f"device boundary (nested mount) at {e.path}; refusing "
                        f"to cross - pass follow_mounts=True to override")
                _assert_single_fs(Path(e.path), root_dev)


def _rmtree_single_fs(directory: Path, root_dev: int) -> None:
    """Re-checks st_dev per directory against mounts appearing after pre-scan.
    Residual TOCTOU between DirEntry.is_dir() and recursion; closing it
    needs O_NOFOLLOW+fstat which os.scandir lacks before 3.12."""
    with os.scandir(directory) as it:
        for e in it:
            if e.is_symlink():
                os.unlink(e.path)
            elif e.is_dir(follow_symlinks=False):
                if _dev(e.path) != root_dev:
                    raise ValueError(f"device boundary appeared mid-delete at {e.path}")
                _rmtree_single_fs(Path(e.path), root_dev)
            else:
                os.unlink(e.path)
    os.rmdir(directory)


def remove_tree(target, within, *, follow_mounts: bool = False,
                missing_ok: bool = False, dry_run: bool = False) -> list[Path]:
    """Safer shutil.rmtree: deletes target only if it resolves to a real
    directory strictly inside `within`, refusing symlinked targets, escapes
    via .. or symlink, target == within, filesystem roots and mount points.

    With follow_mounts=False it pre-scans and refuses outright rather than
    deleting as far as a nested mount and stopping half-done; follow_mounts=True
    falls back to shutil.rmtree and will cross into them."""
    base = Path(within)
    tgt = Path(target)

    if not base.exists():
        raise FileNotFoundError(f"containment base does not exist: {base}")
    base_real = base.resolve(strict=True)
    if not base_real.is_dir():
        raise NotADirectoryError(f"containment base is not a directory: {base}")

    if not tgt.exists() and not tgt.is_symlink():
        if missing_ok:
            return []
        raise FileNotFoundError(f"target does not exist: {tgt}")
    if tgt.is_symlink():
        raise ValueError(f"refusing to remove a symlinked target: {tgt}")

    tgt_real = tgt.resolve(strict=True)
    if not tgt_real.is_dir():
        raise NotADirectoryError(f"target is not a directory: {tgt} (use unlink for files)")

    if tgt_real == base_real or not tgt_real.is_relative_to(base_real):
        raise ValueError(f"target {tgt_real} is not strictly inside {base_real}")
    if tgt_real.parent == tgt_real:
        raise ValueError(f"refusing to remove filesystem root: {tgt_real}")

    root_dev = _dev(tgt_real)
    if not follow_mounts:
        if os.path.ismount(tgt_real):
            raise ValueError(f"refusing to remove a mount point: {tgt_real}")
        if _dev(base_real) != root_dev:
            raise ValueError(f"target is on a different device than base: {tgt_real}")

    if dry_run:
        out = [tgt_real]
        for root, dirs, files in os.walk(tgt_real, followlinks=False):
            for n in files: out.append(Path(root) / n)
            for n in dirs:  out.append(Path(root) / n)
        return sorted(out)

    if follow_mounts:
        shutil.rmtree(tgt_real)
    else:
        _assert_single_fs(tgt_real, root_dev)  # fail-fast, nothing deleted
        _rmtree_single_fs(tgt_real, root_dev)
    _fsync_dir(tgt_real.parent)
    return [tgt_real]
