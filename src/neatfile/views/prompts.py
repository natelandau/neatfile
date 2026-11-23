"""Gather user input from the command line."""

from pathlib import Path

import cappa
from nclutils import pp
from rich.markup import escape

from neatfile.models import File, MatchResult

FOLDER_SELECTION_NO_INPUT_MESSAGE = "Cannot choose a folder for '{file_name}' because stdin has no input. Run neatfile in an interactive terminal to choose one."

STYLE = [
    ("qmark", ""),
    ("question", "bold"),
    ("separator", "fg:#808080"),
    ("answer", "fg:#FF9D00"),
    ("instruction", "fg:#808080"),
    ("highlighted", "bold underline"),
    ("text", ""),
    ("pointer", "bold"),
]


def select_folder(matching_dirs: list[MatchResult], file: File, *, project_path: Path) -> Path:
    """Ask the user which of several matching folders should receive a file.

    Args:
        matching_dirs (list[MatchResult]): Possible folders.
        file (File): File object.
        project_path (Path): Path to the root of the project, used to shorten folder paths.

    Returns:
        Path: Path to the selected folder

    Raises:
        cappa.Exit: If the user chooses to abort, or if stdin has no input for the prompt.
    """
    import questionary  # noqa: PLC0415

    choices: list[dict[str, str] | questionary.Separator] = [questionary.Separator()]

    # Calculate the maximum length of the folder path to visually align the output
    max_length = max(len(str(obj.folder.path.relative_to(project_path))) for obj in matching_dirs)

    for i, obj in enumerate(matching_dirs):
        matching_terms = ", ".join(set(obj.matched_terms))
        folder_path = str(obj.folder.path.relative_to(project_path))

        if pp.get_default().verbosity >= 1:
            display_name = (
                f"{folder_path:{max_length}} [score: {obj.score:.2f}] [matching: {matching_terms}]"
            )
        else:
            display_name = f"{folder_path:{max_length}}"

        choices.append(
            {
                "name": display_name,
                "value": str(i),
            }
        )

    choices.extend(
        [
            questionary.Separator(),
            {"name": "Skip moving this file", "value": "skip"},
            {"name": "Abort", "value": "abort"},
        ]
    )

    noun = "folder" if len(matching_dirs) == 1 else "folders"
    pp.info(
        f"Found {len(matching_dirs)} possible {noun} for '[cyan bold]{escape(file.name)}[/]'",
        markup=True,
    )
    try:
        result = questionary.select(
            "Select a folder", choices=choices, style=questionary.Style(STYLE)
        ).ask()
    except EOFError:
        pp.error(FOLDER_SELECTION_NO_INPUT_MESSAGE.format(file_name=file.name))
        raise cappa.Exit(code=1) from None

    if result is None or result == "abort":
        pp.info("Aborting...")
        raise cappa.Exit()

    if result == "skip":
        pp.info("Skipping...")
        return file.parent

    return matching_dirs[int(result)].folder.path
