# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista import sanitize


class TestSlugify:
    @pytest.mark.parametrize("raw,expected", [
        ("Hello World", "hello-world"),
        ("Träume & Schäume!", "träume-schäume"),
        ("  spaced  out  ", "spaced-out"),
        ("under_scores_too", "under-scores-too"),
        ("multi---dash", "multi-dash"),
        ("Already-Fine", "already-fine"),
    ])
    def test_slugs(self, raw, expected):
        assert sanitize.slugify(raw) == expected

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            sanitize.slugify("")

    def test_sanitized_to_empty_rejected(self):
        with pytest.raises(ValueError):
            sanitize.slugify("!!!")


class TestPathComponent:
    def test_traversal_neutralized(self):
        result = sanitize.sanitize_path_component("../../etc/passwd")
        assert "/" not in result
        assert not result.startswith(".")

    def test_backslash_neutralized(self):
        assert "\\" not in sanitize.sanitize_path_component("a\\b\\c")

    def test_control_chars_neutralized(self):
        result = sanitize.sanitize_path_component("evil\x00name\x1f")
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_case_preserved(self):
        assert sanitize.sanitize_path_component("UserName") == "UserName"

    def test_pure_dot_name_rejected(self):
        with pytest.raises(ValueError):
            sanitize.sanitize_path_component("..")

    def test_windows_reserved_names_defused(self):
        for name in ("CON", "con", "NUL", "COM1", "lpt9"):
            result = sanitize.sanitize_path_component(name)
            assert result.upper().split(".")[0] not in (
                "CON", "PRN", "AUX", "NUL", "COM1", "LPT9",
            ), name

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            sanitize.sanitize_path_component("")

    def test_only_hostile_chars_rejected(self):
        with pytest.raises(ValueError):
            sanitize.sanitize_path_component("///")
