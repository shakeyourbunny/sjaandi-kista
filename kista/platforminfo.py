# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Detection adapted from the jast-downloader project (same author,
# same license); known set and ID_LIKE mapping extended.

from __future__ import annotations

from pathlib import Path

# Distros whose ID stands on its own; anything else is mapped to a
# parent family via ID_LIKE so callers can pick install instructions.
_KNOWN_DISTROS = {
    "ubuntu", "debian", "linuxmint", "fedora", "rhel", "centos",
    "rocky", "almalinux", "arch", "manjaro", "opensuse-leap",
    "opensuse-tumbleweed", "slackware", "gentoo", "void", "alpine",
    "nixos",
}

# ID_LIKE token -> canonical family, checked in order: ubuntu wins
# over debian because ubuntu-based distros ship ubuntu packaging.
_FAMILY_MAP = (
    ("ubuntu", "ubuntu"),
    ("debian", "debian"),
    ("rhel", "fedora"),
    ("centos", "fedora"),
    ("fedora", "fedora"),
    ("arch", "arch"),
    ("suse", "opensuse-leap"),
    ("gentoo", "gentoo"),
)

_UNKNOWN = ("unknown", "Unknown Linux")


def linux_distro(os_release: str | Path = "/etc/os-release") -> tuple[str, str]:
    """Detect the Linux distribution: (distro_id, display_name).

    Derivatives not in the known set are mapped to their parent
    family through ID_LIKE. Never raises; unknown means unknown.
    """
    path = Path(os_release)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return _UNKNOWN

    info: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if "=" in line:
            key, _, value = line.partition("=")
            info[key] = value.strip("\"'")

    distro_id = info.get("ID", "unknown").strip("\"'").lower()
    distro_name = info.get("NAME", info.get("PRETTY_NAME", "Unknown Linux"))

    if distro_id not in _KNOWN_DISTROS:
        id_like_tokens = info.get("ID_LIKE", "").lower().split()
        for token, family in _FAMILY_MAP:
            if token in id_like_tokens:
                distro_id = family
                break
    return (distro_id, distro_name)
