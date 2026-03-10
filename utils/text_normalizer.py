"""
Centralized text normalization utility for consistent matching across all clients.

This module provides standardized text normalization functions that handle:
- Apostrophe variations (\u2018, \u2019 -> ')
- Quote variations (\u201c, \u201d -> ")
- Dash variations (\u2010, \u2012, \u2013, \u2014 -> -)
- Other punctuation removal
"""

import re


def normalize_text(text: str | None) -> str:
    """
    Normalize text for consistent matching across all clients.

    Normalizes common punctuation variations to their standard equivalents:
    - Apostrophes: \u2018 ('), \u2019 (') -> ' (straight apostrophe)
    - Quotes: \u201c ("), \u201d (") -> " (straight quote)
    - Dashes: \u2010 (‐), \u2012 (‒), \u2013 (–), \u2014 (—) -> - (hyphen-minus)
    - Removes other punctuation except spaces, apostrophes, and hyphens

    Args:
        text: The text to normalize (can be None)

    Returns:
        Normalized text string, or empty string if input is None/empty
    """
    if not text:
        return ""

    # Convert to lowercase and strip whitespace
    text = text.lower().strip()

    # Normalize common Unicode chars to ASCII equivalents (Motorhead vs Motörhead, etc.)
    _UNICODE_TO_ASCII = {
        "ö": "o",
        "ü": "u",
        "ä": "a",
        "ß": "ss",
        "ø": "o",
        "œ": "oe",
        "æ": "ae",
        "ñ": "n",
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "á": "a",
        "à": "a",
        "â": "a",
        "ã": "a",
        "å": "a",
        "í": "i",
        "ì": "i",
        "î": "i",
        "ï": "i",
        "ó": "o",
        "ò": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ù": "u",
        "û": "u",
        "ý": "y",
        "ÿ": "y",
        "ç": "c",
        "ð": "d",
        "þ": "th",
    }
    for uchar, ascii_char in _UNICODE_TO_ASCII.items():
        text = text.replace(uchar, ascii_char)

    # Normalize apostrophes (use Unicode escapes to ensure correct characters)
    text = text.replace("\u2019", "'").replace("\u2018", "'")

    # Normalize quotes (use Unicode escapes to ensure correct characters)
    text = text.replace("\u201c", '"').replace("\u201d", '"')

    # Normalize dashes (use Unicode escapes to ensure correct characters)
    text = (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2012", "-")
        .replace("\u2010", "-")
    )

    # Remove other punctuation except spaces and apostrophes
    text = re.sub(r"[^\w\s\'-]", "", text)

    # Replace multiple spaces with single space
    text = re.sub(r"\s+", " ", text)

    return text


def normalize_for_search(text: str | None) -> str:
    """
    Normalize text specifically for search operations.

    This is an alias for normalize_text() but makes the intent clearer
    when used in search contexts.

    Args:
        text: The text to normalize for search

    Returns:
        Normalized text string suitable for search operations
    """
    return normalize_text(text)


# Substrings that indicate an edition suffix (Deluxe, Remaster, Live, etc.)
# Used to strip parenthesized suffixes when matching release titles to avoid
# treating special editions as "new" when the base release exists in MusicBrainz.
# Conservative list to avoid false positives (e.g. "At the Drive-In" band name).
_EDITION_KEYWORDS = frozenset(
    {
        "deluxe",
        "remaster",
        "remastered",
        "live",
        "expanded",
        "anniversary",
        "reissue",
        "bonus",
        "special edition",
    }
)


def strip_edition_suffix(title: str | None) -> str:
    """
    Strip trailing parenthesized edition suffixes for matching purposes.
    E.g. "Album (Deluxe Edition)" -> "Album", "Album (2021 Remaster)" -> "Album".
    Only strips when the parenthesized content contains known edition keywords,
    to avoid false positives (e.g. "Album (At the Drive-In)" is not stripped).
    Returns the original string if no edition suffix is found.
    """
    if not title or not title.strip():
        return title or ""
    text = title.strip()
    while True:
        match = re.search(r"\s*\(([^)]+)\)\s*$", text)
        if not match:
            break
        inner = match.group(1).lower()
        if any(kw in inner for kw in _EDITION_KEYWORDS):
            text = text[: match.start()].rstrip()
        else:
            break
    return text


def normalize_for_indexing(text: str | None) -> str:
    """
    Normalize text specifically for indexing operations.

    This is an alias for normalize_text() but makes the intent clearer
    when used in indexing contexts.

    Args:
        text: The text to normalize for indexing

    Returns:
        Normalized text string suitable for indexing operations
    """
    return normalize_text(text)
