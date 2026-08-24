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


class TestDistroFamily:
    def test_debian(self, tmp_path):
        path = write_release(tmp_path, 'ID=debian\nVERSION_ID="13"\n')
        assert platforminfo.distro_family(path) == "apt"

    def test_ubuntu(self, tmp_path):
        path = write_release(tmp_path, 'ID=ubuntu\nVERSION_ID="24.04"\n')
        assert platforminfo.distro_family(path) == "apt"

    def test_fedora(self, tmp_path):
        path = write_release(tmp_path, 'ID=fedora\nVERSION_ID="44"\n')
        assert platforminfo.distro_family(path) == "dnf"

    def test_arch(self, tmp_path):
        path = write_release(tmp_path, "ID=arch\n")
        assert platforminfo.distro_family(path) == "pacman"

    def test_opensuse_tumbleweed(self, tmp_path):
        path = write_release(tmp_path, 'ID=opensuse-tumbleweed\nID_LIKE="suse"\n')
        assert platforminfo.distro_family(path) == "zypper"

    def test_opensuse_leap(self, tmp_path):
        path = write_release(tmp_path, 'ID=opensuse-leap\nVERSION_ID="15.6"\n')
        assert platforminfo.distro_family(path) == "zypper"

    def test_ubuntu_derivative(self, tmp_path):
        path = write_release(tmp_path, 'ID=pop\nID_LIKE="ubuntu debian"\n')
        assert platforminfo.distro_family(path) == "apt"

    def test_almalinux(self, tmp_path):
        path = write_release(
            tmp_path, 'ID="almalinux"\nID_LIKE="rhel centos fedora"\nVERSION_ID="9.5"\n'
        )
        assert platforminfo.distro_family(path) == "dnf"

    def test_rocky(self, tmp_path):
        path = write_release(
            tmp_path, 'ID=rocky\nID_LIKE="rhel centos fedora"\nVERSION_ID="9"\n'
        )
        assert platforminfo.distro_family(path) == "dnf"

    def test_manjaro(self, tmp_path):
        path = write_release(tmp_path, 'ID=manjaro\nID_LIKE="arch"\n')
        assert platforminfo.distro_family(path) == "pacman"

    def test_linuxmint(self, tmp_path):
        path = write_release(tmp_path, 'ID=linuxmint\nID_LIKE="ubuntu debian"\n')
        assert platforminfo.distro_family(path) == "apt"

    def test_unknown_distro(self, tmp_path):
        path = write_release(tmp_path, "ID=haiku\n")
        assert platforminfo.distro_family(path) == "unknown"

    def test_missing_file(self, tmp_path):
        assert platforminfo.distro_family(tmp_path / "nope") == "unknown"

    def test_slackware(self, tmp_path):
        path = write_release(tmp_path, 'ID=slackware\nNAME="Slackware"\n')
        assert platforminfo.distro_family(path) == "unknown"

    def test_gentoo(self, tmp_path):
        path = write_release(tmp_path, 'ID=gentoo\nNAME="Gentoo"\n')
        assert platforminfo.distro_family(path) == "unknown"


class TestDistroVersionId:
    def test_has_version(self, tmp_path):
        path = write_release(tmp_path, 'ID=debian\nVERSION_ID="13"\n')
        assert platforminfo.distro_version_id(path) == "13"

    def test_dotted_version(self, tmp_path):
        path = write_release(tmp_path, 'ID=ubuntu\nVERSION_ID="24.04"\n')
        assert platforminfo.distro_version_id(path) == "24.04"

    def test_rolling_no_version(self, tmp_path):
        path = write_release(tmp_path, "ID=arch\n")
        assert platforminfo.distro_version_id(path) == ""

    def test_missing_file(self, tmp_path):
        assert platforminfo.distro_version_id(tmp_path / "nope") == ""
