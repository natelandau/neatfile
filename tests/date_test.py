# type: ignore
"""Tests for dates.py."""

from datetime import date, datetime, timedelta, timezone

import pytest

from jdfile.models.dates import Date, DatePattern, MonthToNumber

TODAY = datetime.now(tz=timezone.utc).date()

LAST_MONTH = (TODAY.replace(day=1) - timedelta(days=TODAY.replace(day=1).day)).replace(day=1)
LAST_MONTH_SHORT = date(LAST_MONTH.year, LAST_MONTH.month, LAST_MONTH.day)
LAST_WEEK = TODAY - timedelta(days=7)
LAST_WEEK_SHORT = date(LAST_WEEK.year, LAST_WEEK.month, LAST_WEEK.day)
TODAY_SHORT = date(TODAY.year, TODAY.month, TODAY.day)
TOMORROW = TODAY + timedelta(days=1)
TOMORROW_SHORT = date(TOMORROW.year, TOMORROW.month, TOMORROW.day)
YESTERDAY = TODAY - timedelta(days=1)
YESTERDAY_SHORT = date(YESTERDAY.year, YESTERDAY.month, YESTERDAY.day)


# @pytest.mark.parametrize(
#     ("input_month", "expected"),
#     [
#         ("apr", "04"),
#         ("april", "04"),
#         ("aug", "08"),
#         ("august", "08"),
#         ("dec", "12"),
#         ("Dec", "12"),
#         ("december", "12"),
#         ("Feb", "02"),
#         ("february", "02"),
#         ("ja", "01"),
#         ("JAN", "01"),
#         ("january", "01"),
#         ("January", "01"),
#         ("jul", "07"),
#         ("july", "07"),
#         ("jun", "06"),
#         ("june", "06"),
#         ("mar", "03"),
#         ("Mar", "03"),
#         ("march", "03"),
#         ("may", "05"),
#         ("nov", "11"),
#         ("november", "11"),
#         ("oct", "10"),
#         ("OcTobEr", "10"),
#         ("sep", "09"),
#         ("september", "09"),
#         ("Invalid", ""),
#     ],
# )
# def test_month_num_from_name(input_month: str, expected: int):
#     """Test conversion from month name to month number."""
#     assert MonthToNumber.num_from_name(input_month) == expected


