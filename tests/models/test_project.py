"""Tests for the Project model."""

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from neatfile.constants import NEATFILE_IGNORE_NAME, ProjectType
from neatfile.models.project import IGNORED_FOLDER_LABEL, Project


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Return an empty project folder, separate from the files other fixtures write to `tmp_path`."""
    root = tmp_path / "scanned_project"
    root.mkdir()
    return root


def _make_project(
    root: Path, *, depth: int = 3, project_type: ProjectType = ProjectType.FOLDER
) -> Project:
    return Project(
        name="test", path=root, depth=depth, project_type=project_type, strip_stopwords=True
    )


def _render_tree(project: Project) -> str:
    output = StringIO()
    Console(file=output, width=200, color_system=None).print(project.tree())
    return output.getvalue()


def test_tree_prints_bracketed_folder_names_literally(project_root: Path) -> None:
    """Verify folder names that look like markup appear unchanged in the tree."""
    (project_root / "[old] invoices").mkdir()

    assert "[old] invoices" in _render_tree(_make_project(project_root))


def test_tree_labels_ignored_folders_and_keeps_their_children(project_root: Path) -> None:
    """Verify an ignored folder is labeled while its matchable subfolders still show."""
    (project_root / "archive" / "taxes").mkdir(parents=True)
    (project_root / "archive" / NEATFILE_IGNORE_NAME).touch()

    output = _render_tree(_make_project(project_root))

    assert f"archive {IGNORED_FOLDER_LABEL}" in output
    assert "taxes" in output


def test_tree_stops_at_symlink_loops(project_root: Path) -> None:
    """Verify a symbolic link back up the tree does not recurse forever."""
    (project_root / "a").mkdir()
    (project_root / "a" / "loop").symlink_to(project_root)

    output = _render_tree(_make_project(project_root, depth=2))

    assert "loop" in output


def test_matchable_folders_skip_ignored_folders_but_keep_their_children(project_root: Path) -> None:
    """Verify `.neatfileignore` removes only its own folder from matching."""
    (project_root / "10-19 Finance" / "11 Taxes").mkdir(parents=True)
    (project_root / "10-19 Finance" / NEATFILE_IGNORE_NAME).touch()

    project = _make_project(project_root, project_type=ProjectType.JD)

    assert [folder.number for folder in project.matchable_folders] == ["11"]


@pytest.mark.parametrize(
    ("project_type", "directories", "expected"),
    [
        pytest.param(
            ProjectType.JD,
            [
                "10-19 Finance/11 Taxes/11.01 Returns",
                "10-19 Finance/11.02 Misplaced",
                "10-19 Finance/Receipts",
                "12 Loose category",
            ],
            ["10-19 Finance", "10-19 Finance/11 Taxes", "10-19 Finance/11 Taxes/11.01 Returns"],
            id="jd-expects-area-then-category-then-subcategory",
        ),
        pytest.param(
            ProjectType.FOLDER,
            [".git/objects", "finance/.cache", "finance/taxes"],
            ["finance", "finance/taxes"],
            id="folder-skips-hidden-folders",
        ),
    ],
)
def test_usable_folders_follow_project_type_rules(
    project_root: Path, project_type: ProjectType, directories: list[str], expected: list[str]
) -> None:
    """Verify which folders each project type indexes."""
    for directory in directories:
        (project_root / directory).mkdir(parents=True)
    (project_root / "10-19 notes.txt").touch()

    project = _make_project(project_root, project_type=project_type)

    assert [
        folder.path.relative_to(project_root).as_posix() for folder in project.usable_folders
    ] == expected


def test_usable_folders_skip_unreadable_folders(project_root: Path) -> None:
    """Verify a folder that cannot be listed hides only its own subfolders."""
    (project_root / "locked" / "secret").mkdir(parents=True)
    (project_root / "open").mkdir()
    (project_root / "locked").chmod(0o000)
    try:
        folders = _make_project(project_root).usable_folders
    finally:
        (project_root / "locked").chmod(0o755)

    assert [folder.path.name for folder in folders] == ["locked", "open"]
