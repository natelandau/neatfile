"""Project models."""

import re
from collections.abc import Generator
from pathlib import Path

import cappa
from nclutils import pp
from rich.tree import Tree

from neatfile.constants import NEATFILE_NAME, FolderType, ProjectType

from .folder import Folder


class Project:
    """Manage a project directory's configuration, path, and folder structure.

    Provides functionality to work with both Johnny Decimal and regular folder structures, handling configuration loading and folder organization.

    Args:
        name (str): The name of the project
        path (str | Path): Path to the project directory
        depth (int, optional): Maximum folder depth to traverse. Defaults to 0.
        project_type (ProjectType, optional): Type of project structure to use. Defaults to ProjectType.JD.
    """

    def __init__(
        self,
        name: str,
        path: str | Path,
        depth: int = 0,
        project_type: ProjectType = ProjectType.JD,
    ) -> None:
        """Initialize a new project instance.

        Args:
            name (str): The name of the project
            path (str | Path): Path to the project directory
            depth (int, optional): Maximum folder depth to traverse. Defaults to 0.
            project_type (ProjectType, optional): Type of project structure to use. Defaults to ProjectType.JD.
        """
        self.name = name
        self.path = self._validate_project_path(Path(path).expanduser().resolve())
        self.depth = depth
        self.project_type = project_type

        # Identify usable folders within the project
        self.usable_folders = (
            self._find_jd_folders()
            if self.project_type == ProjectType.JD
            else self._find_non_jd_folders()
        )

    def __repr__(self) -> str:
        """String representation of the project.

        Returns:
            str: String representation of the project.
        """
        return f"PROJECT: {self.name}: {self.path} {len(self.usable_folders)} usable folders (type: {self.project_type})"

    def _find_non_jd_folders(self) -> list[Folder]:
        """Traverse the project directory and identify all non-Johnny Decimal folders.

        Recursively search through the project directory up to the configured depth, identifying and categorizing all folders that don't follow the Johnny Decimal naming convention. Exclude hidden folders (those starting with '.').

        Returns:
            list[Folder]: A sorted list of Folder objects representing non-JD folders, ordered by path.
        """

        def traverse_directory(directory: Path, depth: int) -> Generator[Folder, None, None]:
            for item in directory.iterdir():
                if item.is_dir() and item.name[0] != ".":  # Exclude hidden folders
                    yield Folder(path=item, folder_type=FolderType.OTHER)
                    if depth < self.depth:
                        yield from traverse_directory(item, depth + 1)

        non_jd_folders = list(traverse_directory(self.path, 0))

        pp.trace(f"{len(non_jd_folders)} non-JD folders indexed in project: {self.name}")
        return sorted(non_jd_folders, key=lambda folder: folder.path)

    def _find_jd_folders(self) -> list[Folder]:
        """Identify and categorize Johnny Decimal folders within the project directory.

        Recursively search through the project directory to find folders that follow the Johnny Decimal naming convention. Categorize each folder as an area (XX-XX), category (XX), or subcategory (XX.XX) based on its name pattern. Include folders marked with a `.neatfile` even if they don't match the naming pattern.

        Returns:
            list[Folder]: A sorted list of Folder objects representing JD folders, ordered by path.
        """

        def create_folders(
            directory: Path,
            folder_type: FolderType,
            parent_area: Path | None = None,
            parent_category: Path | None = None,
        ) -> list[Folder]:
            return [
                Folder(
                    path=item,
                    folder_type=folder_type,
                    area=parent_area or item,
                    category=parent_category or item,
                )
                for item in directory.iterdir()
                if item.is_dir() and re.match(folder_type.pattern, item.name)
            ]

        areas = create_folders(self.path, FolderType.AREA)
        categories = [
            folder
            for area in areas
            for folder in create_folders(area.path, FolderType.CATEGORY, parent_area=area.path)
        ]
        subcategories = [
            folder
            for category in categories
            for folder in create_folders(
                category.path,
                FolderType.SUBCATEGORY,
                parent_area=category.area,
                parent_category=category.path,
            )
        ]

        # Filtering to avoid duplicates and include folders with .neatfile
        all_folders: list[Folder] = []
        for folder_list in (areas, categories, subcategories):
            for folder in folder_list:
                if (
                    not any(existing.path == folder.path for existing in all_folders)
                    or Path(folder.path / NEATFILE_NAME).exists()
                ):
                    # pp.trace(f"PROJECT: Add '{folder.path.name}'")  # noqa: ERA001
                    all_folders.append(folder)

        pp.trace(f"{len(all_folders)} folders indexed in project: {self.name}")
        return sorted(all_folders, key=lambda folder: folder.path)

    @staticmethod
    def _validate_project_path(path: str | Path) -> Path:
        """Validate and convert a path string or Path object to a resolved Path.

        Ensure the path exists and is an accessible directory. Convert string paths to resolved Path objects.

        Args:
            path (str | Path): Path to validate, either as string or Path object

        Returns:
            Path: Resolved and validated Path object

        Raises:
            cappa.Exit: When path does not exist or is not a directory
        """
        path_to_validate = Path(path).expanduser().resolve() if isinstance(path, str) else path

        if not path_to_validate.exists():
            pp.error(f"Specified project path does not exist: {path}")
            raise cappa.Exit(code=1)

        if not path_to_validate.is_dir():
            pp.error(f"Specified project path is not a directory: {path}")
            raise cappa.Exit(code=1)

        return path_to_validate

    def _walk_directory(self, directory: Path, tree: Tree) -> None:
        """Build a hierarchical tree structure by recursively traversing directories.

        Sort directories before files and exclude hidden files. For Johnny Decimal projects, only include folders matching JD patterns.

        Args:
            directory (Path): Directory path to traverse and build tree from
            tree (Tree): Tree object to populate with directory structure
        """
        # Sort dirs first then by filename
        paths = sorted(
            Path(directory).iterdir(),
            key=lambda path: (path.is_file(), path.name.lower()),
        )

        for path in paths:
            if path.name.startswith(".") or not path.is_dir():
                continue

            if self.project_type == ProjectType.JD and not any(
                re.match(ft.pattern, path.name)
                for ft in (FolderType.AREA, FolderType.CATEGORY, FolderType.SUBCATEGORY)
            ):
                continue

            branch = tree.add(f"{path.name}")
            self._walk_directory(path, branch)

    def tree(self) -> Tree:
        """Generate a visual tree representation of the project directory structure.

        Create a tree showing the hierarchical folder structure, with the project root as the base.

        Returns:
            Tree: Visual tree representation with folders and formatting
        """
        tree = Tree(
            f":open_file_folder: [link file://{self.path}]{self.path}",
            guide_style="dim",
        )
        self._walk_directory(Path(self.path), tree)
        return tree
