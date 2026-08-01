# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

from kista import platforminfo


def write_release(tmp_path, content):
    path = tmp_path / "os-release"
    path.write_text(content, encoding="utf-8")
    return path


class TestLinuxDistro:
    def test_known_distro(self, tmp_path):
        path = write_release(tmp_path, 'ID=debian\nNAME="Debian GNU/Linux"\n')
        assert platforminfo.linux_distro(path) == ("debian", "Debian GNU/Linux")

    def test_derivative_maps_to_parent(self, tmp_path):
        path = write_release(
            tmp_path, 'ID=neon\nID_LIKE="ubuntu debian"\nNAME="KDE neon"\n'
        )
        distro_id, name = platforminfo.linux_distro(path)
        assert distro_id == "ubuntu"
        assert name == "KDE neon"

    def test_suse_derivative(self, tmp_path):
        path = write_release(
            tmp_path, 'ID=weirdsuse\nID_LIKE="suse"\nNAME="Weird SUSE"\n'
        )
        assert platforminfo.linux_distro(path)[0] == "opensuse-leap"

    def test_quotes_stripped(self, tmp_path):
        path = write_release(tmp_path, "ID='arch'\nNAME='Arch Linux'\n")
        assert platforminfo.linux_distro(path) == ("arch", "Arch Linux")

    def test_missing_file_is_unknown(self, tmp_path):
        assert platforminfo.linux_distro(tmp_path / "ghost") == (
            "unknown", "Unknown Linux",
        )

    def test_garbage_content_is_unknown_id(self, tmp_path):
        path = write_release(tmp_path, "no equals signs here\n")
        assert platforminfo.linux_distro(path)[0] == "unknown"

    def test_slackware_is_known(self, tmp_path):
        path = write_release(tmp_path, 'ID=slackware\nNAME="Slackware"\n')
        assert platforminfo.linux_distro(path) == ("slackware", "Slackware")

    def test_rhel_clone_stays_itself(self, tmp_path):
        path = write_release(
            tmp_path, 'ID=rocky\nID_LIKE="rhel centos fedora"\nNAME="Rocky Linux"\n'
        )
        assert platforminfo.linux_distro(path)[0] == "rocky"

    def test_unknown_rhel_derivative_maps_to_fedora_family(self, tmp_path):
        path = write_release(
            tmp_path, 'ID=eurolinux\nID_LIKE="rhel fedora centos"\nNAME="EuroLinux"\n'
        )
        assert platforminfo.linux_distro(path)[0] == "fedora"

    def test_arch_derivative(self, tmp_path):
        path = write_release(
            tmp_path, 'ID=endeavouros\nID_LIKE="arch"\nNAME="EndeavourOS"\n'
        )
        assert platforminfo.linux_distro(path)[0] == "arch"

    def test_gentoo_known(self, tmp_path):
        path = write_release(tmp_path, 'ID=gentoo\nNAME="Gentoo"\n')
        assert platforminfo.linux_distro(path)[0] == "gentoo"

    def test_pretty_name_fallback(self, tmp_path):
        path = write_release(tmp_path, 'ID=void\nPRETTY_NAME="Void Linux"\n')
        assert platforminfo.linux_distro(path) == ("void", "Void Linux")
