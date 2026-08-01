# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import os

import pytest

from kista import fileops


class TestWriteAtomic:
    def test_writes_content(self, tmp_path):
        target = tmp_path / "out.txt"
        fileops.write_atomic(target, b"payload")
        assert target.read_bytes() == b"payload"

    def test_overwrites_existing(self, tmp_path):
        target = tmp_path / "out.txt"
        target.write_bytes(b"old")
        fileops.write_atomic(target, b"new")
        assert target.read_bytes() == b"new"

    def test_no_temp_leftover(self, tmp_path):
        target = tmp_path / "out.txt"
        fileops.write_atomic(target, b"x")
        assert [p.name for p in tmp_path.iterdir()] == ["out.txt"]

    def test_mode_applied(self, tmp_path):
        target = tmp_path / "out.txt"
        fileops.write_atomic(target, b"x")
        assert oct(target.stat().st_mode & 0o777) == oct(0o644)

    def test_rejects_str_payload(self, tmp_path):
        with pytest.raises(TypeError):
            fileops.write_atomic(tmp_path / "out.txt", "not bytes")

    def test_missing_parent_fails_loudly(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            fileops.write_atomic(tmp_path / "no" / "dir" / "out.txt", b"x")


class TestCopyPreserving:
    def test_content_and_mtime_preserved(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        os.utime(src, (1000000000, 1000000000))
        dst = tmp_path / "dst.bin"
        fileops.copy_preserving(src, dst)
        assert dst.read_bytes() == b"data"
        assert dst.stat().st_mtime == src.stat().st_mtime

    def test_source_must_exist(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            fileops.copy_preserving(tmp_path / "ghost", tmp_path / "dst")


class TestMovePreserving:
    def test_moves_and_preserves_mtime(self, tmp_path):
        src = tmp_path / "src.bin"
        src.write_bytes(b"data")
        os.utime(src, (1000000000, 1000000000))
        dst = tmp_path / "sub"
        dst.mkdir()
        target = dst / "moved.bin"
        fileops.move_preserving(src, target)
        assert not src.exists()
        assert target.read_bytes() == b"data"
        assert int(target.stat().st_mtime) == 1000000000

    def test_refuses_overwrite(self, tmp_path):
        src = tmp_path / "src"
        src.write_bytes(b"a")
        dst = tmp_path / "dst"
        dst.write_bytes(b"b")
        with pytest.raises(FileExistsError):
            fileops.move_preserving(src, dst)
        assert src.exists()
        assert dst.read_bytes() == b"b"
