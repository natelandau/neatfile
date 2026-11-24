"""The neatfile cli."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path  # noqa: TC003
from typing import Annotated

import cappa
from cappa import Dep
from cappa.base import command, invoke
from nclutils import pp
from rich.traceback import install

from neatfile import constants
from neatfile.commands import Mode, execute_command, execute_undo
from neatfile.config import Config, ConfigError, RunOptions, load_config
from neatfile.constants import PrintLevel, Separator, TransformCase
from neatfile.models import Project

NO_PROJECT_MESSAGE = (
    "No project selected. Pass `--project` with a project name from the configuration file."
)
PROJECT_PATH_NOT_FOLDER_MESSAGE = "Project path `{path}` is not an existing folder. Set `path` in the project's configuration to a folder."
TREE_NO_PROJECT_MESSAGE = "You must specify a project name with the `--project` flag."
NO_DATE_FORMAT_MESSAGE = "`--date-only` needs a date format. Set `date_format` in the configuration file or pass `--date-format`."

_CLEAN_DESCRIPTION = """\
Perform the following transformations on a filename:

-   Remove special characters
-   Trim multiple separators (`word----word` becomes `word-word`)
-   Normalize to `lowercase`, `uppercase`, `Sentence case`, or `Title Case`
-   Normalize all word separators to a common one (`_`, `-`, ` `, `.`)
-   Enforce lowercase file extensions
-   Remove filler words such as "the", "of", and "and"
-   Split `camelCase` words into separate words (`camel Case`)
-   Add a date to the filename in your preferred format (removing dates already present in the filename)
"""

_PRINT_LEVEL_VERBOSITY: dict[PrintLevel, int] = {PrintLevel.DEBUG: 1, PrintLevel.TRACE: 2}


def configure_output(neatfile: NeatFile) -> None:
    """Set the output verbosity from the `-v` flags before any command prints.

    Args:
        neatfile (NeatFile): The parsed CLI arguments.
    """
    pp.configure(verbosity=_PRINT_LEVEL_VERBOSITY.get(neatfile.verbosity, 0))


def build_config(neatfile: NeatFile) -> Config:
    """Load the settings for this run, with the CLI flags that map to settings applied last.

    Args:
        neatfile (NeatFile): The parsed CLI arguments.

    Returns:
        Config: The validated settings.

    Raises:
        cappa.Exit: If any setting is invalid or the selected project is not found.
    """
    command = neatfile.command
    flag_values: dict[str, object] = {}
    if isinstance(command, _FileArguments):
        flag_values["overwrite_existing"] = command.overwrite or None
    if isinstance(command, _CleanArguments):
        flag_values |= {
            "date_format": command.date_format,
            "separator": command.separator,
            "transform_case": command.transform_case,
        }
    if isinstance(command, ProcessCommand | SortCommand):
        flag_values["user_terms"] = command.user_terms or None
    cli_overrides = {key: value for key, value in flag_values.items() if value is not None}

    try:
        return load_config(project_name=neatfile.project_name or None, cli_overrides=cli_overrides)
    except ConfigError as e:
        for error in e.errors:
            pp.error(error)
        raise cappa.Exit(code=1) from e


def build_run_options(neatfile: NeatFile) -> RunOptions:
    """Collect the CLI-only values for this run that are not settings.

    Args:
        neatfile (NeatFile): The parsed CLI arguments.

    Returns:
        RunOptions: The values from the command line, with defaults for flags the command lacks.
    """
    command = neatfile.command
    options = RunOptions(dry_run=neatfile.dryrun)
    if isinstance(command, _FileArguments):
        options = replace(
            options,
            files=tuple(command.files),
            force=command.force,
            confirm_changes=command.confirm_changes,
            file_search_depth=options.file_search_depth
            if command.file_search_depth is None
            else command.file_search_depth,
        )
    if isinstance(command, _CleanArguments):
        options = replace(options, date=command.date, date_only=command.date_only)
    return options


def _require_project(config: Config, message: str) -> Project:
    """Build the selected project, or stop the run when no project is selected or its folder is missing.

    Args:
        config (Config): The settings for this run.
        message (str): The error to show when no project is selected.

    Returns:
        Project: The selected project. Its folders are scanned on first use.

    Raises:
        cappa.Exit: If no project is selected, or its path is not an existing folder.
    """
    if config.project is None:
        pp.error(message)
        raise cappa.Exit(code=1)
    project = Project.from_config(project=config.project, strip_stopwords=config.strip_stopwords)
    if not project.path.is_dir():
        pp.error(PROJECT_PATH_NOT_FOLDER_MESSAGE.format(path=project.path))
        raise cappa.Exit(code=1)
    return project


def _require_date_format(config: Config, options: RunOptions) -> None:
    """Stop the run when `--date-only` is given but no date format is set.

    Args:
        config (Config): The settings for this run.
        options (RunOptions): The CLI-only values for this run.

    Raises:
        cappa.Exit: If `--date-only` is given and `date_format` is empty.
    """
    if options.date_only and not config.date_format:
        pp.error(NO_DATE_FORMAT_MESSAGE)
        raise cappa.Exit(code=1)


@command(
    name="neatfile",
    description="""

