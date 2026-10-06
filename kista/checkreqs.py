# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
# Stdlib only (tomllib, shutil.which, subprocess) so it runs before pip.

from __future__ import annotations

import logging
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Dependency:
    name: str
    binary: str
    description: str
    packages: dict[str, str] = field(default_factory=dict)
    repo: dict[str, str] = field(default_factory=dict)
    optional: bool = False
    check_command: str = ""


@dataclass
class CheckResult:
    found: list[Dependency] = field(default_factory=list)
    missing: list[Dependency] = field(default_factory=list)
    optional_missing: list[Dependency] = field(default_factory=list)


_INSTALL_CMD = {
    "apt": "sudo apt install",
    "dnf": "sudo dnf install",
    "pacman": "sudo pacman -S",
    "zypper": "sudo zypper install",
}

_REPO_CMD = {
    "dnf": "sudo dnf install {}",
    "zypper": "sudo zypper addrepo {}",
}


def load_manifest(path: str | Path) -> list[Dependency]:
    path = Path(path)
    with path.open("rb") as f:
        data = tomllib.load(f)

    deps = []
    for name, spec in data.get("deps", {}).items():
        deps.append(Dependency(
            name=name,
            binary=spec.get("binary", ""),
            description=spec.get("description", ""),
            packages=spec.get("packages", {}),
            repo=spec.get("repo", {}),
            optional=spec.get("optional", False),
            check_command=spec.get("check_command", ""),
        ))
    return deps


logger = logging.getLogger(__name__)


def _is_available(dep: Dependency) -> bool:
    if dep.binary:
        return shutil.which(dep.binary) is not None
    if dep.check_command:
        # check_command is a shell line from the project's own manifest
        # (pipes and redirects are part of the contract), not user input.
        try:
            result = subprocess.run(  # nosec B602
                dep.check_command, shell=True, capture_output=True,
                timeout=10, check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False
    logger.debug("dependency %r has no binary or check_command, assuming available", dep.name)
    return True


def check_deps(deps: list[Dependency]) -> CheckResult:
    result = CheckResult()
    for dep in deps:
        if _is_available(dep):
            result.found.append(dep)
        elif dep.optional:
            result.optional_missing.append(dep)
        else:
            result.missing.append(dep)
    return result


def format_install_instructions(result: CheckResult, family: str) -> list[str]:
    lines: list[str] = []

    all_missing = result.missing + result.optional_missing
    if not all_missing:
        return lines

    install_cmd = _INSTALL_CMD.get(family, "")

    repo_pkgs: list[str] = []
    for dep in all_missing:
        repo_spec = dep.repo.get(family, "")
        if repo_spec and repo_spec not in repo_pkgs:
            repo_pkgs.append(repo_spec)

    if result.missing:
        lines.append("Required tools missing:")
        for dep in result.missing:
            pkg = dep.packages.get(family, dep.binary or dep.name)
            lines.append(f"  {dep.name}: {dep.description} (package: {pkg})")

    if result.optional_missing:
        if result.missing:
            lines.append("")
        lines.append("Optional tools (recommended):")
        for dep in result.optional_missing:
            pkg = dep.packages.get(family, dep.binary or dep.name)
            lines.append(f"  {dep.name}: {dep.description} (package: {pkg})")

    if install_cmd:
        lines.append("")
        if repo_pkgs:
            repo_cmd_tpl = _REPO_CMD.get(family, "")
            if repo_cmd_tpl:
                lines.append("First, enable the required repositories:")
                for rp in repo_pkgs:
                    lines.append(f"  {repo_cmd_tpl.format(rp)}")
                lines.append("")

        required_pkgs = [
            dep.packages.get(family, dep.binary or dep.name)
            for dep in result.missing
            if dep.packages.get(family)
        ]
        optional_pkgs = [
            dep.packages.get(family, dep.binary or dep.name)
            for dep in result.optional_missing
            if dep.packages.get(family)
        ]

        if required_pkgs:
            lines.append("Install required packages:")
            lines.append(f"  {install_cmd} {' '.join(required_pkgs)}")

        if optional_pkgs:
            if required_pkgs:
                lines.append("")
            lines.append("Install optional packages:")
            lines.append(f"  {install_cmd} {' '.join(optional_pkgs)}")
    else:
        pkg_names = [
            dep.packages.get(family, dep.binary or dep.name)
            for dep in all_missing
        ]
        lines.append("")
        lines.append("Install the following packages with your package manager:")
        lines.append(f"  {', '.join(pkg_names)}")

    return lines
