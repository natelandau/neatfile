"""Date class for jdfile."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from loguru import logger


class MonthToNumber(Enum):
    """Enum for month names."""

    January = 1
    February = 2
    March = 3
    April = 4
    May = 5
    June = 6
    July = 7
    August = 8
    September = 9
    October = 10
    November = 11
    December = 12

    @classmethod
    def num_from_name(cls, month: str) -> str:
        """Convert a month name to its corresponding number.

        Args:
            month (str): Month name to convert.

        Returns:
            str: The month number or an empty string if the month name is not found.
        """
        month = month.lower()
        for member in cls:
            if member.name.lower().startswith(month):
                return str(member.value).zfill(2)

        return ""


@dataclass
class DatePattern:
    """Regex patterns to find dates in filename strings."""

    pattern_day_flexible = r"0?[1-9]|[12][0-9]|3[01]"
    pattern_day_inflexible = r"0[1-9]|[12][0-9]|3[01]"
    pattern_month = r"0[1-9]|1[012]"
    pattern_months = r"january|jan?|february|feb?|march|mar?|april|apr?|may|june?|july?|august|aug?|september|sep?t?|october|oct?|november|nov?|december|dec?"
    pattern_separator = r"[-\./_, :]*?"
    pattern_year = r"20[0-2][0-9]"

    @staticmethod
    def yyyy_mm_dd(string: str) -> tuple[date, str] | None:
        """Search for a date in the format yyyy-mm-dd.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            # (?:.*[^0-9]|^)        # Start of string
            (?P<found>
                (?P<year>{DatePattern.pattern_year})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_inflexible})
            )
            # (?:[^0-9].*|$)        # End of string from end of date
            """,
            re.VERBOSE,
        )
        match = pattern.search(string)
        if match:
            try:
                return (
                    date(
                        int(match.group("year")), int(match.group("month")), int(match.group("day"))
                    ),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None

        return None  # type: ignore [unreachable]

    @staticmethod
    def yyyy_dd_mm(string: str) -> tuple[date, str] | None:
        """Search for a date in the format yyyy-dd-mm.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            # (?:.*[^0-9]|^)
            (?P<found>
                (?P<year>{DatePattern.pattern_year})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_inflexible})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month})
            )
            # (?:[^0-9].*|$)
            """,
            re.VERBOSE,
        )
        match = pattern.search(string)
        if match:
            try:
                return (
                    date(
                        int(match.group("year")), int(match.group("month")), int(match.group("day"))
                    ),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None

        return None  # type: ignore [unreachable]

    @staticmethod
    def month_dd_yyyy(string: str) -> tuple[date, str] | None:
        """Search for a date in the format month dd, yyyy.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            (?P<found>
                (?P<month>{DatePattern.pattern_months})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_flexible})(?:nd|rd|th|st)?
                {DatePattern.pattern_separator}
                (?P<year>{DatePattern.pattern_year})
            )
            ([^0-9].*|$) # End of string from end of date)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            month = int(MonthToNumber.num_from_name(match.group("month")))

            try:
                return (
                    date(int(match.group("year")), month, int(match.group("day"))),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None  # type: ignore [unreachable]

    @staticmethod
    def dd_month_yyyy(string: str) -> tuple[date, str] | None:
        """Search for a date in the format dd month yyyy.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            (?:.*[^0-9]|^) # text before date
            (?P<found>
                (?P<day>{DatePattern.pattern_day_flexible})(?:nd|rd|th|st)?
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_months})
                {DatePattern.pattern_separator}
                (?P<year>{DatePattern.pattern_year})
            )
            (?:[^0-9].*|$) # text after date (7)
        """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            month = int(MonthToNumber.num_from_name(match.group("month")))
            try:
                return (
                    date(int(match.group("year")), month, int(match.group("day"))),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None  # type: ignore [unreachable]

    @staticmethod
    def month_dd(string: str) -> tuple[date, str] | None:
        """Search for a date in the format month dd.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            (?P<found>
                (?P<month>{DatePattern.pattern_months})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_flexible})(?:nd|rd|th|st)?
            )
            ([^0-9].*|$) # End of string from end of date)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            month = int(MonthToNumber.num_from_name(match.group("month")))
            year = datetime.now(tz=timezone.utc).date().year
            try:
                return (
                    date(year, month, int(match.group("day"))),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None  # type: ignore [unreachable]

    @staticmethod
    def month_yyyy(string: str) -> tuple[date, str] | None:
        """Search for a date in the format month yyyy.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            (?P<found>
                (?P<month>{DatePattern.pattern_months})
                {DatePattern.pattern_separator}
                (?P<year>{DatePattern.pattern_year})
            )
            ([^0-9].*|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            month = int(MonthToNumber.num_from_name(match.group("month")))
            try:
                return (
                    date(int(match.group("year")), month, 1),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None  # type: ignore [unreachable]

    @staticmethod
    def yyyy_month(string: str) -> tuple[date, str] | None:
        """Search for a date in the format yyyy month.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            (?P<found>
                (?P<year>{DatePattern.pattern_year})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_months})
            )
            ([^0-9].*|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            month = int(MonthToNumber.num_from_name(match.group("month")))
            try:
                return (
                    date(int(match.group("year")), month, 1),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None  # type: ignore [unreachable]

    @staticmethod
    def mmddyyyy(string: str) -> tuple[date, str] | None:
        """Search for a date in the format mmddyyyy.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            (?P<found>
                (?P<month>{DatePattern.pattern_month})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_inflexible})
                {DatePattern.pattern_separator}
                (?P<year>{DatePattern.pattern_year})
            )
            ([^0-9].*|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            try:
                return (
                    date(
                        int(match.group("year")), int(match.group("month")), int(match.group("day"))
                    ),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None  # type: ignore [unreachable]

    @staticmethod
    def ddmmyyyy(string: str) -> tuple[date, str] | None:
        """Search for a date in the format ddmmyyyy.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            (?P<found>
                (?P<day>{DatePattern.pattern_day_inflexible})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month})
                {DatePattern.pattern_separator}
                (?P<year>{DatePattern.pattern_year})
            )
            ([^0-9].*|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            try:
                return (
                    date(
                        int(match.group("year")), int(match.group("month")), int(match.group("day"))
                    ),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None  # type: ignore [unreachable]

    @staticmethod
    def mm_dd(string: str) -> tuple[date, str] | None:
        """Search for a date in the format mm-dd.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            (?:^|[^0-9])
            (?P<found>
                (?P<month>{DatePattern.pattern_month})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_inflexible})
            )
            (?:[^0-9]|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            year = datetime.now(tz=timezone.utc).date().year
            try:
                return (
                    date(year, int(match.group("month")), int(match.group("day"))),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None  # type: ignore [unreachable]

    @staticmethod
    def dd_mm(string: str) -> tuple[date, str] | None:
        """Search for a date in the format dd-mm.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            (?:^|[^0-9])
            (?P<found>
                (?P<day>{DatePattern.pattern_day_inflexible})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month})
            )
            (?:[^0-9]|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            year = datetime.now(tz=timezone.utc).date().year
            try:
                return (
                    date(year, int(match.group("month")), int(match.group("day"))),
                    str(match.group("found")),
                )
            except ValueError as e:
                logger.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None  # type: ignore [unreachable]

    @staticmethod
    def today(string: str) -> tuple[date, str] | None:
        """Search for a date in the format today.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            r"""
            (?:^|[^0-9])
            (?P<found>
                (?P<today>today'?s?)
            )
            (?:[^0-9]|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            return (
                datetime.now(tz=timezone.utc).date(),
                str(match.group("found")),
            )
        return None  # type: ignore [unreachable]

    @staticmethod
    def yesterday(string: str) -> tuple[date, str] | None:
        """Search for a date in the format yesterday.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            r"""
            (?:^|[^0-9])
            (?P<found>
                (?P<yesterday>yesterday'?s?)
            )
            (?:[^0-9]|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            yesterday = datetime.now(tz=timezone.utc).date() - timedelta(days=1)
            return (
                date(yesterday.year, yesterday.month, yesterday.day),
                str(match.group("found")),
            )
        return None  # type: ignore [unreachable]

    @staticmethod
    def tomorrow(string: str) -> tuple[date, str] | None:
        """Search for a date in the format tomorrow.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            r"""
            (?:^|[^0-9])
            (?P<found>
                (?P<tomorrow>tomorrow'?s?)
            )
            (?:[^0-9]|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            tomorrow = datetime.now(tz=timezone.utc).date() + timedelta(days=1)
            return (
                date(tomorrow.year, tomorrow.month, tomorrow.day),
                str(match.group("found")),
            )
        return None  # type: ignore [unreachable]

    @staticmethod
    def last_week(string: str) -> tuple[date, str] | None:
        """Search for a date in the format last week.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            r"""
            (?:^|[^0-9])
            (?P<found>
                (?P<last_week>last[- _\.]?week'?s?)
            )
            (?:[^0-9]|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            return (
                datetime.now(tz=timezone.utc).date() - timedelta(days=7),
                str(match.group("found")),
            )
        return None  # type: ignore [unreachable]

    @staticmethod
    def last_month(string: str) -> tuple[date, str] | None:
        """Search for a date in the format last month.

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            r"""
            (?:^|[^0-9])
            (?P<found>
                (?P<last_month>last[- _\.]?month'?s?)
            )
            (?:[^0-9]|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        today = datetime.now(tz=timezone.utc).date()
        last_month = (today.replace(day=1) - timedelta(days=today.replace(day=1).day)).replace(
            day=1
        )

        match = pattern.search(string)
        if match:
            return (
                last_month,
                str(match.group("found")),
            )
        return None  # type: ignore [unreachable]


class Date:
    """Date class for jdfile."""

    def __init__(self, date_format: str, string: str, ctime: datetime | None = None) -> None:
        """Initialize the Date class.

        Args:
            date_format (str): Date format to use.
            string (str): String to search for a date.
            ctime (datetime, optional): Creation time of the file. Defaults to None.
        """
        self.original_string = string
        self.date_format = date_format
        self.ctime = ctime
        if self.date_format is None:
            self.date, self.found_string, self.reformatted_date = None, None, None
        else:
            self.date, self.found_string = self._find_date()
            self.reformatted_date = self._reformat_date()

    def __repr__(self) -> str:
        """Return a string representation of the Date object."""
        return f"{self.found_string} -> {self.reformatted_date}"

    def _find_date(self) -> tuple:  # noqa: C901,PLR0911,PLR0912
        """Find date in a string and reformat it to self.date_format. If no date is found, return None.

        Args:
            text (str): The text to search for dates

        Returns:
            (tuple) A tuple containing the reformatted date and the date string found in the input.
        """
        date_search = DatePattern()
        if date_search.yyyy_mm_dd(self.original_string):
            return date_search.yyyy_mm_dd(self.original_string)

        if date_search.yyyy_dd_mm(self.original_string):  # pragma: no cover
            return date_search.yyyy_dd_mm(self.original_string)

        if date_search.month_dd_yyyy(self.original_string):  # pragma: no cover
            return date_search.month_dd_yyyy(self.original_string)

        if date_search.dd_month_yyyy(self.original_string):  # pragma: no cover
            return date_search.dd_month_yyyy(self.original_string)

        if date_search.month_dd(self.original_string):  # pragma: no cover
            return date_search.month_dd(self.original_string)

        if date_search.month_yyyy(self.original_string):  # pragma: no cover
            return date_search.month_yyyy(self.original_string)

        if date_search.yyyy_month(self.original_string):  # pragma: no cover
            return date_search.yyyy_month(self.original_string)

        if date_search.mmddyyyy(self.original_string):  # pragma: no cover
            return date_search.mmddyyyy(self.original_string)

        if date_search.ddmmyyyy(self.original_string):  # pragma: no cover
            return date_search.ddmmyyyy(self.original_string)

        if date_search.mm_dd(self.original_string):  # pragma: no cover
            return date_search.mm_dd(self.original_string)

        if date_search.dd_mm(self.original_string):  # pragma: no cover
            return date_search.dd_mm(self.original_string)

        if date_search.today(self.original_string):  # pragma: no cover
            return date_search.today(self.original_string)

        if date_search.yesterday(self.original_string):  # pragma: no cover
            return date_search.yesterday(self.original_string)

        if date_search.tomorrow(self.original_string):  # pragma: no cover
            return date_search.tomorrow(self.original_string)

        if date_search.last_week(self.original_string):  # pragma: no cover
            return date_search.last_week(self.original_string)

        if date_search.last_month(self.original_string):  # pragma: no cover
            return date_search.last_month(self.original_string)

        if self.ctime:
            return date(self.ctime.year, self.ctime.month, self.ctime.day), None

        return None, None

    def _reformat_date(self) -> str:
        """Reformat the date to self.date_format.

        Returns:
            str: Reformatted date.
        """
        if self.date:
            try:
                return self.date.strftime(self.date_format)
            except ValueError as e:
                logger.trace(f"Error while reformatting date {self.date}: {e}")
                self.date, self.found_string, self.reformatted_date = None, None, None
        return None
