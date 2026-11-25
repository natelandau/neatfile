"""Test the typed settings loader."""

from pathlib import Path

import pytest

from neatfile.config import PROJECT_NOT_FOUND_MESSAGE, ConfigError, ProjectConfig, load_config
from neatfile.constants import (
    DEFAULT_CONFIG_PATH,
    DateFallback,
    ProjectType,
    Separator,
    TransformCase,
)


def test_defaults_match_default_config_file() -> None:
    """Verify the default config file alone gives the documented defaults."""
    config = load_config(config_paths=(DEFAULT_CONFIG_PATH,), environ={})

    assert config.separator == Separator.IGNORE
    assert config.transform_case == TransformCase.IGNORE
    assert config.date_format == ""
    assert config.date_fallback == DateFallback.CREATED
    assert config.ignore_file_regex.pattern == "^$"
    assert config.user_terms == ()
    assert config.undo_history_runs == 50
    assert config.project is None


@pytest.mark.parametrize(
    ("file_value", "project_value", "env_value", "cli_value", "expected"),
    [
        pytest.param("dash", None, None, None, Separator.DASH, id="file only"),
        pytest.param("dash", "space", None, None, Separator.SPACE, id="project over file"),
        pytest.param("dash", "space", "period", None, Separator.PERIOD, id="env over project"),
        pytest.param(
            "dash", "space", "period", "UNDERSCORE", Separator.UNDERSCORE, id="cli over env"
        ),
    ],
)
def test_precedence(
    tmp_path: Path,
    file_value: str,
    project_value: str | None,
    env_value: str | None,
    cli_value: str | None,
    expected: Separator,
) -> None:
    """Verify each layer overrides the layers below it."""
    project_line = f'separator = "{project_value}"' if project_value else ""
    user_file = tmp_path / "user.toml"
    user_file.write_text(
        f'separator = "{file_value}"\n[projects.work]\npath = "{tmp_path}"\n{project_line}\n'
    )
    environ = {"NEATFILE_SEPARATOR": env_value} if env_value else {}
    cli_overrides = {"separator": cli_value} if cli_value else None

    config = load_config(
        config_paths=(DEFAULT_CONFIG_PATH, user_file),
        environ=environ,
        project_name="work",
        cli_overrides=cli_overrides,
    )

    assert config.separator == expected


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        pytest.param({}, ("a", "b", "c"), id="file and project"),
        pytest.param({"NEATFILE_STOPWORDS": '["z"]'}, ("a", "c", "z"), id="env replaces file"),
        pytest.param({"NEATFILE_STOPWORDS": "[]"}, ("a", "c"), id="empty env clears file"),
    ],
)
def test_list_settings_merge_global_and_project(
    tmp_path: Path, environ: dict[str, str], expected: tuple[str, ...]
) -> None:
    """Verify list settings combine the global and project lists, deduplicated and sorted."""
    user_file = tmp_path / "user.toml"
    user_file.write_text(
        f'stopwords = ["b", "a"]\n[projects.work]\npath = "{tmp_path}"\nstopwords = ["c", "a"]\n'
    )

    config = load_config(
        config_paths=(DEFAULT_CONFIG_PATH, user_file), environ=environ, project_name="work"
    )

    assert config.stopwords == expected


def test_cli_user_terms_replace_configured_terms(tmp_path: Path) -> None:
    """Verify CLI terms replace the project's terms instead of merging with them."""
    user_file = tmp_path / "user.toml"
    user_file.write_text(f'[projects.work]\npath = "{tmp_path}"\nuser_terms = ["koala"]\n')

    config = load_config(
        config_paths=(DEFAULT_CONFIG_PATH, user_file),
        environ={},
        project_name="work",
        cli_overrides={"user_terms": ("fox",)},
    )

    assert config.user_terms == ("fox",)


