"""Load and validate the settings for one run of the CLI."""

from __future__ import annotations

import os
import re
import tomllib
from collections import ChainMap
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tzlocal import get_localzone

from neatfile import constants
from neatfile.constants import (
    DateFirst,
    InsertLocation,
    ProjectType,
    Separator,
    TransformCase,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from datetime import tzinfo


class ConfigError(Exception):
    """Report every invalid setting found while loading the configuration.

    Attributes:
        errors: One line per invalid setting, naming the key, source, bad value, and what is allowed.
    """

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors: tuple[str, ...] = tuple(errors)
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class ProjectConfig:
    """Describe the project folder selected with `--project`."""

    name: str
    path: Path
    depth: int
    project_type: ProjectType


@dataclass(frozen=True)
class Config:
    """Hold the resolved, validated settings for one run of the CLI."""

    date_first: DateFirst
    date_format: str
    ignore_dotfiles: bool
    ignore_file_regex: re.Pattern[str]
    ignored_files: tuple[str, ...]
    insert_location: InsertLocation
    match_case_list: tuple[str, ...]
    overwrite_existing: bool
    separator: Separator
    split_words: bool
    stopwords: tuple[str, ...]
    strip_stopwords: bool
    transform_case: TransformCase
    tz: tzinfo
    undo_history_runs: int
    user_terms: tuple[str, ...]
    project: ProjectConfig | None


@dataclass(frozen=True)
class RunOptions:
    """Hold the CLI-only values for one run that are not configuration settings."""

    files: tuple[Path, ...] = ()
    dry_run: bool = False
    force: bool = False
    confirm_changes: bool = False
    date: str | None = None
    date_only: bool = False
    file_search_depth: int = 1


_SETTING_NAMES: tuple[str, ...] = tuple(
    field.name for field in fields(Config) if field.name != "project"
)
_ENV_PREFIX = "NEATFILE_"
# Lists that combine the global and project values instead of replacing one with the other
_MERGED_LIST_SETTINGS = frozenset({"ignored_files", "match_case_list", "stopwords"})
# Settings that cannot differ per project because the undo journal is one file shared by all projects
_GLOBAL_ONLY_SETTINGS = frozenset({"undo_history_runs"})
_DEFAULT_PROJECT_DEPTH = 2
_DEFAULT_PROJECT_TYPE = ProjectType.FOLDER
PROJECT_NOT_FOUND_MESSAGE = "Project `{project_name}` not found in the configuration file."


@dataclass(frozen=True)
class _SourcedValue:
    """Pair a raw setting value with where it came from, for error messages."""

    value: object
    source: str


@dataclass(frozen=True)
class _ProjectSection:
    """Hold one `[projects.NAME]` table and the file that defined it."""

    table: dict[str, object]
    source: str


class _InvalidValueError(Exception):
    """Signal that a raw value cannot convert, carrying what was expected."""

    def __init__(self, expected: str) -> None:
        self.expected = expected
        super().__init__(expected)


class _SettingError(Exception):
    """Signal that one setting has no valid value, carrying the line to report for it."""


def _to_bool(sourced: _SourcedValue) -> bool:
    if isinstance(sourced.value, bool):
        return sourced.value
    msg = "a boolean (true or false)"
    raise _InvalidValueError(msg)


def _to_non_negative_int(sourced: _SourcedValue) -> int:
    # bool is an int subclass, so reject it explicitly
    if (
        isinstance(sourced.value, int)
        and not isinstance(sourced.value, bool)
        and sourced.value >= 0
    ):
        return sourced.value
    msg = "a whole number of 0 or more"
    raise _InvalidValueError(msg)


def _to_str(sourced: _SourcedValue) -> str:
    if isinstance(sourced.value, str):
        return sourced.value
    msg = "a string"
    raise _InvalidValueError(msg)


def _to_str_tuple(sourced: _SourcedValue) -> tuple[str, ...]:
    value = sourced.value
    if isinstance(value, list | tuple) and all(isinstance(item, str) for item in value):
        return tuple(cast("list[str] | tuple[str, ...]", value))
    msg = "a list of strings"
    raise _InvalidValueError(msg)


def _enum_converter[EnumT: Enum](enum_type: type[EnumT]) -> Callable[[_SourcedValue], EnumT]:
    def convert(sourced: _SourcedValue) -> EnumT:
        if isinstance(sourced.value, str) and sourced.value.upper() in enum_type.__members__:
            return enum_type[sourced.value.upper()]
        allowed = ", ".join(name.lower() for name in enum_type.__members__)
        msg = f"one of: {allowed}"
        raise _InvalidValueError(msg)

    return convert


def _to_regex(sourced: _SourcedValue) -> re.Pattern[str]:
    pattern = _to_str(sourced) or "^$"
    try:
        return re.compile(pattern)
    except re.error as e:
        msg = f"a valid regular expression ({e})"
        raise _InvalidValueError(msg) from e


def _to_timezone(sourced: _SourcedValue) -> tzinfo:
    name = _to_str(sourced)
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as e:
        msg = "an IANA time zone name such as America/New_York"
        raise _InvalidValueError(msg) from e


_to_date_first = _enum_converter(DateFirst)
_to_insert_location = _enum_converter(InsertLocation)
_to_separator = _enum_converter(Separator)
_to_transform_case = _enum_converter(TransformCase)

# Converters for the settings that take the single highest-precedence value
_SCALAR_CONVERTERS: dict[str, Callable[[_SourcedValue], object]] = {
    "date_first": _to_date_first,
    "date_format": _to_str,
    "ignore_dotfiles": _to_bool,
    "ignore_file_regex": _to_regex,
    "insert_location": _to_insert_location,
    "overwrite_existing": _to_bool,
    "separator": _to_separator,
    "split_words": _to_bool,
    "strip_stopwords": _to_bool,
    "transform_case": _to_transform_case,
    "undo_history_runs": _to_non_negative_int,
    "user_terms": _to_str_tuple,
}
_BOOL_SETTINGS = frozenset(
    key for key, convert in _SCALAR_CONVERTERS.items() if convert is _to_bool
)
_INTEGER_SETTINGS = frozenset(
    key for key, convert in _SCALAR_CONVERTERS.items() if convert is _to_non_negative_int
)
_LIST_SETTINGS = _MERGED_LIST_SETTINGS | {
    key for key, convert in _SCALAR_CONVERTERS.items() if convert is _to_str_tuple
}


def _parse_environment_value(key: str, text: str) -> object:
    """Turn environment text into the raw value a config file would hold for `key`.

    Only list settings parse as TOML, so text such as `2023-01-01` stays a string. Text that
    does not fit the setting is returned unchanged for the converter to reject.
    """
    if key in _INTEGER_SETTINGS and text.isascii() and text.isdigit():
        return int(text)
    if key in _BOOL_SETTINGS and text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if key in _LIST_SETTINGS:
        try:
            return tomllib.loads(f"v = {text}")["v"]
        except tomllib.TOMLDecodeError:
            return text
    return text


def _read_config_files(
    paths: Sequence[Path], errors: list[str]
) -> tuple[dict[str, _SourcedValue], dict[str, _ProjectSection]]:
    settings_layer: dict[str, _SourcedValue] = {}
    projects: dict[str, _ProjectSection] = {}
    for path in paths:
        if not path.is_file():
            continue
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except tomllib.TOMLDecodeError as e:
            errors.append(f"{path}: invalid TOML ({e})")
            continue
        except UnicodeDecodeError as e:
            errors.append(f"{path}: cannot read file; expected UTF-8 text ({e})")
            continue
        except OSError as e:
            errors.append(f"{path}: cannot read file ({e})")
            continue
        source = str(path)
        settings_layer.update(
            {
                key: _SourcedValue(value=data[key], source=source)
                for key in _SETTING_NAMES
                if key in data
            }
        )
        project_tables = data.get("projects", {})
        if not isinstance(project_tables, dict):
            errors.append(
                f"`projects` from {source}: {project_tables!r} is invalid; expected a table"
            )
            continue
        for name, table in project_tables.items():
            if isinstance(table, dict):
                projects[name] = _ProjectSection(table=table, source=source)
            else:
                errors.append(
                    f"`projects.{name}` from {source}: {table!r} is invalid; expected a table"
                )
    return settings_layer, projects


def _read_environment(environ: Mapping[str, str]) -> dict[str, _SourcedValue]:
    layer: dict[str, _SourcedValue] = {}
    for key in _SETTING_NAMES:
        variable = f"{_ENV_PREFIX}{key.upper()}"
        if variable in environ:
            layer[key] = _SourcedValue(
                value=_parse_environment_value(key=key, text=environ[variable]),
                source=f"environment variable {variable}",
            )
    return layer


def _build_project(
    name: str, section: _ProjectSection, errors: list[str]
) -> tuple[ProjectConfig | None, dict[str, _SourcedValue]]:
    table = section.table
    prefix = f"Project `{name}` in {section.source}"
    project_errors: list[str] = []

    raw_path = table.get("path")
    path = Path(raw_path) if isinstance(raw_path, str) and raw_path else None
    if path is None:
        project_errors.append(f"{prefix}: `path` is {raw_path!r}; expected a non-empty string")

    raw_depth = table.get("depth", _DEFAULT_PROJECT_DEPTH)
    depth = raw_depth if isinstance(raw_depth, int) and not isinstance(raw_depth, bool) else None
    if depth is None:
        project_errors.append(f"{prefix}: `depth` is {raw_depth!r}; expected an integer")

    project_type: ProjectType | None = _DEFAULT_PROJECT_TYPE
    if "type" in table:
        try:
            project_type = _enum_converter(ProjectType)(
                _SourcedValue(value=table["type"], source=prefix)
            )
        except _InvalidValueError as e:
            project_type = None
            project_errors.append(f"{prefix}: `type` is {table['type']!r}; expected {e.expected}")

    project_errors.extend(
        f"{prefix}: `{key}` can only be set at the top level of the config file"
        for key in sorted(_GLOBAL_ONLY_SETTINGS & table.keys())
    )

    if path is None or depth is None or project_type is None or project_errors:
        errors.extend(project_errors)
        return None, {}

    source = f"project {name} in {section.source}"
    overrides = {
        key: _SourcedValue(value=table[key], source=source)
        for key in _SETTING_NAMES
        if key in table and key not in _GLOBAL_ONLY_SETTINGS
    }
    project = ProjectConfig(name=name, path=path, depth=depth, project_type=project_type)
    return project, overrides


class _SettingResolver:
    """Convert layered raw values into typed settings, raising one error per invalid setting."""

    def __init__(
        self,
        *,
        cli_layer: dict[str, _SourcedValue],
        environment_layer: dict[str, _SourcedValue],
        project_layer: dict[str, _SourcedValue],
        file_layer: dict[str, _SourcedValue],
    ) -> None:
        """Order the layers by precedence for single values and for merged lists."""
        self.values = ChainMap(cli_layer, environment_layer, project_layer, file_layer)
        # The project's list joins the global list, except that a CLI list replaces both
        self.global_lists = ChainMap(cli_layer, environment_layer, file_layer)
        self.project_lists = {
            key: sourced for key, sourced in project_layer.items() if key not in cli_layer
        }

    @staticmethod
    def _convert[T](key: str, sourced: _SourcedValue, converter: Callable[[_SourcedValue], T]) -> T:
        try:
            return converter(sourced)
        except _InvalidValueError as e:
            msg = (
                f"`{key}` from {sourced.source}: {sourced.value!r} is invalid; "
                f"expected {e.expected}"
            )
            raise _SettingError(msg) from e

    @staticmethod
    def _missing(key: str) -> _SettingError:
        return _SettingError(
            f"`{key}` has no value; expected it in {constants.DEFAULT_CONFIG_PATH}"
        )

    def setting[T](self, key: str, converter: Callable[[_SourcedValue], T]) -> T:
        """Convert the value from the highest-precedence layer that sets `key`.

        Returns:
            T: The converted value.

        Raises:
            _SettingError: If no layer sets `key` or its value cannot convert.
        """
        sourced = self.values.get(key)
        if sourced is None:
            raise self._missing(key)
        return self._convert(key=key, sourced=sourced, converter=converter)

    def merged_list(self, key: str) -> tuple[str, ...]:
        """Combine the global and project lists for `key`, deduplicated and sorted.

        Returns:
            tuple[str, ...]: The combined list.

        Raises:
            _SettingError: If no layer sets `key` or a list cannot convert.
        """
        sourced_lists = [
            sourced
            for sourced in (self.global_lists.get(key), self.project_lists.get(key))
            if sourced is not None
        ]
        if not sourced_lists:
            raise self._missing(key)
        items = {
            item
            for sourced in sourced_lists
            for item in self._convert(key=key, sourced=sourced, converter=_to_str_tuple)
        }
        return tuple(sorted(items))

    def timezone(self) -> tzinfo:
        """Convert `tz`, falling back to the local zone because the default file omits it.

        Returns:
            tzinfo: The configured or local time zone.
        """
        if "tz" not in self.values:
            return get_localzone()
        return self.setting(key="tz", converter=_to_timezone)

    def errors(self) -> list[str]:
        """Convert every setting once and list one error for each setting that fails.

        Returns:
            list[str]: The error for each invalid or missing setting, in field order.
        """
        errors: list[str] = []
        for key in _SETTING_NAMES:
            try:
                if key == "tz":
                    self.timezone()
                elif key in _MERGED_LIST_SETTINGS:
                    self.merged_list(key)
                else:
                    self.setting(key=key, converter=_SCALAR_CONVERTERS[key])
            except _SettingError as e:
                errors.append(str(e))
        return errors

    def build(self, project: ProjectConfig | None) -> Config:
        """Build the settings, once `errors` has reported no problems.

        Returns:
            Config: The converted settings.
        """
        return Config(
            date_first=self.setting(key="date_first", converter=_to_date_first),
            date_format=self.setting(key="date_format", converter=_to_str),
            ignore_dotfiles=self.setting(key="ignore_dotfiles", converter=_to_bool),
            ignore_file_regex=self.setting(key="ignore_file_regex", converter=_to_regex),
            ignored_files=self.merged_list("ignored_files"),
            insert_location=self.setting(key="insert_location", converter=_to_insert_location),
            match_case_list=self.merged_list("match_case_list"),
            overwrite_existing=self.setting(key="overwrite_existing", converter=_to_bool),
            separator=self.setting(key="separator", converter=_to_separator),
            split_words=self.setting(key="split_words", converter=_to_bool),
            stopwords=self.merged_list("stopwords"),
            strip_stopwords=self.setting(key="strip_stopwords", converter=_to_bool),
            transform_case=self.setting(key="transform_case", converter=_to_transform_case),
            tz=self.timezone(),
            undo_history_runs=self.setting(key="undo_history_runs", converter=_to_non_negative_int),
            user_terms=self.setting(key="user_terms", converter=_to_str_tuple),
            project=project,
        )


def load_config(
    *,
    config_paths: Sequence[Path] | None = None,
    environ: Mapping[str, str] | None = None,
    project_name: str | None = None,
    cli_overrides: Mapping[str, object] | None = None,
) -> Config:
    """Build the validated settings for a run from config files, environment, and CLI flags.

    Layers apply in order, each overriding the ones before: config files, the selected
    `[projects.NAME]` section, `NEATFILE_*` environment variables, then CLI flags. The lists
    `match_case_list`, `stopwords`, and `ignored_files` combine the global and project values.

    Args:
        config_paths: Config files in precedence order. Missing files are skipped. Defaults to
            the package default, user, and development config files.
        environ: Environment variables to read. Defaults to `os.environ`.
        project_name: Name of the `[projects.NAME]` section to apply. Defaults to None.
        cli_overrides: Raw values from CLI flags, keyed by `Config` field name. Defaults to None.

    Returns:
        Config: The resolved settings.

    Raises:
        ConfigError: If any value is invalid or the project is not found, listing every problem.
        ValueError: If `cli_overrides` has a key that is not a `Config` field.
    """
    cli_overrides = cli_overrides or {}
    if unknown_keys := sorted(set(cli_overrides) - set(_SETTING_NAMES)):
        msg = (
            f"Unknown CLI override keys {unknown_keys}; "
            f"expected Config field names: {', '.join(_SETTING_NAMES)}"
        )
        raise ValueError(msg)
    if config_paths is None:
        config_paths = (
            constants.DEFAULT_CONFIG_PATH,
            constants.USER_CONFIG_PATH,
            constants.DEV_CONFIG_PATH,
        )
    environ = os.environ if environ is None else environ

    errors: list[str] = []
    file_layer, project_sections = _read_config_files(paths=config_paths, errors=errors)

    project: ProjectConfig | None = None
    project_layer: dict[str, _SourcedValue] = {}
    if project_name is not None:
        if project_name in project_sections:
            project, project_layer = _build_project(
                name=project_name, section=project_sections[project_name], errors=errors
            )
        else:
            errors.append(PROJECT_NOT_FOUND_MESSAGE.format(project_name=project_name))

    cli_layer = {
        key: _SourcedValue(value=value, source="CLI flag") for key, value in cli_overrides.items()
    }
    resolver = _SettingResolver(
        cli_layer=cli_layer,
        environment_layer=_read_environment(environ),
        project_layer=project_layer,
        file_layer=file_layer,
    )
    errors.extend(resolver.errors())
    if errors:
        raise ConfigError(errors)
    return resolver.build(project)
