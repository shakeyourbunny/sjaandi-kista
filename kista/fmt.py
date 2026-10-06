# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

from __future__ import annotations

_UNITS = ("KiB", "MiB", "GiB", "TiB", "PiB")


def human_size(size_bytes: int) -> str:
    """Format a byte count with binary units, one decimal from KiB up."""
    if size_bytes < 0:
        raise ValueError(f"size must not be negative: {size_bytes}")
    if size_bytes < 1024:
        return f"{size_bytes} B"
    value = float(size_bytes)
    for unit in _UNITS:
        value /= 1024.0
        if value < 1023.95 or unit == _UNITS[-1]:
            return f"{value:.1f} {unit}"
    raise AssertionError("unreachable")
