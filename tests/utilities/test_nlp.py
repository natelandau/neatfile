"""Tests for the similarity and lemmatization backend."""

from collections.abc import Generator
from pathlib import Path

import cappa
import pytest
from pytest_mock import MockerFixture

from neatfile.utils import nlp


@pytest.fixture(autouse=True)
def _clear_model_caches() -> Generator[None, None, None]:
    """Reset cached model state so each test observes its own environment."""
    nlp._model.cache_clear()
    nlp._embed.cache_clear()
    yield
    nlp._model.cache_clear()
    nlp._embed.cache_clear()


def test_model_dir_honors_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify the model directory follows NEATFILE_MODEL_DIR when set."""
    # Given: An override directory
    monkeypatch.setenv("NEATFILE_MODEL_DIR", str(tmp_path))

    # Then: The model lives in a named subdirectory of the override
    assert nlp.model_dir() == tmp_path / nlp.MODEL_DIR_NAME


def test_model_dir_defaults_to_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the model directory falls back to the XDG data directory."""
    # Given: No override
    monkeypatch.delenv("NEATFILE_MODEL_DIR", raising=False)

    # Then: The default is under DATA_DIR/models
    from neatfile.constants import DATA_DIR  # noqa: PLC0415

    assert nlp.model_dir() == DATA_DIR / "models" / nlp.MODEL_DIR_NAME


def test_ensure_model_skips_download_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MockerFixture
) -> None:
    """Verify a complete model directory is reused without any network call."""
    # Given: Every model file exists
    monkeypatch.setenv("NEATFILE_MODEL_DIR", str(tmp_path))
    target = tmp_path / nlp.MODEL_DIR_NAME
    target.mkdir()
    for name in nlp._MODEL_FILES:
        (target / name).touch()
    download = mocker.patch("neatfile.utils.nlp.snapshot_download")

    # When: Ensuring the model
    result = nlp.ensure_model()

    # Then: No download happened
    assert result == target
    download.assert_not_called()


def test_ensure_model_redownloads_partial_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MockerFixture
) -> None:
    """Verify a directory missing any model file is treated as incomplete."""
    # Given: Only some model files exist
    monkeypatch.setenv("NEATFILE_MODEL_DIR", str(tmp_path))
    target = tmp_path / nlp.MODEL_DIR_NAME
    target.mkdir()
    (target / "model.safetensors").touch()
    (target / "tokenizer.json").touch()
    download = mocker.patch("neatfile.utils.nlp.snapshot_download")

    # When: Ensuring the model
    nlp.ensure_model()

    # Then: The download runs to fill in the missing files
    download.assert_called_once()


def test_ensure_model_downloads_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MockerFixture
) -> None:
    """Verify a missing model triggers a pinned, filtered snapshot download into the model directory."""
    # Given: An empty override directory
    monkeypatch.setenv("NEATFILE_MODEL_DIR", str(tmp_path))
    download = mocker.patch("neatfile.utils.nlp.snapshot_download")

    # When: Ensuring the model
    result = nlp.ensure_model()

    # Then: The download targets the model directory with the allow-list
    assert result == tmp_path / nlp.MODEL_DIR_NAME
    download.assert_called_once()
    kwargs = download.call_args.kwargs
    assert kwargs["repo_id"] == nlp.MODEL_REPO
    assert kwargs["revision"] == nlp.MODEL_REVISION
    assert Path(kwargs["local_dir"]) == tmp_path / nlp.MODEL_DIR_NAME
    assert "model.safetensors" in kwargs["allow_patterns"]
    assert "tokenizer.json" in kwargs["allow_patterns"]


def test_ensure_model_download_failure_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MockerFixture, capsys
) -> None:
    """Verify a failed download exits non-zero and names the target directory."""
    # Given: The download raises
    monkeypatch.setenv("NEATFILE_MODEL_DIR", str(tmp_path / "models"))
    mocker.patch("neatfile.utils.nlp.snapshot_download", side_effect=OSError("offline"))

    # When: Ensuring the model
    with pytest.raises(cappa.Exit) as excinfo:
        nlp.ensure_model()

    # Then: Exit code 1 and the message points at the directory
    assert excinfo.value.code == 1
    assert "models/potion-base-8M" in capsys.readouterr().err


def test_model_load_failure_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mocker: MockerFixture, capsys
) -> None:
    """Verify an unloadable model directory exits non-zero and names the directory."""
    # Given: A complete-looking directory whose files cannot be loaded
    monkeypatch.setenv("NEATFILE_MODEL_DIR", str(tmp_path))
    target = tmp_path / nlp.MODEL_DIR_NAME
    target.mkdir()
    for name in nlp._MODEL_FILES:
        (target / name).touch()
    mocker.patch("neatfile.utils.nlp.StaticModel.from_pretrained", side_effect=ValueError("bad"))

    # When: Loading the model
    with pytest.raises(cappa.Exit) as excinfo:
        nlp._model()

    # Then: Exit code 1 and the message points at the directory
    assert excinfo.value.code == 1
    assert nlp.MODEL_DIR_NAME in capsys.readouterr().err


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("", ""),
        ("running", "run"),
        ("taxes", "tax"),
        ("Invoices", "invoice"),
        ("receipts", "receipt"),
        ("xyzzy123", "xyzzy123"),
    ],
)
def test_lemmatize(token: str, expected: str) -> None:
    """Verify lemmatization lowercases and reduces to the dictionary form."""
    assert nlp.lemmatize(token) == expected


def test_similarity_identical_tokens_is_one() -> None:
    """Verify identical tokens score 1.0 regardless of case."""
    assert nlp.similarity("Invoice", "invoice") == pytest.approx(1.0)


def test_similarity_is_symmetric_and_bounded() -> None:
    """Verify similarity is order-independent and clamped to the unit interval."""
    # When: Scoring a pair both ways and an unrelated pair
    forward = nlp.similarity("photo", "pictures")
    backward = nlp.similarity("pictures", "photo")
    unrelated = nlp.similarity("dog", "finance")

    # Then: Symmetric, related pair scores higher, everything within [0, 1]
    assert forward == pytest.approx(backward)
    assert forward > unrelated
    assert 0.0 <= unrelated <= 1.0
    assert 0.0 <= forward <= 1.0
