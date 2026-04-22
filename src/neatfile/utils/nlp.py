"""Natural language processing utilities."""

import importlib

import spacy
import spacy.cli
from nclutils import console

_MODEL_NAME = "en_core_web_md"

try:
    nlp = spacy.load(_MODEL_NAME)
except OSError:
    # Model missing from the environment (first run after `uv tool install`,
    # fresh pip install, etc). Fetch it via spaCy's installer rather than
    # declaring a direct-URL dependency, which PyPI rejects at upload.
    console.print(f"Downloading spaCy model '{_MODEL_NAME}' (one-time, ~40 MB)...")
    spacy.cli.download(_MODEL_NAME)
    # Newly pip-installed package isn't visible to the running interpreter
    # until import caches are invalidated.
    importlib.invalidate_caches()
    nlp = spacy.load(_MODEL_NAME)
