"""Tests for the sort command."""

import cappa
import pytest

from neatfile.cli import NeatFile, config_subcommand


def test_sort_fail_no_project(tmp_path, create_file, clean_stdout, mocker, debug):
    """Verify sort command fails when no project is configured."""
    # Given: A test file exists in the source directory
    file = create_file("this is a foo file.txt")

    # When: Running sort command without specifying a project
    args = ["sort", str(file), "-v"]
    with pytest.raises(cappa.Exit) as e:
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Command fails with error and file remains in original location
    output = clean_stdout()
    assert "project is not specified" in output
    assert e.value.code == 1
    assert file.exists()


def test_sort_command_match(tmp_path, create_file, clean_stdout, mocker, debug):
    """Verify sorting files into project folder based on name matching."""
    # Given: Mock questionary select to return first option
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = 0

    # Given: A test file exists
    file = create_file("this is a foo file.txt")

    # When: Running sort command
    args = ["sort", str(file), "--project", "mock_jd_project", "-v"]
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: File is moved to matching folder
    output = clean_stdout()
    assert "this is a foo file.txt -> 10-19 foo/this is a foo file.txt" in output
    assert not file.exists()
    assert (tmp_path / "project" / "10-19 foo" / "this is a foo file.txt").exists()


def test_sort_command_jd_number(tmp_path, create_file, clean_stdout, mocker, debug):
    """Verify sorting files into project folder based on Johnny Decimal number."""
    # Given: A test file exists
    file = create_file("this is a foo file.txt")

    # When: Running sort command with JD number term
    args = ["sort", str(file), "--project", "mock_jd_project", "--term", "11.03", "-v"]
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: File is moved to folder matching JD number
    output = clean_stdout()
    debug(output)

    assert "this is a foo file.txt -> 10-19 foo/11 bar/11.03 koala/this is a foo file.txt" in output
    assert not file.exists()
    assert (
        tmp_path / "project" / "10-19 foo" / "11 bar" / "11.03 koala" / "this is a foo file.txt"
    ).exists()


def test_sort_dont_match_jd_number_in_filename(tmp_path, create_file, clean_stdout, mocker, debug):
    """Verify JD numbers in filenames are not used for folder matching."""
    # Given: Mock questionary select to return first option
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = 0

    # Given: A file exists with a JD number in its name
    file = create_file("12.03 this is a foo file.txt")

    # When: Running sort command without explicit term
    args = ["sort", str(file), "--project", "mock_jd_project", "-vv"]
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: File is moved to matching folder
    output = clean_stdout()
    # debug(output)

    assert "12.03 this is a foo file.txt -> 10-19 foo/12.03 this is a foo file.txt" in output
    assert not file.exists()
    assert (tmp_path / "project" / "10-19 foo" / "12.03 this is a foo file.txt").exists()


def test_sort_no_match(tmp_path, create_file, clean_stdout, mocker, debug):
    """Verify handling when no matching folders are found."""
    # Given: A test file exists
    file = create_file("no matches.txt")

    # When: Running sort command
    args = ["sort", str(file), "--project", "mock_jd_project", "-vv"]
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: Error is shown and file remains in place
    output = clean_stdout()
    assert "No matching directories found for no matches.txt" in output
    assert file.exists()


def test_sort_command_match_term(tmp_path, create_file, clean_stdout, mocker, debug):
    """Verify sorting files into project folder based on user-provided term."""
    # Given: Mock questionary select to return first option
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = 0

    # Given: A test file exists
    file = create_file("no matches.txt")

    # When: Running sort command with custom term
    args = ["sort", str(file), "--project", "mock_jd_project", "-v", "--term", "koala"]
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: File is moved to folder matching term
    output = clean_stdout()
    assert "Found 2 possible folders" in output
    assert "no matches.txt -> 10-19 foo/11 bar/11.03 koala/no matches.txt" in output.replace(
        "\n", " "
    )
    assert not file.exists()
    assert (
        tmp_path / "project" / "10-19 foo" / "11 bar" / "11.03 koala" / "no matches.txt"
    ).exists()


def test_sort_command_single_match(tmp_path, create_file, clean_stdout, mocker, debug):
    """Verify sorting files when exactly one matching folder is found."""
    # Given: A test file exists
    file = create_file("wheres_my_fox.txt")

    # When: Running sort command
    args = ["sort", str(file), "--project", "mock_jd_project", "-v"]
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: File is moved to single matching folder
    output = clean_stdout()
    assert "wheres_my_fox.txt -> 20-29_bar/20_foo/20.04 fox/wheres_my_fox.txt" in output.replace(
        "\n", ""
    )
    assert not file.exists()
    assert (
        tmp_path / "project" / "20-29_bar" / "20_foo" / "20.04 fox" / "wheres_my_fox.txt"
    ).exists()


def test_sort_command_single_match_folder(tmp_path, create_file, clean_stdout, mocker, debug):
    """Verify sorting files when exactly one matching folder is found."""
    # Given: A test file exists
    file = create_file("wheres_my_qux.txt")

    # When: Running sort command
    args = ["sort", str(file), "--project", "mock_folder_project", "-v"]
    with pytest.raises(cappa.Exit):
        cappa.invoke(obj=NeatFile, argv=args, deps=[config_subcommand])

    # Then: File is moved to single matching folder
    output = clean_stdout()
    # debug(output)

    assert "wheres_my_qux.txt -> foo/bar/qux/wheres_my_qux.txt" in output
    assert not file.exists()
    assert (tmp_path / "project" / "foo" / "bar" / "qux" / "wheres_my_qux.txt").exists()
