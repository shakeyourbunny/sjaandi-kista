# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

from datetime import UTC

from kista import dt


def test_utc_now_is_timezone_aware():
    now = dt.utc_now()
    assert now.tzinfo is UTC


def test_utc_now_advances():
    assert dt.utc_now() <= dt.utc_now()
