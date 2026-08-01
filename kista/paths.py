# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath

_CONTROL_CHARS = re.compile(r"[\x00-\x1f]")


def resolve_within(root: str | Path, *parts: str) -> Path:
    """Join parts under root and resolve; raise if the result escapes.

    The resolve() step also follows symlinks, so a link pointing
    outside the root is caught, not just textual ".." traversal.
    """
    if not parts:
        raise ValueError("at least one path part is required")
    root = Path(root).resolve()
    for part in parts:
        if not part:
            raise ValueError("empty path part")
        if _CONTROL_CHARS.search(part):
            raise ValueError(f"control character in path part: {part!r}")
        if Path(part).is_absolute():
            raise ValueError(f"absolute path part not allowed: {part!r}")
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"path escapes root {root}: {candidate}")
    return candidate


def normalize_archive_entry(name: str) -> str:
    """Normalize an archive member name to a safe relative POSIX path.

    House ingest rule: backslashes become slashes, and anything that
    is absolute, drive-lettered, UNC, traversing, or carrying control
    characters is rejected rather than repaired.
    """
    if not name or not name.strip():
        raise ValueError("archive entry name must not be empty")
    if _CONTROL_CHARS.search(name):
        raise ValueError(f"control character in archive entry: {name!r}")

    normalized = name.replace("\\", "/")
    if normalized.startswith("//"):
        raise ValueError(f"UNC archive entry not allowed: {name!r}")
    # PureWindowsPath catches drive letters ("C:/...") that a POSIX
    # view would treat as an ordinary file name.
    if PurePosixPath(normalized).is_absolute() or PureWindowsPath(name).is_absolute():
        raise ValueError(f"absolute archive entry not allowed: {name!r}")
    if re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"drive-lettered archive entry not allowed: {name!r}")

    segments = [s for s in normalized.split("/") if s not in ("", ".")]
    if not segments:
        raise ValueError(f"archive entry normalizes to nothing: {name!r}")
    if ".." in segments:
        raise ValueError(f"traversal in archive entry: {name!r}")
    return "/".join(segments)
