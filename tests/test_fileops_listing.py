# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista import fileops


class TestListFiles:
    def _tree(self, tmp_path):
        (tmp_path / "b-dir").mkdir()
        (tmp_path / "b-dir" / "file2.txt").write_text("x", encoding="utf-8")
        (tmp_path / "a-file.txt").write_text("x", encoding="utf-8")
        (tmp_path / ".attic").mkdir()
        (tmp_path / ".attic" / "old.txt").write_text("x", encoding="utf-8")
        (tmp_path / "dangling").symlink_to(tmp_path / "nowhere")
        return tmp_path

    def test_sorted_relative_files(self, tmp_path):
        root = self._tree(tmp_path)
        result = fileops.list_files(root, exclude_top=(".attic",))
        assert result == ["a-file.txt", "b-dir/file2.txt", "dangling"]

    def test_no_exclusion_includes_attic(self, tmp_path):
        root = self._tree(tmp_path)
        result = fileops.list_files(root)
        assert ".attic/old.txt" in result

    def test_directories_not_listed(self, tmp_path):
        root = self._tree(tmp_path)
        assert "b-dir" not in fileops.list_files(root)

    def test_missing_root_fails_loudly(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            fileops.list_files(tmp_path / "ghost")


class TestStampHttpMtime:
    def test_valid_header_stamps(self, tmp_path):
        target = tmp_path / "f"
        target.write_bytes(b"x")
        result = fileops.stamp_http_mtime(target, "Wed, 21 Oct 2015 07:28:00 GMT")
        assert result is not None
        assert int(target.stat().st_mtime) == int(result.timestamp())

    def test_empty_header_is_noop(self, tmp_path):
        target = tmp_path / "f"
        target.write_bytes(b"x")
        before = target.stat().st_mtime
        assert fileops.stamp_http_mtime(target, "") is None
        assert target.stat().st_mtime == before

    def test_garbage_header_is_logged_noop(self, tmp_path):
        target = tmp_path / "f"
        target.write_bytes(b"x")
        assert fileops.stamp_http_mtime(target, "not a date") is None