**Filename cleaning and normalization**

-   Remove special characters
-   Trim multiple separators (`word----word` becomes `word-word`)
-   Normalize to `lowercase`, `uppercase`, `Sentence case`, or `Title Case`
-   Normalize all files to a common word separator (`_`, `-`, ` `, `.`)
-   Enforce lowercase file extensions
-   Remove filler words such as "the", "of", and "and"
-   Split `camelCase` words into separate words (`camel Case`)

**Date parsing**

-   Parse dates in filenames in many different formats
-   Fall back to file creation date if no date is found in the filename
-   Normalize dates in filenames to a preferred format
-   Add the date to the beginning or the end of the filename or remove it entirely

**File organization**

-   Set up projects with directory trees in the config file
-   Match terms in filenames to folder names and move files into the appropriate folders
-   Use vector matching to find similar terms
-   Respect the [Johnny Decimal](https://johnnydecimal.com) system if you use it
-   Optionally, add `.neatfile` files to directories containing a list of words that will match files
-   Revert the last run of `clean`, `sort`, or `process` with `neatfile undo`

**Configuration**

To set your preferences and create projects, you'll need to create a configuration file. Neatfile will look for a file at `~/.config/neatfile/config.toml` or your `$XDG_CONFIG_HOME/neatfile/config.toml` if set.
    """,
)
class NeatFile:
    """A CLI tool that automatically normalizes and organizes your files based on customizable rules."""

    command: cappa.Subcommands[
        CleanCommand | ConfigCommand | SortCommand | ProcessCommand | TreeCommand | UndoCommand
    ]

    project_name: Annotated[
        str,
        cappa.Arg(
            long="project",
            short="p",
            help="Specify a project from the configuration file.",
            propagate=True,
        ),
    ] = ""
    verbosity: Annotated[
        PrintLevel,
        cappa.Arg(
            short=True,
            count=True,
            help="Verbosity level (`-v` or `-vv`)",
            choices=[],
            show_default=False,
            propagate=True,
        ),
    ] = PrintLevel.INFO
    dryrun: Annotated[
        bool,
        cappa.Arg(
            long="dry-run",
            short="-n",
            help="Preview changes without modifying files",
            show_default=False,
            propagate=True,
        ),
    ] = False


_USER_TERMS_ARG = cappa.Arg(
    long="term",
    short="t",
    help="Term used to match files to folders. Add multiple terms with additional `--term` flags",
    show_default=False,
)


@dataclass
class _FileArguments:
    """Hold the arguments shared by every command that changes files."""

    files: Annotated[
        list[Path],
        cappa.Arg(
            help="The files to clean. If a directory is provided, all files in the directory will be cleaned, not the directory itself.",
            required=True,
        ),
    ]

    confirm_changes: Annotated[
        bool,
        cappa.Arg(
            long="confirm",
            short="c",
            help="Confirm changes before applying them",
            show_default=False,
        ),
    ] = False
    file_search_depth: Annotated[
        int | None,
        cappa.Arg(
            long="depth",
            help="Depth to search for files if using a wildcard",
            show_default=False,
        ),
    ] = None
    force: Annotated[
        bool,
        cappa.Arg(
            help="Do not prompt for confirmation before making changes",
            show_default=False,
        ),
    ] = False
    overwrite: Annotated[
        bool,
        cappa.Arg(
            help="Overwrite existing files rather than creating a backup",
            show_default=False,
        ),
    ] = False


@dataclass
class _CleanArguments(_FileArguments):
    """Hold the arguments shared by the commands that rename files."""

    date: Annotated[
        str | None,
        cappa.Arg(
            long="date",
            short="d",
            help="Specify a date to use for the filename (ignores dates found in filename)",
            show_default=False,
        ),
    ] = None
    date_format: Annotated[
        str | None,
        cappa.Arg(
            long="date-format",
            short="f",
            help="Specify a date format to use for the filename (e.g. `%Y-%m-%d`)",
            show_default=False,
        ),
    ] = None
    date_only: Annotated[
        bool,
        cappa.Arg(
            help="Add a date to the filename but make no other changes",
            show_default=False,
        ),
    ] = False
    transform_case: Annotated[
        str | None,
        cappa.Arg(
            choices=[c.name for c in TransformCase],
            long="case",
            help="Transform the case of the filename",
            show_default=True,
            parse=lambda x: x.upper(),
        ),
    ] = None
    separator: Annotated[
        str | None,
        cappa.Arg(
            choices=[c.name for c in Separator],
            long=["separator", "sep"],
            help="Separator to use for the filename.",
            show_default=False,
            parse=lambda x: x.upper(),
        ),
    ] = None


@command(
    name="clean",
    description=_CLEAN_DESCRIPTION
    + """
Learn more [in the README](https://github.com/natelandau/neatfile).
""",
)
# A subclass of a dataclass needs its own decorator, or cappa skips the fields it adds
@dataclass
class CleanCommand(_CleanArguments):
    """Clean and normalize filenames."""

    def __call__(
        self,
        config: Annotated[Config, Dep(build_config)],
        options: Annotated[RunOptions, Dep(build_run_options)],
    ) -> None:
        """Clean the names of the given files and apply the changes."""
        _require_date_format(config=config, options=options)
        execute_command(mode=Mode.CLEAN, config=config, options=options, project=None)


@command(name="config")
class ConfigCommand:
    """View and create a user configuration file."""

    create: Annotated[
        bool,
        cappa.Arg(help="Create a user configuration file", show_default=False),
    ] = False

    def __call__(self, options: Annotated[RunOptions, Dep(build_run_options)]) -> None:
        """Show the current configuration, or create the user configuration file with `--create`."""
        user_config = constants.USER_CONFIG_PATH
        if self.create:
            if user_config.exists():
                pp.info(f"User configuration file already exists: {user_config}")
                raise cappa.Exit(code=1)

            if options.dry_run:
                pp.dryrun(f"Would create configuration file: {user_config}")
                raise cappa.Exit(code=0)

            user_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(constants.DEFAULT_CONFIG_PATH, user_config)
            pp.success(f"User config file created: {user_config}")
            raise cappa.Exit(code=0)

        current_config = user_config if user_config.exists() else constants.DEFAULT_CONFIG_PATH

        from rich.markdown import Markdown  # noqa: PLC0415

        pp.header("Current Configuration")
        pp.console().print(Markdown("```toml\n" + current_config.read_text() + "\n```"))

        if not user_config.exists():
            pp.info(
                "Using default configuration.",
                details=[
                    f"No user configuration file found: {user_config}",
                    "To create a user configuration file, run `neatfile config --create`",
                ],
            )
        else:
            pp.info(f"User configuration file found: {user_config}")


@command(
    name="process",
    description=_CLEAN_DESCRIPTION
    + """
Sort files into a project directory:

-   Specify the project with the `--project` flag
-   Match terms in filenames to directory names and move files into the appropriate directory
-   Use vector matching to find similar terms

**Note:** Projects must be defined in the configuration file.

Learn more [in the README](https://github.com/natelandau/neatfile).
""",
)
# A subclass of a dataclass needs its own decorator, or cappa skips the fields it adds
@dataclass
class ProcessCommand(_CleanArguments):
    """Clean and sort files."""

    user_terms: Annotated[tuple[str, ...], _USER_TERMS_ARG] = ()

    def __call__(
        self,
        config: Annotated[Config, Dep(build_config)],
        options: Annotated[RunOptions, Dep(build_run_options)],
    ) -> None:
        """Clean the names of the given files, sort them into the selected project, and apply the changes."""
        _require_date_format(config=config, options=options)
        project = _require_project(config=config, message=NO_PROJECT_MESSAGE)
        execute_command(mode=Mode.PROCESS, config=config, options=options, project=project)


@command(
    name="sort",
    description="""\
Projects must be defined in the configuration file.

-   Specify the project with the `--project` flag
-   Match terms in filenames to directory names and move files into the appropriate directory
-   Use vector matching to find similar terms

Learn more [in the README](https://github.com/natelandau/neatfile/).
""",
)
# A subclass of a dataclass needs its own decorator, or cappa skips the fields it adds
@dataclass
class SortCommand(_FileArguments):
    """Sort files into a project folder."""

    user_terms: Annotated[tuple[str, ...], _USER_TERMS_ARG] = ()

    def __call__(
        self,
        config: Annotated[Config, Dep(build_config)],
        options: Annotated[RunOptions, Dep(build_run_options)],
    ) -> None:
        """Sort the given files into the selected project and apply the changes."""
        project = _require_project(config=config, message=NO_PROJECT_MESSAGE)
        execute_command(mode=Mode.SORT, config=config, options=options, project=project)


@command(name="tree")
class TreeCommand:
    """Print a tree representation of the project folder."""

    def __call__(self, config: Annotated[Config, Dep(build_config)]) -> None:
        """Print the selected project's folder tree."""
        project = _require_project(config=config, message=TREE_NO_PROJECT_MESSAGE)
        pp.console().print(project.tree())


@command(name="undo")
class UndoCommand:
    """Revert the last run of clean, sort, or process."""

    force: Annotated[
        bool,
        cappa.Arg(
            help="Do not prompt for confirmation before restoring files",
            show_default=False,
        ),
    ] = False

    def __call__(self, options: Annotated[RunOptions, Dep(build_run_options)]) -> None:
        """Move the files of the newest run in the undo journal back to their original paths."""
        execute_undo(dry_run=options.dry_run, force=self.force)


def main() -> None:  # pragma: no cover
    """Initialize and execute the command line interface.

    Parse command line arguments, configure settings, and execute the appropriate command. Handle keyboard interrupts gracefully by exiting with a status code of 1.

    Raises:
        cappa.Exit: If a keyboard interrupt occurs.
    """
    install(show_locals=False)

    try:
        invoke(obj=NeatFile, deps=[configure_output], completion=False)
    except KeyboardInterrupt as e:
        pp.info("Exiting...")
        raise cappa.Exit(code=1) from e


if __name__ == "__main__":  # pragma: no cover
    main()
