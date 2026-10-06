# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#
"""Version has one source: kista.__version__.
0.8.0 shipped with 0.7.0 because pyproject.toml had its own copy.
These tests pin the mechanism against a second copy.
"""

import re
import tomllib
from pathlib import Path

import kista

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
PEP440_RELEASE = re.compile(r"^\d+(\.\d+)+$")


def _pyproject() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_dunder_version_is_a_release_version():
    assert PEP440_RELEASE.match(kista.__version__), kista.__version__


def test_pyproject_has_no_static_version():
    project = _pyproject()["project"]
    assert "version" not in project
    assert "version" in project.get("dynamic", [])


def test_pyproject_reads_version_from_the_package_attribute():
    dynamic = _pyproject()["tool"]["setuptools"]["dynamic"]
    assert dynamic["version"] == {"attr": "kista.__version__"}
