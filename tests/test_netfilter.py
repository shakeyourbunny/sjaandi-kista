# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista import netfilter


class TestJunkHost:
    def test_tracker_host_is_junk(self):
        assert netfilter.is_junk_host("doubleclick.net") is True

    def test_subdomain_of_tracker_is_junk(self):
        assert netfilter.is_junk_host("ads.doubleclick.net") is True

    def test_normal_host_is_not_junk(self):
        assert netfilter.is_junk_host("example.com") is False

    def test_luducat_merge_entries_present(self):
        assert netfilter.is_junk_host("api.rollbar.com") is True
        assert netfilter.is_junk_host("static.cloudflareinsights.com") is True

    def test_whitelist_wins(self):
        # vogons.org is whitelisted against the forum.* junk pattern
        assert netfilter.is_junk_host("forum.vogons.org") is False

    def test_case_insensitive(self):
        assert netfilter.is_junk_host("DoubleClick.NET") is True

    def test_empty_host_rejected(self):
        with pytest.raises(ValueError):
            netfilter.is_junk_host("")


class TestJunkPath:
    def test_wp_admin_is_junk(self):
        assert netfilter.is_junk_path("/wp-admin/options.php") is True

    def test_normal_path_is_not_junk(self):
        assert netfilter.is_junk_path("/articles/2026/review.html") is False

    def test_case_insensitive(self):
        assert netfilter.is_junk_path("/WP-ADMIN/") is True


class TestJunkUrl:
    def test_junk_host_url(self):
        assert netfilter.is_junk_url("https://ads.doubleclick.net/anything") is True

    def test_junk_path_url(self):
        assert netfilter.is_junk_url("https://example.com/wp-login.php") is True

    def test_clean_url(self):
        assert netfilter.is_junk_url("https://example.com/page.html") is False

    def test_whitelist_bypasses_host_check_only(self):
        # Host pattern "forum." is bypassed by the whitelist...
        assert netfilter.is_junk_url("https://forum.vogons.org/index.html") is False
        # ...but path junk still applies on whitelisted hosts (mget semantics)
        assert netfilter.is_junk_url("https://forum.vogons.org/wp-login.php") is True

    def test_empty_url_rejected(self):
        with pytest.raises(ValueError):
            netfilter.is_junk_url("")


class TestHashing:
    def test_md5_streams_file(self, tmp_path):
        from kista import hashing
        f = tmp_path / "x.bin"
        f.write_bytes(b"hello world")
        assert hashing.file_md5(f) == "5eb63bbbe01eeed093cb22bb8f5acdc3"

    def test_sha256(self, tmp_path):
        from kista import hashing
        f = tmp_path / "x.bin"
        f.write_bytes(b"hello world")
        assert hashing.file_sha256(f) == (
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        )

    def test_missing_file_fails_loudly(self, tmp_path):
        from kista import hashing
        with pytest.raises(FileNotFoundError):
            hashing.file_md5(tmp_path / "ghost")


class TestWindowsSafe:
    @pytest.mark.parametrize("raw,expected", [
        ('a<b>c:d"e', "a_b_c_d_e"),
        ("normal-name.txt", "normal-name.txt"),
        ("trailing. ", "trailing"),
        ("ctrl\x01char", "ctrl_char"),
    ])
    def test_replacements(self, raw, expected):
        from kista import sanitize
        assert sanitize.windows_safe(raw) == expected

    def test_never_empty(self):
        from kista import sanitize
        assert sanitize.windows_safe("...") == "_"


class TestSanitizeFilename:
    def test_hostile_chars_removed(self):
        from kista import sanitize
        result = sanitize.sanitize_filename('Game: The "Sequel" <2>?')
        assert ":" not in result
        assert "?" not in result
        assert "<" not in result

    def test_reserved_name_defused(self):
        from kista import sanitize
        assert sanitize.sanitize_filename("CON").upper() != "CON"

    def test_trailing_dots_spaces_stripped(self):
        from kista import sanitize
        assert not sanitize.sanitize_filename("name. ").endswith((".", " "))

    def test_replacement_semantics(self):
        from kista import sanitize
        assert sanitize.sanitize_filename("???") == "___"

    def test_never_empty(self):
        from kista import sanitize
        assert sanitize.sanitize_filename(". ") == "_"

    def test_normal_name_untouched(self):
        from kista import sanitize
        assert sanitize.sanitize_filename("normal-file 1.2.txt") == "normal-file 1.2.txt"
