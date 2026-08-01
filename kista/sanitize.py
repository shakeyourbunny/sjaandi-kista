# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Generalized from litcollect's mirror.py (same author, same license).

from __future__ import annotations

import re

# Windows device names are reserved regardless of extension; writing
# them breaks cross-platform use of the resulting tree.
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def slugify(name: str) -> str:
    """Lowercase filename slug: keeps word chars and hyphens, folds
    whitespace/underscores to single hyphens, drops the rest."""
    if not name:
        raise ValueError("name must not be empty")
    name = name.strip().lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"-+", "-", name)
    name = name.strip("-")
    if not name:
        raise ValueError(f"name slugified to empty: {name!r}")
    return name


def sanitize_path_component(name: str) -> str:
    """Neutralize separators, control chars and dot-names while
    preserving case. Input is treated as hostile (scraped pages,
    archive entries)."""
    if not name:
        raise ValueError("path component must not be empty")
    name = name.strip()
    name = re.sub(r"[/\\\x00-\x1f]", "-", name)
    name = name.strip(". ")
    if not name.strip("-"):
        raise ValueError(f"path component sanitized to empty: {name!r}")
    stem = name.split(".")[0].upper()
    if stem in _WINDOWS_RESERVED:
        name = f"{name}-"
    return name
