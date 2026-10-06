# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

import pytest

from kista import fmt


class TestHumanSize:
    @pytest.mark.parametrize("size,expected", [
        (0, "0 B"),
        (1, "1 B"),
        (1023, "1023 B"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1024 ** 2, "1.0 MiB"),
        (5 * 1024 ** 3, "5.0 GiB"),
        (2 * 1024 ** 4, "2.0 TiB"),
        (3 * 1024 ** 5, "3.0 PiB"),
    ])
    def test_sizes(self, size, expected):
        assert fmt.human_size(size) == expected

    def test_boundary_rounds_up_to_next_unit(self):
        # 1048575 bytes = 1023.999... KiB, rounds to "1024.0 KiB" with .1f
        # but should display as "1.0 MiB"
        assert fmt.human_size(1048575) == "1.0 MiB"
        # same principle at GiB boundary
        assert fmt.human_size(1024 ** 3 - 1) == "1.0 GiB"

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            fmt.human_size(-1)
