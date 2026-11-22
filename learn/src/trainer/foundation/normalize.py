"""Normalize user-typed text before grading."""

from __future__ import annotations

import unicodedata


def normalize_latin(text: str) -> str:
    """NFC, trim and collapse whitespace, then casefold.

    The current Latin dataset is ASCII, so NFC is a no-op for clean data; it
    matters for pasted text with decomposed characters.  NFC does not remove
    accents: ``á`` is still different from ``a``.
    """
    text = unicodedata.normalize("NFC", text)
    text = " ".join(text.split())
    return text.casefold()


__all__ = ["normalize_latin"]
