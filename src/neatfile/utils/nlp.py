"""Word similarity and lemmatization backend."""

import os
from collections.abc import Sequence
from functools import cache
from pathlib import Path

import cappa
import numpy as np
import simplemma
from huggingface_hub import snapshot_download
from model2vec import StaticModel
from nclutils import pp

from neatfile.constants import DATA_DIR

MODEL_REPO = "minishlab/potion-base-8M"
# Pinned so every install embeds identically; the calibrated thresholds depend on these weights.
MODEL_REVISION = "bf8b056651a2c21b8d2565580b8569da283cab23"
MODEL_DIR_NAME = "potion-base-8M"
_MODEL_FILES = (
    "config.json",
    "model.safetensors",
    "modules.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
)
# Written after a verified download. Holds the revision so a pin change forces a fresh download.
_SENTINEL_NAME = ".neatfile-complete"


def model_dir() -> Path:
    """Return the directory that holds the similarity model.

    Returns:
        Path: `$NEATFILE_MODEL_DIR/potion-base-8M` when the variable is set, otherwise the model subdirectory of the user data directory.
    """
    override = os.getenv("NEATFILE_MODEL_DIR")
    base = Path(override).expanduser().absolute() if override else DATA_DIR / "models"
    return base / MODEL_DIR_NAME


def ensure_model() -> Path:
    """Download the similarity model on first use and return its directory.

    The model lives outside the virtualenv so package upgrades never remove it.

    Returns:
        Path: Directory containing the model files.

    Raises:
        cappa.Exit: If the model is absent and the download fails.
    """
    target = model_dir()
    sentinel = target / _SENTINEL_NAME
    if (
        sentinel.is_file()
        and sentinel.read_text() == MODEL_REVISION
        and _model_files_present(target)
    ):
        return target

    pp.info(f"Downloading similarity model '{MODEL_DIR_NAME}' (one-time, ~30 MB) to {target}")
    try:
        snapshot_download(
            repo_id=MODEL_REPO,
            revision=MODEL_REVISION,
            local_dir=str(target),
            allow_patterns=list(_MODEL_FILES),
        )
    except Exception as e:
        pp.error(f"Could not download '{MODEL_REPO}' to {target}: {e}")
        raise cappa.Exit(code=1) from e

    # Files land one at a time, so an interrupted download can leave missing or empty files behind.
    if not _model_files_present(target):
        pp.error(f"Similarity model download to {target} is incomplete.")
        pp.error("Delete that directory to download a fresh copy.")
        raise cappa.Exit(code=1)

    sentinel.write_text(MODEL_REVISION)
    return target


def _model_files_present(target: Path) -> bool:
    """Return True when every model file exists and is non-empty.

    Args:
        target (Path): The model directory.

    Returns:
        bool: Whether the file set looks complete.
    """
    return all(
        (target / name).is_file() and (target / name).stat().st_size > 0 for name in _MODEL_FILES
    )


@cache
def _model() -> StaticModel:
    """Load the similarity model once per process.

    Returns:
        StaticModel: The loaded static embedding model.

    Raises:
        cappa.Exit: If the model files exist but cannot be loaded.
    """
    target = ensure_model()
    try:
        return StaticModel.from_pretrained(str(target))
    except Exception as e:
        pp.error(f"Could not load similarity model from {target}: {e}")
        pp.error("Delete that directory to download a fresh copy.")
        raise cappa.Exit(code=1) from e


# Unit-length vectors keyed by lowercased token, filled in batches by embed().
_vectors: dict[str, np.ndarray] = {}


def embed(tokens: Sequence[str]) -> np.ndarray:
    """Embed tokens as unit vectors, encoding any unseen tokens in a single model call.

    Args:
        tokens (Sequence[str]): Words to embed. Case is ignored.

    Returns:
        np.ndarray: Matrix with one row per token, in input order. Rows are unit length, except for tokens the model cannot represent, which are all zeros.
    """
    lowered = [token.lower() for token in tokens]
    missing = list(dict.fromkeys(token for token in lowered if token not in _vectors))
    if missing:
        raw = _model().encode(missing)
        norms = np.linalg.norm(raw, axis=1, keepdims=True)
        unit = np.divide(raw, norms, out=np.zeros_like(raw), where=norms != 0)
        _vectors.update(zip(missing, unit, strict=True))

    if not lowered:
        return np.empty((0, _model().dim), dtype=np.float32)
    return np.stack([_vectors[token] for token in lowered])


def lemmatize(token: str) -> str:
    """Reduce a token to its English dictionary form.

    Args:
        token (str): Word to lemmatize. Case is ignored.

    Returns:
        str: Lowercase lemma, or the lowercase token itself when no dictionary entry exists.
    """
    if not token:  # simplemma rejects empty input
        return token
    return simplemma.lemmatize(token.lower(), lang="en")


def similarity(a: str, b: str) -> float:
    """Score how semantically close two single tokens are.

    Args:
        a (str): First token.
        b (str): Second token.

    Returns:
        float: Cosine similarity clamped to the range 0.0 to 1.0.
    """
    vec_a, vec_b = embed((a, b))
    cosine = float(np.dot(vec_a, vec_b))
    return min(max(cosine, 0.0), 1.0)
