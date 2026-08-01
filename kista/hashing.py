# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

from __future__ import annotations

import hashlib
from pathlib import Path


def _digest(path: str | Path, factory) -> str:
    with open(path, "rb") as f:
        return hashlib.file_digest(f, factory).hexdigest()


def file_md5(path: str | Path) -> str:
    """Streaming MD5 of a file - integrity checking, not security."""
    return _digest(path, lambda: hashlib.md5(usedforsecurity=False))


def file_sha256(path: str | Path) -> str:
    return _digest(path, hashlib.sha256)