@pytest.mark.parametrize(
    ("name", "raw", "field", "expected"),
    [
        pytest.param("NEATFILE_SPLIT_WORDS", "true", "split_words", True, id="toml bool"),
        pytest.param("NEATFILE_SPLIT_WORDS", "False", "split_words", False, id="capital bool"),
        pytest.param("NEATFILE_SPLIT_WORDS", "TRUE", "split_words", True, id="upper bool"),
        pytest.param(
            "NEATFILE_STOPWORDS",
            '["draft", "final"]',
            "stopwords",
            ("draft", "final"),
            id="toml list",
        ),
        pytest.param("NEATFILE_SEPARATOR", "dash", "separator", Separator.DASH, id="raw enum"),
        pytest.param(
            "NEATFILE_DATE_FALLBACK",
            "modified",
            "date_fallback",
            DateFallback.MODIFIED,
            id="date fallback enum",
        ),
        pytest.param("NEATFILE_DATE_FORMAT", "2024", "date_format", "2024", id="int-like string"),
        pytest.param(
            "NEATFILE_DATE_FORMAT", "2023-01-01", "date_format", "2023-01-01", id="date-like string"
        ),
    ],
)
def test_env_value_parsing(name: str, raw: str, field: str, expected: object) -> None:
    """Verify environment text converts by the setting's type, with lists parsed as TOML."""
    config = load_config(config_paths=(DEFAULT_CONFIG_PATH,), environ={name: raw})

    assert getattr(config, field) == expected


def test_env_empty_ignore_file_regex_matches_nothing() -> None:
    """Verify an empty regex from the environment becomes the match-nothing pattern."""
    config = load_config(
        config_paths=(DEFAULT_CONFIG_PATH,), environ={"NEATFILE_IGNORE_FILE_REGEX": ""}
    )

    assert config.ignore_file_regex.pattern == "^$"


def test_unknown_env_variables_are_ignored() -> None:
    """Verify NEATFILE_ variables that name no setting do not affect loading."""
    config = load_config(
        config_paths=(DEFAULT_CONFIG_PATH,), environ={"NEATFILE_MODEL_DIR": "models"}
    )

    assert config == load_config(config_paths=(DEFAULT_CONFIG_PATH,), environ={})


def test_unknown_cli_override_raises_value_error() -> None:
    """Verify a CLI override key that names no setting fails loudly instead of being dropped."""
    with pytest.raises(ValueError, match="overwrite"):
        load_config(
            config_paths=(DEFAULT_CONFIG_PATH,), environ={}, cli_overrides={"overwrite": True}
        )


def test_unreadable_config_file_is_reported(tmp_path: Path) -> None:
    """Verify a config file that is not UTF-8 becomes an error naming the file."""
    user_file = tmp_path / "user.toml"
    user_file.write_bytes(b'separator = "' + bytes([0xFF, 0xFE]) + b'"\n')

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_paths=(DEFAULT_CONFIG_PATH, user_file), environ={})

    assert str(user_file) in str(exc_info.value)
    assert "UTF-8" in str(exc_info.value)


def test_project_section_builds_project_config(tmp_path: Path) -> None:
    """Verify a project section becomes a ProjectConfig named by its table key."""
    user_file = tmp_path / "user.toml"
    user_file.write_text(f'[projects.work]\npath = "{tmp_path}"\ndepth = 3\ntype = "jd"\n')

    config = load_config(
        config_paths=(DEFAULT_CONFIG_PATH, user_file), environ={}, project_name="work"
    )

    assert config.project == ProjectConfig(
        name="work", path=tmp_path, depth=3, project_type=ProjectType.JD
    )


@pytest.mark.parametrize(
    ("toml", "environ", "expected_substrings"),
    [
        pytest.param(
            'ignore_dotfiles = "false"', {}, ["ignore_dotfiles", "'false'", "bool"], id="file bool"
        ),
        pytest.param('stopwords = "draft"', {}, ["stopwords", "'draft'", "list"], id="file list"),
        pytest.param(
            "",
            {"NEATFILE_STOPWORDS": "draft"},
            ["stopwords", "NEATFILE_STOPWORDS", "'draft'", "list"],
            id="env list",
        ),
        pytest.param(
            "",
            {"NEATFILE_SEPARATOR": "bogus"},
            ["separator", "NEATFILE_SEPARATOR", "bogus", "dash"],
            id="env enum",
        ),
        pytest.param(
            "",
            {"NEATFILE_SEPARATOR": ""},
            ["separator", "NEATFILE_SEPARATOR", "''", "dash"],
            id="env empty enum",
        ),
        pytest.param("ignore_file_regex = '['", {}, ["ignore_file_regex", "'['"], id="regex"),
        pytest.param('tz = "Mars/Olympus"', {}, ["tz", "Mars/Olympus"], id="time zone"),
    ],
)
def test_invalid_value_error_names_key_source_and_value(
    tmp_path: Path, toml: str, environ: dict[str, str], expected_substrings: list[str]
) -> None:
    """Verify an invalid value raises a ConfigError naming the key, source, and value."""
    user_file = tmp_path / "user.toml"
    user_file.write_text(toml)

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_paths=(DEFAULT_CONFIG_PATH, user_file), environ=environ)

    message = str(exc_info.value)
    for substring in expected_substrings:
        assert substring in message
    if toml:
        assert str(user_file) in message


