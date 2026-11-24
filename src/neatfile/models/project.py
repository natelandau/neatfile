"""Project models."""

from __future__ import annotations

import functools
import re
from collections import defaultdict
from typing import TYPE_CHECKING

import cappa
from nclutils import pp
from rich.style import Style
from rich.text import Text
from rich.tree import Tree

from neatfile.constants import FolderType, ProjectType

from .folder import Folder

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from neatfile.config import ProjectConfig

IGNORED_FOLDER_LABEL = "(ignored)"
OPEN_FOLDER_ICON = "\N{OPEN FILE FOLDER}"

# Johnny Decimal folder type expected at each nesting level below the project root
JD_LEVELS = (FolderType.AREA, FolderType.CATEGORY, FolderType.SUBCATEGORY)


def _is_usable_name(name: str, folder_type: FolderType) -> bool:
    """Report whether a folder name fits its expected type, so the scan can reject it before touching the disk.

    Args:
        name (str): Folder name to test.
        folder_type (FolderType): Type the folder must have at its level.

    Returns:
        bool: True when a JD name carries its type's prefix, or a non-JD name is not hidden.
    """
    if folder_type == FolderType.OTHER:
        return not name.startswith(".")
    return re.match(pattern=folder_type.pattern, string=name) is not None


def _list_children(directory: Path) -> list[Path] | None:
    """List a folder's entries, warning instead of crashing when the folder cannot be read.

    An unreadable folder inside a project should hide only that branch, not stop the whole run.

    Args:
        directory (Path): Folder to list.

    Returns:
        list[Path] | None: The folder's entries, or None when the folder cannot be read.
    """
    try:
        return list(directory.iterdir())
    except OSError as error:
        pp.warning(f"Skipping {directory}: expected a readable folder ({error})")
        return None


class Project:
    """Manage a project directory's configuration, path, and folder structure.

    Provides functionality to work with both Johnny Decimal and regular folder structures, handling configuration loading and folder organization.

    Args:
        name (str): The name of the project
        path (Path): Path to the project directory
        depth (int): Maximum folder depth to traverse.
        project_type (ProjectType): Type of project structure to use.
        strip_stopwords (bool): Remove stopwords from the terms taken from folder names.
    """

    def __init__(
        self,
        name: str,
        path: Path,
        *,
        depth: int,
        project_type: ProjectType,
        strip_stopwords: bool,
    ) -> None:
        self.name = name
        self.path = self._validate_project_path(path.expanduser().resolve())
        self.depth = depth
        self.project_type = project_type
        self.strip_stopwords = strip_stopwords

    @classmethod
    def from_config(cls, project: ProjectConfig, *, strip_stopwords: bool) -> Project:
        """Build the project selected in the configuration.

        The folder tree is scanned on first access to `usable_folders`, so commands that never read it pay nothing.

        Args:
            project (ProjectConfig): The validated project settings.
            strip_stopwords (bool): Remove stopwords from the terms taken from folder names.

        Returns:
            Project: The project for the selected configuration.
        """
        return cls(
            name=project.name,
            path=project.path,
            depth=project.depth,
            project_type=project.project_type,
            strip_stopwords=strip_stopwords,
        )

    def __repr__(self) -> str:
        """String representation of the project.

        Returns:
            str: String representation of the project.
        """
        return f"PROJECT: {self.name}: {self.path} (type: {self.project_type})"

    @functools.cached_property
    def usable_folders(self) -> list[Folder]:
        """Index the folders that files can be sorted into.

        For Johnny Decimal projects, keep areas (XX-XX) at the root, categories (XX) inside areas, and subcategories (XX.XX) inside categories. For other projects, keep every non-hidden folder down to the configured depth.

        Returns:
            list[Folder]: The usable folders, ordered by path.
        """
        folders: list[Folder] = sorted(
            (
                Folder(path=path, folder_type=folder_type, strip_stopwords=self.strip_stopwords)
                for path, folder_type in self._scan_folders(directory=self.path, level=0)
            ),
            key=lambda folder: folder.path,
        )
        pp.trace(f"{len(folders)} folders indexed in project: {self.name}")
        return folders

    @functools.cached_property
    def matchable_folders(self) -> tuple[Folder, ...]:
        """List the folders a file can be matched to, leaving out folders marked with `.neatfileignore`.

        Subfolders of an ignored folder stay matchable.

        Returns:
            tuple[Folder, ...]: The usable folders that are not ignored, ordered by path.
        """
        return tuple(folder for folder in self.usable_folders if not folder.is_ignored)

    def _scan_folders(self, directory: Path, level: int) -> Iterator[tuple[Path, FolderType]]:
        """Yield each usable folder below `directory` with its type, recursing to the project's maximum level.

        Args:
            directory (Path): Directory whose children to scan.
            level (int): Nesting level of the children, where 0 is the project root's children.

        Yields:
            tuple[Path, FolderType]: A usable folder and its type.
        """
        folder_type: FolderType = (
            JD_LEVELS[level] if self.project_type == ProjectType.JD else FolderType.OTHER
        )
        max_level: int = len(JD_LEVELS) - 1 if self.project_type == ProjectType.JD else self.depth

        children: list[Path] | None = _list_children(directory)
        if children is None:
            return

        for item in children:
            # The name test comes first so files and rejected names skip the stat in is_dir
            if _is_usable_name(name=item.name, folder_type=folder_type) and item.is_dir():
                yield item, folder_type
                if level < max_level:
                    yield from self._scan_folders(directory=item, level=level + 1)

    @staticmethod
    def _validate_project_path(path: Path) -> Path:
        """Stop the run unless the project path is an existing directory.

        Args:
            path (Path): Resolved project path.

        Returns:
            Path: The same path, once validated.

        Raises:
            cappa.Exit: When path does not exist or is not a directory
        """
        if not path.exists():
            pp.error(f"Specified project path does not exist: {path}")
            raise cappa.Exit(code=1)

        if not path.is_dir():
            pp.error(f"Specified project path is not a directory: {path}")
            raise cappa.Exit(code=1)

        return path

    def tree(self) -> Tree:
        """Draw the folders that files can be sorted into, so users can preview where `sort` may file things.

        Folders marked with `.neatfileignore` are shown and labeled, because their subfolders can still match.

        Returns:
            Tree: The usable folders nested under the project root, sorted by name.
        """
        children_by_parent: defaultdict[Path, list[Folder]] = defaultdict(list)
        for folder in self.usable_folders:
            children_by_parent[folder.path.parent].append(folder)

        # Text instead of markup strings, so brackets in folder names print literally
        root = Tree(
            Text.assemble(f"{OPEN_FOLDER_ICON} ", (str(self.path), Style(link=self.path.as_uri()))),
            guide_style="dim",
        )
        pending: list[tuple[Path, Tree]] = [(self.path, root)]
        while pending:
            directory, branch = pending.pop()
            for folder in sorted(
                children_by_parent[directory], key=lambda child: child.path.name.lower()
            ):
                label = Text(folder.path.name)
                if folder.is_ignored:
                    label.append(f" {IGNORED_FOLDER_LABEL}", style="dim")
                pending.append((folder.path, branch.add(label)))
        return root
