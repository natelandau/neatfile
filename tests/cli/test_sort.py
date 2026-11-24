"""Tests for the sort command."""

from pathlib import Path

import cappa
import pytest
from cappa.base import invoke

from neatfile import constants
from neatfile.cli import NO_PROJECT_MESSAGE, NeatFile, configure_output


def test_sort_fail_no_project(tmp_path, create_file, capsys, mocker, debug):
    """Verify sort command fails when no project is configured."""
    # Given: A test file exists in the source directory
    file = create_file("this is a foo file.txt")

    # When: Running sort command without specifying a project
    args = ["sort", str(file), "-v"]
    with pytest.raises(cappa.Exit) as e:
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: Command fails with error and file remains in original location
    _, stderr = capsys.readouterr()
    assert NO_PROJECT_MESSAGE in stderr
    assert e.value.code == 1
    assert file.exists()


def test_sort_command_match(tmp_path, create_file, capsys, mocker, debug):
    """Verify sorting files into project folder based on name matching."""
    # Given: Mock questionary select to return first option
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = 0

    # Given: A test file exists
    file = create_file("this is a foo file.txt")

    # When: Running sort command
    args = ["sort", str(file), "--project", "mock_jd_project", "-v"]
    with pytest.raises(cappa.Exit):
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: File is moved to matching folder
    output = capsys.readouterr().out
    assert "this is a foo file.txt -> 10-19 foo/this is a foo file.txt" in output
    assert not file.exists()
    assert (tmp_path / "project" / "10-19 foo" / "this is a foo file.txt").exists()


def test_sort_command_jd_number(tmp_path, create_file, capsys, mocker, debug):
    """Verify sorting files into project folder based on Johnny Decimal number."""
    # Given: A test file exists
    file = create_file("this is a foo file.txt")

    # When: Running sort command with JD number term
    args = ["sort", str(file), "--project", "mock_jd_project", "--term", "11.03", "-v"]
    with pytest.raises(cappa.Exit):
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: File is moved to folder matching JD number
    output = capsys.readouterr().out
    debug(output)

    assert "this is a foo file.txt -> 10-19 foo/11 bar/11.03 koala/this is a foo file.txt" in output
    assert not file.exists()
    assert (
        tmp_path / "project" / "10-19 foo" / "11 bar" / "11.03 koala" / "this is a foo file.txt"
    ).exists()


def test_sort_dont_match_jd_number_in_filename(tmp_path, create_file, capsys, mocker, debug):
    """Verify JD numbers in filenames are not used for folder matching."""
    # Given: Mock questionary select to return first option
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = 0

    # Given: A file exists with a JD number in its name
    file = create_file("12.03 this is a foo file.txt")

    # When: Running sort command without explicit term
    args = ["sort", str(file), "--project", "mock_jd_project", "-vv"]
    with pytest.raises(cappa.Exit):
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: File is moved to matching folder
    output = capsys.readouterr().out
    # debug(output)

    assert "12.03 this is a foo file.txt -> 10-19 foo/12.03 this is a foo file.txt" in output
    assert not file.exists()
    assert (tmp_path / "project" / "10-19 foo" / "12.03 this is a foo file.txt").exists()


def test_sort_no_match(tmp_path, create_file, capsys, mocker, debug):
    """Verify handling when no matching folders are found."""
    # Given: A test file exists
    file = create_file("no matches.txt")

    # When: Running sort command
    args = ["sort", str(file), "--project", "mock_jd_project", "-vv"]
    with pytest.raises(cappa.Exit):
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: Error is shown and file remains in place
    _, stderr = capsys.readouterr()
    assert "No matching directories found for `no matches.txt`" in stderr
    assert file.exists()


def test_sort_command_match_term(tmp_path, create_file, capsys, mocker, debug):
    """Verify sorting files into project folder based on user-provided term."""
    # Given: Mock questionary select to return first option
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = 0

    # Given: A test file exists
    file = create_file("no matches.txt")

    # When: Running sort command with custom term
    args = ["sort", str(file), "--project", "mock_jd_project", "-v", "--term", "koala"]
    with pytest.raises(cappa.Exit):
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: File is moved to folder matching term
    stdout, _ = capsys.readouterr()
    assert "Found 2 possible folders" in stdout
    assert "no matches.txt -> 10-19 foo/11 bar/11.03 koala/no matches.txt" in stdout.replace(
        "\n", " "
    )
    assert not file.exists()
    assert (
        tmp_path / "project" / "10-19 foo" / "11 bar" / "11.03 koala" / "no matches.txt"
    ).exists()


