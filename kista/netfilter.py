# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Junk lists and matching semantics from mget (same author, same
# license); crash-reporting and product-analytics hosts merged in
# from luducat's network_manager blocklist.

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

_DATA_DIR = Path(__file__).parent / "data"


def load_patterns(path: str | Path) -> list[str]:
    """Load one-pattern-per-line files; # comments and blanks skipped."""
    patterns = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    return patterns


# Substring semantics on lowercased values, as in mget: a pattern
# matches anywhere in the hostname/path, whitelist beats junk.
JUNK_HOST_PATTERNS = tuple(p.lower() for p in load_patterns(_DATA_DIR / "junk_hosts.txt"))
JUNK_PATH_PATTERNS = tuple(p.lower() for p in load_patterns(_DATA_DIR / "junk_paths.txt"))
JUNK_HOST_WHITELIST = tuple(
    p.lower() for p in load_patterns(_DATA_DIR / "junk_hosts_whitelist.txt")
)


def is_junk_host(host: str) -> bool:
    """True if the hostname matches a junk pattern and no whitelist entry."""
    if not host or not host.strip():
        raise ValueError("host must not be empty")
    host = host.lower()
    if any(entry in host for entry in JUNK_HOST_WHITELIST):
        return False
    return any(pattern in host for pattern in JUNK_HOST_PATTERNS)


def is_junk_path(path: str) -> bool:
    """True if the URL path matches a junk path pattern."""
    if path is None:
        raise ValueError("path must not be None")
    path = path.lower()
    return any(pattern in path for pattern in JUNK_PATH_PATTERNS)


def is_junk_url(url: str) -> bool:
    """True if either the host or the path of the URL is junk."""
    if not url or not url.strip():
        raise ValueError("url must not be empty")
    parsed = urlparse(url)
    if parsed.netloc and is_junk_host(parsed.netloc):
        return True
    return is_junk_path(parsed.path)
