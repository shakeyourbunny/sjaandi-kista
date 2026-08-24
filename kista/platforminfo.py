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

# distro_id -> package manager family
_DISTRO_TO_PKGMGR = {
    "ubuntu": "apt",
    "debian": "apt",
    "linuxmint": "apt",
    "fedora": "dnf",
    "rhel": "dnf",
    "centos": "dnf",
    "rocky": "dnf",
    "almalinux": "dnf",
    "arch": "pacman",
    "manjaro": "pacman",
    "opensuse-leap": "zypper",
    "opensuse-tumbleweed": "zypper",
}

_UNKNOWN = ("unknown", "Unknown Linux")


def _parse_os_release(os_release: str | Path = "/etc/os-release") -> dict[str, str]:
    path = Path(os_release)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    info: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if "=" in line:
            key, _, value = line.partition("=")
            info[key] = value.strip("\"'")
    return info


def linux_distro(os_release: str | Path = "/etc/os-release") -> tuple[str, str]:
    """Detect the Linux distribution: (distro_id, display_name).

    Derivatives not in the known set are mapped to their parent
    family through ID_LIKE. Never raises; unknown means unknown.
    """
    info = _parse_os_release(os_release)
    if not info:
        return _UNKNOWN

    distro_id = info.get("ID", "unknown").strip("\"'").lower()
    distro_name = info.get("NAME", info.get("PRETTY_NAME", "Unknown Linux"))

    if distro_id not in _KNOWN_DISTROS:
        id_like_tokens = info.get("ID_LIKE", "").lower().split()
        for token, family in _FAMILY_MAP:
            if token in id_like_tokens:
                distro_id = family
                break
    return (distro_id, distro_name)


def distro_family(os_release: str | Path = "/etc/os-release") -> str:
    """Package-manager family: apt, dnf, pacman, zypper, or unknown."""
    distro_id, _ = linux_distro(os_release)
    return _DISTRO_TO_PKGMGR.get(distro_id, "unknown")


def distro_version_id(os_release: str | Path = "/etc/os-release") -> str:
    """VERSION_ID from os-release, empty string if absent (rolling distros)."""
    info = _parse_os_release(os_release)
    return info.get("VERSION_ID", "")
