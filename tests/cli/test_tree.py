"""Tests for the `tree` subcommand."""

import cappa
import pytest

from neatfile.cli import NeatFile, config_subcommand


def test_jd_tree(debug, clean_stdout):
    """Verify tree command displays correct JD project structure."""
    # Given: Arguments for tree command with JD project
    args = ["tree", "--project", "mock_jd_project"]

    # When: Invoking tree command
    cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Output matches expected JD structure
    output = clean_stdout()

    assert (
        """\
├── 10-19 foo
│   ├── 11 bar
│   │   ├── 11.01 foo
│   │   ├── 11.02 bar
│   │   └── 11.03 koala
│   └── 12 baz
│       ├── 12.01 foo
│       ├── 12.02 bar
│       ├── 12.03 koala
│       ├── 12.04 baz
│       └── 12.05 waldo
├── 20-29_bar
│   ├── 20_foo
│   │   ├── 20.01_foo_bar_baz
│   │   ├── 20.02_bar
│   │   ├── 20.03_waldo
│   │   └── 20.04 fox
│   ├── 21_bar
│   └── 22 cat
├── 30-39_baz
└── 40-49 dog"""
        in output
    )
    # Verify non-JD folders are excluded
    assert "some_dir" not in output
    assert (
        """\
└── foo
    └── bar
        ├── bar
        ├── baz
        ├── foo
        └── qux"""
        not in output
    )


def test_folder_tree(debug, clean_stdout):
    """Verify tree command displays correct folder project structure."""
    # Given: Arguments for tree command with folder project
    args = ["tree", "-vv", "--project", "mock_folder_project"]

    # When: Invoking tree command
    cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Output matches expected folder structure
    output = clean_stdout()

    assert (
        """\
├── 10-19 foo
│   ├── 11 bar
│   │   ├── 11.01 foo
│   │   ├── 11.02 bar
│   │   └── 11.03 koala
│   └── 12 baz
│       ├── 12.01 foo
│       ├── 12.02 bar
│       ├── 12.03 koala
│       ├── 12.04 baz
│       └── 12.05 waldo
├── 20-29_bar
│   ├── 20_foo
│   │   ├── 20.01_foo_bar_baz
│   │   ├── 20.02_bar
│   │   ├── 20.03_waldo
│   │   └── 20.04 fox
│   │       └── some_dir
│   ├── 21_bar
│   └── 22 cat
├── 30-39_baz
├── 40-49 dog
└── foo
    └── bar
        ├── bar
        ├── baz
        ├── foo
        └── qux"""
        in output
    )


def test_tree_no_project(debug, clean_stdout):
    """Verify tree command fails when no project specified."""
    # Given: Tree command with no project argument
    args = ["tree"]

    # When: Invoking tree command
    with pytest.raises(cappa.Exit) as e:
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Command fails with appropriate error message
    output = clean_stdout()

    assert e.value.code == 1
    assert "You must specify a project name with the --project flag." in output


def test_tree_name_not_found(debug, clean_stdout):
    """Verify tree command fails when project name not found."""
    # Given: Tree command with non-existent project name
    args = ["tree", "--project", "non_existent_project"]

    # When: Invoking tree command
    with pytest.raises(cappa.Exit) as e:
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Command fails with appropriate error message
    output = clean_stdout()
    # debug(output)

    assert e.value.code == 1
    assert "Project non_existent_project not found in the configuration file." in output
