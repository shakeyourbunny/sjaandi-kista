# This file is part of the kista Project.
# License: GPL-3.0-or-later. Contact: kista-project@trinity2k.net
#

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Timezone-aware now; the house never uses naive local time."""
    return datetime.now(UTC)