def test_sort_command_single_match(tmp_path, create_file, capsys, mocker, debug):
    """Verify sorting files when exactly one matching folder is found."""
    # Given: A test file exists
    file = create_file("wheres_my_fox.txt")

    # When: Running sort command
    args = ["sort", str(file), "--project", "mock_jd_project", "-v"]
    with pytest.raises(cappa.Exit):
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: File is moved to single matching folder
    output = capsys.readouterr().out
    assert "wheres_my_fox.txt -> 20-29_bar/20_foo/20.04 fox/wheres_my_fox.txt" in output.replace(
        "\n", ""
    )
    assert not file.exists()
    assert (
        tmp_path / "project" / "20-29_bar" / "20_foo" / "20.04 fox" / "wheres_my_fox.txt"
    ).exists()


def test_sort_command_single_match_folder(tmp_path, create_file, capsys, mocker, debug):
    """Verify sorting files when exactly one matching folder is found."""
    # Given: A test file exists
    file = create_file("wheres_my_qux.txt")

    # When: Running sort command
    args = ["sort", str(file), "--project", "mock_folder_project", "-v"]
    with pytest.raises(cappa.Exit):
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: File is moved to single matching folder
    output = capsys.readouterr().out
    # debug(output)

    assert "wheres_my_qux.txt -> foo/bar/qux/wheres_my_qux.txt" in output
    assert not file.exists()
    assert (tmp_path / "project" / "foo" / "bar" / "qux" / "wheres_my_qux.txt").exists()


def test_sort_skips_unmatched_file_and_exits_non_zero(tmp_path, create_file, capsys, debug):
    """Verify one unmatched file does not stop the rest of the batch from being sorted."""
    # Given: One file with a single folder match and one with none
    matched = create_file("lazy dog.txt")
    unmatched = create_file("no matches.txt")

    # When: Sorting both in one run
    args = ["sort", str(matched), str(unmatched), "--project", "mock_jd_project"]
    with pytest.raises(cappa.Exit) as e:
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: The matched file moved, the unmatched file stayed, and the run reports failure
    stdout, stderr = capsys.readouterr()
    assert "No matching directories found for `no matches.txt`" in stderr
    assert "lazy dog.txt -> 40-49 dog/lazy dog.txt" in stdout
    assert not matched.exists()
    assert (tmp_path / "project" / "40-49 dog" / "lazy dog.txt").exists()
    assert unmatched.exists()
    assert e.value.code == 1


@pytest.mark.parametrize(
    ("extra_args", "expected_folder"),
    [
        pytest.param([], Path("20-29_bar", "20_foo", "20.04 fox"), id="project-terms"),
        pytest.param(["--term", "cat"], Path("20-29_bar", "22 cat"), id="cli-term-replaces"),
    ],
)
def test_project_user_terms_used_for_sorting(
    tmp_path, create_file, render_project_section, extra_args, expected_folder
):
    """Verify a project's user_terms match files to folders and --term flags replace them."""
    # Given: A project whose user_terms match one folder
    project_path = tmp_path / "project"
    with constants.DEV_CONFIG_PATH.open("a") as dev_config:
        dev_config.write(
            render_project_section(
                "terms_project",
                path=project_path,
                settings={"type": "jd", "user_terms": ["fox"]},
            )
        )
    file = create_file("no matches.txt")

    # When: Sorting a file whose name matches no folder
    args = ["sort", str(file), "--project", "terms_project", *extra_args]
    with pytest.raises(cappa.Exit) as e:
        invoke(obj=NeatFile, argv=args, deps=[configure_output])

    # Then: The file moves to the folder that the active terms match
    assert e.value.code == 0
    assert not file.exists()
    assert (project_path / expected_folder / "no matches.txt").exists()