@pytest.mark.parametrize(
    ("pattern", "filename", "expected"),
    [
        ("dd_mm", "1201", (date(TODAY.year, 1, 12), "1201")),
        ("dd_mm", "1301", (date(TODAY.year, 1, 13), "1301")),
        ("dd_mm", "3301", None),
        ("dd_mm", "file 202212", None),
        ("dd_mm", "foo 12232022 bar", None),
        ("dd_mm", "string with no date", None),
        ("dd_month_yyyy", "22nd June, 2019 and more text", (date(2019, 6, 22), "22nd June, 2019")),
        ("dd_month_yyyy", "file 2022-12-31", None),
        ("dd_month_yyyy", "file 2022-12-32", None),
        ("dd_month_yyyy", "file 2022-12", None),
        ("dd_month_yyyy", "hello 23 march, 2020 world", (date(2020, 3, 23), "23 march, 2020")),
        ("dd_month_yyyy", "march 3rd 2022", None),
        ("dd_month_yyyy", "march 42nd, 2022", None),
        ("dd_month_yyyy", "string with no date", None),
        ("dd_month_yyyy", "this not a valid date 2019-99-01 and more text", None),
        ("ddmmyyyy", "file 2022-12", None),
        ("ddmmyyyy", "foo 01-22-2019 bar", None),
        ("ddmmyyyy", "foo 12112022 bar", (date(2022, 11, 12), "12112022")),
        ("ddmmyyyy", "foo 12232022 bar", None),
        ("ddmmyyyy", "foo 2122022 bar", None),
        ("ddmmyyyy", "foo 22-01-2019 bar", (date(2019, 1, 22), "22-01-2019")),
        ("ddmmyyyy", "foo 30122022 bar", (date(2022, 12, 30), "30122022")),
        ("ddmmyyyy", "string with no date", None),
        ("last_month", "file 202212", None),
        ("last_month", "foo 12232022 bar", None),
        ("last_month", "foo last_month bar", (LAST_MONTH_SHORT, "last_month")),
        ("last_month", "last Month's agenda", (LAST_MONTH_SHORT, "last Month's")),
        ("last_month", "string with no date", None),
        ("last_week", "file 202212", None),
        ("last_week", "foo 12232022 bar", None),
        ("last_week", "foo last.week bar", (LAST_WEEK_SHORT, "last.week")),
        ("last_week", "last week's agenda", (LAST_WEEK_SHORT, "last week's")),
        ("last_week", "string with no date", None),
        ("mm_dd", "1201", (date(TODAY.year, 12, 1), "1201")),
        ("mm_dd", "1301", None),
        ("mm_dd", "file 2022-12", None),
        ("mm_dd", "foo 12232022 bar", None),
        ("mm_dd", "string with no date", None),
        ("mmddyyyy", "file 2022-12", None),
        ("mmddyyyy", "foo 01-22-2019 bar", (date(2019, 1, 22), "01-22-2019")),
        ("mmddyyyy", "foo 12112022 bar", (date(2022, 12, 11), "12112022")),
        ("mmddyyyy", "foo 12232022 bar", (date(2022, 12, 23), "12232022")),
        ("mmddyyyy", "foo 30122022 bar", None),
        ("mmddyyyy", "string with no date", None),
        ("month_dd_yyyy", "file 2022-12-31", None),
        ("month_dd_yyyy", "file 2022-12-32", None),
        ("month_dd_yyyy", "file 2022-12", None),
        ("month_dd_yyyy", "foo march 1st, 2019", (date(2019, 3, 1), "march 1st, 2019")),
        ("month_dd_yyyy", "foo Oct 22, 2019 bar", (date(2019, 10, 22), "Oct 22, 2019")),
        ("month_dd_yyyy", "foo Oct222019 bar", (date(2019, 10, 22), "Oct222019")),
        ("month_dd_yyyy", "hello 23 march, 2020 world", None),
        ("month_dd_yyyy", "jan 3rd, 2022", (date(2022, 1, 3), "jan 3rd, 2022")),
        ("month_dd_yyyy", "march 3rd 2022", (date(2022, 3, 3), "march 3rd 2022")),
        ("month_dd_yyyy", "march 42nd, 2022", None),
        ("month_dd_yyyy", "string with no date", None),
        ("month_dd_yyyy", "this not a valid date 2019-99-01 and more text", None),
        ("month_dd", "file 2022-12-31", None),
        ("month_dd", "file 2022-12-32", None),
        ("month_dd", "file 2022-12", None),
        ("month_dd", "march 3rd 2022", (date(TODAY.year, 3, 3), "march 3rd")),
        ("month_dd", "march 42nd, 2022", None),
        ("month_dd", "sep 4", (date(TODAY.year, 9, 4), "sep 4")),
        ("month_dd", "sep 42nd", None),
        ("month_dd", "sept 4th", (date(TODAY.year, 9, 4), "sept 4th")),
        ("month_dd", "string with no date", None),
        ("month_dd", "this not a valid date 2019-99-01 and more text", None),
        ("month_yyyy", "file 2022-12-31", None),
        ("month_yyyy", "file 2022-12-32", None),
        ("month_yyyy", "file 2022-12", None),
        ("month_yyyy", "mar2022", (date(2022, 3, 1), "mar2022")),
        ("month_yyyy", "march 3rd 2022", None),
        ("month_yyyy", "march 42nd, 2022", None),
        ("month_yyyy", "sep 2025", (date(2025, 9, 1), "sep 2025")),
        ("month_yyyy", "string with no date", None),
        ("month_yyyy", "this not a valid date 2019-99-01 and more text", None),
        ("month_yyyy", "xxx_December,-2019/aaa", (date(2019, 12, 1), "December,-2019")),
        ("today", "file 202212", None),
        ("today", "foo 12232022 bar", None),
        ("today", "fooTodayBar", (TODAY_SHORT, "Today")),
        ("today", "string with no date", None),
        ("today", "Todays agenda", (TODAY_SHORT, "Todays")),
        ("tomorrow", "file 202212", None),
        ("tomorrow", "foo 12232022 bar", None),
        ("tomorrow", "footomorrow bar", (TOMORROW_SHORT, "tomorrow")),
        ("tomorrow", "string with no date", None),
        ("tomorrow", "tomorrow's agenda", (TOMORROW_SHORT, "tomorrow's")),
        ("yesterday", "file 202212", None),
        ("yesterday", "foo 12232022 bar", None),
        ("yesterday", "fooyesterday.bar", (YESTERDAY_SHORT, "yesterday")),
        ("yesterday", "string with no date", None),
        ("yesterday", "Yesterday's agenda", (YESTERDAY_SHORT, "Yesterday's")),
        ("yyyy_dd_mm", "2022/31/12", (date(2022, 12, 31), "2022/31/12")),
        ("yyyy_dd_mm", "20223112", (date(2022, 12, 31), "20223112")),
        ("yyyy_dd_mm", "file 2022-12-31", None),
        ("yyyy_dd_mm", "file 2022-12-32", None),
        ("yyyy_dd_mm", "file 2022-12", None),
        ("yyyy_dd_mm", "file 2022-31-12", (date(2022, 12, 31), "2022-31-12")),
        ("yyyy_dd_mm", "file_2022_01_01_somefile", (date(2022, 1, 1), "2022_01_01")),
        ("yyyy_dd_mm", "string with no date", None),
        ("yyyy_dd_mm", "this not a valid date 2019-99-01 and more text", None),
        ("yyyy_mm_dd", "2022/12/31", (date(2022, 12, 31), "2022/12/31")),
        ("yyyy_mm_dd", "20221231", (date(2022, 12, 31), "20221231")),
        ("yyyy_mm_dd", "file 2022-12-31", (date(2022, 12, 31), "2022-12-31")),
        ("yyyy_mm_dd", "file 2022-12-32", None),
        ("yyyy_mm_dd", "file 2022-12", None),
        ("yyyy_mm_dd", "file_2022_01_01_somefile", (date(2022, 1, 1), "2022_01_01")),
        ("yyyy_mm_dd", "string with no date", None),
        ("yyyy_mm_dd", "this not a valid date 2019-99-01 and more text", None),
        ("yyyy_month", "2022mar", (date(2022, 3, 1), "2022mar")),
        ("yyyy_month", "2025 sep", (date(2025, 9, 1), "2025 sep")),
        ("yyyy_month", "file 2022-12", None),
        ("yyyy_month", "march 3rd 2022", None),
        ("yyyy_month", "march 42nd, 2022", None),
        ("yyyy_month", "string with no date", None),
        ("yyyy_month", "this not a valid date 2019-99-01 and more text", None),
        ("yyyy_month", "xxx_2019, December,-2019/aaa", (date(2019, 12, 1), "2019, December")),
    ],
)
def test_date_pattern_regexes(filename, expected, pattern):
    """Test DatePattern class."""
    method = getattr(DatePattern, pattern, None)
    if method:
        assert method(string=filename) == expected
    else:
        msg = f"Method {pattern} not found in DatePattern."
        raise pytest.fail(msg)