def test_invalid_values_are_all_reported(tmp_path: Path) -> None:
    """Verify every invalid value is collected into one ConfigError."""
    user_file = tmp_path / "user.toml"
    user_file.write_text('split_words = "yes"\nstopwords = "draft"\n')

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_paths=(DEFAULT_CONFIG_PATH, user_file), environ={})

    assert len(exc_info.value.errors) == 2


@pytest.mark.parametrize(
    ("toml", "expected_substrings"),
    [
        pytest.param("", [PROJECT_NOT_FOUND_MESSAGE.format(project_name="missing")], id="no table"),
        pytest.param(
            '[projects.other]\npath = "/tmp"\n',
            [PROJECT_NOT_FOUND_MESSAGE.format(project_name="missing")],
            id="other project",
        ),
        pytest.param("[projects.missing]\ndepth = 1\n", ["missing", "path"], id="no path"),
        pytest.param(
            '[projects.missing]\npath = "/tmp"\ntype = "bogus"\n',
            ["missing", "bogus", "jd", "folder"],
            id="bad type",
        ),
        pytest.param(
            '[projects.missing]\npath = "/tmp"\ndepth = 0\n',
            ["missing", "depth", "1 or more"],
            id="depth below one",
        ),
    ],
)
def test_project_errors(tmp_path: Path, toml: str, expected_substrings: list[str]) -> None:
    """Verify a missing or invalid project section raises a ConfigError."""
    user_file = tmp_path / "user.toml"
    user_file.write_text(toml)

    with pytest.raises(ConfigError) as exc_info:
        load_config(
            config_paths=(DEFAULT_CONFIG_PATH, user_file), environ={}, project_name="missing"
        )

    message = str(exc_info.value)
    for substring in expected_substrings:
        assert substring in message


@pytest.mark.parametrize(
    ("toml_value", "shown_value"),
    [
        pytest.param("-1", "-1", id="negative"),
        pytest.param("true", "True", id="boolean"),
        pytest.param('"5"', "'5'", id="string"),
    ],
)
def test_undo_history_runs_rejects_invalid_values(
    tmp_path: Path, toml_value: str, shown_value: str
) -> None:
    """Verify a negative, boolean, or string run count is a config error naming the value."""
    user_file = tmp_path / "user.toml"
    user_file.write_text(f"undo_history_runs = {toml_value}\n")

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_paths=(DEFAULT_CONFIG_PATH, user_file), environ={})

    assert "undo_history_runs" in str(exc_info.value)
    assert shown_value in str(exc_info.value)


def test_undo_history_runs_reads_environment_digits() -> None:
    """Verify NEATFILE_UNDO_HISTORY_RUNS accepts a whole number."""
    config = load_config(
        config_paths=(DEFAULT_CONFIG_PATH,), environ={"NEATFILE_UNDO_HISTORY_RUNS": "10"}
    )

    assert config.undo_history_runs == 10


def test_undo_history_runs_is_global_only(tmp_path: Path) -> None:
    """Verify the journal size is rejected in a project table but loads at the top level."""
    user_file = tmp_path / "user.toml"
    user_file.write_text('[projects.mine]\npath = "/tmp"\nundo_history_runs = 5\n')

    with pytest.raises(ConfigError) as exc_info:
        load_config(config_paths=(DEFAULT_CONFIG_PATH, user_file), environ={}, project_name="mine")

    assert "mine" in str(exc_info.value)
    assert "undo_history_runs" in str(exc_info.value)
    config = load_config(config_paths=(DEFAULT_CONFIG_PATH, user_file), environ={})
    assert config.undo_history_runs == 50
