# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista import fileops


class TestRemoveTree:
    def test_removes_directory_inside_base(self, tmp_path):
        target = tmp_path / "sub" / "deep"
        target.mkdir(parents=True)
        (target / "file.txt").write_bytes(b"x")
        result = fileops.remove_tree(target, tmp_path)
        assert not target.exists()
        assert result == [target.resolve()]

    def test_refuses_target_outside_base(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        base = tmp_path / "base"
        base.mkdir()
        with pytest.raises(ValueError, match="not strictly inside"):
            fileops.remove_tree(outside, base)
        assert outside.exists()

    def test_refuses_target_equals_base(self, tmp_path):
        with pytest.raises(ValueError, match="not strictly inside"):
            fileops.remove_tree(tmp_path, tmp_path)

    def test_refuses_symlink_target(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real)
        with pytest.raises(ValueError, match="symlinked"):
            fileops.remove_tree(link, tmp_path)
        assert real.exists()

    def test_refuses_file_target(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_bytes(b"x")
        with pytest.raises(NotADirectoryError):
            fileops.remove_tree(f, tmp_path)

    def test_missing_target_raises_by_default(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            fileops.remove_tree(tmp_path / "ghost", tmp_path)

    def test_missing_ok_returns_empty(self, tmp_path):
        result = fileops.remove_tree(tmp_path / "ghost", tmp_path, missing_ok=True)
        assert result == []

    def test_dry_run_lists_without_deleting(self, tmp_path):
        target = tmp_path / "sub"
        target.mkdir()
        (target / "a.txt").write_bytes(b"a")
        (target / "b.txt").write_bytes(b"b")
        result = fileops.remove_tree(target, tmp_path, dry_run=True)
        assert target.exists()
        assert len(result) >= 3

    def test_removes_nested_structure(self, tmp_path):
        target = tmp_path / "sub"
        (target / "a" / "b").mkdir(parents=True)
        (target / "a" / "b" / "deep.txt").write_bytes(b"x")
        (target / "top.txt").write_bytes(b"y")
        fileops.remove_tree(target, tmp_path)
        assert not target.exists()

    def test_symlinks_inside_target_removed_not_followed(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        (safe / "keep.txt").write_bytes(b"precious")
        target = tmp_path / "target"
        target.mkdir()
        (target / "link").symlink_to(safe)
        fileops.remove_tree(target, tmp_path)
        assert not target.exists()
        assert safe.exists()
        assert (safe / "keep.txt").read_bytes() == b"precious"

    def test_missing_base_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="containment base"):
            fileops.remove_tree(tmp_path / "t", tmp_path / "nobase")
