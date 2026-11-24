"""Tests for the Project model."""

from io import StringIO
from pathlib import Path

from rich.console import Console

from neatfile.constants import NEATFILE_IGNORE_NAME, ProjectType
from neatfile.models.project import IGNORED_FOLDER_LABEL, Project


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


def test_tree_prints_bracketed_folder_names_literally(tmp_path: Path) -> None:
    """Verify folder names that look like markup appear unchanged in the tree."""
    (tmp_path / "[old] invoices").mkdir()

    assert "[old] invoices" in _render_tree(_make_project(tmp_path))


def test_tree_labels_ignored_folders_and_keeps_their_children(tmp_path: Path) -> None:
    """Verify an ignored folder is labeled while its matchable subfolders still show."""
    (tmp_path / "archive" / "taxes").mkdir(parents=True)
    (tmp_path / "archive" / NEATFILE_IGNORE_NAME).touch()

    output = _render_tree(_make_project(tmp_path))

    assert f"archive {IGNORED_FOLDER_LABEL}" in output
    assert "taxes" in output


def test_tree_stops_at_symlink_loops(tmp_path: Path) -> None:
    """Verify a symbolic link back up the tree does not recurse forever."""
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "loop").symlink_to(tmp_path)

    output = _render_tree(_make_project(tmp_path, depth=2))

    assert "loop" in output
