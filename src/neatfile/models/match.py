"""Dataclasses for neatfile."""

from dataclasses import dataclass

from neatfile.models import Folder


@dataclass
class MatchResult:
    """Result of matching a filename against a folder."""

    folder: Folder
    score: float
    matched_terms: set[str]
