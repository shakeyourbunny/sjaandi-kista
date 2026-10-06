# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Arch detection adapted from release_filter.py in the
# github-user-loader project (same author, same license).
# Local changes: inverted from reject-ARM to detect-any-arch,
# added macOS detection, boundary assertions preserved.

"""Token-bounded architecture detection in filenames.

The boundary assertions prevent false positives: "alarm", "charm",
"swarm", "garmin" must NOT match ARM patterns.
"""

from __future__ import annotations

import re

ARCH_PATTERNS: dict[str, re.Pattern[str]] = {
    "x86_64": re.compile(
        r"(?<![a-z0-9])(x86_64|x86-64|amd64|x64)(?![a-z0-9])", re.IGNORECASE
    ),
    "aarch64": re.compile(
        r"(?<![a-z0-9])(aarch64|arm64)(?![a-z0-9])", re.IGNORECASE
    ),
    "i686": re.compile(
        r"(?<![a-z0-9])(i[36]86|i386)(?![a-z0-9])", re.IGNORECASE
    ),
    "armhf": re.compile(
        r"(?<![a-z0-9])(armhf|armv[0-9]+l?)(?![a-z0-9])", re.IGNORECASE
    ),
}

_MACOS_RE = re.compile(
    r"(?:macos|osx|(?<![a-z])darwin(?![a-z])|mac[-_.]|(?<![a-z])apple(?![a-z])|\.dmg$|\.sit$|\.hqx$)",
    re.IGNORECASE,
)


def detect_arch(text: str) -> str | None:
    """Match an architecture token in a filename or label string.

    Returns the canonical arch name or None if no arch is detected.
    """
    if not text:
        return None
    for arch, pattern in ARCH_PATTERNS.items():
        if pattern.search(text):
            return arch
    return None


def is_macos(text: str) -> bool:
    """True when a filename or label indicates a macOS build."""
    return bool(_MACOS_RE.search(text))
