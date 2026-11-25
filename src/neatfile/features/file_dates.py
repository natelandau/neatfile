"""Dates read from a file itself, for naming files whose names hold no date."""

from datetime import datetime, tzinfo
from pathlib import Path
from typing import assert_never

from neatfile.constants import DateFallback


def filesystem_date(path: Path, *, fallback: DateFallback, tz: tzinfo) -> datetime:
    """Return the file timestamp the user chose to date files that hold no other date.

    `CREATED` uses the birth time, which only some platforms report, and falls back to the
    modification time. ctime is never used because on Unix it is the inode change time and moves
    on every chmod or rename.

    Args:
        path (Path): The file to inspect.
        fallback (DateFallback): Which timestamp to read.
        tz (tzinfo): The time zone to express the date in.

    Returns:
        datetime: The chosen timestamp in `tz`.
    """
    stat = path.stat()
    match fallback:
        case DateFallback.CREATED:
            timestamp: float = getattr(stat, "st_birthtime", stat.st_mtime)
        case DateFallback.MODIFIED:
            timestamp = stat.st_mtime
        case _:
            assert_never(fallback)
    return datetime.fromtimestamp(timestamp, tz=tz)
