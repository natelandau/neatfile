"""Date class for neatfile."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import ClassVar

import regex as re
from nclutils import pp

from neatfile import settings
from neatfile.constants import DateRegion


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

    pattern_day_flexible: ClassVar[str] = r"[12][0-9]|3[01]|0?[1-9]"
    pattern_day_inflexible: ClassVar[str] = r"0[1-9]|[12][0-9]|3[01]"
    pattern_month: ClassVar[str] = r"0[1-9]|1[012]"
    pattern_month_flexible: ClassVar[str] = r"0?[1-9]|1[012]"
    pattern_months: ClassVar[str] = (
        r"january|jan?|february|feb?|march|mar?|april|apr?|may|june?|july?|august|aug?|september|sep?t?|october|oct?|november|nov?|december|dec?"
    )
    _sep_chars: ClassVar[str] = r"-\./_, :"  # Define separator chars for reuse
    pattern_separator: ClassVar[str] = rf"[{_sep_chars}]*?"
    pattern_year: ClassVar[str] = r"20[0-3][0-9]"
    pattern_year_flexible: ClassVar[str] = r"20[0-3][0-9]|[0-3][0-9]"
    pattern_start: ClassVar[str] = rf"(?<![0-9][{_sep_chars}]*)"
    pattern_end: ClassVar[str] = rf"(?![0-9]|[{_sep_chars}][0-9])"

    # Done
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
            # {DatePattern.pattern_start}
            (?P<found>
                (?P<year>{DatePattern.pattern_year})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_inflexible})
            )
            # {DatePattern.pattern_end}
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None

        return None

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
            {DatePattern.pattern_start}
            (?P<found>
                (?P<year>{DatePattern.pattern_year})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_inflexible})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month})
            )
            {DatePattern.pattern_end}
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None

        return None

    # Done
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None

    # Done
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None

    # Done
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None

    # Done
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None

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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None

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
            {DatePattern.pattern_start}
            (?P<found>
                (?P<month>{DatePattern.pattern_month})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_inflexible})
                {DatePattern.pattern_separator}
                (?P<year>{DatePattern.pattern_year})
            )
            {DatePattern.pattern_end}
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None

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
            {DatePattern.pattern_start}
            (?P<found>
                (?P<day>{DatePattern.pattern_day_inflexible})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month})
                {DatePattern.pattern_separator}
                (?P<year>{DatePattern.pattern_year})
            )
            {DatePattern.pattern_end}
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None

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
            {DatePattern.pattern_start}
            (?P<found>
                (?P<month>{DatePattern.pattern_month})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_inflexible})
            )
            {DatePattern.pattern_end}
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None

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
            {DatePattern.pattern_start}
            (?P<found>
                (?P<day>{DatePattern.pattern_day_inflexible})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month})
            )
            {DatePattern.pattern_end}
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
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None
        return None

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
            # (?:^|[^0-9])
            (?P<found>
                (?P<today>today'?s?)
            )
            # (?:[^0-9]|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            return (
                datetime.now(tz=timezone.utc).date(),
                str(match.group("found")),
            )
        return None

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
            # (?:^|[^0-9])
            (?P<found>
                (?P<yesterday>yesterday'?s?)
            )
            # (?:[^0-9]|$)
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
        return None

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
            # (?:^|[^0-9])
            (?P<found>
                (?P<tomorrow>tomorrow'?s?)
            )
            # (?:[^0-9]|$)
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
        return None

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
            # (?:^|[^0-9])
            (?P<found>
                (?P<last_week>last[- _\.]?week'?s?)
            )
            # (?:[^0-9]|$)
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            return (
                datetime.now(tz=timezone.utc).date() - timedelta(days=7),
                str(match.group("found")),
            )
        return None

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
            # (?:^|[^0-9])
            (?P<found>
                (?P<last_month>last[- _\.]?month'?s?)
            )
            # (?:[^0-9]|$)
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
        return None

    @staticmethod
    def eu_ambiguous(string: str) -> tuple[date, str] | None:
        """Search for a date in the format dmyy or ddmmyy.

        Matches dates in european format (dd/mm/yyyy)

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            {DatePattern.pattern_start}
            (?P<found>
                (?P<day>{DatePattern.pattern_day_flexible})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month_flexible})
                {DatePattern.pattern_separator}
                (?P<year>{DatePattern.pattern_year_flexible})
            )
            {DatePattern.pattern_end}
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            try:
                return (
                    date(
                        year=int(match.group("year"))
                        if len(match.group("year")) == 4  # noqa: PLR2004
                        else int(match.group("year")) + 2000,
                        month=int(match.group("month")),
                        day=int(match.group("day")),
                    ),
                    str(match.group("found")),
                )
            except ValueError as e:
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None

        return None

    @staticmethod
    def us_ambiguous(string: str) -> tuple[date, str] | None:
        """Search for a date in the format mmddyy or mddmmyy.

        Matches dates in US format (mm/dd/yyyy)

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            {DatePattern.pattern_start}
            (?P<found>
                (?P<month>{DatePattern.pattern_month_flexible})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_flexible})
                {DatePattern.pattern_separator}
                (?P<year>{DatePattern.pattern_year_flexible})
            )
            {DatePattern.pattern_end}
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            try:
                return (
                    date(
                        year=int(match.group("year"))
                        if len(match.group("year")) == 4  # noqa: PLR2004
                        else int(match.group("year")) + 2000,
                        month=int(match.group("month")),
                        day=int(match.group("day")),
                    ),
                    str(match.group("found")),
                )
            except ValueError as e:
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None

        return None

    @staticmethod
    def jp_ambiguous(string: str) -> tuple[date, str] | None:
        """Search for a date in the format yymmdd or yymmdd.

        Matches dates in Japanese format (yyyy/mm/dd)

        Args:
            string (str): String to search for a date.

        Returns:
            tuple[date, str]: A tuple containing the date and the date string found.
        """
        pattern = re.compile(
            rf"""
            {DatePattern.pattern_start}
            (?P<found>
                (?P<year>{DatePattern.pattern_year_flexible})
                {DatePattern.pattern_separator}
                (?P<month>{DatePattern.pattern_month_flexible})
                {DatePattern.pattern_separator}
                (?P<day>{DatePattern.pattern_day_flexible})
            )
            {DatePattern.pattern_end}
            """,
            re.VERBOSE | re.IGNORECASE,
        )
        match = pattern.search(string)
        if match:
            try:
                return (
                    date(
                        year=int(match.group("year"))
                        if len(match.group("year")) == 4  # noqa: PLR2004
                        else int(match.group("year")) + 2000,
                        month=int(match.group("month")),
                        day=int(match.group("day")),
                    ),
                    str(match.group("found")),
                )
            except ValueError as e:
                pp.trace(f"Error while reformatting date {match}: {e}")
                return None

        return None


class Date:
    """Date class for neatfile."""

    def __init__(self, string: str, ctime: datetime | None = None) -> None:
        """Initialize the Date class.

        Args:
            string (str): String to search for a date.
            ctime (datetime, optional): Creation time of the file. Defaults to None.
        """
        self.original_string = string
        self.ctime = ctime
        if not settings.date_format:
            self.date, self.found_string, self.reformatted_date = None, None, ""
        else:
            self.date, self.found_string = self._find_date()
            self.reformatted_date = self._reformat_date()

    def __repr__(self) -> str:
        """Return a string representation of the Date object."""
        return f"{self.found_string} -> {self.reformatted_date}"

    def _find_date(self) -> tuple[date | None, str | None]:
        """Find date in a string and reformat it to settings.date_format. If no date is found, return None.

        Args:
            text (str): The text to search for dates

        Returns:
            tuple[date | None, str | None]: A tuple containing the reformatted date and the date string found in the input.
        """
        date_search = DatePattern()

        # List of pattern-matching methods to try in sequence
        pattern_methods = [
            date_search.yyyy_mm_dd,
            date_search.yyyy_dd_mm,
            date_search.month_dd_yyyy,
            date_search.dd_month_yyyy,
            date_search.month_dd,
            date_search.month_yyyy,
            date_search.yyyy_month,
            date_search.mmddyyyy,
            date_search.ddmmyyyy,
            date_search.mm_dd,
            date_search.dd_mm,
            date_search.today,
            date_search.yesterday,
            date_search.tomorrow,
            date_search.last_week,
            date_search.last_month,
        ]

        # Dictionary mapping regions to their pattern-matching methods
        region_patterns = {
            DateRegion.EU: date_search.eu_ambiguous,
            DateRegion.US: date_search.us_ambiguous,
            DateRegion.JP: date_search.jp_ambiguous,
        }

        # Try each pattern method in sequence
        for method in pattern_methods:
            if result := method(self.original_string):
                return result

        # Try region-specific pattern if applicable
        if region_method := region_patterns.get(settings.date_region):  # noqa: SIM102
            if result := region_method(self.original_string):
                return result

        # Fall back to ctime if available
        if self.ctime:
            return date(self.ctime.year, self.ctime.month, self.ctime.day), None

        return None, None

    def _reformat_date(self) -> str:
        """Reformat the date to settings.date_format.

        Returns:
            str: Reformatted date.
        """
        if self.date:
            try:
                return self.date.strftime(settings.date_format)
            except ValueError as e:
                pp.trace(f"Error while reformatting date {self.date}: {e}")
                self.date, self.found_string, self.reformatted_date = None, None, None
        return None