# def test_date_class(tmp_path):
#     """Test Date class."""
#     file = tmp_path / "test_file.txt"
#     file.touch()
#     ctime = datetime.fromtimestamp(file.stat().st_ctime)
#     d = Date(date_format="%Y-%m-%d", string="a file with a date 2020-11-01", ctime=ctime)
#     assert d.date == date(2020, 11, 1)
#     assert d.original_string == "a file with a date 2020-11-01"
#     assert d.date_format == "%Y-%m-%d"
#     assert d.found_string == "2020-11-01"
#     assert d.ctime == ctime

#     d = Date(date_format="%Y-%m-%d", string="a file without date", ctime=ctime)
#     assert d.date == date(ctime.year, ctime.month, ctime.day)
#     assert d.original_string == "a file without date"
#     assert d.date_format == "%Y-%m-%d"
#     assert d.found_string is None
#     assert d.ctime == ctime

#     d = Date(date_format="%Y-%m-%d", string="no date")
#     assert d.date is None
#     assert d.original_string == "no date"
#     assert d.date_format == "%Y-%m-%d"
#     assert d.found_string is None
#     assert d.ctime is None


# @pytest.mark.parametrize(
#     ("filename", "date_format", "expected"),
#     [
#         ("January 13,2020", "%B %d,%Y", "January 13,2020"),
#         ("13th, jan 2019", "%Y, %b %d", "2019, Jan 13"),
#         ("2021-09-03", "%m-%Y-%d", "09-2021-03"),
#     ],
# )
# def test_reformat_date(filename, date_format, expected):
#     """Test reformat_date."""
#     d = Date(date_format=date_format, string=filename)
#     assert d.reformatted_date == expected
