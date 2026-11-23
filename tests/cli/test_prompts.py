"""Tests for interactive prompts when stdin has no input."""

import cappa
import pytest
from cappa.base import invoke

from neatfile.cli import NeatFile, configure_output
from neatfile.commands import CONFIRMATION_NO_INPUT_MESSAGE
from neatfile.views.prompts import FOLDER_SELECTION_NO_INPUT_MESSAGE


@pytest.mark.parametrize(
    ("mock_target", "file_name", "args", "expected_message"),
    [
        pytest.param(
            "questionary.select",
            "this is a foo file.txt",
            ["sort", "--project", "mock_jd_project"],
            FOLDER_SELECTION_NO_INPUT_MESSAGE.format(file_name="this is a foo file.txt"),
            id="folder-selection",
        ),
        pytest.param(
            "neatfile.commands.Confirm.ask",
            "file.TXT",
            ["clean", "--date-format", "", "--confirm"],
            CONFIRMATION_NO_INPUT_MESSAGE,
            id="confirmation",
        ),
    ],
)
def test_prompt_without_input_exits_with_error(
    create_file, capsys, mocker, mock_target, file_name, args, expected_message
):
    """Verify a prompt that gets end of input exits with an error and leaves the file in place."""
    # Given: A prompt that reaches end of input, as it does when stdin is not a terminal
    prompt = mocker.patch(mock_target)
    if mock_target == "questionary.select":
        prompt.return_value.ask.side_effect = EOFError
    else:
        prompt.side_effect = EOFError
    file = create_file(file_name)

    # When: Running the command
    with pytest.raises(cappa.Exit) as e:
        invoke(obj=NeatFile, argv=[*args, str(file)], deps=[configure_output])

    # Then: The command exits with an error message and does not touch the file
    _, stderr = capsys.readouterr()
    assert e.value.code == 1
    assert expected_message in stderr
    assert file.exists()
